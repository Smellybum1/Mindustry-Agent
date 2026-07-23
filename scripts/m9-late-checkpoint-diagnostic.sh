#!/usr/bin/env bash
# ADR-0081's exact public immutable-v4 late-checkpoint diagnostic.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

JAVA="${JAVA:-java}"
PORT="${RL_PORT:-47810}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.ippo_late_checkpoint_diagnostic \
  --java "$JAVA" \
  --port "$PORT" \
  --output "$ROOT/runs/m9-ippo-v4-late-checkpoint-diagnostic.json"
