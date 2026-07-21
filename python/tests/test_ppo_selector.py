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
