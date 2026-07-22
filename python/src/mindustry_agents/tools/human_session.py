"""Command-line validation and summary for an opt-in M10.3 demo capture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mindustry_agents.telemetry.human_session import (
    load_partner_population,
    load_session,
    session_summary,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--population", type=Path)
    args = parser.parse_args()

    records = load_session(args.session)
    population = (
        load_partner_population(args.population) if args.population is not None else None
    )
    summary = session_summary(records, population)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    print(
        "HUMAN-SESSION OK "
        f"records={len(records)} controls={summary['style']['commands_total']} "
        f"trajectories={summary['style']['trajectory_boundaries']}"
    )


if __name__ == "__main__":
    main()
