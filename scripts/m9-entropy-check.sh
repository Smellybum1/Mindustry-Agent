#!/usr/bin/env bash
# ADR-0079 exact v3 inheritance and entropy-schedule check.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.ippo_entropy_check \
  --output "$ROOT/runs/m9-ippo-v4-entropy-check.json"
