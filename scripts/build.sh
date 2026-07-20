#!/usr/bin/env bash
# build.sh — build Java modules + Python package.
#
# NOTE: Gradle builds are intentionally NOT run automatically here yet because a
# background engine build may be active and the Gradle daemon/cache must not be
# contended (see AGENTS.md §1). This target currently only builds/validates the
# Python package; the Java build is wired in roadmap M0/M1.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python}"

echo "== Python package sanity =="
export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"
"$PY" -c "import mindustry_agents, mindustry_agents.protocol; print('mindustry_agents', mindustry_agents.__version__)"

echo
echo "Java build is not wired into this target yet."
echo "To build the Java modules manually (only when no background Gradle build is"
echo "running): ./gradlew rl-server:dist agent-core:build agent-plugin:build"
echo "See docs/ROADMAP.md#milestone-0"
