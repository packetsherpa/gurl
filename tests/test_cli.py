import pytest

from gurl import cli
from gurl.resolve import Resolution
from gurl.urls import DriveItem


@pytest.fixture
def fake_resolution(monkeypatch):
    res = Resolution(
        url="https://drive.google.com/drive/folders/FID",
        item=DriveItem(id="FID", is_folder=True),
        source="drivefs",
    )
    monkeypatch.setattr(cli, "resolve", lambda _p, source="auto": res)
    return res


def test_print_only_does_not_open(fake_resolution, monkeypatch, capsys):
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", lambda u: opened.append(u))
    rc = cli.main(["--no-open", "."])
    assert rc == 0
    assert opened == []
    assert capsys.readouterr().out.strip() == fake_resolution.url


def test_default_opens_and_prints(fake_resolution, monkeypatch, capsys):
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", lambda u: opened.append(u))
    rc = cli.main(["."])
    assert rc == 0
    assert opened == [fake_resolution.url]
    assert capsys.readouterr().out.strip() == fake_resolution.url


def test_id_only(fake_resolution, capsys):
    rc = cli.main(["--id", "."])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "FID"


def test_error_exit_code(monkeypatch, capsys):
    from gurl import GurlError

    def _raise(_p, source="auto"):
        raise GurlError("nope")

    monkeypatch.setattr(cli, "resolve", _raise)
    rc = cli.main(["."])
    assert rc == 1
    assert "gurl: nope" in capsys.readouterr().err


def test_source_flag_passed_through(monkeypatch):
    seen = {}

    def _capture(_p, source="auto"):
        seen["source"] = source
        return Resolution(url="u", item=DriveItem(id="X"), source=source)

    monkeypatch.setattr(cli, "resolve", _capture)
    monkeypatch.setattr(cli.webbrowser, "open", lambda _u: None)
    cli.main(["--source", "drivefs", "."])
    assert seen["source"] == "drivefs"


def test_glob_and_recursive_listing(monkeypatch, tmp_path, capsys):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / ".hidden").write_text("x")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("x")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        cli,
        "resolve",
        lambda p, source="auto": Resolution(
            url=f"U/{p.name}", item=DriveItem(id=p.name), source="drivefs"
        ),
    )
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", lambda u: opened.append(u))

    assert cli.main(["--print", "*.txt"]) == 0
    assert capsys.readouterr().out == "a.txt\tU/a.txt\n"
    assert cli.main(["-r", "."]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "a.txt\tU/a.txt",
        "sub\tU/sub",
        "sub/b.txt\tU/b.txt",
    ]
    assert cli.main(["*"]) == 0  # multiple results: never opens
    assert opened == []
    capsys.readouterr()
    assert cli.main(["--id", "-r", "sub"]) == 0
    assert capsys.readouterr().out == "sub/b.txt\tb.txt\n"
