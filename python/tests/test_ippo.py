import importlib.util
import unittest
from copy import deepcopy


def _candidate(index=0, task_type="BUILD_LINE"):
    return {
        "index": index,
        "task_id": f"task:{index}",
        "task_type": task_type,
        "priority": 0.75,
        "estimated_ticks": 600,
        "estimated_cost": {"copper": 31},
        "helpers_requested": 1,
        "dependency_count": 0,
        "exclusive": True,
        "semantic_task_active": False,
        "semantic_task_owned_by_other": False,
        "utility_features": {
            "team_value": 0.75,
            "urgency": 1.0,
            "capability_fit": 1.0,
            "role_fit": 1.0,
            "proximity": 0.5,
            "help_synergy": 1.0,
            "human_priority": 0.0,
            "travel_cost": 0.5,
            "resource_cost": 0.2,
            "duplication_risk": 0.0,
            "switching_cost": 0.0,
            "danger": 0.0,
            "uncertainty": 0.0,
        },
    }


def _boundary():
    team = {
        "tick": 600,
        "wave": 1,
        "copper": 250,
        "core_health": 1100,
        "core_copper_inflow_per_s": 0.3,
        "core_copper_inflow_target_per_s": 0.6,
        "time_to_next_wave": 2100,
        "enemy_count": 0,
        "enemy_total_health": 0,
        "enemy_nearest_core_dist": -1,
        "line_operational": False,
        "defense_ammo_coverage": 0.2,
        "defense_health_coverage": 1.0,
        "defense_turret_coverage": 0.5,
        "defense_readiness": 0.2,
        "broken_block_count": 0,
    }
    observation = {
        "unit": {
            "x": 216,
            "y": 192,
            "health": 150,
            "max_health": 150,
            "dead": False,
            "item_amount": 10,
            "item_capacity": 30,
            "build_queue_depth": 0,
            "build_plan_progress": 0,
        },
        "skill": {"status": "READY", "progress": 0},
        "team": team,
        "task_candidates": [_candidate(), _candidate(1, "WAIT")],
    }
    mask = {
        "candidate_task": [True, True],
        "continue_current_task": False,
        "wait": True,
        "abandon": False,
    }
    metadata = {
        "width": 48,
        "height": 48,
        "tile_size": 8,
        "tick_cap": 9000,
        "wave_count": 3,
        "wave_ticks": [2700, 4500, 6300],
        "copper_budget": 4000,
        "core_health_max": 1100,
    }
    return (
        [deepcopy(observation) for _ in range(3)],
        [deepcopy(mask) for _ in range(3)],
        metadata,
    )


@unittest.skipIf(importlib.util.find_spec("torch") is None, "RL extra is not installed")
class TestSharedRecurrentIPPO(unittest.TestCase):
    def test_pinned_shapes_seed_and_role_sensitivity(self):
        import torch

        from mindustry_agents.training.ippo import (
            SharedRecurrentSelector,
            model_state_digest,
        )

        first = SharedRecurrentSelector(9601)
        second = SharedRecurrentSelector(9601)
        self.assertEqual(model_state_digest(first), model_state_digest(second))
        candidates = torch.zeros((3, 8, 37))
        scalars = torch.zeros((3, 160))
        present = torch.tensor([[True] * 3 + [False] * 5] * 3)
        mask = torch.tensor([[True, False, True] + [False] * 6 + [True]] * 3)
        hidden = torch.zeros((3, 64))
        raw, masked, value, next_hidden = first(
            candidates,
            scalars,
            present,
            mask,
            torch.tensor([0, 1, 2]),
            hidden,
        )
        self.assertEqual(tuple(raw.shape), (3, 10))
        self.assertEqual(tuple(value.shape), (3,))
        self.assertEqual(tuple(next_hidden.shape), (3, 64))
        self.assertTrue((masked[:, 1] < -1e30).all())
        self.assertFalse(torch.equal(next_hidden[0], next_hidden[1]))
        self.assertFalse(torch.equal(next_hidden[1], next_hidden[2]))

    def test_one_model_all_seats_ordered_atomic_bundle(self):
        from mindustry_agents.training.ippo import (
            SharedRecurrentSelector,
            SharedSeatState,
            decide_all_seats,
        )

        observations, masks, metadata = _boundary()
        model = SharedRecurrentSelector(9601)
        state = SharedSeatState.fresh()
        teacher = [
            {
                "agent_id": agent_id,
                "task_action": {
                    "type": "SELECT_CANDIDATE_TASK",
                    "candidate_index": 0,
                },
            }
            for agent_id in range(3)
        ]
        decision = decide_all_seats(
            model,
            state,
            observations,
            masks,
            metadata,
            evaluation=True,
            teacher_actions=teacher,
        )
        self.assertEqual(decision.agent_actions, teacher)
        self.assertEqual(decision.evaluation_order, (0, 1, 2))
        self.assertEqual([row["agent_id"] for row in decision.agent_actions], [0, 1, 2])
        self.assertEqual(len({decision.model_state_sha256}), 1)
        self.assertTrue(all(state.hidden[index].abs().sum() > 0 for index in range(3)))

    def test_dead_seat_resets_only_its_private_state(self):
        import torch

        from mindustry_agents.training.ippo import SharedSeatState

        observations, _, _ = _boundary()
        state = SharedSeatState.fresh()
        state.hidden[:] = 1.0
        state.histories[0].previous_task_type = "BUILD_LINE"
        state.histories[1].previous_task_type = "DEFEND_REGION"
        state.histories[2].previous_task_type = "HARVEST_RESOURCE"
        observations[1]["unit"]["dead"] = True
        state.observe_lifecycle(observations)
        self.assertTrue(torch.equal(state.hidden[0], torch.ones(64)))
        self.assertTrue(torch.equal(state.hidden[1], torch.zeros(64)))
        self.assertTrue(torch.equal(state.hidden[2], torch.ones(64)))
        self.assertEqual(state.histories[0].previous_task_type, "BUILD_LINE")
        self.assertIsNone(state.histories[1].previous_task_type)
        self.assertEqual(state.histories[2].previous_task_type, "HARVEST_RESOURCE")

    def test_teacher_bundle_must_be_agent_ordered(self):
        from mindustry_agents.training.ippo import (
            SharedRecurrentSelector,
            SharedSeatState,
            decide_all_seats,
        )

        observations, masks, metadata = _boundary()
        teacher = [
            {"agent_id": 1, "task_action": {"type": "WAIT"}},
            {"agent_id": 0, "task_action": {"type": "WAIT"}},
            {"agent_id": 2, "task_action": {"type": "WAIT"}},
        ]
        with self.assertRaisesRegex(ValueError, "agent-id order"):
            decide_all_seats(
                SharedRecurrentSelector(9601),
                SharedSeatState.fresh(),
                observations,
                masks,
                metadata,
                evaluation=True,
                teacher_actions=teacher,
            )


if __name__ == "__main__":
    unittest.main()
