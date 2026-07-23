"""Focused ADR-0087 successful-action margin governance tests."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


@unittest.skipIf(importlib.util.find_spec("torch") is None, "RL extra is not installed")
class TestIPPOSuccessMargin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch

        from mindustry_agents.process.launcher import repo_root
        from mindustry_agents.training.ippo_ppo import load_ippo_v6_config

        torch.set_num_threads(1)
        cls.root = repo_root()
        cls.config_path = (
            cls.root / "configs/training/m9-ippo-v6-success-margin.json"
        )
        cls.config = load_ippo_v6_config(cls.config_path)

    def test_config_protocol_and_v4_inheritance_are_exact(self):
        from mindustry_agents.training.ippo_preflight import EXPECTED_V6
        from mindustry_agents.training.ippo_ppo import (
            IPPO_V6_CONFIG_SHA256,
            IPPO_V6_PROTOCOL_SHA256,
            config_sha256,
            protocol_sha256,
            sha256_path,
        )
        from mindustry_agents.training.ippo_success_margin_check import (
            build_report,
        )

        self.assertEqual(
            self.config["candidate_version"], "m9-ippo-v6-success-margin"
        )
        self.assertEqual(config_sha256(self.config), IPPO_V6_CONFIG_SHA256)
        self.assertEqual(protocol_sha256(self.config), IPPO_V6_PROTOCOL_SHA256)
        self.assertNotIn(
            "success_conditioned_self_imitation", self.config
        )
        self.assertIsNone(self.config["teacher"])
        self.assertIsNone(self.config["confirmation_seed_set"])
        self.assertIsNone(self.config["held_out_seed_set"])
        report = build_report(self.root)
        self.assertTrue(report["semantic_inheritance_exact"])
        self.assertTrue(report["optimizer"]["independent_runs_exact"])
        self.assertFalse(report["confirmation_or_held_out_access"])
        evidence = (
            self.root
            / "configs/evaluation/"
            "m9-ippo-v6-success-margin-optimizer-check.json"
        )
        self.assertEqual(
            sha256_path(evidence),
            EXPECTED_V6[
                "configs/evaluation/"
                "m9-ippo-v6-success-margin-optimizer-check.json"
            ],
        )
        committed = json.loads(evidence.read_text(encoding="utf-8"))
        self.assertEqual(
            committed["implementation_commit"],
            "05e6b487727cbefae8f104838dd2a428ee9511c4",
        )

    def test_strongest_other_hinge_excludes_sampled_and_illegal(self):
        import torch

        from mindustry_agents.training.ippo_ppo import _success_margin_loss

        minimum = torch.finfo(torch.float32).min
        logits = torch.tensor([[0.2, 0.5, minimum]])
        successful = torch.tensor([True])
        loss = _success_margin_loss(
            logits,
            torch.tensor([0]),
            successful,
            target_margin=0.1,
        )
        self.assertAlmostEqual(float(loss), 0.4, places=6)
        satisfied = _success_margin_loss(
            logits,
            torch.tensor([1]),
            successful,
            target_margin=0.1,
        )
        self.assertEqual(float(satisfied), 0.0)
        empty = _success_margin_loss(
            logits.requires_grad_(),
            torch.tensor([0]),
            torch.tensor([False]),
            target_margin=0.1,
        )
        self.assertEqual(float(empty), 0.0)
        self.assertFalse(empty.requires_grad)

    def test_v6_dispatches_scheduled_success_margin_optimizer(self):
        import torch

        from mindustry_agents.training.ippo import SharedRecurrentSelector
        from mindustry_agents.training.ippo_ppo import ippo_update

        model = SharedRecurrentSelector(9601)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0001)
        generator = torch.Generator().manual_seed(9604)

        def fake_update(model, optimizer, episodes, config, generator):
            return {
                "batches": 3.0,
                "seen_entropy": config["entropy_coefficient"],
            }

        with (
            patch(
                "mindustry_agents.training.ippo_ppo."
                "_ippo_success_margin_update",
                side_effect=fake_update,
            ) as margin_update,
            patch(
                "mindustry_agents.training.ippo_ppo."
                "_ippo_success_imitation_update"
            ) as imitation_update,
            patch(
                "mindustry_agents.training.ippo_ppo."
                "_ippo_one_boundary_update"
            ) as one_boundary,
        ):
            result = ippo_update(
                model,
                optimizer,
                [],
                self.config,
                generator,
                update_number=16,
            )
        expected = 0.02 * 16 / 31
        self.assertAlmostEqual(result["entropy_coefficient"], expected)
        self.assertEqual(result["seen_entropy"], result["entropy_coefficient"])
        margin_update.assert_called_once()
        imitation_update.assert_not_called()
        one_boundary.assert_not_called()

    def test_v5_dispatch_remains_unchanged(self):
        import torch

        from mindustry_agents.training.ippo import SharedRecurrentSelector
        from mindustry_agents.training.ippo_ppo import (
            ippo_update,
            load_ippo_v5_config,
        )

        v5 = load_ippo_v5_config(
            self.root
            / "configs/training/m9-ippo-v5-success-imitation.json"
        )
        model = SharedRecurrentSelector(9601)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0001)
        generator = torch.Generator().manual_seed(9604)
        sentinel = {"batches": 7.0}
        with (
            patch(
                "mindustry_agents.training.ippo_ppo."
                "_ippo_success_imitation_update",
                return_value=sentinel,
            ) as imitation_update,
            patch(
                "mindustry_agents.training.ippo_ppo."
                "_ippo_success_margin_update"
            ) as margin_update,
        ):
            result = ippo_update(
                model,
                optimizer,
                [],
                v5,
                generator,
                update_number=16,
            )
        self.assertEqual(
            result,
            {**sentinel, "entropy_coefficient": 0.02 * 16 / 31},
        )
        imitation_update.assert_called_once()
        margin_update.assert_not_called()

    def test_zero_wins_produce_exact_zero_margin(self):
        import torch

        from mindustry_agents.training.ippo import SharedRecurrentSelector
        from mindustry_agents.training.ippo_ppo import (
            IPPOEpisodeRollout,
            ippo_update,
        )
        from mindustry_agents.training.ippo_success_margin_check import (
            _transition,
        )

        model = SharedRecurrentSelector(9601)
        optimizer = torch.optim.Adam(
            model.parameters(), lr=0.0001, eps=1e-8
        )
        episodes = [
            IPPOEpisodeRollout(
                18000000001,
                "loss",
                (
                    _transition(
                        model,
                        agent_id=0,
                        action=0,
                        policy_loss_mask=True,
                    ),
                ),
            )
        ]
        metrics = ippo_update(
            model,
            optimizer,
            episodes,
            self.config,
            torch.Generator().manual_seed(9604),
            update_number=16,
        )
        self.assertEqual(metrics["success_margin_qualifying_episodes"], 0.0)
        self.assertEqual(
            metrics["success_margin_qualifying_transitions"], 0.0
        )
        self.assertEqual(metrics["success_margin_active_minibatches"], 0.0)
        self.assertEqual(
            metrics["success_margin_mean_active_minibatch_loss"], 0.0
        )

    def test_margin_adds_no_rng_draw(self):
        import torch

        from mindustry_agents.training.ippo import SharedRecurrentSelector
        from mindustry_agents.training.ippo_ppo import (
            ippo_update,
            load_ippo_v4_config,
        )
        from mindustry_agents.training.ippo_success_margin_check import (
            _fixture,
        )

        v6 = copy.deepcopy(self.config)
        v6["ppo_epochs"] = 1
        v6["optimizer_ppo"]["ppo_epochs"] = 1
        model = SharedRecurrentSelector(9601)
        optimizer = torch.optim.Adam(
            model.parameters(), lr=0.0001, eps=1e-8
        )
        v6_generator = torch.Generator().manual_seed(9604)
        metrics = ippo_update(
            model,
            optimizer,
            _fixture(model),
            v6,
            v6_generator,
            update_number=16,
        )
        self.assertGreater(
            metrics["success_margin_mean_active_minibatch_loss"], 0.0
        )

        v4 = load_ippo_v4_config(
            self.root / "configs/training/m9-ippo-v4-entropy-anneal.json"
        )
        v4 = copy.deepcopy(v4)
        v4["ppo_epochs"] = 1
        v4["optimizer_ppo"]["ppo_epochs"] = 1
        v4_model = SharedRecurrentSelector(9601)
        v4_optimizer = torch.optim.Adam(
            v4_model.parameters(), lr=0.0001, eps=1e-8
        )
        v4_generator = torch.Generator().manual_seed(9604)
        ippo_update(
            v4_model,
            v4_optimizer,
            _fixture(v4_model),
            v4,
            v4_generator,
            update_number=16,
        )
        self.assertTrue(
            torch.equal(v6_generator.get_state(), v4_generator.get_state())
        )

    def test_protocol_diff_is_identity_only(self):
        v4 = json.loads(
            (
                self.root
                / "configs/evaluation/"
                "m9-ippo-v4-entropy-anneal-public-protocol.json"
            ).read_text(encoding="utf-8")
        )
        v6 = json.loads(
            (
                self.root
                / "configs/evaluation/"
                "m9-ippo-v6-success-margin-public-protocol.json"
            ).read_text(encoding="utf-8")
        )
        v6["schema"] = v4["schema"]
        v6["candidate_version"] = v4["candidate_version"]
        self.assertEqual(v6, v4)

    def test_v6_training_authority_requires_v6_gate(self):
        from mindustry_agents.training.ippo_preflight import V6_GATES
        from mindustry_agents.training.ippo_ppo import (
            IPPO_V6_CONFIG_SHA256,
            IPPO_V6_PROTOCOL_SHA256,
        )
        from mindustry_agents.training.ippo_train import (
            validate_training_authority,
        )

        authority = {
            "schema": "m9_ippo_v6_preflight_v1",
            "implementation_commit": "a" * 40,
            "config_sha256": IPPO_V6_CONFIG_SHA256,
            "protocol_sha256": IPPO_V6_PROTOCOL_SHA256,
            "gates": list(V6_GATES),
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
            self.assertEqual(result["config_sha256"], IPPO_V6_CONFIG_SHA256)
            authority["gates"] = list(V6_GATES[:-1])
            path.write_text(json.dumps(authority), encoding="utf-8")
            with patch(
                "mindustry_agents.training.ippo_train._git_commit",
                return_value="a" * 40,
            ):
                with self.assertRaisesRegex(ValueError, "incomplete"):
                    validate_training_authority(
                        path, self.root, self.config
                    )

    def test_v6_schedule_checkpoint_and_manifest_bind_recipe(self):
        import torch

        from mindustry_agents.training.ippo import SharedRecurrentSelector
        from mindustry_agents.training.ippo_artifacts import (
            base_run_manifest,
            load_ippo_checkpoint,
            save_ippo_checkpoint,
        )
        from mindustry_agents.training.ippo_ppo import (
            IPPO_V6_CONFIG_SHA256,
            load_ippo_v4_config,
            sha256_path,
        )
        from mindustry_agents.training.ippo_train import training_seed_schedule

        def identity(path: Path) -> dict:
            document = json.loads(path.read_text(encoding="utf-8"))
            return {
                "id": document["seed_set_id"],
                "version": document["seed_set_version"],
                "split": document["split"],
                "path": str(path.relative_to(self.root).as_posix()),
                "sha256": sha256_path(path),
            }

        train_path = self.root / self.config["train_seed_set"]
        train = json.loads(train_path.read_text(encoding="utf-8"))
        v4 = load_ippo_v4_config(
            self.root / "configs/training/m9-ippo-v4-entropy-anneal.json"
        )
        self.assertEqual(
            training_seed_schedule(train["seeds"], self.config),
            training_seed_schedule(train["seeds"], v4),
        )

        model = SharedRecurrentSelector(int(self.config["model_init_seed"]))
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0001, eps=1e-8)
        with tempfile.TemporaryDirectory() as directory:
            checkpoint_path = Path(directory) / "checkpoint.pt"
            checkpoint = save_ippo_checkpoint(
                checkpoint_path,
                model,
                optimizer,
                update=1,
                parent_checkpoint_content_sha256=None,
                config_sha256_value=IPPO_V6_CONFIG_SHA256,
            )
            loaded = SharedRecurrentSelector(1)
            payload = load_ippo_checkpoint(
                checkpoint_path,
                loaded,
                expected_config_sha256=IPPO_V6_CONFIG_SHA256,
            )
            self.assertEqual(
                payload["checkpoint_content_sha256"],
                checkpoint["checkpoint_content_sha256"],
            )
        dev_path = self.root / self.config["dev_seed_set"]
        manifest = base_run_manifest(
            self.config_path,
            initial_model_state_sha256="initial",
            train_seed_set=identity(train_path),
            dev_seed_set=identity(dev_path),
            baseline_path=(
                self.root
                / "configs/evaluation/m9-ippo-v1-shared-expert-baseline.json"
            ),
        )
        self.assertEqual(
            manifest["source_config"]["sha256"], IPPO_V6_CONFIG_SHA256
        )
        self.assertEqual(
            manifest["training_root_schedule"],
            self.config["training_root_schedule"],
        )


if __name__ == "__main__":
    unittest.main()
