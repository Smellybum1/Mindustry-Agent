"""Prospective V49 operational non-inferiority protocol checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from mindustry_agents.training.scorecard_protocol import (
    PASS_RULE,
    PROTOCOL_SCHEMA,
    SCORECARD_SCHEMA,
    load_scorecard_protocol,
)


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = (
    ROOT
    / "configs"
    / "evaluation"
    / "m8-selector-v49-noninferiority-protocol.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _margins() -> dict[str, float]:
    return {
        "announcements_per_meaningful_transition": 0.01,
        "duplicate_work_incidents": 0.05,
        "idle_fraction": 1.0 / 150.0,
        "recovery_time_after_agent_loss_ticks": 60.0,
        "task_abandonment_rate": 0.01,
        "time_to_help_ticks": 60.0,
    }


def _document(root: Path) -> tuple[dict[str, object], Path, Path, Path]:
    config = root / "config.json"
    checkpoint = root / "checkpoint.pt"
    seed_set = root / "reusable.json"
    config.write_text("{}\n", encoding="utf-8")
    checkpoint.write_bytes(b"checkpoint")
    document: dict[str, object] = {
        "schema": PROTOCOL_SCHEMA,
        "candidate_version": "v49",
        "status": "precommitted_before_reusable_v3_membership",
        "candidate": {
            "behavior": "v47_selected_checkpoint_unchanged",
            "training_config": {
                "path": "config.json",
                "sha256": _sha256(config),
            },
            "checkpoint": {
                "path": "checkpoint.pt",
                "sha256": _sha256(checkpoint),
            },
        },
        "scorecard": {
            "schema": SCORECARD_SCHEMA,
            "direction": "candidate_minus_baseline; lower is better",
            "bootstrap_resamples": 10000,
            "confidence_level": 0.95,
            "uncertainty_is_failure": True,
            "pass_rule": PASS_RULE,
            "margins": _margins(),
            "required_baselines": [
                "permanent_greedy_utility",
                "matched_greedy_utility",
            ],
        },
        "reusable": {
            "seed_set_id": "reusable",
            "seed_set_version": 3,
            "split": "dev",
            "count": 160,
            "path": "reusable.json",
        },
    }
    return document, config, checkpoint, seed_set


def test_checked_in_v49_protocol_is_frozen_before_new_membership() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["schema"] == PROTOCOL_SCHEMA
    assert protocol["status"] == "precommitted_before_reusable_v3_membership"
    assert protocol["candidate"]["behavior"] == (
        "v47_selected_checkpoint_unchanged"
    )
    assert protocol["scorecard"]["margins"] == _margins()
    assert protocol["reusable"]["membership_state_at_precommit"] == "not_created"
    assert protocol["confirmation"]["membership_state_at_precommit"] == (
        "not_created"
    )
    assert protocol["final"]["membership_state_at_precommit"] == "not_created"
    assert protocol["retired_sets"]["held_out_v6"] == (
        "retired_membership_exposed_unexecuted"
    )


def test_protocol_loader_binds_artifacts_seed_role_and_margins(
    tmp_path: Path,
) -> None:
    document, config, checkpoint, seed_set = _document(tmp_path)
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps(document) + "\n", encoding="utf-8")

    loaded = load_scorecard_protocol(
        protocol,
        root=tmp_path,
        config_path=config,
        checkpoint_path=checkpoint,
        seed_set_path=seed_set,
        role="reusable",
    )
    assert loaded["sha256"] == _sha256(protocol)
    assert loaded["margins"] == _margins()
    assert loaded["seed_set"]["id"] == "reusable"


def test_protocol_loader_rejects_margin_and_artifact_drift(
    tmp_path: Path,
) -> None:
    document, config, checkpoint, seed_set = _document(tmp_path)
    document["scorecard"]["margins"].pop("idle_fraction")
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps(document) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exact metric schema"):
        load_scorecard_protocol(
            protocol,
            root=tmp_path,
            config_path=config,
            checkpoint_path=checkpoint,
            seed_set_path=seed_set,
            role="reusable",
        )

    document, config, checkpoint, seed_set = _document(tmp_path)
    document["candidate"]["checkpoint"]["sha256"] = "0" * 64
    protocol.write_text(json.dumps(document) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact drifted"):
        load_scorecard_protocol(
            protocol,
            root=tmp_path,
            config_path=config,
            checkpoint_path=checkpoint,
            seed_set_path=seed_set,
            role="reusable",
        )
