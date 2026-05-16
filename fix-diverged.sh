#!/bin/bash
# fix-diverged.sh — rebase local commit on top of remote then push
cd /Users/praneethtota/MyProjects/AUA-Veritas

echo "=== Rebasing local commit on top of remote ==="
git pull --rebase origin main

echo ""
echo "=== Adding commit-untracked.sh ==="
git add commit-untracked.sh
git commit -m "chore: add commit-untracked.sh helper script" 2>/dev/null || echo "(already committed)"

echo ""
echo "=== Pushing ==="
git push origin main

echo ""
echo "=== Final state ==="
git log --oneline -5
git status
