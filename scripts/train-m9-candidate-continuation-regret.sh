#!/usr/bin/env bash
# Run one non-resumable ADR-0137 construction replica after exact preflight.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.candidate_continuation_regret_train \
  --config \
  "$ROOT/configs/training/m9-candidate-native-continuation-regret-v1.json" \
  --output-dir \
  "${M9_CONTINUATION_OUTPUT:-$ROOT/runs/m9-candidate-continuation-regret-a}" \
  --preflight \
  "${M9_CONTINUATION_PREFLIGHT:-$ROOT/runs/m9-candidate-continuation-regret-preflight.json}" \
  --java "${JAVA:-java}" \
  --port "${RL_PORT:-47810}"
