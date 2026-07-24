#!/usr/bin/env bash
# ADR-0125's fail-closed public-only implementation check.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m pytest \
  python/tests/test_planner_correction_causality.py \
  python/tests/test_candidate_critical_disagreement.py \
  python/tests/test_candidate_semantic_target.py \
  -q
"$PY" -c \
  "from pathlib import Path; from mindustry_agents.training.planner_correction_causality import validate_inputs; protocol, _, seeds = validate_inputs(Path.cwd()); assert protocol['data_classification'] == 'public_dev_only'; assert len(seeds) == 40"
