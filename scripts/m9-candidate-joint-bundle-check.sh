#!/usr/bin/env bash
# ADR-0135 exact-commit joint-bundle preflight.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m pytest \
  python/tests/test_candidate_joint_bundle.py \
  -q \
  --basetemp="$ROOT/runs/.pytest-joint-bundle-check"
"$PY" -m mindustry_agents.training.candidate_joint_bundle_check \
  --java "${JAVA:-java}" \
  --port "${RL_PORT:-47810}" \
  --output "$ROOT/runs/m9-candidate-joint-bundle-preflight.json"
