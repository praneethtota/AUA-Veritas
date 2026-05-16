#!/bin/bash
# update-and-launch.sh — pull latest, rebuild UI, restart
set -e
APP="/Users/praneethtota/MyProjects/AUA-Veritas"
cd "$APP"

echo "=== Step 1: Pull latest fixes ==="
git stash 2>/dev/null || true
git pull origin main
echo "✓ Pulled"

echo ""
echo "=== Step 2: Rebuild UI ==="
cd ui && npm install --silent && npm run build
cd ..
echo "✓ UI rebuilt ($(du -sh ui/dist | cut -f1))"

echo ""
echo "=== Step 3: Check what 422 payload looks like ==="
# Kill any existing backend
pkill -f "uvicorn api.main:app" 2>/dev/null || true
sleep 1

# Start fresh backend
PYTHONPATH="$APP" "$APP/.venv/bin/python3" -m uvicorn api.main:app \
    --port 47821 --host 127.0.0.1 --log-level info &
BPID=$!
sleep 5

echo "Testing query with gpt-4o..."
curl -s -X POST http://127.0.0.1:47821/query \
  -H "Content-Type: application/json" \
  -d '{"query":"what is 2+2","conversation_id":"test-1","accuracy_level":"fast","enabled_models":["gpt-4o"],"conversation_history":[]}' \
  | python3 -m json.tool

echo ""
echo "=== Step 4: Launch Electron ==="
echo "Backend PID: $BPID (keep running)"
echo ""
npx electron .

kill $BPID 2>/dev/null
