import tempfile
import unittest
from pathlib import Path

from mindustry_agents.evaluation.ladder import aggregate_records
from mindustry_agents.evaluation.promotion import (
    promotion_preflight,
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
    def test_confirmation_attempt_marker_is_exclusive(self):
        from mindustry_agents.training.promotion import _create_exclusive_attempt

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attempt.json"
            _create_exclusive_attempt(path, {"status": "started"})
            with self.assertRaises(FileExistsError):
                _create_exclusive_attempt(path, {"status": "started"})

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
