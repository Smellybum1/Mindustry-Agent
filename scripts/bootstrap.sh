#!/usr/bin/env bash
# bootstrap.sh — verify and print the project toolchain.
# Works today in Git Bash (Windows) and Linux/WSL2. Non-interactive.
# Does NOT install anything or run Gradle. Exits nonzero if a hard requirement
# is missing.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail=0
echo "== mindustry-coop-agents bootstrap =="
echo "repo: $ROOT"

# --- Engine pin ----------------------------------------------------------------
if [[ -f ENGINE_VERSION ]]; then
  echo "-- ENGINE_VERSION --"
  cat ENGINE_VERSION
else
  echo "MISSING: ENGINE_VERSION"; fail=1
fi

# --- Java (need 17+; project pins JDK 21 Temurin, compiles --release 17) --------
echo "-- Java --"
if command -v java >/dev/null 2>&1; then
  java -version
  jver="$(java -version 2>&1 | sed -nE 's/.*version "([0-9]+).*/\1/p' | head -1)"
  if [[ ! "$jver" =~ ^[0-9]+$ ]]; then
    echo "ERROR: unable to parse Java major version"; fail=1
  elif (( jver < 17 )); then
    echo "ERROR: JDK 17+ required (found $jver)"; fail=1
  fi
else
  echo "ERROR: java not found on PATH"; fail=1
fi

# --- Python (need >= 3.11) -----------------------------------------------------
echo "-- Python --"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"
if command -v "$PY" >/dev/null 2>&1; then
  "$PY" --version
  "$PY" - <<'EOF'
import sys
maj, min = sys.version_info[:2]
if (maj, min) < (3, 11):
    print(f"ERROR: Python >= 3.11 required (found {maj}.{min})")
    sys.exit(1)
EOF
else
  echo "ERROR: python not found on PATH"; fail=1
fi

# --- Git -----------------------------------------------------------------------
echo "-- Git --"
if command -v git >/dev/null 2>&1; then
  git --version
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
  head="$(git rev-parse --short HEAD 2>/dev/null || echo '?')"
  echo "branch=$branch head=$head"
else
  echo "ERROR: git not found on PATH"; fail=1
fi

# --- Gradle wrapper presence (do not invoke) -----------------------------------
echo "-- Gradle wrapper --"
if [[ -x ./gradlew || -f ./gradlew ]]; then
  echo "present: ./gradlew (not invoked by bootstrap)"
else
  echo "WARN: ./gradlew not found"
fi

# --- pytest availability (optional) --------------------------------------------
echo "-- pytest (optional) --"
if "$PY" -m pytest --version >/dev/null 2>&1; then
  "$PY" -m pytest --version 2>&1 | head -1
else
  echo "pytest not installed; python tests fall back to 'python -m unittest'"
fi

echo "================================"
if [[ "$fail" -ne 0 ]]; then
  echo "bootstrap: FAILED (see errors above)"
  exit 1
fi
echo "bootstrap: OK"
