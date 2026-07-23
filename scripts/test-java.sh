#!/usr/bin/env bash
# test-java.sh — Java JUnit tests (agent-core) + compile checks for custom modules.
set -euo pipefail
cd "$(dirname "$0")/.."
ARGS=(agent-core:test rl-server:test agent-plugin:classes --console=plain)
if head -n 1 ./gradlew | grep -q $'\r$'; then
  # A shared Windows checkout with core.autocrlf may expose gradlew to WSL
  # with CRLF. Normalize only the executed text; keep ./gradlew as $0 so its
  # APP_HOME/wrapper resolution remains exact.
  bash -c "$(sed 's/\r$//' ./gradlew)" ./gradlew "${ARGS[@]}"
else
  ./gradlew "${ARGS[@]}"
fi
echo "test-java: OK"
