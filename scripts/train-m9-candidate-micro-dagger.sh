#!/usr/bin/env bash
# Run one non-resumable ADR-0129 micro-DAgger replica.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.candidate_micro_dagger \
  --config "$ROOT/configs/training/m9-candidate-native-micro-dagger-v1.json" \
  --output-dir "${M9_MICRO_DAGGER_OUTPUT_DIR:-$ROOT/runs/m9-candidate-micro-dagger-a}" \
  --preflight "${M9_MICRO_DAGGER_PREFLIGHT:-$ROOT/runs/m9-candidate-micro-dagger-preflight.json}" \
  --java "${JAVA:-java}" \
  --port "${RL_PORT:-47810}"
