#!/usr/bin/env bash
# ADR-0133 exact-commit trajectory-plan preflight.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m pytest \
  python/tests/test_candidate_trajectory_plan.py \
  python/tests/test_candidate_sequence_relabel.py \
  -q \
  --basetemp="$ROOT/runs/.pytest-trajectory-plan-check"
"$PY" -m mindustry_agents.training.candidate_trajectory_plan_check \
  --java "${JAVA:-java}" \
  --port "${RL_PORT:-47810}" \
  --output "$ROOT/runs/m9-candidate-trajectory-plan-preflight.json"
