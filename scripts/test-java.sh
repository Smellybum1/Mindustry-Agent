#!/usr/bin/env bash
# test-java.sh — Java JUnit tests (agent-core) + compile checks for custom modules.
set -euo pipefail
cd "$(dirname "$0")/.."
./gradlew agent-core:test rl-server:classes agent-plugin:classes --console=plain
echo "test-java: OK"
