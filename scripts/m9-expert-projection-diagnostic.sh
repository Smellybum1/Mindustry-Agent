#!/usr/bin/env bash
# ADR-0089's public-only shared-expert candidate-projection diagnostic.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

JAVA="${JAVA:-java}"
PORT="${RL_PORT:-47810}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.ippo_expert_projection \
  --java "$JAVA" \
  --port "$PORT" \
  --output "$ROOT/runs/m9-shared-expert-candidate-projection-result.json"
