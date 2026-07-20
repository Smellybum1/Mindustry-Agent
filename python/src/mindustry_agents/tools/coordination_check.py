"""Live M5.2 board/action/skill acceptance and cross-process determinism check."""

from __future__ import annotations

import argparse
import json
import sys

from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess


def _candidate_index(observation, prefix: str) -> int:
    for candidate in observation["task_candidates"]:
        if candidate["task_id"].startswith(prefix):
            return int(candidate["index"])
    raise AssertionError(f"candidate prefix not found: {prefix}")


def _run_once(port: int, seed: int, java: str, verbose: bool) -> tuple[str, dict]:
    transcript: list[dict] = []

    with RlServerProcess(
        LaunchConfig(port=port, java=java, build_if_missing=False)
    ) as env:
        env.handshake("m5-coordination-check")
        rr = env.reset(seed, agent_count=3)
        episode = rr.episode_id
        tick = rr.tick
        observations = rr.initial_observations
        transcript.append({"hash": rr.state_hash, "masks": rr.action_masks})

        def step(ticks: int = 0, actions=None):
            nonlocal tick, observations
            response = env.step(
                episode,
                expected_tick=tick,
                ticks_to_advance=ticks,
                agent_actions=actions or [],
            )
            tick = response.tick
            observations = response.observations
            transcript.append(
                {
                    "hash": response.state_hash,
                    "results": response.action_results,
                    "board": response.task_board,
                    "events": response.task_events,
                    "masks": response.action_masks,
                    "metrics": response.coordination_metrics,
                }
            )
            return response

        invalid = step(
            actions=[
                {
                    "agent_id": 2,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": 99,
                    },
                }
            ]
        )
        assert invalid.action_results[0]["reason"] == "candidate_index_out_of_range"

        build_index = _candidate_index(observations[0], "T3:build:")
        bids = [
            float(observations[i]["task_candidates"][build_index]["utility"])
            for i in (0, 1)
        ]
        expected_winner = 0 if bids[0] >= bids[1] else 1
        loser = 1 - expected_winner
        contested = step(
            actions=[
                {
                    "agent_id": i,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": build_index,
                    },
                }
                for i in (0, 1)
            ]
        )
        assert contested.task_board[0]["owner_agent_id"] == expected_winner
        assert contested.task_board[0]["status"] == "RUNNING"
        assert contested.action_results[expected_winner]["accepted"] is True
        assert contested.action_results[loser]["reason"] == "claim_lost"
        assert [event["message_id"] for event in contested.task_events] == list(
            range(len(contested.task_events))
        )

        requested = step(
            actions=[
                {
                    "agent_id": expected_winner,
                    "task_action": {"type": "REQUEST_HELP", "helpers_requested": 1},
                }
            ]
        )
        assert requested.action_results[0]["accepted"] is True
        continued = step(
            actions=[
                {
                    "agent_id": expected_winner,
                    "task_action": {"type": "CONTINUE_CURRENT_TASK"},
                }
            ]
        )
        assert continued.action_results[0]["accepted"] is True

        offered = step(
            actions=[
                {
                    "agent_id": loser,
                    "task_action": {
                        "type": "OFFER_HELP",
                        "task_index": 0,
                        "contribution": "deliver copper",
                        "amount": 20,
                    },
                }
            ]
        )
        assert offered.task_board[0]["pending_offer_count"] == 1
        accepted = step(
            actions=[
                {
                    "agent_id": expected_winner,
                    "task_action": {"type": "ACCEPT_HELP", "offer_index": 0},
                }
            ]
        )
        assert accepted.task_board[0]["helper_count"] == 1

        step(
            actions=[
                {
                    "agent_id": 2,
                    "task_action": {
                        "type": "OFFER_HELP",
                        "task_index": 0,
                        "contribution": "guard builder",
                    },
                }
            ]
        )
        declined = step(
            actions=[
                {
                    "agent_id": expected_winner,
                    "task_action": {"type": "DECLINE_HELP", "offer_index": 0},
                }
            ]
        )
        assert declined.task_board[0]["pending_offer_count"] == 0

        built = declined
        for _ in range(40):
            built = step(30)
            if built.task_board[0]["status"] == "COMPLETED":
                break
        assert built.task_board[0]["status"] == "COMPLETED"
        assert int(observations[0]["team"]["copper"]) == 150

        supply_indices = [
            int(candidate["index"])
            for candidate in observations[0]["task_candidates"]
            if candidate["task_id"].startswith("T4:supply:")
        ]
        assert len(supply_indices) == 2
        supplied = step(
            actions=[
                {
                    "agent_id": i,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": supply_indices[i],
                    },
                }
                for i in (0, 1)
            ]
        )
        assert all(result["accepted"] for result in supplied.action_results)
        for _ in range(60):
            supplied = step(10)
            supply_tasks = [
                task for task in supplied.task_board
                if task["task_type"] == "SUPPLY_TURRET"
            ]
            if len(supply_tasks) == 2 and all(
                task["status"] == "COMPLETED" for task in supply_tasks
            ):
                break
        supply_tasks = [
            task for task in supplied.task_board if task["task_type"] == "SUPPLY_TURRET"
        ]
        assert len(supply_tasks) == 2
        assert all(task["status"] == "COMPLETED" for task in supply_tasks)
        assert [int(t["total_ammo"]) for t in observations[0]["team"]["turrets"]] == [30, 30]

        waited = step(actions=[{"agent_id": 2, "task_action": {"type": "WAIT"}}])
        assert waited.action_results[0]["accepted"] is True
        waited_again = step(actions=[{"agent_id": 2, "task_action": {"type": "WAIT"}}])
        assert waited_again.action_results[0]["accepted"] is True
        assert not any(task["task_type"] == "WAIT" for task in waited_again.task_board)
        assert waited_again.action_masks[2]["wait"] is True
        assert len(waited_again.task_board) <= 32

        summary = {
            "winner": expected_winner,
            "build_complete_tick": next(
                event["tick"]
                for record in transcript
                for event in record.get("events", [])
                if event["task_type"] == "BUILD_SCHEMATIC" and event["act"] == "COMPLETE"
            ),
            "final_tick": tick,
            "board_tasks": len(waited_again.task_board),
            "turret_ammo": [
                int(t["total_ammo"]) for t in observations[0]["team"]["turrets"]
            ],
        }
        if verbose:
            print(
                "coordination: "
                f"winner=agent_{summary['winner']} build_tick={summary['build_complete_tick']} "
                f"final_tick={summary['final_tick']} tasks={summary['board_tasks']} "
                f"ammo={summary['turret_ammo']}"
            )

    canonical = json.dumps(transcript, sort_keys=True, separators=(",", ":"))
    return canonical, summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="M5.2 coordination acceptance")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--java", default="java")
    args = parser.parse_args(argv)

    try:
        first, summary = _run_once(args.port, args.seed, args.java, True)
        second, _ = _run_once(args.port, args.seed, args.java, False)
    except (AssertionError, Exception) as exc:
        print(f"COORDINATION FAIL: {exc}", file=sys.stderr)
        return 1

    if first != second:
        print("COORDINATION FAIL: cross-process transcript mismatch", file=sys.stderr)
        return 1
    print(
        "COORDINATION OK: typed actions/events/board + task skills; "
        f"byte-identical replay through tick {summary['final_tick']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
