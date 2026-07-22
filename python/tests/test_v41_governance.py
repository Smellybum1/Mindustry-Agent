"""Governance checks for the precommitted V41 midpoint construction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V40_CONFIG = (
    ROOT
    / "configs"
    / "training"
    / "m8-selector-v40-partner-intent-teacher-conflict-filter.json"
)
V41_CONFIG = (
    ROOT
    / "configs"
    / "training"
    / "m8-selector-v41-adjacent-frontier-midpoint.json"
)
V41_UMBRELLA = (
    ROOT
    / "configs"
    / "evaluation"
    / "m8-selector-v41-confirmation-umbrella.json"
)
V41_DIAGNOSTIC_REPORT = (
    ROOT / "runs" / "m8-selector-v41-frontier-diagnostic-report.json"
)
V41_DIAGNOSTIC_RECORDS = (
    ROOT / "runs" / "m8-selector-v41-frontier-diagnostic-records.jsonl"
)
ADR_0055 = (
    ROOT
    / "docs"
    / "decisions"
    / "ADR-0055-v41-adjacent-frontier-midpoint.md"
)

V41_CONFIG_SHA256 = (
    "c4705974f18512a627ac9f12646b140ea60da79e0e8c50c5f35248298f00eac9"
)
V41_UMBRELLA_SHA256 = (
    "7ce8f5cf640978ef479165584d05c520a4e0200c3f49f986a14ae489d6d180f0"
)
V41_DIAGNOSTIC_REPORT_SHA256 = (
    "7da028137a4550a39daa9081f2945e9c21d33e497698404ded93385838d4d3fe"
)
V41_DIAGNOSTIC_RECORDS_SHA256 = (
    "4463ba2b62cdaa4a1a20ebfd76a6cf7571d52b128552866f9c2477a6ead5d2a0"
)
HELD_OUT_V6_SHA256 = (
    "2bf4aa04ef54d873e961ff367db849c14c72b83bb4d280c4e31ba75bdeefa51c"
)
V40_TRAINING_CONFIG = (
    "configs/training/"
    "m8-selector-v40-partner-intent-teacher-conflict-filter.json"
)
V40_TRAINING_COMMIT = "c288483436c1003d25dc64ce7aba968600d45f3a"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v41_is_the_exact_validated_adjacent_frontier_midpoint() -> None:
    from mindustry_agents.training.checkpoint_interpolation import (
        _validate_construction_config,
    )

    v41 = _load_json(V41_CONFIG)

    assert _sha256(V41_CONFIG) == V41_CONFIG_SHA256
    parents = _validate_construction_config(v41)
    assert parents == [
        {
            "role": "base",
            "training_config": V40_TRAINING_CONFIG,
            "training_repository_commit": V40_TRAINING_COMMIT,
            "update": 26,
            "weight": 0.5,
        },
        {
            "role": "auxiliary",
            "training_config": V40_TRAINING_CONFIG,
            "training_repository_commit": V40_TRAINING_COMMIT,
            "update": 25,
            "weight": 0.5,
        },
    ]


def test_v41_derived_runtime_is_v40_exact_without_training_behavior() -> None:
    v40 = _load_json(V40_CONFIG)
    v41 = _load_json(V41_CONFIG)

    runtime_keys = (
        "runtime_contract",
        "scenario_id",
        "scenario_version",
        "dev_seed_set",
        "held_out_seed_set_id",
        "held_out_seed_set_version",
        "reward_schema",
        "quality_reward",
        "policy_logit_adjustment",
        "scripted_partner_opening",
        "partner_intent_duplication_risk",
        "model_init_seed",
        "action_sampling_seed",
        "torch_threads",
        "model_architecture",
    )
    for key in runtime_keys:
        assert v41[key] == v40[key]

    assert set(v41) == {
        "schema",
        "candidate_version",
        "runtime_contract",
        "quality_intervention",
        "scenario_id",
        "scenario_version",
        "dev_seed_set",
        "confirmation_seed_set",
        "held_out_seed_set_id",
        "held_out_seed_set_version",
        "reward_schema",
        "quality_reward",
        "policy_logit_adjustment",
        "scripted_partner_opening",
        "partner_intent_duplication_risk",
        "model_init_seed",
        "action_sampling_seed",
        "torch_threads",
        "model_architecture",
        "checkpoint_construction",
    }
    assert v41["candidate_version"] == "v41"
    assert v41["quality_intervention"] == "v40_adjacent_frontier_midpoint_v14"
    assert v41["confirmation_seed_set"] == (
        "configs/evaluation/bootstrap-defense-v1-dev-v37.json"
    )
    assert "partner_intent_teacher_conflict_filter" not in v41
    assert not any(
        key.startswith(("teacher_", "training_")) for key in v41
    )
    assert "train_seed_set" not in v41
    assert "optimizer_ppo" not in v41


def test_v41_value_free_reservation_precedes_governed_membership() -> None:
    umbrella = _load_json(V41_UMBRELLA)

    assert _sha256(V41_UMBRELLA) == V41_UMBRELLA_SHA256
    assert umbrella["status"] == "reserved_before_membership_creation"
    assert umbrella["access_owner"] == "primary_agent_only"
    assert umbrella["delegation_forbidden"] is True
    assert umbrella["training_config"] == {
        "path": (
            "configs/training/m8-selector-v41-adjacent-frontier-midpoint.json"
        ),
        "sha256": V41_CONFIG_SHA256,
    }

    replacement = umbrella["replacement_set"]
    assert replacement["seed_set_id"] == "bootstrap-defense-v1-dev-v37"
    assert replacement["seed_set_version"] == 37
    assert replacement["count"] == 160
    assert replacement["membership_state_at_reservation"] == "not_created"
    assert replacement["exclusive_namespace"] == {
        "minimum_inclusive": 5_000_000_000,
        "maximum_exclusive": 6_000_000_000,
    }
    assert replacement["replaces"] == "bootstrap-defense-v1-dev-v36"

    final_binding = umbrella["sealed_final_binding"]
    assert final_binding["seed_set_id"] == "bootstrap-defense-v1-held-out-v6"
    assert final_binding["seed_set_version"] == 6
    assert final_binding["sha256"] == HELD_OUT_V6_SHA256
    assert final_binding["consumption_state"] == "sealed_unconsumed"
    assert final_binding["membership_read_for_v41_reservation"] is False


def test_v41_ignored_diagnostic_evidence_remains_exact() -> None:
    assert V41_DIAGNOSTIC_REPORT.exists()
    assert V41_DIAGNOSTIC_RECORDS.exists()
    assert _sha256(V41_DIAGNOSTIC_REPORT) == V41_DIAGNOSTIC_REPORT_SHA256
    assert _sha256(V41_DIAGNOSTIC_RECORDS) == V41_DIAGNOSTIC_RECORDS_SHA256


def test_adr_0055_pins_the_complete_v41_precommit_packet() -> None:
    adr = ADR_0055.read_text(encoding="utf-8")

    for digest in (
        V41_CONFIG_SHA256,
        V41_UMBRELLA_SHA256,
        V41_DIAGNOSTIC_REPORT_SHA256,
        V41_DIAGNOSTIC_RECORDS_SHA256,
    ):
        assert digest in adr
