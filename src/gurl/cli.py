"""gurl command-line entry point."""

from __future__ import annotations

import argparse
import glob
import os
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
        "paths",
        nargs="*",
        metavar="PATH",
        help="Files or directories to resolve; glob patterns are expanded "
        "(default: current directory).",
    )
    p.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="List every (non-hidden) descendant of each directory as '<path>\\t<url>'.",
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
        help="Force a resolution strategy (default: auto) instead of trying "
        "each in order. Useful for debugging.",
    )
    p.add_argument("--version", action="version", version=f"gurl {__version__}")
    return p


_GLOB_CHARS = set("*?[")


def _expand(arg: str) -> list[Path]:
    """Expand a glob argument (``**`` recursive); literal paths pass through."""
    if _GLOB_CHARS & set(arg) and not os.path.exists(os.path.expanduser(arg)):
        matches = sorted(glob.glob(os.path.expanduser(arg), recursive=True))
        if not matches:
            raise GurlError(f"No match for pattern: {arg}")
        return [Path(m) for m in matches]
    return [Path(arg)]


def _descendants(root: Path) -> list[Path]:
    """Sorted non-hidden descendants of ``root`` (symlinked dirs listed, not followed)."""
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root.expanduser()):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        base = Path(dirpath)
        out.extend(base / n for n in sorted(dirnames))
        out.extend(base / n for n in sorted(f for f in filenames if not f.startswith(".")))
    return sorted(out)


def _display(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def _output(result, id_only: bool) -> str | None:
    if not id_only:
        return result.url
    return result.item.id if result.item is not None and result.item.id else None


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    globbed = False
    try:
        targets: list[Path] = []
        for arg in args.paths or ["."]:
            expanded = _expand(arg)
            globbed = globbed or expanded != [Path(arg)]
            for t in expanded:
                if args.recursive and t.expanduser().is_dir():
                    targets.extend(_descendants(t))
                else:
                    targets.append(t)
    except GurlError as exc:
        print(f"gurl: {exc}", file=sys.stderr)
        return 1

    # Single target without -r: original behaviour (bare value, open browser).
    multi = args.recursive or globbed or len(targets) != 1
    failed = False
    urls: list[str] = []
    for t in targets:
        try:
            result = resolve(t, source=args.source)
        except GurlError as exc:
            print(f"gurl: {exc}", file=sys.stderr)
            failed = True
            continue
        value = _output(result, args.id_only)
        if value is None:
            print(
                f"gurl: no object id available for {t} (resolved to a direct URL).",
                file=sys.stderr,
            )
            failed = True
            continue
        urls.append(result.url)
        print(f"{_display(t)}\t{value}" if multi else value)

    # Default: open in the browser, but only for a single result.
    if args.open_browser and not args.id_only and not multi and urls:
        webbrowser.open(urls[0])
    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
