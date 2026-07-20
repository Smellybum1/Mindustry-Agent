import importlib.util
import tempfile
import unittest
from pathlib import Path


@unittest.skipIf(importlib.util.find_spec("torch") is None, "RL extra is not installed")
class TestPpoSelector(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
