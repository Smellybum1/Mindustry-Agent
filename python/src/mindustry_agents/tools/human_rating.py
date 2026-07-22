"""Create one explicit, digest-bound post-session human rating artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mindustry_agents.evaluation.human_scorecard import (
    build_human_rating,
    write_human_rating,
)
from mindustry_agents.telemetry.human_session import load_session


def _yes_no(value: str) -> bool:
    return value == "yes"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bind explicit human judgments to one completed demo capture."
    )
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--announcement-usefulness-rating",
        type=int,
        choices=range(1, 6),
        required=True,
    )
    parser.add_argument("--keep-this-team", choices=("yes", "no"), required=True)
    parser.add_argument(
        "--comparative-rating-vs-scripted",
        type=int,
        choices=range(-2, 3),
        required=True,
    )
    parser.add_argument("--serious-session", choices=("yes", "no"), required=True)
    args = parser.parse_args()

    records = load_session(args.session)
    rating = build_human_rating(
        records[-1]["content_sha256"],
        args.announcement_usefulness_rating,
        _yes_no(args.keep_this_team),
        args.comparative_rating_vs_scripted,
        _yes_no(args.serious_session),
    )
    write_human_rating(args.output, rating)
    print(json.dumps(rating, sort_keys=True, separators=(",", ":")))
    print(
        "HUMAN-RATING OK "
        f"serious={str(rating['serious_session']).lower()} "
        f"keep={str(rating['keep_this_team']).lower()}"
    )


if __name__ == "__main__":
    main()
