---
name: api-fallback-removed
description: The Drive API fallback was prototyped then removed; local resolution is the whole tool
metadata:
  type: project
---

gurl deliberately has **no Drive API fallback**. One was built (ADC + cached
OAuth, `api.py`, a `gurl[api]` extra, and a `--source api` mode) and then
removed on 2026-07-20.

**Why:** it never earned its place. Local resolution ([[drivefs-schema]] +
[[native-file-sidecar]] + [[drive-shortcuts]]) resolved every real path on the
owner's machine, so the API path always lost the race. Proving it live also hit
a hard environment wall: ADC user credentials require a quota project with the
Drive API enabled, and the owner lacks `serviceusage.services.enable` on the
org project (`ts-ai-assisted-api-hub`). Full auth worked (Drive scope granted),
but the API-enablement gate is not something the owner can change.

**How to apply:** keep gurl fully local — no network, no credentials, stdlib
only. Don't re-introduce an API fallback unless the requirement changes *and*
the quota-project/enablement blocker is actually solvable. `--source` remains
but only offers `auto|sidecar|drivefs`.
