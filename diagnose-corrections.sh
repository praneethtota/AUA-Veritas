#!/bin/bash
# diagnose-corrections.sh — inspect what's in the corrections table

DB="$HOME/Library/Application Support/AUA-Veritas/veritas.db"
echo "=== Corrections table ==="
sqlite3 "$DB" "SELECT correction_id, scope, domain, canonical_query, corrective_instruction, created_at FROM corrections ORDER BY created_at DESC LIMIT 10;" 2>/dev/null || echo "DB not found or empty"

echo ""
echo "=== All corrections count ==="
sqlite3 "$DB" "SELECT count(*) FROM corrections;" 2>/dev/null

echo ""
echo "=== Non-superseded corrections ==="
sqlite3 "$DB" "SELECT scope, domain, canonical_query, substr(corrective_instruction,1,80) FROM corrections WHERE scope != 'superseded';" 2>/dev/null

echo ""
echo "=== Simulate retrieve for 'What database should I use' ==="
sqlite3 "$DB" "SELECT correction_id, domain, scope, canonical_query, substr(corrective_instruction,1,80) FROM corrections WHERE user_id='local' AND domain='software_engineering';" 2>/dev/null
