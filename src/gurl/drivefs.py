"""Resolve folders and binary files via the DriveFS local metadata database.

Google Drive for Desktop keeps a SQLite database mapping each synced object to
its Drive id. We open it strictly read-only (``immutable=1``) so we never lock
or perturb the running client.

Key facts (verified against Drive for Desktop on macOS):
  * ``items(stable_id PK, id, mime_type, is_folder, team_drive_stable_id,
    local_title, trashed, is_tombstone)`` — ``id`` is the Drive object id.
  * ``stable_parents(item_stable_id, parent_stable_id)`` — the folder tree.
  * The FUSE mount inode is NOT the ``stable_id`` and has no stable mapping, so
    we resolve by walking the path segments by name from a known root.
  * A Shared Drive's root row has ``stable_id == team_drive_stable_id``.
  * Shortcuts (``mime_type`` ``...google-apps.shortcut``) point at a target via
    ``shortcut_details(shortcut_stable_id, target_stable_id, target_mime_type)``.
    On disk they are symlinks into ``.shortcut-targets-by-id/<TARGET_DRIVE_ID>/``,
    so a resolved path can arrive there directly (the id is in the path).

This module is macOS-focused but keeps OS-specific locations behind small
functions so Windows support can slot in later.
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from . import GurlError
from .urls import SHORTCUT_MIME, DriveItem

# Symlinked shortcut targets live under this dir at the mount root; the path
# segment immediately after it is the target's Drive id.
SHORTCUT_TARGETS_DIR = ".shortcut-targets-by-id"

# ---------------------------------------------------------------------------
# OS-specific locations
# ---------------------------------------------------------------------------


def _drivefs_support_dir() -> Path | None:
    """Directory holding per-account DriveFS metadata, or None on this OS."""
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Google/DriveFS"
    if sys.platform.startswith("win"):
        import os

        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "Google/DriveFS"
    return None


def _mount_roots() -> list[Path]:
    """Candidate Drive for Desktop mount roots on this OS."""
    roots: list[Path] = []
    if sys.platform == "darwin":
        cloud = Path.home() / "Library/CloudStorage"
        if cloud.is_dir():
            roots.extend(sorted(cloud.glob("GoogleDrive-*")))
        legacy = Path("/Volumes/GoogleDrive")
        if legacy.is_dir():
            roots.append(legacy)
    # Windows drive-letter mounts are discovered lazily in detect_mount().
    return roots


def find_account_dbs() -> list[Path]:
    """All available DriveFS metadata databases, one per signed-in account."""
    support = _drivefs_support_dir()
    if not support or not support.is_dir():
        return []
    dbs = []
    for child in sorted(support.iterdir()):
        if child.is_dir() and child.name.isdigit():
            db = child / "metadata_sqlite_db"
            if db.is_file():
                dbs.append(db)
    return dbs


# ---------------------------------------------------------------------------
# Path -> (mount, in-drive segments)
# ---------------------------------------------------------------------------


def detect_mount(target: Path) -> tuple[Path, list[str]] | None:
    """Split an absolute path into (mount_root, segments_within_mount).

    ``segments`` are the path parts under the mount, e.g.
    ``["My Drive", "Reports", "Q3.pdf"]`` or
    ``["Shared drives", "Team", "spec.pdf"]``. Returns None if the path is not
    under a known Drive mount.
    """
    target = target.resolve()
    for root in _mount_roots():
        try:
            rel = target.relative_to(root)
        except ValueError:
            continue
        return root, [p for p in rel.parts if p not in (".", "")]
    return None


# ---------------------------------------------------------------------------
# Database walk
# ---------------------------------------------------------------------------


@dataclass
class _Row:
    stable_id: int
    id: str
    is_folder: bool
    mime_type: str


class DriveDB:
    """Read-only accessor over a single account's metadata database."""

    def __init__(self, db_path: Path):
        self.path = db_path
        # immutable=1: open without locks and without touching WAL; safe while
        # Drive for Desktop is running.
        uri = f"file:{db_path}?immutable=1"
        self._conn = sqlite3.connect(uri, uri=True)
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> DriveDB:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- lookups -----------------------------------------------------------

    def _mydrive_root(self) -> _Row | None:
        """The My Drive root: titled 'My Drive' with no owning team drive."""
        cur = self._conn.execute(
            "SELECT stable_id, id, is_folder, mime_type FROM items "
            "WHERE local_title = 'My Drive' AND team_drive_stable_id IS NULL "
            "AND is_folder = 1 AND is_tombstone = 0 LIMIT 1"
        )
        r = cur.fetchone()
        return _Row(r["stable_id"], r["id"], bool(r["is_folder"]), r["mime_type"]) if r else None

    def _shared_drive_root(self, title: str) -> _Row | None:
        """A Shared Drive root: its row has stable_id == team_drive_stable_id."""
        cur = self._conn.execute(
            "SELECT stable_id, id, is_folder, mime_type FROM items "
            "WHERE local_title = ? AND stable_id = team_drive_stable_id "
            "AND is_tombstone = 0 LIMIT 1",
            (title,),
        )
        r = cur.fetchone()
        return _Row(r["stable_id"], r["id"], bool(r["is_folder"]), r["mime_type"]) if r else None

    def _children_named(self, parent_stable_id: int, name: str) -> list[_Row]:
        cur = self._conn.execute(
            "SELECT i.stable_id, i.id, i.is_folder, i.mime_type "
            "FROM items i JOIN stable_parents sp "
            "  ON sp.item_stable_id = i.stable_id "
            "WHERE sp.parent_stable_id = ? AND i.local_title = ? "
            "  AND i.trashed = 0 AND i.is_tombstone = 0",
            (parent_stable_id, name),
        )
        return [
            _Row(r["stable_id"], r["id"], bool(r["is_folder"]), r["mime_type"])
            for r in cur.fetchall()
        ]

    def _by_drive_id(self, drive_id: str) -> _Row | None:
        cur = self._conn.execute(
            "SELECT stable_id, id, is_folder, mime_type FROM items "
            "WHERE id = ? AND is_tombstone = 0 LIMIT 1",
            (drive_id,),
        )
        r = cur.fetchone()
        return _Row(r["stable_id"], r["id"], bool(r["is_folder"]), r["mime_type"]) if r else None

    def _follow_shortcut(self, row: _Row) -> _Row:
        """If ``row`` is a shortcut, resolve to its target; else return it.

        Falls back to the shortcut's own id when the target isn't in the local
        DB — opening a shortcut's own Drive URL redirects to the target.
        """
        if row.mime_type != SHORTCUT_MIME:
            return row
        cur = self._conn.execute(
            "SELECT t.stable_id, t.id, t.is_folder, t.mime_type "
            "FROM shortcut_details sd JOIN items t "
            "  ON t.stable_id = sd.target_stable_id "
            "WHERE sd.shortcut_stable_id = ? AND t.is_tombstone = 0",
            (row.stable_id,),
        )
        r = cur.fetchone()
        if r is None:
            return row
        return _Row(r["stable_id"], r["id"], bool(r["is_folder"]), r["mime_type"])

    def _start_node(self, segments: list[str]) -> tuple[_Row | None, list[str]]:
        """Resolve the anchor row and the remaining child segments to walk."""
        top = segments[0]
        if top == SHORTCUT_TARGETS_DIR:
            # <mount>/.shortcut-targets-by-id/<TARGET_DRIVE_ID>/<name>[/child...]
            # The id names the target root; the next segment is its own name.
            if len(segments) < 2:
                return None, []
            drive_id = segments[1]
            root = self._by_drive_id(drive_id)
            if root is None:
                # Target not synced locally; anchor directly on the Drive id so
                # the caller can emit a redirecting URL (no children to walk).
                return _Row(-1, drive_id, is_folder=False, mime_type=""), []
            return root, segments[3:]
        if top == "Shared drives":
            if len(segments) < 2:
                raise GurlError(
                    "Path points at the 'Shared drives' container; "
                    "descend into a specific shared drive."
                )
            return self._shared_drive_root(segments[1]), segments[2:]
        if top == "My Drive":
            return self._mydrive_root(), segments[1:]
        # Some setups mount My Drive contents at the top level.
        return self._mydrive_root(), segments

    def resolve_segments(self, segments: list[str]) -> DriveItem | None:
        """Walk in-drive path segments to the target item, or None if absent."""
        if not segments:
            return None

        current, rest = self._start_node(segments)
        if current is None:
            return None

        for name in rest:
            matches = self._children_named(current.stable_id, name)
            if not matches:
                return None
            if len(matches) > 1:
                print(
                    f"gurl: warning: {len(matches)} items named {name!r} in the "
                    "same folder; using the first.",
                    file=sys.stderr,
                )
            current = matches[0]

        # A resolved item may itself be a shortcut; open the target instead.
        if current.stable_id >= 0:
            current = self._follow_shortcut(current)

        return DriveItem(
            id=current.id,
            mime_type=current.mime_type or None,
            is_folder=current.is_folder,
            title=segments[-1],
        )


def resolve_via_drivefs(target: Path) -> DriveItem | None:
    """Resolve a path through any account's DriveFS DB, or None if not found."""
    split = detect_mount(target)
    if split is None:
        return None
    _root, segments = split

    dbs = find_account_dbs()
    if not dbs:
        raise GurlError(
            "Path is under a Drive mount but no DriveFS metadata database was "
            "found. Is Google Drive for Desktop installed and signed in?"
        )

    for db_path in dbs:
        try:
            with DriveDB(db_path) as db:
                item = db.resolve_segments(segments)
        except sqlite3.DatabaseError as exc:
            raise GurlError(f"Could not read DriveFS database: {exc}") from exc
        if item is not None:
            return item
    return None
