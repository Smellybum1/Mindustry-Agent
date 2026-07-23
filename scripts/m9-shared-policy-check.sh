#!/usr/bin/env bash
# M9.1 real-JVM teacher-controlled parity for the all-seat shared model path.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python}"
JAVA="${JAVA:-java}"
PORT="${RL_PORT:-47810}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON" -m mindustry_agents.training.ippo_check \
  --java "$JAVA" \
  --port "$PORT" \
  --output "$ROOT/runs/m9-shared-policy-check.json"
