#!/usr/bin/env bash
# V47 public live single-brain death-failover acceptance check.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"
PORT="${RL_PORT:-47847}"
JAVA="${JAVA:-java}"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

JAR="$ROOT/rl-server/build/libs/rl-server.jar"
if [[ ! -f "$JAR" ]]; then
  if [[ -x ./gradlew ]]; then ./gradlew rl-server:dist --console=plain
  else bash ./gradlew rl-server:dist --console=plain; fi
fi

exec "$PY" -m mindustry_agents.tools.single_brain_failover_check \
  --port "$PORT" \
  --java "$JAVA"
