#!/usr/bin/env bash
# Deterministic no-port M10.3 capture, replay, summary, and profile-catalog gate.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DEMO_HUMAN_CAPTURE=1 exec bash scripts/demo-server.sh
