#!/usr/bin/env bash
# Exact Python/Java fallback parity over the real plugin public-candidate trace.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"
DEMO_PUBLIC_POLICY=1 bash scripts/demo-server.sh
EXPECTED="PUBLIC-DEMO-PARITY OK boundaries=338 actions=1014 selections=170 "
EXPECTED+="digest=127bc6f8dc02b276531d17c94ce348d209a7de692bbbcff2ff18284cfc177907"
ACTUAL="$("$PY" -m mindustry_agents.tools.public_demo_parity \
    "$ROOT/runs/demo-server-probe.log")"
printf '%s\n' "$ACTUAL"
if [[ "$ACTUAL" != "$EXPECTED" ]]; then
    echo "public demo golden drift: expected '$EXPECTED'" >&2
    exit 1
fi
