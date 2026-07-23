#!/usr/bin/env bash
# Verify ADR-0083 inheritance and success-imitation optimizer semantics.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"
"$PY" -m mindustry_agents.training.ippo_success_imitation_check "$@"
