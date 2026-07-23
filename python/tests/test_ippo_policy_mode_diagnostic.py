"""Pure governance tests for ADR-0077's policy-mode diagnostic."""

from __future__ import annotations

import importlib.util
import json
import unittest


@unittest.skipIf(importlib.util.find_spec("torch") is None, "RL extra is not installed")
class TestIPPOPolicyModeDiagnostic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from mindustry_agents.process.launcher import repo_root

        cls.root = repo_root()

    def test_protocol_is_exact_public_only_and_non_promotional(self):
        from mindustry_agents.training.ippo_policy_mode_diagnostic import (
            PROTOCOL_RELATIVE,
            PROTOCOL_SHA256,
        )
        from mindustry_agents.training.ippo_ppo import sha256_path

        path = self.root / PROTOCOL_RELATIVE
        self.assertEqual(sha256_path(path), PROTOCOL_SHA256)
        protocol = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(protocol["data_classification"], "public_dev_only")
        self.assertEqual(
            protocol["modes"]["stochastic_categorical"][
                "action_sampling_seeds"
            ],
            [9602, 19602, 29602, 39602],
        )
        self.assertEqual(
            protocol["classification"][
                "minimum_stochastic_wins_total_for_sampling_signal"
            ],
            32,
        )
        self.assertFalse(
            any(protocol["authority"].values()),
        )

    def test_bound_local_sources_are_exact_and_rejected(self):
        from mindustry_agents.training.ippo_policy_mode_diagnostic import (
            validate_inputs,
        )

        checkpoint = (
            self.root
            / "runs/m9-ippo-v3-diverse2048-a1"
            / "ippo-v3-diverse2048-update-29.pt"
        )
        if not checkpoint.exists():
            self.skipTest("ignored immutable v3 checkpoint is not local")
        protocol, manifest, seeds = validate_inputs(self.root)
        self.assertEqual(len(seeds), 40)
        self.assertEqual(len(set(seeds)), 40)
        self.assertFalse(manifest["construction_passed"])
        self.assertEqual(protocol["source_checkpoint"]["update"], 29)

    def test_classification_threshold_is_fail_closed(self):
        from mindustry_agents.training.ippo_policy_mode_diagnostic import (
            classify,
        )

        self.assertFalse(classify(31, 32)["sampling_signal"])
        self.assertTrue(classify(32, 32)["sampling_signal"])
        with self.assertRaisesRegex(ValueError, "threshold drifted"):
            classify(32, 31)
        with self.assertRaisesRegex(ValueError, "win count"):
            classify(161, 32)


if __name__ == "__main__":
    unittest.main()
