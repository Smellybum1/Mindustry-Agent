#!/usr/bin/env bash
# evaluate-scripted.sh — five-seed M7.3 greedy-policy evaluation and summaries.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"
PORT="${RL_PORT:-47810}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

JAR="$ROOT/rl-server/build/libs/rl-server.jar"
if [[ ! -f "$JAR" ]]; then
  if [[ -x ./gradlew ]]; then ./gradlew rl-server:dist --console=plain
  else bash ./gradlew rl-server:dist --console=plain; fi
fi

exec "$PY" -m mindustry_agents.tools.evaluate_scripted \
  --port "$PORT" --output "${EVALUATION_OUTPUT:-runs/scripted-evaluation.jsonl}"
