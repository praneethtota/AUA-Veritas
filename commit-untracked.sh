#!/bin/bash
# commit-untracked.sh — commit all untracked files to repo
cd /Users/praneethtota/MyProjects/AUA-Veritas

echo "=== Pulling latest first ==="
git pull origin main

echo ""
echo "=== Adding all untracked files ==="
git add \
  assets/dmg-background.png \
  assets/icon.icns \
  assets/icon.png \
  assets/tray-icon.png \
  build-dmg.sh \
  diagnose-corrections.sh \
  diagnose.sh \
  docs/bug_report.md \
  docs/design_log.md \
  fix-all-and-rebuild-dmg.sh \
  fix-and-build.sh \
  hotfix.sh \
  launch-electron.sh \
  package-lock.json \
  pull-latest.sh \
  rebuild-backend.sh \
  reset-and-launch.sh \
  resume-build.sh \
  sync-from-remote.sh \
  ui/src/theme.css \
  update-and-launch.sh

echo ""
echo "=== Status before commit ==="
git status

echo ""
echo "=== Committing ==="
git commit -m "chore: add untracked files — assets, scripts, docs, theme.css, package-lock

Assets (app icons generated during build):
  assets/icon.png, icon.icns, tray-icon.png, dmg-background.png

Build and helper scripts:
  build-dmg.sh               — build macOS DMG
  fix-all-and-rebuild-dmg.sh — pull + rebuild + DMG in one command
  fix-and-build.sh           — stash + pull + rebuild
  hotfix.sh                  — quick rebuild after fix
  rebuild-backend.sh         — PyInstaller rebuild only
  resume-build.sh            — resume interrupted build
  reset-and-launch.sh        — wipe DB + relaunch
  update-and-launch.sh       — pull + rebuild + launch
  launch-electron.sh         — launch Electron only
  pull-latest.sh             — pull latest from remote

Debug scripts:
  diagnose.sh                — test all API endpoints
  diagnose-corrections.sh    — inspect corrections SQLite table

Sync scripts:
  sync-from-remote.sh        — Mac: stash local, pull remote, drop stash

UI:
  ui/src/theme.css           — CSS variable system for dark/light mode

Docs:
  docs/bug_report.md         — timestamped bug log
  docs/design_log.md         — timestamped design decision log

Infra:
  package-lock.json          — Electron dependency lock file"

echo ""
echo "=== Pushing ==="
git push origin main

echo ""
echo "=== Done ==="
git log --oneline -3
git status
