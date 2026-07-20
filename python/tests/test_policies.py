import unittest

from mindustry_agents.policies import (
    GreedyUtilityPolicy,
    HelperCoordinator,
    RoleAssignmentPolicy,
)


def observation(x=0.0, candidates=None):
    return {
        "unit": {"x": x, "y": 0.0},
        "task_candidates": candidates
        or [
            {"index": 0, "task_type": "HARVEST_RESOURCE", "utility": 2.0},
            {"index": 1, "task_type": "BUILD_SCHEMATIC", "utility": 3.0},
            {"index": 2, "task_type": "WAIT", "utility": 0.1},
        ],
    }


class TestScriptedPolicies(unittest.TestCase):
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

    def test_roles_choose_distinct_preferred_work(self):
        policy = RoleAssignmentPolicy(("miner", "builder"))
        mask = {"candidate_task": [True, True, True]}
        miner = policy.action(0, observation(), mask)
        builder = policy.action(1, observation(), mask)
        self.assertEqual(miner["task_action"]["candidate_index"], 0)
        self.assertEqual(builder["task_action"]["candidate_index"], 1)

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
