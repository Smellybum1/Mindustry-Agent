import unittest

from mindustry_agents.training.reward import (
    COMPONENT_KEYS,
    QUALITY_COMPONENT_KEYS,
    RewardAuditError,
    SelectorReward,
)

QUALITY = {
    "idle_agent_tick_cost": 0.0001,
    "duplicate_work_cost": 0.05,
    "duplicate_work_cap": 1.0,
    "announcement_cost": 0.005,
    "announcement_cap": 1.0,
    "team_abandonment_cost": 0.1,
    "team_abandonment_cap": 2.0,
}
from mindustry_agents.training.reward_adversary import CASES, run_case


def team(tick=0, *, line=False, readiness=0.0, enemies=0, wave=1):
    return {
        "tick": tick,
        "line_operational": line,
        "defense_readiness": readiness,
        "enemy_count": enemies,
        "wave": wave,
    }


class TestSelectorRewardAdversaries(unittest.TestCase):
    def test_reward_v2_charges_monotonic_deltas_and_preserves_v1_default(self):
        self.assertEqual(set(SelectorReward().component_keys), set(COMPONENT_KEYS))
        reward = SelectorReward(quality_reward=QUALITY)
        first = reward.observe(
            team(),
            team(10),
            advanced_ticks=10,
            tick_cap=9000,
            coordination_metrics={
                "agent_ticks": 30,
                "idle_agent_ticks": 12,
                "duplicate_work_incidents": 2,
                "announced_messages": 3,
            },
            task_events=[
                {"act": "ABANDON", "agent_id": 1, "reason_code": "blocked_replan"}
            ],
        )
        self.assertEqual(
            set(first.components), set(COMPONENT_KEYS + QUALITY_COMPONENT_KEYS)
        )
        self.assertAlmostEqual(first.components["reward.penalty.team_idle_ticks"], -0.0012)
        self.assertEqual(first.components["reward.penalty.duplicate_work"], -0.1)
        self.assertEqual(first.components["reward.penalty.communication"], -0.015)
        self.assertEqual(first.components["reward.penalty.team_abandonment"], -0.1)

        unchanged = reward.observe(
            team(10),
            team(20),
            advanced_ticks=10,
            tick_cap=9000,
            coordination_metrics={
                "agent_ticks": 60,
                "idle_agent_ticks": 12,
                "duplicate_work_incidents": 2,
                "announced_messages": 3,
            },
        )
        self.assertTrue(
            all(unchanged.components[key] == 0.0 for key in QUALITY_COMPONENT_KEYS)
        )

    def test_reward_v2_rejects_missing_invalid_or_rolled_back_metrics(self):
        with self.assertRaisesRegex(RewardAuditError, "requires coordination"):
            SelectorReward(quality_reward=QUALITY).observe(
                team(), team(1), advanced_ticks=1, tick_cap=9000
            )
        reward = SelectorReward(quality_reward=QUALITY)
        metrics = {
            "agent_ticks": 30,
            "idle_agent_ticks": 10,
            "duplicate_work_incidents": 1,
            "announced_messages": 1,
        }
        reward.observe(
            team(), team(10), advanced_ticks=10, tick_cap=9000,
            coordination_metrics=metrics,
        )
        with self.assertRaisesRegex(RewardAuditError, "rolled back"):
            reward.observe(
                team(10), team(20), advanced_ticks=10, tick_cap=9000,
                coordination_metrics={**metrics, "idle_agent_ticks": 9},
            )

    def test_reward_v2_caps_quality_costs_and_excludes_forced_abandonment(self):
        reward = SelectorReward(quality_reward=QUALITY)
        result = reward.observe(
            team(), team(9000), advanced_ticks=9000, tick_cap=9000,
            coordination_metrics={
                "agent_ticks": 27000,
                "idle_agent_ticks": 27000,
                "duplicate_work_incidents": 100,
                "announced_messages": 1000,
            },
            task_events=[
                {"act": "ABANDON", "agent_id": 1, "reason_code": "blocked_replan"}
                for _ in range(30)
            ] + [
                {"act": "ABANDON", "agent_id": 2, "reason_code": "wave_preemption"}
            ],
        )
        self.assertEqual(result.components["reward.penalty.team_idle_ticks"], -2.7)
        self.assertEqual(result.components["reward.penalty.duplicate_work"], -1.0)
        self.assertEqual(result.components["reward.penalty.communication"], -1.0)
        self.assertEqual(result.components["reward.penalty.team_abandonment"], -2.0)

    def test_every_named_audit_case_emits_complete_machine_evidence(self):
        reports = [run_case(case) for case in CASES]
        self.assertTrue(all(report["pass"] for report in reports))
        for report in reports:
            expected = COMPONENT_KEYS
            if report["reward_schema"] == "selector_reward_v2":
                expected += QUALITY_COMPONENT_KEYS
            self.assertEqual(set(report["components"]), set(expected))
            self.assertEqual(len(report["action_hashes"]), len(report["state_hashes"]))
            self.assertIn("structured_events", report)
            self.assertIn("coordination_metrics", report)

    def test_reward_v2_breakdown_exposes_auditable_counters_and_totals(self):
        result = SelectorReward(quality_reward=QUALITY).observe(
            team(),
            team(10),
            advanced_ticks=10,
            tick_cap=9000,
            coordination_metrics={
                "agent_ticks": 30,
                "idle_agent_ticks": 12,
                "duplicate_work_incidents": 2,
                "announced_messages": 3,
            },
        )
        self.assertEqual(result.quality_counters["idle_agent_ticks"], 12)
        self.assertAlmostEqual(
            result.quality_penalty_totals["reward.penalty.team_idle_ticks"],
            0.0012,
        )

    def test_rebuild_loop_and_fake_wave_clear_pay_each_physical_highwater_once(self):
        reward = SelectorReward()
        first = reward.observe(team(), team(10, line=True, readiness=1.0), advanced_ticks=10, tick_cap=9000)
        rebuilt = reward.observe(team(10, line=True), team(20, line=True, readiness=1.0), advanced_ticks=10, tick_cap=9000)
        fake = reward.observe(team(20, enemies=1), team(30), advanced_ticks=10, tick_cap=9000, boundary_reasons=["wave_clear"])
        self.assertEqual(first.components["reward.team.milestone_highwater"], 2.0)
        self.assertEqual(rebuilt.components["reward.team.milestone_highwater"], 0.0)
        self.assertEqual(fake.components["reward.team.milestone_highwater"], 0.0)

    def test_real_waves_pay_once_and_total_milestones_cap_at_eight(self):
        reward = SelectorReward()
        total = reward.observe(team(), team(1, line=True, readiness=1.0), advanced_ticks=1, tick_cap=9000).total
        for wave in (1, 2, 3):
            reward.observe(team(enemies=0, wave=wave), team(enemies=wave + 1, wave=wave), advanced_ticks=1, tick_cap=9000, boundary_reasons=["wave_spawn"])
            total += reward.observe(team(enemies=wave + 1, wave=wave), team(enemies=0, wave=wave), advanced_ticks=1, tick_cap=9000, boundary_reasons=["wave_clear"]).components["reward.team.milestone_highwater"]
        self.assertAlmostEqual(total, 8.0 - 0.0002)
        self.assertEqual(len(reward.credited_milestones), 5)

    def test_survival_only_pays_no_terminal_or_milestone(self):
        value = SelectorReward().observe(team(), team(600), advanced_ticks=600, tick_cap=9000)
        self.assertEqual(value.components["reward.team.milestone_highwater"], 0.0)
        self.assertEqual(value.components["reward.team.terminal_outcome"], 0.0)
        self.assertLess(value.total, 0.0)

    def test_forced_truncation_equals_loss_and_reckless_win_stays_terminal_only(self):
        loss = SelectorReward().observe(team(), team(100), advanced_ticks=100, tick_cap=9000, outcome="loss")
        trunc = SelectorReward().observe(team(), team(100), advanced_ticks=100, tick_cap=9000, outcome="truncated")
        win = SelectorReward().observe(team(), team(8100), advanced_ticks=8100, tick_cap=9000, outcome="win")
        self.assertEqual(loss.total, trunc.total)
        self.assertEqual(loss.components["reward.team.terminal_outcome"], -10.0)
        self.assertEqual(win.components["reward.team.terminal_outcome"], 10.0)
        self.assertEqual(win.components["reward.team.milestone_highwater"], 0.0)

    def test_early_suicide_and_late_loss_have_same_tick_cost_horizon(self):
        early = SelectorReward().observe(team(), team(100), advanced_ticks=100, tick_cap=9000, outcome="loss")
        late = SelectorReward().observe(team(), team(8000), advanced_ticks=8000, tick_cap=9000, outcome="loss")
        self.assertEqual(early.charged_ticks, late.charged_ticks)
        self.assertEqual(early.components["reward.team.unresolved_tick_cost"], -1.8)

    def test_chunk_size_is_reward_invariant(self):
        one = SelectorReward().observe(team(), team(600), advanced_ticks=600, tick_cap=9000)
        split_reward = SelectorReward()
        split = [split_reward.observe(team(i), team(i + 100), advanced_ticks=100, tick_cap=9000) for i in range(0, 600, 100)]
        self.assertAlmostEqual(one.total, sum(item.total for item in split))
        self.assertEqual(one.charged_ticks, sum(item.charged_ticks for item in split))

    def test_readiness_then_abandon_does_not_repeat_or_reverse_credit(self):
        reward = SelectorReward()
        ready = reward.observe(team(), team(10, readiness=1.0), advanced_ticks=10, tick_cap=9000)
        abandoned = reward.observe(team(10, readiness=1.0), team(20, readiness=0.0), advanced_ticks=10, tick_cap=9000)
        restored = reward.observe(team(20), team(30, readiness=1.0), advanced_ticks=10, tick_cap=9000)
        self.assertEqual(ready.components["reward.team.milestone_highwater"], 1.0)
        self.assertEqual(abandoned.components["reward.team.milestone_highwater"], 0.0)
        self.assertEqual(restored.components["reward.team.milestone_highwater"], 0.0)

    def test_invalid_spam_caps_and_mask_corruption_fails_the_run(self):
        reward = SelectorReward()
        penalties = [reward.observe(team(i), team(i + 1), advanced_ticks=1, tick_cap=9000, raw_action_valid=False).components["reward.penalty.invalid_action"] for i in range(8)]
        self.assertEqual(sum(penalties), -1.0)
        with self.assertRaisesRegex(RewardAuditError, "mask/boundary mismatch"):
            reward.observe(team(), team(1), advanced_ticks=1, tick_cap=9000, environment_mask_valid=False)

    def test_invalid_probe_has_one_penalty_and_no_alternate_credit(self):
        reward = SelectorReward()
        result = reward.observe(team(), team(1), advanced_ticks=1, tick_cap=9000, raw_action_valid=False)
        self.assertEqual(result.components["reward.penalty.invalid_action"], -0.25)
        self.assertEqual(result.components["reward.team.milestone_highwater"], 0.0)

    def test_claim_abandon_churn_caps_and_exclusions_are_exact_zero(self):
        reward = SelectorReward()
        reward.record_learned_selection("learned-task")
        charged = 0.0
        for index in range(15):
            result = reward.observe(
                team(index), team(index + 1), advanced_ticks=1, tick_cap=9000,
                task_events=[{"act": "ABANDON", "agent_id": 0, "task_id": "learned-task", "reason_code": "blocked_replan"}],
            )
            charged += result.components["reward.penalty.abandonment_liability"]
        self.assertAlmostEqual(charged, -0.5)
        for reason in ("wave_preemption", "readiness_rebalance", "death", "lease_failure", "human_override", "terminal_cleanup"):
            result = reward.observe(
                team(), team(1), advanced_ticks=1, tick_cap=9000,
                task_events=[{"act": "ABANDON", "agent_id": 0, "task_id": "learned-task", "reason_code": reason}],
            )
            self.assertEqual(result.components["reward.penalty.abandonment_liability"], 0.0)

    def test_blocked_never_release_wait_and_unrewarded_signals_cannot_farm(self):
        result = SelectorReward().observe(
            team(), team(300), advanced_ticks=300, tick_cap=9000,
            task_events=[
                {"act": "MESSAGE", "agent_id": 0},
                {"act": "OFFER_HELP", "agent_id": 0},
                {"act": "PROGRESS", "agent_id": 0, "progress": 1.0},
            ],
        )
        self.assertEqual(set(result.components), set(COMPONENT_KEYS))
        self.assertTrue(all(value <= 0.0 for value in result.components.values()))


if __name__ == "__main__":
    unittest.main()
