import importlib.util
import json
import unittest
from dataclasses import replace


@unittest.skipIf(importlib.util.find_spec("torch") is None, "RL extra is not installed")
class TestCheckpointInterpolation(unittest.TestCase):
    @staticmethod
    def _parent(role, weight, state):
        from pathlib import Path

        from mindustry_agents.training.checkpoint_interpolation import ParentEvidence

        return ParentEvidence(
            role=role,
            weight=weight,
            update=2,
            checkpoint_path=Path("checkpoint.pt"),
            checkpoint_sha256="checkpoint",
            checkpoint_model_state_sha256="model",
            manifest_path=Path("manifest.json"),
            manifest_sha256="manifest",
            manifest_reproducibility_sha256="run",
            training_config_path=Path("config.json"),
            training_config_sha256="config",
            initial_model_state_sha256="initial",
            repository_commit="commit",
            state=state,
        )

    def test_interpolation_is_ordered_and_exact(self):
        import torch

        from mindustry_agents.training.checkpoint_interpolation import (
            interpolate_model_states,
        )

        base = self._parent(
            "base",
            0.75,
            {
                "float": torch.tensor([0.0, 4.0]),
                "integer": torch.tensor([2], dtype=torch.int64),
            },
        )
        auxiliary = self._parent(
            "auxiliary",
            0.25,
            {
                "float": torch.tensor([4.0, 0.0]),
                "integer": torch.tensor([2], dtype=torch.int64),
            },
        )

        state = interpolate_model_states([base, auxiliary])

        self.assertTrue(torch.equal(state["float"], torch.tensor([1.0, 3.0])))
        self.assertTrue(
            torch.equal(state["integer"], torch.tensor([2], dtype=torch.int64))
        )

    def test_interpolation_rejects_tensor_schema_or_integer_differences(self):
        import torch

        from mindustry_agents.training.checkpoint_interpolation import (
            interpolate_model_states,
        )

        base = self._parent(
            "base", 0.75, {"value": torch.tensor([1], dtype=torch.int64)}
        )
        changed = self._parent(
            "auxiliary", 0.25, {"value": torch.tensor([2], dtype=torch.int64)}
        )
        with self.assertRaisesRegex(ValueError, "non-floating"):
            interpolate_model_states([base, changed])

        wrong_shape = replace(
            changed, state={"value": torch.tensor([1.0, 2.0])}
        )
        float_base = replace(base, state={"value": torch.tensor([1.0])})
        with self.assertRaisesRegex(ValueError, "tensor schema"):
            interpolate_model_states([float_base, wrong_shape])

    def test_config_requires_fixed_parent_order_and_normalized_weights(self):
        from mindustry_agents.training.checkpoint_interpolation import (
            INTERPOLATION_SCHEMA,
            _validate_construction_config,
        )

        config = {
            "schema": INTERPOLATION_SCHEMA,
            "checkpoint_construction": {
                "parents": [
                    {"role": "base", "weight": 0.75, "update": 2},
                    {"role": "auxiliary", "weight": 0.25, "update": 2},
                ]
            },
        }
        self.assertEqual(len(_validate_construction_config(config)), 2)
        config["checkpoint_construction"]["parents"][0][
            "training_repository_commit"
        ] = "a" * 40
        with self.assertRaisesRegex(ValueError, "both full training commits"):
            _validate_construction_config(config)
        config["checkpoint_construction"]["parents"][1][
            "training_repository_commit"
        ] = "b" * 40
        self.assertEqual(len(_validate_construction_config(config)), 2)
        config["checkpoint_construction"]["parents"][1]["weight"] = 0.2
        with self.assertRaisesRegex(ValueError, "sum to 1"):
            _validate_construction_config(config)

    def test_governed_configs_differ_only_by_auxiliary_coefficient(self):
        from mindustry_agents.process.launcher import repo_root

        root = repo_root()
        base = json.loads(
            (root / "configs/training/m8-selector-v2.json").read_text()
        )
        auxiliary = json.loads(
            (
                root / "configs/training/m8-selector-v2-auxiliary.json"
            ).read_text()
        )
        self.assertEqual(base["success_imitation_coefficient"], 0.0)
        self.assertEqual(auxiliary["success_imitation_coefficient"], 0.1)
        for document in (base, auxiliary):
            document.pop("success_imitation_coefficient")
            document["optimizer_ppo"].pop("success_imitation_coefficient")
        self.assertEqual(base, auxiliary)

        construction = json.loads(
            (
                root / "configs/training/m8-selector-v2-interpolation.json"
            ).read_text()
        )["checkpoint_construction"]["parents"]
        self.assertEqual(
            [(item["role"], item["update"], item["weight"]) for item in construction],
            [("base", 2, 0.75), ("auxiliary", 2, 0.25)],
        )

        v7 = json.loads(
            (
                root / "configs/training/m8-selector-v7-interpolation.json"
            ).read_text()
        )
        self.assertEqual(
            v7["held_out_seed_set_id"], "bootstrap-defense-v1-held-out-v2"
        )
        self.assertEqual(
            [
                (item["role"], item["update"], item["weight"])
                for item in v7["checkpoint_construction"]["parents"]
            ],
            [("base", 31, 0.9), ("auxiliary", 5, 0.1)],
        )


if __name__ == "__main__":
    unittest.main()
