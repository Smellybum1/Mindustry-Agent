#!/usr/bin/env bash
# Reconstruct and verify the M8 Linux/WSL2 CPU training dependency boundary.
# uv is supplied explicitly or discovered on PATH; all packages go into a
# temporary environment which is deleted on exit.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
UV="${UV:-uv}"
LOCK="$ROOT/python/requirements-rl-linux-py312.lock"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "ERROR: ADR-0011 verification requires Linux/WSL2" >&2
  exit 1
fi
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "ERROR: python not found: $PY" >&2
  exit 1
fi
if ! command -v "$UV" >/dev/null 2>&1; then
  echo "ERROR: uv not found: $UV (M8.2 is pinned to uv 0.11.16)" >&2
  exit 1
fi
if [[ ! -f "$LOCK" ]]; then
  echo "ERROR: missing RL lockfile: $LOCK" >&2
  exit 1
fi

"$PY" - <<'PY'
import sys
if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"ERROR: Python 3.12 required, found {sys.version.split()[0]}")
PY
if [[ "$("$UV" --version)" != "uv 0.11.16"* ]]; then
  echo "ERROR: uv 0.11.16 required, found $("$UV" --version)" >&2
  exit 1
fi

echo "== zero-third-party core =="
PYTHONPATH="$ROOT/python/src:$ROOT/python/tests" "$PY" -S -m unittest -v \
  test_import test_protocol test_env test_supervisor

VENV="$(mktemp -d "${TMPDIR:-/tmp}/mindustry-rl-verify.XXXXXX")"
trap 'rm -rf -- "$VENV"' EXIT
"$UV" venv --python "$PY" --no-project "$VENV"
"$UV" pip sync --python "$VENV/bin/python" "$LOCK"

echo "== pinned Linux CPU RL runtime =="
PYTHONPATH="$ROOT/python/src" "$VENV/bin/python" - <<'PY'
from importlib.metadata import version
import platform

import numpy
import pettingzoo
import torch

expected = {
    "numpy": "2.4.2",
    "pettingzoo": "1.26.1",
    "torch": "2.12.1",
}
actual = {name: version(name).split("+", 1)[0] for name in expected}
if actual != expected:
    raise SystemExit(f"ERROR: dependency versions {actual!r} != {expected!r}")
if torch.version.cuda is not None or torch.cuda.is_available():
    raise SystemExit("ERROR: ADR-0011 lock must install CPU-only PyTorch")

from mindustry_agents import env, evaluation, process, protocol  # noqa: F401

print(f"python={platform.python_version()}")
print(f"platform={platform.platform()}")
print(f"numpy={numpy.__version__}")
print(f"pettingzoo={version('pettingzoo')}")
print(f"torch={torch.__version__} device=cpu")
PY

echo "lock_sha256=$(sha256sum "$LOCK" | awk '{print $1}')"
echo "RL-BOUNDARY OK"
