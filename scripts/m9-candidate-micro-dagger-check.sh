#!/usr/bin/env bash
# ADR-0129 exact-commit micro-DAgger preflight.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.candidate_micro_dagger_check \
  --java "${JAVA:-java}" \
  --port "${RL_PORT:-47810}" \
  --output "$ROOT/runs/m9-candidate-micro-dagger-preflight.json"
