#!/usr/bin/env bash
# ADR-0131's fail-closed public-only implementation and live check.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

JAVA="${JAVA:-java}"
PORT="${RL_PORT:-47810}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m pytest \
  python/tests/test_planner_trajectory_divergence.py \
  python/tests/test_planner_correction_causality.py \
  -q
"$PY" -m mindustry_agents.training.planner_trajectory_divergence_check \
  --java "$JAVA" \
  --port "$PORT" \
  --output \
  "$ROOT/runs/m9-planner-trajectory-divergence-v1-live-preflight.json"
