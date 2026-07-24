#!/usr/bin/env bash
# Run one non-resumable ADR-0123 continuation after exact preflight.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

JAVA="${JAVA:-java}"
PORT="${RL_PORT:-47810}"
OUTPUT_DIR="${M9_HARD_EXAMPLE_OUTPUT_DIR:-$ROOT/runs/m9-candidate-hard-example-relabel-a}"
PREFLIGHT="${M9_HARD_EXAMPLE_PREFLIGHT:-$ROOT/runs/m9-candidate-hard-example-relabel-preflight.json}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.candidate_hard_example_relabel \
  --config "$ROOT/configs/training/m9-candidate-native-hard-example-relabel-v1.json" \
  --output-dir "$OUTPUT_DIR" \
  --preflight "$PREFLIGHT" \
  --java "$JAVA" \
  --port "$PORT"
