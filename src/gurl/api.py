"""Drive API fallback — Phase 3 (stub).

Planned: authenticate via Application Default Credentials (gcloud) first, then
fall back to a cached OAuth token, and resolve a path by walking folder names
through the Drive API. For now this returns None so resolution falls through to
a clear "not found" error.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .urls import DriveItem


def resolve_via_api(target: Path) -> Optional[DriveItem]:  # noqa: ARG001
    """Not yet implemented; returns None so local resolution stays authoritative."""
    return None
