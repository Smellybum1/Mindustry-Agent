#!/usr/bin/env bash
# Real v159.7 dedicated-server + loadable agent-plugin demonstration.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

./gradlew agent-plugin:dist server:dist --console=plain

PLUGIN_JAR="$ROOT/agent-plugin/build/libs/mindustry-coop-agents-plugin.jar"
PLUGIN_ENTRIES="$(jar tf "$PLUGIN_JAR")"
for required in \
    plugin.json \
    mindustry/agentplugin/AgentPlugin.class \
    mindustry/agentplugin/DemoAgentRegistry.class \
    mindustry/agentplugin/DemoAgentController.class \
    mindustry/agentplugin/PublicCandidateDemo.class \
    mindustry/agentplugin/FixedProbeGraphics.class \
    agentcore/board/TaskBoard.class \
    agentcore/skill/ExecuteSchematic.class \
    scenarios/bootstrap-defense-v0/scenario.json; do
    grep -Fx "$required" <<<"$PLUGIN_ENTRIES" >/dev/null || {
        echo "demo-server: plugin jar missing $required" >&2
        exit 1
    }
done
if grep -E '^mindustry/(gen|content|core)/' <<<"$PLUGIN_ENTRIES" >/dev/null; then
    echo "demo-server: plugin jar incorrectly bundles upstream engine classes" >&2
    exit 1
fi

mkdir -p "$ROOT/runs"
RUNTIME="$(mktemp -d "$ROOT/runs/demo-server.XXXXXX")"
cleanup(){
    case "$RUNTIME" in
        "$ROOT"/runs/demo-server.*) rm -rf -- "$RUNTIME" ;;
        *) echo "refusing to remove unexpected demo runtime: $RUNTIME" >&2 ;;
    esac
}
trap cleanup EXIT

mkdir -p "$RUNTIME/config/mods"
cp "$ROOT/server/build/libs/server-release.jar" "$RUNTIME/server.jar"
cp "$PLUGIN_JAR" \
    "$RUNTIME/config/mods/mindustry-coop-agents-plugin.jar"

JAVA_BIN="${JAVA_BIN:-java}"
DEMO_PORT="${DEMO_PORT:-6567}"
POLICY_ARGS=()
if [[ "${DEMO_PUBLIC_POLICY:-0}" == "1" ]]; then
    POLICY_ARGS=(-Dmindustry.agents.demo.public-policy=true)
fi

if [[ "${DEMO_SURVIVAL:-0}" == "1" ]]; then
    LOG="$ROOT/runs/demo-server-survival.log"
    echo "demo-server: real-time three-wave survival probe (no network port)"
    cd "$RUNTIME"
    set +e
    "$JAVA_BIN" "${POLICY_ARGS[@]}" -Dmindustry.agents.demo.mode=survival -jar server.jar 2>&1 | tee "$LOG"
    server_status=${PIPESTATUS[0]}
    set -e
    cd "$ROOT"
    [[ $server_status -eq 0 ]] || exit "$server_status"
    grep -F "AGENT-DEMO SURVIVAL OK" "$LOG" >/dev/null
    grep -F "AGENT-DEMO RESERVE MINING" "$LOG" >/dev/null
    grep -F "AGENT-DEMO MAINTENANCE COMPLETE" "$LOG" | grep -F "wave=1" >/dev/null
    grep -F "AGENT-DEMO MAINTENANCE COMPLETE" "$LOG" | grep -F "wave=2" >/dev/null
    grep -F "AGENT-DEMO EXPANSION COMPLETE" "$LOG" | grep -F "wave=1 turrets=8" >/dev/null
    grep -F "AGENT-DEMO EXPANSION COMPLETE" "$LOG" | grep -F "wave=2 turrets=10" >/dev/null
    grep -F "AGENT-DEMO WAVE CLEAR" "$LOG" | grep -F "wave=1" >/dev/null
    grep -F "AGENT-DEMO WAVE CLEAR" "$LOG" | grep -F "wave=2" >/dev/null
    grep -F "AGENT-DEMO WAVE CLEAR" "$LOG" | grep -F "wave=3" >/dev/null
    if grep -F "AGENT-DEMO SURVIVAL FAIL" "$LOG" >/dev/null; then
        echo "demo-server: expert did not survive" >&2
        exit 1
    fi
    if grep -F "AGENT-DEMO EXPANSION INCOMPLETE" "$LOG" >/dev/null; then
        echo "demo-server: defense expansion incomplete" >&2
        exit 1
    fi
    echo "demo-server: SURVIVAL OK"
    exit 0
fi

if [[ "${DEMO_JOIN:-0}" == "1" ]]; then
    python - "$DEMO_PORT" <<'PY'
import socket
import sys

port = int(sys.argv[1])
if not 1 <= port <= 65535:
    raise SystemExit(f"invalid DEMO_PORT: {port}")
for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
    sock = socket.socket(socket.AF_INET, kind)
    try:
        sock.bind(("0.0.0.0", port))
    except OSError as exc:
        raise SystemExit(f"DEMO_PORT {port} is unavailable: {exc}") from exc
    finally:
        sock.close()
PY
    echo "demo-server: explicit join mode; opening private game port $DEMO_PORT"
    echo "demo-server: connect a stock v159.7 client to localhost:$DEMO_PORT"
    cd "$RUNTIME"
    "$JAVA_BIN" "${POLICY_ARGS[@]}" \
        -Dmindustry.agents.demo.mode=join \
        -Dmindustry.agents.demo.port="$DEMO_PORT" \
        -jar server.jar
    exit $?
fi

LOG="$ROOT/runs/demo-server-probe.log"
echo "demo-server: isolated acceptance probe (no network port will be opened)"
cd "$RUNTIME"
set +e
"$JAVA_BIN" "${POLICY_ARGS[@]}" -Dmindustry.agents.demo.mode=probe -jar server.jar 2>&1 | tee "$LOG"
server_status=${PIPESTATUS[0]}
set -e
cd "$ROOT"

if [[ $server_status -ne 0 ]]; then
    echo "demo-server: server exited $server_status" >&2
    exit "$server_status"
fi
grep -F "AGENT-DEMO PARITY OK" "$LOG" >/dev/null
grep -F "AGENT-DEMO EXPERT READY" "$LOG" >/dev/null
grep -F "AGENT-DEMO RESERVE MINING" "$LOG" >/dev/null
grep -F "AGENT-DEMO CONTROLS OK" "$LOG" >/dev/null
grep -F "AGENT-DEMO PROBE OK" "$LOG" >/dev/null
if grep -F "Opened a server on port" "$LOG" >/dev/null; then
    echo "demo-server: probe unexpectedly opened a network port" >&2
    exit 1
fi
echo "demo-server: OK (real server/plugin, build order parity, mining/building/supply, no port)"
