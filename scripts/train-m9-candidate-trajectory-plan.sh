#!/usr/bin/env bash
# ADR-0133 governed trajectory-plan construction.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.candidate_trajectory_plan_train \
  --config \
  "$ROOT/configs/training/m9-candidate-native-trajectory-plan-v1.json" \
  --preflight \
  "$ROOT/configs/evaluation/m9-candidate-native-trajectory-plan-v1-preflight-result.json" \
  --output-dir "${M9_OUTPUT_DIR:-$ROOT/runs/m9-candidate-trajectory-plan-a}" \
  --java "${JAVA:-java}" \
  --port "${RL_PORT:-47810}"
