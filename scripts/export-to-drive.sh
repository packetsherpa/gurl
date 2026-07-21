#!/usr/bin/env bash
#
# export-to-drive.sh — refresh a git-free exported snapshot of this repo to a
# destination folder (e.g. a Google Drive shared drive) and stamp PROVENANCE.md.
#
# This script is repo-agnostic: drop it into any repo's scripts/ unchanged. Repo
# name, remote, branch, and local path are all read from git at run time.
#
# The snapshot is a copy of tracked files only (via `git archive`). NEVER place a
# live .git inside a Drive sync client — it can corrupt the repo.
#
# The destination is a CONTAINER folder (e.g. a "Claude" or "Gemini" directory on
# the drive); the snapshot lands in a subdirectory named after the repo inside it,
# i.e. <destination>/<repo-name>/. Sibling exports in the same container are left
# untouched, and files renamed or removed upstream do not linger as stale copies.
#
# The snapshot is built in a temp staging dir and rsync'd into the target IN
# PLACE (rsync --inplace). This is deliberate: wiping and re-extracting the
# target would make the Drive sync client see every file as deleted-and-recreated
# and assign a brand-new Drive file ID (and share URL) on every run. Syncing in
# place rewrites changed files' contents (preserving their inode, so Drive keeps
# the same ID/URL), creates only genuinely new files, and deletes only files
# removed upstream.
#
# Destination (container) resolution (first match wins):
#   1. first argument
#   2. $DRIVE_EXPORT_DEST
#   3. the path on the first line of .drive-dest (gitignored)
#   4. if none of the above, prompt for it and save the answer to .drive-dest
#
# Usage:
#   scripts/export-to-drive.sh ["/path/to/container"]

set -euo pipefail

# capture this script's absolute path BEFORE any cd (it lives outside the repo)
SCRIPT_ABS="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null && pwd)/$(basename "${BASH_SOURCE[0]}")"

# operate on the git repo of the current working directory, not the script's dir
REPO_ROOT="$(git -C "$PWD" rev-parse --show-toplevel)"
cd "$REPO_ROOT"
REPO_NAME="$(basename "$REPO_ROOT")"
SCRIPT_REL="$SCRIPT_ABS"   # absolute, since the script is not inside the repo

# --- resolve destination ------------------------------------------------------
DEST="${1:-${DRIVE_EXPORT_DEST:-}}"
if [[ -z "$DEST" && -f .drive-dest ]]; then
  DEST="$(head -n1 .drive-dest)"
fi
if [[ -z "$DEST" ]]; then
  # not configured — prompt (only show the prompt if attached to a terminal),
  # capture the answer, and persist it to .drive-dest for next time
  if [[ -t 0 ]]; then
    printf 'No export destination configured.\nEnter the destination (container) folder — it will be saved to .drive-dest: ' >&2
  fi
  IFS= read -r DEST || DEST=""
  DEST="${DEST/#\~/$HOME}"   # expand a leading ~ to an absolute path
  if [[ -z "$DEST" ]]; then
    echo "error: no destination provided. Pass it as an argument, set DRIVE_EXPORT_DEST, or put the path on line 1 of .drive-dest" >&2
    exit 2
  fi
  printf '%s\n' "$DEST" > "$REPO_ROOT/.drive-dest"
  echo "==> Saved destination to .drive-dest" >&2
fi

# the snapshot lands in a repo-named subdirectory of the container, and only that
# subdirectory is wiped — sibling exports in the same container are left alone
TARGET="$DEST/$REPO_NAME"

# --- discover git facts (repo-agnostic) ---------------------------------------
REMOTE="$(git remote | head -n1 || true)"

# default branch: remote HEAD → main → current branch
BRANCH=""
if [[ -n "$REMOTE" ]]; then
  BRANCH="$(git symbolic-ref --short "refs/remotes/$REMOTE/HEAD" 2>/dev/null | sed "s@^$REMOTE/@@" || true)"
fi
if [[ -z "$BRANCH" ]] && git show-ref --verify --quiet refs/heads/main; then
  BRANCH="main"
fi
[[ -z "$BRANCH" ]] && BRANCH="$(git rev-parse --abbrev-ref HEAD)"

git rev-parse --verify "$BRANCH" >/dev/null 2>&1 || { echo "error: no '$BRANCH' branch to export" >&2; exit 1; }

