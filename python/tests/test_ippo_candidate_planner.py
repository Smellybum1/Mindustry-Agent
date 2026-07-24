import copy
import json
from pathlib import Path

import pytest

from mindustry_agents.training.ippo_candidate_planner import (
    DEFAULT_PROTOCOL,
    _bundle_conflicts,
    _eligible,
    _load_protocol,
    _summarize,
)


def test_protocol_is_public_only_and_binds_seed_set():
    protocol, seeds = _load_protocol(DEFAULT_PROTOCOL)
    assert protocol["data_classification"] == "public_dev_only"
    assert len(seeds) == 40
    assert len(set(seeds)) == 40
    assert not any(protocol["authority"].values())


def test_v2_protocol_binds_single_serialization_coordinate():
    protocol, seeds = _load_protocol(
        DEFAULT_PROTOCOL.with_name(
            "m9-candidate-native-planner-v2-protocol.json"
        )
    )
    assert len(seeds) == 40
    assert protocol["sole_behavior_change"] == (
        "at_most_one_build_schematic_selection_per_atomic_bundle"
    )
    assert protocol["planner"]["additional_bundle_constraint"][
        "maximum_simultaneous_selections"
    ] == 1


def test_v3_protocol_binds_active_board_coordinate():
    protocol, seeds = _load_protocol(
        DEFAULT_PROTOCOL.with_name(
            "m9-candidate-native-planner-v3-protocol.json"
        )
    )
    assert len(seeds) == 40
    assert protocol["planner"]["additional_active_task_constraint"][
        "active_statuses"
    ] == ["CLAIMED", "RUNNING", "BLOCKED"]


def test_v4_protocol_binds_active_build_supply_coordinate():
    protocol, seeds = _load_protocol(
        DEFAULT_PROTOCOL.with_name(
            "m9-candidate-native-planner-v4-protocol.json"
        )
    )
    assert len(seeds) == 40
    assert protocol["planner"]["active_build_fallback_priority"][
        "task_order"
    ] == ["SUPPLY_TURRET", "HARVEST_RESOURCE"]


def test_v5_protocol_binds_candidate_actionability_coordinate():
    protocol, seeds = _load_protocol(
        DEFAULT_PROTOCOL.with_name(
            "m9-candidate-native-planner-v5-protocol.json"
        )
    )
    assert len(seeds) == 40
    assert "valid_actor_masked_supply_turret_candidate_exists" in protocol[
        "planner"
    ]["active_build_fallback_priority"]["preconditions"]


def test_v6_protocol_binds_completed_fortification_coordinate():
    protocol, seeds = _load_protocol(
        DEFAULT_PROTOCOL.with_name(
            "m9-candidate-native-planner-v6-protocol.json"
        )
    )
    assert len(seeds) == 40
    assert protocol["planner"]["completed_fortification_constraint"][
        "suppressed_new_task_type"
    ] == "BUILD_LINE"


def test_protocol_rejects_digest_drift(tmp_path: Path):
    document = json.loads(DEFAULT_PROTOCOL.read_text(encoding="utf-8"))
    document["authority"]["may_train"] = True
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="digest is not accepted"):
        _load_protocol(path)


def test_eligible_excludes_dead_and_wait_only_slots():
    wait = {
        "index": 0,
        "task_type": "WAIT",
        "valid": True,
    }
    assert not _eligible(
        {"unit": {"dead": True}, "task_candidates": []}, {"wait": True}
    )
    assert not _eligible(
        {"unit": {"dead": False}, "task_candidates": [wait]},
        {"candidate_task": [True], "wait": True},
    )
    assert _eligible(
        {
            "unit": {"dead": False},
            "task_candidates": [{**wait, "task_type": "BUILD_LINE"}],
        },
        {"candidate_task": [True]},
    )


def test_bundle_conflict_detects_semantic_duplicate_with_distinct_ids():
    observations = [
        {
            "task_candidates": [
                {
                    "task_id": f"task-{agent_id}",
                    "task_type": "SUPPLY_TURRET",
                    "target": "tile (2, 3)",
                    "exclusive": True,
                }
            ]
        }
        for agent_id in range(2)
    ]
    actions = [
        {
            "agent_id": agent_id,
            "task_action": {
                "type": "SELECT_CANDIDATE_TASK",
                "candidate_index": 0,
            },
        }
        for agent_id in range(2)
    ]
    assert _bundle_conflicts(actions, observations) == 1


def _fresh_run(*, wins: int = 30, coverage: float = 1.0):
    eligible = 100
    non_wait = round(eligible * coverage)
    episodes = [
        {
            "outcome": "win" if index < wins else "loss",
            "rejected_actions": 0,
            "cross_seat_exclusive_conflicts": 0,
            "eligible_slots": eligible,
            "non_wait_slots": non_wait,
        }
        for index in range(40)
    ]
    return {
        "episodes": episodes,
        "terminal_reset_replay_equal": True,
        "canonical_sha256": "same",
    }


def test_summary_requires_exact_runs_and_all_frozen_thresholds():
    protocol, _ = _load_protocol(DEFAULT_PROTOCOL)
    first = _fresh_run()
    result = _summarize(protocol, first, copy.deepcopy(first))
    assert result["passed"]
    assert result["minimum_retained_wins"] == 29

    second = copy.deepcopy(first)
    second["canonical_sha256"] = "different"
    assert not _summarize(protocol, first, second)["passed"]
    assert not _summarize(
        protocol, _fresh_run(wins=29), _fresh_run(wins=29)
    )["passed"]
    assert not _summarize(
        protocol, _fresh_run(coverage=0.94), _fresh_run(coverage=0.94)
    )["passed"]
