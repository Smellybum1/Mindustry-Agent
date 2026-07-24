"""Governance tests for ADR-0125's planner-correction diagnostic."""

import json
from pathlib import Path

import pytest

from mindustry_agents.training.ippo import AllSeatDecision
from mindustry_agents.training.planner_correction_causality import (
    PROTOCOL_SHA256,
    _paired_exact_binomial_p_value,
    classify,
    corrected_decision,
    paired_outcomes,
    validate_inputs,
)
from mindustry_agents.training.ippo_ppo import sha256_path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = (
    ROOT
    / "configs/evaluation/"
    "m9-planner-correction-causality-v1-protocol.json"
)


def _rules():
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))["classification"]


def _checkpoint_report(
    *,
    expected_wins: int = 13,
    expected_core: float = 242.975,
    baseline_wins: int = 13,
    baseline_core: float = 242.975,
    correct_all_wins: int,
):
    return {
        "expected_baseline_wins": expected_wins,
        "expected_baseline_mean_core_health": expected_core,
        "modes": {
            "baseline": {
                "wins": baseline_wins,
                "mean_core_health": baseline_core,
            },
            "correct_all": {"wins": correct_all_wins},
        },
    }


def _roots(wins: set[int]):
    return [
        {
            "seed": seed,
            "outcome": "win" if seed in wins else "loss",
        }
        for seed in range(40)
    ]


def test_protocol_is_exact_public_only_and_non_mutating():
    assert sha256_path(PROTOCOL) == PROTOCOL_SHA256
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["data_classification"] == "public_dev_only"
    assert [item["lineage_update"] for item in protocol["checkpoints"]] == [
        64,
        96,
    ]
    assert protocol["execution"]["mode_order"] == [
        "baseline",
        "correct_first",
        "correct_all",
    ]
    assert not protocol["authority"]["may_train_or_modify_model_or_optimizer"]
    assert not protocol["authority"]["may_access_confirmation"]
    assert not protocol["authority"]["may_access_held_out"]


def test_bound_inputs_are_exact_rejected_and_public():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if not all(
        (ROOT / item["path"]).exists() for item in protocol["checkpoints"]
    ):
        pytest.skip("ignored immutable checkpoints are not local")
    loaded, _, seeds = validate_inputs(ROOT)
    assert len(seeds) == len(set(seeds)) == 40
    assert [item["lineage_update"] for item in loaded["checkpoints"]] == [
        64,
        96,
    ]
    assert all(
        item["construction_passed"] is False
        and item["selected_or_promoted"] is False
        and item["repaired"] is False
        for item in loaded["checkpoints"]
    )


def test_classification_is_strong_low_mixed_or_invalid():
    strong = classify(
        [
            _checkpoint_report(correct_all_wins=28),
            _checkpoint_report(
                expected_core=234.425,
                baseline_core=234.425,
                correct_all_wins=35,
            ),
        ],
        _rules(),
    )
    assert strong["valid"]
    assert strong["signal"] == "strong_correction_signal"
    assert strong["strong_correction_signal"]
    assert not strong["successor_training_authorized"]

    low = classify(
        [
            _checkpoint_report(correct_all_wins=21),
            _checkpoint_report(
                expected_core=234.425,
                baseline_core=234.425,
                correct_all_wins=20,
            ),
        ],
        _rules(),
    )
    assert low["signal"] == "low_correction_signal"

    mixed = classify(
        [
            _checkpoint_report(correct_all_wins=27),
            _checkpoint_report(
                expected_core=234.425,
                baseline_core=234.425,
                correct_all_wins=29,
            ),
        ],
        _rules(),
    )
    assert mixed["signal"] == "mixed_correction_signal"

    invalid = classify(
        [
            _checkpoint_report(baseline_wins=12, correct_all_wins=40),
            _checkpoint_report(
                expected_core=234.425,
                baseline_core=234.425,
                correct_all_wins=40,
            ),
        ],
        _rules(),
    )
    assert not invalid["valid"]
    assert invalid["signal"] == "invalid"
    assert not invalid["strong_correction_signal"]


def test_paired_outcomes_and_exact_mcnemar_are_root_matched():
    baseline = _roots(set(range(13)))
    corrected = _roots(set(range(5, 25)))
    paired = paired_outcomes(baseline, corrected)
    assert paired["both_win"] == 8
    assert paired["baseline_only_win"] == 5
    assert paired["correct_all_only_win"] == 12
    assert paired["both_loss"] == 15
    assert paired["exact_mcnemar_binomial_p_value"] == (
        _paired_exact_binomial_p_value(5, 12)
    )
    assert _paired_exact_binomial_p_value(0, 0) == 1.0

    drifted = list(corrected)
    drifted[0] = {**drifted[0], "seed": 99}
    with pytest.raises(ValueError, match="seed order drifted"):
        paired_outcomes(baseline, drifted)


def test_correction_replaces_complete_eligible_bundle_not_forced_seat():
    student = [
        {"agent_id": 0, "task_action": {"type": "WAIT"}},
        {"agent_id": 1, "task_action": {"type": "CONTINUE_CURRENT_TASK"}},
        {"agent_id": 2, "task_action": {"type": "DEFEND"}},
    ]
    teacher = [
        {
            "agent_id": 0,
            "task_action": {
                "type": "SELECT_CANDIDATE_TASK",
                "candidate_index": 0,
            },
        },
        {"agent_id": 1, "task_action": {"type": "WAIT"}},
        {"agent_id": 2, "task_action": {"type": "WAIT"}},
    ]
    observations = [
        {"task_candidates": [{"task_type": "BUILD_LINE"}]},
        {"task_candidates": []},
        {"task_candidates": []},
    ]
    decision = AllSeatDecision(
        schema="test",
        agent_actions=student,
        features={},
        action_indices={0: 9, 1: 8, 2: 9},
        hidden_inputs={},
        old_log_probabilities={},
        old_values={},
        policy_loss_masks={},
        recurrent_resets={},
        evaluation_order=(0, 1, 2),
        model_state_sha256="0" * 64,
    )
    corrected = corrected_decision(
        decision,
        teacher,
        {0: 0, 1: 9},
        observations,
    )
    assert corrected.agent_actions[:2] == teacher[:2]
    assert corrected.agent_actions[2] == student[2]
    assert corrected.action_indices == {0: 0, 1: 9, 2: 9}
    assert decision.agent_actions == student


def test_classification_rejects_rule_drift():
    rules = _rules()
    rules["correct_first_role"] = "selection_signal"
    with pytest.raises(ValueError, match="classification drifted"):
        classify(
            [
                _checkpoint_report(correct_all_wins=28),
                _checkpoint_report(
                    expected_core=234.425,
                    baseline_core=234.425,
                    correct_all_wins=28,
                ),
            ],
            rules,
        )
