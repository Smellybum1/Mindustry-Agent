"""Live M5.5 deterministic agent-failure, lease-expiry, and reclaim check."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess


def _build_candidate(observation: dict[str, Any]) -> int:
    for candidate in observation["task_candidates"]:
        if candidate["task_type"] == "BUILD_SCHEMATIC":
            return int(candidate["index"])
    raise AssertionError("build candidate not found")


def _run_once(port: int, seed: int, java: str, verbose: bool) -> tuple[str, dict]:
    transcript: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    with RlServerProcess(
        LaunchConfig(port=port, java=java, build_if_missing=False)
    ) as env:
        env.handshake("m5-chaos-check")
        rr = env.reset(
            seed,
            agent_count=2,
            options={"lease_failure_agent_id": 0, "lease_failure_tick": 30},
        )
        episode = rr.episode_id
        tick = rr.tick
        observations = rr.initial_observations
        transcript.append({"reset_hash": rr.state_hash, "masks": rr.action_masks})

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
            events.extend(response.task_events)
            transcript.append(
                {
                    "hash": response.state_hash,
                    "results": response.action_results,
                    "board": response.task_board,
                    "events": response.task_events,
                    "metrics": response.coordination_metrics,
                    "outcome": response.outcome,
                    "terminations": response.terminations,
                }
            )
            return response

        selected = step(
            actions=[
                {
                    "agent_id": 0,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": _build_candidate(observations[0]),
                    },
                }
            ]
        )
        assert selected.action_results[0]["accepted"] is True
        assert selected.task_board[0]["reservation_count"] == 2

        # No more actions are sent for agent 0. At tick 30 the validation hook
        # freezes its controller and all adapter lifecycle reports.
        failed = step(30)
        assert observations[0]["skill"]["status"] == "READY"
        assert observations[0]["unit"]["build_queue_depth"] == 0
        assert 0.0 < float(failed.task_board[0]["progress"]) < 1.0
        assert failed.task_board[0]["status"] == "RUNNING"
        assert failed.task_board[0]["reservation_count"] == 2

        expired = step(650)
        expiry = next(
            event
            for event in expired.task_events
            if event["from_status"] == "RUNNING" and event["to_status"] == "EXPIRED"
        )
        assert expiry["agent_id"] == 0
        assert expired.task_board[0]["status"] == "OPEN"
        assert expired.task_board[0]["owner_agent_id"] == -1
        assert expired.task_board[0]["reservation_count"] == 0

        reclaimed = step(
            actions=[
                {
                    "agent_id": 1,
                    "task_action": {
                        "type": "SELECT_CANDIDATE_TASK",
                        "candidate_index": _build_candidate(observations[1]),
                    },
                }
            ]
        )
        assert reclaimed.action_results[0]["accepted"] is True
        assert reclaimed.task_board[0]["owner_agent_id"] == 1
        assert reclaimed.task_board[0]["reservation_count"] == 2

        completed = reclaimed
        for _ in range(40):
            completed = step(30)
            if completed.task_board[0]["status"] == "COMPLETED":
                break
        assert completed.task_board[0]["status"] == "COMPLETED"
        assert completed.task_board[0]["reservation_count"] == 0
        completion = next(
            event
            for event in events
            if event["task_type"] == "BUILD_SCHEMATIC" and event["act"] == "COMPLETE"
        )
        assert completion["agent_id"] == 1

        terminal = step(max(0, 3600 - tick))
        assert terminal.outcome == "loss"
        assert terminal.terminations == [True, True]
        assert terminal.truncations == [False, False]

        summary = {
            "expiry_tick": int(expiry["tick"]),
            "complete_tick": int(completion["tick"]),
            "terminal_tick": int(terminal.tick),
            "outcome": terminal.outcome,
        }
        if verbose:
            print(
                f"chaos: failed=agent_0 expired={summary['expiry_tick']} "
                f"reclaimed=agent_1 complete={summary['complete_tick']} "
                f"terminal={summary['terminal_tick']} outcome={summary['outcome']}"
            )

    return json.dumps(transcript, sort_keys=True, separators=(",", ":")), summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="M5.5 live lease recovery check")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--java", default="java")
    args = parser.parse_args(argv)

    try:
        first, summary = _run_once(args.port, args.seed, args.java, True)
        second, _ = _run_once(args.port, args.seed, args.java, False)
    except Exception as exc:
        print(f"CHAOS FAIL: {exc}", file=sys.stderr)
        return 1

    if first != second:
        print("CHAOS FAIL: cross-process transcript mismatch", file=sys.stderr)
        return 1
    print(
        "CHAOS OK: deterministic expiry + reclaim + completion + termination; "
        f"byte-identical replay through tick {summary['terminal_tick']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
