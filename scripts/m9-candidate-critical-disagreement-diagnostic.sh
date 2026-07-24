#!/usr/bin/env bash
# ADR-0119's exact immutable student-controlled disagreement diagnostic.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

JAVA="${JAVA:-java}"
PORT="${RL_PORT:-47810}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.candidate_critical_disagreement \
  --java "$JAVA" \
  --port "$PORT" \
  --output "$ROOT/runs/m9-candidate-on-policy-critical-disagreement.json"
