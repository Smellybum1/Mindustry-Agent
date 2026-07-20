#!/usr/bin/env bash
# smoke.sh — live protocol, skill-ledger, combat, M4 acceptance, and loss checks.
# Builds the rl-server fat jar if missing, then runs the Python harnesses in order.
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
"$PY" -m mindustry_agents.tools.smoke --port "$PORT" --seed "$SEED"

echo
echo "== M5.2 coordination check (port=$PORT seed=$SEED) =="
"$PY" -m mindustry_agents.tools.coordination_check --port "$PORT" --seed "$SEED"

echo
echo "== M5.3 scripted policy check (port=$PORT seed=$SEED) =="
"$PY" -m mindustry_agents.tools.policy_check --port "$PORT" --seed "$SEED"

echo
echo "== rl-server combat check (port=$PORT seed=$SEED) =="
"$PY" -m mindustry_agents.tools.combat_check --port "$PORT" --seed "$SEED"

echo
echo "== Milestone 4 acceptance (port=$PORT seed=$SEED) =="
"$PY" -m mindustry_agents.tools.m4_acceptance --port "$PORT" --seed "$SEED"

echo
echo "== rl-server scenario check (port=$PORT seed=$SEED) =="
exec "$PY" -m mindustry_agents.tools.scenario_check --port "$PORT" --seed "$SEED"
