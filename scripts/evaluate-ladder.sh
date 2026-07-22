#!/usr/bin/env bash
# M7.6 permanent policy ladder and teammate scorecard.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"
PORT="${RL_PORT:-47810}"
WORKERS="${LADDER_WORKERS:-1}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

JAR="$ROOT/rl-server/build/libs/rl-server.jar"
if [[ ! -f "$JAR" ]]; then
  if [[ -x ./gradlew ]]; then ./gradlew rl-server:dist --console=plain
  else bash ./gradlew rl-server:dist --console=plain; fi
fi

"$PY" -m mindustry_agents.tools.evaluate_ladder \
  --port "$PORT" --workers "$WORKERS" "$@"
