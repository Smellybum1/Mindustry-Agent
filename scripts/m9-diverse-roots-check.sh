#!/usr/bin/env bash
# Verify ADR-0075's exact public train membership and one-use schedule.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"
"$PY" scripts/freeze-m9-v3-train-seed-set.py --check
"$PY" -m mindustry_agents.training.ippo_diverse_roots_check \
  --output "$ROOT/runs/m9-ippo-v3-diverse-roots-check.json"
