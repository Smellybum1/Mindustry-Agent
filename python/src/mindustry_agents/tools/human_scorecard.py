"""Create a local M10.4 human teammate scorecard from a complete capture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mindustry_agents.evaluation.human_scorecard import (
    human_teammate_scorecard,
    load_human_rating,
    write_human_scorecard,
)
from mindustry_agents.telemetry.human_session import load_session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--rating", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    records = load_session(args.session)
    rating = (
        load_human_rating(args.rating, records[-1]["content_sha256"])
        if args.rating is not None
        else None
    )
    scorecard = human_teammate_scorecard(records, rating)
    write_human_scorecard(args.output, scorecard)
    print(json.dumps(scorecard, sort_keys=True, separators=(",", ":")))
    print(
        "HUMAN-SCORECARD OK "
        f"rating={scorecard['rating_status']} "
        f"conflicts={scorecard['metrics']['plan_conflicts_per_session']}"
    )


if __name__ == "__main__":
    main()
