#!/usr/bin/env bash
# M8.3 WSL2 gate: locked CPU shadow inference on the real event-driven
# collector, then the long-run reset test. No package is installed globally.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

UV="${UV:-uv}"
JAVA="${JAVA:-java}"
RESETS="${M8_RESETS:-10000}"
EPISODES="${M8_EPISODES:-1}"
POOLS="${M8_POOLS:-1 2 4}"
BASE_PORT="${RL_PORT:-47810}"
LOCK="$ROOT/python/requirements-rl-linux-py312.lock"
JAR="$ROOT/rl-server/build/libs/rl-server.jar"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "ERROR: M8.3 training gate requires Linux/WSL2" >&2
  exit 1
fi
if [[ "$("$UV" --version 2>/dev/null)" != "uv 0.11.16"* ]]; then
  echo "ERROR: UV must point to uv 0.11.16" >&2
  exit 1
fi
java_version="$("$JAVA" -version 2>&1)"
if [[ "$java_version" != *'Temurin-21.0.11+10'* ]]; then
  echo "ERROR: JAVA must point to pinned Temurin 21.0.11+10" >&2
  echo "found: $java_version" >&2
  exit 1
fi
if [[ ! -f "$LOCK" || ! -f "$JAR" ]]; then
  echo "ERROR: missing lock or rl-server jar; build the jar before the WSL2 gate" >&2
  exit 1
fi
if [[ ! "$RESETS" =~ ^[0-9]+$ ]] || (( RESETS < 1 )); then
  echo "ERROR: M8_RESETS must be a positive integer" >&2
  exit 1
fi

VENV="$(mktemp -d "${TMPDIR:-/tmp}/mindustry-m8-gate.XXXXXX")"
cleanup(){ rm -rf -- "$VENV"; }
trap cleanup EXIT

"$UV" venv --python 3.12 --no-project "$VENV"
"$UV" pip sync --python "$VENV/bin/python" "$LOCK"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"
# A checkout mounted from Windows can make WSL git report every CRLF file as
# modified. Use the checkout's Git for Windows binary when available so the
# manifest records the real worktree state; native Linux keeps ordinary git.
if [[ -x "/mnt/c/Program Files/Git/cmd/git.exe" ]] && command -v wslpath >/dev/null 2>&1; then
  export M8_GIT="/mnt/c/Program Files/Git/cmd/git.exe"
  export M8_GIT_ROOT="$(wslpath -w "$ROOT")"
fi

read -r -a pool_args <<< "$POOLS"
echo "== M8.3 throughput gate =="
"$VENV/bin/python" -m mindustry_agents.training.throughput \
  --java "$JAVA" \
  --base-port "$BASE_PORT" \
  --pools "${pool_args[@]}" \
  --episodes "$EPISODES" \
  --max-chunk 600 \
  --output "$ROOT/runs/m8-throughput.json"

echo "== M8.3 long-run reset gate =="
"$VENV/bin/python" -m mindustry_agents.tools.stress_reset \
  --java "$JAVA" \
  --port "$BASE_PORT" \
  --resets "$RESETS" \
  --seed 12345 \
  --sample-every 100 \
  --max-heap 350m \
  --json-output "$ROOT/runs/m8-stress-reset.json"

echo "TRAINING-GATE OK"
