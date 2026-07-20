---
name: drivefs-schema
description: DriveFS local metadata SQLite schema facts and landmines for path->Drive-id resolution
metadata:
  type: reference
---

Google Drive for Desktop keeps a per-account SQLite metadata DB at
`~/Library/Application Support/Google/DriveFS/<numeric_account_id>/metadata_sqlite_db`
(macOS). Mounts are at `~/Library/CloudStorage/GoogleDrive-<email>/`, containing
`My Drive/` and `Shared drives/<Name>/`. Open the DB read-only via
`file:...?immutable=1` (no locks, safe while Drive is running).

Tables used:
- `items(stable_id PK, id, mime_type, is_folder, team_drive_stable_id,
  local_title, trashed, is_tombstone)` — `id` is the Drive object id.
- `stable_parents(item_stable_id, parent_stable_id)` — the folder tree.

Landmines (each verified live, and cost real debugging time):
- **FUSE mount inode ≠ `stable_id`.** `stat` inode has no stable/derivable
  mapping to `stable_id`, so you cannot do an O(1) inode lookup. Resolve by
  **walking path segments by name** from a known root (`local_title` +
  `stable_parents`). Duplicate names in one folder are the only ambiguity.
- **My Drive root** row: `local_title='My Drive'` with `team_drive_stable_id
  IS NULL`. **Shared Drive root** rows: `stable_id == team_drive_stable_id`.
  These need *different* queries — a single "root by title" query fails.
- **Native files** (`.gdoc`/`.gsheet`/…): DB `local_title` has NO extension,
  but the filesystem name does. Resolve these via the sidecar JSON (`doc_id`)
  instead — see [[native-file-sidecar]].

The `Shared drives` top-level entry is a virtual container with no `items` row;
it has no single URL.
