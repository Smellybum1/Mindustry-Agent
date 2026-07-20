#!/usr/bin/env bash
# M7.2 decision-sequence parity over one recorded scenario snapshot trace.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

./gradlew agent-core:classes rl-server:dist --console=plain
java -cp agent-core/build/classes/java/main agentcore.coordination.DecisionParityProbe

export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"
FIXED_OUTPUT="$(python -m mindustry_agents.tools.shared_policy_check)"
printf '%s\n' "$FIXED_OUTPUT"

bash scripts/demo-server.sh
DEMO_LINE="$(grep -F 'AGENT-DEMO DECISION DIGEST' runs/demo-server-probe.log | tail -n 1)"
printf '%s\n' "$DEMO_LINE"

FIXED_DIGEST="$(sed -n 's/.*digest=\([^ ]*\).*/\1/p' <<<"$FIXED_OUTPUT")"
DEMO_DIGEST="$(sed -n 's/.*digest=\([^ ]*\).*/\1/p' <<<"$DEMO_LINE")"
FIXED_COUNT="$(sed -n 's/.*selections=\([0-9]*\).*/\1/p' <<<"$FIXED_OUTPUT")"
DEMO_COUNT="$(sed -n 's/.*selections=\([0-9]*\).*/\1/p' <<<"$DEMO_LINE")"

if [[ -z "$FIXED_DIGEST" || "$FIXED_DIGEST" != "$DEMO_DIGEST" || "$FIXED_COUNT" != "$DEMO_COUNT" ]]; then
    echo "coordination parity mismatch: fixed=$FIXED_DIGEST/$FIXED_COUNT demo=$DEMO_DIGEST/$DEMO_COUNT" >&2
    exit 1
fi
echo "ADAPTER DECISION PARITY OK digest=$FIXED_DIGEST selections=$FIXED_COUNT"
