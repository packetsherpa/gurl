"""Drive API fallback.

Used when a path is under a Drive mount but the local DriveFS database can't
resolve it (e.g. not yet synced, or the schema changed). We reuse the in-drive
path segments from the mount and walk them through the Drive API.

Authentication, in order:
  1. Application Default Credentials (gcloud). Requires the Drive scope, e.g.:
       gcloud auth application-default login \
         --scopes=openid,https://www.googleapis.com/auth/drive.readonly
  2. Cached OAuth installed-app flow. Requires an OAuth client config at
     $GURL_OAUTH_CLIENT or ~/.config/gurl/client_secret.json; the refresh
     token is cached at ~/.config/gurl/token.json.

The optional dependencies (``gurl[api]``) are imported lazily: if they are not
installed, this fallback quietly returns None and local resolution stays
authoritative.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import GurlError
from .drivefs import detect_mount
from .urls import EXT_TO_MIME, FOLDER_MIME, DriveItem

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def _config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "gurl"


def _api_available() -> bool:
    try:
        import google.auth  # noqa: F401
        import googleapiclient  # noqa: F401
    except ImportError:
        return False
    return True


def _load_credentials():
    """Return Drive credentials via ADC, else cached/interactive OAuth."""
    # 1. Application Default Credentials.
    try:
        import google.auth

        creds, _ = google.auth.default(scopes=SCOPES)
        return creds
    except Exception:  # noqa: BLE001 -- fall through to OAuth
        pass

    # 2. OAuth installed-app flow with an on-disk token cache.
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    cfg = _config_dir()
    token_path = cfg / "token.json"
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
            return creds

    client_path = os.environ.get("GURL_OAUTH_CLIENT") or str(cfg / "client_secret.json")
    if not Path(client_path).exists():
        raise GurlError(
            "Drive API fallback needs credentials. Either run "
            "`gcloud auth application-default login "
            "--scopes=openid,https://www.googleapis.com/auth/drive.readonly`, "
            f"or place an OAuth client config at {client_path} "
            "(or set $GURL_OAUTH_CLIENT)."
        )
    flow = InstalledAppFlow.from_client_secrets_file(client_path, SCOPES)
    creds = flow.run_local_server(port=0)
    cfg.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _q_escape(name: str) -> str:
    return name.replace("\\", "\\\\").replace("'", "\\'")


def _child_in(service, parent_id: str, name: str, *, drive_id: str | None):
    """Find a single child named ``name`` under ``parent_id``."""
    params = dict(
        q=f"'{parent_id}' in parents and name = '{_q_escape(name)}' and trashed = false",
        fields="files(id, name, mimeType)",
        pageSize=2,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    )
    if drive_id:
        params.update(corpora="drive", driveId=drive_id)
    files = service.files().list(**params).execute().get("files", [])
    if not files:
        return None
    return files[0]


def _find_shared_drive(service, name: str) -> str | None:
    resp = (
        service.drives()
        .list(q=f"name = '{_q_escape(name)}'", fields="drives(id, name)", pageSize=2)
        .execute()
    )
    drives = resp.get("drives", [])
    return drives[0]["id"] if drives else None


def resolve_via_api(target: Path) -> DriveItem | None:
    """Resolve a mounted path through the Drive API, or None if not applicable."""
    if not _api_available():
        return None
    split = detect_mount(target)
    if split is None:
        return None  # No mount => no in-drive path to walk.
    _root, segments = split
    if not segments:
        return None

    from googleapiclient.errors import HttpError

    try:
        return _resolve_segments_via_api(segments)
    except HttpError as exc:
        raise GurlError(_explain_http_error(exc)) from exc


def _explain_http_error(exc) -> str:
    """Turn a Drive API HttpError into an actionable message by its real reason."""
    status = str(getattr(exc, "status_code", None) or getattr(exc.resp, "status", None))
    low = str(exc).lower()

    if status == "401":
        return (
            "Drive API returned 401 (credentials expired or invalid). "
            "Re-authenticate and try again."
        )

    if status == "403":
        if any(s in low for s in ("has not been used", "it is disabled", "accessnotconfigured")):
            return (
                "Drive API is not enabled in your ADC quota project. Enable it:\n"
                "  gcloud services enable drive.googleapis.com "
                "--project=<your-project>"
            )
        if "quota project" in low:
            return (
                "ADC needs a quota project with the Drive API enabled. Set one:\n"
                "  gcloud auth application-default set-quota-project <your-project>"
            )
        if "insufficient" in low or "scope" in low:
            return (
                "Drive API returned 403 (insufficient scopes). Re-authenticate "
                "with the Drive scope:\n  gcloud auth application-default login "
                "--scopes=openid,https://www.googleapis.com/auth/drive.readonly"
            )
    return f"Drive API request failed: {exc}"


def _resolve_segments_via_api(segments: list[str]) -> DriveItem | None:
    creds = _load_credentials()
    from googleapiclient.discovery import build

    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    drive_id: str | None = None
    if segments[0] == "Shared drives":
        if len(segments) < 2:
            raise GurlError(
                "Path points at the 'Shared drives' container; "
                "descend into a specific shared drive."
            )
        drive_id = _find_shared_drive(service, segments[1])
        if not drive_id:
            return None
        parent_id = drive_id
        rest = segments[2:]
        if not rest:  # the shared drive root itself
            return DriveItem(id=drive_id, mime_type=FOLDER_MIME, is_folder=True, title=segments[1])
    else:
        parent_id = "root"
        rest = segments[1:] if segments[0] == "My Drive" else segments
        if not rest:  # My Drive root
            root = service.files().get(fileId="root", fields="id").execute()
            return DriveItem(id=root["id"], mime_type=FOLDER_MIME, is_folder=True, title="My Drive")

    node = None
    for i, name in enumerate(rest):
        # The final segment may be a native file whose local name carries a
        # synthetic extension (.gdoc) absent from the Drive title.
        if i == len(rest) - 1 and Path(name).suffix.lower() in EXT_TO_MIME:
            name = Path(name).stem
        node = _child_in(service, parent_id, name, drive_id=drive_id)
        if node is None:
            return None
        parent_id = node["id"]

    if node is None:
        return None
    mime = node.get("mimeType")
    return DriveItem(
        id=node["id"],
        mime_type=mime,
        is_folder=mime == FOLDER_MIME,
        title=node.get("name"),
    )
