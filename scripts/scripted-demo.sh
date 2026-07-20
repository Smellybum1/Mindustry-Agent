#!/usr/bin/env bash
# scripted-demo.sh — adaptive public greedy expert and constrained replan variant.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python}"
PORT="${RL_PORT:-47810}"
SEED="${RL_SEED:-12345}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

JAR="$ROOT/rl-server/build/libs/rl-server.jar"
if [[ ! -f "$JAR" ]]; then
  echo "== building rl-server:dist (jar missing) =="
  if [[ -x ./gradlew ]]; then ./gradlew rl-server:dist --console=plain
  else bash ./gradlew rl-server:dist --console=plain; fi
fi

echo "== M7.4 adaptive greedy candidate expert (port=$PORT seed=$SEED) =="
"$PY" -m mindustry_agents.tools.scripted_demo --port "$PORT" --seed "$SEED"

echo
echo "== M7.4 insufficient-copper replan (port=$PORT seed=$SEED) =="
exec "$PY" -m mindustry_agents.tools.scripted_demo \
  --port "$PORT" --seed "$SEED" --blocked-variant
