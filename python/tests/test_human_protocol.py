from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from mindustry_agents.evaluation.human_protocol import (
    CONDITIONS,
    build_block_rating,
    build_human_protocol,
    human_protocol_report,
    load_human_protocol,
    validate_assigned_session,
    write_human_protocol,
)
from mindustry_agents.evaluation.human_scorecard import build_human_rating
from mindustry_agents.tools import human_protocol as human_protocol_tool


def _reference() -> list[dict]:
    return [
        {
            "capture_schema_version": 4,
            "record_type": "session_start",
            "tick": 0,
            "engine_tag": "v159.7",
            "engine_commit": "c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c",
            "arc_version": "208a754044",
            "protocol_version": 1,
            "scenario_id": "bootstrap-defense-v0",
            "scenario_version": 1,
            "policy": "public-greedy-candidates-v1",
            "agent_condition": "present",
            "repository_commit": "1" * 40,
            "agent_plugin_content_sha256": "2" * 64,
            "server_content_sha256": "3" * 64,
        },
        {"record_type": "session_end", "tick": 1, "content_sha256": "0" * 64},
    ]


def _control(tick: int, goal_id: str, task_type: str) -> dict:
    return {
        "record_type": "control",
        "tick": tick,
        "control": {
            "tick": tick,
            "accepted": True,
            "goal_id": goal_id,
            "canonical_command": {
                "type": "GOAL",
                "task_type": task_type,
                "region_id": "test",
                "author_id": "player:test",
            },
        },
    }


def _session(
    protocol: dict,
    block_index: int,
    condition: str,
    digest_character: str,
    *,
    slower: bool = False,
) -> list[dict]:
    block = protocol["blocks"][block_index]
    condition_identity = protocol["conditions"][condition]
    start = {
        "capture_schema_version": 4,
        "record_type": "session_start",
        "tick": 0,
        **protocol["runtime_identity"],
        "policy": condition_identity["policy"],
        "agent_condition": condition_identity["agent_condition"],
        "experiment_id": protocol["experiment_id"],
        "experiment_block": block["block_id"],
        "experiment_condition": condition,
        "experiment_order": block["condition_order"].index(condition) + 1,
        "trial_seed": block["trial_seed"],
    }
    records = [start, {"record_type": "trajectory", "tick": 10}]
    if condition != "absent":
        yield_tick = 13 if slower else 11
        help_tick = 26 if slower else 22
        records.extend(
            [
                _control(10, "human:goal:1", "BUILD_LINE"),
                {
                    "record_type": "human_presence",
                    "tick": 10,
                    "added": [{"id": "human:presence:1"}],
                    "removed": [],
                },
                {
                    "record_type": "coordination",
                    "tick": yield_tick,
                    "announcement_status": "rendered",
                    "event": {
                        "tick": yield_tick,
                        "task_id": "agent-task",
                        "act": "ABANDON",
                        "reason_code": "yield_to_human",
                    },
                },
                {
                    "record_type": "coordination",
                    "tick": 15,
                    "announcement_status": "rendered",
                    "event": {
                        "tick": 15,
                        "task_id": "human:goal:1",
                        "act": "COMPLETE",
                        "reason_code": "goal_complete",
                    },
                },
                {"record_type": "trajectory", "tick": 20},
                _control(20, "human:goal:2", "REQUEST_HELP"),
                {
                    "record_type": "coordination",
                    "tick": help_tick,
                    "announcement_status": "rendered",
                    "event": {
                        "tick": help_tick,
                        "task_id": "human:goal:2",
                        "act": "COMPLETE",
                        "reason_code": "help_fulfilled",
                    },
                },
            ]
        )
    records.append(
        {
            "record_type": "session_end",
            "tick": 30,
            "content_sha256": digest_character * 64,
        }
    )
    return records


