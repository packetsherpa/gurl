from gurl.urls import DriveItem, url_for


def test_folder_url():
    assert url_for(DriveItem(id="X", is_folder=True)) == (
        "https://drive.google.com/drive/folders/X"
    )


def test_folder_url_by_mime():
    item = DriveItem(id="X", mime_type="application/vnd.google-apps.folder")
    assert url_for(item) == "https://drive.google.com/drive/folders/X"


def test_native_editor_urls():
    cases = {
        "application/vnd.google-apps.document": "https://docs.google.com/document/d/X/edit",
        "application/vnd.google-apps.spreadsheet": "https://docs.google.com/spreadsheets/d/X/edit",
        "application/vnd.google-apps.presentation": "https://docs.google.com/presentation/d/X/edit",
        "application/vnd.google-apps.form": "https://docs.google.com/forms/d/X/edit",
        "application/vnd.google-apps.drawing": "https://docs.google.com/drawings/d/X/edit",
    }
    for mime, expected in cases.items():
        assert url_for(DriveItem(id="X", mime_type=mime)) == expected


def test_binary_file_url():
    item = DriveItem(id="X", mime_type="application/pdf")
    assert url_for(item) == "https://drive.google.com/file/d/X/view"


def test_unknown_type_falls_back_to_open():
    assert url_for(DriveItem(id="X")) == "https://drive.google.com/open?id=X"
