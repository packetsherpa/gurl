"""Map a resolved Drive item to a type-specific web URL."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from . import GurlError

# Drive object ids are URL-safe base64-ish tokens. Reject anything else before
# interpolating into a URL so a crafted id can't inject path/query segments.
_VALID_ID = re.compile(r"^[A-Za-z0-9_-]+$")

# Web hosts a resolved URL is ever allowed to point at. Used to vet the "url"
# value embedded in a (possibly attacker-controlled) sidecar file.
ALLOWED_URL_HOSTS = frozenset(
    {
        "docs.google.com",
        "drive.google.com",
        "script.google.com",
        "sites.google.com",
    }
)


def is_drive_web_url(url: str) -> bool:
    """True if ``url`` is an HTTPS URL on a known Google web host."""
    try:
        parts = urlparse(url)
    except ValueError:
        return False
    return parts.scheme == "https" and parts.hostname in ALLOWED_URL_HOSTS

# mime_type -> (docs host path). Google-native editor URLs.
_EDITOR_PATHS = {
    "application/vnd.google-apps.document": "https://docs.google.com/document/d/{id}/edit",
    "application/vnd.google-apps.spreadsheet": "https://docs.google.com/spreadsheets/d/{id}/edit",
    "application/vnd.google-apps.presentation": "https://docs.google.com/presentation/d/{id}/edit",
    "application/vnd.google-apps.form": "https://docs.google.com/forms/d/{id}/edit",
    "application/vnd.google-apps.drawing": "https://docs.google.com/drawings/d/{id}/edit",
    "application/vnd.google-apps.script": "https://script.google.com/d/{id}/edit",
    "application/vnd.google-apps.site": "https://sites.google.com/d/{id}/edit",
}

# Google Drive native-file extensions -> mime_type. Used when resolving via the
# sidecar JSON, where we know the extension but not always the mime.
EXT_TO_MIME = {
    ".gdoc": "application/vnd.google-apps.document",
    ".gsheet": "application/vnd.google-apps.spreadsheet",
    ".gslides": "application/vnd.google-apps.presentation",
    ".gform": "application/vnd.google-apps.form",
    ".gdraw": "application/vnd.google-apps.drawing",
    ".gscript": "application/vnd.google-apps.script",
    ".gsite": "application/vnd.google-apps.site",
}

FOLDER_MIME = "application/vnd.google-apps.folder"
SHORTCUT_MIME = "application/vnd.google-apps.shortcut"


@dataclass
class DriveItem:
    """A resolved Drive object."""

    id: str
    mime_type: str | None = None
    is_folder: bool = False
    title: str | None = None


def url_for(item: DriveItem) -> str:
    """Return the best web URL for a resolved Drive item."""
    if not _VALID_ID.match(item.id or ""):
        raise GurlError(f"Refusing to build a URL for a malformed Drive id: {item.id!r}")
    if item.mime_type in _EDITOR_PATHS:
        return _EDITOR_PATHS[item.mime_type].format(id=item.id)
    if item.is_folder or item.mime_type == FOLDER_MIME:
        return f"https://drive.google.com/drive/folders/{item.id}"
    if item.mime_type:  # a known non-native, non-folder file
        return f"https://drive.google.com/file/d/{item.id}/view"
    # Unknown type: let Google redirect to the right viewer.
    return f"https://drive.google.com/open?id={item.id}"
