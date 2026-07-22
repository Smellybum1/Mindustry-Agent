from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from mindustry_agents.evaluation.human_evidence import (
    human_evidence_report,
    write_human_evidence,
)
from mindustry_agents.evaluation.human_scorecard import build_human_rating
from mindustry_agents.tools import human_evidence as human_evidence_tool


def _records(
    digest: str,
    policy: str = "public-greedy-candidates-v1",
    schema_version: int = 2,
) -> list[dict]:
    provenance = (
        {
            "repository_commit": "1" * 40,
            "agent_plugin_sha256": "2" * 64,
            "server_sha256": "3" * 64,
        }
        if schema_version >= 2
        else {}
    )
    return [
        {
            "capture_schema_version": schema_version,
            "record_type": "session_start",
            "tick": 0,
            "engine_tag": "v159.7",
            "engine_commit": "c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c",
            "arc_version": "208a754044",
            "protocol_version": 1,
            "scenario_id": "bootstrap-defense-v0",
            "scenario_version": 1,
            "policy": policy,
            **provenance,
        },
        {"record_type": "trajectory", "tick": 10},
        {
            "record_type": "session_end",
            "tick": 11,
            "content_sha256": digest,
        },
    ]


def _entry(
    digest: str,
    *,
    serious: bool = True,
    keep: bool = True,
    comparison: int = 0,
    policy: str = "public-greedy-candidates-v1",
    schema_version: int = 2,
) -> tuple[list[dict], dict]:
    return (
        _records(digest, policy, schema_version),
        build_human_rating(digest, 4, keep, comparison, serious),
    )


def test_three_pin_compatible_serious_sessions_meet_only_the_floor():
    report = human_evidence_report(
        [
            _entry("a" * 64, comparison=1),
            _entry("b" * 64),
            _entry("c" * 64, keep=False, comparison=-1),
            _entry("d" * 64, serious=False),
        ]
    )
    assert report["distinct_session_count"] == 4
    assert report["serious_session_count"] == 3
    assert report["pin_compatible_serious_session_floor_met"] is True
    assert report["acceptance_status"] == "not_evaluated"
    assert "scorecard_targets_not_precommitted" in report["blocking_reasons"]
    assert "legacy_capture_v1_excluded_from_acceptance" not in report[
        "blocking_reasons"
    ]
    assert "agents_present_vs_absent_not_measured_by_rating_v1" in report[
        "blocking_reasons"
    ]
    group = report["groups"][0]
    assert group["serious_session_count"] == 3
    assert group["serious_session_floor_met"] is True
    assert group["serious_metrics"]["keep_this_team_rate"] == {
        "observed_sessions": 3,
        "mean": 2 / 3,
    }
    assert group["serious_metrics"]["comparative_rating_vs_scripted"] == {
        "observed_sessions": 3,
        "mean": 0.0,
    }


def test_incompatible_policy_groups_do_not_meet_comparable_floor():
    report = human_evidence_report(
        [
            _entry("a" * 64),
            _entry("b" * 64),
            _entry("c" * 64, policy="future-learned-policy-v1"),
        ]
    )
    assert report["serious_session_count"] == 3
    assert report["pin_compatible_serious_session_floor_met"] is False
    assert len(report["groups"]) == 2
    assert report["blocking_reasons"][0] == (
        "fewer_than_three_pin_compatible_serious_sessions"
    )


def test_duplicate_session_digest_is_rejected():
    with pytest.raises(ValueError, match="duplicate human session digest"):
        human_evidence_report([_entry("a" * 64), _entry("a" * 64)])


def test_missing_session_identity_is_rejected():
    records, rating = _entry("a" * 64)
    del records[0]["policy"]
    with pytest.raises(ValueError, match="session identity missing: policy"):
        human_evidence_report([(records, rating)])


def test_v2_missing_artifact_provenance_is_rejected():
    records, rating = _entry("a" * 64)
    del records[0]["server_sha256"]
    with pytest.raises(ValueError, match="session identity missing: server_sha256"):
        human_evidence_report([(records, rating)])


def test_legacy_v1_sessions_are_excluded_from_floor():
    report = human_evidence_report(
        [
            _entry("a" * 64, schema_version=1),
            _entry("b" * 64, schema_version=1),
            _entry("c" * 64, schema_version=1),
        ]
    )
    assert report["serious_session_count"] == 3
    assert report["pin_compatible_serious_session_floor_met"] is False
    assert "legacy_capture_v1_excluded_from_acceptance" in report[
        "blocking_reasons"
    ]
    assert report["groups"][0]["provenance_complete"] is False


def test_evidence_output_is_create_new():
    root = Path(__file__).parents[2]
    report = human_evidence_report([_entry("a" * 64)])
    with TemporaryDirectory(dir=root / "runs") as directory:
        path = Path(directory) / "evidence.json"
        write_human_evidence(path, report)
        assert json.loads(path.read_text(encoding="utf-8")) == report
        with pytest.raises(ValueError, match="refusing to overwrite"):
            write_human_evidence(path, report)


def test_human_evidence_cli_writes_report(monkeypatch, capsys):
    root = Path(__file__).parents[2]
    records, rating = _entry("a" * 64)
    with TemporaryDirectory(dir=root / "runs") as directory:
        output = Path(directory) / "evidence.json"
        monkeypatch.setattr(human_evidence_tool, "load_session", lambda _: records)
        monkeypatch.setattr(
            human_evidence_tool,
            "load_human_rating",
            lambda _path, _digest: rating,
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "human_evidence",
                "--entry",
                "session.jsonl",
                "rating.json",
                "--output",
                str(output),
            ],
        )
        human_evidence_tool.main()
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["distinct_session_count"] == 1
        output_text = capsys.readouterr().out
        assert "pin_floor=false" in output_text
        assert "acceptance=not_evaluated" in output_text
