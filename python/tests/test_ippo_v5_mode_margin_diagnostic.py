"""Pure governance tests for ADR-0085's v5 mode-margin diagnostic."""

from __future__ import annotations

import importlib.util
import json
import unittest


@unittest.skipIf(importlib.util.find_spec("torch") is None, "RL extra is not installed")
class TestIPPOV5ModeMarginDiagnostic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch

        from mindustry_agents.process.launcher import repo_root

        torch.set_num_threads(1)
        cls.root = repo_root()

    def test_protocol_is_exact_public_only_and_non_promotional(self):
        from mindustry_agents.training.ippo_ppo import sha256_path
        from mindustry_agents.training.ippo_v5_mode_margin_diagnostic import (
            PROTOCOL_RELATIVE,
            PROTOCOL_SHA256,
        )

        path = self.root / PROTOCOL_RELATIVE
        self.assertEqual(sha256_path(path), PROTOCOL_SHA256)
        protocol = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(protocol["data_classification"], "public_dev_only")
        self.assertEqual(
            [item["update"] for item in protocol["source_checkpoints"]],
            [7, 32],
        )
        self.assertEqual(
            protocol["modes"]["stochastic_categorical"][
                "action_sampling_seeds"
            ],
            [9602, 19602, 29602, 39602],
        )
        self.assertFalse(any(protocol["authority"].values()))

    def test_bound_local_sources_are_exact_and_rejected(self):
        from mindustry_agents.training.ippo_v5_mode_margin_diagnostic import (
            validate_inputs,
        )

        checkpoint = (
            self.root
            / "runs/m9-ippo-v5-success-imitation-a"
            / "ippo-v5-success-imitation-update-7.pt"
        )
        if not checkpoint.exists():
            self.skipTest("ignored immutable v5 checkpoints are not local")
        protocol, manifest, seeds = validate_inputs(self.root)
        self.assertEqual(len(seeds), 40)
        self.assertEqual(len(set(seeds)), 40)
        self.assertFalse(manifest["construction_passed"])
        self.assertEqual(
            [item["update"] for item in protocol["source_checkpoints"]],
            [7, 32],
        )

    def test_classification_is_exact_and_fail_closed(self):
        from mindustry_agents.training.ippo_v5_mode_margin_diagnostic import (
            classify,
        )

        rules = {
            "maximum_argmax_wins_for_unconsolidated": 1,
            "minimum_update_32_stochastic_wins_for_retention": 16,
            "retention_ratio_numerator": 4,
            "retention_ratio_denominator": 5,
            "minimum_update_7_stochastic_wins_for_erosion_reference": 16,
            "erosion_ratio_numerator": 1,
            "erosion_ratio_denominator": 2,
        }
        retained = classify(
            update_7_argmax_wins=1,
            update_32_argmax_wins=0,
            update_7_stochastic_wins=20,
            update_32_stochastic_wins=16,
            rules=rules,
        )
        self.assertEqual(
            retained["outcome"],
            "stochastic_success_retained_without_deterministic_consolidation",
        )
        eroded = classify(
            update_7_argmax_wins=1,
            update_32_argmax_wins=0,
            update_7_stochastic_wins=40,
            update_32_stochastic_wins=20,
            rules=rules,
        )
        self.assertEqual(eroded["outcome"], "success_distribution_eroded")
        inconclusive = classify(
            update_7_argmax_wins=1,
            update_32_argmax_wins=0,
            update_7_stochastic_wins=10,
            update_32_stochastic_wins=8,
            rules=rules,
        )
        self.assertEqual(inconclusive["outcome"], "inconclusive")
        drifted = dict(rules)
        drifted["retention_ratio_numerator"] = 3
        with self.assertRaisesRegex(ValueError, "rules drifted"):
            classify(
                update_7_argmax_wins=1,
                update_32_argmax_wins=0,
                update_7_stochastic_wins=20,
                update_32_stochastic_wins=16,
                rules=drifted,
            )
        with self.assertRaisesRegex(ValueError, "win count"):
            classify(
                update_7_argmax_wins=1,
                update_32_argmax_wins=0,
                update_7_stochastic_wins=161,
                update_32_stochastic_wins=16,
                rules=rules,
            )

    def test_action_measurement_uses_actor_valid_transitions_only(self):
        from mindustry_agents.training.ippo import (
            SharedRecurrentSelector,
            model_state_digest,
        )
        from mindustry_agents.training.ippo_success_imitation_check import (
            _fixture,
        )
        from mindustry_agents.training.ippo_v5_mode_margin_diagnostic import (
            _measure_rollout,
        )

        model = SharedRecurrentSelector(9601)
        model.eval()
        before = model_state_digest(model)
        rollout = _fixture(model)[0]
        measurement = _measure_rollout(model, rollout)
        self.assertEqual(measurement["transition_count"], 1.0)
        self.assertGreater(
            measurement["chosen_action_probability_sum"], 0.0
        )
        self.assertGreaterEqual(
            measurement["top_two_logit_margin_sum"], 0.0
        )
        self.assertEqual(model_state_digest(model), before)


if __name__ == "__main__":
    unittest.main()
