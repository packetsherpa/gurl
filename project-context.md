# gurl — Live State

> Live state only: what is in flight, blocked, and next. Durable facts live in
> `.claude/memory/` (see `.claude/memory/MEMORY.md`). Changelog lives in git
> history.

## Goal

A CLI to identify the Google URL for the current working directory or a file in the directory and open it in the browser.

## Active Work

- Core complete: local resolution (sidecar + DriveFS DB walk), CLI (open +
  print, `--no-open`/`--print`, `--id`, `--source`), and **Drive shortcut
  following**. 38 pytest tests pass. Fully local — no network/credentials.
- Tooling: ruff (lint + format) and GitHub Actions CI (ruff + pytest on
  Python 3.9 and 3.12). Installed globally via `uv tool install`.
- Validated live on macOS against a real Drive (My Drive, Shared Drives,
  native docs, binary files, folder/native shortcuts, spaces/pipes in names).
- **Drive API fallback removed** — see `.claude/memory/api-fallback-removed.md`.

## Blockers

- None.

## Next

- Windows support: fill in DriveFS DB path + mount detection in `drivefs.py`
  (locations are already isolated behind `_drivefs_support_dir` / `_mount_roots`).
- Optional: `--copy` (clipboard); multi-account disambiguation beyond "try each DB".
