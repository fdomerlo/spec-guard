#!/usr/bin/env bash
# scripts/verify-crit.sh — Deterministic verification of CRIT-XX acceptance criteria
set -euo pipefail

CHANGE=""
EXTRA_ARGS=()
for arg in "$@"; do
    if [[ "$arg" == --* ]]; then
        EXTRA_ARGS+=("$arg")
    elif [ -z "$CHANGE" ]; then
        CHANGE="$arg"
    else
        EXTRA_ARGS+=("$arg")
    fi
done

if [ -z "$CHANGE" ]; then
    CHANGE=$(python3 -m spec_guard.cli list-changes 2>/dev/null | python3 -c "import sys, json; c = json.load(sys.stdin).get('changes', []); print(c[0]['name'] if c else '')" 2>/dev/null || true)
fi

if [ -z "$CHANGE" ]; then
    echo "Uso: ./scripts/verify-crit.sh <nombre-del-change> [--run-tests]" >&2
    exit 1
fi

python3 -m spec_guard.cli verify-crit --change "$CHANGE" "${EXTRA_ARGS[@]}"
