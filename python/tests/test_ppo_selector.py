import hashlib
import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


@unittest.skipIf(importlib.util.find_spec("torch") is None, "RL extra is not installed")
class TestPpoSelector(unittest.TestCase):
    @staticmethod
    def _repro_manifest(trace_digest="trace-a"):
        from mindustry_agents.training.ppo_selector import (
            _json_digest,
            _reproducibility_evidence,
        )

        manifest = {
            "source_config": {"sha256": "config"},
            "runtime": {"jvm_args": ["-Xbatch"]},
            "rng_seeds": {"model_init_seed": 1},
            "initial_model_state_sha256": "initial",
            "checkpoint": {"update": 1, "model_state_sha256": "selected"},
            "optimizer_updates": [{"policy_loss": 0.25}],
            "dev_checkpoint_selection": [
                {
                    "update": 1,
                    "wins": 1,
                    "mean_return": 2.0,
                    "mean_core_health": 3.0,
                }
            ],
            "train": [{"trace_digest": trace_digest}],
            "dev": [{"trace_digest": "dev"}],
            "scorecard": {"dev_wins": 1},
            "action_state_trace_digest": "dev-traces",
            "deterministic_checkpoint_verification": {
                "seed": 2,
                "fresh_runs": 2,
                "trace_digest_a": "replay",
                "trace_digest_b": "replay",
                "bit_exact": True,
            },
        }
        manifest["full_run_reproducibility"] = {
            "schema": "selector_training_reproducibility_v1",
            "digest": _json_digest(_reproducibility_evidence(manifest)),
        }
        return manifest

    def test_held_out_seed_set_is_refused(self):
        from mindustry_agents.process.launcher import repo_root
        from mindustry_agents.training.ppo_selector import _seed_set

        with self.assertRaisesRegex(ValueError, "held-out"):
            _seed_set(
                repo_root(),
                "configs/evaluation/bootstrap-defense-v1-held-out-v1.json",
                "dev",
            )

    def test_training_seed_schedule_repeats_only_train_seeds_deterministically(self):
        from mindustry_agents.training.ppo_selector import _training_seed_schedule

        train_set = {"seeds": [1, 2, 3, 4]}
        config = {"shuffle_seed": 91, "training_cycles": 3}
        first = _training_seed_schedule(train_set, config)
        second = _training_seed_schedule(train_set, config)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 12)
        for start in range(0, len(first), 4):
            self.assertEqual(sorted(first[start : start + 4]), [1, 2, 3, 4])

        with self.assertRaisesRegex(ValueError, "training_cycles"):
            _training_seed_schedule(
                train_set, {"shuffle_seed": 91, "training_cycles": 0}
            )

    def test_teacher_warmup_schedule_is_separate_deterministic_and_optional(self):
        import torch

        from mindustry_agents.training.ppo_selector import (
            _policy_logit_adjustment,
            _task_type_logit_bias,
            _teacher_rehearsal_policy,
            _teacher_warmup_policy,
            _teacher_warmup_seed_schedule,
            _teacher_warmup_train_set,
        )

        train_set = {"seeds": [1, 2, 3, 4]}
        config = {
            "teacher_warmup_cycles": 2,
            "teacher_warmup_shuffle_seed": 123,
        }
        first = _teacher_warmup_seed_schedule(train_set, config)
        second = _teacher_warmup_seed_schedule(train_set, config)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 8)
        self.assertEqual(sorted(first[:4]), [1, 2, 3, 4])
        self.assertEqual(sorted(first[4:]), [1, 2, 3, 4])
        self.assertEqual(_teacher_warmup_seed_schedule(train_set, {}), [])
        self.assertIs(_teacher_warmup_train_set(Path.cwd(), train_set, {}), train_set)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            auxiliary_path = root / "auxiliary.json"
            auxiliary_path.write_text(
                json.dumps(
                    {
                        "seed_set_id": "teacher-train-v1",
                        "seed_set_version": 1,
                        "split": "train",
                        "seeds": [11, 12],
                    }
                ),
                encoding="utf-8",
            )
            auxiliary = _teacher_warmup_train_set(
                root,
                train_set,
                {"teacher_warmup_seed_set": "auxiliary.json"},
            )
            self.assertEqual(auxiliary["seeds"], [11, 12])
            auxiliary_path.write_text(
                json.dumps(
                    {
                        "seed_set_id": "teacher-dev-v1",
                        "seed_set_version": 1,
                        "split": "dev",
                        "seeds": [11, 12],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "expected train"):
                _teacher_warmup_train_set(
                    root,
                    train_set,
                    {"teacher_warmup_seed_set": "auxiliary.json"},
                )
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            _teacher_warmup_seed_schedule(
                train_set, {"teacher_warmup_cycles": -1}
            )
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            _teacher_warmup_policy(
                {
                    "teacher_warmup_cycles": 1,
                    "teacher_warmup_epochs": 1,
                    "teacher_warmup_minibatch_size": 1,
                    "teacher_warmup_success_only": 1,
                    "teacher_warmup_shuffle_seed": 123,
                    "teacher_warmup_minibatch_seed": 124,
                },
            )
        with self.assertRaisesRegex(ValueError, "requires teacher warmup"):
            _teacher_rehearsal_policy(
                {
                    "teacher_rehearsal_epochs_per_update": 1,
                    "teacher_rehearsal_minibatch_seed": 125,
                }
            )
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            _teacher_rehearsal_policy(
                {"teacher_rehearsal_epochs_per_update": -1}
            )
        with self.assertRaisesRegex(ValueError, "requires teacher warmup"):
            _teacher_warmup_policy(
                {"teacher_warmup_seed_set": "auxiliary.json"}
            )
        warmup_config = {
            "teacher_warmup_cycles": 1,
            "teacher_warmup_epochs": 1,
            "teacher_warmup_minibatch_size": 1,
            "teacher_warmup_success_only": True,
            "teacher_warmup_shuffle_seed": 123,
            "teacher_warmup_minibatch_seed": 124,
        }
        with self.assertRaisesRegex(
            ValueError, "samples_per_epoch must be positive"
        ):
            _teacher_warmup_policy(
                warmup_config | {"teacher_warmup_samples_per_epoch": 0}
            )
        with self.assertRaisesRegex(
            ValueError, "samples_per_epoch must be positive"
        ):
            _teacher_rehearsal_policy(
                warmup_config
                | {
                    "teacher_rehearsal_epochs_per_update": 1,
                    "teacher_rehearsal_minibatch_seed": 125,
                    "teacher_rehearsal_samples_per_epoch": -1,
                }
            )
        adjustment = _policy_logit_adjustment(
            {
                "policy_logit_adjustment": {
                    "schema": "initial_task_type_logit_bias_v1",
                    "tick": 0,
                    "task_type": "BUILD_SCHEMATIC",
                    "bias": 1.0,
                }
            }
        )
        bias = _task_type_logit_bias(
            [
                {"task_type": "BUILD_LINE"},
                {"task_type": "BUILD_SCHEMATIC"},
            ],
            [True] * 10,
            tick=0,
            adjustment=adjustment,
        )
        self.assertIsNotNone(bias)
        self.assertEqual(bias.tolist(), [0.0, 1.0] + [0.0] * 8)
        self.assertIsNone(
            _task_type_logit_bias(
                [{"task_type": "BUILD_SCHEMATIC"}],
                torch.ones(10, dtype=torch.bool),
                tick=1,
                adjustment=adjustment,
            )
        )
        with self.assertRaisesRegex(ValueError, "unsupported"):
            _policy_logit_adjustment(
                {"policy_logit_adjustment": {"schema": "unknown"}}
            )
        with self.assertRaisesRegex(ValueError, "invalid initial"):
            _policy_logit_adjustment(
                {
                    "policy_logit_adjustment": {
                        "schema": "initial_task_type_logit_bias_v1",
                        "tick": 0,
                        "task_type": "BUILD_SCHEMATIC",
                        "bias": 0.0,
                    }
                }
            )
        with self.assertRaisesRegex(RuntimeError, "matched no valid candidate"):
            _task_type_logit_bias(
                [{"task_type": "BUILD_LINE"}],
                torch.ones(10, dtype=torch.bool),
                tick=0,
                adjustment=adjustment,
            )

    def test_quality_gated_checkpoint_selection_is_strict_and_ranked(self):
        from mindustry_agents.training.ppo_selector import (
            _dev_checkpoint_selection_policy,
            _select_dev_checkpoint_index,
        )

        policy = _dev_checkpoint_selection_policy(
            {
                "dev_checkpoint_selection": {
                    "schema": "quality_gate_v1",
                    "minimum_wins": 9,
                    "maximum_mean_idle_fraction_exclusive": 0.25,
                    "ranking": [
                        "wins_desc",
                        "mean_return_desc",
                        "mean_core_health_desc",
                        "update_asc",
                    ],
                }
            }
        )
        rows = [
            {
                "update": 1,
                "wins": 10,
                "mean_return": 10.0,
                "mean_core_health": 1000.0,
                "mean_idle_fraction": 0.25,
            },
            {
                "update": 2,
                "wins": 9,
                "mean_return": 8.0,
                "mean_core_health": 900.0,
                "mean_idle_fraction": 0.20,
            },
            {
                "update": 3,
                "wins": 10,
                "mean_return": 7.0,
                "mean_core_health": 950.0,
                "mean_idle_fraction": 0.24,
            },
        ]
        self.assertEqual(_select_dev_checkpoint_index(rows, policy), 2)
        self.assertEqual(_select_dev_checkpoint_index(rows, None), 0)

    def test_scripted_partner_opening_is_validated_and_legacy_optional(self):
        from mindustry_agents.training.ppo_selector import (
            _scripted_partner_opening,
        )

        self.assertIsNone(_scripted_partner_opening({}))
        opening = {
            "schema": "fixed_seat_initial_task_type_v1",
            "tick": 0,
            "agent_id": 2,
            "task_type": "HARVEST_RESOURCE",
        }
        self.assertEqual(
            _scripted_partner_opening({"scripted_partner_opening": opening}),
            opening,
        )
        invalid = (
            opening | {"schema": "unknown"},
            opening | {"tick": -1},
            opening | {"agent_id": 0},
            opening | {"task_type": ""},
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                _scripted_partner_opening({"scripted_partner_opening": value})

    def test_partner_intent_duplication_risk_is_exact_and_legacy_optional(self):
        from mindustry_agents.training.ppo_selector import (
            _partner_intent_duplication_risk,
        )

        self.assertIsNone(_partner_intent_duplication_risk({}))
        intervention = {
            "schema": "fixed_partner_selected_task_duplication_risk_v1",
            "agent_ids": [1, 2],
            "match": "task_id",
            "feature": "utility_features.duplication_risk",
            "value": 1.0,
        }
        self.assertEqual(
            _partner_intent_duplication_risk(
                {"partner_intent_duplication_risk": intervention}
            ),
            intervention,
        )
        invalid = (
            "invalid",
            intervention | {"schema": "unknown"},
            intervention | {"agent_ids": [2, 1]},
            intervention | {"agent_ids": [1, True]},
            intervention | {"agent_ids": [True, 2]},
            intervention | {"match": "candidate_index"},
            intervention | {"feature": "utility_features.urgency"},
            intervention | {"value": True},
            intervention | {"value": 1},
            intervention | {"value": float("nan")},
            intervention | {"value": 0.5},
            intervention | {"extra": "not-allowed"},
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "partner_intent_duplication_risk"
            ):
                _partner_intent_duplication_risk(
                    {"partner_intent_duplication_risk": value}
                )

    def test_partner_intent_teacher_conflict_filter_is_exact_and_dependent(self):
        from mindustry_agents.training.ppo_selector import (
            _partner_intent_teacher_conflict_filter,
        )

        risk = {
            "schema": "fixed_partner_selected_task_duplication_risk_v1",
            "agent_ids": [1, 2],
            "match": "task_id",
            "feature": "utility_features.duplication_risk",
            "value": 1.0,
        }
        conflict_filter = {
            "schema": "partner_intent_teacher_conflict_filter_v1",
            "match": "teacher_action_index_in_risk_candidate_indices",
            "applies_to": [
                "teacher_warmup",
                "teacher_rehearsal",
                "ppo_teacher_imitation",
            ],
        }
        self.assertIsNone(_partner_intent_teacher_conflict_filter({}))
        config = {
            "partner_intent_duplication_risk": risk,
            "partner_intent_teacher_conflict_filter": conflict_filter,
        }
        self.assertEqual(
            _partner_intent_teacher_conflict_filter(config), conflict_filter
        )
        invalid = (
            "invalid",
            conflict_filter | {"schema": "unknown"},
            conflict_filter | {"match": "task_type"},
            conflict_filter
            | {"applies_to": conflict_filter["applies_to"][:-1]},
            conflict_filter | {"extra": True},
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "partner_intent_teacher_conflict_filter"
            ):
                _partner_intent_teacher_conflict_filter(
                    config | {"partner_intent_teacher_conflict_filter": value}
                )
        with self.assertRaisesRegex(ValueError, "requires"):
            _partner_intent_teacher_conflict_filter(
                {"partner_intent_teacher_conflict_filter": conflict_filter}
            )

    def test_fixed_partner_intended_task_ids_are_structured_and_fail_closed(self):
        from mindustry_agents.training.ppo_selector import (
            _fixed_partner_intended_task_ids,
            _partner_intent_duplication_risk,
        )

        intervention = _partner_intent_duplication_risk(
            {
                "partner_intent_duplication_risk": {
                    "schema": "fixed_partner_selected_task_duplication_risk_v1",
                    "agent_ids": [1, 2],
                    "match": "task_id",
                    "feature": "utility_features.duplication_risk",
                    "value": 1.0,
                }
            }
        )
        actions = [
            {"agent_id": 0, "task_action": {"type": "WAIT"}},
            {
                "agent_id": 1,
                "task_action": {
                    "type": "SELECT_CANDIDATE_TASK",
                    "candidate_index": 0,
                },
            },
            {
                "agent_id": 2,
                "task_action": {
                    "type": "SELECT_CANDIDATE_TASK",
                    "candidate_index": 1,
                },
            },
        ]
        observations = [
            {"task_candidates": []},
            {"task_candidates": [{"task_id": "supply:alpha"}]},
            {
                "task_candidates": [
                    {"task_id": "harvest:beta"},
                    {"task_id": "build:gamma"},
                ]
            },
        ]
        original_actions = deepcopy(actions)
        original_observations = deepcopy(observations)
        self.assertEqual(
            _fixed_partner_intended_task_ids(
                actions, observations, intervention
            ),
            ("supply:alpha", "build:gamma"),
        )
        self.assertEqual(actions, original_actions)
        self.assertEqual(observations, original_observations)
        self.assertEqual(
            _fixed_partner_intended_task_ids(actions, observations, None), ()
        )

        malformed = (
            actions[:1],
            actions[:1]
            + [{"agent_id": 1, "task_action": {"type": "WAIT"}}]
            + actions[2:],
            actions[:1]
            + [
                {
                    "agent_id": 1,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": True,
                    },
                }
            ]
            + actions[2:],
            actions[:1]
            + [
                {
                    "agent_id": 1,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": "0",
                    },
                }
            ]
            + actions[2:],
            actions[:1]
            + [
                {
                    "agent_id": 1,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": -1,
                    },
                }
            ]
            + actions[2:],
            actions[:1]
            + [
                {
                    "agent_id": 1,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": 9,
                    },
                }
            ]
            + actions[2:],
            actions[:1]
            + [
                {
                    "agent_id": True,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": 0,
                    },
                }
            ]
            + actions[2:],
            actions[:1]
            + [
                {
                    "agent_id": 2,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": 0,
                    },
                }
            ]
            + actions[2:],
            actions[:1]
            + [
                {
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": 0,
                    },
                }
            ]
            + actions[2:],
        )
        for changed_actions in malformed:
            with self.subTest(actions=changed_actions):
                self.assertNotIn(
                    "supply:alpha",
                    _fixed_partner_intended_task_ids(
                        changed_actions, observations, intervention
                    ),
                )

        for candidate in ({}, {"task_id": ""}, {"task_id": 7}, "not-an-object"):
            changed_observations = deepcopy(observations)
            changed_observations[1]["task_candidates"][0] = candidate
            with self.subTest(candidate=candidate):
                self.assertNotIn(
                    "supply:alpha",
                    _fixed_partner_intended_task_ids(
                        actions, changed_observations, intervention
                    ),
                )

        duplicate_observations = deepcopy(observations)
        duplicate_observations[2]["task_candidates"][1]["task_id"] = "supply:alpha"
        self.assertEqual(
            _fixed_partner_intended_task_ids(
                actions, duplicate_observations, intervention
            ),
            ("supply:alpha",),
        )

    def test_scripted_partner_opening_replaces_only_fixed_seat_at_exact_tick(self):
        from mindustry_agents.training.ppo_selector import (
            _apply_scripted_partner_opening,
            _scripted_partner_opening,
        )

        opening = _scripted_partner_opening(
            {
                "scripted_partner_opening": {
                    "schema": "fixed_seat_initial_task_type_v1",
                    "tick": 0,
                    "agent_id": 2,
                    "task_type": "HARVEST_RESOURCE",
                }
            }
        )
        actions = [
            {"agent_id": agent_id, "task_action": {"type": "WAIT"}}
            for agent_id in range(3)
        ]
        observations = [
            {"task_candidates": []},
            {"task_candidates": []},
            {
                "task_candidates": [
                    {"task_type": "BUILD_LINE", "valid": True},
                    {"task_type": "HARVEST_RESOURCE", "valid": True},
                ]
            },
        ]
        masks = [
            {"candidate_task": []},
            {"candidate_task": []},
            {"candidate_task": [True, True]},
        ]

        legacy, legacy_evidence = _apply_scripted_partner_opening(
            actions, observations, masks, tick=0, opening=None
        )
        self.assertEqual(legacy, actions)
        self.assertIsNone(legacy_evidence)
        later, later_evidence = _apply_scripted_partner_opening(
            actions, observations, masks, tick=1, opening=opening
        )
        self.assertEqual(later, actions)
        self.assertIsNone(later_evidence)

        bundle, evidence = _apply_scripted_partner_opening(
            actions, observations, masks, tick=0, opening=opening
        )
        expected = {
            "agent_id": 2,
            "task_action": {
                "type": "SELECT_CANDIDATE_TASK",
                "candidate_index": 1,
            },
        }
        self.assertEqual(bundle[:2], actions[:2])
        self.assertEqual(bundle[2], expected)
        self.assertEqual(evidence, expected)
        self.assertEqual(actions[2]["task_action"], {"type": "WAIT"})

    def test_scripted_partner_opening_fails_closed_on_candidate_drift(self):
        from mindustry_agents.training.ppo_selector import (
            _apply_scripted_partner_opening,
        )

        opening = {
            "schema": "fixed_seat_initial_task_type_v1",
            "tick": 0,
            "agent_id": 2,
            "task_type": "HARVEST_RESOURCE",
        }
        actions = [
            {"agent_id": agent_id, "task_action": {"type": "WAIT"}}
            for agent_id in range(3)
        ]

        def apply(candidates, candidate_mask):
            return _apply_scripted_partner_opening(
                actions,
                [
                    {"task_candidates": []},
                    {"task_candidates": []},
                    {"task_candidates": candidates},
                ],
                [
                    {"candidate_task": []},
                    {"candidate_task": []},
                    {"candidate_task": candidate_mask},
                ],
                tick=0,
                opening=opening,
            )

        with self.assertRaisesRegex(RuntimeError, "exactly one"):
            apply([{"task_type": "BUILD_LINE", "valid": True}], [True])
        with self.assertRaisesRegex(RuntimeError, "exactly one"):
            apply(
                [
                    {"task_type": "HARVEST_RESOURCE", "valid": True},
                    {"task_type": "HARVEST_RESOURCE", "valid": True},
                ],
                [True, True],
            )
        with self.assertRaisesRegex(RuntimeError, "invalid"):
            apply([{"task_type": "HARVEST_RESOURCE", "valid": False}], [True])
        with self.assertRaisesRegex(RuntimeError, "masked"):
            apply([{"task_type": "HARVEST_RESOURCE", "valid": True}], [False])

    def test_quality_gated_checkpoint_selection_fails_without_eligible_row(self):
        from mindustry_agents.training.ppo_selector import (
            _dev_checkpoint_selection_policy,
            _select_dev_checkpoint_index,
        )

        policy = _dev_checkpoint_selection_policy(
            {
                "dev_checkpoint_selection": {
                    "schema": "quality_gate_v1",
                    "minimum_wins": 9,
                    "maximum_mean_idle_fraction_exclusive": 0.25,
                    "ranking": [
                        "wins_desc",
                        "mean_return_desc",
                        "mean_core_health_desc",
                        "update_asc",
                    ],
                }
            }
        )
        with self.assertRaisesRegex(RuntimeError, "precommitted dev quality gate"):
            _select_dev_checkpoint_index(
                [
                    {
                        "update": 1,
                        "wins": 10,
                        "mean_return": 10.0,
                        "mean_core_health": 1000.0,
                        "mean_idle_fraction": 0.25,
                    }
                ],
                policy,
            )

    def test_rejected_quality_frontier_is_persisted_before_failure(self):
        from mindustry_agents.training.ppo_selector import (
            _write_dev_checkpoint_frontier,
        )

        policy = {
            "schema": "quality_gate_v1",
            "minimum_wins": 9,
            "maximum_mean_idle_fraction_exclusive": 0.25,
            "ranking": [
                "wins_desc",
                "mean_return_desc",
                "mean_core_health_desc",
                "update_asc",
            ],
        }
        rows = [
            {
                "update": 1,
                "wins": 10,
                "mean_return": 10.0,
                "mean_core_health": 1000.0,
                "mean_idle_fraction": 0.25,
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_dir = root / "runs" / "rejected"
            output_dir.mkdir(parents=True)
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "candidate_version": "v-test",
                        "runtime_contract": "test-runtime-v1",
                        "dev_checkpoint_selection": policy,
                    }
                ),
                encoding="utf-8",
            )
            dev_set = {
                "seed_set_id": "dev-test",
                "seed_set_version": 1,
                "split": "dev",
                "seeds": [101, 102],
            }

            with self.assertRaisesRegex(
                RuntimeError, "precommitted dev quality gate"
            ):
                _write_dev_checkpoint_frontier(
                    root,
                    output_dir,
                    config_path,
                    json.loads(config_path.read_text(encoding="utf-8")),
                    dev_set,
                    rows,
                )

            report_path = output_dir / "selector-v1-dev-frontier.json"
            self.assertTrue(report_path.is_file())
            self.assertFalse(
                (output_dir / "selector-v1-dev-frontier.json.tmp").exists()
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["schema"], "selector_dev_checkpoint_frontier_v1")
            self.assertEqual(report["frontier"], rows)
            self.assertEqual(report["dev_seed_set"], dev_set)
            self.assertEqual(report["selection_policy"], policy)
            self.assertEqual(
                report["candidate"],
                {"version": "v-test", "runtime_contract": "test-runtime-v1"},
            )
            self.assertEqual(
                report["result"],
                {
                    "eligible": False,
                    "selected_index": None,
                    "selected_update": None,
                    "reason": "no checkpoint passed the precommitted dev quality gate",
                },
            )

    def test_quality_selection_policy_validation_rejects_rule_drift(self):
        from mindustry_agents.training.ppo_selector import (
            _dev_checkpoint_selection_policy,
        )

        with self.assertRaisesRegex(ValueError, "selection ranking"):
            _dev_checkpoint_selection_policy(
                {
                    "dev_checkpoint_selection": {
                        "schema": "quality_gate_v1",
                        "minimum_wins": 9,
                        "maximum_mean_idle_fraction_exclusive": 0.25,
                        "ranking": ["mean_idle_fraction_asc"],
                    }
                }
            )

    def test_teacher_wait_candidate_maps_to_canonical_wait_action(self):
        from mindustry_agents.training.ppo_selector import (
            _canonical_scripted_action,
            _scripted_index,
        )

        action = {
            "task_action": {
                "type": "SELECT_CANDIDATE_TASK",
                "candidate_index": 2,
            }
        }
        candidates = [
            {"task_type": "HARVEST_RESOURCE"},
            {"task_type": "BUILD_LINE"},
            {"task_type": "WAIT"},
        ]

        self.assertEqual(_scripted_index(action, candidates), 9)
        self.assertEqual(_scripted_index(action), 2)
        self.assertEqual(
            _canonical_scripted_action(action, candidates),
            {"agent_id": 0, "task_action": {"type": "WAIT"}},
        )

    def test_selected_candidate_diagnostics_are_bounded_and_behavior_neutral(self):
        from mindustry_agents.training.ppo_selector import (
            _selected_candidate_diagnostics,
        )

        candidate = {
            "task_type": "SUPPLY_TURRET",
            "target": "entity #75",
            "estimated_cost": {"copper": 15},
            "utility_features": {
                "resource_cost": 0.75,
                "urgency": 0.9,
                "switching_cost": 0.2,
            },
            "semantic_task_active": True,
        }
        self.assertEqual(
            _selected_candidate_diagnostics([candidate], 0),
            {
                "candidate_index": 0,
                "task_type": "SUPPLY_TURRET",
                "target": "entity #75",
                "resource_cost": 0.75,
                "urgency": 0.9,
                "switching_cost": 0.2,
                "estimated_copper": 15,
                "semantic_task_active": True,
            },
        )
        self.assertIsNone(_selected_candidate_diagnostics([candidate], 9))

    def test_gae_lambda_decay_depends_on_elapsed_ticks_not_boundary_count(self):
        import torch

        from mindustry_agents.training.ppo_selector import (
            EpisodeRollout,
            Transition,
            _advantages,
        )

        def transition(ticks, reward=0.0, done=False):
            return Transition(
                candidates=torch.zeros((8, 37)),
                scalars=torch.zeros(56),
                candidate_present=torch.zeros(8, dtype=torch.bool),
                action_mask=torch.ones(10, dtype=torch.bool),
                action=9,
                old_log_prob=0.0,
                old_value=0.0,
                reward=reward,
                advanced_ticks=ticks,
                done=done,
                policy_loss_mask=False,
            )

        def rollout(transitions):
            return EpisodeRollout(
                seed=1,
                outcome="win",
                tick=61,
                core_health=1.0,
                transitions=transitions,
                reward_components={},
                trace=[],
                coordination_metrics={},
            )

        config = {"gamma_per_second": 0.99, "gae_lambda": 0.95}
        _, whole, _ = _advantages(
            [rollout([transition(60), transition(1, reward=1.0, done=True)])],
            config,
        )
        _, chunked, _ = _advantages(
            [
                rollout(
                    [
                        transition(30),
                        transition(30),
                        transition(1, reward=1.0, done=True),
                    ]
                )
            ],
            config,
        )

        self.assertAlmostEqual(float(whole[0]), float(chunked[0]), places=6)

    def test_success_imitation_uses_only_unforced_winning_transitions(self):
        import torch

        from mindustry_agents.training.model import SelectorActorCritic
        from mindustry_agents.training.ppo_selector import (
            EpisodeRollout,
            Transition,
            ppo_update,
        )

        def transition(successful, policy_loss_mask=True):
            return Transition(
                candidates=torch.zeros((8, 37)),
                scalars=torch.zeros(56),
                candidate_present=torch.zeros(8, dtype=torch.bool),
                action_mask=torch.ones(10, dtype=torch.bool),
                action=9,
                old_log_prob=0.0,
                old_value=0.0,
                reward=1.0,
                advanced_ticks=60,
                done=True,
                policy_loss_mask=policy_loss_mask,
                successful_episode=successful,
            )

        def rollout(item):
            return EpisodeRollout(
                seed=1,
                outcome="win" if item.successful_episode else "loss",
                tick=60,
                core_health=1.0,
                transitions=[item],
                reward_components={},
                trace=[],
                coordination_metrics={},
            )

        model = SelectorActorCritic(1)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0)
        config = {
            "gamma_per_second": 0.99,
            "gae_lambda": 0.95,
            "minibatch_size": 3,
            "ppo_epochs": 1,
            "clip_ratio": 0.2,
            "value_coefficient": 0.5,
            "entropy_coefficient": 0.0,
            "success_imitation_coefficient": 0.1,
            "max_grad_norm": 0.5,
        }
        metrics = ppo_update(
            model,
            optimizer,
            [
                rollout(transition(True)),
                rollout(transition(False)),
                rollout(transition(True, policy_loss_mask=False)),
            ],
            config,
            torch.Generator().manual_seed(3),
        )

        self.assertEqual(metrics["success_imitation_samples"], 1.0)
        self.assertGreater(metrics["success_imitation_loss"], 0.0)

    def test_successful_teacher_imitation_uses_teacher_action(self):
        import torch

        from mindustry_agents.training.model import SelectorActorCritic
        from mindustry_agents.training.ppo_selector import (
            EpisodeRollout,
            Transition,
            ppo_update,
        )

        transition = Transition(
            candidates=torch.zeros((8, 37)),
            scalars=torch.zeros(56),
            candidate_present=torch.zeros(8, dtype=torch.bool),
            action_mask=torch.ones(10, dtype=torch.bool),
            action=9,
            old_log_prob=0.0,
            old_value=0.0,
            reward=1.0,
            advanced_ticks=60,
            done=True,
            policy_loss_mask=True,
            successful_episode=True,
            teacher_action=0,
        )
        episode = EpisodeRollout(
            seed=1,
            outcome="win",
            tick=60,
            core_health=1.0,
            transitions=[transition],
            reward_components={},
            trace=[],
            coordination_metrics={},
        )
        model = SelectorActorCritic(1)
        with torch.no_grad():
            _, logits, _ = model(
                transition.candidates[None, :],
                transition.scalars[None, :],
                transition.candidate_present[None, :],
                transition.action_mask[None, :],
            )
            expected = -torch.log_softmax(logits, dim=-1)[0, 0].item()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0)
        config = {
            "gamma_per_second": 0.99,
            "gae_lambda": 0.95,
            "minibatch_size": 1,
            "ppo_epochs": 1,
            "clip_ratio": 0.2,
            "value_coefficient": 0.5,
            "entropy_coefficient": 0.0,
            "success_imitation_coefficient": 0.0,
            "successful_teacher_imitation_coefficient": 0.05,
            "max_grad_norm": 0.5,
        }

        metrics = ppo_update(
            model,
            optimizer,
            [episode],
            config,
            torch.Generator().manual_seed(3),
        )

        self.assertEqual(metrics["successful_teacher_imitation_samples"], 1.0)
        self.assertAlmostEqual(
            metrics["successful_teacher_imitation_loss"], expected, places=6
        )

        biased_model = SelectorActorCritic(1)
        transition.policy_logit_bias = torch.tensor([1.0] + [0.0] * 9)
        with torch.no_grad():
            _, biased_logits, _ = biased_model(
                transition.candidates[None, :],
                transition.scalars[None, :],
                transition.candidate_present[None, :],
                transition.action_mask[None, :],
            )
            biased_expected = -torch.log_softmax(
                biased_logits + transition.policy_logit_bias[None, :], dim=-1
            )[0, 0].item()
        biased_metrics = ppo_update(
            biased_model,
            torch.optim.Adam(biased_model.parameters(), lr=0.0),
            [episode],
            config,
            torch.Generator().manual_seed(3),
        )
        self.assertAlmostEqual(
            biased_metrics["successful_teacher_imitation_loss"],
            biased_expected,
            places=6,
        )

    def test_full_teacher_imitation_includes_losing_unforced_transition(self):
        import torch

        from mindustry_agents.training.model import SelectorActorCritic
        from mindustry_agents.training.ppo_selector import (
            EpisodeRollout,
            Transition,
            ppo_update,
        )

        transition = Transition(
            candidates=torch.zeros((8, 37)),
            scalars=torch.zeros(56),
            candidate_present=torch.zeros(8, dtype=torch.bool),
            action_mask=torch.ones(10, dtype=torch.bool),
            action=9,
            old_log_prob=0.0,
            old_value=0.0,
            reward=-1.0,
            advanced_ticks=60,
            done=True,
            policy_loss_mask=True,
            successful_episode=False,
            teacher_action=0,
        )
        episode = EpisodeRollout(
            seed=1,
            outcome="loss",
            tick=60,
            core_health=0.0,
            transitions=[transition],
            reward_components={},
            trace=[],
            coordination_metrics={},
        )
        model = SelectorActorCritic(1)
        with torch.no_grad():
            _, logits, _ = model(
                transition.candidates[None, :],
                transition.scalars[None, :],
                transition.candidate_present[None, :],
                transition.action_mask[None, :],
            )
            expected = -torch.log_softmax(logits, dim=-1)[0, 0].item()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0)
        config = {
            "gamma_per_second": 0.99,
            "gae_lambda": 0.95,
            "minibatch_size": 1,
            "ppo_epochs": 1,
            "clip_ratio": 0.2,
            "value_coefficient": 0.5,
            "entropy_coefficient": 0.0,
            "success_imitation_coefficient": 0.0,
            "successful_teacher_imitation_coefficient": 0.0,
            "teacher_imitation_coefficient": 1.0,
            "max_grad_norm": 0.5,
        }

        metrics = ppo_update(
            model,
            optimizer,
            [episode],
            config,
            torch.Generator().manual_seed(3),
        )

        self.assertEqual(metrics["teacher_imitation_samples"], 1.0)
        self.assertEqual(metrics["successful_teacher_imitation_samples"], 0.0)
        self.assertAlmostEqual(metrics["teacher_imitation_loss"], expected, places=6)

        del config["teacher_imitation_coefficient"]
        metrics = ppo_update(
            model,
            optimizer,
            [episode],
            config,
            torch.Generator().manual_seed(3),
        )
        self.assertEqual(metrics["teacher_imitation_samples"], 0.0)
        self.assertEqual(metrics["teacher_imitation_loss"], 0.0)

    def test_teacher_trajectory_warmup_is_ce_only_and_deterministic(self):
        import torch

        from mindustry_agents.training.model import SelectorActorCritic
        from mindustry_agents.training.ppo_selector import (
            EpisodeRollout,
            Transition,
            _model_state_digest,
            teacher_trajectory_rehearsal_update,
            teacher_trajectory_warmup_update,
        )

        transition = Transition(
            candidates=torch.zeros((8, 37)),
            scalars=torch.zeros(56),
            candidate_present=torch.zeros(8, dtype=torch.bool),
            action_mask=torch.ones(10, dtype=torch.bool),
            action=0,
            old_log_prob=0.0,
            old_value=0.0,
            reward=0.0,
            advanced_ticks=60,
            done=True,
            policy_loss_mask=True,
            teacher_action=0,
        )
        episode = EpisodeRollout(
            seed=1,
            outcome="win",
            tick=60,
            core_health=1.0,
            transitions=[transition],
            reward_components={},
            trace=[],
            coordination_metrics={},
        )
        losing_episode = EpisodeRollout(
            seed=2,
            outcome="loss",
            tick=60,
            core_health=0.0,
            transitions=[transition],
            reward_components={},
            trace=[],
            coordination_metrics={},
        )
        config = {
            "teacher_warmup_cycles": 1,
            "teacher_warmup_epochs": 2,
            "teacher_warmup_minibatch_size": 1,
            "teacher_warmup_success_only": True,
            "teacher_warmup_shuffle_seed": 16,
            "teacher_warmup_minibatch_seed": 17,
            "max_grad_norm": 0.5,
        }
        models = [SelectorActorCritic(9), SelectorActorCritic(9)]
        before = _model_state_digest(models[0].state_dict())
        results = []
        for model in models:
            optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
            results.append(
                teacher_trajectory_warmup_update(
                    model,
                    optimizer,
                    [episode, losing_episode],
                    config,
                    torch.Generator().manual_seed(17),
                )
            )
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0]["schema"], "teacher_trajectory_warmup_v1")
        self.assertEqual(results[0]["samples"], 2)
        self.assertEqual(results[0]["unique_transitions"], 1)
        self.assertEqual(results[0]["eligible_episodes"], 1)
        self.assertEqual(results[0]["total_episodes"], 2)
        self.assertTrue(results[0]["success_only"])
        self.assertNotEqual(before, _model_state_digest(models[0].state_dict()))
        self.assertEqual(
            _model_state_digest(models[0].state_dict()),
            _model_state_digest(models[1].state_dict()),
        )
        rehearsal_config = dict(config) | {
            "teacher_rehearsal_epochs_per_update": 1,
            "teacher_rehearsal_minibatch_seed": 18,
        }
        rehearsal_model = SelectorActorCritic(9)
        rehearsal = teacher_trajectory_rehearsal_update(
            rehearsal_model,
            torch.optim.Adam(rehearsal_model.parameters(), lr=1e-3),
            [episode, losing_episode],
            rehearsal_config,
            torch.Generator().manual_seed(18),
        )
        self.assertEqual(rehearsal["schema"], "teacher_trajectory_rehearsal_v1")
        self.assertEqual(rehearsal["epochs"], 1)
        self.assertEqual(rehearsal["samples"], 1)
        self.assertNotIn("samples_per_epoch_cap", rehearsal)

        capped_config = dict(config) | {"teacher_warmup_samples_per_epoch": 2}
        capped_episode = EpisodeRollout(
            seed=3,
            outcome="win",
            tick=60,
            core_health=1.0,
            transitions=[transition, transition, transition],
            reward_components={},
            trace=[],
            coordination_metrics={},
        )
        capped_results = []
        for model in [SelectorActorCritic(10), SelectorActorCritic(10)]:
            capped_results.append(
                teacher_trajectory_warmup_update(
                    model,
                    torch.optim.Adam(model.parameters(), lr=1e-3),
                    [capped_episode],
                    capped_config,
                    torch.Generator().manual_seed(17),
                )
            )
        self.assertEqual(capped_results[0], capped_results[1])
        self.assertEqual(capped_results[0]["samples"], 4)
        self.assertEqual(capped_results[0]["samples_per_epoch_cap"], 2)
        self.assertEqual(
            [
                len(order)
                for order in capped_results[0][
                    "sampled_transition_indices_by_epoch"
                ]
            ],
            [2, 2],
        )
        self.assertEqual(
            capped_results[0]["sampled_unique_transitions"],
            len(
                {
                    index
                    for order in capped_results[0][
                        "sampled_transition_indices_by_epoch"
                    ]
                    for index in order
                }
            ),
        )
        capped_rehearsal_model = SelectorActorCritic(11)
        capped_rehearsal = teacher_trajectory_rehearsal_update(
            capped_rehearsal_model,
            torch.optim.Adam(capped_rehearsal_model.parameters(), lr=1e-3),
            [capped_episode],
            dict(config)
            | {
                "teacher_rehearsal_epochs_per_update": 1,
                "teacher_rehearsal_minibatch_seed": 18,
                "teacher_rehearsal_samples_per_epoch": 2,
            },
            torch.Generator().manual_seed(18),
        )
        self.assertEqual(capped_rehearsal["samples"], 2)
        self.assertEqual(capped_rehearsal["samples_per_epoch_cap"], 2)
        self.assertEqual(
            [
                len(order)
                for order in capped_rehearsal[
                    "sampled_transition_indices_by_epoch"
                ]
            ],
            [2],
        )
        biased_transition = Transition(
            candidates=transition.candidates,
            scalars=transition.scalars,
            candidate_present=transition.candidate_present,
            action_mask=transition.action_mask,
            action=transition.action,
            old_log_prob=transition.old_log_prob,
            old_value=transition.old_value,
            reward=transition.reward,
            advanced_ticks=transition.advanced_ticks,
            done=transition.done,
            policy_loss_mask=transition.policy_loss_mask,
            teacher_action=transition.teacher_action,
            policy_logit_bias=torch.tensor([1.0] + [0.0] * 9),
        )
        biased_episode = EpisodeRollout(
            seed=4,
            outcome="win",
            tick=60,
            core_health=1.0,
            transitions=[biased_transition],
            reward_components={},
            trace=[],
            coordination_metrics={},
        )
        biased_model = SelectorActorCritic(12)
        with torch.no_grad():
            _, biased_logits, _ = biased_model(
                biased_transition.candidates[None, :],
                biased_transition.scalars[None, :],
                biased_transition.candidate_present[None, :],
                biased_transition.action_mask[None, :],
            )
            biased_expected = -torch.log_softmax(
                biased_logits + biased_transition.policy_logit_bias[None, :],
                dim=-1,
            )[0, 0].item()
        biased_metrics = teacher_trajectory_warmup_update(
            biased_model,
            torch.optim.Adam(biased_model.parameters(), lr=0.0),
            [biased_episode],
            dict(config) | {"teacher_warmup_epochs": 1},
            torch.Generator().manual_seed(17),
        )
        self.assertAlmostEqual(
            biased_metrics["mean_cross_entropy"], biased_expected, places=6
        )
        transition.action_mask[0] = False
        invalid_model = SelectorActorCritic(9)
        with self.assertRaisesRegex(RuntimeError, "masked action"):
            teacher_trajectory_warmup_update(
                invalid_model,
                torch.optim.Adam(invalid_model.parameters(), lr=1e-3),
                [episode],
                config,
                torch.Generator().manual_seed(17),
            )

    def test_teacher_conflict_filter_excludes_only_teacher_ce_paths(self):
        import torch

        from mindustry_agents.training.model import SelectorActorCritic
        from mindustry_agents.training.ppo_selector import (
            EpisodeRollout,
            Transition,
            _model_state_digest,
            ppo_update,
            teacher_trajectory_rehearsal_update,
            teacher_trajectory_warmup_update,
        )

        def transition(*, conflict: bool) -> Transition:
            return Transition(
                candidates=torch.zeros((8, 37)),
                scalars=torch.zeros(56),
                candidate_present=torch.zeros(8, dtype=torch.bool),
                action_mask=torch.ones(10, dtype=torch.bool),
                action=1,
                old_log_prob=0.0,
                old_value=0.0,
                reward=1.0,
                advanced_ticks=60,
                done=True,
                policy_loss_mask=True,
                successful_episode=True,
                teacher_action=0,
                teacher_partner_intent_risk_conflict=conflict,
            )

        episode = EpisodeRollout(
            seed=1,
            outcome="win",
            tick=60,
            core_health=1.0,
            transitions=[transition(conflict=True), transition(conflict=False)],
            reward_components={},
            trace=[],
            coordination_metrics={},
        )
        risk = {
            "schema": "fixed_partner_selected_task_duplication_risk_v1",
            "agent_ids": [1, 2],
            "match": "task_id",
            "feature": "utility_features.duplication_risk",
            "value": 1.0,
        }
        conflict_filter = {
            "schema": "partner_intent_teacher_conflict_filter_v1",
            "match": "teacher_action_index_in_risk_candidate_indices",
            "applies_to": [
                "teacher_warmup",
                "teacher_rehearsal",
                "ppo_teacher_imitation",
            ],
        }
        base = {
            "teacher_warmup_cycles": 1,
            "teacher_warmup_epochs": 2,
            "teacher_warmup_minibatch_size": 2,
            "teacher_warmup_success_only": True,
            "teacher_warmup_shuffle_seed": 16,
            "teacher_warmup_minibatch_seed": 17,
            "teacher_warmup_samples_per_epoch": 1,
            "max_grad_norm": 0.5,
        }
        enabled = base | {
            "partner_intent_duplication_risk": risk,
            "partner_intent_teacher_conflict_filter": conflict_filter,
        }
        results = []
        digests = []
        for seed in (17, 17):
            model = SelectorActorCritic(20)
            results.append(
                teacher_trajectory_warmup_update(
                    model,
                    torch.optim.Adam(model.parameters(), lr=1e-3),
                    [episode],
                    enabled,
                    torch.Generator().manual_seed(seed),
                )
            )
            digests.append(_model_state_digest(model.state_dict()))
        self.assertEqual(results[0], results[1])
        self.assertEqual(digests[0], digests[1])
        evidence = results[0]["teacher_conflict_filter"]
        self.assertEqual(evidence["eligible_transitions"], 2)
        self.assertEqual(evidence["excluded_conflict_transitions"], 1)
        self.assertEqual(evidence["retained_transitions"], 1)
        self.assertEqual(evidence["sampled_conflict_presentations"], 0)
        self.assertEqual(evidence["sampled_retained_presentations"], 2)
        self.assertEqual(
            evidence["sampled_retained_transition_indices_by_epoch"], [[1], [1]]
        )

        rehearsal_config = enabled | {
            "teacher_rehearsal_epochs_per_update": 1,
            "teacher_rehearsal_minibatch_seed": 18,
            "teacher_rehearsal_samples_per_epoch": 1,
        }
        rehearsal_model = SelectorActorCritic(21)
        rehearsal = teacher_trajectory_rehearsal_update(
            rehearsal_model,
            torch.optim.Adam(rehearsal_model.parameters(), lr=0.0),
            [episode],
            rehearsal_config,
            torch.Generator().manual_seed(18),
        )
        self.assertEqual(
            rehearsal["teacher_conflict_filter"]["excluded_conflict_transitions"],
            1,
        )
        self.assertEqual(rehearsal["samples"], 1)

        legacy_model = SelectorActorCritic(23)
        legacy_copy = SelectorActorCritic(23)
        legacy = teacher_trajectory_warmup_update(
            legacy_model,
            torch.optim.Adam(legacy_model.parameters(), lr=1e-3),
            [episode],
            base,
            torch.Generator().manual_seed(17),
        )
        no_conflict_episode = deepcopy(episode)
        for item in no_conflict_episode.transitions:
            item.teacher_partner_intent_risk_conflict = False
        legacy_no_conflict = teacher_trajectory_warmup_update(
            legacy_copy,
            torch.optim.Adam(legacy_copy.parameters(), lr=1e-3),
            [no_conflict_episode],
            base,
            torch.Generator().manual_seed(17),
        )
        self.assertEqual(legacy, legacy_no_conflict)
        self.assertEqual(
            _model_state_digest(legacy_model.state_dict()),
            _model_state_digest(legacy_copy.state_dict()),
        )
        self.assertNotIn("teacher_conflict_filter", legacy)

        ppo_base = {
            "gamma_per_second": 0.99,
            "gae_lambda": 0.95,
            "minibatch_size": 2,
            "ppo_epochs": 1,
            "clip_ratio": 0.2,
            "value_coefficient": 0.5,
            "entropy_coefficient": 0.0,
            "success_imitation_coefficient": 0.0,
            "successful_teacher_imitation_coefficient": 0.0,
            "teacher_imitation_coefficient": 1.0,
            "max_grad_norm": 0.5,
        }
        unfiltered_model = SelectorActorCritic(24)
        filtered_model = SelectorActorCritic(24)
        unfiltered = ppo_update(
            unfiltered_model,
            torch.optim.Adam(unfiltered_model.parameters(), lr=0.0),
            [episode],
            ppo_base,
            torch.Generator().manual_seed(19),
        )
        filtered = ppo_update(
            filtered_model,
            torch.optim.Adam(filtered_model.parameters(), lr=0.0),
            [episode],
            ppo_base
            | {
                "partner_intent_duplication_risk": risk,
                "partner_intent_teacher_conflict_filter": conflict_filter,
            },
            torch.Generator().manual_seed(19),
        )
        self.assertEqual(unfiltered["teacher_imitation_samples"], 2.0)
        self.assertEqual(filtered["teacher_imitation_samples"], 1.0)
        self.assertEqual(filtered["teacher_imitation_eligible_samples"], 2.0)
        self.assertEqual(
            filtered["teacher_imitation_excluded_conflict_samples"], 1.0
        )
        self.assertEqual(filtered["policy_loss"], unfiltered["policy_loss"])
        self.assertEqual(filtered["value_loss"], unfiltered["value_loss"])
        self.assertEqual(filtered["entropy"], unfiltered["entropy"])
        self.assertEqual(
            filtered["successful_teacher_imitation_samples"],
            unfiltered["successful_teacher_imitation_samples"],
        )

    def test_teacher_warmup_report_is_atomic_and_reproducibility_evidence(self):
        from mindustry_agents.training.ppo_selector import (
            _reproducibility_evidence,
            _write_teacher_rehearsal_report,
            _write_teacher_warmup_report,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_dir = root / "runs" / "warmup"
            output_dir.mkdir(parents=True)
            config_path = root / "config.json"
            config = {
                "teacher_warmup_cycles": 1,
                "teacher_warmup_epochs": 8,
                "teacher_warmup_minibatch_size": 128,
                "teacher_warmup_success_only": True,
                "teacher_warmup_shuffle_seed": 41,
                "teacher_warmup_minibatch_seed": 42,
                "teacher_rehearsal_epochs_per_update": 1,
                "teacher_rehearsal_minibatch_seed": 43,
                "teacher_warmup_samples_per_epoch": 121,
                "teacher_rehearsal_samples_per_epoch": 121,
            }
            config_path.write_text(json.dumps(config), encoding="utf-8")
            path, report = _write_teacher_warmup_report(
                root,
                output_dir,
                config_path,
                config,
                {
                    "seed_set_id": "train-v1",
                    "seed_set_version": 1,
                    "split": "train",
                },
                [11, 12],
                [
                    {
                        "outcome": "win",
                        "policy_decisions": 1,
                        "trace_digest": "teacher-trace",
                    }
                ],
                {"schema": "teacher_trajectory_warmup_v1", "samples": 8},
                "initial-model",
                "warm-model",
            )
            self.assertTrue(path.is_file())
            self.assertFalse(path.with_suffix(".json.tmp").exists())
            self.assertEqual(report["wins"], 1)
            self.assertEqual(report["initial_model_state_sha256"], "initial-model")
            self.assertEqual(
                report["post_warmup_model_state_sha256"], "warm-model"
            )
            self.assertEqual(report["configuration"]["teacher_warmup_cycles"], 1)
            self.assertEqual(
                report["configuration"]["teacher_warmup_samples_per_epoch"], 121
            )
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")), report
            )

            rehearsal_path, rehearsal_report = _write_teacher_rehearsal_report(
                root,
                output_dir,
                config_path,
                config,
                path,
                report["episodes"],
                [
                    {
                        "update": 1,
                        "schema": "teacher_trajectory_rehearsal_v1",
                        "samples": 1,
                    }
                ],
                "rehearsed-model",
            )
            self.assertTrue(rehearsal_path.is_file())
            self.assertFalse(rehearsal_path.with_suffix(".json.tmp").exists())
            self.assertEqual(rehearsal_report["updates"], 1)
            self.assertEqual(
                rehearsal_report["configuration"][
                    "teacher_rehearsal_samples_per_epoch"
                ],
                121,
            )
            self.assertEqual(rehearsal_report["corpus"]["unique_transitions"], 1)
            self.assertEqual(
                rehearsal_report["source_warmup_report"]["sha256"],
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )

            manifest = self._repro_manifest()
            manifest["teacher_warmup"] = report
            manifest["teacher_rehearsal"] = rehearsal_report
            first = _reproducibility_evidence(manifest)
            manifest["teacher_rehearsal"] = dict(rehearsal_report) | {
                "post_rehearsal_model_state_sha256": "changed"
            }
            second = _reproducibility_evidence(manifest)
            self.assertNotEqual(first, second)

    def test_checkpoint_requires_exact_schema_match(self):
        import torch

        from mindustry_agents.training.model import SelectorActorCritic
        from mindustry_agents.training.ppo_selector import load_checkpoint

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.pt"
            torch.save(
                {
                    "feature_schema": "wrong",
                    "reward_schema": "selector_reward_v1",
                    "model_schema": "selector_actor_critic_v1",
                    "model_state": SelectorActorCritic(1).state_dict(),
                },
                path,
            )
            with self.assertRaisesRegex(ValueError, "schema mismatch"):
                load_checkpoint(path, SelectorActorCritic(1))

            v2 = Path(directory) / "v2.pt"
            state = SelectorActorCritic(1).state_dict()
            torch.save(
                {
                    "feature_schema": "selector_features_v1",
                    "reward_schema": "selector_reward_v2",
                    "model_schema": "selector_actor_critic_v1",
                    "model_state": state,
                },
                v2,
            )
            with self.assertRaisesRegex(ValueError, "schema mismatch"):
                load_checkpoint(v2, SelectorActorCritic(1))
            load_checkpoint(
                v2,
                SelectorActorCritic(1),
                reward_schema="selector_reward_v2",
            )

    def test_model_state_digest_is_stable_and_weight_sensitive(self):
        from mindustry_agents.training.model import SelectorActorCritic
        from mindustry_agents.training.ppo_selector import _model_state_digest

        self.assertEqual(
            _model_state_digest(SelectorActorCritic(1).state_dict()),
            _model_state_digest(SelectorActorCritic(1).state_dict()),
        )
        self.assertNotEqual(
            _model_state_digest(SelectorActorCritic(1).state_dict()),
            _model_state_digest(SelectorActorCritic(2).state_dict()),
        )

    def test_full_run_manifest_comparison_detects_divergence(self):
        from mindustry_agents.training.ppo_selector import (
            _json_digest,
            _legacy_reproducibility_evidence,
            _reproducibility_evidence,
            compare_run_manifests,
        )

        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            first.write_text(json.dumps(self._repro_manifest()), encoding="utf-8")
            second.write_text(json.dumps(self._repro_manifest()), encoding="utf-8")
            compare_run_manifests(first, second)

            second.write_text(
                json.dumps(self._repro_manifest("trace-b")), encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "diverged"):
                compare_run_manifests(first, second)

            replicas = [self._repro_manifest(), self._repro_manifest()]
            for index, manifest in enumerate(replicas):
                manifest["teacher_rehearsal"] = {
                    "source_warmup_report": {
                        "path": f"runs/replica-{index}/teacher-warmup.json",
                        "sha256": "warmup-report",
                    },
                    "post_rehearsal_model_state_sha256": "rehearsed-model",
                }
                manifest["full_run_reproducibility"]["digest"] = _json_digest(
                    _legacy_reproducibility_evidence(manifest)
                )
            first.write_text(json.dumps(replicas[0]), encoding="utf-8")
            second.write_text(json.dumps(replicas[1]), encoding="utf-8")
            self.assertEqual(
                _reproducibility_evidence(replicas[0]),
                _reproducibility_evidence(replicas[1]),
            )
            compare_run_manifests(first, second)

    def test_quality_selection_frontier_is_reproducibility_evidence(self):
        from mindustry_agents.training.ppo_selector import _reproducibility_evidence

        manifest = self._repro_manifest()
        manifest["dev_checkpoint_selection_policy"] = {
            "schema": "quality_gate_v1",
            "minimum_wins": 9,
            "maximum_mean_idle_fraction_exclusive": 0.25,
            "ranking": [
                "wins_desc",
                "mean_return_desc",
                "mean_core_health_desc",
                "update_asc",
            ],
        }
        manifest["dev_checkpoint_selection"][0]["mean_idle_fraction"] = 0.24
        first = _reproducibility_evidence(manifest)
        manifest["dev_checkpoint_selection"][0]["mean_idle_fraction"] = 0.23
        second = _reproducibility_evidence(manifest)
        self.assertNotEqual(first, second)
        self.assertNotIn(
            "dev_checkpoint_selection_policy",
            _reproducibility_evidence(self._repro_manifest()),
        )

    def test_episode_summary_hashes_action_state_not_inference_diagnostics(self):
        from mindustry_agents.training.ppo_selector import (
            EpisodeRollout,
            _episode_summary,
        )

        base = {
            "tick": 10,
            "advanced_ticks": 20,
            "action": {"type": "WAIT"},
            "agent_actions": [],
            "action_index": 9,
            "policy_loss_mask": True,
            "reward_components": {"reward.team.unresolved_tick_cost": -0.1},
            "boundary_reasons": ["task_terminal"],
            "state_hash": "abc",
            "outcome": "running",
            "raw_logits": [1.0],
            "masked_logits": [1.0],
            "log_probability": -0.5,
            "value_prediction": 0.25,
            "task_events": [],
        }
        changed = dict(base)
        changed.update(
            raw_logits=[1.0000001],
            masked_logits=[1.0000001],
            log_probability=-0.5000001,
            value_prediction=0.2500001,
            teacher_candidate_diagnostics={"task_type": "SUPPLY_TURRET"},
            fixed_partner_intended_task_ids=["supply:alpha"],
            partner_intent_duplication_risk_candidate_indices=[0],
            task_events=[{"message_id": 1}],
        )

        def summary(trace):
            rollout = EpisodeRollout(
                seed=1,
                outcome="running",
                tick=30,
                core_health=1000.0,
                transitions=[],
                reward_components={},
                trace=[trace],
                coordination_metrics={},
            )
            return _episode_summary(rollout)

        self.assertEqual(summary(base)["trace_digest"], summary(changed)["trace_digest"])


if __name__ == "__main__":
    unittest.main()