if [[ -n "$REMOTE" ]]; then
  REMOTE_URL="$(git remote get-url "$REMOTE" 2>/dev/null || echo 'unknown')"
else
  REMOTE_URL="(no remote configured)"
fi

COMMIT="$(git rev-parse --short "$BRANCH")"
TODAY="$(date +%F)"

# --- safety -------------------------------------------------------------------
case "$DEST" in
  ""|"/"|"$HOME") echo "error: refusing to wipe '$DEST'" >&2; exit 1 ;;
esac

# --- build snapshot in a staging dir ------------------------------------------
# Build a fresh, complete snapshot off to the side, then sync it into the target
# in place (below). This keeps the target consistent and lets rsync do a precise
# add/update/delete pass that preserves Drive file IDs for unchanged files.
echo "==> Exporting $REPO_NAME @ $COMMIT ($BRANCH) to: $TARGET"
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/drive-export.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
git archive "$BRANCH" | tar -x -C "$STAGE"

# --- dereference symlinks -----------------------------------------------------
# Drive sync clients don't reliably sync symlinks (they skip them or flag sync
# errors), so replace each with a copy of its target's content. Broken links are
# removed. Uses `find -print0` to survive spaces in the staging path.
while IFS= read -r -d '' link; do
  if tgt="$(readlink -f "$link" 2>/dev/null)" && [[ -f "$tgt" ]]; then
    rm -f "$link"; cp "$tgt" "$link"
  else
    echo "==> warning: removing broken symlink $link" >&2
    rm -f "$link"
  fi
done < <(find "$STAGE" -type l -print0)

# --- stamp provenance (generated per export from git; not tracked) ------------
cat > "$STAGE/PROVENANCE.md" <<'EOF'
# Provenance

This folder is an **exported snapshot** of the `@@REPO@@` repository — a copy of
static, tracked files for direct use on the shared drive. It is **not a git
repository** and must not be edited as the source of truth.

## Authoritative source

- **Remote:** @@REMOTE_URL@@
- **Local working copy:** @@LOCAL@@

Make changes there, commit, and re-export — do not edit this snapshot in place, and
do not run `git init` here (a live `.git` inside a Drive sync client risks
corruption from the sync process).

## This snapshot

- Repository: **@@REPO@@**
- Exported from branch **@@BRANCH@@** at commit **@@COMMIT@@** on **@@DATE@@**.
- Produced with `@@SCRIPT@@` (tracked files only; working scratch is excluded).

## Refreshing

From the authoritative working copy:

```
@@SCRIPT@@
```

Re-run after any update to bring this snapshot current. The script syncs its own
subdirectory in place — unchanged files keep their Drive ID/URL, changed files
are rewritten, and renamed or removed files are pruned.
EOF

# substitute runtime values (escape \ & | so paths/URLs are literal for sed)
esc() { printf '%s' "$1" | sed -e 's/[\\&|]/\\&/g'; }
sed \
  -e "s|@@REPO@@|$(esc "$REPO_NAME")|g" \
  -e "s|@@REMOTE_URL@@|$(esc "$REMOTE_URL")|g" \
  -e "s|@@LOCAL@@|$(esc "$REPO_ROOT")|g" \
  -e "s|@@BRANCH@@|$(esc "$BRANCH")|g" \
  -e "s|@@COMMIT@@|$(esc "$COMMIT")|g" \
  -e "s|@@DATE@@|$(esc "$TODAY")|g" \
  -e "s|@@SCRIPT@@|$(esc "$SCRIPT_REL")|g" \
  "$STAGE/PROVENANCE.md" > "$STAGE/PROVENANCE.md.tmp"
mv "$STAGE/PROVENANCE.md.tmp" "$STAGE/PROVENANCE.md"

# --- sync staging into the target IN PLACE ------------------------------------
# --inplace  rewrites changed files without a temp+rename, preserving the inode
#            so the Drive client uploads a new revision (same file ID/URL) rather
#            than treating it as a delete+create (new ID/URL).
# --checksum decides what changed by content, not mtime — git archive re-stamps
#            every file's mtime on each commit, which would otherwise re-upload
#            unchanged files needlessly.
# --delete   prunes files removed or renamed upstream.
mkdir -p "$TARGET"
rsync -a --checksum --inplace --delete "$STAGE"/ "$TARGET"/

echo "==> Done. Snapshot at: $TARGET"
