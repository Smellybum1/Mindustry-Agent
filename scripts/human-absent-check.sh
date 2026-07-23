#!/usr/bin/env bash
# Deterministic no-port M10 human-only condition capture gate.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DEMO_AGENTS=0 DEMO_ABSENT_CHECK=1 exec bash scripts/demo-server.sh
