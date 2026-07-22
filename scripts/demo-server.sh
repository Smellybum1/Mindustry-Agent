#!/usr/bin/env bash
# Real v159.7 dedicated-server + loadable agent-plugin demonstration.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

./gradlew agent-plugin:dist server:dist --console=plain

PLUGIN_JAR="$ROOT/agent-plugin/build/libs/mindustry-coop-agents-plugin.jar"
SERVER_JAR="$ROOT/server/build/libs/server-release.jar"
PLUGIN_ENTRIES="$(jar tf "$PLUGIN_JAR")"
for required in \
    plugin.json \
    mindustry/agentplugin/AgentPlugin.class \
    mindustry/agentplugin/DemoAgentRegistry.class \
    mindustry/agentplugin/DemoAgentController.class \
    mindustry/agentplugin/PublicCandidateDemo.class \
    mindustry/agentplugin/DemoSessionCapture.class \
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
cp "$SERVER_JAR" "$RUNTIME/server.jar"
cp "$PLUGIN_JAR" \
    "$RUNTIME/config/mods/mindustry-coop-agents-plugin.jar"

JAVA_BIN="${JAVA_BIN:-java}"
DEMO_PORT="${DEMO_PORT:-6567}"
# Public candidates are the production default; 0 retains the legacy regression oracle.
case "${DEMO_PUBLIC_POLICY:-1}" in
    1) POLICY_ARGS=(-Dmindustry.agents.demo.public-policy=true) ;;
    0) POLICY_ARGS=(-Dmindustry.agents.demo.public-policy=false) ;;
    *) echo "DEMO_PUBLIC_POLICY must be 0 or 1" >&2; exit 2 ;;
esac

CAPTURE_ARGS=()
CAPTURE_FILE="${DEMO_CAPTURE_PATH:-}"
SCORECARD_FILE=""

check_new_output(){
    local output_file="$1"
    local output_name="$2"
    local output_parent
    output_parent="$(dirname "$output_file")"
    [[ -d "$output_parent" ]] || {
        echo "demo-server: $output_name parent does not exist: $output_parent" >&2
        exit 2
    }
    [[ ! -e "$output_file" ]] || {
        echo "demo-server: refusing to overwrite $output_name: $output_file" >&2
        exit 2
    }
}

validate_and_score_capture(){
    local capture_file="$1"
    local scorecard_file="$2"
    [[ -s "$capture_file" ]] || {
        echo "demo-server: human capture was not written: $capture_file" >&2
        exit 1
    }
    export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"
    source "$ROOT/scripts/python-command.sh"
    "$PY" -m mindustry_agents.tools.human_session \
        --session "$capture_file" \
        --population "$ROOT/configs/partners/human-scripted-v1.json"
    "$PY" -m mindustry_agents.tools.human_scorecard \
        --session "$capture_file" \
        --output "$scorecard_file"
    [[ -s "$scorecard_file" ]] || {
        echo "demo-server: human scorecard was not written: $scorecard_file" >&2
        exit 1
    }
}

if [[ "${DEMO_HUMAN_CAPTURE:-0}" == "1" && -z "$CAPTURE_FILE" ]]; then
    CAPTURE_FILE="$RUNTIME/human-session.jsonl"
fi
if [[ -n "$CAPTURE_FILE" ]]; then
    check_new_output "$CAPTURE_FILE" "capture"
    REPOSITORY_COMMIT="$(git rev-parse --verify HEAD)"
    export PYTHONPATH="$ROOT/python/src${PYTHONPATH:+:$PYTHONPATH}"
    source "$ROOT/scripts/python-command.sh"
    PLUGIN_CONTENT_SHA256="$(
        "$PY" -m mindustry_agents.tools.jar_content_sha256 "$PLUGIN_JAR"
    )"
    SERVER_CONTENT_SHA256="$(
        "$PY" -m mindustry_agents.tools.jar_content_sha256 "$SERVER_JAR"
    )"
    CAPTURE_ARGS=(
        -Dmindustry.agents.demo.capture-path="$CAPTURE_FILE"
        -Dmindustry.agents.demo.repository-commit="$REPOSITORY_COMMIT"
        -Dmindustry.agents.demo.plugin-content-sha256="$PLUGIN_CONTENT_SHA256"
        -Dmindustry.agents.demo.server-content-sha256="$SERVER_CONTENT_SHA256"
    )
fi

