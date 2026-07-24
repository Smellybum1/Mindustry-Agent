#!/usr/bin/env bash
# ADR-0121's exact immutable semantic-target disagreement diagnostic.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

JAVA="${JAVA:-java}"
PORT="${RL_PORT:-47810}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.candidate_semantic_target \
  --java "$JAVA" \
  --port "$PORT" \
  --output "$ROOT/runs/m9-candidate-semantic-target-diagnostic.json"
