# gurl

[![CI](https://panwgithub.paloaltonetworks.local/ddeville/gurl/actions/workflows/ci.yml/badge.svg)](https://panwgithub.paloaltonetworks.local/ddeville/gurl/actions/workflows/ci.yml)

A CLI to identify the Google Drive URL for the current working directory or a
file within a Google Drive for Desktop mount, and open it in the browser.

Handles native Google files, folders, binary files, Shared Drives, and Drive
shortcuts.

```
gurl                 # resolve the current directory, open + print its Drive URL
gurl path/to/file    # resolve a specific file or folder
gurl --no-open .     # print the URL only (also --print)
gurl --id report.pdf # print just the Drive object id
```

## How it resolves

1. **Native sidecar** — `.gdoc`/`.gsheet`/`.gslides`/… files embed the Drive id
   directly; read it, no database or network needed.
2. **DriveFS metadata DB** — folders and binary files are resolved by walking
   the local Drive for Desktop SQLite metadata (opened strictly read-only).

Resolution is fully local — no network or credentials. macOS is supported
today; the OS-specific bits are isolated so Windows can be added later.
Requires Google Drive for Desktop installed and signed in.

Force a single strategy with `--source {auto,sidecar,drivefs}` (default `auto`).

## Development

```
uv run gurl [PATH]         # run
uv run pytest              # tests (synthetic fixture DB; no live Drive needed)
uv run ruff check .        # lint
uv run ruff format .       # format
```

CI (GitHub Actions) runs ruff and pytest on Python 3.9 and 3.12.
