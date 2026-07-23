"""Focused governance tests for the M9 IPPO full-run orchestrator."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import torch

from mindustry_agents.process.launcher import repo_root
from mindustry_agents.training.ippo import (
    SharedRecurrentSelector,
    model_state_digest,
)
from mindustry_agents.training.ippo_artifacts import (
    atomic_write_manifest,
    base_run_manifest,
    finalize_run_manifest,
    save_ippo_checkpoint,
)
from mindustry_agents.training.ippo_preflight import GATES
from mindustry_agents.training.ippo_ppo import (
    IPPO_V1_CONFIG_SHA256,
    IPPO_V1_PROTOCOL_SHA256,
    load_ippo_v1_config,
)
from mindustry_agents.training.ippo_train import (
    DEV_MAXIMUM,
    DEV_MINIMUM,
    TRAIN_MAXIMUM,
    TRAIN_MINIMUM,
    _load_seed_set,
    compare_replicas,
    public_comparison,
    select_checkpoint,
    training_seed_schedule,
    validate_training_authority,
)


class TestIPPOTrainingOrchestrator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = repo_root()
        cls.config = load_ippo_v1_config(
            cls.root / "configs/training/m9-ippo-v1.json"
        )

    def test_training_schedule_is_exact_and_cycle_local(self):
        train = json.loads(
            (
                self.root
                / "configs/evaluation/bootstrap-defense-v1-m9-train-v1.json"
            ).read_text(encoding="utf-8")
        )
        schedule = training_seed_schedule(train["seeds"], self.config)
        self.assertEqual(len(schedule), 2048)
        roots = set(train["seeds"])
        for start in range(0, len(schedule), 64):
            self.assertEqual(set(schedule[start : start + 64]), roots)
        self.assertNotEqual(schedule[:64], schedule[64:128])
        self.assertEqual(
            schedule,
            training_seed_schedule(train["seeds"], self.config),
        )

    def test_only_frozen_public_seed_documents_are_valid(self):
        train, _ = _load_seed_set(
            self.root,
            self.config["train_seed_set"],
            split="train",
            expected_count=64,
            lower=TRAIN_MINIMUM,
            upper=TRAIN_MAXIMUM,
            config=self.config,
        )
        dev, _ = _load_seed_set(
            self.root,
            self.config["dev_seed_set"],
            split="dev",
            expected_count=40,
            lower=DEV_MINIMUM,
            upper=DEV_MAXIMUM,
            config=self.config,
        )
        self.assertEqual(train["split"], "train")
        self.assertEqual(dev["split"], "dev")
        with self.assertRaisesRegex(ValueError, "only public train or dev"):
            _load_seed_set(
                self.root,
                self.config["dev_seed_set"],
                split="held-out",
                expected_count=40,
                lower=DEV_MINIMUM,
                upper=DEV_MAXIMUM,
                config=self.config,
            )

    def test_checkpoint_selection_is_eligible_only_and_lexicographic(self):
        policy = self.config["checkpoint_selection"]
        rows = [
            {
                "update": 1,
                "wins": 31,
                "mean_team_return": 1.0,
                "mean_core_health": 900.0,
                "mean_team_idle_fraction": 0.20,
            },
            {
                "update": 2,
                "wins": 31,
                "mean_team_return": 2.0,
                "mean_core_health": 800.0,
                "mean_team_idle_fraction": 0.20,
            },
            {
                "update": 3,
                "wins": 40,
                "mean_team_return": 99.0,
                "mean_core_health": 1100.0,
                "mean_team_idle_fraction": 0.25,
            },
        ]
        self.assertEqual(select_checkpoint(rows, policy), 1)
        self.assertIsNone(
            select_checkpoint(
                [
                    {
                        "update": 1,
                        "wins": 29,
                        "mean_team_return": 10.0,
                        "mean_core_health": 1100.0,
                        "mean_team_idle_fraction": 0.0,
                    }
                ],
                policy,
            )
        )

    def test_training_authority_must_match_current_commit(self):
        authority = {
            "schema": "m9_ippo_preflight_v1",
            "implementation_commit": "a" * 40,
            "config_sha256": IPPO_V1_CONFIG_SHA256,
            "protocol_sha256": IPPO_V1_PROTOCOL_SHA256,
            "gates": list(GATES),
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
                result = validate_training_authority(path, self.root)
                self.assertTrue(result["passed"])
            authority["implementation_commit"] = "b" * 40
            path.write_text(json.dumps(authority), encoding="utf-8")
            with patch(
                "mindustry_agents.training.ippo_train._git_commit",
                return_value="a" * 40,
            ):
                with self.assertRaisesRegex(ValueError, "current commit"):
                    validate_training_authority(path, self.root)

    def test_public_comparison_uses_paired_frozen_thresholds(self):
        baseline_rows = [
            {
                "seed": seed,
                "outcome": "win",
                "team_return": 1.0,
                "team_idle_fraction": 0.5,
                "core_health": 1000.0,
            }
            for seed in range(40)
        ]
        candidate = [
            {
                **row,
                "team_return": 2.0,
                "team_idle_fraction": 0.25,
            }
            for row in baseline_rows
        ]
        protocol = {
            "paired_bootstrap": {
                "iterations": 200,
                "seed": 9701,
                "interval": 0.95,
            },
            "mappo_authorization": {
                "win_rate_difference_lower_bound_minimum": 0.0,
                "team_return_difference_lower_bound_exclusive": 0.0,
                "team_idle_fraction_difference_upper_bound_maximum": 0.0,
            },
        }
        baseline = {
            "episodes": baseline_rows,
            "aggregate": {
                "episodes": 40,
                "wins": 40,
                "mean_team_return": 1.0,
                "mean_core_health": 1000.0,
                "mean_team_idle_fraction": 0.5,
            },
        }
        result = public_comparison(candidate, baseline, protocol)
        self.assertTrue(result["mappo_statistical_thresholds_passed"])
        self.assertEqual(
            result["differences"]["team_return"]["ci95"], [1.0, 1.0]
        )
        self.assertFalse(result["confirmation_or_held_out_access"])

    def test_replica_comparison_requires_direct_checkpoint_identity(self):
        model = SharedRecurrentSelector(int(self.config["model_init_seed"]))
        optimizer = torch.optim.Adam(
            model.parameters(),
            lr=float(self.config["learning_rate"]),
            eps=float(self.config["adam_epsilon"]),
        )
        train_path = (
            self.root
            / "configs/evaluation/bootstrap-defense-v1-m9-train-v1.json"
        )
        dev_path = (
            self.root
            / "configs/evaluation/bootstrap-defense-v1-m9-dev-v1.json"
        )

        def identity(path: Path) -> dict:
            document = json.loads(path.read_text(encoding="utf-8"))
            return {
                "id": document["seed_set_id"],
                "version": document["seed_set_version"],
                "split": document["split"],
                "path": str(path.relative_to(self.root).as_posix()),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }

        with tempfile.TemporaryDirectory(dir=self.root / "runs") as directory:
            root = Path(directory)
            checkpoints = [
                save_ippo_checkpoint(
                    root / replica / "checkpoint.pt",
                    model,
                    optimizer,
                    update=0,
                    parent_checkpoint_content_sha256=None,
                )
                for replica in ("a", "b")
            ]
            manifest = base_run_manifest(
                self.root / "configs/training/m9-ippo-v1.json",
                initial_model_state_sha256=model_state_digest(model),
                train_seed_set=identity(train_path),
                dev_seed_set=identity(dev_path),
                baseline_path=(
                    self.root
                    / "configs/evaluation/"
                    "m9-ippo-v1-shared-expert-baseline.json"
                ),
            )
            manifests = []
            for checkpoint in checkpoints:
                candidate = deepcopy(manifest)
                candidate["selected_checkpoint"] = {
                    **{
                        key: checkpoint[key]
                        for key in (
                            "file_sha256",
                            "checkpoint_content_sha256",
                            "model_state_sha256",
                            "optimizer_state_sha256",
                            "update",
                            "parent_checkpoint_content_sha256",
                        )
                    },
                    "path": str(
                        Path(checkpoint["path"])
                        .relative_to(self.root)
                        .as_posix()
                    ),
                }
                candidate["deterministic_checkpoint_verification"] = {
                    "seed": 19000000001,
                    "trace_digest_a": "trace",
                    "trace_digest_b": "trace",
                    "bit_exact": True,
                }
                candidate["construction_passed"] = True
                candidate["selected_checkpoint_payload_update"] = 0
                manifests.append(finalize_run_manifest(candidate))
            paths = [root / "a.json", root / "b.json"]
            for path, manifest_value in zip(paths, manifests, strict=True):
                atomic_write_manifest(path, manifest_value)
            result = compare_replicas(*paths)
            self.assertTrue(result["exact_replica"])
            self.assertTrue(result["direct_checkpoint_lineage"])


if __name__ == "__main__":
    unittest.main()
