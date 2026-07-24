import unittest

from mindustry_agents.policies import (
    CandidateNativePlanner,
    CandidateNativePlannerV2,
    GreedyUtilityPolicy,
    HelperCoordinator,
    PureGreedyUtilityPolicy,
    RandomValidPolicy,
    RoleAssignmentPolicy,
)


def observation(x=0.0, candidates=None, skill=None, team=None):
    return {
        "unit": {"x": x, "y": 0.0},
        "skill": skill or {},
        "team": team or {},
        "task_candidates": candidates
        or [
            {"index": 0, "task_type": "HARVEST_RESOURCE", "utility": 2.0},
            {"index": 1, "task_type": "BUILD_SCHEMATIC", "utility": 3.0},
            {"index": 2, "task_type": "WAIT", "utility": 0.1},
        ],
    }


class TestScriptedPolicies(unittest.TestCase):
    @staticmethod
    def planner_candidate(
        index,
        task_type,
        *,
        target=None,
        utility=1.0,
        exclusive=True,
    ):
        return {
            "index": index,
            "task_id": f"{task_type}:{target or index}",
            "task_type": task_type,
            "target": target or f"target-{index}",
            "utility": utility,
            "valid": True,
            "exclusive": exclusive,
        }

    def test_candidate_native_planner_allocates_distinct_opening_roles(self):
        candidates = [
            self.planner_candidate(0, "HARVEST_RESOURCE", utility=2.0),
            self.planner_candidate(1, "BUILD_LINE", utility=3.0),
            self.planner_candidate(2, "BUILD_SCHEMATIC", utility=4.0),
            self.planner_candidate(3, "WAIT", exclusive=False),
        ]
        team = {
            "tick": 0,
            "enemy_count": 0,
            "line_operational": False,
            "defense_turret_coverage": 0.0,
        }
        actions = CandidateNativePlanner().actions(
            [observation(candidates=candidates, team=team) for _ in range(3)],
            [{"candidate_task": [True] * 4} for _ in range(3)],
        )
        self.assertEqual(
            [action["task_action"]["candidate_index"] for action in actions],
            [1, 2, 0],
        )

    def test_candidate_native_planner_rejects_cross_seat_semantic_duplicates(self):
        first = self.planner_candidate(
            0, "SUPPLY_TURRET", target="tile (30, 20)", utility=5.0
        )
        duplicate = {
            **first,
            "index": 1,
            "task_id": "different-id",
            "utility": 4.0,
        }
        harvest = self.planner_candidate(2, "HARVEST_RESOURCE", utility=1.0)
        team = {
            "tick": 100,
            "enemy_count": 2,
            "defense_ammo_coverage": 0.2,
        }
        candidates = [first, duplicate, harvest]
        actions = CandidateNativePlanner().actions(
            [observation(candidates=candidates, team=team) for _ in range(2)],
            [{"candidate_task": [True] * 3} for _ in range(2)],
        )
        selected = [
            action["task_action"].get("candidate_index") for action in actions
        ]
        self.assertIn(2, selected)
        self.assertEqual(sum(index in {0, 1} for index in selected), 1)

    def test_candidate_native_planner_v2_only_serializes_schematic_selections(self):
        candidates = [
            self.planner_candidate(
                0, "BUILD_SCHEMATIC", target="fortification-a", utility=5.0
            ),
            self.planner_candidate(
                1, "BUILD_SCHEMATIC", target="fortification-b", utility=4.0
            ),
            self.planner_candidate(2, "HARVEST_RESOURCE", utility=1.0),
        ]
        team = {
            "tick": 250,
            "enemy_count": 0,
            "line_operational": True,
            "defense_turret_coverage": 0.5,
        }
        observations = [
            observation(candidates=candidates, team=team) for _ in range(2)
        ]
        masks = [{"candidate_task": [True] * 3} for _ in range(2)]
        v1 = CandidateNativePlanner().actions(observations, masks)
        v2 = CandidateNativePlannerV2().actions(observations, masks)
        self.assertEqual(
            sum(
                action["task_action"].get("candidate_index") in {0, 1}
                for action in v1
            ),
            2,
        )
        self.assertEqual(
            sum(
                action["task_action"].get("candidate_index") in {0, 1}
                for action in v2
            ),
            1,
        )
        self.assertIn(2, [action["task_action"].get("candidate_index") for action in v2])

    def test_candidate_native_planner_preserves_continue_and_preempts_for_wave(self):
        planner = CandidateNativePlanner()
        team = {"tick": 100, "enemy_count": 2}
        actions = planner.actions(
            [
                observation(
                    skill={"type": "DEFEND", "status": "RUNNING"}, team=team
                ),
                observation(skill={"type": "BUILD", "status": "RUNNING"}, team=team),
            ],
            [
                {"continue_current_task": True, "abandon": True},
                {"continue_current_task": True, "abandon": True},
            ],
        )
        self.assertEqual(
            actions[0]["task_action"], {"type": "CONTINUE_CURRENT_TASK"}
        )
        self.assertEqual(
            actions[1]["task_action"],
            {"type": "ABANDON", "reason": "wave_preempt"},
        )

    def test_candidate_native_planner_bounds_blocked_replans_and_resets(self):
        planner = CandidateNativePlanner()
        mask = {"continue_current_task": True, "abandon": True}
        for tick in (10, 20, 30):
            action = planner.actions(
                [
                    observation(
                        skill={"status": "BLOCKED", "reason": "STUCK"},
                        team={"tick": tick},
                    )
                ],
                [mask],
            )[0]
            self.assertEqual(action["task_action"]["type"], "ABANDON")
        bounded = planner.actions(
            [
                observation(
                    skill={"status": "BLOCKED", "reason": "STUCK"},
                    team={"tick": 40},
                )
            ],
            [mask],
        )[0]
        self.assertEqual(
            bounded["task_action"], {"type": "CONTINUE_CURRENT_TASK"}
        )
        reset = planner.actions(
            [
                observation(
                    skill={"status": "BLOCKED", "reason": "STUCK"},
                    team={"tick": 0},
                )
            ],
            [mask],
        )[0]
        self.assertEqual(reset["task_action"]["type"], "ABANDON")

    def test_greedy_selects_highest_valid_utility_with_stable_tie_break(self):
        candidates = [
            {"index": 0, "task_type": "HARVEST_RESOURCE", "utility": 4.0},
            {"index": 1, "task_type": "BUILD_SCHEMATIC", "utility": 4.0},
        ]
        action = GreedyUtilityPolicy().action(
            0, observation(candidates=candidates), {"candidate_task": [True, True]}
        )
        self.assertEqual(action["task_action"]["candidate_index"], 0)

    def test_greedy_continues_active_task(self):
        action = GreedyUtilityPolicy().action(
            2, observation(), {"continue_current_task": True}
        )
        self.assertEqual(action["task_action"], {"type": "CONTINUE_CURRENT_TASK"})

    def test_greedy_replans_resource_block_instead_of_retrying(self):
        action = GreedyUtilityPolicy().action(
            2,
            observation(skill={"status": "BLOCKED", "reason": "RESOURCES_SHORT"}),
            {"continue_current_task": True, "abandon": True},
        )
        self.assertEqual(
            action["task_action"],
            {"type": "ABANDON", "reason": "resources_short_replan"},
        )

    def test_greedy_generalizes_blocked_replan_and_bounds_switches(self):
        policy = GreedyUtilityPolicy()
        mask = {"continue_current_task": True, "abandon": True}
        for tick in (10, 20, 30):
            action = policy.action(
                1,
                observation(
                    skill={"status": "BLOCKED", "reason": "INVALID_TARGET"},
                    team={"tick": tick},
                ),
                mask,
            )
            self.assertEqual(
                action["task_action"]["reason"], "blocked_replan:invalid_target"
            )
        bounded = policy.action(
            1,
            observation(
                skill={"status": "BLOCKED", "reason": "INVALID_TARGET"},
                team={"tick": 40},
            ),
            mask,
        )
        self.assertEqual(bounded["task_action"], {"type": "CONTINUE_CURRENT_TASK"})

    def test_team_bundle_rebalances_one_defender_to_supply(self):
        policy = GreedyUtilityPolicy()
        candidates = [
            {"index": 0, "task_type": "SUPPLY_TURRET", "utility": 2.0},
            {"index": 1, "task_type": "DEFEND_REGION", "utility": 3.0},
        ]
        team = {"tick": 100, "enemy_count": 3, "defense_ammo_coverage": 0.5}
        observations = [
            observation(candidates=candidates, skill={"type": "DEFEND"}, team=team)
            for _ in range(3)
        ]
        masks = [
            {
                "continue_current_task": True,
                "abandon": True,
                "candidate_task": [False, False],
            }
            for _ in range(3)
        ]
        actions = policy.actions(observations, masks)
        self.assertEqual(
            actions[2]["task_action"],
            {"type": "ABANDON", "reason": "readiness_rebalance"},
        )
        self.assertEqual(actions[0]["task_action"]["type"], "CONTINUE_CURRENT_TASK")
        self.assertEqual(actions[1]["task_action"]["type"], "CONTINUE_CURRENT_TASK")

        selected = policy.action(
            2,
            observation(candidates=candidates, team=team),
            {"candidate_task": [True, True]},
        )
        self.assertEqual(selected["task_action"]["candidate_index"], 0)
        policy.observe_action_results([{"agent_id": 2, "accepted": True}])
        next_supply = policy.action(
            2,
            observation(candidates=candidates, team=team),
            {"candidate_task": [True, True]},
        )
        self.assertEqual(next_supply["task_action"]["candidate_index"], 0)

        logistics_idle = policy.action(
            2,
            observation(
                candidates=candidates,
                team={**team, "defense_ammo_coverage": 1.0},
            ),
            {"candidate_task": [False, True]},
        )
        self.assertEqual(logistics_idle["task_action"], {"type": "WAIT"})

        after_wave = policy.action(
            2,
            observation(candidates=candidates, team={**team, "enemy_count": 0}),
            {"candidate_task": [False, True]},
        )
        self.assertEqual(after_wave["task_action"]["candidate_index"], 1)

    def test_active_supplier_is_not_preempted_by_wave(self):
        action = GreedyUtilityPolicy().action(
            2,
            observation(
                skill={"type": "SUPPLY", "status": "RUNNING"},
                team={"tick": 100, "enemy_count": 3},
            ),
            {"continue_current_task": True, "abandon": True},
        )
        self.assertEqual(action["task_action"], {"type": "CONTINUE_CURRENT_TASK"})

    def test_roles_choose_distinct_preferred_work(self):
        policy = RoleAssignmentPolicy(("miner", "builder"))
        mask = {"candidate_task": [True, True, True]}
        miner = policy.action(0, observation(), mask)
        builder = policy.action(1, observation(), mask)
        self.assertEqual(miner["task_action"]["candidate_index"], 0)
        self.assertEqual(builder["task_action"]["candidate_index"], 1)

    def test_pure_greedy_has_no_team_rebalance_and_releases_blocks(self):
        policy = PureGreedyUtilityPolicy()
        blocked = policy.action(
            0,
            observation(skill={"status": "BLOCKED", "reason": "STUCK"}),
            {"continue_current_task": True, "abandon": True},
        )
        self.assertEqual(
            blocked["task_action"],
            {"type": "ABANDON", "reason": "baseline_blocked:stuck"},
        )

    def test_random_valid_is_seeded_and_version_stable(self):
        mask = {"candidate_task": [True, True, True]}
        first = RandomValidPolicy(42)
        second = RandomValidPolicy(42)
        trace_a = [first.action(0, observation(), mask) for _ in range(8)]
        trace_b = [second.action(0, observation(), mask) for _ in range(8)]
        self.assertEqual(trace_a, trace_b)
        self.assertEqual(
            [action["task_action"]["candidate_index"] for action in trace_a],
            [2, 1, 0, 2, 0, 1, 0, 2],
        )

    def test_helper_flow_chooses_nearest_idle_and_builds_typed_actions(self):
        observations = [observation(0), observation(10), observation(2)]
        masks = [
            {"continue_current_task": True},
            {"continue_current_task": False},
            {"continue_current_task": False},
        ]
        helper = HelperCoordinator.nearest_idle_helper(0, observations, masks)
        self.assertEqual(helper, 2)
        self.assertEqual(
            HelperCoordinator.request(0)["task_action"]["type"], "REQUEST_HELP"
        )
        self.assertEqual(
            HelperCoordinator.offer(helper, 3)["task_action"]["task_index"], 3
        )
        self.assertEqual(
            HelperCoordinator.accept(0)["task_action"]["type"], "ACCEPT_HELP"
        )


if __name__ == "__main__":
    unittest.main()
