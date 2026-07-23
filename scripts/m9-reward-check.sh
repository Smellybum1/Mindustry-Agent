#!/usr/bin/env bash
# M9.1 CPU-only adversarial gate for the precommitted individual shaping.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON" -m mindustry_agents.training.ippo_reward_adversary \
  --config "$ROOT/configs/training/m9-ippo-v1.json" \
  --output "$ROOT/runs/m9-ippo-reward-adversaries.json"
