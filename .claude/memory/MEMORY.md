# Memory

Durable facts, decisions, and landmines for gurl. One file per
fact. Live/churning state lives in `project-context.md`, not here.

<!-- Add entries as one line each:
     - [Title](slug.md) — one-line hook of what the fact is
     Each entry links to a sibling <slug>.md with frontmatter:
       ---
       name: <slug>
       description: <one line>
       metadata:
         type: user | feedback | project | reference
       ---
-->

- [DriveFS schema](drivefs-schema.md) — local metadata SQLite tables + landmines (inode≠stable_id; My Drive vs Shared Drive root queries)
- [Native file sidecar](native-file-sidecar.md) — .gdoc/.gsheet files embed doc_id in JSON; resolve offline, no DB
- [Drive shortcuts](drive-shortcuts.md) — resolve to target via .shortcut-targets-by-id path id, sidecar, or shortcut_details
- [API fallback removed](api-fallback-removed.md) — decision: gurl stays fully local; no Drive API fallback
