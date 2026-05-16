#!/bin/bash
# rebuild-backend.sh
# Rebuilds the PyInstaller binary with the fixed field_classifier.py
# Run from ~/MyProjects/AUA-Veritas

set -e
APP="/Users/praneethtota/MyProjects/AUA-Veritas"
cd "$APP"

echo "=== Rebuilding PyInstaller backend binary ==="
echo ""

# Activate venv
source .venv/bin/activate

echo "1. Cleaning old build..."
rm -rf dist-backend build/pyinstaller-work

echo "2. Running PyInstaller with fixed field_classifier..."
pyinstaller build/veritas-backend.spec \
    --distpath dist-backend \
    --workpath build/pyinstaller-work \
    --noconfirm \
    --log-level WARN

[ ! -f "dist-backend/veritas-backend" ] && echo "ERROR: binary not found" && exit 1
chmod +x dist-backend/veritas-backend
echo ""
echo "3. Binary built: $(du -sh dist-backend/veritas-backend | cut -f1)"

echo ""
echo "4. Smoke testing..."
VERITAS_API_PORT=47899 PYTHONPATH="$APP" ./dist-backend/veritas-backend &
BPID=$!
sleep 5

RESULT=$(curl -s http://127.0.0.1:47899/health 2>/dev/null)
if echo "$RESULT" | grep -q '"status"'; then
    echo "✅ Binary smoke test passed: $RESULT"
else
    echo "❌ Binary failed health check"
    echo "Result: $RESULT"
fi

kill $BPID 2>/dev/null
wait $BPID 2>/dev/null
deactivate

echo ""
echo "Done! Now run: npx electron ."