if [[ "${DEMO_JOIN:-0}" == "1" ]]; then
    if [[ -n "${DEMO_SCORECARD_PATH:-}" && -z "$CAPTURE_FILE" ]]; then
        echo "demo-server: DEMO_SCORECARD_PATH requires DEMO_CAPTURE_PATH" >&2
        exit 2
    fi
    if [[ -n "$CAPTURE_FILE" ]]; then
        if [[ -n "${DEMO_SCORECARD_PATH:-}" ]]; then
            SCORECARD_FILE="$DEMO_SCORECARD_PATH"
        elif [[ "$CAPTURE_FILE" == *.jsonl ]]; then
            SCORECARD_FILE="${CAPTURE_FILE%.jsonl}.scorecard.unrated.json"
        else
            SCORECARD_FILE="$CAPTURE_FILE.scorecard.unrated.json"
        fi
        [[ "$SCORECARD_FILE" != "$CAPTURE_FILE" ]] || {
            echo "demo-server: capture and scorecard paths must differ" >&2
            exit 2
        }
        check_new_output "$SCORECARD_FILE" "scorecard"
    fi
fi

if [[ "${DEMO_HUMAN_CONTROL:-0}" == "1" || "${DEMO_HUMAN_CAPTURE:-0}" == "1" ]]; then
    LOG="$ROOT/runs/demo-server-human-control.log"
    echo "demo-server: deterministic queued human-control probe (no network port)"
    cd "$RUNTIME"
    set +e
    "$JAVA_BIN" "${POLICY_ARGS[@]}" "${CAPTURE_ARGS[@]}" \
        -Dmindustry.agents.demo.mode=human -jar server.jar 2>&1 | tee "$LOG"
    server_status=${PIPESTATUS[0]}
    set -e
    cd "$ROOT"
    [[ $server_status -eq 0 ]] || exit "$server_status"
    grep -F "AGENT-DEMO HUMAN CONTROL OK" "$LOG" >/dev/null
    for command in GOAL CANCEL ASSIGN RELEASE AUTONOMY QUIET; do
        grep -F "\"command\":\"$command\"" "$LOG" >/dev/null
    done
    if grep -F 'AGENT-DEMO HUMAN CONTROL {' "$LOG" | grep -F '"accepted":false' >/dev/null; then
        echo "demo-server: human control command was rejected" >&2
        exit 1
    fi
    grep -F '"task_id":"human:goal:1"' "$LOG" >/dev/null
    grep -F 'low=true high=true' "$LOG" | grep -F 'yields=1' >/dev/null
    yield_notices=$(grep -F '"reason_code":"yield_to_human"' "$LOG" \
        | grep -F '"announce":true' | wc -l | tr -d ' ')
    if [[ "$yield_notices" != "1" ]]; then
        echo "demo-server: expected exactly one human-yield notice, got $yield_notices" >&2
        exit 1
    fi
    grep -F 'AGENT-DEMO CHAT SUPPRESSED' "$LOG" >/dev/null
    if grep -F "Opened a server on port" "$LOG" >/dev/null; then
        echo "demo-server: human probe unexpectedly opened a network port" >&2
        exit 1
    fi
    if [[ "${DEMO_HUMAN_CAPTURE:-0}" == "1" ]]; then
        SCORECARD_FILE="$RUNTIME/human-scorecard.json"
        check_new_output "$SCORECARD_FILE" "scorecard"
        validate_and_score_capture "$CAPTURE_FILE" "$SCORECARD_FILE"
    fi
    echo "demo-server: HUMAN CONTROL OK"
    exit 0
fi

if [[ "${DEMO_SURVIVAL:-0}" == "1" ]]; then
    LOG="$ROOT/runs/demo-server-survival.log"
    echo "demo-server: real-time three-wave survival probe (no network port)"
    cd "$RUNTIME"
    set +e
    "$JAVA_BIN" "${POLICY_ARGS[@]}" "${CAPTURE_ARGS[@]}" \
        -Dmindustry.agents.demo.mode=survival -jar server.jar 2>&1 | tee "$LOG"
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
    set +e
    "$JAVA_BIN" "${POLICY_ARGS[@]}" "${CAPTURE_ARGS[@]}" \
        -Dmindustry.agents.demo.mode=join \
        -Dmindustry.agents.demo.port="$DEMO_PORT" \
        -jar server.jar
    server_status=$?
    set -e
    cd "$ROOT"
    [[ $server_status -eq 0 ]] || exit "$server_status"
    if [[ -n "$CAPTURE_FILE" ]]; then
        validate_and_score_capture "$CAPTURE_FILE" "$SCORECARD_FILE"
        echo "demo-server: validated capture: $CAPTURE_FILE"
        echo "demo-server: unrated scorecard: $SCORECARD_FILE"
    fi
    exit 0
fi

LOG="$ROOT/runs/demo-server-probe.log"
echo "demo-server: isolated acceptance probe (no network port will be opened)"
cd "$RUNTIME"
set +e
"$JAVA_BIN" "${POLICY_ARGS[@]}" "${CAPTURE_ARGS[@]}" \
    -Dmindustry.agents.demo.mode=probe -jar server.jar 2>&1 | tee "$LOG"
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
