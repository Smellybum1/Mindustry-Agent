#!/usr/bin/env bash
# Exact Python/Java fallback parity over the real plugin public-candidate trace.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source "$(dirname "${BASH_SOURCE[0]}")/python-command.sh"

export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"
bash scripts/demo-server.sh
EXPECTED="PUBLIC-DEMO-PARITY OK boundaries=390 actions=1170 selections=225 "
EXPECTED+="rebalances=2 combat_waits=7 "
EXPECTED+="digest=aaf2e734ea384fe4b537cbdf3bd5342fb5e954f3432a91470ebce311fa503714"
ACTUAL="$("$PY" -m mindustry_agents.tools.public_demo_parity \
    "$ROOT/runs/demo-server-probe.log")"
printf '%s\n' "$ACTUAL"
if [[ "$ACTUAL" != "$EXPECTED" ]]; then
    echo "public demo golden drift: expected '$EXPECTED'" >&2
    exit 1
fi
