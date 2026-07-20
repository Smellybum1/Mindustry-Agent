#!/usr/bin/env bash
# test-python.sh — run the Python unit tests. Prefers pytest; falls back to the
# stdlib unittest runner so a bare checkout with zero third-party deps still runs.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

if "$PY" -m pytest --version >/dev/null 2>&1; then
  echo "== pytest =="
  exec "$PY" -m pytest python/tests -q
else
  echo "== unittest (pytest not installed) =="
  exec "$PY" -m unittest discover -s python/tests -p 'test_*.py' -v
fi
