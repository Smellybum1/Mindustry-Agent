"""Pure governance tests for ADR-0081's late-checkpoint diagnostic."""

from __future__ import annotations

import importlib.util
import json
import unittest


@unittest.skipIf(importlib.util.find_spec("torch") is None, "RL extra is not installed")
class TestIPPOLateCheckpointDiagnostic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from mindustry_agents.process.launcher import repo_root

        cls.root = repo_root()

    def test_protocol_is_exact_public_only_and_non_promotional(self):
        from mindustry_agents.training.ippo_late_checkpoint_diagnostic import (
            PROTOCOL_RELATIVE,
            PROTOCOL_SHA256,
        )
        from mindustry_agents.training.ippo_ppo import sha256_path

        path = self.root / PROTOCOL_RELATIVE
        self.assertEqual(sha256_path(path), PROTOCOL_SHA256)
        protocol = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(protocol["data_classification"], "public_dev_only")
        self.assertEqual(
            [item["update"] for item in protocol["source_checkpoints"]],
            [31, 32],
        )
        self.assertEqual(
            protocol["modes"]["stochastic_categorical"][
                "action_sampling_seeds"
            ],
            [9602, 19602, 29602, 39602],
        )
        self.assertFalse(any(protocol["authority"].values()))

    def test_bound_local_sources_are_exact_and_rejected(self):
        from mindustry_agents.training.ippo_late_checkpoint_diagnostic import (
            validate_inputs,
        )

        checkpoint = (
            self.root
            / "runs/m9-ippo-v4-entropy-anneal-a1"
            / "ippo-v4-entropy-anneal-update-31.pt"
        )
        if not checkpoint.exists():
            self.skipTest("ignored immutable v4 checkpoints are not local")
        protocol, manifest, seeds = validate_inputs(self.root)
        self.assertEqual(len(seeds), 40)
        self.assertEqual(len(set(seeds)), 40)
        self.assertFalse(manifest["construction_passed"])
        self.assertEqual(
            [item["update"] for item in protocol["source_checkpoints"]],
            [31, 32],
        )

    def test_classification_is_exact_and_fail_closed(self):
        from mindustry_agents.training.ippo_late_checkpoint_diagnostic import (
            classify,
        )

        rules = {
            "required_argmax_win_drop": 10,
            "minimum_update_32_stochastic_wins_for_retention": 32,
            "mode_instability_retention_ratio_numerator": 4,
            "mode_instability_retention_ratio_denominator": 5,
            "optimizer_collapse_ratio_numerator": 1,
            "optimizer_collapse_ratio_denominator": 2,
        }
        mode = classify(
            update_31_argmax_wins=18,
            update_32_argmax_wins=0,
            update_31_stochastic_wins=50,
            update_32_stochastic_wins=40,
            rules=rules,
        )
        self.assertEqual(mode["outcome"], "deterministic_mode_instability")
        collapse = classify(
            update_31_argmax_wins=18,
            update_32_argmax_wins=0,
            update_31_stochastic_wins=80,
            update_32_stochastic_wins=40,
            rules=rules,
        )
        self.assertEqual(
            collapse["outcome"],
            "optimizer_distribution_collapse",
        )
        inconclusive = classify(
            update_31_argmax_wins=18,
            update_32_argmax_wins=0,
            update_31_stochastic_wins=60,
            update_32_stochastic_wins=40,
            rules=rules,
        )
        self.assertEqual(inconclusive["outcome"], "inconclusive")
        drifted = dict(rules)
        drifted["required_argmax_win_drop"] = 9
        with self.assertRaisesRegex(ValueError, "rules drifted"):
            classify(
                update_31_argmax_wins=18,
                update_32_argmax_wins=0,
                update_31_stochastic_wins=50,
                update_32_stochastic_wins=40,
                rules=drifted,
            )
        with self.assertRaisesRegex(ValueError, "win count"):
            classify(
                update_31_argmax_wins=18,
                update_32_argmax_wins=0,
                update_31_stochastic_wins=161,
                update_32_stochastic_wins=40,
                rules=rules,
            )


if __name__ == "__main__":
    unittest.main()
