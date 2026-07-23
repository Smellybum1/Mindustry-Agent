"""Focused ADR-0073 recurrent-sequence optimization tests."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


@unittest.skipIf(importlib.util.find_spec("torch") is None, "RL extra is not installed")
class TestIPPOSequenceOptimization(unittest.TestCase):
    @staticmethod
    def _transition(
        model,
        *,
        agent_id: int,
        boundary: int,
        recurrent_reset: bool,
        done: bool,
        policy_loss_mask: bool = True,
    ):
        import torch

        from mindustry_agents.training.ippo_ppo import IPPOTransition

        candidates = torch.zeros((8, 37))
        candidates[:, 0] = boundary + agent_id / 10
        scalars = torch.zeros(160)
        scalars[0] = boundary / 10
        present = torch.ones(8, dtype=torch.bool)
        mask = torch.ones(10, dtype=torch.bool)
        hidden = (
            torch.zeros(64)
            if recurrent_reset
            else torch.full((64,), 0.01 * (boundary + agent_id))
        )
        with torch.no_grad():
            _, logits, value, _ = model(
                candidates[None],
                scalars[None],
                present[None],
                mask[None],
                torch.tensor([agent_id]),
                hidden[None],
            )
            action = (boundary + agent_id) % 8
            old_log_prob = torch.log_softmax(logits[0], dim=-1)[action]
        return IPPOTransition(
            agent_id=agent_id,
            candidates=candidates,
            scalars=scalars,
            candidate_present=present,
            action_mask=mask,
            hidden_input=hidden,
            action=action,
            old_log_prob=float(old_log_prob),
            old_value=float(value[0]),
            team_reward=1.0 + boundary / 10,
            individual_reward=-0.01 * agent_id,
            advanced_ticks=60,
            done=done,
            policy_loss_mask=policy_loss_mask,
            recurrent_reset=recurrent_reset,
        )

    @staticmethod
    def _sequence_config(*, length: int, per_minibatch: int, epochs: int = 1):
        return {
            "gamma_per_second": 0.99,
            "gae_lambda": 0.95,
            "minibatch_size": length * per_minibatch,
            "ppo_epochs": epochs,
            "clip_ratio": 0.2,
            "value_coefficient": 0.5,
            "entropy_coefficient": 0.02,
            "max_grad_norm": 0.5,
            "recurrent_backpropagation": {
                "schema": "truncated_seat_sequence_v1",
                "sequence_length": length,
                "sequences_per_minibatch": per_minibatch,
            },
        }

    def test_v2_config_is_exact_and_sealed_paths_are_absent(self):
        from mindustry_agents.training.ippo_ppo import load_ippo_v2_config

        path = (
            Path(__file__).resolve().parents[2]
            / "configs/training/m9-ippo-v2-sequence16.json"
        )
        config = load_ippo_v2_config(path)
        self.assertEqual(config["candidate_version"], "m9-ippo-v2-sequence16")
        self.assertEqual(
            config["recurrent_backpropagation"]["sequence_length"], 16
        )
        self.assertIsNone(config["confirmation_seed_set"])
        self.assertIsNone(config["held_out_seed_set"])
        evidence_path = (
            Path(__file__).resolve().parents[2]
            / "configs/evaluation/"
            "m9-ippo-v2-sequence16-optimizer-check.json"
        )
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertEqual(
            hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
            "580493699e7c342b1932afd272c43353fed20180b1fa6511fb2ad76809f6ea63",
        )
        self.assertTrue(evidence["independent_processes_exact"])
        self.assertTrue(evidence["optimizer_and_checkpoint_exact"])
        self.assertFalse(evidence["confirmation_or_held_out_access"])

    def test_v2_checkpoint_and_manifest_bind_successor_config(self):
        import torch

        from mindustry_agents.process.launcher import repo_root
        from mindustry_agents.training.ippo import SharedRecurrentSelector
        from mindustry_agents.training.ippo_artifacts import (
            base_run_manifest,
            load_ippo_checkpoint,
            save_ippo_checkpoint,
        )
        from mindustry_agents.training.ippo_ppo import (
            IPPO_V2_CONFIG_SHA256,
            load_ippo_v2_config,
            sha256_path,
        )

        root = repo_root()
        config_path = root / "configs/training/m9-ippo-v2-sequence16.json"
        config = load_ippo_v2_config(config_path)

        def identity(path):
            document = json.loads(path.read_text(encoding="utf-8"))
            return {
                "id": document["seed_set_id"],
                "version": document["seed_set_version"],
                "split": document["split"],
                "path": str(path.relative_to(root).as_posix()),
                "sha256": sha256_path(path),
            }

        model = SharedRecurrentSelector(int(config["model_init_seed"]))
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0001, eps=1e-8)
        with tempfile.TemporaryDirectory() as directory:
            checkpoint_path = Path(directory) / "checkpoint.pt"
            checkpoint = save_ippo_checkpoint(
                checkpoint_path,
                model,
                optimizer,
                update=0,
                parent_checkpoint_content_sha256=None,
                config_sha256_value=IPPO_V2_CONFIG_SHA256,
            )
            loaded = SharedRecurrentSelector(1)
            with self.assertRaisesRegex(ValueError, "config mismatch"):
                load_ippo_checkpoint(checkpoint_path, loaded)
            payload = load_ippo_checkpoint(
                checkpoint_path,
                loaded,
                expected_config_sha256=IPPO_V2_CONFIG_SHA256,
            )
            self.assertEqual(
                payload["checkpoint_content_sha256"],
                checkpoint["checkpoint_content_sha256"],
            )
        train_path = root / config["train_seed_set"]
        dev_path = root / config["dev_seed_set"]
        manifest = base_run_manifest(
            config_path,
            initial_model_state_sha256="initial",
            train_seed_set=identity(train_path),
            dev_seed_set=identity(dev_path),
            baseline_path=(
                root
                / "configs/evaluation/m9-ippo-v1-shared-expert-baseline.json"
            ),
        )
        self.assertEqual(
            manifest["source_config"]["sha256"], IPPO_V2_CONFIG_SHA256
        )
        self.assertEqual(
            manifest["optimizer_ppo"]["recurrent_backpropagation"][
                "sequence_length"
            ],
            16,
        )

    def test_v2_training_authority_requires_successor_gate(self):
        from mindustry_agents.process.launcher import repo_root
        from mindustry_agents.training.ippo_preflight import V2_GATES
        from mindustry_agents.training.ippo_ppo import (
            IPPO_V2_CONFIG_SHA256,
            IPPO_V2_PROTOCOL_SHA256,
            load_ippo_v2_config,
        )
        from mindustry_agents.training.ippo_train import (
            validate_training_authority,
        )

        root = repo_root()
        config = load_ippo_v2_config(
            root / "configs/training/m9-ippo-v2-sequence16.json"
        )
        authority = {
            "schema": "m9_ippo_v2_preflight_v1",
            "implementation_commit": "a" * 40,
            "config_sha256": IPPO_V2_CONFIG_SHA256,
            "protocol_sha256": IPPO_V2_PROTOCOL_SHA256,
            "gates": list(V2_GATES),
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
                    path, root, config
                )
            self.assertEqual(
                result["config_sha256"], IPPO_V2_CONFIG_SHA256
            )
            authority["gates"] = list(V2_GATES[:-1])
            path.write_text(json.dumps(authority), encoding="utf-8")
            with patch(
                "mindustry_agents.training.ippo_train._git_commit",
                return_value="a" * 40,
            ):
                with self.assertRaisesRegex(ValueError, "incomplete"):
                    validate_training_authority(path, root, config)

    def test_windows_never_cross_agents_resets_or_length(self):
        from mindustry_agents.training.ippo import SharedRecurrentSelector
        from mindustry_agents.training.ippo_ppo import (
            IPPOEpisodeRollout,
            ippo_sequence_windows,
        )

        model = SharedRecurrentSelector(9601)
        transitions = []
        for boundary in range(5):
            for agent_id in range(3):
                transitions.append(
                    self._transition(
                        model,
                        agent_id=agent_id,
                        boundary=boundary,
                        recurrent_reset=(
                            boundary == 0 or (agent_id == 1 and boundary == 3)
                        ),
                        done=boundary == 4,
                    )
                )
        episode = IPPOEpisodeRollout(1, "win", tuple(transitions))
        self.assertEqual(
            ippo_sequence_windows([episode], sequence_length=2),
            (
                (0, 3),
                (6, 9),
                (12,),
                (1, 4),
                (7,),
                (10, 13),
                (2, 5),
                (8, 11),
                (14,),
            ),
        )

    def test_length_one_matches_v1_optimizer_exactly(self):
        import torch

        from mindustry_agents.training.ippo import (
            SharedRecurrentSelector,
            model_state_digest,
        )
        from mindustry_agents.training.ippo_ppo import (
            IPPOEpisodeRollout,
            ippo_update,
        )

        source = SharedRecurrentSelector(9601)
        transition = self._transition(
            source,
            agent_id=0,
            boundary=0,
            recurrent_reset=True,
            done=True,
        )
        episode = IPPOEpisodeRollout(1, "win", (transition,))
        common = {
            "gamma_per_second": 0.99,
            "gae_lambda": 0.95,
            "minibatch_size": 1,
            "ppo_epochs": 1,
            "clip_ratio": 0.2,
            "value_coefficient": 0.5,
            "entropy_coefficient": 0.02,
            "max_grad_norm": 0.5,
        }
        v1 = {**common, "recurrent_backpropagation": {"schema": "one_boundary_truncation_v1"}}
        v2 = {
            **common,
            "recurrent_backpropagation": {
                "schema": "truncated_seat_sequence_v1",
                "sequence_length": 1,
                "sequences_per_minibatch": 1,
            },
        }
        models = [SharedRecurrentSelector(9601) for _ in range(2)]
        optimizers = [
            torch.optim.Adam(model.parameters(), lr=0.0001, eps=1e-8)
            for model in models
        ]
        metrics = [
            ippo_update(
                model,
                optimizer,
                [episode],
                config,
                torch.Generator().manual_seed(9604),
            )
            for model, optimizer, config in zip(
                models, optimizers, (v1, v2), strict=True
            )
        ]
        for key in ("policy_loss", "value_loss", "entropy", "batches"):
            self.assertEqual(metrics[0][key], metrics[1][key])
        self.assertEqual(model_state_digest(models[0]), model_state_digest(models[1]))

    def test_padding_has_no_optimizer_effect(self):
        import torch

        from mindustry_agents.training.ippo import (
            SharedRecurrentSelector,
            model_state_digest,
        )
        from mindustry_agents.training.ippo_ppo import (
            IPPOEpisodeRollout,
            ippo_update,
        )

        source = SharedRecurrentSelector(9601)
        episode = IPPOEpisodeRollout(
            1,
            "win",
            (
                self._transition(
                    source,
                    agent_id=0,
                    boundary=0,
                    recurrent_reset=True,
                    done=False,
                ),
                self._transition(
                    source,
                    agent_id=0,
                    boundary=1,
                    recurrent_reset=False,
                    done=True,
                ),
            ),
        )
        models = [SharedRecurrentSelector(9601) for _ in range(2)]
        optimizers = [
            torch.optim.Adam(model.parameters(), lr=0.0001, eps=1e-8)
            for model in models
        ]
        metrics = [
            ippo_update(
                model,
                optimizer,
                [episode],
                self._sequence_config(length=length, per_minibatch=1),
                torch.Generator().manual_seed(9604),
            )
            for model, optimizer, length in zip(
                models, optimizers, (2, 4), strict=True
            )
        ]
        for key in ("policy_loss", "value_loss", "entropy", "batches"):
            self.assertEqual(metrics[0][key], metrics[1][key])
        self.assertEqual(metrics[0]["padded_transition_slots"], 0.0)
        self.assertEqual(metrics[1]["padded_transition_slots"], 2.0)
        self.assertEqual(model_state_digest(models[0]), model_state_digest(models[1]))

    def test_later_loss_backpropagates_through_earlier_recurrent_step(self):
        import torch

        from mindustry_agents.training.ippo import SharedRecurrentSelector
        from mindustry_agents.training.ippo_ppo import (
            _sequence_minibatch_loss,
        )

        model = SharedRecurrentSelector(9601)
        transitions = [
            self._transition(
                model,
                agent_id=0,
                boundary=0,
                recurrent_reset=True,
                done=False,
                policy_loss_mask=False,
            ),
            self._transition(
                model,
                agent_id=0,
                boundary=1,
                recurrent_reset=False,
                done=True,
                policy_loss_mask=False,
            ),
        ]
        with torch.no_grad():
            hidden = transitions[0].hidden_input[None]
            values = []
            for item in transitions:
                _, _, value, hidden = model(
                    item.candidates[None],
                    item.scalars[None],
                    item.candidate_present[None],
                    item.action_mask[None],
                    torch.tensor([item.agent_id]),
                    hidden,
                )
                values.append(float(value[0]))
        recurrent_outputs = []

        def retain_output(_module, _inputs, output):
            output.retain_grad()
            recurrent_outputs.append(output)

        handle = model.recurrent_cell.register_forward_hook(retain_output)
        try:
            loss, *_ = _sequence_minibatch_loss(
                model,
                transitions,
                torch.zeros(2),
                torch.tensor([values[0], values[1] + 1.0]),
                [(0, 1)],
                sequence_length=2,
                clip_ratio=0.2,
                value_coefficient=0.5,
                entropy_coefficient=0.02,
            )
            loss.backward()
        finally:
            handle.remove()
        self.assertEqual(len(recurrent_outputs), 2)
        self.assertIsNotNone(recurrent_outputs[0].grad)
        self.assertGreater(float(recurrent_outputs[0].grad.abs().sum()), 0.0)

    def test_sequence_update_is_cpu_deterministic(self):
        import torch

        from mindustry_agents.training.ippo import (
            SharedRecurrentSelector,
            model_state_digest,
        )
        from mindustry_agents.training.ippo_ppo import (
            IPPOEpisodeRollout,
            ippo_update,
        )

        torch.set_num_threads(1)
        source = SharedRecurrentSelector(9601)
        transitions = []
        for boundary in range(3):
            for agent_id in range(3):
                transitions.append(
                    self._transition(
                        source,
                        agent_id=agent_id,
                        boundary=boundary,
                        recurrent_reset=boundary == 0,
                        done=boundary == 2,
                    )
                )
        episode = IPPOEpisodeRollout(1, "win", tuple(transitions))
        config = self._sequence_config(
            length=2, per_minibatch=2, epochs=2
        )
        models = [SharedRecurrentSelector(9601) for _ in range(2)]
        optimizers = [
            torch.optim.Adam(model.parameters(), lr=0.0001, eps=1e-8)
            for model in models
        ]
        metrics = [
            ippo_update(
                model,
                optimizer,
                [episode],
                deepcopy(config),
                torch.Generator().manual_seed(9604),
            )
            for model, optimizer in zip(models, optimizers, strict=True)
        ]
        self.assertEqual(metrics[0], metrics[1])
        self.assertEqual(model_state_digest(models[0]), model_state_digest(models[1]))


if __name__ == "__main__":
    unittest.main()
