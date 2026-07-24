"""Governance tests for ADR-0131's trajectory-divergence diagnostic."""

import json
from pathlib import Path

import pytest

from mindustry_agents.training.ippo_ppo import sha256_path
from mindustry_agents.training.planner_trajectory_divergence import (
    PROTOCOL_SHA256,
    _append_grid,
    _apply_actor_tokens,
    classify,
    compare_root_trajectories,
    compress_joint_tokens,
    levenshtein_distance,
    paired_report,
    validate_inputs,
)


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = (
    ROOT
    / "configs/evaluation/"
    "m9-planner-trajectory-divergence-v1-protocol.json"
)


def _rules():
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))["classification"]


def _episode(
    seed: int,
    outcome: str,
    trajectory: list[list[str]],
    *,
    terminal_tick: int | None = None,
):
    return {
        "seed": seed,
        "outcome": outcome,
        "reset_tick": 0,
        "terminal_tick": terminal_tick or 60 * len(trajectory),
        "joint_task_family_trajectory": trajectory,
    }


def _paired(
    *,
    planner_only: int,
    occupancy: float,
    distance: float,
):
    return {
        "planner_only_win": planner_only,
        "median_primary_occupancy_mismatch": occupancy,
        "median_primary_normalized_compressed_sequence_distance": distance,
    }


def test_protocol_is_exact_public_only_derived_and_non_mutating():
    assert sha256_path(PROTOCOL) == PROTOCOL_SHA256
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["data_classification"] == "public_dev_only"
    assert protocol["source_checkpoint"]["lineage_update"] == 64
    assert protocol["trajectory_measurement"]["sample_period_ticks"] == 60
    assert not protocol["trajectory_measurement"][
        "target_identifiers_recorded"
    ]
    assert not protocol["trajectory_measurement"][
        "raw_observations_published"
    ]
    assert not protocol["downstream_authority"]["may_train"]
    assert not protocol["downstream_authority"][
        "may_access_confirmation"
    ]
    assert not protocol["downstream_authority"]["may_access_held_out"]


def test_bound_inputs_are_exact_rejected_and_public():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    checkpoint = ROOT / protocol["source_checkpoint"]["path"]
    if not checkpoint.exists():
        pytest.skip("ignored immutable checkpoint is not local")
    loaded, _, seeds = validate_inputs(ROOT)
    source = loaded["source_checkpoint"]
    assert len(seeds) == len(set(seeds)) == 40
    assert source["construction_passed"] is False
    assert source["selected_or_promoted"] is False
    assert source["repaired"] is False


def test_grid_and_actor_token_semantics_are_exact():
    tokens = ["WAIT", "WAIT", "WAIT"]
    actions = [
        {
            "agent_id": 0,
            "task_action": {
                "type": "SELECT_CANDIDATE_TASK",
                "candidate_index": 0,
            },
        },
        {"agent_id": 1, "task_action": {"type": "WAIT"}},
        {
            "agent_id": 2,
            "task_action": {
                "type": "SELECT_CANDIDATE_TASK",
                "candidate_index": 0,
            },
        },
    ]
    observations = [
        {"task_candidates": [{"task_type": "BUILD_LINE"}]},
        {"task_candidates": []},
        {"task_candidates": [{"task_type": "DEFEND_REGION"}]},
    ]
    _apply_actor_tokens(
        tokens,
        actions,
        observations,
        {0, 1, 2},
        actor_authoritative={0, 1},
    )
    assert tokens == ["BUILD_LINE", "WAIT", "WAIT"]

    trajectory = []
    next_tick = _append_grid(
        trajectory,
        tokens,
        next_grid_tick=60,
        boundary_tick=130,
    )
    assert trajectory == [tokens, tokens]
    assert trajectory[0] is not tokens
    assert next_tick == 180


def test_compression_edit_distance_and_common_prefix_metrics():
    wait = ["WAIT", "WAIT", "WAIT"]
    build = ["BUILD_LINE", "WAIT", "WAIT"]
    defend = ["DEFEND_REGION", "WAIT", "WAIT"]
    assert compress_joint_tokens([wait, wait, build, build, wait]) == [
        wait,
        build,
        wait,
    ]
    assert levenshtein_distance([wait, build], [wait, defend]) == 1
    assert levenshtein_distance([], [wait, defend]) == 2

    student = _episode(1, "loss", [wait, wait, build], terminal_tick=180)
    planner = _episode(1, "win", [wait, defend], terminal_tick=120)
    compared = compare_root_trajectories(student, planner)
    assert compared["common_grid_samples"] == 2
    assert compared["mismatched_grid_samples"] == 1
    assert compared["occupancy_mismatch_fraction"] == 0.5
    assert compared["compressed_levenshtein_distance"] == 1
    assert compared["normalized_compressed_sequence_distance"] == 0.5


def test_paired_median_and_classification_are_frozen():
    wait = ["WAIT", "WAIT", "WAIT"]
    build = ["BUILD_LINE", "WAIT", "WAIT"]
    defend = ["DEFEND_REGION", "WAIT", "WAIT"]
    students = [
        _episode(1, "loss", [wait, wait]),
        _episode(2, "loss", [wait, build]),
        _episode(3, "win", [wait, build]),
        _episode(4, "loss", [wait, wait]),
    ]
    planners = [
        _episode(1, "win", [build, build]),
        _episode(2, "win", [defend, defend]),
        _episode(3, "win", [wait, build]),
        _episode(4, "loss", [wait, wait]),
    ]
    paired = paired_report(students, planners)
    assert paired["both_win"] == 1
    assert paired["planner_only_win"] == 2
    assert paired["both_loss"] == 1
    assert paired["median_primary_occupancy_mismatch"] == 1.0

    strong = classify(
        _paired(planner_only=15, occupancy=0.5, distance=0.5),
        _rules(),
        valid=True,
    )
    assert strong["signal"] == "trajectory_supervision_signal"
    assert strong["new_prospective_adr_authorized"]
    assert not strong["training_authorized"]

    low = classify(
        _paired(planner_only=20, occupancy=0.25, distance=0.9),
        _rules(),
        valid=True,
    )
    assert low["signal"] == "low_trajectory_signal"

    mixed = classify(
        _paired(planner_only=14, occupancy=0.6, distance=0.7),
        _rules(),
        valid=True,
    )
    assert mixed["signal"] == "mixed_trajectory_signal"

    invalid = classify(
        _paired(planner_only=20, occupancy=0.9, distance=0.9),
        _rules(),
        valid=False,
    )
    assert invalid["signal"] == "invalid"
    assert not invalid["new_prospective_adr_authorized"]


def test_classification_rejects_rule_drift():
    rules = _rules()
    rules["trajectory_supervision_signal"][
        "minimum_planner_only_wins"
    ] = 14
    with pytest.raises(ValueError, match="classification drifted"):
        classify(
            _paired(planner_only=15, occupancy=0.5, distance=0.5),
            rules,
            valid=True,
        )
