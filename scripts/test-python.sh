#!/usr/bin/env bash
# test-python.sh — run the Python unit tests. Prefers pytest for the complete
# suite; falls back to the governed stdlib-only core boundary so a bare checkout
# with zero third-party deps still runs.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

if "$PY" -m pytest --version >/dev/null 2>&1; then
  echo "== pytest =="
  exec "$PY" -m pytest python/tests -q
else
  echo "== unittest core boundary (pytest not installed) =="
  export PYTHONPATH="$ROOT/python/src:$ROOT/python/tests${PYTHONPATH:+:$PYTHONPATH}"
  exec "$PY" -S -m unittest -v \
    test_import test_protocol test_env test_supervisor
fi
