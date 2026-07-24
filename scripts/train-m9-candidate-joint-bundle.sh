#!/usr/bin/env bash
# ADR-0135 governed joint-bundle construction.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.candidate_joint_bundle_train \
  --config \
  "$ROOT/configs/training/m9-candidate-native-joint-bundle-v1.json" \
  --preflight \
  "${M9_JOINT_BUNDLE_PREFLIGHT:-$ROOT/runs/m9-candidate-joint-bundle-preflight.json}" \
  --output-dir "${M9_OUTPUT_DIR:-$ROOT/runs/m9-candidate-joint-bundle-a}" \
  --java "${JAVA:-java}" \
  --port "${RL_PORT:-47810}"
