"""Focused ADR-0079 entropy-annealing governance tests."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


@unittest.skipIf(importlib.util.find_spec("torch") is None, "RL extra is not installed")
class TestIPPOEntropyAnneal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from mindustry_agents.process.launcher import repo_root
        from mindustry_agents.training.ippo_ppo import load_ippo_v4_config

        cls.root = repo_root()
        cls.config = load_ippo_v4_config(
            cls.root / "configs/training/m9-ippo-v4-entropy-anneal.json"
        )

    def test_config_and_protocol_are_exact_public_only(self):
        from mindustry_agents.training.ippo_ppo import (
            IPPO_V4_CONFIG_SHA256,
            IPPO_V4_PROTOCOL_SHA256,
            config_sha256,
            protocol_sha256,
        )

        self.assertEqual(
            self.config["candidate_version"], "m9-ippo-v4-entropy-anneal"
        )
        self.assertEqual(config_sha256(self.config), IPPO_V4_CONFIG_SHA256)
        self.assertEqual(protocol_sha256(self.config), IPPO_V4_PROTOCOL_SHA256)
        self.assertIsNone(self.config["teacher"])
        self.assertIsNone(self.config["confirmation_seed_set"])
        self.assertIsNone(self.config["held_out_seed_set"])

    def test_v4_inherits_v3_except_entropy_schedule(self):
        from mindustry_agents.training.ippo_entropy_check import build_report

        report = build_report(self.root)
        self.assertTrue(report["semantic_inheritance_exact"])
        self.assertEqual(report["training_root_count"], 2048)
        self.assertEqual(report["training_root_reuse_count"], 1)
        self.assertFalse(report["confirmation_or_held_out_access"])

    def test_entropy_schedule_is_exact_and_strict(self):
        from mindustry_agents.training.ippo_ppo import (
            entropy_coefficient_for_update,
        )

        values = [
            entropy_coefficient_for_update(self.config, update)
            for update in range(1, 33)
        ]
        self.assertEqual(values[0], 0.02)
        self.assertEqual(values[-1], 0.0)
        self.assertAlmostEqual(values[15], 0.02 * 16 / 31)
        self.assertTrue(
            all(left > right for left, right in zip(values, values[1:]))
        )
        with self.assertRaisesRegex(ValueError, "required"):
            entropy_coefficient_for_update(self.config, None)
        with self.assertRaisesRegex(ValueError, "out of range"):
            entropy_coefficient_for_update(self.config, 33)

    def test_v4_dispatches_scheduled_one_boundary_optimizer(self):
        import torch

        from mindustry_agents.training.ippo import SharedRecurrentSelector
        from mindustry_agents.training.ippo_ppo import ippo_update

        model = SharedRecurrentSelector(9601)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0001)
        generator = torch.Generator().manual_seed(9604)

        def fake_update(model, optimizer, episodes, config, generator):
            return {"batches": 3.0, "seen": config["entropy_coefficient"]}

        with (
            patch(
                "mindustry_agents.training.ippo_ppo._ippo_one_boundary_update",
                side_effect=fake_update,
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
                update_number=16,
            )
        self.assertAlmostEqual(result["entropy_coefficient"], 0.02 * 16 / 31)
        self.assertEqual(result["seen"], result["entropy_coefficient"])
        one_boundary.assert_called_once()
        sequence.assert_not_called()

    def test_v3_dispatch_and_metrics_remain_unchanged(self):
        import torch

        from mindustry_agents.training.ippo import SharedRecurrentSelector
        from mindustry_agents.training.ippo_ppo import (
            ippo_update,
            load_ippo_v3_config,
        )

        v3 = load_ippo_v3_config(
            self.root / "configs/training/m9-ippo-v3-diverse2048.json"
        )
        model = SharedRecurrentSelector(9601)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0001)
        generator = torch.Generator().manual_seed(9604)
        sentinel = {"batches": 7.0}
        with patch(
            "mindustry_agents.training.ippo_ppo._ippo_one_boundary_update",
            return_value=sentinel,
        ) as one_boundary:
            result = ippo_update(model, optimizer, [], v3, generator)
        self.assertEqual(result, sentinel)
        one_boundary.assert_called_once_with(model, optimizer, [], v3, generator)

    def test_v4_twin_real_updates_are_exact(self):
        import torch

        from mindustry_agents.training.ippo import (
            SharedRecurrentSelector,
            model_state_digest,
        )
        from mindustry_agents.training.ippo_ppo import (
            IPPOEpisodeRollout,
            IPPOTransition,
            ippo_update,
        )

        def fixture(model):
            transitions = []
            for agent_id in range(3):
                candidates = torch.zeros((8, 37))
                candidates[:, 0] = agent_id / 10
                scalars = torch.zeros(160)
                scalars[0] = agent_id / 10
                present = torch.ones(8, dtype=torch.bool)
                mask = torch.ones(10, dtype=torch.bool)
                hidden = torch.zeros(64)
                with torch.no_grad():
                    _, logits, value, _ = model(
                        candidates[None],
                        scalars[None],
                        present[None],
                        mask[None],
                        torch.tensor([agent_id]),
                        hidden[None],
                    )
                    action = agent_id
                    old_log_prob = torch.log_softmax(
                        logits[0], dim=-1
                    )[action]
                transitions.append(
                    IPPOTransition(
                        agent_id=agent_id,
                        candidates=candidates,
                        scalars=scalars,
                        candidate_present=present,
                        action_mask=mask,
                        hidden_input=hidden,
                        action=action,
                        old_log_prob=float(old_log_prob),
                        old_value=float(value[0]),
                        team_reward=1.0,
                        individual_reward=-0.01 * agent_id,
                        advanced_ticks=60,
                        done=True,
                        policy_loss_mask=True,
                        recurrent_reset=True,
                    )
                )
            return [IPPOEpisodeRollout(12345, "win", tuple(transitions))]

        results = []
        for _ in range(2):
            model = SharedRecurrentSelector(9601)
            optimizer = torch.optim.Adam(
                model.parameters(), lr=0.0001, eps=1e-8
            )
            metrics = ippo_update(
                model,
                optimizer,
                fixture(model),
                self.config,
                torch.Generator().manual_seed(9604),
                update_number=16,
            )
            results.append((metrics, model_state_digest(model)))
        self.assertEqual(results[0], results[1])

    def test_protocol_diff_is_identity_only(self):
        v3 = json.loads(
            (
                self.root
                / "configs/evaluation/m9-ippo-v3-diverse2048-public-protocol.json"
            ).read_text(encoding="utf-8")
        )
        v4 = json.loads(
            (
                self.root
                / "configs/evaluation/m9-ippo-v4-entropy-anneal-public-protocol.json"
            ).read_text(encoding="utf-8")
        )
        v4["schema"] = v3["schema"]
        v4["candidate_version"] = v3["candidate_version"]
        self.assertEqual(v4, v3)

    def test_v4_training_authority_requires_v4_gate(self):
        from mindustry_agents.training.ippo_preflight import V4_GATES
        from mindustry_agents.training.ippo_ppo import (
            IPPO_V4_CONFIG_SHA256,
            IPPO_V4_PROTOCOL_SHA256,
        )
        from mindustry_agents.training.ippo_train import (
            validate_training_authority,
        )

        authority = {
            "schema": "m9_ippo_v4_preflight_v1",
            "implementation_commit": "a" * 40,
            "config_sha256": IPPO_V4_CONFIG_SHA256,
            "protocol_sha256": IPPO_V4_PROTOCOL_SHA256,
            "gates": list(V4_GATES),
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
            self.assertEqual(result["config_sha256"], IPPO_V4_CONFIG_SHA256)
            authority["gates"] = list(V4_GATES[:-1])
            path.write_text(json.dumps(authority), encoding="utf-8")
            with patch(
                "mindustry_agents.training.ippo_train._git_commit",
                return_value="a" * 40,
            ):
                with self.assertRaisesRegex(ValueError, "incomplete"):
                    validate_training_authority(
                        path, self.root, self.config
                    )

    def test_v4_schedule_is_the_exact_v3_root_schedule(self):
        from mindustry_agents.training.ippo_ppo import load_ippo_v3_config
        from mindustry_agents.training.ippo_train import training_seed_schedule

        train = json.loads(
            (self.root / self.config["train_seed_set"]).read_text(
                encoding="utf-8"
            )
        )
        v3 = load_ippo_v3_config(
            self.root / "configs/training/m9-ippo-v3-diverse2048.json"
        )
        self.assertEqual(
            training_seed_schedule(train["seeds"], self.config),
            training_seed_schedule(train["seeds"], v3),
        )

    def test_v4_checkpoint_and_manifest_bind_scheduled_recipe(self):
        import torch

        from mindustry_agents.training.ippo import SharedRecurrentSelector
        from mindustry_agents.training.ippo_artifacts import (
            base_run_manifest,
            load_ippo_checkpoint,
            save_ippo_checkpoint,
        )
        from mindustry_agents.training.ippo_ppo import (
            IPPO_V4_CONFIG_SHA256,
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
                config_sha256_value=IPPO_V4_CONFIG_SHA256,
            )
            loaded = SharedRecurrentSelector(1)
            payload = load_ippo_checkpoint(
                checkpoint_path,
                loaded,
                expected_config_sha256=IPPO_V4_CONFIG_SHA256,
            )
            self.assertEqual(
                payload["checkpoint_content_sha256"],
                checkpoint["checkpoint_content_sha256"],
            )
        train_path = self.root / self.config["train_seed_set"]
        dev_path = self.root / self.config["dev_seed_set"]
        manifest = base_run_manifest(
            self.root / "configs/training/m9-ippo-v4-entropy-anneal.json",
            initial_model_state_sha256="initial",
            train_seed_set=identity(train_path),
            dev_seed_set=identity(dev_path),
            baseline_path=(
                self.root
                / "configs/evaluation/m9-ippo-v1-shared-expert-baseline.json"
            ),
        )
        self.assertEqual(
            manifest["source_config"]["sha256"], IPPO_V4_CONFIG_SHA256
        )
        self.assertEqual(
            manifest["training_root_schedule"],
            self.config["training_root_schedule"],
        )


if __name__ == "__main__":
    unittest.main()
