# gurl — Live State

> Live state only: what is in flight, blocked, and next. Durable facts live in
> `.claude/memory/` (see `.claude/memory/MEMORY.md`). Changelog lives in git
> history.

## Goal

A CLI to identify the Google URL for the current working directory or a file in the directory and open it in the browser.

## Active Work

- Phases 1–3 complete: local resolution (sidecar + DriveFS DB walk), CLI
  (open + print, `--no-open`/`--print`, `--id`), and the Drive API fallback
  (ADC → cached OAuth). 40 pytest tests pass (`uv run pytest`).
- Validated live on macOS against a real Drive (My Drive, Shared Drives,
  native docs, binary files, nested paths with spaces/pipes).

## Blockers

- None.

## Next

- Windows support: fill in DriveFS DB path + mount detection in `drivefs.py`
  (locations are already isolated behind `_drivefs_support_dir` / `_mount_roots`).
- Consider `--copy` (clipboard) if wanted; multi-account disambiguation beyond
  "try each DB".
- Package/distribute (e.g. `uv tool install`).
