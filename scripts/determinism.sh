#!/usr/bin/env bash
# determinism.sh — golden replay / hash check (roadmap M1).
# Builds the rl-server fat jar if missing, then runs the Python determinism
# harness: two fresh JVMs with the same seed must match hash-for-hash, and two
# resets in one JVM must produce identical initial hashes. Exit 0 iff all match.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"
PORT="${RL_PORT:-47810}"
SEED="${RL_SEED:-12345}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

JAR="$ROOT/rl-server/build/libs/rl-server.jar"
if [[ ! -f "$JAR" ]]; then
  echo "== building rl-server:dist (jar missing) =="
  if [[ -x ./gradlew ]]; then ./gradlew rl-server:dist --console=plain
  else bash ./gradlew rl-server:dist --console=plain; fi
fi

echo "== rl-server determinism (port=$PORT seed=$SEED) =="
"$PY" -m mindustry_agents.tools.determinism --port "$PORT" --seed "$SEED"

echo
echo "== M6 golden scripted replay (port=$PORT) =="
NEGATIVE=()
if [[ "${REPLAY_NEGATIVE:-0}" == "1" ]]; then NEGATIVE=(--negative-check); fi
exec "$PY" -m mindustry_agents.tools.replay --port "$PORT" "${NEGATIVE[@]}"
