#!/usr/bin/env bash
# ADR-0137 focused exact-commit public continuation-regret preflight.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m pytest \
  python/tests/test_candidate_continuation_regret.py \
  -q \
  --basetemp="$ROOT/runs/.pytest-continuation-regret-check"
"$PY" -m mindustry_agents.training.candidate_continuation_regret_check \
  --java "${JAVA:-java}" \
  --port "${RL_PORT:-47810}" \
  --output "$ROOT/runs/m9-candidate-continuation-regret-preflight.json"
