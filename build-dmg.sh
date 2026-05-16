#!/bin/bash
# build-dmg.sh — Build fresh AUA-Veritas.dmg
APP="/Users/praneethtota/MyProjects/AUA-Veritas"
cd "$APP"

echo "=== AUA-Veritas DMG Builder ==="
echo ""

echo "[1/5] Pulling latest fixes..."
git stash 2>/dev/null || true
git pull origin main
echo "✓ Done"

echo ""
echo "[2/5] Rebuilding React UI..."
cd ui && npm install --silent && npm run build --silent && cd ..
echo "✓ UI: $(du -sh ui/dist | cut -f1)"

echo ""
echo "[3/5] Rebuilding Python binary (3-4 min)..."
PYINSTALLER="$APP/.venv/bin/pyinstaller"
rm -rf dist-backend build/pyinstaller-work

"$PYINSTALLER" build/veritas-backend.spec \
    --distpath dist-backend \
    --workpath build/pyinstaller-work \
    --noconfirm \
    --log-level WARN

if [ ! -f "dist-backend/veritas-backend" ]; then
    echo "ERROR: binary not found after PyInstaller"
    exit 1
fi
chmod +x dist-backend/veritas-backend
echo "✓ Binary: $(du -sh dist-backend/veritas-backend | cut -f1)"

echo ""
echo "[4/5] Building .dmg..."
npm install --silent
npx electron-builder --mac --config electron-builder.json

echo ""
echo "[5/5] Done!"
DMG=$(find release -name "*.dmg" 2>/dev/null | head -1)
if [ -z "$DMG" ]; then
    echo "ERROR: No .dmg found in release/"
    exit 1
fi

echo ""
echo "┌─────────────────────────────────────────────────┐"
echo "│  DMG: $DMG"
echo "│  Size: $(du -sh "$DMG" | cut -f1)"
echo "├─────────────────────────────────────────────────┤"
echo "│  Install steps:                                 │"
echo "│  1. Open the .dmg (Finder opening now)          │"
echo "│  2. Drag AUA-Veritas → Applications             │"
echo "│  3. Eject the DMG                               │"
echo "│  4. Right-click AUA-Veritas → Open              │"
echo "│  5. Click Open in the security dialog           │"
echo "└─────────────────────────────────────────────────┘"
echo ""

open -R "$APP/$DMG"
