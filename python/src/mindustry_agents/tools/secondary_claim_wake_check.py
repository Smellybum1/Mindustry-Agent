"""Live V35 fixed-seat claim-loss decision-boundary acceptance check."""

from __future__ import annotations

import argparse
import math
import sys

from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
)


def _candidate_by_id(observation: dict, task_id: str) -> dict:
    return next(
        candidate
        for candidate in observation["task_candidates"]
        if candidate["task_id"] == task_id
    )


def _contest(observations: list[dict], loser: int) -> tuple[int, str, int, int]:
    for candidate in observations[loser]["task_candidates"]:
        if not candidate.get("valid", True) or not candidate.get("exclusive", False):
            continue
        task_id = str(candidate["task_id"])
        loser_utility = float(candidate["utility"])
        for winner in range(len(observations)):
            if winner == loser:
                continue
            try:
                other = _candidate_by_id(observations[winner], task_id)
            except StopIteration:
                continue
            if not other.get("valid", True):
                continue
            winner_utility = float(other["utility"])
            if winner_utility > loser_utility or (
                math.isclose(winner_utility, loser_utility, rel_tol=0.0, abs_tol=0.0)
                and winner < loser
            ):
                return (
                    winner,
                    task_id,
                    int(candidate["index"]),
                    int(other["index"]),
                )
    raise AssertionError(f"no deterministic losing contest found for seat {loser}")


def _probe(
    env: RlServerProcess,
    *,
    seed: int,
    loser: int,
    should_wake: bool,
) -> dict:
    reset = env.reset(seed, agent_count=3)
    winner, task_id, loser_index, winner_index = _contest(
        reset.initial_observations, loser
    )
    response = env.step(
        reset.episode_id,
        expected_tick=reset.tick,
        ticks_to_advance=1,
        agent_actions=[
            {
                "agent_id": loser,
                "task_action": {
                    "type": "SELECT_CANDIDATE_TASK",
                    "candidate_index": loser_index,
                },
            },
            {
                "agent_id": winner,
                "task_action": {
                    "type": "SELECT_CANDIDATE_TASK",
                    "candidate_index": winner_index,
                },
            },
        ],
        stop_on_decision_event=True,
    )

    loser_result, winner_result = response.action_results
    assert loser_result["accepted"] is False
    assert loser_result["reason"] == "claim_lost"
    assert loser_result["task_id"] == task_id
    assert winner_result["accepted"] is True
    assert winner_result["task_id"] == task_id
    task = next(item for item in response.task_board if item["task_id"] == task_id)
    assert task["owner_agent_id"] == winner
    assert task["status"] == "RUNNING"
    assert not any(event.get("act") == "CLAIM_LOST" for event in response.task_events)
    assert response.decision_boundary["advanced_ticks"] == 1
    assert response.decision_boundary["triggered"] is should_wake
    assert response.decision_boundary["reasons"] == (
        ["claim_lost"] if should_wake else []
    )
    assert any(response.action_masks[loser]["candidate_task"])
    return {
        "loser": loser,
        "winner": winner,
        "task_id": task_id,
        "triggered": response.decision_boundary["triggered"],
        "advanced_ticks": response.decision_boundary["advanced_ticks"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--java", default="java")
    args = parser.parse_args(argv)

    try:
        with RlServerProcess(
            LaunchConfig(port=args.port, java=args.java, build_if_missing=False)
        ) as env:
            env.handshake("m8-v35-secondary-claim-wake-check")
            secondary = _probe(
                env, seed=args.seed, loser=1, should_wake=True
            )
            learned = _probe(
                env, seed=args.seed, loser=0, should_wake=False
            )
    except Exception as exc:
        print(f"SECONDARY-CLAIM-WAKE FAIL: {exc}", file=sys.stderr)
        return 1

    print(
        "secondary claim wake: "
        f"seat {secondary['loser']} lost {secondary['task_id']} to "
        f"seat {secondary['winner']} and woke after one tick"
    )
    print(
        "learned-seat preservation: "
        f"seat {learned['loser']} lost {learned['task_id']} to "
        f"seat {learned['winner']} without a decision wake"
    )
    print("SECONDARY-CLAIM-WAKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
