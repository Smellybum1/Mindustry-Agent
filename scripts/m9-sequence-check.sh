#!/usr/bin/env bash
# ADR-0073 cross-process recurrent optimizer/checkpoint determinism gate.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.ippo_sequence_check \
  --output "$ROOT/runs/m9-ippo-v2-sequence-check.json"
