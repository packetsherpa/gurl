"""Map a resolved Drive item to a type-specific web URL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# mime_type -> (docs host path). Google-native editor URLs.
_EDITOR_PATHS = {
    "application/vnd.google-apps.document": "https://docs.google.com/document/d/{id}/edit",
    "application/vnd.google-apps.spreadsheet": "https://docs.google.com/spreadsheets/d/{id}/edit",
    "application/vnd.google-apps.presentation": "https://docs.google.com/presentation/d/{id}/edit",
    "application/vnd.google-apps.form": "https://docs.google.com/forms/d/{id}/edit",
    "application/vnd.google-apps.drawing": "https://docs.google.com/drawings/d/{id}/edit",
    "application/vnd.google-apps.script": "https://script.google.com/d/{id}/edit",
    "application/vnd.google-apps.site": "https://sites.google.com/d/{id}/edit",
}

# Google Drive native-file extensions -> mime_type. Used when resolving via the
# sidecar JSON, where we know the extension but not always the mime.
EXT_TO_MIME = {
    ".gdoc": "application/vnd.google-apps.document",
    ".gsheet": "application/vnd.google-apps.spreadsheet",
    ".gslides": "application/vnd.google-apps.presentation",
    ".gform": "application/vnd.google-apps.form",
    ".gdraw": "application/vnd.google-apps.drawing",
    ".gscript": "application/vnd.google-apps.script",
    ".gsite": "application/vnd.google-apps.site",
}

FOLDER_MIME = "application/vnd.google-apps.folder"


@dataclass
class DriveItem:
    """A resolved Drive object."""

    id: str
    mime_type: Optional[str] = None
    is_folder: bool = False
    title: Optional[str] = None


def url_for(item: DriveItem) -> str:
    """Return the best web URL for a resolved Drive item."""
    if item.mime_type in _EDITOR_PATHS:
        return _EDITOR_PATHS[item.mime_type].format(id=item.id)
    if item.is_folder or item.mime_type == FOLDER_MIME:
        return f"https://drive.google.com/drive/folders/{item.id}"
    if item.mime_type:  # a known non-native, non-folder file
        return f"https://drive.google.com/file/d/{item.id}/view"
    # Unknown type: let Google redirect to the right viewer.
    return f"https://drive.google.com/open?id={item.id}"
