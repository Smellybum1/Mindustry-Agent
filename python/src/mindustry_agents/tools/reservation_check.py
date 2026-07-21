"""Live M5.4 footprint/resource reservation acceptance and determinism check."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from typing import Any

from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess


def _candidate(observation: dict[str, Any], suffix: str) -> dict[str, Any]:
    for candidate in observation["task_candidates"]:
        task_id = candidate["task_id"]
        overlap = suffix.endswith(":overlap-probe")
        stem = suffix.removesuffix(":overlap-probe")
        if task_id.startswith(stem) and (
            task_id.endswith(":overlap-probe") if overlap
            else not task_id.endswith(":overlap-probe")
        ):
            return candidate
    raise AssertionError(f"candidate suffix not found: {suffix}")


def _run_once(port: int, seed: int, java: str, verbose: bool) -> tuple[str, dict]:
    transcript: list[dict[str, Any]] = []
    all_events: list[dict[str, Any]] = []

    with RlServerProcess(
        LaunchConfig(port=port, java=java, build_if_missing=False)
    ) as env:
        env.handshake("m5-reservation-check")
        rr = env.reset(
            seed,
            agent_count=2,
            options={"reservation_overlap_probe": True},
        )
        episode = rr.episode_id
        tick = rr.tick
        observations = rr.initial_observations
        transcript.append({"reset_hash": rr.state_hash, "masks": rr.action_masks})

        def step(
            ticks: int = 0,
            actions=None,
            *,
            stop_on_decision_event: bool = False,
        ):
            nonlocal tick, observations
            response = env.step(
                episode,
                expected_tick=tick,
                ticks_to_advance=ticks,
                agent_actions=actions or [],
                stop_on_decision_event=stop_on_decision_event,
            )
            tick = response.tick
            observations = response.observations
            all_events.extend(response.task_events)
            transcript.append(
                {
                    "hash": response.state_hash,
                    "results": response.action_results,
                    "board": response.task_board,
                    "events": response.task_events,
                    "metrics": response.coordination_metrics,
                    "decision_boundary": response.decision_boundary,
                }
            )
            return response

        base = _candidate(observations[0], "T3:build:east_duo_v1")
        probe = _candidate(observations[1], "T3:build:east_duo_v1:overlap-probe")
        expected_winner = 0 if float(base["utility"]) >= float(probe["utility"]) else 1
        chosen = {0: base, 1: probe}
        contested = step(
            actions=[
                {
                    "agent_id": agent_id,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": int(chosen[agent_id]["index"]),
                    },
                }
                for agent_id in (0, 1)
            ]
        )
        loser = 1 - expected_winner
        results = {int(result["agent_id"]): result for result in contested.action_results}
        assert results[expected_winner]["accepted"] is True
        assert results[loser]["reason"] == "reservation_overlap"

        running = next(
            task for task in contested.task_board if task["owner_agent_id"] == expected_winner
        )
        rejected = next(task for task in contested.task_board if task["index"] != running["index"])
        assert running["reservation_count"] == 2
        assert running["tile_reservation_count"] == 1
        assert running["reserved_resources"] == {"copper": 100}
        assert rejected["status"] == "OPEN"
        assert rejected["reservation_count"] == 0
        conflict = next(
            event
            for event in contested.task_events
            if event["reason_code"] == "reservation_overlap"
        )
        assert conflict["agent_id"] == loser
        assert conflict["related_agent_id"] == expected_winner
        assert contested.coordination_metrics["duplicate_work_incidents"] == 1

        planned = step(30)
        assert observations[expected_winner]["unit"]["build_queue_depth"] > 0
        assert observations[loser]["unit"]["build_queue_depth"] == 0

        abandoned = step(
            30,
            actions=[
                {
                    "agent_id": expected_winner,
                    "task_action": {"type": "ABANDON", "reason": "release_probe"},
                }
            ],
            stop_on_decision_event=True,
        )
        assert abandoned.decision_boundary["triggered"] is True
        assert abandoned.decision_boundary["advanced_ticks"] == 1
        assert "task_terminal" in abandoned.decision_boundary["reasons"]
        abandoned_task = next(
            task for task in abandoned.task_board if task["index"] == running["index"]
        )
        assert abandoned_task["status"] == "ABANDONED"
        assert abandoned_task["reservation_count"] == 0
        assert observations[expected_winner]["unit"]["build_queue_depth"] == 0

        loser_candidate = _candidate(observations[loser], "T3:build:east_duo_v1")
        reclaimed = step(
            actions=[
                {
                    "agent_id": loser,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": int(loser_candidate["index"]),
                    },
                }
            ]
        )
        assert reclaimed.action_results[0]["accepted"] is True
        reclaimed_task = next(
            task for task in reclaimed.task_board if task["owner_agent_id"] == loser
        )
        assert reclaimed_task["reservation_count"] == 2

        completed = reclaimed
        for _ in range(40):
            completed = step(30)
            task = next(
                task
                for task in completed.task_board
                if task["task_id"] == reclaimed_task["task_id"]
            )
            if task["status"] == "COMPLETED":
                break
        assert task["status"] == "COMPLETED"
        assert task["reservation_count"] == 0

        supply = [
            candidate
            for candidate in observations[0]["task_candidates"]
            if candidate["task_type"] == "SUPPLY_TURRET"
        ]
        assert len(supply) == 2
        supplied = step(
            actions=[
                {
                    "agent_id": agent_id,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": int(supply[agent_id]["index"]),
                    },
                }
                for agent_id in (0, 1)
            ]
        )
        assert all(result["accepted"] for result in supplied.action_results)
        supply_tasks = [
            task for task in supplied.task_board if task["task_type"] == "SUPPLY_TURRET"
        ]
        assert len(supply_tasks) == 2
        assert all(task["reservation_count"] == 1 for task in supply_tasks)
        assert all(task["reserved_resources"] == {"copper": 15} for task in supply_tasks)

        for _ in range(40):
            supplied = step(10)
            supply_tasks = [
                task
                for task in supplied.task_board
                if task["task_type"] == "SUPPLY_TURRET"
            ]
            if all(task["status"] == "COMPLETED" for task in supply_tasks):
                break
        assert all(task["status"] == "COMPLETED" for task in supply_tasks)
        assert all(task["reservation_count"] == 0 for task in supply_tasks)

        wait_candidate = next(
            candidate
            for candidate in observations[0]["task_candidates"]
            if candidate["task_type"] == "WAIT"
        )
        wait_selected = step(
            actions=[
                {
                    "agent_id": 0,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": int(wait_candidate["index"]),
                    },
                }
            ]
        )
        assert wait_selected.action_results[0]["accepted"] is True
        wait_task_id = str(wait_selected.action_results[0]["task_id"])
        wait_finished = step(120, stop_on_decision_event=True)
        assert wait_finished.decision_boundary["triggered"] is True
        assert wait_finished.decision_boundary["advanced_ticks"] == 61
        assert "task_terminal" in wait_finished.decision_boundary["reasons"]
        wait_release = next(
            event
            for event in wait_finished.task_events
            if event["task_id"] == wait_task_id and event["act"] == "RELEASE"
        )
        assert int(wait_release["tick"]) == wait_finished.tick
        wait_task = next(
            task for task in wait_finished.task_board if task["task_id"] == wait_task_id
        )
        assert wait_task["status"] == "OPEN"
        assert wait_task["owner_agent_id"] == -1

        summary = {
            "winner": expected_winner,
            "conflict_tick": int(conflict["tick"]),
            "build_complete_tick": next(
                int(event["tick"])
                for event in all_events
                if event["task_type"] == "BUILD_SCHEMATIC"
                and event["act"] == "COMPLETE"
            ),
            "final_tick": tick,
            "metrics": supplied.coordination_metrics,
        }
        if verbose:
            print(
                f"reservations: winner=agent_{expected_winner} conflict={summary['conflict_tick']} "
                f"build={summary['build_complete_tick']} final={summary['final_tick']}"
            )

    return json.dumps(transcript, sort_keys=True, separators=(",", ":")), summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="M5.4 live reservation acceptance")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--java", default="java")
    args = parser.parse_args(argv)

    try:
        first, summary = _run_once(args.port, args.seed, args.java, True)
        second, _ = _run_once(args.port, args.seed, args.java, False)
    except Exception as exc:
        traceback.print_exc()
        print(f"RESERVATION FAIL: {exc}", file=sys.stderr)
        return 1

    if first != second:
        print("RESERVATION FAIL: cross-process transcript mismatch", file=sys.stderr)
        return 1
    print(
        "RESERVATION OK: footprint conflict + release + resource budgets; "
        f"byte-identical replay through tick {summary['final_tick']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
