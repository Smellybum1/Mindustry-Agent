"""Probe seat-zero staging while another seat owns live schematic work."""

from __future__ import annotations

import argparse
import sys
import traceback
from typing import Any

from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
)


PUBLIC_SEED = 12345
SCENARIO_ID = "bootstrap-defense-v1"
SCENARIO_VERSION = 2


def _aligned_candidates(
    observation: dict[str, Any], mask: dict[str, Any], *, seat: int
) -> list[dict[str, Any]]:
    candidates = observation.get("task_candidates", [])
    selectable = mask.get("candidate_task", [])
    if len(candidates) != len(selectable):
        raise AssertionError(
            f"seat {seat} candidate/mask length mismatch: "
            f"{len(candidates)} != {len(selectable)}"
        )
    for position, candidate in enumerate(candidates):
        if int(candidate.get("index", -1)) != position:
            raise AssertionError(
                f"seat {seat} candidate index drift at position {position}: {candidate}"
            )
    return candidates


def _unique_selectable(
    observation: dict[str, Any],
    mask: dict[str, Any],
    *,
    seat: int,
    task_type: str,
) -> dict[str, Any]:
    candidates = _aligned_candidates(observation, mask, seat=seat)
    matches = [
        candidate
        for candidate in candidates
        if candidate.get("task_type") == task_type
        and candidate.get("valid") is True
        and mask["candidate_task"][int(candidate["index"])] is True
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"seat {seat} expected one selectable {task_type}, got {matches}"
        )
    return matches[0]


def _select(seat: int, candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "agent_id": seat,
        "task_action": {
            "type": "SELECT_CANDIDATE_TASK",
            "candidate_index": int(candidate["index"]),
        },
    }


