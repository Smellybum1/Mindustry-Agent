"""Precommitted M10 paired-condition protocol and acceptance evaluator."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from mindustry_agents.evaluation.human_scorecard import human_teammate_scorecard

PROTOCOL_SCHEMA = "human_teammate_protocol_v1"
BLOCK_RATING_SCHEMA = "human_teammate_block_rating_v1"
REPORT_SCHEMA = "human_teammate_acceptance_v1"
CONDITIONS = ("absent", "scripted", "learned")
MINIMUM_SERIOUS_BLOCKS = 3
RUNTIME_IDENTITY_FIELDS = (
    "engine_tag",
    "engine_commit",
    "arc_version",
    "protocol_version",
    "scenario_id",
    "scenario_version",
    "repository_commit",
    "agent_plugin_content_sha256",
    "server_content_sha256",
)
OBJECTIVE_DIRECTIONS = {
    "human_intervention_rate": "lower",
    "plan_conflicts_per_session": "lower",
    "mean_yield_latency_ticks": "lower",
    "goal_compliance_rate": "higher",
    "mean_time_to_help_ticks": "lower",
    "announcement_usefulness_rating": "higher",
}
LATIN_ORDERS = (
    ("absent", "scripted", "learned"),
    ("scripted", "learned", "absent"),
    ("learned", "absent", "scripted"),
)


def _slug(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 80:
        raise ValueError(f"{field} must be a non-empty string of at most 80 characters")
    if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in value):
        raise ValueError(f"{field} must use lowercase letters, digits, hyphen, or underscore")
    return value


def _digest(value: Any, field: str, length: int = 64) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be {length} lowercase hex characters")
    return value


def _reference_start(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records or records[0].get("record_type") != "session_start":
        raise ValueError("protocol reference must start with session_start")
    start = records[0]
    if start.get("capture_schema_version", 0) < 4:
        raise ValueError("paired protocol requires capture schema v4 or later")
    for field in RUNTIME_IDENTITY_FIELDS:
        if field not in start:
            raise ValueError(f"protocol reference missing {field}")
    _digest(start["repository_commit"], "repository_commit", 40)
    _digest(start["agent_plugin_content_sha256"], "agent_plugin_content_sha256")
    _digest(start["server_content_sha256"], "server_content_sha256")
    return start


def build_human_protocol(
    reference_records: list[dict[str, Any]],
    experiment_id: str,
    learned_policy: str,
) -> dict[str, Any]:
    """Freeze a three-block Latin-square comparison before acceptance play."""

    start = _reference_start(reference_records)
    experiment_id = _slug(experiment_id, "experiment_id")
    learned_policy = _slug(learned_policy, "learned_policy")
    if learned_policy in {
        "agents-absent-human-only-v1",
        "public-greedy-candidates-v1",
    }:
        raise ValueError("learned_policy must identify a distinct promoted policy")

    blocks = []
    for index, order in enumerate(LATIN_ORDERS, 1):
        block_id = f"block-{index:03d}"
        seed_material = f"{experiment_id}\0{block_id}".encode("ascii")
        trial_seed = int(hashlib.sha256(seed_material).hexdigest()[:15], 16)
        blocks.append(
            {
                "block_id": block_id,
                "trial_seed": trial_seed,
                "condition_order": list(order),
            }
        )
    protocol = {
        "schema": PROTOCOL_SCHEMA,
        "version": 1,
        "experiment_id": experiment_id,
        "minimum_complete_serious_blocks": MINIMUM_SERIOUS_BLOCKS,
        "runtime_identity": {
            field: start[field] for field in RUNTIME_IDENTITY_FIELDS
        },
        "conditions": {
            "absent": {
                "policy": "agents-absent-human-only-v1",
                "agent_condition": "absent",
            },
            "scripted": {
                "policy": "public-greedy-candidates-v1",
                "agent_condition": "present",
            },
            "learned": {
                "policy": learned_policy,
                "agent_condition": "present",
            },
        },
        "blocks": blocks,
        "objective_targets": {
            metric: {"direction": direction, "minimum_mean_improvement": 0.0}
            for metric, direction in OBJECTIVE_DIRECTIONS.items()
        },
        "preference_targets": {
            "learned_vs_absent_minimum_positive_blocks": 2,
            "learned_vs_absent_mean_must_be_positive": True,
            "learned_vs_scripted_minimum_nonnegative_blocks": 2,
            "learned_vs_scripted_minimum_mean": 0.0,
            "learned_keep_team_minimum_rate": 2 / 3,
        },
    }
    return validate_human_protocol(protocol)


def validate_human_protocol(value: Any) -> dict[str, Any]:
    """Validate the exact immutable protocol schema."""

    if not isinstance(value, dict) or value.get("schema") != PROTOCOL_SCHEMA:
        raise ValueError("unsupported human teammate protocol schema")
    expected = {
        "schema",
        "version",
        "experiment_id",
        "minimum_complete_serious_blocks",
        "runtime_identity",
        "conditions",
        "blocks",
        "objective_targets",
        "preference_targets",
    }
    if set(value) != expected or value.get("version") != 1:
        raise ValueError("human teammate protocol fields/version mismatch")
    _slug(value["experiment_id"], "experiment_id")
    if value["minimum_complete_serious_blocks"] != MINIMUM_SERIOUS_BLOCKS:
        raise ValueError("human teammate protocol serious-block floor mismatch")
    runtime = value.get("runtime_identity")
    if not isinstance(runtime, dict) or set(runtime) != set(RUNTIME_IDENTITY_FIELDS):
        raise ValueError("human teammate protocol runtime identity mismatch")
    _digest(runtime["repository_commit"], "repository_commit", 40)
    _digest(runtime["agent_plugin_content_sha256"], "agent_plugin_content_sha256")
    _digest(runtime["server_content_sha256"], "server_content_sha256")
    conditions = value.get("conditions")
    if not isinstance(conditions, dict) or set(conditions) != set(CONDITIONS):
        raise ValueError("human teammate protocol conditions mismatch")
    expected_fixed = {
        "absent": ("agents-absent-human-only-v1", "absent"),
        "scripted": ("public-greedy-candidates-v1", "present"),
    }
    for name in CONDITIONS:
        condition = conditions[name]
        if not isinstance(condition, dict) or set(condition) != {
            "policy",
            "agent_condition",
        }:
            raise ValueError(f"human teammate protocol {name} condition mismatch")
        _slug(condition["policy"], f"{name} policy")
        if condition["agent_condition"] not in {"present", "absent"}:
            raise ValueError(f"human teammate protocol {name} agent condition invalid")
    for name, expected_condition in expected_fixed.items():
        observed = conditions[name]
        if (observed["policy"], observed["agent_condition"]) != expected_condition:
            raise ValueError(f"human teammate protocol {name} identity is not canonical")
    if conditions["learned"]["agent_condition"] != "present" or conditions[
        "learned"
    ]["policy"] in {item[0] for item in expected_fixed.values()}:
        raise ValueError("human teammate protocol learned policy is not distinct")

    blocks = value.get("blocks")
    if not isinstance(blocks, list) or len(blocks) != MINIMUM_SERIOUS_BLOCKS:
        raise ValueError("human teammate protocol requires exactly three blocks")
    for index, (block, expected_order) in enumerate(zip(blocks, LATIN_ORDERS), 1):
        if not isinstance(block, dict) or set(block) != {
            "block_id",
            "trial_seed",
            "condition_order",
        }:
            raise ValueError("human teammate protocol block fields mismatch")
        if block["block_id"] != f"block-{index:03d}":
            raise ValueError("human teammate protocol block id/order mismatch")
        if (
            isinstance(block["trial_seed"], bool)
            or not isinstance(block["trial_seed"], int)
            or block["trial_seed"] < 0
        ):
            raise ValueError("human teammate protocol trial seed is invalid")
        if tuple(block["condition_order"]) != expected_order:
            raise ValueError("human teammate protocol Latin-square order mismatch")
    expected_objective = {
        metric: {"direction": direction, "minimum_mean_improvement": 0.0}
        for metric, direction in OBJECTIVE_DIRECTIONS.items()
    }
    if value.get("objective_targets") != expected_objective:
        raise ValueError("human teammate protocol objective targets mismatch")
    expected_preference = {
        "learned_vs_absent_minimum_positive_blocks": 2,
        "learned_vs_absent_mean_must_be_positive": True,
        "learned_vs_scripted_minimum_nonnegative_blocks": 2,
        "learned_vs_scripted_minimum_mean": 0.0,
        "learned_keep_team_minimum_rate": 2 / 3,
    }
    if value.get("preference_targets") != expected_preference:
        raise ValueError("human teammate protocol preference targets mismatch")
    return value


def load_human_protocol(path: Path) -> dict[str, Any]:
    return validate_human_protocol(json.loads(path.read_text(encoding="utf-8")))


def _write_new(path: Path, value: dict[str, Any], kind: str) -> None:
    if not path.parent.is_dir():
        raise ValueError(f"{kind} parent directory does not exist: {path.parent}")
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
    except FileExistsError as exc:
        raise ValueError(f"refusing to overwrite {kind}: {path}") from exc


def write_human_protocol(path: Path, protocol: dict[str, Any]) -> None:
    _write_new(path, validate_human_protocol(protocol), "human teammate protocol")


def _block(protocol: dict[str, Any], block_id: str) -> dict[str, Any]:
    for block in protocol["blocks"]:
        if block["block_id"] == block_id:
            return block
    raise ValueError(f"unknown human teammate protocol block: {block_id}")


def validate_assigned_session(
    protocol: dict[str, Any],
    block_id: str,
    condition_name: str,
    records: list[dict[str, Any]],
) -> str:
    """Verify that capture-time assignment matches one frozen protocol slot."""

    protocol = validate_human_protocol(protocol)
    if condition_name not in CONDITIONS:
        raise ValueError(f"unknown human teammate condition: {condition_name}")
    block = _block(protocol, block_id)
    start = _reference_start(records)
    for field, expected in protocol["runtime_identity"].items():
        if start.get(field) != expected:
            raise ValueError(f"human teammate session {field} mismatch")
    condition = protocol["conditions"][condition_name]
    expected_assignment = {
        "policy": condition["policy"],
        "agent_condition": condition["agent_condition"],
        "experiment_id": protocol["experiment_id"],
        "experiment_block": block_id,
        "experiment_condition": condition_name,
        "experiment_order": block["condition_order"].index(condition_name) + 1,
        "trial_seed": block["trial_seed"],
    }
    for field, expected in expected_assignment.items():
        if start.get(field) != expected:
            raise ValueError(f"human teammate session {field} mismatch")
    if not records[-1].get("content_sha256"):
        raise ValueError("human teammate session is incomplete")
    return _digest(records[-1]["content_sha256"], "session content digest")


def build_block_rating(
    protocol: dict[str, Any],
    block_id: str,
    sessions: Mapping[str, list[dict[str, Any]]],
    learned_vs_absent_preference: int,
    learned_vs_scripted_preference: int,
    serious_block: bool,
) -> dict[str, Any]:
    """Bind direct paired judgments to all three authoritative captures."""

    if set(sessions) != set(CONDITIONS):
        raise ValueError("block rating requires absent, scripted, and learned sessions")
    for value, name in (
        (learned_vs_absent_preference, "learned_vs_absent_preference"),
        (learned_vs_scripted_preference, "learned_vs_scripted_preference"),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or not -2 <= value <= 2:
            raise ValueError(f"{name} must be an integer from -2 to 2")
    if not isinstance(serious_block, bool):
        raise ValueError("serious_block must be boolean")
    digests = {
        condition: validate_assigned_session(
            protocol, block_id, condition, sessions[condition]
        )
        for condition in CONDITIONS
    }
    return {
        "schema": BLOCK_RATING_SCHEMA,
        "version": 1,
        "experiment_id": protocol["experiment_id"],
        "block_id": block_id,
        "session_content_sha256": digests,
        "learned_vs_absent_preference": learned_vs_absent_preference,
        "learned_vs_scripted_preference": learned_vs_scripted_preference,
        "serious_block": serious_block,
    }


def validate_block_rating(
    value: Any, protocol: dict[str, Any], block_id: str
) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != BLOCK_RATING_SCHEMA:
        raise ValueError("unsupported human teammate block rating schema")
    expected = {
        "schema",
        "version",
        "experiment_id",
        "block_id",
        "session_content_sha256",
        "learned_vs_absent_preference",
        "learned_vs_scripted_preference",
        "serious_block",
    }
    if set(value) != expected or value.get("version") != 1:
        raise ValueError("human teammate block rating fields/version mismatch")
    if value.get("experiment_id") != protocol["experiment_id"] or value.get(
        "block_id"
    ) != block_id:
        raise ValueError("human teammate block rating assignment mismatch")
    digests = value.get("session_content_sha256")
    if not isinstance(digests, dict) or set(digests) != set(CONDITIONS):
        raise ValueError("human teammate block rating session digests mismatch")
    for condition, digest in digests.items():
        _digest(digest, f"{condition} session content digest")
    for field in (
        "learned_vs_absent_preference",
        "learned_vs_scripted_preference",
    ):
        preference = value.get(field)
        if (
            isinstance(preference, bool)
            or not isinstance(preference, int)
            or not -2 <= preference <= 2
        ):
            raise ValueError(f"{field} must be an integer from -2 to 2")
    if not isinstance(value.get("serious_block"), bool):
        raise ValueError("serious_block must be boolean")
    return value


def load_block_rating(
    path: Path, protocol: dict[str, Any], block_id: str
) -> dict[str, Any]:
    return validate_block_rating(
        json.loads(path.read_text(encoding="utf-8")), protocol, block_id
    )


def write_block_rating(
    path: Path, rating: dict[str, Any], protocol: dict[str, Any]
) -> None:
    validated = validate_block_rating(rating, protocol, rating.get("block_id", ""))
    _write_new(path, validated, "human teammate block rating")


def _improvement(metric: str, learned: Any, scripted: Any) -> float | None:
    if learned is None or scripted is None:
        return None
    if OBJECTIVE_DIRECTIONS[metric] == "higher":
        return float(learned) - float(scripted)
    return float(scripted) - float(learned)


def human_protocol_report(
    protocol: dict[str, Any],
    entries: Sequence[
        tuple[
            str,
            Mapping[str, tuple[list[dict[str, Any]], dict[str, Any]]],
            dict[str, Any],
        ]
    ],
) -> dict[str, Any]:
    """Evaluate only preassigned complete blocks against frozen targets."""

    protocol = validate_human_protocol(protocol)
    if not entries:
        raise ValueError("human teammate acceptance requires at least one block")
    seen_blocks: set[str] = set()
    seen_sessions: set[str] = set()
    block_rows = []
    for block_id, sessions, block_rating in entries:
        if block_id in seen_blocks:
            raise ValueError(f"duplicate human teammate block: {block_id}")
        seen_blocks.add(block_id)
        if set(sessions) != set(CONDITIONS):
            raise ValueError("acceptance block requires all three conditions")
        validated_rating = validate_block_rating(block_rating, protocol, block_id)
        scorecards = {}
        session_serious = True
        for condition in CONDITIONS:
            records, rating = sessions[condition]
            digest = validate_assigned_session(protocol, block_id, condition, records)
            if digest in seen_sessions:
                raise ValueError(f"duplicate human teammate session: {digest}")
            seen_sessions.add(digest)
            if validated_rating["session_content_sha256"][condition] != digest:
                raise ValueError("human teammate block rating digest mismatch")
            scorecard = human_teammate_scorecard(records, rating)
            if scorecard["rating_status"] != "provided":
                raise ValueError("human teammate acceptance requires session ratings")
            scorecards[condition] = scorecard
            session_serious = session_serious and bool(
                scorecard["metrics"]["serious_session"]
            )
        serious = validated_rating["serious_block"] and session_serious
        improvements = {
            metric: _improvement(
                metric,
                scorecards["learned"]["metrics"][metric],
                scorecards["scripted"]["metrics"][metric],
            )
            for metric in OBJECTIVE_DIRECTIONS
        }
        block_rows.append(
            {
                "block_id": block_id,
                "serious": serious,
                "session_content_sha256": dict(
                    validated_rating["session_content_sha256"]
                ),
                "learned_vs_absent_preference": validated_rating[
                    "learned_vs_absent_preference"
                ],
                "learned_vs_scripted_preference": validated_rating[
                    "learned_vs_scripted_preference"
                ],
                "learned_keep_this_team": scorecards["learned"]["metrics"][
                    "keep_this_team"
                ],
                "objective_improvement_vs_scripted": improvements,
            }
        )
    block_rows.sort(key=lambda row: row["block_id"])
    serious_rows = [row for row in block_rows if row["serious"]]
    floor_met = len(serious_rows) >= protocol["minimum_complete_serious_blocks"]

    objective = {}
    objective_pass = floor_met
    for metric in OBJECTIVE_DIRECTIONS:
        observed = [
            row["objective_improvement_vs_scripted"][metric]
            for row in serious_rows
            if row["objective_improvement_vs_scripted"][metric] is not None
        ]
        mean = sum(observed) / len(observed) if observed else None
        passed = floor_met and len(observed) == len(serious_rows) and mean is not None and mean >= 0.0
        objective[metric] = {
            "observed_blocks": len(observed),
            "mean_improvement": mean,
            "passed": passed,
        }
        objective_pass = objective_pass and passed

    absent_values = [row["learned_vs_absent_preference"] for row in serious_rows]
    scripted_values = [row["learned_vs_scripted_preference"] for row in serious_rows]
    keep_values = [bool(row["learned_keep_this_team"]) for row in serious_rows]
    absent_mean = sum(absent_values) / len(absent_values) if absent_values else None
    scripted_mean = sum(scripted_values) / len(scripted_values) if scripted_values else None
    keep_rate = sum(keep_values) / len(keep_values) if keep_values else None
    preference_pass = (
        floor_met
        and sum(value > 0 for value in absent_values) >= 2
        and absent_mean is not None
        and absent_mean > 0.0
        and sum(value >= 0 for value in scripted_values) >= 2
        and scripted_mean is not None
        and scripted_mean >= 0.0
        and keep_rate is not None
        and keep_rate >= 2 / 3
    )
    blockers = []
    if not floor_met:
        blockers.append("fewer_than_three_complete_serious_blocks")
    if not objective_pass:
        blockers.append("learned_objective_scorecard_regresses_vs_scripted")
    if not preference_pass:
        blockers.append("paired_owner_preference_target_not_met")
    return {
        "schema": REPORT_SCHEMA,
        "version": 1,
        "experiment_id": protocol["experiment_id"],
        "protocol_sha256": hashlib.sha256(
            json.dumps(protocol, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "complete_block_count": len(block_rows),
        "complete_serious_block_count": len(serious_rows),
        "serious_block_floor_met": floor_met,
        "objective_scorecard": objective,
        "preference": {
            "learned_vs_absent_positive_blocks": sum(
                value > 0 for value in absent_values
            ),
            "learned_vs_absent_mean": absent_mean,
            "learned_vs_scripted_nonnegative_blocks": sum(
                value >= 0 for value in scripted_values
            ),
            "learned_vs_scripted_mean": scripted_mean,
            "learned_keep_team_rate": keep_rate,
            "passed": preference_pass,
        },
        "acceptance_status": "passed" if not blockers else "not_passed",
        "blocking_reasons": blockers,
        "blocks": block_rows,
    }


def write_human_protocol_report(path: Path, report: dict[str, Any]) -> None:
    _write_new(path, report, "human teammate acceptance report")
