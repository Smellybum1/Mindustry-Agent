#!/usr/bin/env bash
# ADR-0125's exact immutable public-only planner-correction diagnostic.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

JAVA="${JAVA:-java}"
PORT="${RL_PORT:-47810}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.planner_correction_causality \
  --java "$JAVA" \
  --port "$PORT" \
  --output "$ROOT/runs/m9-planner-correction-causality-v1.json"
