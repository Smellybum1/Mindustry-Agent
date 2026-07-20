"""Run the M6 expert seed set, write JSONL summaries, and print a table."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

from mindustry_agents.evaluation.scripted import EVALUATION_SEEDS, aggregate, episode_summary
from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess
from mindustry_agents.tools.scripted_demo import run_episode


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the M6 scripted expert")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--java", default="java")
    parser.add_argument("--output", type=Path, default=Path("runs/scripted-evaluation.jsonl"))
    parser.add_argument("--seeds", nargs="*", type=int, default=list(EVALUATION_SEEDS))
    args = parser.parse_args(argv)
    if not args.seeds:
        parser.error("--seeds must not be empty")

    summaries = []
    try:
        with RlServerProcess(LaunchConfig(port=args.port, java=args.java)) as env:
            handshake = env.handshake("m6-scripted-evaluation")
            manifest = {
                "engine_tag": handshake.engine_version,
                "engine_commit": handshake.engine_commit,
                "arc_hash": handshake.arc_version,
                "protocol_version": handshake.protocol_version,
                "scenario_id": "bootstrap-defense-v0",
                "scenario_version": 1,
                "policy": "scripted-expert-v1",
                "agent_count": 3,
                "python": platform.python_version(),
            }
            for seed in args.seeds:
                result = run_episode(env, seed)
                summaries.append(episode_summary(result, manifest))
    except Exception as exc:
        print(f"EVALUATE-SCRIPTED FAIL: {exc}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for summary in summaries:
            stream.write(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n")

    print("| seed | outcome | core hp | first drill | line | turrets | supplied | lost | msgs |")
    print("|---:|:---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in summaries:
        milestones = row["milestones"]
        print(
            f"| {row['seed']} | {row['outcome']} | {row['core']['health_final']:.0f} "
            f"| {milestones['first_drill_tick']} | {milestones['line_complete_tick']} "
            f"| {milestones['turrets_built_tick']} | {milestones['turrets_supplied_tick']} "
            f"| {row['units_lost']} | {row['messages']['structured']}/{row['messages']['announced']} |"
        )
    totals = aggregate(summaries)
    print(
        f"evaluation: wins={totals['wins']}/{totals['episodes']} "
        f"core_health_min={totals['core_health_min']:.0f} "
        f"core_health_mean={totals['core_health_mean']:.1f} "
        f"output={args.output.as_posix()}"
    )
    if totals["wins"] != totals["episodes"]:
        print("EVALUATE-SCRIPTED FAIL: not every seed won", file=sys.stderr)
        return 1
    print("EVALUATE-SCRIPTED OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
