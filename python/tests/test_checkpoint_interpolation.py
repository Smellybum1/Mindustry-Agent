import importlib.util
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock


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

    def test_reward_schema_defaults_legacy_and_resolves_v41(self):
        from mindustry_agents.process.launcher import repo_root
        from mindustry_agents.training.checkpoint_interpolation import (
            REWARD_SCHEMA,
            REWARD_SCHEMA_V2,
            _reward_schema,
        )

        self.assertEqual(_reward_schema({}), REWARD_SCHEMA)
        v41 = json.loads(
            (
                repo_root()
                / "configs/training/"
                "m8-selector-v41-adjacent-frontier-midpoint.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(_reward_schema(v41), REWARD_SCHEMA_V2)

    def test_reward_schema_rejects_unsupported_values(self):
        from mindustry_agents.training.checkpoint_interpolation import (
            _reward_schema,
        )

        with self.assertRaisesRegex(
            ValueError, "unsupported interpolation reward schema"
        ):
            _reward_schema({"reward_schema": "selector_reward_v999"})

    def test_parent_loader_passes_configured_reward_schema(self):
        import mindustry_agents.training.checkpoint_interpolation as interpolation

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            training_config = root / "training.json"
            manifest_path = root / "manifest.json"
            checkpoint_path = root / "checkpoint.pt"
            training_config.write_text(
                json.dumps({"reward_schema": interpolation.REWARD_SCHEMA_V2}),
                encoding="utf-8",
            )
            training_sha256 = interpolation._sha256(training_config)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source_config": {
                            "path": "training.json",
                            "sha256": training_sha256,
                        },
                        "schemas": {"reward": interpolation.REWARD_SCHEMA_V2},
                    }
                ),
                encoding="utf-8",
            )

            with (
                mock.patch.object(
                    interpolation,
                    "_manifest_reproducibility_digest",
                    return_value="manifest-digest",
                ),
                mock.patch.object(interpolation, "SelectorActorCritic"),
                mock.patch.object(
                    interpolation,
                    "load_checkpoint",
                    side_effect=RuntimeError("checkpoint load reached"),
                ) as load_checkpoint,
            ):
                with self.assertRaisesRegex(RuntimeError, "checkpoint load reached"):
                    interpolation._load_parent(
                        root=root,
                        construction={"model_init_seed": 8601},
                        spec={
                            "role": "base",
                            "training_config": "training.json",
                            "update": 26,
                            "weight": 0.5,
                        },
                        checkpoint_path=checkpoint_path,
                        manifest_path=manifest_path,
                        reward_schema=interpolation.REWARD_SCHEMA_V2,
                    )

            self.assertEqual(
                load_checkpoint.call_args.kwargs["reward_schema"],
                interpolation.REWARD_SCHEMA_V2,
            )

    def test_lineage_validator_passes_configured_reward_schema(self):
        import mindustry_agents.training.checkpoint_interpolation as interpolation

        manifest = {
            "schema": interpolation.INTERPOLATION_SCHEMA,
            "source_config": {"sha256": "artifact-sha256"},
            "repository": {"commit": "a" * 40},
            "schemas": {"reward": interpolation.REWARD_SCHEMA_V2},
            "model_init_seed": 8601,
            "parents": [],
            "checkpoint": {
                "sha256": "artifact-sha256",
                "model_state_sha256": "model-state-sha256",
            },
            "lineage_reproducibility": {"digest": "lineage-sha256"},
        }
        checkpoint = {
            "config_sha256": "artifact-sha256",
            "model_state": {},
        }

        with (
            mock.patch.object(
                interpolation,
                "_load_json",
                side_effect=[manifest, {"reward_schema": "selector_reward_v2"}],
            ),
            mock.patch.object(interpolation, "_lineage_evidence", return_value={}),
            mock.patch.object(
                interpolation, "_json_digest", return_value="lineage-sha256"
            ),
            mock.patch.object(
                interpolation, "_sha256", return_value="artifact-sha256"
            ),
            mock.patch.object(
                interpolation,
                "_model_state_digest",
                return_value="model-state-sha256",
            ),
            mock.patch.object(interpolation, "SelectorActorCritic"),
            mock.patch.object(
                interpolation, "load_checkpoint", return_value=checkpoint
            ) as load_checkpoint,
        ):
            interpolation.validate_lineage_manifest(
                manifest_path=Path("lineage.json"),
                config_path=Path("config.json"),
                checkpoint_path=Path("checkpoint.pt"),
            )

        self.assertEqual(
            load_checkpoint.call_args.kwargs["reward_schema"],
            interpolation.REWARD_SCHEMA_V2,
        )

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
