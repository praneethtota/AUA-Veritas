#!/bin/bash
# hotfix.sh — fix model_id bug, rebuild UI, restart backend, launch
set -e
APP="/Users/praneethtota/MyProjects/AUA-Veritas"
cd "$APP"

echo "Rebuilding UI..."
cd ui && npm run build --silent && cd ..
echo "✓ UI rebuilt"

echo "Restarting backend..."
pkill -f "uvicorn api.main" 2>/dev/null || true
pkill -f "veritas-backend" 2>/dev/null || true
sleep 2

PYTHONPATH="$APP" "$APP/.venv/bin/python3" -m uvicorn api.main:app \
    --port 47821 --host 127.0.0.1 --log-level warning &
BPID=$!
sleep 4

echo "Testing /models endpoint..."
curl -s http://127.0.0.1:47821/models | python3 -c "
import sys, json
models = json.load(sys.stdin)
for mid, m in models.items():
    if m.get('connected'):
        print(f'  Connected: {mid}  model_id field: {m.get(\"model_id\", \"MISSING\")}')
"

echo ""
echo "Launching Electron..."
npx electron .
kill $BPID 2>/dev/null
