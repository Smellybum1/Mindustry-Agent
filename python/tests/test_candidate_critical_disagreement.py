"""Governance tests for ADR-0119's critical-disagreement diagnostic."""

from pathlib import Path

import pytest

from mindustry_agents.training.candidate_critical_disagreement import (
    PROTOCOL_SHA256,
    classify,
    validate_inputs,
)
from mindustry_agents.training.ippo_ppo import sha256_path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = (
    ROOT
    / "configs/evaluation/"
    "m9-candidate-on-policy-critical-disagreement-protocol.json"
)


def _rules():
    return {
        "top_task_pairs": 3,
        "minimum_top_task_pair_disagreement_fraction_for_concentration": 0.5,
        "minimum_dominant_first_pair_loss_fraction_for_concentration": 0.5,
        "minimum_loss_minus_win_rejection_episode_fraction": 0.25,
    }


def _report(
    task_counts: dict[str, int],
    first_loss: dict[str, int],
    *,
    win_rejections: int,
    loss_rejections: int,
):
    return {
        "eligible_labels": 100,
        "top1_disagreements": sum(task_counts.values()),
        "episodes_by_outcome": {"win": 10, "loss": 30},
        "teacher_task_to_student_task_confusion_by_outcome": task_counts,
        "first_disagreement_task_pair_on_losses": first_loss,
        "episodes_with_rejection_by_outcome": {
            "win": win_rejections,
            "loss": loss_rejections,
        },
    }


def test_protocol_is_exact_public_only_and_non_mutating():
    assert sha256_path(PROTOCOL) == PROTOCOL_SHA256
    protocol = __import__("json").loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["data_classification"] == "public_dev_only"
    assert [item["lineage_update"] for item in protocol["checkpoints"]] == [
        32,
        64,
    ]
    assert not protocol["authority"]["may_train_or_modify_model"]
    assert not protocol["authority"]["may_access_confirmation"]
    assert not protocol["authority"]["may_access_held_out"]


def test_bound_local_inputs_are_exact_and_rejected():
    protocol = __import__("json").loads(PROTOCOL.read_text(encoding="utf-8"))
    if not all((ROOT / item["path"]).exists() for item in protocol["checkpoints"]):
        pytest.skip("ignored immutable checkpoints are not local")
    loaded, _, seeds = validate_inputs(ROOT)
    assert len(seeds) == len(set(seeds)) == 40
    assert [item["lineage_update"] for item in loaded["checkpoints"]] == [
        32,
        64,
    ]


def test_classification_distinguishes_concentrated_and_rejection_signals():
    concentrated = classify(
        _report(
            {
                "WAIT->DEFEND_REGION:loss": 30,
                "SUPPLY_TURRET->HARVEST_RESOURCE:loss": 10,
                "HARVEST_RESOURCE->SUPPLY_TURRET:win": 5,
            },
            {"WAIT->DEFEND_REGION": 20},
            win_rejections=1,
            loss_rejections=20,
        ),
        _rules(),
    )
    assert concentrated["concentrated_critical_error_signal"]
    assert concentrated["rejection_association_signal"]
    assert not concentrated["diffuse_residual_signal"]
    assert not concentrated["successor_training_authorized"]

    diffuse = classify(
        _report(
            {
                "A->B:loss": 10,
                "C->D:loss": 10,
                "E->F:loss": 10,
                "G->H:loss": 10,
                "I->J:win": 10,
                "K->L:win": 10,
                "M->N:win": 10,
            },
            {"A->B": 5, "C->D": 5, "E->F": 5, "G->H": 5},
            win_rejections=2,
            loss_rejections=6,
        ),
        _rules(),
    )
    assert not diffuse["concentrated_critical_error_signal"]
    assert not diffuse["rejection_association_signal"]
    assert diffuse["diffuse_residual_signal"]
    drifted = _rules()
    drifted["top_task_pairs"] = 2
    with pytest.raises(ValueError, match="thresholds drifted"):
        classify(diffuse, drifted)
