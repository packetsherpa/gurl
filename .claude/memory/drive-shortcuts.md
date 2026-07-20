---
name: drive-shortcuts
description: How Drive shortcuts appear on disk and resolve to their targets
metadata:
  type: reference
---

Drive shortcuts (`mime_type = application/vnd.google-apps.shortcut`) resolve to
their target so `gurl` returns the target's URL, not the shortcut's.

Three on-disk forms, handled in different layers:
- **Shortcut to a native file** (`.gdoc`/`.gslides`/…): the on-disk sidecar JSON
  already contains the *target's* `doc_id`, so the [[native-file-sidecar]] step
  resolves it for free — no shortcut logic needed.
- **Shortcut to a folder or binary file**: it's a **symlink** to
  `<mount>/.shortcut-targets-by-id/<TARGET_DRIVE_ID>/<name>`. `os.path.realpath`
  follows it, so the resolved path carries the target's Drive id as the segment
  right after `.shortcut-targets-by-id`. `drivefs._start_node` anchors on that id
  (skipping the id + the target's own name segment) and walks any children.
- **Safety net**: if a walk lands on a `shortcut`-mime item, `_follow_shortcut`
  reads `shortcut_details(shortcut_stable_id, target_stable_id, target_mime_type)`
  and returns the target item.

If the target isn't synced locally (no `items` row for that Drive id — ~40% of
`shortcut_details` rows on a real machine), fall back to `open?id=<drive_id>`;
Drive redirects a shortcut/id to its target. See [[drivefs-schema]].
