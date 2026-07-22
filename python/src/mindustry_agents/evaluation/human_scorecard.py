"""M10.4 human teammate scorecard derived from authoritative session capture."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

SCORECARD_SCHEMA = "human_teammate_scorecard_v1"
RATING_SCHEMA = "human_session_rating_v1"
RATING_FIELDS = frozenset(
    {
        "schema",
        "version",
        "session_content_sha256",
        "announcement_usefulness_rating",
        "keep_this_team",
        "comparative_rating_vs_scripted",
        "serious_session",
    }
)


def build_human_rating(
    session_content_sha256: str,
    announcement_usefulness_rating: int,
    keep_this_team: bool,
    comparative_rating_vs_scripted: int,
    serious_session: bool,
) -> dict[str, Any]:
    """Build the exact local rating schema from explicit human judgments."""

    return _validated_rating(
        {
            "schema": RATING_SCHEMA,
            "version": 1,
            "session_content_sha256": session_content_sha256,
            "announcement_usefulness_rating": announcement_usefulness_rating,
            "keep_this_team": keep_this_team,
            "comparative_rating_vs_scripted": comparative_rating_vs_scripted,
            "serious_session": serious_session,
        },
        session_content_sha256,
    )


def load_human_rating(path: Path, session_content_sha256: str) -> dict[str, Any]:
    """Load a local post-session rating bound to exactly one capture digest."""

    value = json.loads(path.read_text(encoding="utf-8"))
    return _validated_rating(value, session_content_sha256)


def _validated_rating(
    value: Any, session_content_sha256: str
) -> dict[str, Any]:
    if (
        not isinstance(session_content_sha256, str)
        or len(session_content_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in session_content_sha256
        )
    ):
        raise ValueError(
            "session content digest must be 64 lowercase hex characters"
        )
    if not isinstance(value, dict) or value.get("schema") != RATING_SCHEMA:
        raise ValueError("unsupported human session rating schema")
    if set(value) != RATING_FIELDS:
        raise ValueError("human session rating fields must match schema exactly")
    if value.get("version") != 1:
        raise ValueError("unsupported human session rating version")
    if value.get("session_content_sha256") != session_content_sha256:
        raise ValueError("human session rating digest mismatch")
    usefulness = value.get("announcement_usefulness_rating")
    if (
        isinstance(usefulness, bool)
        or not isinstance(usefulness, int)
        or not 1 <= usefulness <= 5
    ):
        raise ValueError("announcement usefulness rating must be an integer from 1 to 5")
    keep = value.get("keep_this_team")
    if not isinstance(keep, bool):
        raise ValueError("keep_this_team must be boolean")
    comparison = value.get("comparative_rating_vs_scripted")
    if (
        isinstance(comparison, bool)
        or not isinstance(comparison, int)
        or not -2 <= comparison <= 2
    ):
        raise ValueError("comparative rating must be an integer from -2 to 2")
    serious = value.get("serious_session")
    if not isinstance(serious, bool):
        raise ValueError("serious_session must be boolean")
    return {
        "schema": RATING_SCHEMA,
        "version": 1,
        "session_content_sha256": session_content_sha256,
        "announcement_usefulness_rating": usefulness,
        "keep_this_team": keep,
        "comparative_rating_vs_scripted": comparison,
        "serious_session": serious,
    }


def human_teammate_scorecard(
    records: list[dict[str, Any]],
    rating: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive M10.4 metrics without chat prose or inferred human preferences."""

    if rating is not None:
        rating = _validated_rating(rating, records[-1]["content_sha256"])

    accepted_controls = [
        record["control"]
        for record in records
        if record.get("record_type") == "control"
        and record.get("control", {}).get("accepted", False)
    ]
    trajectory_ticks = {
        int(record["tick"])
        for record in records
        if record.get("record_type") == "trajectory"
    }
    trajectory_boundaries = sum(
        record.get("record_type") == "trajectory" for record in records
    )
    applied_control_ticks = {int(control["tick"]) for control in accepted_controls}
    intervention_ticks = applied_control_ticks & trajectory_ticks

    created: dict[str, tuple[int, str]] = {}
    cancelled: dict[str, int] = {}
    help_requests: dict[str, deque[int]] = defaultdict(deque)
    for control in accepted_controls:
        command = control["canonical_command"]
        kind = command["type"]
        if kind == "GOAL":
            goal_id = str(control["goal_id"])
            task_type = str(command["task_type"])
            created[goal_id] = (int(control["tick"]), task_type)
            if task_type == "REQUEST_HELP" and not help_requests[goal_id]:
                help_requests[goal_id].append(int(control["tick"]))
        elif kind == "CANCEL":
            cancelled[str(control["goal_id"])] = int(control["tick"])

    completed: dict[str, int] = {}
    help_times: list[int] = []
    pending_presence: deque[tuple[str, int]] = deque()
    yield_latencies: list[int] = []
    conflicts = 0
    rendered = 0
    suppressed = 0
    for record in records:
        record_type = record.get("record_type")
        tick = int(record.get("tick", 0))
        if record_type == "human_presence":
            removed = {str(presence_id) for presence_id in record.get("removed", [])}
            if removed:
                pending_presence = deque(
                    entry for entry in pending_presence if entry[0] not in removed
                )
            pending_presence.extend(
                (str(presence["id"]), tick) for presence in record.get("added", [])
            )
            continue
        if record_type != "coordination":
            continue
        event = record.get("event", {})
        task_id = str(event.get("task_id", ""))
        act = str(event.get("act", ""))
        reason = str(event.get("reason_code", ""))
        if record.get("announcement_status") == "rendered":
            rendered += 1
        elif record.get("announcement_status") == "suppressed":
            suppressed += 1
        if task_id.startswith("human:goal:") and act == "COMPLETE":
            completed.setdefault(task_id, tick)
        if act == "REQUEST_HELP" and not help_requests[task_id]:
            help_requests[task_id].append(tick)
        if reason == "help_fulfilled" and help_requests[task_id]:
            help_times.append(tick - help_requests[task_id].popleft())
        if reason == "yield_to_human":
            conflicts += 1
            if pending_presence:
                _, presence_tick = pending_presence.popleft()
                yield_latencies.append(tick - presence_tick)

    eligible_goals = {
        goal_id
        for goal_id in created
        if goal_id in completed
        or goal_id not in cancelled
        or completed.get(goal_id, 2**63 - 1) <= cancelled[goal_id]
    }
    compliant_goals = eligible_goals & completed.keys()
    scorecard = {
        "human_intervention_rate": (
            len(intervention_ticks) / len(trajectory_ticks) if trajectory_ticks else None
        ),
        "human_intervention_ticks": len(intervention_ticks),
        "applied_control_ticks": len(applied_control_ticks),
        "accepted_human_commands": len(accepted_controls),
        "trajectory_boundaries": trajectory_boundaries,
        "trajectory_boundary_ticks": len(trajectory_ticks),
        "plan_conflicts_per_session": conflicts,
        "mean_yield_latency_ticks": (
            sum(yield_latencies) / len(yield_latencies) if yield_latencies else None
        ),
        "yield_latencies_observed": len(yield_latencies),
        "goal_compliance_rate": (
            len(compliant_goals) / len(eligible_goals) if eligible_goals else None
        ),
        "human_goals_created": len(created),
        "human_goals_eligible": len(eligible_goals),
        "human_goals_completed": len(compliant_goals),
        "mean_time_to_help_ticks": (
            sum(help_times) / len(help_times) if help_times else None
        ),
        "help_requests_observed": sum(len(queue) for queue in help_requests.values())
        + len(help_times),
        "help_fulfilments_observed": len(help_times),
        "rendered_announcements": rendered,
        "suppressed_announcements": suppressed,
        "announcement_usefulness_rating": (
            rating["announcement_usefulness_rating"] if rating else None
        ),
        "keep_this_team": rating["keep_this_team"] if rating else None,
        "comparative_rating_vs_scripted": (
            rating["comparative_rating_vs_scripted"] if rating else None
        ),
        "serious_session": rating["serious_session"] if rating else None,
    }
    return {
        "schema": SCORECARD_SCHEMA,
        "version": 1,
        "session_content_sha256": records[-1]["content_sha256"],
        "rating_status": "provided" if rating else "not_provided",
        "metrics": scorecard,
    }


def write_human_scorecard(path: Path, scorecard: dict[str, Any]) -> None:
    """Write one local scorecard without overwriting prior session evidence."""

    parent = path.parent
    if not parent.is_dir():
        raise ValueError(f"scorecard parent directory does not exist: {parent}")
    rendered = json.dumps(scorecard, sort_keys=True, separators=(",", ":")) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
    except FileExistsError as exc:
        raise ValueError(f"refusing to overwrite scorecard: {path}") from exc


def write_human_rating(path: Path, rating: dict[str, Any]) -> None:
    """Write one exact, digest-bound human rating without overwriting evidence."""

    digest = (
        rating.get("session_content_sha256") if isinstance(rating, dict) else None
    )
    validated = _validated_rating(rating, digest)
    parent = path.parent
    if not parent.is_dir():
        raise ValueError(f"rating parent directory does not exist: {parent}")
    rendered = json.dumps(validated, sort_keys=True, separators=(",", ":")) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
    except FileExistsError as exc:
        raise ValueError(f"refusing to overwrite rating: {path}") from exc
