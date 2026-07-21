import importlib.util
import tempfile
import unittest
from pathlib import Path

from mindustry_agents.evaluation.ladder import aggregate_records


def _record(policy, seed, win, score):
    return {
        "manifest": {"policy": policy},
        "seed": seed,
        "outcome": "win" if win else "loss",
        "core": {"health_final": 100.0 if win else 0.0},
        "seed_set": {"id": "held", "version": 1, "split": "held-out"},
        "scorecard": {
            "idle_fraction": score,
            "duplicate_work_incidents": score,
            "time_to_help_ticks": None,
            "announcements_per_meaningful_transition": score,
            "task_abandonment_rate": score,
            "recovery_time_after_agent_loss_ticks": None,
        },
    }


@unittest.skipIf(importlib.util.find_spec("torch") is None, "RL extra is not installed")
class TestPromotionFinal(unittest.TestCase):
    def test_final_requires_permanent_ci_separation_and_scorecards(self):
        from mindustry_agents.training.promotion import (
            CANDIDATE_POLICY,
            GREEDY_MIXED,
        )
        from mindustry_agents.training.promotion_final import (
            held_out_final_decision,
        )

        records = []
        for seed in range(10):
            records.extend(
                (
                    _record(CANDIDATE_POLICY, seed, True, 0.0),
                    _record("random-valid", seed, False, 2.0),
                    _record("greedy-utility", seed, False, 1.0),
                    _record(GREEDY_MIXED, seed, seed == 0, 1.0),
                )
            )
        report = held_out_final_decision(
            records,
            aggregate_records(records),
            reward_adversaries_passed=True,
        )

        self.assertTrue(report["promoted"])
        self.assertEqual(report["status"], "promoted")
        self.assertTrue(
            all(
                item["passed"]
                for item in report["permanent_win_rate_ci_comparisons"]
            )
        )

    def test_final_rejects_overlapping_permanent_intervals(self):
        from mindustry_agents.training.promotion import (
            CANDIDATE_POLICY,
            GREEDY_MIXED,
        )
        from mindustry_agents.training.promotion_final import (
            held_out_final_decision,
        )

        records = []
        for seed in range(10):
            records.extend(
                (
                    _record(CANDIDATE_POLICY, seed, seed < 8, 0.0),
                    _record("random-valid", seed, seed < 2, 2.0),
                    _record("greedy-utility", seed, seed < 7, 1.0),
                    _record(GREEDY_MIXED, seed, seed < 2, 1.0),
                )
            )
        report = held_out_final_decision(
            records,
            aggregate_records(records),
            reward_adversaries_passed=True,
        )

        self.assertFalse(report["promoted"])
        self.assertEqual(report["status"], "not_promoted")

    def test_attempt_marker_is_exclusive(self):
        from mindustry_agents.training.promotion_final import _create_attempt

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attempt.json"
            _create_attempt(path, {"schema": "attempt", "status": "started"})
            with self.assertRaises(FileExistsError):
                _create_attempt(path, {"schema": "attempt", "status": "started"})


if __name__ == "__main__":
    unittest.main()
