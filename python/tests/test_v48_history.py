"""Focused ADR-0066 per-seat structured-history cache checks."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from mindustry_agents.training.selector import (
    SelectorFeatures,
    SelectorHistory,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT
    / "configs"
    / "training"
    / "m8-selector-v48-per-seat-history-cache.json"
)


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def _observations(*dead: bool) -> list[dict]:
    return [
        {
            "unit": {"dead": value},
            "task_candidates": [
                {
                    "task_id": f"task-{agent_id}",
                    "task_type": "BUILD_LINE",
                }
            ],
        }
        for agent_id, value in enumerate(dead)
    ]


def _features(marker: float) -> SelectorFeatures:
    return SelectorFeatures(
        candidates=[[marker] * 37] + [[0.0] * 37 for _ in range(7)],
        scalars=[marker] + [0.0] * 169,
        candidate_present=[True] + [False] * 7,
        action_mask=[True] + [False] * 10,
        policy_loss_mask=True,
        forced_task_action=None,
    )


def test_v48_history_config_and_failover_pair_are_exact() -> None:
    from mindustry_agents.training.ppo_selector import (
        LEARNED_SEAT_HISTORY_SCHEMA,
        _learned_seat_failover,
        _learned_seat_history,
    )

    config = _config()
    assert _learned_seat_history(config) == config["learned_seat_history"]
    assert (
        config["learned_seat_history"]["schema"]
        == LEARNED_SEAT_HISTORY_SCHEMA
    )
    assert (
        _learned_seat_failover(config)["history_on_switch"]
        == "use_target_seat_cached_prior_boundary"
    )

    missing = _config()
    missing.pop("learned_seat_history")
    with pytest.raises(ValueError, match="learned_seat_history"):
        _learned_seat_history(missing)

    reset = _config()
    reset["learned_seat_failover"]["history_on_switch"] = "reset"
    with pytest.raises(ValueError, match="cached death failover"):
        _learned_seat_history(reset)

    malformed = _config()
    malformed["learned_seat_history"]["model_evaluations_per_boundary"] = 2
    with pytest.raises(ValueError, match="learned_seat_history"):
        _learned_seat_history(malformed)


def test_v48_failover_adopts_target_cache_and_v47_reset_remains_compatible() -> None:
    from mindustry_agents.training.ppo_selector import (
        _advance_learned_seat,
        _learned_seat_failover,
    )

    failover = _learned_seat_failover(_config())
    histories = [
        SelectorHistory(previous_action_index=0),
        SelectorHistory(previous_action_index=4),
        SelectorHistory(previous_action_index=7),
    ]
    active, adopted, transfer = _advance_learned_seat(
        _observations(True, False, False),
        0,
        histories[0],
        failover,
        histories,
    )
    assert active == 1
    assert adopted is histories[1]
    assert adopted.previous_action_index == 4
    assert transfer == {
        "from_agent_id": 0,
        "to_agent_id": 1,
        "reason": "active_agent_dead",
    }

    retained_active, retained, no_transfer = _advance_learned_seat(
        _observations(True, False, False),
        1,
        adopted,
        failover,
        histories,
    )
    assert (retained_active, retained, no_transfer) == (1, histories[1], None)

    legacy = _config()
    legacy.pop("learned_seat_history")
    legacy["learned_seat_failover"]["history_on_switch"] = "reset"
    _, reset, _ = _advance_learned_seat(
        _observations(True, False, False),
        0,
        histories[0],
        _learned_seat_failover(legacy),
    )
    assert reset == SelectorHistory()
    assert reset is not histories[1]


def test_v48_nonactive_cache_inputs_are_per_seat_and_dead_seats_retain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mindustry_agents.training.ppo_selector as selector

    observations = _observations(False, False, True)
    masks = [{}, {}, {}]
    histories = [
        SelectorHistory(previous_action_index=0),
        SelectorHistory(previous_action_index=1),
        SelectorHistory(previous_action_index=6),
    ]
    bundle = [
        {
            "agent_id": agent_id,
            "task_action": {
                "type": "SELECT_CANDIDATE_TASK",
                "candidate_index": 0,
            },
        }
        for agent_id in range(3)
    ]
    seen: list[tuple[int, SelectorHistory, tuple[str, ...]]] = []

    def intended(*_args, active_agent_id: int, **_kwargs):
        return (f"partner-for-{active_agent_id}",)

    def build(*_args, **kwargs):
        seen.append(
            (
                int(kwargs["agent_id"]),
                kwargs["history"],
                tuple(kwargs["fixed_partner_intended_task_ids"]),
            )
        )
        return _features(float(kwargs["agent_id"]))

    monkeypatch.setattr(selector, "_fixed_partner_intended_task_ids", intended)
    monkeypatch.setattr(selector, "build_selector_features", build)
    boundaries = selector._scripted_seat_history_boundaries(
        observations,
        masks,
        {},
        bundle,
        active_agent_id=0,
        histories=histories,
        task_board=[],
        boundary_reasons=[],
        partner_intent_duplication_risk={"enabled": True},
        feature_schema="test",
        control_schema="test",
    )
    assert list(boundaries) == [1]
    assert seen == [(1, histories[1], ("partner-for-1",))]

    counts = [0, 0, 0]
    selector._record_scripted_seat_history_boundaries(
        histories,
        boundaries,
        [{"agent_id": 1, "accepted": True}],
        observations,
        tick=700,
        update_counts=counts,
    )
    assert histories[1].previous_action_index == 0
    assert histories[1].previous_task_type == "BUILD_LINE"
    assert histories[1].previous_scalars is not None
    assert histories[2].previous_action_index == 6
    assert histories[2].previous_scalars is None
    assert counts == [0, 1, 0]


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="RL extra is not installed",
)
def test_v48_lineage_and_promotion_bind_history_authority() -> None:
    from mindustry_agents.training.checkpoint_lineage import (
        _expected_lineage_schemas,
    )
    from mindustry_agents.training.ppo_selector import (
        LEARNED_SEAT_FAILOVER_SCHEMA,
        LEARNED_SEAT_HISTORY_SCHEMA,
    )
    from mindustry_agents.training.promotion import (
        CANDIDATE_POLICY,
        GREEDY_MIXED,
        _learned_seat_failover_gate,
    )
    from mindustry_agents.training.promotion_final import (
        _validate_learned_seat_failover_preflight,
    )

    assert _expected_lineage_schemas(_config()) == {
        "feature": "selector_features_v3_expert_defer",
        "reward": "selector_reward_v2",
        "model": "selector_actor_critic_v5_expert_defer_control",
        "control": "selector_control_actions_v2_expert_defer",
        "seat_control": LEARNED_SEAT_FAILOVER_SCHEMA,
        "seat_history": LEARNED_SEAT_HISTORY_SCHEMA,
    }

    def record(policy: str, model_evaluations: int) -> dict:
        return {
            "manifest": {"policy": policy},
            "seat_control": {
                "schema": LEARNED_SEAT_FAILOVER_SCHEMA,
                "initial_agent_id": 0,
                "final_agent_id": 0,
                "transfer_count": 0,
                "transfers": [],
                "maximum_simultaneous_learned_seats": 1,
                "history_schema": LEARNED_SEAT_HISTORY_SCHEMA,
                "history_boundary_updates": [4, 4, 4],
                "maximum_model_evaluations_per_boundary": model_evaluations,
                "maximum_learned_actions_per_boundary": 1,
            },
        }

    gate = _learned_seat_failover_gate(
        [
            record(CANDIDATE_POLICY, 1),
            record(GREEDY_MIXED, 0),
        ],
        _config(),
    )
    assert gate is not None
    assert gate["history_schema"] == LEARNED_SEAT_HISTORY_SCHEMA
    assert gate["maximum_model_evaluations_per_boundary"] == 1
    assert gate["maximum_learned_actions_per_boundary"] == 1
    _validate_learned_seat_failover_preflight(gate, expected_history=True)

    invalid = record(CANDIDATE_POLICY, 2)
    with pytest.raises(RuntimeError, match="single-brain"):
        _learned_seat_failover_gate([invalid], _config())
    with pytest.raises(ValueError, match="seat-history"):
        _validate_learned_seat_failover_preflight(
            gate | {"history_schema": "drift"},
            expected_history=True,
        )
