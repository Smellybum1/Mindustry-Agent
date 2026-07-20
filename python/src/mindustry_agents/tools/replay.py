"""Replay and verify a checked-in deterministic action/coordination trace."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess

DEFAULT_GOLDEN = Path("tests/golden/bootstrap-defense-v0-scripted-v1.jsonl")


def load_trace(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as stream:
        return parse_trace_lines(stream)


def parse_trace_lines(lines) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = [json.loads(line) for line in lines if line.strip()]
    if not rows or rows[0].get("kind") != "manifest":
        raise ValueError("trace is missing its manifest")
    return rows[0], rows[1:]


def mutate_first_mine(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    changed = copy.deepcopy(records)
    for record in changed:
        for action in record.get("agent_actions", []):
            command = action.get("command") or {}
            if command.get("type") == "MINE":
                command["tile_x"] = int(command["tile_x"]) + 1
                return changed
    raise ValueError("trace contains no MINE command to mutate")


def replay_records(env, records: list[dict[str, Any]], *, expect_mismatch: bool = False) -> tuple[int, int]:
    episode = ""
    tick = 0
    checkpoints = 0
    total_ticks = 0
    for index, record in enumerate(records):
        if record["kind"] == "reset":
            response = env.reset(
                root_seed=int(record["seed"]), agent_count=int(record["agent_count"])
            )
            episode = response.episode_id
            tick = response.tick
            actual_hash = response.state_hash
            actual_events: list[dict[str, Any]] = []
        elif record["kind"] == "step":
            advance = int(record["ticks_to_advance"])
            response = env.step(
                episode,
                expected_tick=tick,
                ticks_to_advance=advance,
                agent_actions=record["agent_actions"],
            )
            tick = response.tick
            total_ticks += advance
            actual_hash = response.state_hash
            actual_events = response.task_events
        else:
            raise ValueError(f"unknown trace record kind at {index}: {record['kind']}")

        mismatch = actual_hash != record["state_hash"] or (
            record["kind"] == "step" and actual_events != record["task_events"]
        )
        if mismatch:
            if expect_mismatch:
                return checkpoints, total_ticks
            raise AssertionError(
                f"checkpoint {index} mismatch: expected={record['state_hash'][:24]} "
                f"actual={actual_hash[:24]}"
            )
        checkpoints += 1
    if expect_mismatch:
        raise AssertionError("deliberate one-line MINE mutation did not change the replay")
    return checkpoints, total_ticks


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Replay the M6 golden trace")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--java", default="java")
    parser.add_argument("--trace", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--negative-check", action="store_true")
    args = parser.parse_args(argv)

    try:
        manifest, records = load_trace(args.trace)
        with RlServerProcess(LaunchConfig(port=args.port, java=args.java)) as env:
            handshake = env.handshake("m6-golden-replay")
            if handshake.engine_commit != manifest["engine_commit"]:
                raise AssertionError("golden engine commit does not match runtime")
            checkpoints, ticks = replay_records(env, records)
            if args.negative_check:
                replay_records(env, mutate_first_mine(records), expect_mismatch=True)
    except Exception as exc:
        print(f"REPLAY FAIL: {exc}", file=sys.stderr)
        return 1

    print(
        f"REPLAY OK: checkpoints={checkpoints} ticks={ticks} episodes={manifest['episodes']}"
    )
    if args.negative_check:
        print("NEGATIVE REPLAY OK: one-line MINE target change flipped a checkpoint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
