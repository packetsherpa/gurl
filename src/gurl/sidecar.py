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

from .urls import EXT_TO_MIME, DriveItem


def is_native_sidecar(path: Path) -> bool:
    """True if the path looks like a Google-native sidecar file by extension."""
    return path.suffix.lower() in EXT_TO_MIME


def resolve_sidecar(path: Path) -> DriveItem | None:
    """Parse a native sidecar file into a DriveItem, or None if it isn't one.

    Returns None (rather than raising) when the file is not parseable as a
    sidecar, so the caller can fall through to database resolution.
    """
    if not is_native_sidecar(path) or not path.is_file():
        return None
    try:
        # Sidecars are tiny; cap the read so we never slurp a large misnamed file.
        data = json.loads(path.read_text(encoding="utf-8", errors="strict")[:65536])
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
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
    """Return a "url" value embedded directly in a sidecar, if present."""
    if not is_native_sidecar(path) or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="strict")[:65536])
    except (OSError, ValueError):
        return None
    url = data.get("url") if isinstance(data, dict) else None
    return url if isinstance(url, str) and url.startswith("http") else None
