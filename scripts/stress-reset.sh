#!/usr/bin/env bash
# stress-reset.sh — repeated in-memory reset test (roadmap M2).
# Builds the rl-server fat jar if missing, then boots ONE persistent JVM and
# resets it 1000x with the same seed: every initial hash must match, reset
# latency (median/p95/max) is reported, and the child's RSS is sampled to check
# for leaks. Exit 0 iff hashes are stable and no leak is detected.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"
RESETS="${RL_RESETS:-1000}"
SEED="${RL_SEED:-12345}"
PORT="${RL_PORT:-47810}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

JAR="$ROOT/rl-server/build/libs/rl-server.jar"
if [[ ! -f "$JAR" ]]; then
  echo "== building rl-server:dist (jar missing) =="
  if [[ -x ./gradlew ]]; then ./gradlew rl-server:dist --console=plain
  else bash ./gradlew rl-server:dist --console=plain; fi
fi

echo "== rl-server stress-reset (resets=$RESETS seed=$SEED) =="
exec "$PY" -m mindustry_agents.tools.stress_reset \
  --resets "$RESETS" --seed "$SEED" --port "$PORT"
