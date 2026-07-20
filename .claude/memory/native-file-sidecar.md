---
name: native-file-sidecar
description: Google-native files (.gdoc/.gsheet/...) embed the Drive doc_id in a local JSON sidecar
metadata:
  type: reference
---

On a Drive for Desktop mount, a Google-native file (`.gdoc`, `.gsheet`,
`.gslides`, `.gform`, `.gdraw`, `.gscript`, `.gsite`) is a tiny JSON file whose
contents are the Drive object reference, e.g.:

```json
{"doc_id": "1VmAE0...", "resource_key": "", "email": "user@example.com"}
```

So native files resolve with **no DB and no network**: read the file, take
`doc_id`, and build the editor URL from the extension (`.gdoc` ->
`docs.google.com/document/d/<id>/edit`, etc.). Older clients wrote a `url` key
directly instead of `doc_id`; if present, use it verbatim.

This is why the resolver tries the sidecar step *before* the DriveFS DB walk
([[drivefs-schema]]): it's faster, offline, and sidesteps the extension
mismatch between the filesystem name and the DB `local_title`.
