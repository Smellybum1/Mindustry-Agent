#!/usr/bin/env bash
# Freeze ADR-0070's public fixed-role baseline before replica A.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

JAVA="${JAVA:-java}"
PORT="${RL_PORT:-47810}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.ippo_baseline \
  --java "$JAVA" \
  --port "$PORT" \
  --output "$ROOT/runs/m9-ippo-v1-shared-expert-baseline.json"
