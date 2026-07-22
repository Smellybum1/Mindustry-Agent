"""Aggregate M10 capture/rating pairs without claiming unmeasured acceptance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mindustry_agents.evaluation.human_evidence import (
    human_evidence_report,
    write_human_evidence,
)
from mindustry_agents.evaluation.human_scorecard import load_human_rating
from mindustry_agents.telemetry.human_session import load_session


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate pin-compatible M10 human session evidence."
    )
    parser.add_argument(
        "--entry",
        nargs=2,
        action="append",
        required=True,
        metavar=("SESSION", "RATING"),
        help="completed capture and its digest-bound rating; repeat per session",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    entries = []
    for session_value, rating_value in args.entry:
        records = load_session(Path(session_value))
        rating = load_human_rating(
            Path(rating_value), records[-1]["content_sha256"]
        )
        entries.append((records, rating))
    report = human_evidence_report(entries)
    write_human_evidence(args.output, report)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    print(
        "HUMAN-EVIDENCE OK "
        f"sessions={report['distinct_session_count']} "
        f"serious={report['serious_session_count']} "
        "pin_floor="
        f"{str(report['pin_compatible_serious_session_floor_met']).lower()} "
        "acceptance=not_evaluated"
    )


if __name__ == "__main__":
    main()
