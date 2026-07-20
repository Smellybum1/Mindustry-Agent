#!/usr/bin/env bash
# build.sh — build Java modules + Python package.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python}"

echo "== Java modules =="
./gradlew rl-server:dist agent-core:classes agent-plugin:classes --console=plain

echo
echo "== Python package sanity =="
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"
"$PY" -c "import mindustry_agents, mindustry_agents.protocol; print('mindustry_agents', mindustry_agents.__version__)"

echo
echo "build: OK"
