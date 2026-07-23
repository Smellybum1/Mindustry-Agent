#!/usr/bin/env bash
# Reconstruct the pinned CPU runtime and run ADR-0070's exact M9 replicas.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="${1:-all}"
UV="${UV:-uv}"
JAVA="${JAVA:-java}"
BASE_PORT="${RL_PORT:-47810}"
LOCK="$ROOT/python/requirements-rl-linux-py312.lock"
JAR="$ROOT/rl-server/build/libs/rl-server.jar"
PREFLIGHT="${M9_PREFLIGHT:-$ROOT/runs/m9-ippo-preflight.json}"
PRIMARY_OUT="${M9_PRIMARY_OUT:-$ROOT/runs/m9-ippo-v1-a}"
REPLICA_OUT="${M9_REPLICA_OUT:-$ROOT/runs/m9-ippo-v1-b}"
COMPARISON_OUT="${M9_COMPARISON_OUT:-$ROOT/runs/m9-ippo-v1-replicas.json}"

case "$MODE" in
  a|b|compare|all) ;;
  *)
    echo "ERROR: mode must be a, b, compare, or all" >&2
    exit 1
    ;;
esac
if [[ "$(uname -s)" != "Linux" ]]; then
  echo "ERROR: M9 IPPO training requires Linux/WSL2" >&2
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
if [[ ! -f "$LOCK" || ! -f "$JAR" || ! -f "$PREFLIGHT" ]]; then
  echo "ERROR: missing lock, rl-server jar, or exact-commit preflight" >&2
  exit 1
fi

VENV="$(mktemp -d "${TMPDIR:-/tmp}/mindustry-m9-ippo.XXXXXX")"
cleanup(){ rm -rf -- "$VENV"; }
trap cleanup EXIT

"$UV" venv --python 3.12 --no-project "$VENV"
"$UV" pip sync --python "$VENV/bin/python" "$LOCK"
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"

run_replica(){
  local label="$1"
  local output="$2"
  set +e
  "$VENV/bin/python" -m mindustry_agents.training.ippo_train \
    --config "$ROOT/configs/training/m9-ippo-v1.json" \
    --output-dir "$output" \
    --preflight "$PREFLIGHT" \
    --java "$JAVA" \
    --port "$BASE_PORT"
  local status=$?
  set -e
  if [[ "$status" -ne 0 && "$status" -ne 2 ]]; then
    echo "ERROR: replica $label failed before a governed result" >&2
    exit "$status"
  fi
  return "$status"
}

compare_replicas(){
  "$VENV/bin/python" -m mindustry_agents.training.ippo_train \
    --compare-runs \
    "$PRIMARY_OUT/ippo-v1-run.manifest.json" \
    "$REPLICA_OUT/ippo-v1-run.manifest.json" \
    --comparison-output "$COMPARISON_OUT"
}

case "$MODE" in
  a)
    run_replica A "$PRIMARY_OUT"
    ;;
  b)
    run_replica B "$REPLICA_OUT"
    ;;
  compare)
    compare_replicas
    ;;
  all)
    replica_a_status=0
    replica_b_status=0
    run_replica A "$PRIMARY_OUT" || replica_a_status=$?
    run_replica B "$REPLICA_OUT" || replica_b_status=$?
    compare_replicas
    comparison_status=$?
    if [[ "$replica_a_status" -eq 2 || "$replica_b_status" -eq 2 ]]; then
      exit 2
    fi
    exit "$comparison_status"
    ;;
esac
