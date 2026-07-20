#!/usr/bin/env bash
# benchmark.sh — scaling + timing report (roadmap M2).
# Builds the rl-server fat jar if missing, then measures three layers: single-env
# engine ticks/sec + reset latency, protocol overhead (round-trip minus engine),
# and aggregate ticks/sec scaling across 1/2/4 concurrent JVMs. Prints a markdown
# report. Concurrency is capped at 4 JVMs on purpose (shared workstation).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python}"
BASE_PORT="${RL_PORT:-47810}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

JAR="$ROOT/rl-server/build/libs/rl-server.jar"
if [[ ! -f "$JAR" ]]; then
  echo "== building rl-server:dist (jar missing) =="
  if [[ -x ./gradlew ]]; then ./gradlew rl-server:dist --console=plain
  else bash ./gradlew rl-server:dist --console=plain; fi
fi

echo "== rl-server benchmark (base-port=$BASE_PORT) =="
exec "$PY" -m mindustry_agents.tools.benchmark --base-port "$BASE_PORT"
