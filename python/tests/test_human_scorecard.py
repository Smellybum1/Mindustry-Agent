from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from mindustry_agents.evaluation.human_scorecard import (
    human_teammate_scorecard,
    load_human_rating,
    write_human_scorecard,
)


def _control(tick: int, kind: str, goal_id: str, task_type: str = "") -> dict:
    command = {"type": kind, "author_id": "probe"}
    if task_type:
        command.update(task_type=task_type, region_id="test")
    elif goal_id:
        command["goal_id"] = goal_id
    return {
        "record_type": "control",
        "tick": tick,
        "control": {
            "tick": tick,
            "accepted": True,
            "goal_id": goal_id,
            "canonical_command": command,
        },
    }


def _event(tick: int, task_id: str, act: str = "", reason: str = "") -> dict:
    return {
        "record_type": "coordination",
        "tick": tick,
        "announcement_status": "rendered" if act == "COMPLETE" else "not_requested",
        "event": {
            "tick": tick,
            "task_id": task_id,
            "act": act,
            "reason_code": reason,
        },
    }


def _records() -> list[dict]:
    return [
        {"record_type": "session_start", "tick": 0},
        {"record_type": "trajectory", "tick": 10},
        _control(10, "GOAL", "human:goal:1", "BUILD_LINE"),
        {
            "record_type": "human_presence",
            "tick": 10,
            "added": [{"id": "human:presence:1"}],
            "removed": [],
        },
        _event(11, "agent-task", reason="yield_to_human"),
        _event(15, "human:goal:1", act="COMPLETE"),
        {"record_type": "trajectory", "tick": 20},
        _control(20, "GOAL", "human:goal:2", "REQUEST_HELP"),
        _event(25, "human:goal:2", reason="help_fulfilled"),
        {"record_type": "trajectory", "tick": 30},
        _control(30, "CANCEL", "human:goal:2"),
        {
            "record_type": "coordination",
            "tick": 31,
            "announcement_status": "suppressed",
            "event": {"tick": 31, "task_id": "other", "act": "PROGRESS"},
        },
        {
            "record_type": "session_end",
            "tick": 32,
            "content_sha256": "a" * 64,
        },
    ]


def test_human_scorecard_derives_structured_metrics_without_rating():
    scorecard = human_teammate_scorecard(_records())
    metrics = scorecard["metrics"]
    assert scorecard["rating_status"] == "not_provided"
    assert metrics["human_intervention_rate"] == 1.0
    assert metrics["accepted_human_commands"] == 3
    assert metrics["trajectory_boundaries"] == 3
    assert metrics["trajectory_boundary_ticks"] == 3
    assert metrics["plan_conflicts_per_session"] == 1
    assert metrics["mean_yield_latency_ticks"] == 1.0
    assert metrics["goal_compliance_rate"] == 1.0
    assert metrics["human_goals_created"] == 2
    assert metrics["human_goals_eligible"] == 1
    assert metrics["mean_time_to_help_ticks"] == 5.0
    assert metrics["announcement_usefulness_rating"] is None
    assert metrics["rendered_announcements"] == 1
    assert metrics["suppressed_announcements"] == 1


def test_digest_bound_rating_and_create_new_output():
    root = Path(__file__).parents[2]
    with TemporaryDirectory(dir=root / "runs") as directory:
        directory_path = Path(directory)
        rating_path = directory_path / "rating.json"
        output_path = directory_path / "scorecard.json"
        rating_path.write_text(
            json.dumps(
                {
                    "schema": "human_session_rating_v1",
                    "version": 1,
                    "session_content_sha256": "a" * 64,
                    "announcement_usefulness_rating": 4,
                    "keep_this_team": True,
                    "comparative_rating_vs_scripted": 1,
                    "serious_session": True,
                }
            ),
            encoding="utf-8",
        )
        rating = load_human_rating(rating_path, "a" * 64)
        scorecard = human_teammate_scorecard(_records(), rating)
        assert scorecard["rating_status"] == "provided"
        assert scorecard["metrics"]["keep_this_team"] is True
        assert scorecard["metrics"]["announcement_usefulness_rating"] == 4

        write_human_scorecard(output_path, scorecard)
        assert json.loads(output_path.read_text(encoding="utf-8")) == scorecard
        with pytest.raises(ValueError, match="refusing to overwrite"):
            write_human_scorecard(output_path, scorecard)


def test_rating_rejects_wrong_session_digest():
    root = Path(__file__).parents[2]
    with TemporaryDirectory(dir=root / "runs") as directory:
        path = Path(directory) / "rating.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "human_session_rating_v1",
                    "version": 1,
                    "session_content_sha256": "b" * 64,
                    "announcement_usefulness_rating": 5,
                    "keep_this_team": True,
                    "comparative_rating_vs_scripted": 2,
                    "serious_session": True,
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="digest mismatch"):
            load_human_rating(path, "a" * 64)
        wrong_rating = json.loads(path.read_text(encoding="utf-8"))
        with pytest.raises(ValueError, match="digest mismatch"):
            human_teammate_scorecard(_records(), wrong_rating)
