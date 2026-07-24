"""Governance tests for ADR-0115's immutable agreement diagnostic."""

from pathlib import Path

import pytest

from mindustry_agents.training.candidate_distill_agreement import (
    PROTOCOL_SHA256,
    action_task,
    classify,
    validate_inputs,
)
from mindustry_agents.training.ippo_ppo import sha256_path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = (
    ROOT
    / "configs/evaluation/"
    "m9-candidate-distill-v1-agreement-diagnostic-protocol.json"
)


def test_protocol_is_exact_and_public_only():
    assert sha256_path(PROTOCOL) == PROTOCOL_SHA256
    protocol, _, seeds = validate_inputs(ROOT)
    assert len(seeds) == len(set(seeds)) == 40
    assert protocol["data_classification"] == "public_dev_only"
    assert [item["update"] for item in protocol["checkpoints"]] == [3, 32]
    assert not protocol["authority"]["may_access_confirmation"]
    assert not protocol["authority"]["may_access_held_out"]
    assert not protocol["authority"]["may_train_or_modify_model"]


def test_action_task_uses_structured_candidate_family():
    observation = {
        "task_candidates": [
            {"task_type": "HARVEST_RESOURCE"},
            {"task_type": "DEFEND_REGION"},
        ]
    }
    assert action_task(0, observation) == "HARVEST_RESOURCE"
    assert action_task(1, observation) == "DEFEND_REGION"
    assert action_task(8, observation) == "CONTINUE_CURRENT_TASK"
    assert action_task(9, observation) == "WAIT"
    with pytest.raises(ValueError, match="no candidate"):
        action_task(2, observation)


def test_classification_reports_exact_non_authorizing_signals():
    rules = {
        "teacher_forced_fit_retained": {
            "minimum_top1_agreement": 0.9,
            "maximum_teacher_label_nll": 0.35,
        }
    }
    closed_loop = classify(
        [
            {
                "update": 3,
                "eligible_labels": 100,
                "top1_agreement": 0.92,
                "teacher_label_nll": 0.2,
                "autonomous_public_dev_wins": 18,
            },
            {
                "update": 32,
                "eligible_labels": 100,
                "top1_agreement": 0.91,
                "teacher_label_nll": 0.25,
                "autonomous_public_dev_wins": 9,
            },
        ],
        rules,
    )
    assert closed_loop["closed_loop_shift_signal"]
    assert not closed_loop["forgetting_signal"]
    assert not closed_loop["generalization_gap_signal"]
    assert not closed_loop["successor_training_authorized"]

    forgetting = classify(
        [
            {
                "update": 3,
                "eligible_labels": 100,
                "top1_agreement": 0.93,
                "teacher_label_nll": 0.2,
                "autonomous_public_dev_wins": 18,
            },
            {
                "update": 32,
                "eligible_labels": 100,
                "top1_agreement": 0.80,
                "teacher_label_nll": 0.5,
                "autonomous_public_dev_wins": 9,
            },
        ],
        rules,
    )
    assert forgetting["forgetting_signal"]
    assert not forgetting["generalization_gap_signal"]

    gap = classify(
        [
            {
                "update": 3,
                "eligible_labels": 100,
                "top1_agreement": 0.7,
                "teacher_label_nll": 0.6,
                "autonomous_public_dev_wins": 18,
            },
            {
                "update": 32,
                "eligible_labels": 100,
                "top1_agreement": 0.75,
                "teacher_label_nll": 0.5,
                "autonomous_public_dev_wins": 9,
            },
        ],
        rules,
    )
    assert gap["generalization_gap_signal"]
    drifted = {
        "teacher_forced_fit_retained": {
            "minimum_top1_agreement": 0.89,
            "maximum_teacher_label_nll": 0.35,
        }
    }
    with pytest.raises(ValueError, match="thresholds drifted"):
        classify([], drifted)
