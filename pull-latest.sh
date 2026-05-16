#!/bin/bash
# pull-latest.sh — pull all latest changes to the Mac repo
cd /Users/praneethtota/MyProjects/AUA-Veritas
git stash 2>/dev/null || true
git pull origin main
echo "✓ Up to date with GitHub"
git log --oneline -5
