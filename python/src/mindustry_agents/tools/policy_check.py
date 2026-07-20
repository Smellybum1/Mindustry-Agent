"""Live M5.3 scripted-policy and fulfilled-helper-contract acceptance."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from mindustry_agents.policies import HelperCoordinator, RoleAssignmentPolicy
from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess


def _candidate_index(observation: dict[str, Any], prefix: str) -> int:
    for candidate in observation["task_candidates"]:
        if candidate["task_id"].startswith(prefix):
            return int(candidate["index"])
    raise AssertionError(f"candidate prefix not found: {prefix}")


def _run_once(port: int, seed: int, java: str, verbose: bool) -> tuple[str, dict]:
    transcript: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    with RlServerProcess(
        LaunchConfig(port=port, java=java, build_if_missing=False)
    ) as env:
        env.handshake("m5-policy-check")

        rr = env.reset(seed, agent_count=3)
        episode = rr.episode_id
        tick = rr.tick
        observations = rr.initial_observations
        masks = rr.action_masks

        def step(ticks: int = 0, actions=None):
            nonlocal tick, observations, masks
            response = env.step(
                episode,
                expected_tick=tick,
                ticks_to_advance=ticks,
                agent_actions=actions or [],
            )
            tick = response.tick
            observations = response.observations
            masks = response.action_masks
            events.extend(response.task_events)
            transcript.append(
                {
                    "tick": response.tick,
                    "hash": response.state_hash,
                    "results": response.action_results,
                    "board": response.task_board,
                    "events": response.task_events,
                    "metrics": response.coordination_metrics,
                }
            )
            return response

        # Role policy: simultaneous miner/builder choices must announce distinct work.
        policy = RoleAssignmentPolicy(("miner", "builder", "supplier"))
        distinct = step(
            actions=[
                policy.action(0, observations[0], masks[0]),
                policy.action(1, observations[1], masks[1]),
            ]
        )
        owners = {
            task["owner_agent_id"]: task["task_type"]
            for task in distinct.task_board
            if task["owner_agent_id"] in (0, 1)
        }
        assert owners == {0: "HARVEST_RESOURCE", 1: "BUILD_SCHEMATIC"}
        assert {
            event["task_type"]
            for event in distinct.task_events
            if event["act"] == "ANNOUNCE_INTENT"
        } >= {"HARVEST_RESOURCE", "BUILD_SCHEMATIC"}

        # Start a clean helper trace with 98 copper, two short of the schematic.
        rr = env.reset(seed, agent_count=3)
        episode = rr.episode_id
        tick = rr.tick
        observations = rr.initial_observations
        masks = rr.action_masks
        transcript.append({"reset_hash": rr.state_hash, "masks": masks})
        events.clear()

        def run_command(agent_id: int, command: dict[str, Any], limit: int = 40):
            response = step(30, [{"agent_id": agent_id, "command": command}])
            for _ in range(limit - 1):
                skill = response.observations[agent_id]["skill"]
                if skill["status"] in {"SUCCEEDED", "BLOCKED", "FAILED"}:
                    return response
                response = step(30)
            raise AssertionError(f"command did not reach a terminal status: {command}")

        setup = [
            ("duo", 10, 10),
            ("duo", 13, 10),
            ("duo", 16, 10),
            ("duo", 19, 10),
            ("copper-wall", 22, 10),
            ("copper-wall", 23, 10),
        ]
        for block, x, y in setup:
            built = run_command(
                2,
                {
                    "type": "BUILD",
                    "block": block,
                    "tile_x": x,
                    "tile_y": y,
                    "rotation": 0,
                },
            )
            assert built.observations[2]["skill"]["status"] == "SUCCEEDED"
        assert int(observations[0]["team"]["copper"]) == 98

        build_index = _candidate_index(observations[1], "T3:build:")
        build_action = policy.action(1, observations[1], masks[1])
        assert build_action["task_action"]["candidate_index"] == build_index
        selected = step(actions=[build_action])
        assert selected.action_results[0]["accepted"] is True
        assert selected.action_results[0]["task_id"].startswith("T3:build:")

        blocked = selected
        for _ in range(50):
            blocked = step(30)
            build_task = next(
                task
                for task in blocked.task_board
                if task["task_id"].startswith("T3:build:")
            )
            if build_task["status"] == "BLOCKED":
                break
        assert build_task["status"] == "BLOCKED"
        assert build_task["reason"] == "resources_short"
        assert int(observations[0]["team"]["copper"]) < 6

        requested = step(actions=[HelperCoordinator.request(1)])
        assert requested.action_results[0]["accepted"] is True
        helper = HelperCoordinator.nearest_idle_helper(1, observations, masks)
        assert helper == 0
        board_index = next(
            int(task["index"])
            for task in requested.task_board
            if task["task_id"].startswith("T3:build:")
        )
        offered = step(actions=[HelperCoordinator.offer(helper, board_index)])
        assert offered.action_results[0]["accepted"] is True
        accepted = step(actions=[HelperCoordinator.accept(1)])
        assert accepted.action_results[0]["accepted"] is True
        assert next(
            task for task in accepted.task_board if task["index"] == board_index
        )["helper_count"] == 1

        mined = run_command(
            helper,
            {"type": "MINE", "tile_x": 32, "tile_y": 32, "amount": 20},
        )
        assert mined.observations[helper]["skill"]["status"] == "SUCCEEDED"
        mined_amount = int(mined.observations[helper]["unit"]["item_amount"])
        assert mined_amount >= 20, f"helper cargo after mining: {mined_amount}"
        core_before_delivery = int(mined.observations[0]["team"]["copper"])
        delivery = run_command(helper, {"type": "DELIVER_CORE"})
        assert delivery.observations[helper]["skill"]["status"] == "SUCCEEDED"
        assert int(delivery.observations[helper]["unit"]["item_amount"]) == 0
        assert any(event["reason_code"] == "help_fulfilled" for event in events)

        complete = step(actions=[policy.action(1, observations[1], masks[1])])
        for _ in range(40):
            build_task = next(
                task
                for task in complete.task_board
                if task["task_id"].startswith("T3:build:")
            )
            if build_task["status"] == "COMPLETED":
                break
            complete = step(30)
        assert build_task["status"] == "COMPLETED"
        assert sum(
            1
            for task in complete.task_board
            if task["task_id"].startswith("T3:build:")
        ) == 1
        assert sum(
            1
            for event in events
            if event["task_type"] == "BUILD_SCHEMATIC" and event["act"] == "COMPLETE"
        ) == 1

        summary = {
            "helper": helper,
            "blocked_tick": next(
                event["tick"]
                for event in events
                if event["task_type"] == "BUILD_SCHEMATIC"
                and event["act"] == "BLOCKED"
            ),
            "fulfilled_tick": next(
                event["tick"]
                for event in events
                if event["reason_code"] == "help_fulfilled"
            ),
            "complete_tick": next(
                event["tick"]
                for event in events
                if event["task_type"] == "BUILD_SCHEMATIC"
                and event["act"] == "COMPLETE"
            ),
            "delivered": mined_amount,
            "core_before_delivery": core_before_delivery,
            "core_final": int(observations[0]["team"]["copper"]),
            "metrics": complete.coordination_metrics,
        }
        if verbose:
            print(
                "policies: distinct=miner/builder "
                f"helper=agent_{helper} delivered={summary['delivered']} "
                f"blocked={summary['blocked_tick']} fulfilled={summary['fulfilled_tick']} "
                f"complete={summary['complete_tick']}"
            )

    return json.dumps(transcript, sort_keys=True, separators=(",", ":")), summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="M5.3 scripted-policy acceptance")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--java", default="java")
    args = parser.parse_args(argv)

    try:
        first, summary = _run_once(args.port, args.seed, args.java, True)
        second, _ = _run_once(args.port, args.seed, args.java, False)
    except Exception as exc:
        print(f"POLICY FAIL: {exc}", file=sys.stderr)
        return 1

    if first != second:
        print("POLICY FAIL: cross-process transcript mismatch", file=sys.stderr)
        return 1
    print(
        "POLICY OK: distinct roles + measurable helper fulfilment; "
        f"byte-identical replay through tick {summary['complete_tick']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
