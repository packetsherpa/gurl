"""Shared fixtures: a synthetic DriveFS metadata DB mirroring the real schema."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

# Minimal subset of the real DriveFS schema needed for resolution.
_SCHEMA = """
CREATE TABLE items (
    stable_id INTEGER PRIMARY KEY NOT NULL,
    id TEXT UNIQUE NOT NULL,
    trashed BOOLEAN NOT NULL DEFAULT 0,
    is_owner BOOLEAN NOT NULL DEFAULT 1,
    mime_type TEXT NOT NULL DEFAULT '',
    is_folder BOOLEAN NOT NULL DEFAULT 0,
    is_tombstone BOOLEAN NOT NULL DEFAULT 0,
    local_title TEXT,
    team_drive_stable_id INTEGER
);
CREATE TABLE stable_parents (
    item_stable_id INTEGER NOT NULL,
    parent_stable_id INTEGER NOT NULL,
    local_title_hash INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (item_stable_id, parent_stable_id)
);
CREATE TABLE shortcut_details (
    shortcut_stable_id INTEGER PRIMARY KEY NOT NULL,
    target_stable_id INTEGER NOT NULL,
    target_mime_type TEXT NOT NULL
);
"""

FOLDER = "application/vnd.google-apps.folder"
DOC = "application/vnd.google-apps.document"
SHORTCUT = "application/vnd.google-apps.shortcut"


def _item(
    cur, stable_id, drive_id, title, *, folder=False, mime="", team=None, trashed=0, tombstone=0
):
    cur.execute(
        "INSERT INTO items (stable_id, id, mime_type, is_folder, is_tombstone, "
        "trashed, local_title, team_drive_stable_id) VALUES (?,?,?,?,?,?,?,?)",
        (stable_id, drive_id, mime, int(folder), int(tombstone), int(trashed), title, team),
    )


def _parent(cur, child, parent):
    cur.execute(
        "INSERT INTO stable_parents (item_stable_id, parent_stable_id) VALUES (?,?)",
        (child, parent),
    )


def _shortcut(cur, shortcut_stable_id, target_stable_id, target_mime):
    cur.execute(
        "INSERT INTO shortcut_details (shortcut_stable_id, target_stable_id, "
        "target_mime_type) VALUES (?,?,?)",
        (shortcut_stable_id, target_stable_id, target_mime),
    )


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    """Build a small DriveFS-like DB and return its path.

    Tree:
      My Drive (101, id=ROOT_MYDRIVE, team NULL)
        Reports (200, folder)
          Q3.pdf (201, binary)
          notes (202, google doc)
        dup (300, folder)  +  dup (301, folder)  <- duplicate names
        Team Docs Link (600, shortcut) -> Team Docs (700, folder, id=ID_TEAMDOCS)
      Team Docs (700, folder) [target of the shortcut]
        brief.pdf (701, binary)
      Shared drives (virtual)
        Team (500, id=TD_TEAM, team=500)
          spec.pdf (501, binary)
    """
    db = tmp_path / "metadata_sqlite_db"
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.executescript(_SCHEMA)

    _item(cur, 101, "ROOT_MYDRIVE", "My Drive", folder=True, mime=FOLDER, team=None)
    _item(cur, 200, "ID_REPORTS", "Reports", folder=True, mime=FOLDER)
    _item(cur, 201, "ID_Q3PDF", "Q3.pdf", mime="application/pdf")
    _item(cur, 202, "ID_NOTES", "notes", mime=DOC)
    _item(cur, 300, "ID_DUP_A", "dup", folder=True, mime=FOLDER)
    _item(cur, 301, "ID_DUP_B", "dup", folder=True, mime=FOLDER)
    # A shortcut in My Drive pointing at the Team Docs folder.
    _item(cur, 600, "ID_SHORTCUT", "Team Docs Link", mime=SHORTCUT)
    _item(cur, 700, "ID_TEAMDOCS", "Team Docs", folder=True, mime=FOLDER)
    _item(cur, 701, "ID_BRIEF", "brief.pdf", mime="application/pdf")
    _shortcut(cur, 600, 700, FOLDER)
    # Shared drive root: stable_id == team_drive_stable_id
    _item(cur, 500, "TD_TEAM", "Team", folder=True, mime=FOLDER, team=500)
    _item(cur, 501, "ID_SPEC", "spec.pdf", mime="application/pdf", team=500)

    for child, parent in [
        (200, 101),
        (201, 200),
        (202, 200),
        (300, 101),
        (301, 101),
        (600, 101),
        (701, 700),
        (501, 500),
    ]:
        _parent(cur, child, parent)

    conn.commit()
    conn.close()
    return db
