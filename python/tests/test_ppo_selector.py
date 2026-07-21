import importlib.util
import json
import tempfile
import unittest
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
        from mindustry_agents.training.ppo_selector import compare_run_manifests

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
