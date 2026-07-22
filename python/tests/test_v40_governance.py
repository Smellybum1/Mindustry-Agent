"""Governance checks for the precommitted V40 training coordinate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V39_CONFIG = (
    ROOT
    / "configs"
    / "training"
    / "m8-selector-v39-partner-intent-duplication-risk.json"
)
V40_CONFIG = (
    ROOT
    / "configs"
    / "training"
    / "m8-selector-v40-partner-intent-teacher-conflict-filter.json"
)
V40_UMBRELLA = (
    ROOT
    / "configs"
    / "evaluation"
    / "m8-selector-v40-confirmation-umbrella.json"
)
ADR_0054 = (
    ROOT
    / "docs"
    / "decisions"
    / "ADR-0054-v40-partner-intent-teacher-conflict-filter.md"
)

V40_CONFIG_SHA256 = (
    "230759e7e02dcca9a6b7608f7784b20f85845c40da0f7a28dd1ec13641d0013a"
)
V40_UMBRELLA_SHA256 = (
    "27c1948085e53dff1abdf7a6b99a8226f8d7e4f5e60c5f58b14cd1224b44d4be"
)
HELD_OUT_V6_SHA256 = (
    "2bf4aa04ef54d873e961ff367db849c14c72b83bb4d280c4e31ba75bdeefa51c"
)


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v40_is_the_exact_precommitted_v39_training_delta() -> None:
    v39 = _load_json(V39_CONFIG)
    v40 = _load_json(V40_CONFIG)

    assert _sha256(V40_CONFIG) == V40_CONFIG_SHA256
    assert {
        key for key in set(v39) | set(v40) if v39.get(key) != v40.get(key)
    } == {
        "candidate_version",
        "quality_intervention",
        "confirmation_seed_set",
        "partner_intent_teacher_conflict_filter",
    }
    assert v40["candidate_version"] == "v40"
    assert v40["quality_intervention"] == (
        "resource_actionability_staging_secondary_claim_wake_seat2_harvest_"
        "owned_schematic_staging_partner_intent_risk_and_teacher_conflict_filter_v13"
    )
    assert v40["confirmation_seed_set"] == (
        "configs/evaluation/bootstrap-defense-v1-dev-v36.json"
    )
    assert v40["partner_intent_teacher_conflict_filter"] == {
        "schema": "partner_intent_teacher_conflict_filter_v1",
        "match": "teacher_action_index_in_risk_candidate_indices",
        "applies_to": [
            "teacher_warmup",
            "teacher_rehearsal",
            "ppo_teacher_imitation",
        ],
    }

    for key in (
        "runtime_contract",
        "reward_schema",
        "quality_reward",
        "model_architecture",
        "normalizers",
        "train_seed_set",
        "teacher_warmup_seed_set",
        "dev_seed_set",
        "held_out_seed_set_id",
        "held_out_seed_set_version",
        "training_cycles",
        "teacher_warmup_cycles",
        "episodes_per_update",
        "model_init_seed",
        "action_sampling_seed",
        "shuffle_seed",
        "minibatch_seed",
        "teacher_warmup_shuffle_seed",
        "teacher_warmup_minibatch_seed",
        "teacher_rehearsal_minibatch_seed",
        "optimizer_ppo",
    ):
        assert v40[key] == v39[key]


def test_v40_value_free_reservation_precedes_governed_membership() -> None:
    umbrella = _load_json(V40_UMBRELLA)
    adr = ADR_0054.read_text(encoding="utf-8")

    assert _sha256(V40_UMBRELLA) == V40_UMBRELLA_SHA256
    assert umbrella["status"] == "reserved_before_membership_creation"
    assert umbrella["access_owner"] == "primary_agent_only"
    assert umbrella["delegation_forbidden"] is True
    assert umbrella["training_config"] == {
        "path": (
            "configs/training/"
            "m8-selector-v40-partner-intent-teacher-conflict-filter.json"
        ),
        "sha256": V40_CONFIG_SHA256,
    }

    replacement = umbrella["replacement_set"]
    assert replacement["seed_set_id"] == "bootstrap-defense-v1-dev-v36"
    assert replacement["seed_set_version"] == 36
    assert replacement["count"] == 160
    assert replacement["membership_state_at_reservation"] == "not_created"
    assert replacement["exclusive_namespace"] == {
        "minimum_inclusive": 4_000_000_000,
        "maximum_exclusive": 5_000_000_000,
    }
    assert replacement["replaces"] == "bootstrap-defense-v1-dev-v35"

    final_binding = umbrella["sealed_final_binding"]
    assert final_binding["seed_set_id"] == "bootstrap-defense-v1-held-out-v6"
    assert final_binding["seed_set_version"] == 6
    assert final_binding["sha256"] == HELD_OUT_V6_SHA256
    assert final_binding["consumption_state"] == "sealed_unconsumed"
    assert final_binding["membership_read_for_v40_reservation"] is False

    assert V40_CONFIG_SHA256 in adr
    assert V40_UMBRELLA_SHA256 in adr
