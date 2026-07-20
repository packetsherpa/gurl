import pytest

from gurl import GurlError, drivefs
from gurl.drivefs import DriveDB, detect_mount


def test_walk_mydrive_folder(fixture_db):
    with DriveDB(fixture_db) as db:
        item = db.resolve_segments(["My Drive", "Reports"])
    assert item.id == "ID_REPORTS"
    assert item.is_folder


def test_walk_mydrive_binary_file(fixture_db):
    with DriveDB(fixture_db) as db:
        item = db.resolve_segments(["My Drive", "Reports", "Q3.pdf"])
    assert item.id == "ID_Q3PDF"
    assert not item.is_folder
    assert item.mime_type == "application/pdf"


def test_walk_mydrive_root(fixture_db):
    with DriveDB(fixture_db) as db:
        item = db.resolve_segments(["My Drive"])
    assert item.id == "ROOT_MYDRIVE"


def test_walk_shared_drive_file(fixture_db):
    with DriveDB(fixture_db) as db:
        item = db.resolve_segments(["Shared drives", "Team", "spec.pdf"])
    assert item.id == "ID_SPEC"


def test_walk_shared_drive_root(fixture_db):
    with DriveDB(fixture_db) as db:
        item = db.resolve_segments(["Shared drives", "Team"])
    assert item.id == "TD_TEAM"


def test_shared_drives_container_errors(fixture_db):
    with DriveDB(fixture_db) as db:
        with pytest.raises(GurlError):
            db.resolve_segments(["Shared drives"])


def test_missing_path_returns_none(fixture_db):
    with DriveDB(fixture_db) as db:
        assert db.resolve_segments(["My Drive", "Nope"]) is None


def test_duplicate_names_warn_and_pick_first(fixture_db, capsys):
    with DriveDB(fixture_db) as db:
        item = db.resolve_segments(["My Drive", "dup"])
    assert item.id in {"ID_DUP_A", "ID_DUP_B"}
    assert "2 items named" in capsys.readouterr().err


def test_final_item_shortcut_follows_target(fixture_db):
    # Walking to the shortcut item itself resolves to its target folder.
    with DriveDB(fixture_db) as db:
        item = db.resolve_segments(["My Drive", "Team Docs Link"])
    assert item.id == "ID_TEAMDOCS"
    assert item.is_folder


def test_shortcut_targets_by_id_anchor(fixture_db):
    # realpath rewrites a folder shortcut to .shortcut-targets-by-id/<id>/<name>.
    with DriveDB(fixture_db) as db:
        item = db.resolve_segments([".shortcut-targets-by-id", "ID_TEAMDOCS", "Team Docs"])
    assert item.id == "ID_TEAMDOCS"
    assert item.is_folder


def test_shortcut_targets_by_id_with_child(fixture_db):
    with DriveDB(fixture_db) as db:
        item = db.resolve_segments(
            [".shortcut-targets-by-id", "ID_TEAMDOCS", "Team Docs", "brief.pdf"]
        )
    assert item.id == "ID_BRIEF"
    assert not item.is_folder


def test_shortcut_target_not_synced_locally(fixture_db):
    # Unknown Drive id in the path: anchor on it and let Drive redirect.
    with DriveDB(fixture_db) as db:
        item = db.resolve_segments([".shortcut-targets-by-id", "UNKNOWN_ID", "whatever"])
    assert item.id == "UNKNOWN_ID"
    assert item.mime_type is None  # -> url_for emits open?id=UNKNOWN_ID


def test_detect_mount_splits_segments(tmp_path, monkeypatch):
    mount = tmp_path / "GoogleDrive-user@example.com"
    target = mount / "My Drive" / "Reports"
    target.mkdir(parents=True)
    monkeypatch.setattr(drivefs, "_mount_roots", lambda: [mount])
    root, segments = detect_mount(target)
    assert root == mount
    assert segments == ["My Drive", "Reports"]


def test_detect_mount_outside_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(drivefs, "_mount_roots", lambda: [tmp_path / "GoogleDrive-x"])
    assert detect_mount(tmp_path / "elsewhere") is None
