#!/bin/bash
# resume-build.sh — pull fixes and rebuild binary, then launch
# Run from ~/MyProjects/AUA-Veritas

set -e
APP="/Users/praneethtota/MyProjects/AUA-Veritas"
cd "$APP"

echo "=== Step 1: Pull latest fixes ==="
git pull origin main
echo ""

echo "=== Step 2: Rebuild PyInstaller binary with fixed field_classifier ==="
source .venv/bin/activate
rm -rf dist-backend build/pyinstaller-work

pyinstaller build/veritas-backend.spec \
    --distpath dist-backend \
    --workpath build/pyinstaller-work \
    --noconfirm \
    --log-level WARN

[ ! -f "dist-backend/veritas-backend" ] && echo "ERROR: binary not found" && exit 1
chmod +x dist-backend/veritas-backend
echo "Binary: $(du -sh dist-backend/veritas-backend | cut -f1)"
echo ""

echo "=== Step 3: Smoke test ==="
VERITAS_API_PORT=47899 PYTHONPATH="$APP" ./dist-backend/veritas-backend &
BPID=$!
sleep 5
RESULT=$(curl -s http://127.0.0.1:47899/health 2>/dev/null)
kill $BPID 2>/dev/null; wait $BPID 2>/dev/null

if echo "$RESULT" | grep -q '"status"'; then
    echo "✅ Smoke test passed: $RESULT"
else
    echo "❌ Smoke test failed — trying direct uvicorn..."
    PYTHONPATH="$APP" python3 -m uvicorn api.main:app --port 47899 --host 127.0.0.1 &
    UPID=$!
    sleep 5
    RESULT2=$(curl -s http://127.0.0.1:47899/health 2>/dev/null)
    kill $UPID 2>/dev/null; wait $UPID 2>/dev/null
    if echo "$RESULT2" | grep -q '"status"'; then
        echo "✅ uvicorn works — binary has issue but app can use .venv fallback"
    else
        echo "❌ Both failed. Result: $RESULT2"
        deactivate
        exit 1
    fi
fi

deactivate

echo ""
echo "=== Step 4: Launching app ==="
echo "Starting AUA-Veritas..."
npx electron .
