#!/bin/bash
# fix-and-build.sh — stash local edits, pull fixes, rebuild, launch
set -e
APP="/Users/praneethtota/MyProjects/AUA-Veritas"
cd "$APP"

echo "=== Step 1: Stash local edits and pull ==="
git stash
git pull origin main
echo "✓ Pulled latest (field_classifier fix + main.js fix)"
echo ""

echo "=== Step 2: Rebuild PyInstaller binary ==="
source .venv/bin/activate
rm -rf dist-backend build/pyinstaller-work

pyinstaller build/veritas-backend.spec \
    --distpath dist-backend \
    --workpath build/pyinstaller-work \
    --noconfirm \
    --log-level WARN

[ ! -f "dist-backend/veritas-backend" ] && echo "ERROR: binary not found" && deactivate && exit 1
chmod +x dist-backend/veritas-backend
echo "✓ Binary: $(du -sh dist-backend/veritas-backend | cut -f1)"
echo ""

echo "=== Step 3: Smoke test ==="
VERITAS_API_PORT=47899 PYTHONPATH="$APP" ./dist-backend/veritas-backend &
BPID=$!
sleep 6
RESULT=$(curl -s http://127.0.0.1:47899/health 2>/dev/null)
kill $BPID 2>/dev/null; wait $BPID 2>/dev/null

if echo "$RESULT" | grep -q '"status"'; then
    echo "✅ Smoke test passed: $RESULT"
    BINARY_OK=1
else
    echo "⚠ Binary smoke test inconclusive — will use .venv fallback"
    BINARY_OK=0
fi
deactivate
echo ""

echo "=== Step 4: Launch ==="
if [ "$BINARY_OK" = "1" ]; then
    echo "Launching via binary..."
    npx electron .
else
    echo "Launching with .venv backend in background..."
    PYTHONPATH="$APP" .venv/bin/python3 -m uvicorn api.main:app \
        --port 47821 --host 127.0.0.1 --log-level warning &
    BPID=$!
    sleep 4
    echo "Backend PID: $BPID — launching Electron..."
    npx electron .
    kill $BPID 2>/dev/null
fi
