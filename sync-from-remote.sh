#!/bin/bash
# sync-from-remote.sh
# Mac local files are ahead of local git but behind remote.
# Stash local changes, pull remote (source of truth), drop the stash.

cd /Users/praneethtota/MyProjects/AUA-Veritas

echo "=== Before sync ==="
git log --oneline -3
echo ""

echo "=== Stashing local changes ==="
git stash push -m "pre-sync local edits $(date +%Y%m%d-%H%M%S)"

echo ""
echo "=== Pulling from remote (source of truth) ==="
git pull origin main

echo ""
echo "=== Dropping stash (already in remote) ==="
git stash drop 2>/dev/null || true

echo ""
echo "=== After sync ==="
git log --oneline -5
git status
