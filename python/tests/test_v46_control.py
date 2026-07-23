"""Focused ADR-0063 feature, translation, and governance checks."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

from mindustry_agents.training.selector import (
    CONTROL_SCHEMA_V1,
    CONTROL_SCHEMA_V2,
    FEATURE_SCHEMA_V2,
    FEATURE_SCHEMA_V3,
    SelectorFeatureError,
    SelectorHistory,
    build_selector_features,
    expected_control_schema,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/training/m8-selector-v46-expert-defer-control.json"


def _candidate(index: int, task_type: str) -> dict[str, object]:
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


def _boundary() -> tuple[list[dict], list[dict], dict]:
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
        "task_candidates": [
            _candidate(0, "BUILD_LINE"),
            _candidate(1, "WAIT"),
        ],
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
    return [observation] * 3, [mask] * 3, metadata


def _features(expert_index: int, **kwargs):
    observations, masks, metadata = _boundary()
    return build_selector_features(
        observations,
        masks,
        metadata,
        feature_schema=FEATURE_SCHEMA_V3,
        control_schema=CONTROL_SCHEMA_V2,
        expert_action_index=expert_index,
        **kwargs,
    )


def test_v46_feature_shape_one_hot_and_defer_legality() -> None:
    features = _features(0)
    assert len(features.scalars) == 170
    assert features.scalars[56:160] == [0.0] * 104
    assert features.scalars[160:] == [1.0] + [0.0] * 9
    assert features.action_mask == (
        [True] + [False] * 7 + [False, True, True]
    )
    assert features.policy_loss_mask

    wait = _features(9)
    assert wait.scalars[160:] == [0.0] * 9 + [1.0]
    assert not wait.action_mask[10]


def test_v46_forced_and_single_action_boundaries_cannot_defer() -> None:
    observations, masks, metadata = _boundary()
    observations[0] = dict(observations[0])
    observations[0]["skill"] = {
        "status": "BLOCKED",
        "reason": "STUCK",
        "progress": 0,
    }
    masks[0] = dict(masks[0], abandon=True, continue_current_task=True)
    forced = build_selector_features(
        observations,
        masks,
        metadata,
        feature_schema=FEATURE_SCHEMA_V3,
        control_schema=CONTROL_SCHEMA_V2,
        expert_action_index=0,
    )
    assert not forced.action_mask[10]
    assert not forced.policy_loss_mask

    observations, masks, metadata = _boundary()
    masks[0] = dict(
        masks[0],
        candidate_task=[True, False],
        wait=False,
    )
    single = build_selector_features(
        observations,
        masks,
        metadata,
        feature_schema=FEATURE_SCHEMA_V3,
        control_schema=CONTROL_SCHEMA_V2,
        expert_action_index=0,
    )
    assert sum(single.action_mask) == 1
    assert not single.action_mask[10]
    assert not single.policy_loss_mask


def test_v46_feature_and_control_schema_pairing_fails_closed() -> None:
    observations, masks, metadata = _boundary()
    for feature_schema, control_schema in (
        (FEATURE_SCHEMA_V2, CONTROL_SCHEMA_V2),
        (FEATURE_SCHEMA_V3, CONTROL_SCHEMA_V1),
    ):
        with pytest.raises(SelectorFeatureError, match="schema mismatch"):
            build_selector_features(
                observations,
                masks,
                metadata,
                feature_schema=feature_schema,
                control_schema=control_schema,
                expert_action_index=0,
            )
    with pytest.raises(SelectorFeatureError, match="missing or invalid"):
        build_selector_features(
            observations,
            masks,
            metadata,
            feature_schema=FEATURE_SCHEMA_V3,
            control_schema=CONTROL_SCHEMA_V2,
        )


def test_v46_history_records_effective_ordinary_action() -> None:
    first = _features(0)
    history = SelectorHistory()
    history.record_boundary(first, 0)
    second = _features(8, history=history)
    assert second.scalars[150:160] == [1.0] + [0.0] * 9
    assert second.scalars[160:] == [0.0] * 8 + [1.0, 0.0]


def test_v46_control_declaration_is_exact() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert expected_control_schema(config) == CONTROL_SCHEMA_V2
    malformed = json.loads(CONFIG.read_text(encoding="utf-8"))
    malformed["control_actions"]["forced_safety_override"] = True
    with pytest.raises(ValueError, match="declaration mismatch"):
        expected_control_schema(malformed)


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="RL extra is not installed",
)
def test_v46_control_translation_and_teacher_space_are_bounded() -> None:
    import torch

    from mindustry_agents.training.ppo_selector import (
        _ordinary_teacher_logits,
        _resolve_policy_control_action,
    )

    candidates = [_candidate(0, "BUILD_LINE"), _candidate(1, "WAIT")]
    scripted = {
        "agent_id": 0,
        "task_action": {"type": "SELECT_CANDIDATE_TASK", "candidate_index": 0},
    }
    translated, effective, deferred = _resolve_policy_control_action(
        10,
        scripted,
        candidates,
        control_schema=CONTROL_SCHEMA_V2,
    )
    assert translated is scripted
    assert effective == 0
    assert deferred

    ordinary, effective, deferred = _resolve_policy_control_action(
        8,
        scripted,
        candidates,
        control_schema=CONTROL_SCHEMA_V2,
    )
    assert ordinary["task_action"] == {"type": "CONTINUE_CURRENT_TASK"}
    assert effective == 8
    assert not deferred

    with pytest.raises(ValueError, match="requires the V2"):
        _resolve_policy_control_action(
            10,
            scripted,
            candidates,
            control_schema=CONTROL_SCHEMA_V1,
        )
    wait = {"agent_id": 0, "task_action": {"type": "WAIT"}}
    translated, effective, deferred = _resolve_policy_control_action(
        10,
        wait,
        candidates,
        control_schema=CONTROL_SCHEMA_V2,
    )
    assert translated is wait
    assert effective == 9
    assert deferred

    logits = torch.arange(22, dtype=torch.float32).reshape(2, 11)
    ordinary_logits = _ordinary_teacher_logits(logits)
    assert ordinary_logits.shape == (2, 10)
    assert torch.equal(ordinary_logits, logits[:, :10])
    logits[:, 10] = math.inf
    assert torch.equal(_ordinary_teacher_logits(logits), ordinary_logits)


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="RL extra is not installed",
)
def test_v46_checkpoint_selection_enforces_inclusive_defer_cap() -> None:
    from mindustry_agents.training.ppo_selector import (
        _dev_checkpoint_selection_policy,
        _select_dev_checkpoint_index,
    )

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    policy = _dev_checkpoint_selection_policy(config)
    rows = [
        {
            "update": 1,
            "wins": 10,
            "mean_return": 10.0,
            "mean_core_health": 1000.0,
            "mean_idle_fraction": 0.1,
            "mean_expert_defer_fraction": 0.2500001,
        },
        {
            "update": 2,
            "wins": 9,
            "mean_return": 8.0,
            "mean_core_health": 900.0,
            "mean_idle_fraction": 0.1,
            "mean_expert_defer_fraction": 0.25,
        },
    ]
    assert _select_dev_checkpoint_index(rows, policy) == 1

    invalid = json.loads(CONFIG.read_text(encoding="utf-8"))
    invalid["dev_checkpoint_selection"][
        "maximum_mean_expert_defer_fraction_inclusive"
    ] = 1.0
    with pytest.raises(ValueError, match="expert-defer"):
        _dev_checkpoint_selection_policy(invalid)


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="RL extra is not installed",
)
def test_v46_promotion_gate_requires_valid_bounded_telemetry() -> None:
    from mindustry_agents.training.promotion import (
        CANDIDATE_POLICY,
        _expert_defer_control_gate,
    )

    config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def record(count: int, decisions: int = 10) -> dict:
        return {
            "manifest": {"policy": CANDIDATE_POLICY},
            "control": {
                "schema": CONTROL_SCHEMA_V2,
                "expert_defer_opportunities": 5,
                "expert_defer_count": count,
                "expert_defer_policy_decisions": decisions,
                "expert_defer_fraction": count / decisions if decisions else 0.0,
            },
        }

    gate = _expert_defer_control_gate([record(2), record(3)], config)
    assert gate is not None
    assert gate["mean_expert_defer_fraction"] == 0.25
    assert gate["passed"]

    gate = _expert_defer_control_gate([record(2), record(4)], config)
    assert gate is not None
    assert not gate["passed"]

    with pytest.raises(RuntimeError, match="incomplete"):
        _expert_defer_control_gate(
            [{"manifest": {"policy": CANDIDATE_POLICY}}],
            config,
        )
    invalid = record(2)
    invalid["control"]["expert_defer_fraction"] = 0.3
    with pytest.raises(RuntimeError, match="invalid"):
        _expert_defer_control_gate([invalid], config)


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="RL extra is not installed",
)
def test_v46_final_preflight_rejects_nonfinite_or_incomplete_gate() -> None:
    from mindustry_agents.training.promotion_final import (
        _validate_expert_defer_preflight,
    )

    control = {
        "schema": CONTROL_SCHEMA_V2,
        "episodes": 10,
        "mean_expert_defer_fraction": 0.25,
        "maximum_mean_expert_defer_fraction_inclusive": 0.25,
        "passed": True,
    }
    _validate_expert_defer_preflight(control, expected_limit=0.25)
    for malformed in (
        control | {"episodes": 0},
        control | {"mean_expert_defer_fraction": math.nan},
        control | {"mean_expert_defer_fraction": -0.1},
        control | {"mean_expert_defer_fraction": 0.2500001},
        control | {"maximum_mean_expert_defer_fraction_inclusive": math.inf},
        control | {"passed": False},
    ):
        with pytest.raises(ValueError, match="did not pass"):
            _validate_expert_defer_preflight(malformed, expected_limit=0.25)
