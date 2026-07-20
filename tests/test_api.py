"""Tests for the Drive API fallback using a fake service (no real deps)."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from gurl import api
from gurl.urls import FOLDER_MIME


def test_q_escape():
    assert api._q_escape("O'Brien") == "O\\'Brien"
    assert api._q_escape("a\\b") == "a\\\\b"


def test_returns_none_when_api_unavailable(monkeypatch):
    monkeypatch.setattr(api, "_api_available", lambda: False)
    assert api.resolve_via_api(Path("/whatever")) is None


def test_returns_none_when_not_under_mount(monkeypatch):
    monkeypatch.setattr(api, "_api_available", lambda: True)
    monkeypatch.setattr(api, "detect_mount", lambda _t: None)
    assert api.resolve_via_api(Path("/whatever")) is None


# --- fake Drive service -----------------------------------------------------


class _FakeExec:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class _FakeFiles:
    def __init__(self, tree):
        self._tree = tree  # {(parent_id, name): {id, name, mimeType}}

    def list(self, *, q, **_):
        # q looks like: '<parent>' in parents and name = '<name>' and trashed...
        parent = q.split("'", 2)[1]
        name = q.split("name = '", 1)[1].split("'", 1)[0]
        hit = self._tree.get((parent, name))
        return _FakeExec({"files": [hit] if hit else []})

    def get(self, *, fileId, **_):
        return _FakeExec({"id": "REAL_ROOT" if fileId == "root" else fileId})


class _FakeDrives:
    def __init__(self, drives):
        self._drives = drives  # {name: id}

    def list(self, *, q, **_):
        name = q.split("name = '", 1)[1].split("'", 1)[0]
        did = self._drives.get(name)
        return _FakeExec({"drives": [{"id": did, "name": name}] if did else []})


class _FakeService:
    def __init__(self, tree, drives):
        self._files = _FakeFiles(tree)
        self._drives = _FakeDrives(drives)

    def files(self):
        return self._files

    def drives(self):
        return self._drives


@pytest.fixture
def fake_build(monkeypatch):
    """Install a fake googleapiclient.discovery.build and stub auth."""
    monkeypatch.setattr(api, "_api_available", lambda: True)
    monkeypatch.setattr(api, "_load_credentials", lambda: object())

    tree = {
        ("root", "Reports"): {"id": "ID_REPORTS", "name": "Reports", "mimeType": FOLDER_MIME},
        ("ID_REPORTS", "Q3.pdf"): {"id": "ID_Q3", "name": "Q3.pdf", "mimeType": "application/pdf"},
        ("ID_REPORTS", "Plan"): {
            "id": "ID_PLAN", "name": "Plan",
            "mimeType": "application/vnd.google-apps.document",
        },
        ("TD_TEAM", "spec.pdf"): {"id": "ID_SPEC", "name": "spec.pdf", "mimeType": "application/pdf"},
    }
    service = _FakeService(tree, drives={"Team": "TD_TEAM"})

    fake_disc = types.ModuleType("googleapiclient.discovery")
    fake_disc.build = lambda *a, **k: service
    fake_pkg = types.ModuleType("googleapiclient")
    fake_pkg.discovery = fake_disc
    monkeypatch.setitem(sys.modules, "googleapiclient", fake_pkg)
    monkeypatch.setitem(sys.modules, "googleapiclient.discovery", fake_disc)
    return service


def _mount(monkeypatch, segments):
    monkeypatch.setattr(api, "detect_mount", lambda _t: (Path("/mnt"), segments))


def test_walk_mydrive_file(fake_build, monkeypatch):
    _mount(monkeypatch, ["My Drive", "Reports", "Q3.pdf"])
    item = api.resolve_via_api(Path("/mnt/My Drive/Reports/Q3.pdf"))
    assert item.id == "ID_Q3"
    assert not item.is_folder


def test_walk_native_file_strips_extension(fake_build, monkeypatch):
    _mount(monkeypatch, ["My Drive", "Reports", "Plan.gdoc"])
    item = api.resolve_via_api(Path("/mnt/My Drive/Reports/Plan.gdoc"))
    assert item.id == "ID_PLAN"


def test_walk_mydrive_root(fake_build, monkeypatch):
    _mount(monkeypatch, ["My Drive"])
    item = api.resolve_via_api(Path("/mnt/My Drive"))
    assert item.id == "REAL_ROOT"
    assert item.is_folder


def test_walk_shared_drive_file(fake_build, monkeypatch):
    _mount(monkeypatch, ["Shared drives", "Team", "spec.pdf"])
    item = api.resolve_via_api(Path("/mnt/Shared drives/Team/spec.pdf"))
    assert item.id == "ID_SPEC"


def test_walk_shared_drive_root(fake_build, monkeypatch):
    _mount(monkeypatch, ["Shared drives", "Team"])
    item = api.resolve_via_api(Path("/mnt/Shared drives/Team"))
    assert item.id == "TD_TEAM"
    assert item.is_folder


def test_walk_missing_returns_none(fake_build, monkeypatch):
    _mount(monkeypatch, ["My Drive", "Reports", "Nope.pdf"])
    assert api.resolve_via_api(Path("/mnt/My Drive/Reports/Nope.pdf")) is None
