"""Focused ADR-0075 diverse-root governance tests."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


@unittest.skipIf(importlib.util.find_spec("torch") is None, "RL extra is not installed")
class TestIPPODiverseRoots(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from mindustry_agents.process.launcher import repo_root
        from mindustry_agents.training.ippo_ppo import load_ippo_v3_config

        cls.root = repo_root()
        cls.config = load_ippo_v3_config(
            cls.root / "configs/training/m9-ippo-v3-diverse2048.json"
        )

    def test_v3_config_is_exact_public_only_and_v1_optimizer(self):
        from mindustry_agents.training.ippo_ppo import (
            IPPO_V3_CONFIG_SHA256,
            IPPO_V3_PROTOCOL_SHA256,
            config_sha256,
            protocol_sha256,
        )

        self.assertEqual(
            self.config["candidate_version"], "m9-ippo-v3-diverse2048"
        )
        self.assertEqual(config_sha256(self.config), IPPO_V3_CONFIG_SHA256)
        self.assertEqual(protocol_sha256(self.config), IPPO_V3_PROTOCOL_SHA256)
        self.assertEqual(
            self.config["recurrent_backpropagation"]["schema"],
            "one_boundary_truncation_v1",
        )
        self.assertIsNone(self.config["confirmation_seed_set"])
        self.assertIsNone(self.config["held_out_seed_set"])

    def test_public_root_packet_is_unique_disjoint_and_exact(self):
        from mindustry_agents.training.ippo_diverse_roots import (
            V3_TRAIN_SEED_SHA256,
            validate_diverse_root_packet,
        )

        report = validate_diverse_root_packet(self.root)
        self.assertEqual(report["train_seed_sha256"], V3_TRAIN_SEED_SHA256)
        self.assertEqual(report["root_count"], 2048)
        self.assertEqual(report["unique_root_count"], 2048)
        self.assertEqual(report["root_reuse_count"], 1)
        self.assertEqual(report["v1_train_overlap"], 0)
        self.assertEqual(report["public_dev_overlap"], 0)
        self.assertFalse(report["confirmation_or_held_out_access"])

    def test_schedule_is_deterministic_complete_and_sliced_32_by_64(self):
        from mindustry_agents.training.ippo_train import training_seed_schedule

        train = json.loads(
            (self.root / self.config["train_seed_set"]).read_text(
                encoding="utf-8"
            )
        )
        schedule = training_seed_schedule(train["seeds"], self.config)
        self.assertEqual(len(schedule), 2048)
        self.assertEqual(len(set(schedule)), 2048)
        self.assertEqual(set(schedule), set(train["seeds"]))
        self.assertEqual(
            schedule,
            training_seed_schedule(train["seeds"], self.config),
        )
        updates = [schedule[start : start + 64] for start in range(0, 2048, 64)]
        self.assertEqual(len(updates), 32)
        self.assertTrue(all(len(update) == 64 for update in updates))
        self.assertTrue(
            all(
                set(updates[left]).isdisjoint(updates[right])
                for left in range(32)
                for right in range(left + 1, 32)
            )
        )

    def test_schedule_rejects_duplicate_or_short_membership(self):
        from mindustry_agents.training.ippo_train import training_seed_schedule

        train = json.loads(
            (self.root / self.config["train_seed_set"]).read_text(
                encoding="utf-8"
            )
        )
        with self.assertRaisesRegex(ValueError, "schedule drifted"):
            training_seed_schedule(train["seeds"][:-1], self.config)
        duplicate = list(train["seeds"])
        duplicate[-1] = duplicate[0]
        with self.assertRaisesRegex(ValueError, "public train roots"):
            training_seed_schedule(duplicate, self.config)

    def test_v3_dispatches_v1_one_boundary_optimizer(self):
        import torch

        from mindustry_agents.training.ippo import SharedRecurrentSelector
        from mindustry_agents.training.ippo_ppo import ippo_update

        model = SharedRecurrentSelector(9601)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0001)
        generator = torch.Generator().manual_seed(9604)
        sentinel = {"batches": 7.0}
        with (
            patch(
                "mindustry_agents.training.ippo_ppo._ippo_one_boundary_update",
                return_value=sentinel,
            ) as one_boundary,
            patch(
                "mindustry_agents.training.ippo_ppo.ippo_sequence_update"
            ) as sequence,
        ):
            result = ippo_update(
                model,
                optimizer,
                [],
                self.config,
                generator,
            )
        self.assertEqual(result, sentinel)
        one_boundary.assert_called_once()
        sequence.assert_not_called()

    def test_v3_training_authority_requires_v3_gate(self):
        from mindustry_agents.training.ippo_preflight import V3_GATES
        from mindustry_agents.training.ippo_ppo import (
            IPPO_V3_CONFIG_SHA256,
            IPPO_V3_PROTOCOL_SHA256,
        )
        from mindustry_agents.training.ippo_train import (
            validate_training_authority,
        )

        authority = {
            "schema": "m9_ippo_v3_preflight_v1",
            "implementation_commit": "a" * 40,
            "config_sha256": IPPO_V3_CONFIG_SHA256,
            "protocol_sha256": IPPO_V3_PROTOCOL_SHA256,
            "gates": list(V3_GATES),
            "confirmation_or_held_out_access": False,
            "passed": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preflight.json"
            path.write_text(json.dumps(authority), encoding="utf-8")
            with patch(
                "mindustry_agents.training.ippo_train._git_commit",
                return_value="a" * 40,
            ):
                result = validate_training_authority(
                    path, self.root, self.config
                )
            self.assertEqual(result["config_sha256"], IPPO_V3_CONFIG_SHA256)
            authority["gates"] = list(V3_GATES[:-1])
            path.write_text(json.dumps(authority), encoding="utf-8")
            with patch(
                "mindustry_agents.training.ippo_train._git_commit",
                return_value="a" * 40,
            ):
                with self.assertRaisesRegex(ValueError, "incomplete"):
                    validate_training_authority(path, self.root, self.config)

    def test_v3_checkpoint_and_manifest_bind_successor_config(self):
        import torch

        from mindustry_agents.training.ippo import SharedRecurrentSelector
        from mindustry_agents.training.ippo_artifacts import (
            base_run_manifest,
            load_ippo_checkpoint,
            save_ippo_checkpoint,
        )
        from mindustry_agents.training.ippo_ppo import (
            IPPO_V3_CONFIG_SHA256,
            sha256_path,
        )

        def identity(path: Path) -> dict:
            document = json.loads(path.read_text(encoding="utf-8"))
            return {
                "id": document["seed_set_id"],
                "version": document["seed_set_version"],
                "split": document["split"],
                "path": str(path.relative_to(self.root).as_posix()),
                "sha256": sha256_path(path),
            }

        model = SharedRecurrentSelector(int(self.config["model_init_seed"]))
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0001, eps=1e-8)
        with tempfile.TemporaryDirectory() as directory:
            checkpoint_path = Path(directory) / "checkpoint.pt"
            checkpoint = save_ippo_checkpoint(
                checkpoint_path,
                model,
                optimizer,
                update=0,
                parent_checkpoint_content_sha256=None,
                config_sha256_value=IPPO_V3_CONFIG_SHA256,
            )
            loaded = SharedRecurrentSelector(1)
            payload = load_ippo_checkpoint(
                checkpoint_path,
                loaded,
                expected_config_sha256=IPPO_V3_CONFIG_SHA256,
            )
            self.assertEqual(
                payload["checkpoint_content_sha256"],
                checkpoint["checkpoint_content_sha256"],
            )
        train_path = self.root / self.config["train_seed_set"]
        dev_path = self.root / self.config["dev_seed_set"]
        manifest = base_run_manifest(
            self.root / "configs/training/m9-ippo-v3-diverse2048.json",
            initial_model_state_sha256="initial",
            train_seed_set=identity(train_path),
            dev_seed_set=identity(dev_path),
            baseline_path=(
                self.root
                / "configs/evaluation/m9-ippo-v1-shared-expert-baseline.json"
            ),
        )
        self.assertEqual(
            manifest["source_config"]["sha256"], IPPO_V3_CONFIG_SHA256
        )
        self.assertEqual(
            manifest["seed_sets"]["train"]["sha256"],
            identity(train_path)["sha256"],
        )
        self.assertEqual(
            manifest["training_root_schedule"]["root_count"],
            2048,
        )


if __name__ == "__main__":
    unittest.main()
