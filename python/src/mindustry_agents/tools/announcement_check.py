"""Live M5.6 rendered-announcement, rate-limit, and metrics acceptance."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from mindustry_agents.process.launcher import DEFAULT_PORT
from mindustry_agents.tools.policy_check import _run_once as run_policy_once


def _helper_records(raw: str) -> list[dict[str, Any]]:
    records = json.loads(raw)
    reset_index = max(
        index for index, record in enumerate(records) if "reset_hash" in record
    )
    return records[reset_index + 1 :]


def _validate(raw: str, *, print_lines: bool) -> dict[str, Any]:
    records = _helper_records(raw)
    events = [event for record in records for event in record.get("events", [])]
    announcements = [
        event["announcement"] for event in events if event.get("announcement")
    ]

    def position(act: str, *, reason: str | None = None) -> int:
        for index, event in enumerate(events):
            if event["act"] == act and (reason is None or event["reason_code"] == reason):
                return index
        raise AssertionError(f"event not found: {act}/{reason}")

    intent = next(
        index
        for index, event in enumerate(events)
        if event["act"] == "ANNOUNCE_INTENT"
        and event["task_type"] == "BUILD_SCHEMATIC"
    )
    progress = position("PROGRESS")
    blocked = position("BLOCKED", reason="resources_short")
    requested = position("REQUEST_HELP")
    offered = position("OFFER_HELP")
    accepted = position("ACCEPT_HELP")
    fulfilled = position("PROGRESS", reason="help_fulfilled")
    completed = position("COMPLETE")
    assert intent < progress < blocked < requested < offered < accepted < fulfilled < completed

    assert any(line.startswith("[Agent 1] Intending:") for line in announcements)
    assert "[Agent 1] Blocked: resources_short" in announcements
    assert "[Agent 0] Offering to help 1: deliver copper." in announcements
    assert any(line.startswith("[Agent 1] Complete:") for line in announcements)
    assert all(bool(event["announcement"]) == bool(event["announce"]) for event in events)
    assert all(
        not event["announcement"]
        for event in events
        if event["act"] in {"HEARTBEAT", "PROGRESS"}
    )

    offer_event = events[offered]
    accept_event = events[accepted]
    assert offer_event["announce"] is True
    assert accept_event["announce"] is False
    assert offer_event["tick"] == accept_event["tick"]
    assert len(announcements) <= 6
    assert len(events) <= 160

    final = records[-1]
    metrics = final["metrics"]
    assert metrics["structured_messages"] == len(events)
    assert metrics["announced_messages"] == len(announcements)
    assert metrics["tasks_completed"] == 1
    assert metrics["tasks_abandoned"] == 0
    assert metrics["duplicate_work_incidents"] == 0
    assert metrics["agent_ticks"] == int(final["tick"]) * 3
    assert 0.0 <= float(metrics["idle_fraction"]) <= 1.0

    if print_lines:
        print("announcement transcript:")
        for line in announcements:
            print(f"  {line}")
        print(
            "metrics: "
            f"structured={metrics['structured_messages']} "
            f"announced={metrics['announced_messages']} "
            f"completed={metrics['tasks_completed']} "
            f"idle_fraction={float(metrics['idle_fraction']):.3f}"
        )
    return metrics


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="M5.6 announcement/metrics check")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--java", default="java")
    args = parser.parse_args(argv)

    try:
        first, _ = run_policy_once(args.port, args.seed, args.java, False)
        metrics = _validate(first, print_lines=True)
        second, _ = run_policy_once(args.port, args.seed, args.java, False)
        _validate(second, print_lines=False)
    except Exception as exc:
        print(f"ANNOUNCEMENT FAIL: {exc}", file=sys.stderr)
        return 1

    if first != second:
        print("ANNOUNCEMENT FAIL: cross-process transcript mismatch", file=sys.stderr)
        return 1
    print(
        "ANNOUNCEMENT OK: rendered/rate-limited events + deterministic metrics; "
        f"announced={metrics['announced_messages']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
