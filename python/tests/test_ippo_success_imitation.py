"""Focused ADR-0083 success-imitation governance tests."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


@unittest.skipIf(importlib.util.find_spec("torch") is None, "RL extra is not installed")
class TestIPPOSuccessImitation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch

        from mindustry_agents.process.launcher import repo_root
        from mindustry_agents.training.ippo_ppo import load_ippo_v5_config

        torch.set_num_threads(1)
        cls.root = repo_root()
        cls.config_path = (
            cls.root / "configs/training/m9-ippo-v5-success-imitation.json"
        )
        cls.config = load_ippo_v5_config(cls.config_path)

    def test_config_and_protocol_are_exact_public_only(self):
        from mindustry_agents.training.ippo_ppo import (
            IPPO_V5_CONFIG_SHA256,
            IPPO_V5_PROTOCOL_SHA256,
            config_sha256,
            protocol_sha256,
        )

        self.assertEqual(
            self.config["candidate_version"],
            "m9-ippo-v5-success-imitation",
        )
        self.assertEqual(config_sha256(self.config), IPPO_V5_CONFIG_SHA256)
        self.assertEqual(protocol_sha256(self.config), IPPO_V5_PROTOCOL_SHA256)
        self.assertIsNone(self.config["teacher"])
        self.assertIsNone(self.config["confirmation_seed_set"])
        self.assertIsNone(self.config["held_out_seed_set"])

    def test_v5_inherits_v4_except_success_imitation(self):
        from mindustry_agents.training.ippo_preflight import EXPECTED_V5
        from mindustry_agents.training.ippo_ppo import sha256_path
        from mindustry_agents.training.ippo_success_imitation_check import (
            build_report,
        )

        report = build_report(self.root)
        self.assertTrue(report["semantic_inheritance_exact"])
        self.assertTrue(report["optimizer"]["independent_runs_exact"])
        self.assertEqual(
            report["optimizer"]["metrics"][
                "success_imitation_qualifying_episodes"
            ],
            1.0,
        )
        self.assertEqual(
            report["optimizer"]["metrics"][
                "success_imitation_qualifying_transitions"
            ],
            1.0,
        )
        self.assertFalse(report["confirmation_or_held_out_access"])
        evidence = (
            self.root
            / "configs/evaluation/"
            "m9-ippo-v5-success-imitation-optimizer-check.json"
        )
        self.assertEqual(
            sha256_path(evidence),
            EXPECTED_V5[
                "configs/evaluation/"
                "m9-ippo-v5-success-imitation-optimizer-check.json"
            ],
        )
        committed = json.loads(evidence.read_text(encoding="utf-8"))
        self.assertEqual(
            committed["implementation_commit"],
            "d6969679ad7e500756660f2a820815b1998a51f9",
        )

    def test_v5_dispatches_scheduled_success_imitation_optimizer(self):
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
                "_ippo_success_imitation_update",
                side_effect=fake_update,
            ) as success_update,
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
        success_update.assert_called_once()
        one_boundary.assert_not_called()

    def test_v4_dispatch_and_metrics_remain_unchanged(self):
        import torch

        from mindustry_agents.training.ippo import SharedRecurrentSelector
        from mindustry_agents.training.ippo_ppo import (
            ippo_update,
            load_ippo_v4_config,
        )

        v4 = load_ippo_v4_config(
            self.root / "configs/training/m9-ippo-v4-entropy-anneal.json"
        )
        model = SharedRecurrentSelector(9601)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0001)
        generator = torch.Generator().manual_seed(9604)
        sentinel = {"batches": 7.0}
        with (
            patch(
                "mindustry_agents.training.ippo_ppo."
                "_ippo_one_boundary_update",
                return_value=sentinel,
            ) as one_boundary,
            patch(
                "mindustry_agents.training.ippo_ppo."
                "_ippo_success_imitation_update"
            ) as success_update,
        ):
            result = ippo_update(
                model,
                optimizer,
                [],
                v4,
                generator,
                update_number=16,
            )
        self.assertEqual(
            result,
            {**sentinel, "entropy_coefficient": 0.02 * 16 / 31},
        )
        one_boundary.assert_called_once()
        success_update.assert_not_called()

    def test_zero_wins_produce_exact_zero_imitation(self):
        import torch

        from mindustry_agents.training.ippo import SharedRecurrentSelector
        from mindustry_agents.training.ippo_ppo import (
            IPPOEpisodeRollout,
            ippo_update,
        )
        from mindustry_agents.training.ippo_success_imitation_check import (
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
        self.assertEqual(
            metrics["success_imitation_qualifying_episodes"], 0.0
        )
        self.assertEqual(
            metrics["success_imitation_qualifying_transitions"], 0.0
        )
        self.assertEqual(
            metrics["success_imitation_active_minibatches"], 0.0
        )
        self.assertEqual(
            metrics["success_imitation_mean_active_minibatch_loss"], 0.0
        )

    def test_sampled_action_nll_is_exact_and_adds_no_rng_draw(self):
        import copy

        import torch

        from mindustry_agents.training.ippo import SharedRecurrentSelector
        from mindustry_agents.training.ippo_ppo import (
            ippo_update,
            load_ippo_v4_config,
        )
        from mindustry_agents.training.ippo_success_imitation_check import (
            _fixture,
        )

        v5 = copy.deepcopy(self.config)
        v5["ppo_epochs"] = 1
        v5["optimizer_ppo"]["ppo_epochs"] = 1
        model = SharedRecurrentSelector(9601)
        episodes = _fixture(model)
        successful = episodes[0].transitions[0]
        with torch.no_grad():
            _, logits, _, _ = model(
                successful.candidates[None],
                successful.scalars[None],
                successful.candidate_present[None],
                successful.action_mask[None],
                torch.tensor([successful.agent_id]),
                successful.hidden_input[None],
            )
            expected = -torch.log_softmax(logits[0], dim=-1)[
                successful.action
            ].item()
        optimizer = torch.optim.Adam(
            model.parameters(), lr=0.0001, eps=1e-8
        )
        v5_generator = torch.Generator().manual_seed(9604)
        metrics = ippo_update(
            model,
            optimizer,
            episodes,
            v5,
            v5_generator,
            update_number=16,
        )
        self.assertAlmostEqual(
            metrics["success_imitation_mean_active_minibatch_loss"],
            expected,
            places=6,
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
            torch.equal(v5_generator.get_state(), v4_generator.get_state())
        )

    def test_protocol_diff_is_identity_only(self):
        v4 = json.loads(
            (
                self.root
                / "configs/evaluation/"
                "m9-ippo-v4-entropy-anneal-public-protocol.json"
            ).read_text(encoding="utf-8")
        )
        v5 = json.loads(
            (
                self.root
                / "configs/evaluation/"
                "m9-ippo-v5-success-imitation-public-protocol.json"
            ).read_text(encoding="utf-8")
        )
        v5["schema"] = v4["schema"]
        v5["candidate_version"] = v4["candidate_version"]
        self.assertEqual(v5, v4)

    def test_v5_training_authority_requires_v5_gate(self):
        from mindustry_agents.training.ippo_preflight import V5_GATES
        from mindustry_agents.training.ippo_ppo import (
            IPPO_V5_CONFIG_SHA256,
            IPPO_V5_PROTOCOL_SHA256,
        )
        from mindustry_agents.training.ippo_train import (
            validate_training_authority,
        )

        authority = {
            "schema": "m9_ippo_v5_preflight_v1",
            "implementation_commit": "a" * 40,
            "config_sha256": IPPO_V5_CONFIG_SHA256,
            "protocol_sha256": IPPO_V5_PROTOCOL_SHA256,
            "gates": list(V5_GATES),
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
            self.assertEqual(result["config_sha256"], IPPO_V5_CONFIG_SHA256)
            authority["gates"] = list(V5_GATES[:-1])
            path.write_text(json.dumps(authority), encoding="utf-8")
            with patch(
                "mindustry_agents.training.ippo_train._git_commit",
                return_value="a" * 40,
            ):
                with self.assertRaisesRegex(ValueError, "incomplete"):
                    validate_training_authority(
                        path, self.root, self.config
                    )

    def test_v5_schedule_is_the_exact_v4_root_schedule(self):
        from mindustry_agents.training.ippo_ppo import load_ippo_v4_config
        from mindustry_agents.training.ippo_train import training_seed_schedule

        train = json.loads(
            (self.root / self.config["train_seed_set"]).read_text(
                encoding="utf-8"
            )
        )
        v4 = load_ippo_v4_config(
            self.root / "configs/training/m9-ippo-v4-entropy-anneal.json"
        )
        self.assertEqual(
            training_seed_schedule(train["seeds"], self.config),
            training_seed_schedule(train["seeds"], v4),
        )

    def test_v5_checkpoint_and_manifest_bind_recipe(self):
        import torch

        from mindustry_agents.training.ippo import SharedRecurrentSelector
        from mindustry_agents.training.ippo_artifacts import (
            base_run_manifest,
            load_ippo_checkpoint,
            save_ippo_checkpoint,
        )
        from mindustry_agents.training.ippo_ppo import (
            IPPO_V5_CONFIG_SHA256,
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
                update=1,
                parent_checkpoint_content_sha256=None,
                config_sha256_value=IPPO_V5_CONFIG_SHA256,
            )
            loaded = SharedRecurrentSelector(1)
            payload = load_ippo_checkpoint(
                checkpoint_path,
                loaded,
                expected_config_sha256=IPPO_V5_CONFIG_SHA256,
            )
            self.assertEqual(
                payload["checkpoint_content_sha256"],
                checkpoint["checkpoint_content_sha256"],
            )
        train_path = self.root / self.config["train_seed_set"]
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
            manifest["source_config"]["sha256"], IPPO_V5_CONFIG_SHA256
        )
        self.assertEqual(
            manifest["training_root_schedule"],
            self.config["training_root_schedule"],
        )


if __name__ == "__main__":
    unittest.main()
