"""Pure governance checks for the precommitted V42 training coordinate."""

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
V42_CONFIG = (
    ROOT
    / "configs"
    / "training"
    / "m8-selector-v42-partner-intent-teacher-conflict-relabel.json"
)
V42_UMBRELLA = (
    ROOT
    / "configs"
    / "evaluation"
    / "m8-selector-v42-confirmation-umbrella.json"
)

V42_CONFIG_SHA256 = (
    "3fcb0c8800c638a333068ab116f8270be076c1cbae2438b55cc6f193c0583d0d"
)
V42_UMBRELLA_SHA256 = (
    "c1644d2dd6dde231e3a3409632169e182bfb13ebaff84deb2225368a82371532"
)
V42_PARENT_COMMIT = "30e16e99b852f2f90141e174e9806978fc6a365b"
HELD_OUT_V6_SHA256 = (
    "2bf4aa04ef54d873e961ff367db849c14c72b83bb4d280c4e31ba75bdeefa51c"
)


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v42_is_the_exact_precommitted_v40_training_delta() -> None:
    v40 = _load_json(V40_CONFIG)
    v42 = _load_json(V42_CONFIG)

    assert _sha256(V42_CONFIG) == V42_CONFIG_SHA256
    assert {
        key for key in set(v40) | set(v42) if v40.get(key) != v42.get(key)
    } == {
        "candidate_version",
        "quality_intervention",
        "confirmation_seed_set",
        "partner_intent_teacher_conflict_filter",
        "partner_intent_teacher_conflict_relabel",
    }
    assert v42["candidate_version"] == "v42"
    assert v42["quality_intervention"] == (
        "resource_actionability_staging_secondary_claim_wake_seat2_harvest_"
        "owned_schematic_staging_partner_intent_risk_and_teacher_conflict_"
        "relabel_v14"
    )
    assert v42["confirmation_seed_set"] == (
        "configs/evaluation/bootstrap-defense-v1-dev-v38.json"
    )
    assert "partner_intent_teacher_conflict_filter" not in v42
    assert v42["partner_intent_teacher_conflict_relabel"] == {
        "schema": "partner_intent_teacher_conflict_relabel_v1",
        "match": "teacher_action_index_in_risk_candidate_indices",
        "selection": "adaptive_preference_then_highest_utility_nonrisk_select_v1",
        "fallback": "exclude_if_no_valid_nonrisk_select",
        "applies_to": [
            "teacher_warmup",
            "teacher_rehearsal",
            "ppo_teacher_imitation",
        ],
    }

    unchanged_groups = {
        "root": (
            "schema",
            "scenario_id",
            "scenario_version",
            "train_seed_set",
            "teacher_warmup_seed_set",
            "dev_seed_set",
            "held_out_seed_set_id",
            "held_out_seed_set_version",
        ),
        "runtime": (
            "runtime_contract",
            "policy_logit_adjustment",
            "scripted_partner_opening",
            "partner_intent_duplication_risk",
            "torch_threads",
        ),
        "reward": (
            "reward_schema",
            "quality_reward",
            "dev_checkpoint_selection",
        ),
        "model": ("normalizers", "model_architecture"),
        "budget": (
            "training_cycles",
            "teacher_warmup_cycles",
            "teacher_warmup_epochs",
            "teacher_warmup_minibatch_size",
            "teacher_warmup_success_only",
            "teacher_warmup_samples_per_epoch",
            "teacher_rehearsal_epochs_per_update",
            "teacher_rehearsal_samples_per_epoch",
            "episodes_per_update",
        ),
        "rng": (
            "model_init_seed",
            "action_sampling_seed",
            "shuffle_seed",
            "minibatch_seed",
            "teacher_warmup_shuffle_seed",
            "teacher_warmup_minibatch_seed",
            "teacher_rehearsal_minibatch_seed",
        ),
        "optimizer": ("optimizer_ppo",),
    }
    for keys in unchanged_groups.values():
        for key in keys:
            assert v42[key] == v40[key]


def test_v42_successful_teacher_imitation_remains_disabled() -> None:
    v42 = _load_json(V42_CONFIG)

    assert v42["successful_teacher_imitation_coefficient"] == 0.0
    assert (
        v42["optimizer_ppo"]["successful_teacher_imitation_coefficient"]
        == 0.0
    )


def test_v42_value_free_reservation_is_exact_and_access_gated() -> None:
    umbrella = _load_json(V42_UMBRELLA)

    assert _sha256(V42_UMBRELLA) == V42_UMBRELLA_SHA256
    assert umbrella["repository_parent_commit"] == V42_PARENT_COMMIT
    assert umbrella["status"] == "reserved_before_membership_creation"
    assert umbrella["access_owner"] == "primary_agent_only"
    assert umbrella["delegation_forbidden"] is True
    assert umbrella["training_config"] == {
        "path": (
            "configs/training/"
            "m8-selector-v42-partner-intent-teacher-conflict-relabel.json"
        ),
        "sha256": V42_CONFIG_SHA256,
    }

    replacement = umbrella["replacement_set"]
    assert replacement == {
        "role": "confirmation",
        "seed_set_id": "bootstrap-defense-v1-dev-v38",
        "seed_set_version": 38,
        "split": "dev",
        "count": 160,
        "path": "configs/evaluation/bootstrap-defense-v1-dev-v38.json",
        "exclusive_namespace": {
            "minimum_inclusive": 6_000_000_000,
            "maximum_exclusive": 7_000_000_000,
        },
        "membership_state_at_reservation": "not_created",
        "exclusive_umbrella_attempt": (
            "runs/m8-selector-v42-dev-v38-umbrella-attempt.json"
        ),
        "replaces": "bootstrap-defense-v1-dev-v37",
    }

    final_binding = umbrella["sealed_final_binding"]
    assert final_binding == {
        "seed_set_id": "bootstrap-defense-v1-held-out-v6",
        "seed_set_version": 6,
        "split": "held-out",
        "count": 160,
        "path": "configs/evaluation/bootstrap-defense-v1-held-out-v6.json",
        "sha256": HELD_OUT_V6_SHA256,
        "consumption_state": "sealed_unconsumed",
        "membership_read_for_v42_reservation": False,
    }

    assert umbrella["rules"] == [
        (
            "This reservation and the exact V42 relabel coordinate must be "
            "committed before dev-v38 membership creation or model work."
        ),
        (
            "Membership construction and disjointness verification are "
            "primary-agent-only and must not render seed values into agent output."
        ),
        (
            "Dev-v38 must be generated solely within [6000000000,7000000000), "
            "disjoint by namespace from every prior governed set without reading "
            "their membership."
        ),
        (
            "The committed one-way consumer must atomically create the dev-v38 "
            "umbrella attempt before its first manifest read or baseline episode."
        ),
        (
            "A started, aborted, failed, exposed, or completed dev-v38 attempt "
            "consumes that set permanently."
        ),
        (
            "No dev-v38 access is authorized until exact replicas and reusable "
            "permanent-greedy and matched-greedy scorecards pass."
        ),
        (
            "Held-out-v6 remains governed by ADR-0053 and cannot be read until "
            "dev-v38 passes every frozen gate."
        ),
    ]
