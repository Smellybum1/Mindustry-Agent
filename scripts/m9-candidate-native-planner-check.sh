#!/usr/bin/env bash
# ADR-0091's public-only candidate-native planner survival gate.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

JAVA="${JAVA:-java}"
PORT="${RL_PORT:-47810}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.ippo_candidate_planner \
  --java "$JAVA" \
  --port "$PORT" \
  --output "$ROOT/runs/m9-candidate-native-planner-v1-result.json"
