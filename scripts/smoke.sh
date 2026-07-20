#!/usr/bin/env bash
# smoke.sh — one reset/step/close against a live rl-server JVM (roadmap M1).
# Builds the rl-server fat jar if missing, then runs the Python smoke harness:
# handshake, reset(seed), step 600 ticks in 10x60 chunks, print transcript, exit 0.
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

echo "== rl-server smoke (port=$PORT seed=$SEED) =="
exec "$PY" -m mindustry_agents.tools.smoke --port "$PORT" --seed "$SEED"
