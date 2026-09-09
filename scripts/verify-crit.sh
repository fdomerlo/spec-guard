#!/usr/bin/env bash
# scripts/verify-crit.sh — Deterministic verification of CRIT-XX acceptance criteria
set -euo pipefail

CHANGE="${1:-}"
if [ -z "$CHANGE" ]; then
    if [ -f "SESSION.md" ]; then
        CHANGE=$(grep -oE 'Plan:\s*([a-zA-Z0-9_-]+)' SESSION.md | awk '{print $2}' || true)
    fi
    if [ -z "$CHANGE" ]; then
        CHANGE=$(python3 -m spec_guard.cli list-changes 2>/dev/null | python3 -c "import sys, json; c = json.load(sys.stdin).get('changes', []); print(c[0]['name'] if c else '')" 2>/dev/null || true)
    fi
fi

if [ -z "$CHANGE" ]; then
    echo "Uso: ./scripts/verify-crit.sh <nombre-del-change>" >&2
    exit 1
fi

python3 -m spec_guard.cli verify-crit --change "$CHANGE"
