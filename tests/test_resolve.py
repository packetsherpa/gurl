import json

import pytest

from gurl import GurlError, resolve as resolve_mod
from gurl.resolve import resolve
from gurl.urls import DriveItem


def test_nonexistent_path_errors(tmp_path):
    with pytest.raises(GurlError):
        resolve(tmp_path / "does-not-exist")


def test_sidecar_takes_precedence(tmp_path, monkeypatch):
    f = tmp_path / "Plan.gdoc"
    f.write_text(json.dumps({"doc_id": "ABC"}), encoding="utf-8")

    def _boom(_):  # drivefs must not be consulted for a native sidecar
        raise AssertionError("drivefs should not run when sidecar resolves")

    monkeypatch.setattr(resolve_mod, "resolve_via_drivefs", _boom)
    res = resolve(f)
    assert res.source == "sidecar"
    assert res.url == "https://docs.google.com/document/d/ABC/edit"


def test_falls_through_to_drivefs(tmp_path, monkeypatch):
    d = tmp_path / "folder"
    d.mkdir()
    monkeypatch.setattr(
        resolve_mod, "resolve_via_drivefs",
        lambda _: DriveItem(id="FID", is_folder=True),
    )
    res = resolve(d)
    assert res.source == "drivefs"
    assert res.url == "https://drive.google.com/drive/folders/FID"


def test_unresolved_raises(tmp_path, monkeypatch):
    d = tmp_path / "folder"
    d.mkdir()
    monkeypatch.setattr(resolve_mod, "resolve_via_drivefs", lambda _: None)
    with pytest.raises(GurlError):
        resolve(d)
