"""Top-level resolution: local path -> Drive web URL.

Order (hybrid strategy):
  1. Native sidecar JSON (.gdoc/.gsheet/...) — fastest, no DB/network.
  2. DriveFS local metadata database — folders and binary files.
  3. Drive API fallback — Phase 3 (not yet wired in).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import GurlError
from .drivefs import resolve_via_drivefs
from .sidecar import resolve_sidecar, sidecar_direct_url
from .urls import DriveItem, url_for


@dataclass
class Resolution:
    url: str
    item: DriveItem | None
    source: str  # "sidecar" | "drivefs" | "api"


SOURCES = ("auto", "sidecar", "drivefs", "api")


def resolve(path: Path, source: str = "auto") -> Resolution:
    """Resolve a local path to its Drive URL, or raise GurlError.

    ``source`` selects the resolution strategy: ``auto`` (default) tries each in
    order; ``sidecar``/``drivefs``/``api`` force a single strategy (useful for
    testing and comparison).
    """
    target = path.expanduser()
    if not target.exists():
        raise GurlError(f"No such file or directory: {path}")
    target = target.resolve()

    # 1. Native sidecar: an embedded "url" wins outright; else build from doc_id.
    if source in ("auto", "sidecar"):
        direct = sidecar_direct_url(target)
        if direct:
            return Resolution(url=direct, item=None, source="sidecar")
        item = resolve_sidecar(target)
        if item is not None:
            return Resolution(url=url_for(item), item=item, source="sidecar")

    # 2. DriveFS metadata database (folders + binary files).
    if source in ("auto", "drivefs"):
        item = resolve_via_drivefs(target)
        if item is not None:
            return Resolution(url=url_for(item), item=item, source="drivefs")

    # 3. Drive API fallback.
    if source in ("auto", "api"):
        from .api import _api_available, resolve_via_api  # lazy: optional dependency

        if source == "api" and not _api_available():
            raise GurlError(
                "Drive API support isn't installed. Install it with "
                "`uv tool install --force '.[api]'` (or `pip install 'gurl[api]'`)."
            )
        item = resolve_via_api(target)
        if item is not None:
            return Resolution(url=url_for(item), item=item, source="api")

    raise GurlError(
        f"Could not resolve a Google Drive URL for: {path} (source={source}).\n"
        "It may not be inside a Google Drive for Desktop mount, it isn't synced "
        "yet, or the chosen source can't resolve it."
    )
