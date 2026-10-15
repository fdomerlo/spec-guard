#!/usr/bin/env bash
# scripts/verify-crit.sh — Deterministic verification of CRIT-XX acceptance criteria
set -euo pipefail

CHANGE="${1:-}"
if [ -z "$CHANGE" ]; then
    for SESSION_FILE in ".spec-guard/SESSION.md" "SESSION.md"; do
        if [ -f "$SESSION_FILE" ]; then
            CHANGE=$(grep -oE 'Plan:\*{0,2}\s*([a-zA-Z0-9_-]+)' "$SESSION_FILE" | awk '{print $NF}' || true)
            [ -n "$CHANGE" ] && break
        fi
    done
    if [ -z "$CHANGE" ]; then
        CHANGE=$(python3 -m spec_guard.cli list-changes 2>/dev/null | python3 -c "import sys, json; c = json.load(sys.stdin).get('changes', []); print(c[0]['name'] if c else '')" 2>/dev/null || true)
    fi
fi

if [ -z "$CHANGE" ]; then
    echo "Uso: ./scripts/verify-crit.sh <nombre-del-change>" >&2
    exit 1
fi

python3 -m spec_guard.cli verify-crit --change "$CHANGE"
