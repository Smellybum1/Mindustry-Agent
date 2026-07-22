"""Replay public-demo candidate traces through the Python greedy fallback."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

from mindustry_agents.policies import GreedyUtilityPolicy

TRACE_MARKER = "AGENT-DEMO PUBLIC TRACE "
DIGEST_MARKER = "AGENT-DEMO DECISION DIGEST "
DIGEST_PATTERN = re.compile(r"digest=([0-9a-f]{64}) selections=([0-9]+)")


def load_trace(lines: Iterable[str]) -> tuple[list[dict[str, Any]], str, int]:
    """Extract complete trace records and the final Java selection digest."""

    records: list[dict[str, Any]] = []
    digest = ""
    selections = -1
    for line in lines:
        trace_at = line.find(TRACE_MARKER)
        if trace_at >= 0:
            payload = line[trace_at + len(TRACE_MARKER) :].strip()
            record = json.loads(payload)
            if not isinstance(record, dict):
                raise ValueError("public demo trace record must be an object")
            records.append(record)
        digest_at = line.find(DIGEST_MARKER)
        if digest_at >= 0:
            match = DIGEST_PATTERN.search(line[digest_at:])
            if match is None:
                raise ValueError("malformed public demo decision digest")
            digest = match.group(1)
            selections = int(match.group(2))
    if not records:
        raise ValueError("public demo trace contains no decision records")
    if not digest or selections < 0:
        raise ValueError("public demo trace contains no final decision digest")
    return records, digest, selections


def replay_trace(records: Iterable[dict[str, Any]]) -> tuple[str, int, int]:
    """Require action-for-action parity and reproduce accepted-selection digest."""

    policy = GreedyUtilityPolicy()
    accepted_rows: list[str] = []
    boundaries = 0
    actions_checked = 0
    previous_tick = -1
    for record in records:
        tick = int(record["tick"])
        if tick < previous_tick:
            raise ValueError(
                f"public demo trace tick regressed: {previous_tick} -> {tick}"
            )
        previous_tick = tick
        observations = record["observations"]
        masks = record["action_masks"]
        expected = record["actions"]
        actual = policy.actions(observations, masks)
        if actual != expected:
            raise AssertionError(
                f"public policy action mismatch at tick {tick}: "
                f"python={actual!r} java={expected!r}"
            )
        results = record["action_results"]
        if len(results) != len(expected):
            raise ValueError(f"action result cardinality drift at tick {tick}")
        for action, result in zip(expected, results):
            if not result.get("accepted", False):
                continue
            task_action = action.get("task_action", {})
            if task_action.get("type") != "SELECT_CANDIDATE_TASK":
                continue
            agent_id = int(action["agent_id"])
            candidate_index = int(task_action["candidate_index"])
            candidates = observations[agent_id]["task_candidates"]
            candidate = candidates[candidate_index]
            task_id = re.sub(r":at-[0-9]+$", ":at-*", str(candidate["task_id"]))
            accepted_rows.append(
                f"{agent_id}\x1f{task_id}\x1f{candidate['task_type']}"
            )
        policy.observe_action_results(results)
        boundaries += 1
        actions_checked += len(expected)
    payload = "".join(f"{row}\n" for row in accepted_rows).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), len(accepted_rows), actions_checked


def check_log(path: Path) -> tuple[int, int, int, str]:
    records, expected_digest, expected_selections = load_trace(
        path.read_text(encoding="utf-8").splitlines()
    )
    digest, selections, actions = replay_trace(records)
    if (digest, selections) != (expected_digest, expected_selections):
        raise AssertionError(
            "public policy selection digest mismatch: "
            f"python={digest}/{selections} java={expected_digest}/{expected_selections}"
        )
    return len(records), actions, selections, digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check Python/Java parity over a public demo candidate trace"
    )
    parser.add_argument("log", type=Path)
    args = parser.parse_args(argv)
    try:
        boundaries, actions, selections, digest = check_log(args.log)
    except Exception as exc:
        print(f"PUBLIC-DEMO-PARITY FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "PUBLIC-DEMO-PARITY OK "
        f"boundaries={boundaries} actions={actions} selections={selections} "
        f"digest={digest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
