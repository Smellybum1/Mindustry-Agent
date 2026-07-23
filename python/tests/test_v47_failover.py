"""Focused ADR-0065 single-brain death-failover checks."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from mindustry_agents.training.selector import CONTROL_SCHEMA_V2, SelectorHistory


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT
    / "configs"
    / "training"
    / "m8-selector-v47-single-brain-death-failover.json"
)
V46_CONFIG = (
    ROOT / "configs" / "training" / "m8-selector-v46-expert-defer-control.json"
)


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def _observations(*dead: bool) -> list[dict]:
    return [
        {
            "unit": {"dead": value},
            "task_candidates": [{"task_id": f"task-{agent_id}"}],
        }
        for agent_id, value in enumerate(dead)
    ]


def test_v47_failover_config_is_exact_and_legacy_optional() -> None:
    from mindustry_agents.training.ppo_selector import (
        LEARNED_SEAT_FAILOVER_SCHEMA,
        _learned_seat_failover,
    )

    config = _config()
    failover = _learned_seat_failover(config)
    assert failover is not None
    assert failover["schema"] == LEARNED_SEAT_FAILOVER_SCHEMA
    assert failover["maximum_active_learned_seats"] == 1
    assert _learned_seat_failover(
        json.loads(V46_CONFIG.read_text(encoding="utf-8"))
    ) is None

    for key, value in (
        ("selection", "highest_health"),
        ("switch_trigger", "model_choice"),
        ("maximum_active_learned_seats", 2),
        ("history_on_switch", "retain"),
        ("forced_safety_override", True),
    ):
        malformed = _config()
        malformed["learned_seat_failover"][key] = value
        with pytest.raises(ValueError, match="learned_seat_failover"):
            _learned_seat_failover(malformed)


def test_v47_active_seat_is_sticky_lowest_alive_and_history_resets() -> None:
    from mindustry_agents.training.ppo_selector import (
        _advance_learned_seat,
        _learned_seat_failover,
    )

    failover = _learned_seat_failover(_config())
    history = SelectorHistory(previous_action_index=3)

    active, retained, transfer = _advance_learned_seat(
        _observations(False, False, False), 0, history, failover
    )
    assert (active, retained, transfer) == (0, history, None)
    assert retained is history

    active, reset, transfer = _advance_learned_seat(
        _observations(True, False, False), 0, history, failover
    )
    assert active == 1
    assert reset is not history
    assert reset == SelectorHistory()
    assert transfer == {
        "from_agent_id": 0,
        "to_agent_id": 1,
        "reason": "active_agent_dead",
    }

    active, retained, transfer = _advance_learned_seat(
        _observations(True, False, False), 1, reset, failover
    )
    assert (active, retained, transfer) == (1, reset, None)

    active, _, transfer = _advance_learned_seat(
        _observations(True, True, False), 1, reset, failover
    )
    assert active == 2
    assert transfer == {
        "from_agent_id": 1,
        "to_agent_id": 2,
        "reason": "active_agent_dead",
    }

    active, retained, transfer = _advance_learned_seat(
        _observations(True, True, True), 2, reset, failover
    )
    assert (active, retained, transfer) == (2, reset, None)


def test_v47_dynamic_partner_intent_excludes_active_and_dead_agents() -> None:
    from mindustry_agents.training.ppo_selector import (
        _fixed_partner_intended_task_ids,
        _partner_intent_duplication_risk,
    )

    config = _config()
    intervention = _partner_intent_duplication_risk(config)
    actions = [
        {
            "agent_id": agent_id,
            "task_action": {
                "type": "SELECT_CANDIDATE_TASK",
                "candidate_index": 0,
            },
        }
        for agent_id in range(3)
    ]
    observations = _observations(True, False, False)
    assert _fixed_partner_intended_task_ids(
        actions,
        observations,
        intervention,
        active_agent_id=1,
    ) == ("task-2",)

    malformed = _config()
    malformed.pop("learned_seat_failover")
    with pytest.raises(ValueError, match="partner_intent_duplication_risk"):
        _partner_intent_duplication_risk(malformed)


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="RL extra is not installed",
)
def test_v47_active_seat_translation_and_lineage_are_explicit() -> None:
    from mindustry_agents.training.checkpoint_lineage import (
        _expected_lineage_schemas,
    )
    from mindustry_agents.training.ppo_selector import (
        LEARNED_SEAT_FAILOVER_SCHEMA,
        _resolve_policy_control_action,
    )

    candidates = [{"task_type": "BUILD_LINE"}]
    scripted = {
        "agent_id": 2,
        "task_action": {"type": "SELECT_CANDIDATE_TASK", "candidate_index": 0},
    }
    ordinary, effective, deferred = _resolve_policy_control_action(
        8,
        scripted,
        candidates,
        control_schema=CONTROL_SCHEMA_V2,
        agent_id=2,
    )
    assert ordinary == {
        "agent_id": 2,
        "task_action": {"type": "CONTINUE_CURRENT_TASK"},
    }
    assert effective == 8
    assert not deferred

    expert, effective, deferred = _resolve_policy_control_action(
        10,
        scripted,
        candidates,
        control_schema=CONTROL_SCHEMA_V2,
        agent_id=2,
    )
    assert expert is scripted
    assert effective == 0
    assert deferred

    assert _expected_lineage_schemas(_config()) == {
        "feature": "selector_features_v3_expert_defer",
        "reward": "selector_reward_v2",
        "model": "selector_actor_critic_v5_expert_defer_control",
        "control": "selector_control_actions_v2_expert_defer",
        "seat_control": LEARNED_SEAT_FAILOVER_SCHEMA,
    }


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="RL extra is not installed",
)
def test_v47_promotion_and_final_gates_require_one_brain() -> None:
    from mindustry_agents.training.promotion import (
        CANDIDATE_POLICY,
        GREEDY_MIXED,
        RANDOM_MIXED,
        _learned_seat_failover_gate,
    )
    from mindustry_agents.training.promotion_final import (
        _validate_learned_seat_failover_preflight,
    )

    def record(policy: str, transfers: list[dict] | None = None) -> dict:
        transfers = transfers or []
        return {
            "manifest": {"policy": policy},
            "seat_control": {
                "schema": "single_learned_brain_death_failover_v1",
                "initial_agent_id": 0,
                "final_agent_id": (
                    transfers[-1]["to_agent_id"] if transfers else 0
                ),
                "transfer_count": len(transfers),
                "transfers": transfers,
                "maximum_simultaneous_learned_seats": 1,
            },
        }

    transfer = [
        {
            "tick": 3000,
            "from_agent_id": 0,
            "to_agent_id": 1,
            "reason": "active_agent_dead",
        }
    ]
    gate = _learned_seat_failover_gate(
        [
            record(CANDIDATE_POLICY, transfer),
            record(GREEDY_MIXED, transfer),
            record(RANDOM_MIXED),
        ],
        _config(),
    )
    assert gate == {
        "schema": "single_learned_brain_death_failover_v1",
        "candidate_episodes": 1,
        "matched_episodes": 2,
        "candidate_transfers": 1,
        "matched_transfers": 1,
        "maximum_simultaneous_learned_seats": 1,
        "passed": True,
    }
    _validate_learned_seat_failover_preflight(gate)

    invalid = record(CANDIDATE_POLICY)
    invalid["seat_control"]["maximum_simultaneous_learned_seats"] = 2
    with pytest.raises(RuntimeError, match="single-brain"):
        _learned_seat_failover_gate([invalid], _config())
    with pytest.raises(ValueError, match="single-brain"):
        _validate_learned_seat_failover_preflight(gate | {"passed": False})
