#!/usr/bin/env bash
# M9.1 stochastic all-seat rollout and terminal-reset reproduction gate.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

JAVA="${JAVA:-java}"
PORT="${RL_PORT:-47810}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.ippo_rollout_check \
  --java "$JAVA" \
  --port "$PORT" \
  --output "$ROOT/runs/m9-ippo-rollout-check.json"
