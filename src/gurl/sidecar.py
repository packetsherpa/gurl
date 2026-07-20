"""Resolve Google-native files via their local sidecar JSON.

A `.gdoc` / `.gsheet` / `.gslides` / ... file on a Drive for Desktop mount is a
small JSON file that embeds the Drive object id directly, e.g.:

    {"doc_id": "1VmAE0...", "resource_key": "", "email": "user@example.com"}

Older clients wrote a "url" key instead. Either way we can build the web URL
with no database or network access.
"""

from __future__ import annotations

import json
from pathlib import Path

from .urls import EXT_TO_MIME, DriveItem, is_drive_web_url

# Sidecars are tiny JSON files; never read more than this from a file with a
# native extension (it may be an attacker-shared or misnamed large file).
_MAX_SIDECAR_BYTES = 65536


def is_native_sidecar(path: Path) -> bool:
    """True if the path looks like a Google-native sidecar file by extension."""
    return path.suffix.lower() in EXT_TO_MIME


def _load_sidecar(path: Path) -> dict | None:
    """Read a bounded prefix of a native sidecar and parse it as a JSON object.

    Returns None when the path isn't a native sidecar or can't be parsed. The
    read is capped at the byte level so a large file with a native extension
    never gets slurped whole into memory.
    """
    if not is_native_sidecar(path) or not path.is_file():
        return None
    try:
        with path.open("rb") as fh:
            raw = fh.read(_MAX_SIDECAR_BYTES)
        data = json.loads(raw.decode("utf-8", errors="strict"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def resolve_sidecar(path: Path) -> DriveItem | None:
    """Parse a native sidecar file into a DriveItem, or None if it isn't one.

    Returns None (rather than raising) when the file is not parseable as a
    sidecar, so the caller can fall through to database resolution.
    """
    data = _load_sidecar(path)
    if data is None:
        return None

    doc_id = data.get("doc_id")
    if not isinstance(doc_id, str) or not doc_id:
        return None

    return DriveItem(
        id=doc_id,
        mime_type=EXT_TO_MIME.get(path.suffix.lower()),
        is_folder=False,
        title=path.stem,
    )


def sidecar_direct_url(path: Path) -> str | None:
    """Return a "url" value embedded directly in a sidecar, if present.

    The URL is only returned when it points at a known Google web host over
    HTTPS; a sidecar can be attacker-controlled (shared into your Drive), so we
    never hand an arbitrary URL to the browser.
    """
    data = _load_sidecar(path)
    if data is None:
        return None
    url = data.get("url")
    if isinstance(url, str) and is_drive_web_url(url):
        return url
    return None
