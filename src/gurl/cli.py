"""gurl command-line entry point."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from . import GurlError, __version__
from .resolve import SOURCES, resolve


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gurl",
        description="Identify the Google Drive URL for a local path and open it in the browser.",
    )
    p.add_argument(
        "path",
        nargs="?",
        default=".",
        help="File or directory to resolve (default: current directory).",
    )
    p.add_argument(
        "--no-open",
        "--print",
        dest="open_browser",
        action="store_false",
        help="Print the URL only; do not open a browser.",
    )
    p.add_argument(
        "--id",
        dest="id_only",
        action="store_true",
        help="Print just the Drive object id.",
    )
    p.add_argument(
        "--source",
        choices=SOURCES,
        default="auto",
        help="Force a resolution strategy (default: auto). Use 'api' to bypass "
        "local resolution and go straight to the Drive API.",
    )
    p.add_argument("--version", action="version", version=f"gurl {__version__}")
    return p


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        result = resolve(Path(args.path), source=args.source)
    except GurlError as exc:
        print(f"gurl: {exc}", file=sys.stderr)
        return 1

    if args.id_only:
        if result.item is None or not result.item.id:
            print(
                "gurl: no object id available for this resolution (resolved to a direct URL).",
                file=sys.stderr,
            )
            return 1
        print(result.item.id)
        return 0

    # Default: open in the browser AND print the URL.
    if args.open_browser:
        webbrowser.open(result.url)
    print(result.url)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
