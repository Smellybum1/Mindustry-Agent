#!/usr/bin/env bash
# Reconstruct the pinned CPU runtime and run ADR-0083's governed replicas.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="${1:-all}"
UV="${UV:-uv}"
JAVA="${JAVA:-java}"
BASE_PORT="${RL_PORT:-47810}"
LOCK="$ROOT/python/requirements-rl-linux-py312.lock"
JAR="$ROOT/rl-server/build/libs/rl-server.jar"
CONFIG="$ROOT/configs/training/m9-ippo-v5-success-imitation.json"
PREFLIGHT="${M9_PREFLIGHT:-$ROOT/runs/m9-ippo-v5-preflight.json}"
PRIMARY_OUT="${M9_PRIMARY_OUT:-$ROOT/runs/m9-ippo-v5-success-imitation-a}"
REPLICA_OUT="${M9_REPLICA_OUT:-$ROOT/runs/m9-ippo-v5-success-imitation-b}"
COMPARISON_OUT="${M9_COMPARISON_OUT:-$ROOT/runs/m9-ippo-v5-success-imitation-replicas.json}"
PRIMARY_MANIFEST="$PRIMARY_OUT/ippo-v5-success-imitation-run.manifest.json"
REPLICA_MANIFEST="$REPLICA_OUT/ippo-v5-success-imitation-run.manifest.json"

case "$MODE" in
  a|b|compare|all) ;;
  *)
    echo "ERROR: mode must be a, b, compare, or all" >&2
    exit 1
    ;;
esac
if [[ "$(uname -s)" != "Linux" ]]; then
  echo "ERROR: M9 IPPO v5 training requires Linux/WSL2" >&2
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

VENV="$(mktemp -d "${TMPDIR:-/tmp}/mindustry-m9-ippo-v5.XXXXXX")"
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
    --config "$CONFIG" \
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

authorize_replica_b(){
  "$VENV/bin/python" - "$PRIMARY_MANIFEST" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
manifest = json.loads(path.read_text(encoding="utf-8"))
if manifest.get("construction_passed") is not True:
    raise SystemExit("ERROR: replica B requires passing replica A construction")
PY
}

compare_replicas(){
  "$VENV/bin/python" -m mindustry_agents.training.ippo_train \
    --compare-runs "$PRIMARY_MANIFEST" "$REPLICA_MANIFEST" \
    --comparison-output "$COMPARISON_OUT"
}

case "$MODE" in
  a)
    run_replica A "$PRIMARY_OUT"
    ;;
  b)
    authorize_replica_b
    run_replica B "$REPLICA_OUT"
    ;;
  compare)
    compare_replicas
    ;;
  all)
    replica_a_status=0
    run_replica A "$PRIMARY_OUT" || replica_a_status=$?
    if [[ "$replica_a_status" -eq 2 ]]; then
      exit 2
    fi
    authorize_replica_b
    replica_b_status=0
    run_replica B "$REPLICA_OUT" || replica_b_status=$?
    compare_replicas
    if [[ "$replica_b_status" -eq 2 ]]; then
      exit 1
    fi
    ;;
esac
