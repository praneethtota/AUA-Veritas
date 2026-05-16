#!/bin/bash
# reset-and-launch.sh
# Deletes the stale database (wrong schema) and relaunches with fresh schema

APP="/Users/praneethtota/MyProjects/AUA-Veritas"
DB="$HOME/Library/Application Support/AUA-Veritas/veritas.db"

echo "=== AUA-Veritas — Reset DB and Relaunch ==="
echo ""

# Commit schema fix to git
cd "$APP"
git add db/schema.sql
git diff --cached --stat

echo ""
echo "Deleting stale database: $DB"
rm -f "$DB"
echo "✓ Database cleared — will be recreated with correct schema on next launch"

echo ""
echo "Starting backend with fixed schema..."
PYTHONPATH="$APP" "$APP/.venv/bin/python3" -m uvicorn api.main:app \
    --port 47821 --host 127.0.0.1 --log-level info &
BPID=$!
sleep 5

echo ""
RESULT=$(curl -s http://127.0.0.1:47821/health 2>/dev/null)
if echo "$RESULT" | grep -q '"status"'; then
    echo "✅ Backend ready: $RESULT"
    echo ""
    echo "Launching Electron..."
    npx electron .
    kill $BPID 2>/dev/null
else
    echo "❌ Backend failed. Response: $RESULT"
    kill $BPID 2>/dev/null
fi
