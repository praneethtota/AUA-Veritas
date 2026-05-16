#!/bin/bash
# fix-all-and-rebuild-dmg.sh
# Pulls all fixes, rebuilds UI + binary, builds fresh DMG
APP="/Users/praneethtota/MyProjects/AUA-Veritas"
cd "$APP"

echo "=== Pulling latest fixes ==="
git stash 2>/dev/null || true
git pull origin main
echo "✓ Pulled"

echo ""
echo "=== Rebuilding React UI (fixes checkbox bug + 422) ==="
cd ui && npm install --silent && npm run build --silent && cd ..
echo "✓ UI rebuilt — model_id is now included in /models response"
echo "  This fixes: all checkboxes toggling together"
echo "  This fixes: 422 from null model IDs in enabled_models array"

echo ""
echo "=== Rebuilding Python backend binary ==="
"$APP/.venv/bin/pyinstaller" build/veritas-backend.spec \
    --distpath dist-backend \
    --workpath build/pyinstaller-work \
    --noconfirm \
    --log-level WARN
[ ! -f "dist-backend/veritas-backend" ] && echo "ERROR: binary not found" && exit 1
chmod +x dist-backend/veritas-backend
echo "✓ Binary: $(du -sh dist-backend/veritas-backend | cut -f1)"

echo ""
echo "=== Building .dmg ==="
npm install --silent
npx electron-builder --mac --config electron-builder.json

DMG=$(find release -name "*.dmg" 2>/dev/null | head -1)
[ -z "$DMG" ] && echo "ERROR: No .dmg found" && exit 1

echo ""
echo "┌───────────────────────────────────────────────────────────┐"
echo "│  ✓ DMG ready: $DMG"
echo "│  Size: $(du -sh "$DMG" | cut -f1)"
echo "├───────────────────────────────────────────────────────────┤"
echo "│  Install:                                                 │"
echo "│   1. Trash the current AUA-Veritas in Applications       │"
echo "│   2. Double-click the .dmg below                         │"
echo "│   3. Drag AUA-Veritas → Applications                     │"
echo "│   4. Right-click → Open (first launch only)              │"
echo "└───────────────────────────────────────────────────────────┘"

open -R "$APP/$DMG"
