"""Focused ADR-0056 tests for deterministic teacher-conflict relabeling."""

from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

import torch

from mindustry_agents.policies import GreedyUtilityPolicy
from mindustry_agents.training.model import SelectorActorCritic
from mindustry_agents.training.ppo_selector import (
    EpisodeRollout,
    Transition,
    _effective_teacher_action,
    _evaluate,
    _json_digest,
    _partner_intent_teacher_conflict_filter,
    _partner_intent_teacher_conflict_relabel,
    ppo_update,
    teacher_trajectory_rehearsal_update,
    teacher_trajectory_warmup_update,
)


RISK = {
    "schema": "fixed_partner_selected_task_duplication_risk_v1",
    "agent_ids": [1, 2],
    "match": "task_id",
    "feature": "utility_features.duplication_risk",
    "value": 1.0,
}
FILTER = {
    "schema": "partner_intent_teacher_conflict_filter_v1",
    "match": "teacher_action_index_in_risk_candidate_indices",
    "applies_to": [
        "teacher_warmup",
        "teacher_rehearsal",
        "ppo_teacher_imitation",
    ],
}
RELABEL = {
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


def relabel_config() -> dict:
    return {
        "partner_intent_duplication_risk": copy.deepcopy(RISK),
        "partner_intent_teacher_conflict_relabel": copy.deepcopy(RELABEL),
        "successful_teacher_imitation_coefficient": 0.0,
        "optimizer_ppo": {"successful_teacher_imitation_coefficient": 0.0},
    }


def transition(
    *,
    original: int = 0,
    effective: int | None = None,
    conflict: bool = False,
    status: str | None = None,
    action: int = 1,
    successful: bool = True,
) -> Transition:
    candidates = torch.zeros((8, 37))
    for index in range(8):
        candidates[index, 0] = float(index + 1)
    return Transition(
        candidates=candidates,
        scalars=torch.zeros(56),
        candidate_present=torch.ones(8, dtype=torch.bool),
        action_mask=torch.ones(10, dtype=torch.bool),
        action=action,
        old_log_prob=0.0,
        old_value=0.0,
        reward=1.0,
        advanced_ticks=60,
        done=True,
        policy_loss_mask=True,
        successful_episode=successful,
        teacher_action=original,
        teacher_effective_action=effective,
        teacher_partner_intent_risk_conflict=conflict,
        teacher_partner_intent_relabel_status=status,
    )


def episode(items: list[Transition]) -> EpisodeRollout:
    return EpisodeRollout(
        seed=1,
        outcome="win",
        tick=60,
        core_health=100.0,
        transitions=items,
        reward_components={},
        trace=[],
        coordination_metrics={},
    )


def warmup_config() -> dict:
    return relabel_config() | {
        "teacher_warmup_cycles": 1,
        "teacher_warmup_epochs": 2,
        "teacher_warmup_minibatch_size": 2,
        "teacher_warmup_success_only": True,
        "teacher_warmup_shuffle_seed": 16,
        "teacher_warmup_minibatch_seed": 17,
        "teacher_warmup_samples_per_epoch": 2,
        "teacher_rehearsal_epochs_per_update": 1,
        "teacher_rehearsal_minibatch_seed": 18,
        "teacher_rehearsal_samples_per_epoch": 2,
        "max_grad_norm": 0.5,
    }


def ppo_config() -> dict:
    return relabel_config() | {
        "gamma_per_second": 0.99,
        "gae_lambda": 0.95,
        "minibatch_size": 3,
        "ppo_epochs": 1,
        "clip_ratio": 0.2,
        "value_coefficient": 0.5,
        "entropy_coefficient": 0.0,
        "success_imitation_coefficient": 0.0,
        "teacher_imitation_coefficient": 1.0,
        "max_grad_norm": 0.5,
    }


class TestV42ConflictRelabel(unittest.TestCase):
    def test_exact_validator_and_historical_noop(self) -> None:
        config = relabel_config()
        self.assertEqual(_partner_intent_teacher_conflict_relabel(config), RELABEL)
        self.assertIsNone(_partner_intent_teacher_conflict_relabel({}))

        malformed = []
        for key in RELABEL:
            value = copy.deepcopy(RELABEL)
            del value[key]
            malformed.append(value)
        malformed.append(RELABEL | {"extra": "forbidden"})
        malformed.append(RELABEL | {"schema": "wrong"})
        malformed.append(
            RELABEL
            | {
                "applies_to": [
                    "teacher_rehearsal",
                    "teacher_warmup",
                    "ppo_teacher_imitation",
                ]
            }
        )
        for value in malformed:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "invalid.*relabel"):
                    _partner_intent_teacher_conflict_relabel(
                        config | {"partner_intent_teacher_conflict_relabel": value}
                    )

        for mutation in (
            {"partner_intent_duplication_risk": None},
            {"partner_intent_teacher_conflict_filter": FILTER},
        ):
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):
                    _partner_intent_teacher_conflict_relabel(config | mutation)

    def test_relabel_requires_exact_zero_float_coefficients(self) -> None:
        base = relabel_config()
        variants = [
            {
                key: value
                for key, value in base.items()
                if key != "successful_teacher_imitation_coefficient"
            },
            base | {"successful_teacher_imitation_coefficient": 0},
            base | {"successful_teacher_imitation_coefficient": False},
            base | {"successful_teacher_imitation_coefficient": 0.1},
            base | {"optimizer_ppo": {}},
            base | {"optimizer_ppo": {"successful_teacher_imitation_coefficient": 0}},
            base
            | {"optimizer_ppo": {"successful_teacher_imitation_coefficient": False}},
            base
            | {"optimizer_ppo": {"successful_teacher_imitation_coefficient": -0.1}},
        ]
        for value in variants:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "coefficient 0.0"):
                    _partner_intent_teacher_conflict_relabel(value)

    def test_greedy_alternate_is_pure_and_fail_closed_on_catalog_drift(self) -> None:
        policy = GreedyUtilityPolicy()
        candidates = [
            {"index": 0, "task_type": "HARVEST_RESOURCE", "utility": 4.0},
            {"index": 1, "task_type": "BUILD_SCHEMATIC", "utility": 9.0},
        ]
        observation = {"task_candidates": candidates}
        mask = {"candidate_task": [True, True]}
        before = copy.deepcopy(policy.__dict__)
        self.assertEqual(
            policy.alternate_nonconflicting_candidate(0, observation, mask, [1]), 0
        )
        self.assertEqual(policy.__dict__, before)

        for bad_index in (True, 1):
            drift = copy.deepcopy(candidates)
            drift[0]["index"] = bad_index
            with self.subTest(index=bad_index):
                with self.assertRaisesRegex(ValueError, "catalog/index drift"):
                    policy.alternate_nonconflicting_candidate(
                        0, {"task_candidates": drift}, mask, []
                    )

    def test_greedy_alternate_exclusions_validity_wait_and_no_alternate(self) -> None:
        policy = GreedyUtilityPolicy()
        candidates = [
            {"index": 0, "task_type": "BUILD_SCHEMATIC", "utility": 10.0},
            {
                "index": 1,
                "task_type": "HARVEST_RESOURCE",
                "utility": 9.0,
                "valid": False,
            },
            {"index": 2, "task_type": "WAIT", "utility": 8.0},
            {"index": 3, "task_type": "DEFEND_REGION", "utility": 7.0},
        ]
        observation = {"task_candidates": candidates}
        self.assertEqual(
            policy.alternate_nonconflicting_candidate(
                0, observation, {"candidate_task": [True, True, True, True]}, [0]
            ),
            3,
        )
        self.assertIsNone(
            policy.alternate_nonconflicting_candidate(
                0, observation, {"candidate_task": [False, True, True, False]}, [0]
            )
        )
        self.assertIsNone(
            policy.alternate_nonconflicting_candidate(
                0, observation, {"candidate_task": []}, []
            )
        )

    def test_greedy_alternate_preserves_adaptive_preference_and_ties(self) -> None:
        policy = GreedyUtilityPolicy()
        candidates = [
            {"index": 0, "task_type": "HARVEST_RESOURCE", "utility": 2.0},
            {"index": 1, "task_type": "SUPPLY_TURRET", "utility": 3.0},
            {"index": 2, "task_type": "BUILD_SCHEMATIC", "utility": 99.0},
            {"index": 3, "task_type": "SUPPLY_TURRET", "utility": 3.0},
            {"index": 4, "task_type": "DEFEND_REGION", "utility": 1.0},
        ]
        observation = {"task_candidates": candidates}
        mask = {"candidate_task": [True] * 5}
        policy._preferred_types[0] = "SUPPLY_TURRET"
        self.assertEqual(
            policy.alternate_nonconflicting_candidate(0, observation, mask, []), 1
        )
        self.assertEqual(
            policy.alternate_nonconflicting_candidate(0, observation, mask, [1, 3]),
            2,
        )
        policy._return_to_defense.add(0)
        self.assertEqual(
            policy.alternate_nonconflicting_candidate(0, observation, mask, []), 4
        )
        policy._return_to_defense.clear()
        policy._preferred_types.clear()
        candidates[2]["utility"] = 3.0
        self.assertEqual(
            policy.alternate_nonconflicting_candidate(0, observation, mask, []), 1
        )

    def test_effective_teacher_action_all_modes_and_fail_closed_drift(self) -> None:
        historical = transition(original=2)
        self.assertEqual(
            _effective_teacher_action(
                historical, teacher_conflict_filter=None, teacher_conflict_relabel=None
            ),
            2,
        )
        self.assertEqual(
            _effective_teacher_action(
                transition(original=2, conflict=False),
                teacher_conflict_filter=FILTER,
                teacher_conflict_relabel=None,
            ),
            2,
        )
        self.assertIsNone(
            _effective_teacher_action(
                transition(original=2, conflict=True),
                teacher_conflict_filter=FILTER,
                teacher_conflict_relabel=None,
            )
        )
        cases = [
            (transition(original=2, effective=2, status="original_nonconflict"), 2),
            (
                transition(
                    original=2,
                    effective=3,
                    conflict=True,
                    status="relabeled_nonconflict",
                ),
                3,
            ),
            (
                transition(
                    original=2,
                    effective=None,
                    conflict=True,
                    status="fallback_excluded",
                ),
                None,
            ),
        ]
        for item, expected in cases:
            self.assertEqual(
                _effective_teacher_action(
                    item, teacher_conflict_filter=None, teacher_conflict_relabel=RELABEL
                ),
                expected,
            )

        inconsistent = [
            transition(
                original=2,
                effective=2,
                conflict=True,
                status="relabeled_nonconflict",
            ),
            transition(
                original=2,
                effective=3,
                conflict=True,
                status="fallback_excluded",
            ),
            transition(
                original=2,
                effective=None,
                conflict=True,
                status="relabeled_nonconflict",
            ),
            transition(original=2, effective=3, status="original_nonconflict"),
            transition(original=2, effective=2, status=None),
        ]
        for item in inconsistent:
            with self.subTest(item=item):
                with self.assertRaisesRegex(RuntimeError, "relabel transition"):
                    _effective_teacher_action(
                        item,
                        teacher_conflict_filter=None,
                        teacher_conflict_relabel=RELABEL,
                    )

    def test_warmup_and_rehearsal_retain_relabels_before_sampling(self) -> None:
        items = [
            transition(
                original=0,
                effective=2,
                conflict=True,
                status="relabeled_nonconflict",
            ),
            transition(
                original=1,
                effective=None,
                conflict=True,
                status="fallback_excluded",
            ),
            transition(original=3, effective=3, status="original_nonconflict"),
        ]
        config = warmup_config()
        outputs = []
        for _ in range(2):
            model = SelectorActorCritic(42)
            outputs.append(
                teacher_trajectory_warmup_update(
                    model,
                    torch.optim.Adam(model.parameters(), lr=0.0),
                    [episode(items)],
                    config,
                    torch.Generator().manual_seed(17),
                )
            )
        self.assertEqual(outputs[0], outputs[1])
        evidence = outputs[0]["teacher_conflict_relabel"]
        self.assertEqual(evidence["eligible_transitions"], 3)
        self.assertEqual(evidence["original_conflict_transitions"], 2)
        self.assertEqual(evidence["relabeled_transitions"], 1)
        self.assertEqual(evidence["fallback_excluded_transitions"], 1)
        self.assertEqual(evidence["retained_transitions"], 2)
        self.assertEqual(evidence["sampled_relabel_presentations"], 2)
        self.assertEqual(evidence["sampled_retained_presentations"], 4)
        schedule = evidence["sampled_retained_transition_indices_by_epoch"]
        self.assertTrue(all(sorted(order) == [0, 2] for order in schedule))
        self.assertEqual(
            evidence["sampled_retained_schedule_sha256"], _json_digest(schedule)
        )
        json.dumps(outputs[0])

        rehearsal_model = SelectorActorCritic(43)
        rehearsal = teacher_trajectory_rehearsal_update(
            rehearsal_model,
            torch.optim.Adam(rehearsal_model.parameters(), lr=0.0),
            [episode(items)],
            config,
            torch.Generator().manual_seed(18),
        )
        self.assertEqual(rehearsal["samples"], 2)
        self.assertEqual(
            rehearsal["teacher_conflict_relabel"]["sampled_relabel_presentations"],
            1,
        )

    def test_effective_labels_drive_ce_and_historical_has_no_keys(self) -> None:
        item = transition(
            original=0, effective=2, conflict=True, status="relabeled_nonconflict"
        )
        config = warmup_config() | {
            "teacher_warmup_epochs": 1,
            "teacher_warmup_samples_per_epoch": 1,
        }
        model = SelectorActorCritic(45)
        with torch.no_grad():
            _, logits, _ = model(
                item.candidates[None],
                item.scalars[None],
                item.candidate_present[None],
                item.action_mask[None],
            )
            expected = -torch.log_softmax(logits, dim=-1)[0, 2].item()
        metrics = teacher_trajectory_warmup_update(
            model,
            torch.optim.Adam(model.parameters(), lr=0.0),
            [episode([item])],
            config,
            torch.Generator().manual_seed(17),
        )
        self.assertAlmostEqual(metrics["mean_cross_entropy"], expected, places=6)

        historical_item = transition(original=0)
        historical_model = SelectorActorCritic(46)
        historical = teacher_trajectory_warmup_update(
            historical_model,
            torch.optim.Adam(historical_model.parameters(), lr=0.0),
            [episode([historical_item])],
            {
                key: value
                for key, value in config.items()
                if key
                not in {
                    "partner_intent_duplication_risk",
                    "partner_intent_teacher_conflict_relabel",
                    "optimizer_ppo",
                    "successful_teacher_imitation_coefficient",
                }
            },
            torch.Generator().manual_seed(17),
        )
        self.assertNotIn("teacher_conflict_relabel", historical)
        self.assertNotIn("teacher_conflict_filter", historical)

    def test_v40_filter_fixture_remains_exact(self) -> None:
        items = [transition(original=0, conflict=True), transition(original=1)]
        config = {
            key: value
            for key, value in warmup_config().items()
            if key != "partner_intent_teacher_conflict_relabel"
        } | {"partner_intent_teacher_conflict_filter": FILTER}
        model = SelectorActorCritic(48)
        metrics = teacher_trajectory_warmup_update(
            model,
            torch.optim.Adam(model.parameters(), lr=0.0),
            [episode(items)],
            config,
            torch.Generator().manual_seed(17),
        )
        evidence = metrics["teacher_conflict_filter"]
        self.assertEqual(
            evidence,
            FILTER
            | {
                "eligible_transitions": 2,
                "excluded_conflict_transitions": 1,
                "retained_transitions": 1,
                "sampled_conflict_presentations": 0,
                "sampled_retained_presentations": 2,
                "sampled_retained_transition_indices_by_epoch": [[1], [1]],
                "sampled_retained_schedule_sha256": _json_digest([[1], [1]]),
            },
        )

    def test_ppo_uses_effective_generic_label_only_and_emits_telemetry(self) -> None:
        items = [
            transition(
                original=0,
                effective=2,
                conflict=True,
                status="relabeled_nonconflict",
                action=1,
            ),
            transition(
                original=1,
                effective=None,
                conflict=True,
                status="fallback_excluded",
                action=2,
            ),
            transition(
                original=3,
                effective=3,
                status="original_nonconflict",
                action=3,
            ),
        ]
        model = SelectorActorCritic(50)
        with torch.no_grad():
            _, logits, _ = model(
                torch.stack([item.candidates for item in items]),
                torch.stack([item.scalars for item in items]),
                torch.stack([item.candidate_present for item in items]),
                torch.stack([item.action_mask for item in items]),
            )
            log_probs = torch.log_softmax(logits, dim=-1)
            expected_generic = float(((-log_probs[0, 2] - log_probs[2, 3]) / 2).item())
            expected_successful_original = float(
                (-log_probs[range(3), torch.tensor([0, 1, 3])]).mean().item()
            )
        metrics = ppo_update(
            model,
            torch.optim.Adam(model.parameters(), lr=0.0),
            [episode(items)],
            ppo_config(),
            torch.Generator().manual_seed(19),
        )
        self.assertAlmostEqual(
            metrics["teacher_imitation_loss"], expected_generic, places=6
        )
        self.assertEqual(metrics["teacher_imitation_samples"], 2.0)
        self.assertAlmostEqual(
            metrics["successful_teacher_imitation_loss"],
            expected_successful_original,
            places=6,
        )
        self.assertEqual(metrics["successful_teacher_imitation_samples"], 3.0)
        evidence = metrics["teacher_conflict_relabel"]
        self.assertEqual(evidence["sampled_relabel_presentations"], 1)
        self.assertEqual(evidence["sampled_retained_presentations"], 2)
        self.assertEqual(evidence["retained_transitions"], 2)
        self.assertEqual(
            evidence["sampled_retained_schedule_sha256"],
            _json_digest(evidence["sampled_retained_transition_indices_by_epoch"]),
        )
        json.dumps(metrics)

        historical_model = SelectorActorCritic(50)
        historical_config = {
            key: value
            for key, value in ppo_config().items()
            if key
            not in {
                "partner_intent_duplication_risk",
                "partner_intent_teacher_conflict_relabel",
                "optimizer_ppo",
            }
        }
        historical = ppo_update(
            historical_model,
            torch.optim.Adam(historical_model.parameters(), lr=0.0),
            [episode(items)],
            historical_config,
            torch.Generator().manual_seed(19),
        )
        for key in (
            "policy_loss",
            "value_loss",
            "entropy",
            "success_imitation_loss",
            "successful_teacher_imitation_loss",
            "successful_teacher_imitation_samples",
        ):
            self.assertEqual(metrics[key], historical[key])
        self.assertNotIn("teacher_conflict_relabel", historical)
        self.assertNotIn("teacher_conflict_filter", historical)

    def test_malformed_evaluation_config_is_rejected_before_launcher(self) -> None:
        config = relabel_config() | {
            "partner_intent_teacher_conflict_relabel": RELABEL | {"fallback": "wrong"},
            "action_sampling_seed": 1,
        }
        with patch(
            "mindustry_agents.training.ppo_selector.RlServerProcess",
            side_effect=AssertionError("launcher must not be reached"),
        ):
            with self.assertRaisesRegex(ValueError, "invalid.*relabel"):
                _evaluate(SelectorActorCritic(51), [], config, java="java", port=1)


if __name__ == "__main__":
    unittest.main()
