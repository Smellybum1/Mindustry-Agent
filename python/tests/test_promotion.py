import json
import tempfile
import unittest
from pathlib import Path

from mindustry_agents.evaluation.ladder import aggregate_records
from mindustry_agents.evaluation.promotion import (
    paired_scorecard_non_regression,
    promotion_preflight,
    validate_scorecard_margins,
    win_rate_comparison,
)


def _record(policy, seed, win, score):
    return {
        "manifest": {"policy": policy},
        "seed": seed,
        "outcome": "win" if win else "loss",
        "core": {"health_final": 100.0 if win else 0.0},
        "seed_set": {"id": "dev", "version": 1, "split": "dev"},
        "scorecard": {
            "idle_fraction": score,
            "duplicate_work_incidents": score,
            "time_to_help_ticks": None,
            "announcements_per_meaningful_transition": score,
            "task_abandonment_rate": score,
            "recovery_time_after_agent_loss_ticks": None,
        },
    }


class TestPromotion(unittest.TestCase):
    def test_operational_margins_are_explicit_and_default_to_zero(self):
        records = []
        for seed in range(10):
            records.append(_record("learned", seed, True, 0.005))
            records.append(_record("baseline", seed, False, 0.0))

        zero_margin = paired_scorecard_non_regression(
            records,
            candidate_policy="learned",
            baseline_policy="baseline",
        )
        self.assertFalse(zero_margin["passed"])
        self.assertNotIn("margins", zero_margin)

        margins = {
            metric: 0.01
            for metric in (
                "idle_fraction",
                "duplicate_work_incidents",
                "time_to_help_ticks",
                "announcements_per_meaningful_transition",
                "task_abandonment_rate",
                "recovery_time_after_agent_loss_ticks",
            )
        }
        operational = paired_scorecard_non_regression(
            records,
            candidate_policy="learned",
            baseline_policy="baseline",
            margins=margins,
        )
        self.assertTrue(operational["passed"])
        self.assertEqual(operational["margins"], margins)
        self.assertEqual(
            operational["metrics"]["idle_fraction"]["status"],
            "operationally_noninferior",
        )
        self.assertEqual(
            operational["metrics"]["idle_fraction"][
                "noninferiority_margin"
            ],
            0.01,
        )

    def test_operational_margins_fail_closed_on_schema_or_value_drift(self):
        with self.assertRaisesRegex(ValueError, "exact metric schema"):
            validate_scorecard_margins({"idle_fraction": 0.01})

        margins = validate_scorecard_margins(None)
        margins["idle_fraction"] = float("nan")
        with self.assertRaisesRegex(ValueError, "idle_fraction"):
            validate_scorecard_margins(margins)

    def test_partner_intent_duplication_risk_uses_shared_validator(self):
        from mindustry_agents.training.promotion import (
            _partner_intent_duplication_risk,
        )

        intervention = {
            "schema": "fixed_partner_selected_task_duplication_risk_v1",
            "agent_ids": [1, 2],
            "match": "task_id",
            "feature": "utility_features.duplication_risk",
            "value": 1.0,
        }
        self.assertEqual(
            _partner_intent_duplication_risk(
                {"partner_intent_duplication_risk": intervention}
            ),
            intervention,
        )

        malformed = dict(intervention, match="task_type")
        with self.assertRaisesRegex(
            ValueError, "invalid partner_intent_duplication_risk config"
        ):
            _partner_intent_duplication_risk(
                {"partner_intent_duplication_risk": malformed}
            )

    def test_matched_control_canonicalizes_catalog_wait_before_indexing(self):
        from mindustry_agents.training.promotion import _canonical_control_action

        candidates = [{"task_type": "HARVEST_RESOURCE"}, {"task_type": "WAIT"}]
        action, index = _canonical_control_action(
            {
                "agent_id": 0,
                "task_action": {
                    "type": "SELECT_CANDIDATE_TASK",
                    "candidate_index": 1,
                },
            },
            candidates,
        )
        self.assertEqual(action["task_action"], {"type": "WAIT"})
        self.assertEqual(index, 9)

        with self.assertRaisesRegex(ValueError, "out-of-range"):
            _canonical_control_action(
                {
                    "agent_id": 0,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": 7,
                    },
                },
                candidates,
            )

    def test_confirmation_attempt_marker_is_exclusive(self):
        from mindustry_agents.training.promotion import _create_exclusive_attempt

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attempt.json"
            _create_exclusive_attempt(path, {"status": "started"})
            with self.assertRaises(FileExistsError):
                _create_exclusive_attempt(path, {"status": "started"})

    def test_baseline_record_loader_requires_every_policy_seed_pair(self):
        from mindustry_agents.training.promotion import (
            PERMANENT_BASELINES,
            _load_baseline_records,
        )

        seed_set = {
            "seed_set_id": "dev",
            "seed_set_version": 1,
            "seeds": [10, 11],
        }
        records = [
            _record(policy, seed, False, 0.0)
            for policy in PERMANENT_BASELINES
            for seed in seed_set["seeds"]
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baselines.jsonl"
            path.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            self.assertEqual(
                len(_load_baseline_records(path, seed_set)), len(records)
            )

            records[-1] = records[-2]
            path.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "missing or stale"):
                _load_baseline_records(path, seed_set)

    def test_baseline_loaders_require_exact_runtime_provenance_when_expected(self):
        from mindustry_agents.training.promotion import (
            PERMANENT_BASELINES,
            RUNTIME_PROVENANCE_ERROR,
            _load_baseline_records,
            _load_baselines,
        )

        expected = {
            "schema": "mindustry_rl_runtime_provenance_v1",
            "config": {"sha256": "config"},
            "repository": {"commit": "commit"},
            "rl_server_jar": {"sha256": "jar"},
        }
        seed_set = {
            "seed_set_id": "dev",
            "seed_set_version": 1,
            "seeds": [10],
        }
        aggregates = [
            {
                "policy": policy,
                "seed_set": {"id": "dev", "version": 1},
            }
            for policy in PERMANENT_BASELINES
        ]
        records = [
            _record(policy, 10, False, 0.0) for policy in PERMANENT_BASELINES
        ]
        for record in records:
            record["manifest"]["runtime_provenance"] = expected

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            aggregate_path = root / "aggregate.json"
            records_path = root / "records.jsonl"
            aggregate_path.write_text(
                json.dumps(
                    {
                        "aggregates": aggregates,
                        "runtime_provenance": expected,
                    }
                ),
                encoding="utf-8",
            )
            records_path.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            self.assertEqual(
                len(_load_baselines(aggregate_path, seed_set, expected)), 2
            )
            self.assertEqual(
                len(_load_baseline_records(records_path, seed_set, expected)), 2
            )

            for field, stale in (
                ("config", {"sha256": "stale"}),
                ("repository", {"commit": "stale"}),
                ("rl_server_jar", {"sha256": "stale"}),
            ):
                changed = json.loads(json.dumps(expected))
                changed[field] = stale
                aggregate_path.write_text(
                    json.dumps(
                        {
                            "aggregates": aggregates,
                            "runtime_provenance": changed,
                        }
                    ),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(RuntimeError, RUNTIME_PROVENANCE_ERROR):
                    _load_baselines(aggregate_path, seed_set, expected)

            aggregate_path.write_text(
                json.dumps({"aggregates": aggregates}), encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, RUNTIME_PROVENANCE_ERROR):
                _load_baselines(aggregate_path, seed_set, expected)
            for field, stale in (
                (None, None),
                ("config", {"sha256": "stale"}),
                ("repository", {"commit": "stale"}),
                ("rl_server_jar", {"sha256": "stale"}),
            ):
                records[0]["manifest"]["runtime_provenance"] = json.loads(
                    json.dumps(expected)
                )
                if field is None:
                    del records[0]["manifest"]["runtime_provenance"]
                else:
                    records[0]["manifest"]["runtime_provenance"][field] = stale
                records_path.write_text(
                    "".join(json.dumps(record) + "\n" for record in records),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    RuntimeError, RUNTIME_PROVENANCE_ERROR
                ):
                    _load_baseline_records(records_path, seed_set, expected)

    def test_preflight_requires_all_win_comparators_and_paired_scorecard(self):
        records = []
        for seed in range(10):
            records.append(_record("learned", seed, True, 0.0))
            records.append(_record("greedy-mixed", seed, seed < 2, 1.0))
            records.append(_record("random-mixed", seed, seed == 0, 2.0))
        aggregates = aggregate_records(records)
        report = promotion_preflight(
            records,
            aggregates,
            candidate_policy="learned",
            win_rate_baselines=("greedy-mixed", "random-mixed"),
            scorecard_baseline="greedy-mixed",
            reward_adversaries_passed=True,
        )

        self.assertTrue(report["eligible_for_held_out"])
        metrics = report["scorecard_non_regression"]["metrics"]
        self.assertEqual(metrics["time_to_help_ticks"]["status"], "not_observed")
        self.assertIsNone(metrics["time_to_help_ticks"]["passed"])

    def test_preflight_fails_tied_win_rate_or_scorecard_regression(self):
        records = []
        for seed in range(10):
            records.append(_record("learned", seed, seed < 7, 2.0))
            records.append(_record("greedy-mixed", seed, seed < 7, 1.0))
        report = promotion_preflight(
            records,
            aggregate_records(records),
            candidate_policy="learned",
            win_rate_baselines=("greedy-mixed",),
            scorecard_baseline="greedy-mixed",
            reward_adversaries_passed=True,
        )

        self.assertFalse(report["eligible_for_held_out"])
        self.assertEqual(
            report["win_rate_comparisons"][0]["status"],
            "not_better_observed_rate",
        )
        self.assertFalse(report["scorecard_non_regression"]["passed"])

    def test_preflight_requires_permanent_and_matched_scorecard_parity(self):
        records = []
        for seed in range(10):
            records.append(_record("learned", seed, True, 0.0))
            records.append(_record("permanent-greedy", seed, seed < 5, -1.0))
            records.append(_record("greedy-mixed", seed, seed < 2, 1.0))
        report = promotion_preflight(
            records,
            aggregate_records(records),
            candidate_policy="learned",
            win_rate_baselines=("permanent-greedy", "greedy-mixed"),
            scorecard_baselines=("permanent-greedy", "greedy-mixed"),
            reward_adversaries_passed=True,
        )

        self.assertFalse(report["eligible_for_held_out"])
        scorecards = report["scorecard_non_regressions"]
        self.assertEqual(
            [item["baseline"] for item in scorecards],
            ["permanent-greedy", "greedy-mixed"],
        )
        self.assertFalse(scorecards[0]["passed"])
        self.assertTrue(scorecards[1]["passed"])
        self.assertIs(report["scorecard_non_regression"], scorecards[-1])

    def test_dev_screen_can_improve_before_held_out_ci_is_separated(self):
        records = []
        for seed in range(10):
            records.append(_record("learned", seed, seed < 8, 0.0))
            records.append(_record("baseline", seed, seed < 7, 0.0))
        learned, baseline = aggregate_records(records)

        dev = win_rate_comparison(
            learned, baseline, require_ci_separation=False
        )
        held_out = win_rate_comparison(
            learned, baseline, require_ci_separation=True
        )

        self.assertTrue(dev["passed"])
        self.assertEqual(dev["status"], "better_observed_rate")
        self.assertFalse(held_out["passed"])
        self.assertEqual(held_out["status"], "not_ci_separated")

    def test_preflight_refuses_non_dev_records(self):
        records = []
        for seed in range(10):
            learned = _record("learned", seed, True, 0.0)
            baseline = _record("baseline", seed, False, 1.0)
            learned["seed_set"]["split"] = "held-out"
            baseline["seed_set"]["split"] = "held-out"
            records.extend((learned, baseline))

        with self.assertRaisesRegex(ValueError, "dev split"):
            promotion_preflight(
                records,
                aggregate_records(records),
                candidate_policy="learned",
                win_rate_baselines=("baseline",),
                scorecard_baseline="baseline",
                reward_adversaries_passed=True,
            )


if __name__ == "__main__":
    unittest.main()
