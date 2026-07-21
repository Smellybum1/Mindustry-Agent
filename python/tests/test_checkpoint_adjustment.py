"""Governed selector-logit adjustment tests."""

from __future__ import annotations

import importlib.util
import unittest


@unittest.skipIf(importlib.util.find_spec("torch") is None, "RL extra is not installed")
class TestCheckpointAdjustment(unittest.TestCase):
    def test_adjustment_changes_exactly_one_coordinate(self):
        import torch

        from mindustry_agents.training.checkpoint_adjustment import adjust_model_state

        state = {
            "special_head.2.bias": torch.tensor([0.5, 0.25]),
            "other": torch.tensor([3.0]),
        }
        adjusted = adjust_model_state(
            state,
            tensor_name="special_head.2.bias",
            index=1,
            delta=-0.25,
        )

        self.assertTrue(
            torch.equal(adjusted["special_head.2.bias"], torch.tensor([0.5, 0.0]))
        )
        self.assertTrue(torch.equal(adjusted["other"], state["other"]))
        self.assertTrue(
            torch.equal(state["special_head.2.bias"], torch.tensor([0.5, 0.25]))
        )

    def test_checked_in_v8_contract_targets_wait_once(self):
        import json

        from mindustry_agents.process.launcher import repo_root
        from mindustry_agents.training.checkpoint_lineage import (
            ADJUSTMENT_LINEAGE_SCHEMA,
        )

        config = json.loads(
            (
                repo_root()
                / "configs/training/m8-selector-v8-wait-adjustment.json"
            ).read_text()
        )
        self.assertEqual(config["schema"], ADJUSTMENT_LINEAGE_SCHEMA)
        self.assertEqual(
            config["adjustment"],
            {
                "tensor": "special_head.2.bias",
                "index": 1,
                "action": "WAIT",
                "delta": -0.25,
            },
        )
        self.assertEqual(
            config["held_out_seed_set_id"], "bootstrap-defense-v1-held-out-v2"
        )

        v9 = json.loads(
            (
                repo_root()
                / "configs/training/m8-selector-v9-wait-adjustment.json"
            ).read_text()
        )
        self.assertEqual(v9["schema"], ADJUSTMENT_LINEAGE_SCHEMA)
        self.assertEqual(v9["adjustment"], config["adjustment"])
        self.assertEqual(
            v9["parent"]["checkpoint_sha256"],
            "1f3c4525fb5fd10da6b9e8f0cb6c28b52e82fd39f92b1c0cc349399fac9e66f1",
        )
        self.assertEqual(
            v9["held_out_seed_set_id"], "bootstrap-defense-v1-held-out-v3"
        )
        self.assertEqual(v9["held_out_seed_set_version"], 3)
