#!/usr/bin/env bash
# Run one non-resumable ADR-0113 distillation replica after exact preflight.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

JAVA="${JAVA:-java}"
PORT="${RL_PORT:-47810}"
OUTPUT_DIR="${M9_DISTILL_OUTPUT_DIR:-$ROOT/runs/m9-candidate-distill-a}"
PREFLIGHT="${M9_DISTILL_PREFLIGHT:-$ROOT/runs/m9-candidate-native-distill-preflight.json}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.candidate_distill \
  --config "$ROOT/configs/training/m9-candidate-native-distill-v1.json" \
  --output-dir "$OUTPUT_DIR" \
  --preflight "$PREFLIGHT" \
  --java "$JAVA" \
  --port "$PORT"
