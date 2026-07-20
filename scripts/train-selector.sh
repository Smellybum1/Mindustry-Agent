#!/usr/bin/env bash
# M8.4 WSL2 gate: reconstruct the exact CPU lock, pass reward adversaries,
# train only on train seeds, select only on dev, and verify fresh replay parity.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

UV="${UV:-uv}"
JAVA="${JAVA:-java}"
BASE_PORT="${RL_PORT:-47810}"
LOCK="$ROOT/python/requirements-rl-linux-py312.lock"
JAR="$ROOT/rl-server/build/libs/rl-server.jar"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "ERROR: M8.4 selector training requires Linux/WSL2" >&2
  exit 1
fi
if [[ "$("$UV" --version 2>/dev/null)" != "uv 0.11.16"* ]]; then
  echo "ERROR: UV must point to uv 0.11.16" >&2
  exit 1
fi
java_version="$("$JAVA" -version 2>&1)"
if [[ "$java_version" != *'Temurin-21.0.11+10'* ]]; then
  echo "ERROR: JAVA must point to pinned Temurin 21.0.11+10" >&2
  exit 1
fi
if [[ ! -f "$LOCK" || ! -f "$JAR" ]]; then
  echo "ERROR: missing lock or rl-server jar; build before training" >&2
  exit 1
fi

VENV="$(mktemp -d "${TMPDIR:-/tmp}/mindustry-m8-selector.XXXXXX")"
cleanup(){ rm -rf -- "$VENV"; }
trap cleanup EXIT

"$UV" venv --python 3.12 --no-project "$VENV"
"$UV" pip sync --python "$VENV/bin/python" "$LOCK"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"
if [[ -x "/mnt/c/Program Files/Git/cmd/git.exe" ]] && command -v wslpath >/dev/null 2>&1; then
  export M8_GIT="/mnt/c/Program Files/Git/cmd/git.exe"
  export M8_GIT_ROOT="$(wslpath -w "$ROOT")"
fi

echo "== M8.4 reward adversaries =="
"$VENV/bin/python" -m mindustry_agents.training.reward_adversary \
  --output "$ROOT/runs/m8-selector-v1/reward-adversaries.json"

echo "== M8.4 one-seat PPO =="
"$VENV/bin/python" -m mindustry_agents.training.ppo_selector \
  --config "$ROOT/configs/training/m8-selector-v1.json" \
  --output-dir "$ROOT/runs/m8-selector-v1" \
  --java "$JAVA" \
  --port "$BASE_PORT"

echo "TRAIN-SELECTOR OK"
