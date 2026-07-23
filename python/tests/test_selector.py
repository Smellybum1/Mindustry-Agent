import math
import unittest
from copy import deepcopy

from mindustry_agents.training.selector import (
    BOUNDARY_REASONS,
    FEATURE_SCHEMA_V2,
    SelectorFeatureError,
    SelectorHistory,
    build_selector_features,
    selector_action,
)


def candidate(index=0, task_type="BUILD_LINE"):
    return {
        "index": index,
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


def boundary():
    candidates = [candidate(), candidate(1, "WAIT")]
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
        "task_candidates": candidates,
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
    mask = {
        "candidate_task": [True, True],
        "continue_current_task": False,
        "wait": True,
        "abandon": False,
    }
    return [observation, observation, observation], [mask, mask, mask], metadata


class TestSelectorFeatures(unittest.TestCase):
    def test_lagged_boundary_is_zero_initialized_bounded_and_reset_local(self):
        observations, masks, metadata = boundary()
        history = SelectorHistory()
        first = build_selector_features(
            observations,
            masks,
            metadata,
            history=history,
            feature_schema=FEATURE_SCHEMA_V2,
        )
        self.assertEqual(len(first.scalars), 160)
        self.assertEqual(first.scalars[56:], [0.0] * 104)

        history.record_boundary(first, 9)
        frozen_scalars = first.scalars[:56]
        frozen_mean = [
            (first.candidates[0][index] + first.candidates[1][index]) / 2
            for index in range(37)
        ]
        first.scalars[0] = 999.0
        first.candidates[0][0] = 999.0
        second = build_selector_features(
            observations,
            masks,
            metadata,
            history=history,
            feature_schema=FEATURE_SCHEMA_V2,
        )
        self.assertEqual(second.scalars[56:112], frozen_scalars)
        self.assertEqual(second.scalars[112:149], frozen_mean)
        self.assertEqual(second.scalars[149], 0.25)
        self.assertEqual(second.scalars[150:160], [0.0] * 9 + [1.0])

        reset = build_selector_features(
            observations,
            masks,
            metadata,
            history=SelectorHistory(),
            feature_schema=FEATURE_SCHEMA_V2,
        )
        self.assertEqual(reset.scalars[56:], [0.0] * 104)

    def test_exact_shapes_order_masks_and_history(self):
        observations, masks, metadata = boundary()
        history = SelectorHistory()
        history.record_selection("HARVEST_RESOURCE", 300)
        result = build_selector_features(
            observations,
            masks,
            metadata,
            history=history,
            boundary_reasons=["wave_spawn", "core_damage"],
        )
        self.assertEqual((len(result.candidates), len(result.candidates[0])), (8, 37))
        self.assertEqual(len(result.scalars), 56)
        self.assertEqual(result.candidate_present, [True, True] + [False] * 6)
        self.assertEqual(result.action_mask, [True] + [False] * 7 + [False, True])
        self.assertTrue(result.policy_loss_mask)
        self.assertEqual(result.scalars[-7:], [
            1.0 if reason in {"wave_spawn", "core_damage"} else 0.0
            for reason in BOUNDARY_REASONS
        ])
        self.assertTrue(all(math.isfinite(value) for row in result.candidates for value in row))
        self.assertTrue(all(0.0 <= value <= 1.0 for value in result.scalars))

    def test_forced_blocked_and_terminal_wait_are_excluded_from_loss(self):
        observations, masks, metadata = boundary()
        observations[0] = dict(observations[0])
        observations[0]["skill"] = {"status": "BLOCKED", "reason": "STUCK", "progress": 0}
        masks[0] = dict(masks[0], abandon=True, continue_current_task=True)
        forced = build_selector_features(observations, masks, metadata)
        self.assertEqual(forced.forced_task_action["type"], "ABANDON")
        self.assertFalse(forced.policy_loss_mask)
        terminal = build_selector_features(observations, masks, metadata, terminated=True)
        self.assertEqual(terminal.action_mask, [False] * 9 + [True])
        self.assertEqual(terminal.forced_task_action, {"type": "WAIT"})

    def test_partner_intent_raises_only_exact_task_duplication_risk(self):
        observations, masks, metadata = boundary()
        observations[0]["task_candidates"][0]["task_id"] = "build-line:alpha"
        risk_index = 9

        matched = build_selector_features(
            observations,
            masks,
            metadata,
            fixed_partner_intended_task_ids=["build-line:alpha"],
        )
        unmatched = build_selector_features(
            observations,
            masks,
            metadata,
            fixed_partner_intended_task_ids=["build-line:beta"],
        )

        self.assertEqual(matched.candidates[0][risk_index], 1.0)
        self.assertEqual(unmatched.candidates[0][risk_index], 0.0)
        self.assertEqual(len(matched.candidates[0]), 37)

    def test_partner_intent_is_idempotent_and_does_not_mutate_inputs(self):
        observations, masks, metadata = boundary()
        observations[0]["task_candidates"][0]["task_id"] = "build-line:alpha"
        before_observations = deepcopy(observations)
        before_masks = deepcopy(masks)
        before_metadata = deepcopy(metadata)

        result = build_selector_features(
            observations,
            masks,
            metadata,
            fixed_partner_intended_task_ids=[
                "build-line:alpha",
                "build-line:alpha",
            ],
        )

        self.assertEqual(result.candidates[0][9], 1.0)
        self.assertEqual(observations, before_observations)
        self.assertEqual(masks, before_masks)
        self.assertEqual(metadata, before_metadata)

    def test_partner_intent_malformed_ids_fail_closed(self):
        malformed_ids = (None, "", 7, {"task": "build-line:alpha"})
        observations, masks, metadata = boundary()
        missing = build_selector_features(
            observations,
            masks,
            metadata,
            fixed_partner_intended_task_ids=["build-line:alpha"],
        )
        self.assertEqual(missing.candidates[0][9], 0.0)

        for candidate_task_id in malformed_ids:
            with self.subTest(candidate_task_id=candidate_task_id):
                observations, masks, metadata = boundary()
                observations[0]["task_candidates"][0]["task_id"] = candidate_task_id
                result = build_selector_features(
                    observations,
                    masks,
                    metadata,
                    fixed_partner_intended_task_ids=[
                        None,
                        "",
                        7,
                        "build-line:alpha",
                    ],
                )
                self.assertEqual(result.candidates[0][9], 0.0)

        observations, masks, metadata = boundary()
        observations[0]["task_candidates"][0]["task_id"] = "build-line:alpha"
        malformed_intents = build_selector_features(
            observations,
            masks,
            metadata,
            fixed_partner_intended_task_ids=[None, "", 7, {"task": "other"}],
        )
        self.assertEqual(malformed_intents.candidates[0][9], 0.0)

    def test_omitted_partner_intent_preserves_exact_features(self):
        observations, masks, metadata = boundary()
        observations[0]["task_candidates"][0]["task_id"] = "build-line:alpha"

        omitted = build_selector_features(observations, masks, metadata)
        malformed_outer = build_selector_features(
            observations,
            masks,
            metadata,
            fixed_partner_intended_task_ids="build-line:alpha",
        )
        malformed_mapping = build_selector_features(
            observations,
            masks,
            metadata,
            fixed_partner_intended_task_ids={"build-line:alpha": True},
        )
        empty = build_selector_features(
            observations,
            masks,
            metadata,
            fixed_partner_intended_task_ids=[],
        )

        self.assertEqual(omitted, empty)
        self.assertEqual(omitted, malformed_outer)
        self.assertEqual(omitted, malformed_mapping)

    def test_schema_failures_are_loud(self):
        observations, masks, metadata = boundary()
        observations[0]["task_candidates"][0]["task_type"] = "UNKNOWN"
        with self.assertRaisesRegex(SelectorFeatureError, "unknown task type"):
            build_selector_features(observations, masks, metadata)
        observations, masks, metadata = boundary()
        observations[0]["task_candidates"][0]["utility_features"]["danger"] = math.nan
        with self.assertRaisesRegex(SelectorFeatureError, "not finite"):
            build_selector_features(observations, masks, metadata)
        observations, masks, metadata = boundary()
        masks[0] = {"candidate_task": [False, False]}
        with self.assertRaisesRegex(SelectorFeatureError, "no legal action"):
            build_selector_features(observations, masks, metadata)

    def test_typed_action_mapping_rejects_wait_candidate(self):
        observations, _, _ = boundary()
        candidates = observations[0]["task_candidates"]
        self.assertEqual(
            selector_action(0, candidates),
            {"type": "SELECT_CANDIDATE_TASK", "candidate_index": 0},
        )
        self.assertEqual(selector_action(8, candidates), {"type": "CONTINUE_CURRENT_TASK"})
        self.assertEqual(selector_action(9, candidates), {"type": "WAIT"})
        with self.assertRaises(SelectorFeatureError):
            selector_action(1, candidates)


if __name__ == "__main__":
    unittest.main()
