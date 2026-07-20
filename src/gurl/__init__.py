"""gurl — resolve a local Google Drive path to its Drive web URL."""

__version__ = "0.1.0"


class GurlError(Exception):
    """User-facing error; the CLI prints the message and exits non-zero."""
