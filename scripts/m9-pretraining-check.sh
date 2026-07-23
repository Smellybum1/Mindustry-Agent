#!/usr/bin/env bash
# Complete fail-closed gate before the first governed M9 training episode.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

bash scripts/test-python.sh
bash scripts/test-java.sh
bash scripts/m9-reward-check.sh
bash scripts/m9-shared-policy-check.sh
bash scripts/m9-rollout-check.sh
bash scripts/m9-artifact-check.sh
bash scripts/smoke.sh
bash scripts/determinism.sh
"$PY" -m mindustry_agents.training.ippo_preflight \
  --output "$ROOT/runs/m9-ippo-preflight.json"
