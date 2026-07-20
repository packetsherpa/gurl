# gurl — Agent Instructions

A CLI to identify the Google URL for the current working directory or a file in the directory and open it in the browser.

This file is the single source of truth for any agent working in this repo
(Claude Code, Codex, or others). `CLAUDE.md` is a symlink to this file. Global
conventions live in `~/.claude/CLAUDE.md` — do not restate them here. This file
covers only what is specific to gurl.

## What This Tool Is

`gurl [PATH]` resolves a local path inside a Google Drive for Desktop mount to
its Drive **web URL**, prints it, and opens it in the browser. `PATH` defaults
to the current directory. Flags: `--no-open`/`--print` (print only), `--id`
(print just the Drive object id).

Resolution is a hybrid, tried in order (`src/gurl/resolve.py`):
1. **Sidecar** (`sidecar.py`) — `.gdoc`/`.gsheet`/… files embed `doc_id` in JSON.
2. **DriveFS DB** (`drivefs.py`) — folders/binary files via a read-only
   (`immutable=1`) name-walk of the local metadata SQLite DB.
3. **Drive API** (`api.py`, extra `gurl[api]`) — ADC then cached OAuth; walks
   the same segments via the API. Returns None if deps absent.

URL shapes live in `urls.py`. Pure stdlib for local resolution; API deps are
optional and lazily imported.

### Gotchas (see `.claude/memory/`)
- FUSE mount **inode ≠ `stable_id`** — no stable mapping; resolve by name-walk.
- **My Drive root**: `team_drive_stable_id IS NULL`. **Shared Drive root**:
  `stable_id == team_drive_stable_id`. Different queries.
- Native files' DB `local_title` has **no** extension; the filesystem name does
  — handled by the sidecar step (and extension-stripping in the API walk).

### Dev
- Run: `uv run gurl [PATH]`  •  Tests: `uv run pytest` (fixture DB, no live Drive).

## On Session Start

1. Read `project-context.md` — the authoritative **live** state (what is in
   flight, blocked, and the next starting point).
2. Run `git status --short --branch` and `git log --oneline -5`.
3. State the current task before starting; if it is not obvious, ask.

## Durable Memory

Durable facts, decisions, and landmines live in `.claude/memory/` as one-fact
files (frontmatter: `name`, `description`, `metadata.type`; linked with
`[[slug]]`). When something becomes durable, add a one-fact file and a line in
`.claude/memory/MEMORY.md` — do not bury it in `project-context.md`.

@.claude/memory/MEMORY.md
