"""Validation, deterministic control replay, and style summaries for M10.3."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from mindustry_agents import ARC_VERSION, ENGINE_COMMIT, ENGINE_TAG, PROTOCOL_VERSION

CAPTURE_SCHEMA_VERSION = 3
SUPPORTED_CAPTURE_SCHEMA_VERSIONS = (1, 2, 3)
CAPTURE_PROVENANCE_FIELDS = (
    "repository_commit",
    "agent_plugin_sha256",
    "server_sha256",
    "agent_plugin_content_sha256",
    "server_content_sha256",
)
CAPTURE_PROVENANCE_FIELDS_BY_VERSION = {
    1: (),
    2: ("repository_commit", "agent_plugin_sha256", "server_sha256"),
    3: (
        "repository_commit",
        "agent_plugin_content_sha256",
        "server_content_sha256",
    ),
}
POPULATION_SCHEMA = "scripted_human_partner_population_v1"
PROFILE_IDS = (
    "fast-expert",
    "slow-beginner",
    "cautious",
    "plan-changer",
    "help-requester",
)
RECORD_TYPES = {
    "session_start",
    "trajectory",
    "control",
    "coordination",
    "human_presence",
    "session_end",
}


def load_session(path: Path) -> list[dict[str, Any]]:
    """Load a complete capture, validating ordering, pins, and content digest."""

    raw_lines = path.read_bytes().splitlines(keepends=True)
    if len(raw_lines) < 2:
        raise ValueError("human session must contain start and end records")
    records: list[dict[str, Any]] = []
    for line_number, raw in enumerate(raw_lines, 1):
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid JSONL at line {line_number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"human session line {line_number} is not an object")
        schema_version = value.get("capture_schema_version")
        if schema_version not in SUPPORTED_CAPTURE_SCHEMA_VERSIONS:
            raise ValueError(f"unsupported capture schema at line {line_number}")
        if records and schema_version != records[0]["capture_schema_version"]:
            raise ValueError(f"mixed capture schema at line {line_number}")
        if value.get("record_type") not in RECORD_TYPES:
            raise ValueError(f"unsupported record type at line {line_number}")
        records.append(value)

    if records[0].get("record_type") != "session_start":
        raise ValueError("human session must start with session_start")
    if records[-1].get("record_type") != "session_end":
        raise ValueError("human session must end with session_end")
    if any(record.get("record_type") == "session_end" for record in records[:-1]):
        raise ValueError("human session contains an early session_end")

    start = records[0]
    expected_pins = {
        "engine_tag": ENGINE_TAG,
        "engine_commit": ENGINE_COMMIT,
        "arc_version": ARC_VERSION,
        "protocol_version": PROTOCOL_VERSION,
    }
    for field, expected in expected_pins.items():
        if start.get(field) != expected:
            raise ValueError(f"human session {field} mismatch")
    for field in (
        "scenario_id",
        "scenario_version",
        "policy",
        "python_lockfile",
        "training_config",
    ):
        if field not in start:
            raise ValueError(f"human session start missing {field}")
    provenance_fields = CAPTURE_PROVENANCE_FIELDS_BY_VERSION[
        start["capture_schema_version"]
    ]
    if provenance_fields:
        for field in provenance_fields:
            value = start.get(field)
            length = 40 if field == "repository_commit" else 64
            if (
                not isinstance(value, str)
                or len(value) != length
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise ValueError(f"human session {field} is not lowercase hex")

    ticks = [int(record.get("tick", -1)) for record in records]
    if any(tick < 0 for tick in ticks):
        raise ValueError("human session ticks must be non-negative")
    if ticks != sorted(ticks):
        raise ValueError("human session records are not tick ordered")

    end = records[-1]
    if end.get("records") != len(records) - 1:
        raise ValueError("human session record count mismatch")
    observed_digest = hashlib.sha256(b"".join(raw_lines[:-1])).hexdigest()
    if end.get("content_sha256") != observed_digest:
        raise ValueError("human session content digest mismatch")

    replay_controls(records)
    return records


def replay_controls(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Replay accepted control events in recorded simulation-tick order."""

    goals: dict[str, dict[str, str]] = {}
    assignments: dict[int, str] = {}
    autonomy = "NORMAL"
    quiet = False
    revision = 0
    schedule: list[dict[str, Any]] = []

    for record in records:
        if record.get("record_type") != "control":
            continue
        control = record.get("control")
        if not isinstance(control, dict):
            raise ValueError("control record missing control object")
        command = control.get("canonical_command")
        if not isinstance(command, dict):
            raise ValueError("control record missing canonical command")
        queued_tick = int(control.get("queued_tick", -1))
        applied_tick = int(control.get("tick", -1))
        if queued_tick < 0 or queued_tick > applied_tick:
            raise ValueError("control queued/applied ticks are invalid")
        if int(record.get("tick", -1)) != applied_tick:
            raise ValueError("control envelope tick mismatch")

        accepted = bool(control.get("accepted", False))
        event_revision = int(control.get("revision", -1))
        if accepted:
            revision += 1
            if event_revision != revision:
                raise ValueError("accepted control revision is not contiguous")
            kind = str(command.get("type", ""))
            goal_id = str(control.get("goal_id", ""))
            agent_index = int(control.get("agent_index", -1))
            if kind == "GOAL":
                goals[goal_id] = {
                    "task_type": str(command.get("task_type", "")),
                    "region_id": str(command.get("region_id", "")),
                }
            elif kind == "CANCEL":
                goals.pop(goal_id, None)
                assignments = {
                    agent: goal
                    for agent, goal in assignments.items()
                    if goal != goal_id
                }
            elif kind == "ASSIGN":
                assignments[agent_index] = goal_id
            elif kind == "RELEASE":
                assignments.pop(agent_index, None)
            elif kind == "AUTONOMY":
                autonomy = str(command.get("autonomy", ""))
            elif kind == "QUIET":
                quiet = bool(command.get("quiet", False))
            else:
                raise ValueError(f"unknown canonical command type: {kind}")
        elif event_revision != revision:
            raise ValueError("rejected control changed the revision")

        schedule.append(
            {
                "sequence": int(control.get("sequence", -1)),
                "queued_tick": queued_tick,
                "applied_tick": applied_tick,
                "accepted": accepted,
                "reason": str(control.get("reason", "")),
                "command": command,
            }
        )

    rendered = json.dumps(
        schedule, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return {
        "revision": revision,
        "active_goals": goals,
        "assignments": {str(key): value for key, value in sorted(assignments.items())},
        "autonomy": autonomy,
        "quiet": quiet,
        "control_schedule_sha256": hashlib.sha256(rendered).hexdigest(),
    }


def partner_style_statistics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive pace, role preference, and plan-change statistics from structure."""

    controls = [
        record["control"]
        for record in records
        if record.get("record_type") == "control"
    ]
    accepted = [control for control in controls if control.get("accepted", False)]
    ticks = [int(control["tick"]) for control in accepted]
    intervals = [later - earlier for earlier, later in zip(ticks, ticks[1:])]
    command_types = Counter(
        str(control["canonical_command"]["type"]) for control in accepted
    )
    role_preferences = Counter(
        str(control["canonical_command"]["task_type"])
        for control in accepted
        if control["canonical_command"]["type"] == "GOAL"
    )
    presence_changes = sum(
        len(record.get("added", [])) + len(record.get("removed", []))
        for record in records
        if record.get("record_type") == "human_presence"
    )
    announcement_status = Counter(
        str(record.get("announcement_status", ""))
        for record in records
        if record.get("record_type") == "coordination"
    )
    yields = sum(
        1
        for record in records
        if record.get("record_type") == "coordination"
        and record.get("event", {}).get("reason_code") == "yield_to_human"
    )
    duration = int(records[-1]["tick"]) - int(records[0]["tick"])
    return {
        "duration_ticks": duration,
        "trajectory_boundaries": sum(
            record.get("record_type") == "trajectory" for record in records
        ),
        "commands_total": len(controls),
        "commands_accepted": len(accepted),
        "commands_per_3600_ticks": (
            len(accepted) * 3600.0 / duration if duration > 0 else 0.0
        ),
        "mean_command_interval_ticks": (
            sum(intervals) / len(intervals) if intervals else None
        ),
        "command_types": dict(sorted(command_types.items())),
        "role_preferences": dict(sorted(role_preferences.items())),
        "plan_changes": command_types["CANCEL"] + command_types["RELEASE"],
        "presence_changes": presence_changes,
        "yield_to_human_events": yields,
        "announcement_status": dict(sorted(announcement_status.items())),
    }


def load_partner_population(path: Path) -> dict[str, Any]:
    """Validate the staged, deterministic M9 human-partner profile catalog."""

    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != POPULATION_SCHEMA or value.get("version") != 1:
        raise ValueError("unsupported human-partner population schema")
    profiles = value.get("profiles")
    if not isinstance(profiles, list):
        raise ValueError("human-partner profiles must be a list")
    ids = tuple(profile.get("id") for profile in profiles if isinstance(profile, dict))
    if ids != PROFILE_IDS:
        raise ValueError("human-partner profile ids/order mismatch")
    for profile in profiles:
        if int(profile.get("decision_interval_ticks", 0)) <= 0:
            raise ValueError(f"invalid decision interval for {profile.get('id')}")
        if not profile.get("role_preference"):
            raise ValueError(f"missing role preference for {profile.get('id')}")
        if profile.get("autonomy") not in {"LOW", "NORMAL", "HIGH"}:
            raise ValueError(f"invalid autonomy for {profile.get('id')}")
    return value


def scripted_partner_decision(
    population: dict[str, Any],
    profile_id: str,
    tick: int,
    *,
    blocked_ticks: int = 0,
    plan_age_ticks: int = 0,
) -> dict[str, Any]:
    """Produce one deterministic, engine-neutral decision from a staged profile."""

    profiles = {profile["id"]: profile for profile in population["profiles"]}
    if profile_id not in profiles:
        raise ValueError(f"unknown human-partner profile: {profile_id}")
    if tick < 0 or blocked_ticks < 0 or plan_age_ticks < 0:
        raise ValueError("partner decision ticks must be non-negative")
    profile = profiles[profile_id]
    interval = int(profile["decision_interval_ticks"])
    roles = list(profile["role_preference"])
    change_interval = int(profile["plan_change_interval_ticks"])
    decision_index = tick // interval
    role_index = (tick // change_interval) % len(roles)
    return {
        "profile_id": profile_id,
        "tick": tick,
        "decision_due": tick % interval == 0,
        "decision_index": decision_index,
        "preferred_task_type": roles[role_index],
        "change_plan": plan_age_ticks >= change_interval,
        "request_help": blocked_ticks
        >= int(profile["help_request_after_blocked_ticks"]),
        "autonomy": profile["autonomy"],
    }


def session_summary(
    records: list[dict[str, Any]], population: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Return the deterministic local summary used by the capture gate."""

    result = {
        "capture_schema_version": records[0]["capture_schema_version"],
        "session_content_sha256": records[-1]["content_sha256"],
        "style": partner_style_statistics(records),
        "control_replay": replay_controls(records),
    }
    if population is not None:
        result["scripted_partner_profiles"] = [
            profile["id"] for profile in population["profiles"]
        ]
        result["population_status"] = population.get("status", "")
    return result
