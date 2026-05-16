#!/bin/bash
# diagnose.sh — test the /query endpoint and capture the full error

APP="/Users/praneethtota/MyProjects/AUA-Veritas"
VENV="$APP/.venv/bin/python3"

echo "=== Starting backend ==="
cd "$APP"
PYTHONPATH="$APP" "$VENV" -m uvicorn api.main:app \
    --port 47821 --host 127.0.0.1 --log-level debug 2>&1 &
BPID=$!
sleep 5

echo ""
echo "=== Health check ==="
curl -s http://127.0.0.1:47821/health | python3 -m json.tool

echo ""
echo "=== Test query (no models) ==="
curl -s -X POST http://127.0.0.1:47821/query \
  -H "Content-Type: application/json" \
  -d '{"query":"what is 2+2","conversation_id":"diag-test","accuracy_level":"fast","enabled_models":[],"conversation_history":[]}' \
  | python3 -m json.tool

echo ""
echo "=== Test conversations endpoint ==="
curl -s http://127.0.0.1:47821/conversations | python3 -m json.tool

echo ""
echo "=== Test models endpoint ==="
curl -s http://127.0.0.1:47821/models | python3 -m json.tool

echo ""
echo "=== Backend stderr output (last 30 lines) ==="
kill $BPID 2>/dev/null
wait $BPID 2>/dev/null
