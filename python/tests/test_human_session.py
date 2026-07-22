from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from mindustry_agents.telemetry.human_session import (
    PROFILE_IDS,
    load_partner_population,
    load_session,
    partner_style_statistics,
    replay_controls,
    scripted_partner_decision,
    session_summary,
)


def _line(value: dict) -> bytes:
    return (json.dumps(value, separators=(",", ":")) + "\n").encode()


def _capture(path: Path) -> None:
    records = [
        {
            "capture_schema_version": 1,
            "record_type": "session_start",
            "tick": 0,
            "engine_tag": "v159.7",
            "engine_commit": "c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c",
            "arc_version": "208a754044",
            "protocol_version": 1,
            "scenario_id": "bootstrap-defense-v0",
            "scenario_version": 1,
            "policy": "public-greedy-candidates-v1",
            "python_lockfile": "not_applicable_demo_runtime",
            "training_config": "not_applicable_demo_runtime",
        },
        {
            "capture_schema_version": 1,
            "record_type": "control",
            "tick": 10,
            "control": {
                "sequence": 1,
                "queued_tick": 9,
                "tick": 10,
                "accepted": True,
                "reason": "goal_added",
                "revision": 1,
                "goal_id": "human:goal:1",
                "agent_index": -1,
                "canonical_command": {
                    "type": "GOAL",
                    "task_type": "BUILD_LINE",
                    "region_id": "line",
                    "author_id": "probe",
                },
            },
        },
        {
            "capture_schema_version": 1,
            "record_type": "coordination",
            "tick": 11,
            "announcement_status": "rendered",
            "event": {"tick": 11, "reason_code": "yield_to_human"},
        },
    ]
    raw = b"".join(_line(record) for record in records)
    end = {
        "capture_schema_version": 1,
        "record_type": "session_end",
        "tick": 12,
        "reason": "test",
        "records": len(records),
        "content_sha256": hashlib.sha256(raw).hexdigest(),
    }
    path.write_bytes(raw + _line(end))


def test_load_replay_and_style_summary():
    root = Path(__file__).parents[2]
    with TemporaryDirectory(dir=root / "runs") as directory:
        path = Path(directory) / "session.jsonl"
        _capture(path)
        records = load_session(path)
        replay = replay_controls(records)
        style = partner_style_statistics(records)

        assert replay["revision"] == 1
        assert replay["active_goals"]["human:goal:1"]["task_type"] == "BUILD_LINE"
        assert style["commands_total"] == 1
        assert style["role_preferences"] == {"BUILD_LINE": 1}
        assert style["yield_to_human_events"] == 1
        assert session_summary(records)["session_content_sha256"] == records[-1][
            "content_sha256"
        ]


def test_digest_and_control_tick_fail_closed():
    root = Path(__file__).parents[2]
    with TemporaryDirectory(dir=root / "runs") as directory:
        path = Path(directory) / "session.jsonl"
        _capture(path)
        raw = path.read_bytes()
        path.write_bytes(raw.replace(b'"queued_tick":9', b'"queued_tick":99'))
        with pytest.raises(ValueError, match="content digest"):
            load_session(path)


def test_partner_population_contract():
    root = Path(__file__).parents[2]
    population = load_partner_population(
        root / "configs" / "partners" / "human-scripted-v1.json"
    )
    assert tuple(profile["id"] for profile in population["profiles"]) == PROFILE_IDS
    assert population["status"] == "staged_for_m9_after_promotion_authorization"
    decision = scripted_partner_decision(
        population, "help-requester", 150, blocked_ticks=90, plan_age_ticks=720
    )
    assert decision == scripted_partner_decision(
        population, "help-requester", 150, blocked_ticks=90, plan_age_ticks=720
    )
    assert decision["request_help"] is True
    assert decision["change_plan"] is True
