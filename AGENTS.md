# gurl — Agent Instructions

A CLI to identify the Google URL for the current working directory or a file in the directory and open it in the browser.

This file is the single source of truth for any agent working in this repo
(Claude Code, Codex, or others). `CLAUDE.md` is a symlink to this file. Global
conventions live in `~/.claude/CLAUDE.md` — do not restate them here. This file
covers only what is specific to gurl.

## What This Tool Is

<!-- Fill in: purpose, the I/O contract (e.g. JSON in / JSON out on stdio),
     key commands, and any gotchas a new agent must know. Keep it short. -->
TODO: describe gurl's purpose and interface.

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
