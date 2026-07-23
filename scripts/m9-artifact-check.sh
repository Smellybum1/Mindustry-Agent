#!/usr/bin/env bash
# M9.1 checkpoint reconstruction and manifest-lineage pretraining gate.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

JAVA="${JAVA:-java}"
PORT="${RL_PORT:-47810}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PY" -m mindustry_agents.training.ippo_artifact_check \
  --java "$JAVA" \
  --port "$PORT" \
  --output "$ROOT/runs/m9-ippo-artifact-check.json"
