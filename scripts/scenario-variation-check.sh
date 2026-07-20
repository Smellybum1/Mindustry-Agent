#!/usr/bin/env bash
# M7.5 scenario-v2 variation, reset determinism, and frozen-dev acceptance.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python}"
PORT="${RL_PORT:-47810}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

JAR="$ROOT/rl-server/build/libs/rl-server.jar"
if [[ ! -f "$JAR" ]]; then
  if [[ -x ./gradlew ]]; then ./gradlew rl-server:dist --console=plain
  else bash ./gradlew rl-server:dist --console=plain; fi
fi

"$PY" -m mindustry_agents.tools.scenario_variation_check --port "$PORT"
"$PY" -m mindustry_agents.tools.scenario_check \
  --port "$PORT" --scenario-id bootstrap-defense-v1 --seed 2001
