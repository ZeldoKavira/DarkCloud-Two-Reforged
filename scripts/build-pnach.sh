#!/usr/bin/env bash
# Combines all pnach files in pcsx2-files/pnach/ into a single 1DF41F33.pnach
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PNACH_DIR="$SCRIPT_DIR/../pcsx2-files/pnach"
OUT="$SCRIPT_DIR/../pcsx2-files/1DF41F33.pnach"

echo "gametitle=Dark Cloud 2 [SCUS 97213] (U) [1DF41F33]" > "$OUT"

for f in "$PNACH_DIR"/*.pnach; do
    name="$(basename "$f" .pnach)"
    echo "" >> "$OUT"
    echo "// ======== $name ========" >> "$OUT"
    # Strip blank lines at start/end, keep comments and patch lines
    sed '/^$/d' "$f" >> "$OUT"
done

count=$(grep -c '^patch=' "$OUT" || true)
echo "Built $OUT ($count patches from $(ls "$PNACH_DIR"/*.pnach | wc -l | tr -d ' ') files)"
