import json
from pathlib import Path

from gurl.sidecar import is_native_sidecar, resolve_sidecar, sidecar_direct_url


def _write(path: Path, payload) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_is_native_sidecar():
    assert is_native_sidecar(Path("a.gdoc"))
    assert is_native_sidecar(Path("a.GSHEET"))  # case-insensitive
    assert not is_native_sidecar(Path("a.pdf"))


def test_resolve_gdoc_uses_doc_id_and_ext_mime(tmp_path):
    f = _write(tmp_path / "Plan.gdoc", {"doc_id": "ABC123"})
    item = resolve_sidecar(f)
    assert item is not None
    assert item.id == "ABC123"
    assert item.mime_type == "application/vnd.google-apps.document"
    assert item.title == "Plan"


def test_resolve_gsheet_mime(tmp_path):
    f = _write(tmp_path / "Budget.gsheet", {"doc_id": "S1"})
    assert resolve_sidecar(f).mime_type == "application/vnd.google-apps.spreadsheet"


def test_non_sidecar_extension_returns_none(tmp_path):
    f = _write(tmp_path / "x.pdf", {"doc_id": "ABC"})
    assert resolve_sidecar(f) is None


def test_missing_doc_id_returns_none(tmp_path):
    f = _write(tmp_path / "x.gdoc", {"email": "a@b.c"})
    assert resolve_sidecar(f) is None


def test_malformed_json_returns_none(tmp_path):
    f = tmp_path / "x.gdoc"
    f.write_text("not json", encoding="utf-8")
    assert resolve_sidecar(f) is None


def test_direct_url_when_present(tmp_path):
    f = _write(tmp_path / "x.gdoc", {"url": "https://docs.google.com/document/d/Z/edit"})
    assert sidecar_direct_url(f) == "https://docs.google.com/document/d/Z/edit"


def test_direct_url_ignores_non_http(tmp_path):
    f = _write(tmp_path / "x.gdoc", {"url": "ftp://nope"})
    assert sidecar_direct_url(f) is None


def test_direct_url_rejects_non_google_host(tmp_path):
    # A sidecar can be attacker-shared; never open an arbitrary external URL.
    f = _write(tmp_path / "x.gdoc", {"url": "https://evil.example/phish"})
    assert sidecar_direct_url(f) is None


def test_direct_url_rejects_http_scheme(tmp_path):
    f = _write(tmp_path / "x.gdoc", {"url": "http://docs.google.com/document/d/Z/edit"})
    assert sidecar_direct_url(f) is None


def test_oversized_sidecar_is_bounded(tmp_path):
    # Only a bounded prefix is read; a huge file with a native extension must
    # not be slurped whole and must not resolve past the cap.
    f = tmp_path / "big.gdoc"
    payload = '{"doc_id": "ABC123", "pad": "' + ("x" * 200_000) + '"}'
    f.write_text(payload, encoding="utf-8")
    # Truncated read yields invalid JSON -> None, proving the cap took effect.
    assert resolve_sidecar(f) is None
