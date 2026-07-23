"""Create and evaluate the precommitted M10 paired human protocol."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mindustry_agents.evaluation.human_protocol import (
    CONDITIONS,
    build_block_rating,
    build_human_protocol,
    human_protocol_report,
    load_block_rating,
    load_human_protocol,
    write_block_rating,
    write_human_protocol,
    write_human_protocol_report,
)
from mindustry_agents.evaluation.human_scorecard import load_human_rating
from mindustry_agents.telemetry.human_session import load_session


def _yes_no(value: str) -> bool:
    return value == "yes"


def _load_sessions(values: list[list[str]]) -> dict[str, list[dict]]:
    sessions = {condition: load_session(Path(path)) for condition, path in values}
    if set(sessions) != set(CONDITIONS) or len(values) != len(CONDITIONS):
        raise ValueError("exactly one session per absent/scripted/learned condition is required")
    return sessions


def _load_rated_sessions(
    values: list[list[str]],
) -> dict[str, tuple[list[dict], dict]]:
    result = {}
    for condition, session_path, rating_path in values:
        records = load_session(Path(session_path))
        rating = load_human_rating(
            Path(rating_path), records[-1]["content_sha256"]
        )
        result[condition] = (records, rating)
    if set(result) != set(CONDITIONS) or len(values) != len(CONDITIONS):
        raise ValueError("exactly one rated session per condition is required")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Govern M10 paired absent/scripted/learned human evidence."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="freeze a protocol from a v4 reference")
    create.add_argument("--reference-session", type=Path, required=True)
    create.add_argument("--experiment-id", required=True)
    create.add_argument("--learned-policy", required=True)
    create.add_argument("--output", type=Path, required=True)

    rate = subparsers.add_parser("rate-block", help="bind paired judgments to one block")
    rate.add_argument("--protocol", type=Path, required=True)
    rate.add_argument("--block-id", required=True)
    rate.add_argument(
        "--session",
        nargs=2,
        action="append",
        required=True,
        metavar=("CONDITION", "CAPTURE"),
    )
    rate.add_argument(
        "--learned-vs-absent-preference", type=int, choices=range(-2, 3), required=True
    )
    rate.add_argument(
        "--learned-vs-scripted-preference", type=int, choices=range(-2, 3), required=True
    )
    rate.add_argument("--serious-block", choices=("yes", "no"), required=True)
    rate.add_argument("--output", type=Path, required=True)

    report = subparsers.add_parser("report", help="evaluate complete rated blocks")
    report.add_argument("--protocol", type=Path, required=True)
    report.add_argument(
        "--block",
        nargs=8,
        action="append",
        required=True,
        metavar=(
            "BLOCK_ID",
            "BLOCK_RATING",
            "ABSENT_CAPTURE",
            "ABSENT_RATING",
            "SCRIPTED_CAPTURE",
            "SCRIPTED_RATING",
            "LEARNED_CAPTURE",
            "LEARNED_RATING",
        ),
    )
    report.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "create":
        protocol = build_human_protocol(
            load_session(args.reference_session), args.experiment_id, args.learned_policy
        )
        write_human_protocol(args.output, protocol)
        result = protocol
        status = f"HUMAN-PROTOCOL OK experiment={protocol['experiment_id']} blocks=3"
    elif args.command == "rate-block":
        protocol = load_human_protocol(args.protocol)
        sessions = _load_sessions(args.session)
        rating = build_block_rating(
            protocol,
            args.block_id,
            sessions,
            args.learned_vs_absent_preference,
            args.learned_vs_scripted_preference,
            _yes_no(args.serious_block),
        )
        write_block_rating(args.output, rating, protocol)
        result = rating
        status = f"HUMAN-BLOCK-RATING OK block={args.block_id}"
    else:
        protocol = load_human_protocol(args.protocol)
        entries = []
        for values in args.block:
            block_id, block_rating_path, *session_values = values
            rated_sessions = _load_rated_sessions(
                [
                    ["absent", session_values[0], session_values[1]],
                    ["scripted", session_values[2], session_values[3]],
                    ["learned", session_values[4], session_values[5]],
                ]
            )
            block_rating = load_block_rating(
                Path(block_rating_path), protocol, block_id
            )
            entries.append((block_id, rated_sessions, block_rating))
        result = human_protocol_report(protocol, entries)
        write_human_protocol_report(args.output, result)
        status = (
            "HUMAN-ACCEPTANCE OK "
            f"status={result['acceptance_status']} "
            f"serious_blocks={result['complete_serious_block_count']}"
        )

    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print(status)


if __name__ == "__main__":
    main()
