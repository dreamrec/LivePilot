#!/usr/bin/env bash
# Blessed test entrypoint — always uses the repo's .venv so contributors
# don't get misleading failures from system-Python / missing pytest-asyncio.
#
# Usage:
#   scripts/test.sh                 # full suite
#   scripts/test.sh tests/test_x.py # subset
#   scripts/test.sh -k keyword      # pytest -k
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PY="$ROOT/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
    echo "error: $VENV_PY not found." >&2
    echo "Create a venv first:" >&2
    echo "    python3 -m venv .venv" >&2
    echo "    .venv/bin/pip install -r requirements.txt pytest pytest-asyncio" >&2
    exit 2
fi

cd "$ROOT"
exec "$VENV_PY" -m pytest "$@"
