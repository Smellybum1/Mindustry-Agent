"""M10 human-evidence aggregation over authoritative capture/rating pairs."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

from mindustry_agents.evaluation.human_scorecard import human_teammate_scorecard
from mindustry_agents.telemetry.human_session import (
    CAPTURE_PROVENANCE_FIELDS,
    CAPTURE_PROVENANCE_FIELDS_BY_VERSION,
)

EVIDENCE_SCHEMA = "human_teammate_evidence_v2"
MINIMUM_SERIOUS_SESSIONS = 3
BASE_IDENTITY_FIELDS = (
    "capture_schema_version",
    "engine_tag",
    "engine_commit",
    "arc_version",
    "protocol_version",
    "scenario_id",
    "scenario_version",
    "policy",
)
IDENTITY_FIELDS = BASE_IDENTITY_FIELDS + CAPTURE_PROVENANCE_FIELDS
MEAN_METRICS = (
    "human_intervention_rate",
    "plan_conflicts_per_session",
    "mean_yield_latency_ticks",
    "goal_compliance_rate",
    "mean_time_to_help_ticks",
    "announcement_usefulness_rating",
    "comparative_rating_vs_scripted",
)


def _metric_summary(rows: Sequence[dict[str, Any]], name: str) -> dict[str, Any]:
    observed = [
        row["metrics"][name]
        for row in rows
        if row["metrics"][name] is not None
    ]
    return {
        "observed_sessions": len(observed),
        "mean": sum(observed) / len(observed) if observed else None,
    }


def _aggregate(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    keep = [row["metrics"]["keep_this_team"] for row in rows]
    return {
        **{name: _metric_summary(rows, name) for name in MEAN_METRICS},
        "keep_this_team_rate": {
            "observed_sessions": len(keep),
            "mean": sum(keep) / len(keep) if keep else None,
        },
    }


def human_evidence_report(
    entries: Sequence[tuple[list[dict[str, Any]], dict[str, Any]]],
) -> dict[str, Any]:
    """Aggregate distinct sessions without claiming unprecommitted acceptance."""

    if not entries:
        raise ValueError("human evidence requires at least one session/rating pair")

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for records, rating in entries:
        if not records or records[0].get("record_type") != "session_start":
            raise ValueError("human evidence entry must start with session_start")
        scorecard = human_teammate_scorecard(records, rating)
        if scorecard["rating_status"] != "provided":
            raise ValueError("human evidence entry requires an explicit rating")
        digest = scorecard["session_content_sha256"]
        if digest in seen:
            raise ValueError(f"duplicate human session digest: {digest}")
        seen.add(digest)
        start = records[0]
        schema_version = start.get("capture_schema_version", 0)
        required_identity = (
            BASE_IDENTITY_FIELDS
            + CAPTURE_PROVENANCE_FIELDS_BY_VERSION.get(schema_version, ())
        )
        missing = [field for field in required_identity if field not in start]
        if missing:
            raise ValueError(
                "human evidence session identity missing: " + ", ".join(missing)
            )
        provenance_complete = schema_version >= 3
        identity = {
            field: start.get(field) for field in IDENTITY_FIELDS
        }
        rows.append(
            {
                "session_content_sha256": digest,
                "identity": identity,
                "provenance_complete": provenance_complete,
                "serious_session": scorecard["metrics"]["serious_session"],
                "metrics": scorecard["metrics"],
            }
        )
    rows.sort(key=lambda row: row["session_content_sha256"])

    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = tuple(row["identity"][field] for field in IDENTITY_FIELDS)
        grouped[key].append(row)

    groups = []
    pin_floor_met = False
    for key in sorted(grouped, key=lambda value: tuple(str(item) for item in value)):
        group_rows = grouped[key]
        serious_rows = [row for row in group_rows if row["serious_session"]]
        provenance_complete = all(
            row["provenance_complete"] for row in group_rows
        )
        floor_met = (
            provenance_complete
            and len(serious_rows) >= MINIMUM_SERIOUS_SESSIONS
        )
        pin_floor_met = pin_floor_met or floor_met
        groups.append(
            {
                "identity": dict(zip(IDENTITY_FIELDS, key, strict=True)),
                "session_count": len(group_rows),
                "serious_session_count": len(serious_rows),
                "provenance_complete": provenance_complete,
                "serious_session_floor_met": floor_met,
                "session_content_sha256": [
                    row["session_content_sha256"] for row in group_rows
                ],
                "serious_metrics": _aggregate(serious_rows),
            }
        )

    serious_rows = [row for row in rows if row["serious_session"]]
    blockers = [
        "scorecard_targets_not_precommitted",
        "agents_present_vs_absent_not_measured_by_rating_v1",
    ]
    if any(not row["provenance_complete"] for row in rows):
        blockers.insert(0, "legacy_capture_schema_excluded_from_acceptance")
    if not pin_floor_met:
        blockers.insert(0, "fewer_than_three_pin_compatible_serious_sessions")
    return {
        "schema": EVIDENCE_SCHEMA,
        "version": 2,
        "minimum_serious_sessions": MINIMUM_SERIOUS_SESSIONS,
        "distinct_session_count": len(rows),
        "serious_session_count": len(serious_rows),
        "pin_compatible_serious_session_floor_met": pin_floor_met,
        "acceptance_status": "not_evaluated",
        "blocking_reasons": blockers,
        "serious_metrics_all_identities": _aggregate(serious_rows),
        "groups": groups,
    }


def write_human_evidence(path: Path, report: dict[str, Any]) -> None:
    """Write one deterministic evidence report without overwriting prior data."""

    if not path.parent.is_dir():
        raise ValueError(f"evidence parent directory does not exist: {path.parent}")
    rendered = json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
    except FileExistsError as exc:
        raise ValueError(f"refusing to overwrite human evidence: {path}") from exc
