"""Direct reproducible-checkpoint lineage tests."""

from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


@unittest.skipIf(importlib.util.find_spec("torch") is None, "RL extra is not installed")
class TestDirectCheckpointLineage(unittest.TestCase):
    def test_direct_lineage_requires_exact_replicas_and_validates(self):
        import torch

        from mindustry_agents.training.checkpoint_lineage import (
            build_direct_lineage,
            validate_lineage_manifest,
        )
        from mindustry_agents.training.model import (
            MODEL_SCHEMA,
            SelectorActorCritic,
        )
        from mindustry_agents.training.ppo_selector import (
            FEATURE_SCHEMA,
            REWARD_SCHEMA,
            _json_digest,
            _model_state_digest,
            _reproducibility_evidence,
            _sha256,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps({"model_init_seed": 7}), encoding="utf-8"
            )
            config_sha = _sha256(config_path)
            model = SelectorActorCritic(7)
            model_state_sha = _model_state_digest(model.state_dict())
            checkpoint_a = root / "checkpoint-a.pt"
            checkpoint_b = root / "checkpoint-b.pt"
            torch.save(
                {
                    "feature_schema": FEATURE_SCHEMA,
                    "reward_schema": REWARD_SCHEMA,
                    "model_schema": MODEL_SCHEMA,
                    "config_sha256": config_sha,
                    "update": 3,
                    "model_state": model.state_dict(),
                },
                checkpoint_a,
            )
            shutil.copyfile(checkpoint_a, checkpoint_b)

            def run_manifest(checkpoint_path):
                manifest = {
                    "schema": "selector_training_run_v1",
                    "source_config": {"path": "config.json", "sha256": config_sha},
                    "runtime": {"jvm_args": ["-Xbatch"]},
                    "rng_seeds": {"model_init_seed": 7},
                    "initial_model_state_sha256": model_state_sha,
                    "checkpoint": {
                        "update": 3,
                        "sha256": _sha256(checkpoint_path),
                        "model_state_sha256": model_state_sha,
                    },
                    "optimizer_updates": [{"policy_loss": 0.25}],
                    "dev_checkpoint_selection": [
                        {
                            "update": 3,
                            "wins": 9,
                            "mean_return": 1.0,
                            "mean_core_health": 500.0,
                        }
                    ],
                    "train": [{"trace_digest": "train"}],
                    "dev": [{"trace_digest": "dev"}],
                    "scorecard": {"dev_wins": 9},
                    "action_state_trace_digest": "dev-traces",
                    "deterministic_checkpoint_verification": {
                        "seed": 2,
                        "fresh_runs": 2,
                        "trace_digest_a": "replay",
                        "trace_digest_b": "replay",
                        "bit_exact": True,
                    },
                    "repository": {
                        "commit": "training-commit",
                        "status": [" M AGENTS.md"],
                    },
                    "schemas": {
                        "feature": FEATURE_SCHEMA,
                        "reward": REWARD_SCHEMA,
                        "model": MODEL_SCHEMA,
                    },
                }
                manifest["full_run_reproducibility"] = {
                    "digest": _json_digest(_reproducibility_evidence(manifest))
                }
                return manifest

            manifest_a = root / "manifest-a.json"
            manifest_b = root / "manifest-b.json"
            manifest_a.write_text(
                json.dumps(run_manifest(checkpoint_a)), encoding="utf-8"
            )
            manifest_b.write_text(
                json.dumps(run_manifest(checkpoint_b)), encoding="utf-8"
            )
            lineage = build_direct_lineage(
                config_path=config_path,
                checkpoint_paths=(checkpoint_a, checkpoint_b),
                manifest_paths=(manifest_a, manifest_b),
                repository={"commit": "construction-commit", "status": []},
            )
            lineage_path = root / "lineage.json"
            lineage_path.write_text(json.dumps(lineage), encoding="utf-8")

            validated = validate_lineage_manifest(
                manifest_path=lineage_path,
                config_path=config_path,
                checkpoint_path=checkpoint_a,
            )
            self.assertEqual(
                validated["checkpoint_sha256"], _sha256(checkpoint_a)
            )
            self.assertEqual(
                validated["training_repository_commit"], "training-commit"
            )

            second = json.loads(manifest_b.read_text(encoding="utf-8"))
            second["scorecard"]["dev_wins"] = 8
            second["full_run_reproducibility"]["digest"] = _json_digest(
                _reproducibility_evidence(second)
            )
            manifest_b.write_text(json.dumps(second), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "diverge"):
                build_direct_lineage(
                    config_path=config_path,
                    checkpoint_paths=(checkpoint_a, checkpoint_b),
                    manifest_paths=(manifest_a, manifest_b),
                    repository={"commit": "construction-commit", "status": []},
                )
