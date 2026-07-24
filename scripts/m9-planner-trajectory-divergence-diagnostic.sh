#!/usr/bin/env bash
# ADR-0131's exact public-only planner trajectory-divergence diagnostic.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

JAVA="${JAVA:-java}"
PORT="${RL_PORT:-47810}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.planner_trajectory_divergence \
  --java "$JAVA" \
  --port "$PORT" \
  --output "$ROOT/runs/m9-planner-trajectory-divergence-v1.json"