def _accepted_entries(protocol: dict):
    entries = []
    characters = iter("abcdef012")
    for block_index, block in enumerate(protocol["blocks"]):
        sessions = {
            condition: _session(
                protocol,
                block_index,
                condition,
                next(characters),
                slower=condition == "scripted",
            )
            for condition in CONDITIONS
        }
        ratings = {
            condition: build_human_rating(
                records[-1]["content_sha256"],
                5 if condition == "learned" else 4,
                condition == "learned",
                1 if condition == "learned" else 0,
                True,
            )
            for condition, records in sessions.items()
        }
        block_rating = build_block_rating(protocol, block["block_id"], sessions, 1, 0, True)
        entries.append(
            (
                block["block_id"],
                {
                    condition: (sessions[condition], ratings[condition])
                    for condition in CONDITIONS
                },
                block_rating,
            )
        )
    return entries


def test_protocol_freezes_runtime_conditions_orders_and_targets():
    protocol = build_human_protocol(_reference(), "owner-acceptance-v1", "learned-v1")
    assert protocol["minimum_complete_serious_blocks"] == 3
    assert [block["condition_order"] for block in protocol["blocks"]] == [
        ["absent", "scripted", "learned"],
        ["scripted", "learned", "absent"],
        ["learned", "absent", "scripted"],
    ]
    assert protocol["conditions"]["absent"]["agent_condition"] == "absent"
    assert protocol["conditions"]["learned"]["policy"] == "learned-v1"
    assert protocol["objective_targets"]["goal_compliance_rate"]["direction"] == "higher"


def test_protocol_round_trip_is_create_new_and_order_independent():
    root = Path(__file__).parents[2]
    protocol = build_human_protocol(_reference(), "owner-acceptance-v1", "learned-v1")
    with TemporaryDirectory(dir=root / "runs") as directory:
        path = Path(directory) / "protocol.json"
        write_human_protocol(path, protocol)
        assert load_human_protocol(path) == json.loads(path.read_text(encoding="utf-8"))
        with pytest.raises(ValueError, match="refusing to overwrite"):
            write_human_protocol(path, protocol)


def test_protocol_create_cli_writes_frozen_plan(monkeypatch, capsys):
    root = Path(__file__).parents[2]
    with TemporaryDirectory(dir=root / "runs") as directory:
        output = Path(directory) / "protocol.json"
        monkeypatch.setattr(human_protocol_tool, "load_session", lambda _: _reference())
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "human_protocol",
                "create",
                "--reference-session",
                "reference.jsonl",
                "--experiment-id",
                "owner-acceptance-v1",
                "--learned-policy",
                "learned-v1",
                "--output",
                str(output),
            ],
        )
        human_protocol_tool.main()
        protocol = load_human_protocol(output)
        assert protocol["conditions"]["learned"]["policy"] == "learned-v1"
        assert "HUMAN-PROTOCOL OK" in capsys.readouterr().out


def test_assigned_session_rejects_post_hoc_condition_label():
    protocol = build_human_protocol(_reference(), "owner-acceptance-v1", "learned-v1")
    records = _session(protocol, 0, "scripted", "a", slower=True)
    records[0]["experiment_condition"] = "learned"
    with pytest.raises(ValueError, match="session policy mismatch"):
        validate_assigned_session(protocol, "block-001", "learned", records)


def test_three_complete_serious_blocks_pass_frozen_acceptance_targets():
    protocol = build_human_protocol(_reference(), "owner-acceptance-v1", "learned-v1")
    report = human_protocol_report(protocol, _accepted_entries(protocol))
    assert report["complete_serious_block_count"] == 3
    assert report["serious_block_floor_met"] is True
    assert report["preference"]["learned_vs_absent_positive_blocks"] == 3
    assert report["preference"]["passed"] is True
    assert all(
        metric["passed"] for metric in report["objective_scorecard"].values()
    )
    assert report["acceptance_status"] == "passed"
    assert report["blocking_reasons"] == []


def test_missing_objective_observation_fails_closed():
    protocol = build_human_protocol(_reference(), "owner-acceptance-v1", "learned-v1")
    entries = _accepted_entries(protocol)
    learned_records = entries[0][1]["learned"][0]
    learned_records[:] = [
        learned_records[0],
        {"record_type": "trajectory", "tick": 10},
        learned_records[-1],
    ]
    report = human_protocol_report(protocol, entries)
    assert report["acceptance_status"] == "not_passed"
    assert "learned_objective_scorecard_regresses_vs_scripted" in report[
        "blocking_reasons"
    ]