def _probe(env: RlServerProcess) -> tuple[str, str, str]:
    reset = env.reset(
        PUBLIC_SEED,
        scenario_id=SCENARIO_ID,
        scenario_version=SCENARIO_VERSION,
        agent_count=3,
    )
    if reset.tick != 0:
        raise AssertionError(f"reset tick drifted: {reset.tick}")
    if len(reset.initial_observations) != 3 or len(reset.action_masks) != 3:
        raise AssertionError(
            "reset did not expose exactly three seats: "
            f"observations={len(reset.initial_observations)} "
            f"masks={len(reset.action_masks)}"
        )
    for seat, (observation, mask) in enumerate(
        zip(reset.initial_observations, reset.action_masks, strict=True)
    ):
        _aligned_candidates(observation, mask, seat=seat)

    schematic = _unique_selectable(
        reset.initial_observations[1],
        reset.action_masks[1],
        seat=1,
        task_type="BUILD_SCHEMATIC",
    )
    harvest = _unique_selectable(
        reset.initial_observations[2],
        reset.action_masks[2],
        seat=2,
        task_type="HARVEST_RESOURCE",
    )
    response = env.step(
        reset.episode_id,
        expected_tick=reset.tick,
        ticks_to_advance=1,
        agent_actions=[
            {"agent_id": 0, "task_action": {"type": "WAIT"}},
            _select(1, schematic),
            _select(2, harvest),
        ],
    )

    if response.previous_tick != 0 or response.tick != 1:
        raise AssertionError(
            "probe did not advance exactly one external tick: "
            f"previous={response.previous_tick} tick={response.tick}"
        )
    if len(response.action_results) != 3 or not all(
        result.get("accepted") is True for result in response.action_results
    ):
        raise AssertionError(
            f"opening actions were not all accepted: {response.action_results}"
        )
    if [int(result.get("agent_id", -1)) for result in response.action_results] != [
        0,
        1,
        2,
    ]:
        raise AssertionError(f"opening result order drifted: {response.action_results}")
    wait_result = response.action_results[0]
    if wait_result.get("task_action_type") != "WAIT" or wait_result.get("task_id"):
        raise AssertionError(
            f"seat-zero WAIT gained a task: {response.action_results[0]}"
        )

    live_schematics = [
        task
        for task in response.task_board
        if task.get("task_type") == "BUILD_SCHEMATIC"
        and int(task.get("owner_agent_id", -1)) == 1
        and task.get("status") == "RUNNING"
    ]
    if len(live_schematics) != 1:
        raise AssertionError(
            f"expected one live seat-one schematic task, got {live_schematics}"
        )

    if len(response.observations) != 3 or len(response.action_masks) != 3:
        raise AssertionError(
            "step did not expose exactly three seats: "
            f"observations={len(response.observations)} "
            f"masks={len(response.action_masks)}"
        )
    for seat, (observation, mask) in enumerate(
        zip(response.observations, response.action_masks, strict=True)
    ):
        _aligned_candidates(observation, mask, seat=seat)

    seat_zero = response.observations[0]
    seat_zero_mask = response.action_masks[0]
    if seat_zero.get("skill", {}).get("status") != "READY":
        raise AssertionError(f"seat zero is not idle: {seat_zero.get('skill')}")
    if not seat_zero_mask.get("wait", False) or seat_zero_mask.get(
        "continue_current_task", False
    ):
        raise AssertionError(f"seat zero idle mask drifted: {seat_zero_mask}")

    stage = [
        candidate
        for candidate in seat_zero["task_candidates"]
        if candidate.get("task_type") == "DEFEND_REGION"
        and ":stage:" in str(candidate.get("task_id", ""))
        and candidate.get("valid") is True
        and seat_zero_mask["candidate_task"][int(candidate["index"])] is True
    ]
    if len(stage) != 1:
        catalog = [
            {
                "index": candidate.get("index"),
                "task_id": candidate.get("task_id"),
                "task_type": candidate.get("task_type"),
                "valid": candidate.get("valid"),
                "masked": not bool(
                    seat_zero_mask["candidate_task"][int(candidate["index"])]
                ),
            }
            for candidate in seat_zero["task_candidates"]
        ]
        raise AssertionError(
            "seat zero expected one selectable stage candidate: "
            f"matches={stage} catalog={catalog} board={live_schematics}"
        )
    ordinary = [
        candidate
        for candidate in seat_zero["task_candidates"]
        if candidate.get("task_type") != "WAIT"
        and ":stage:" not in str(candidate.get("task_id", ""))
        and candidate.get("valid") is True
        and seat_zero_mask["candidate_task"][int(candidate["index"])] is True
    ]
    if not ordinary:
        raise AssertionError(
            "seat zero exposes no ordinary selectable non-WAIT candidate"
        )

    for seat in (1, 2):
        exposed = [
            candidate
            for candidate in response.observations[seat]["task_candidates"]
            if ":stage:" in str(candidate.get("task_id", ""))
        ]
        if exposed:
            raise AssertionError(f"seat {seat} unexpectedly exposes staging: {exposed}")

    seat_zero_owned = [
        task
        for task in response.task_board
        if int(task.get("owner_agent_id", -1)) == 0
    ]
    helper_state = [
        task
        for task in response.task_board
        if int(task.get("pending_offer_count", 0)) != 0
        or int(task.get("helper_count", 0)) != 0
    ]
    seat_zero_events = [
        event
        for event in response.task_events
        if int(event.get("agent_id", -1)) == 0
        or int(event.get("related_agent_id", -1)) == 0
    ]
    if seat_zero_owned or helper_state or seat_zero_events:
        raise AssertionError(
            "seat zero gained synthetic claim/helper state: "
            f"owned={seat_zero_owned} helpers={helper_state} events={seat_zero_events}"
        )

    return (
        str(live_schematics[0]["task_id"]),
        str(stage[0]["task_id"]),
        str(ordinary[0]["task_type"]),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--java", default="java")
    args = parser.parse_args(argv)

    try:
        with RlServerProcess(
            LaunchConfig(port=args.port, java=args.java, build_if_missing=False)
        ) as env:
            env.handshake("owned-schematic-staging-check")
            schematic_id, stage_id, ordinary_type = _probe(env)
    except Exception as exc:
        print(f"OWNED-SCHEMATIC-STAGING FAIL: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1

    print(
        "owned schematic staging: "
        f"seed={PUBLIC_SEED} schematic={schematic_id} "
        f"stage={stage_id} ordinary={ordinary_type}"
    )
    print("OWNED-SCHEMATIC-STAGING OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
