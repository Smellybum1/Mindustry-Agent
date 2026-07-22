"""Pure tests for the reusable V39 partner-intent replay diagnostic."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mindustry_agents.training.partner_intent_diagnostic import (
    REPORT_SCHEMA,
    atomic_write_json,
    build_report,
    common_action_state_prefix,
    diagnostic_exposure,
    exact_legacy_trace_parity,
    first_causally_comparable_action_difference,
    validate_report_gates,
    validate_reusable_inputs,
)
from mindustry_agents.training.ppo_selector import EpisodeRollout


def _row(tick, action_index, state_hash, *, diagnostics=False):
    row = {
        "tick": tick,
        "advanced_ticks": 10,
        "action": {
            "type": "SELECT_CANDIDATE_TASK",
            "candidate_index": action_index,
        },
        "agent_actions": [
            {
                "agent_id": 0,
                "task_action": {
                    "type": "SELECT_CANDIDATE_TASK",
                    "candidate_index": action_index,
                },
            }
        ],
        "action_index": action_index,
        "policy_loss_mask": True,
        "reward_components": {},
        "boundary_reasons": ["task_event"],
        "state_hash": state_hash,
        "outcome": "running",
        "raw_logits": [0.0],
    }
    if diagnostics:
        row["fixed_partner_intended_task_ids"] = ["supply:copper"]
        row["partner_intent_duplication_risk_candidate_indices"] = [2]
    return row


def _episode(seed, trace, *, outcome="win"):
    return EpisodeRollout(
        seed=seed,
        outcome=outcome,
        tick=trace[-1]["tick"] + trace[-1]["advanced_ticks"],
        core_health=800.0,
        transitions=[SimpleNamespace(policy_loss_mask=True) for _ in trace],
        reward_components={},
        trace=trace,
        coordination_metrics={},
    )


def _config(version, *, enabled):
    config = {
        "schema": "selector_training_config_v1",
        "candidate_version": version,
        "scenario_id": "bootstrap-defense-v1",
        "scenario_version": 2,
        "model_architecture": {"schema": "selector_actor_critic_v1"},
        "reward_schema": "selector_reward_v2",
        "quality_reward": {"idle_agent_tick_cost": 0.002},
        "model_init_seed": 8601,
        "action_sampling_seed": 8602,
        "dev_seed_set": "configs/evaluation/bootstrap-defense-v1-dev-v1.json",
    }
    if enabled:
        config["partner_intent_duplication_risk"] = {
            "schema": "fixed_partner_selected_task_duplication_risk_v1",
            "agent_ids": [1, 2],
            "match": "task_id",
            "feature": "utility_features.duplication_risk",
            "value": 1.0,
        }
    return config


def _seed_set():
    return {
        "seed_set_id": "bootstrap-defense-v1-dev-v1",
        "seed_set_version": 1,
        "scenario_id": "bootstrap-defense-v1",
        "scenario_version": 2,
        "split": "dev",
        "seeds": list(range(2001, 2011)),
    }


class PartnerIntentDiagnosticTests(unittest.TestCase):
    def test_reusable_inputs_require_exact_legacy_and_enabled_coordinate(self):
        seeds, intervention = validate_reusable_inputs(
            _config("v38", enabled=False),
            _config("v39", enabled=True),
            _seed_set(),
        )
        self.assertEqual(seeds, list(range(2001, 2011)))
        self.assertEqual(intervention["agent_ids"], [1, 2])

        bad_set = _seed_set()
        bad_set["split"] = "confirmation"
        with self.assertRaisesRegex(ValueError, "not a dev split"):
            validate_reusable_inputs(
                _config("v38", enabled=False),
                _config("v39", enabled=True),
                bad_set,
            )

    def test_exact_legacy_trace_equality_and_digest(self):
        trace = [_row(0, 1, "a"), _row(10, 2, "b")]
        parity = exact_legacy_trace_parity(
            trace, json.loads(json.dumps(trace)), seed=2001
        )
        self.assertTrue(parity["bit_exact"])
        self.assertEqual(parity["actual_rows"], 2)
        self.assertEqual(
            parity["actual_trace_digest"], parity["expected_trace_digest"]
        )
        changed = json.loads(json.dumps(trace))
        changed[1]["raw_logits"] = [0.25]
        self.assertFalse(
            exact_legacy_trace_parity(trace, changed, seed=2001)["bit_exact"]
        )

    def test_common_prefix_and_first_causally_comparable_action_difference(self):
        disabled = [_row(0, 1, "a"), _row(10, 2, "b")]
        enabled = [
            _row(0, 1, "a", diagnostics=True),
            _row(10, 3, "c", diagnostics=True),
        ]
        self.assertEqual(common_action_state_prefix(disabled, enabled), 1)
        difference = first_causally_comparable_action_difference(disabled, enabled)
        self.assertEqual(
            difference,
            {
                "decision_ordinal": 1,
                "tick": 10,
                "disabled_action": {
                    "type": "SELECT_CANDIDATE_TASK",
                    "candidate_index": 2,
                },
                "disabled_action_index": 2,
                "enabled_action": {
                    "type": "SELECT_CANDIDATE_TASK",
                    "candidate_index": 3,
                },
                "enabled_action_index": 3,
                "enabled_intended_task_ids": ["supply:copper"],
                "enabled_risk_candidate_indices": [2],
            },
        )

    def test_no_change_has_full_prefix_and_no_first_difference(self):
        disabled = [_row(0, 1, "a"), _row(10, 2, "b")]
        enabled = json.loads(json.dumps(disabled))
        for row in enabled:
            row["fixed_partner_intended_task_ids"] = ["supply:copper"]
            row["partner_intent_duplication_risk_candidate_indices"] = [2]
        self.assertEqual(common_action_state_prefix(disabled, enabled), 2)
        self.assertIsNone(
            first_causally_comparable_action_difference(disabled, enabled)
        )

    def test_state_first_divergence_is_not_reported_as_causal_action_change(self):
        disabled = [_row(0, 1, "a")]
        enabled = [_row(0, 1, "different", diagnostics=True)]
        self.assertEqual(common_action_state_prefix(disabled, enabled), 0)
        self.assertIsNone(
            first_causally_comparable_action_difference(disabled, enabled)
        )

    def test_diagnostic_exposure_counts_and_completeness(self):
        complete = [
            _row(0, 1, "a", diagnostics=True),
            _row(10, 2, "b", diagnostics=True),
        ]
        complete[1]["fixed_partner_intended_task_ids"] = []
        complete[0]["partner_intent_duplication_risk_candidate_indices"] = [1, 3]
        self.assertEqual(
            diagnostic_exposure(complete),
            {
                "diagnostics_complete": True,
                "intent_exposed_decisions": 1,
                "exact_risk_candidate_exposures": 3,
            },
        )
        del complete[1]["fixed_partner_intended_task_ids"]
        self.assertFalse(diagnostic_exposure(complete)["diagnostics_complete"])

    def test_compact_report_is_deterministic_and_records_non_comparable_tail(self):
        seeds = list(range(2001, 2011))
        disabled = []
        enabled = []
        for seed in seeds:
            disabled_trace = [_row(0, 1, f"{seed}-a"), _row(10, 2, f"{seed}-b")]
            enabled_trace = [
                _row(0, 1, f"{seed}-a", diagnostics=True),
                _row(10, 2, f"{seed}-b", diagnostics=True),
            ]
            disabled.append(_episode(seed, disabled_trace))
            enabled.append(_episode(seed, enabled_trace))
        enabled[0].trace[1] = _row(10, 3, "changed", diagnostics=True)
        parity = exact_legacy_trace_parity(
            disabled[0].trace, disabled[0].trace, seed=2001
        )
        kwargs = {
            "source_bindings": {
                "checkpoint": {"path": "checkpoint.pt", "sha256": "abc"}
            },
            "seeds": seeds,
            "disabled_episodes": disabled,
            "enabled_episodes": enabled,
            "legacy_parity": parity,
        }
        first = build_report(**kwargs)
        second = build_report(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], REPORT_SCHEMA)
        self.assertEqual(first["seeds_with_action_change"], 1)
        self.assertEqual(first["total_intent_exposed_decisions"], 20)
        self.assertEqual(first["total_exact_risk_candidate_exposures"], 20)
        self.assertEqual(
            first["per_seed"][0]["non_comparable_tail_rows"],
            {"disabled": 1, "enabled": 1},
        )
        self.assertEqual(
            set(first),
            {
                "schema",
                "sources",
                "seeds",
                "disabled_legacy_parity",
                "disabled_summary_digest",
                "enabled_summary_digest",
                "disabled_outcomes",
                "enabled_outcomes",
                "total_intent_exposed_decisions",
                "total_exact_risk_candidate_exposures",
                "seeds_with_action_change",
                "enabled_diagnostics_complete",
                "per_seed",
            },
        )

    def test_report_gates_fail_closed_without_required_evidence(self):
        base = {
            "disabled_legacy_parity": {"bit_exact": True},
            "enabled_diagnostics_complete": True,
            "total_intent_exposed_decisions": 1,
            "total_exact_risk_candidate_exposures": 1,
        }
        validate_report_gates(base)
        cases = (
            ("disabled_legacy_parity", {"bit_exact": False}, "does not match"),
            ("enabled_diagnostics_complete", False, "lacks"),
            ("total_intent_exposed_decisions", 0, "no partner intent"),
            ("total_exact_risk_candidate_exposures", 0, "no exact-risk"),
        )
        for key, value, message in cases:
            report = dict(base)
            report[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, message):
                validate_report_gates(report)

    def test_atomic_output_creates_parent_and_cleans_failed_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "report.json"
            atomic_write_json(output, {"b": 2, "a": 1})
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")), {"a": 1, "b": 2}
            )
            self.assertTrue(output.read_text(encoding="utf-8").endswith("\n"))

            with patch.object(os, "replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(RuntimeError, "atomically write"):
                    atomic_write_json(output, {"a": 3})
            self.assertEqual(
                [path for path in output.parent.iterdir() if path.suffix == ".tmp"],
                [],
            )
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")), {"a": 1, "b": 2}
            )


if __name__ == "__main__":
    unittest.main()
