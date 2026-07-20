"""Record the pinned M6 two-episode golden action/coordination trace."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess
from mindustry_agents.tools.scripted_demo import ExpertEpisode

GOLDEN_SEEDS = (12345, 23456)


def write_trace(path: Path, header: dict, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(header, sort_keys=True, separators=(",", ":")) + "\n")
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Record the M6 scripted golden trace")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--java", default="java")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/golden/bootstrap-defense-v0-scripted-v1.jsonl"),
    )
    args = parser.parse_args(argv)

    records: list[dict] = []
    try:
        with RlServerProcess(LaunchConfig(port=args.port, java=args.java)) as env:
            handshake = env.handshake("m6-golden-recorder")
            for seed in GOLDEN_SEEDS:
                episode = ExpertEpisode(env, seed)
                result = episode.run()
                if result.outcome != "win" or result.tick != 8100:
                    raise AssertionError(f"seed {seed} did not produce a golden win")
                records.extend(episode.trace_records)
    except Exception as exc:
        print(f"RECORD-REPLAY FAIL: {exc}", file=sys.stderr)
        return 1

    header = {
        "kind": "manifest",
        "format_version": 1,
        "engine_tag": handshake.engine_version,
        "engine_commit": handshake.engine_commit,
        "arc_hash": handshake.arc_version,
        "protocol_version": handshake.protocol_version,
        "scenario_id": "bootstrap-defense-v0",
        "scenario_version": 1,
        "policy": "scripted-expert-v1",
        "episodes": len(GOLDEN_SEEDS),
        "total_ticks": 8100 * len(GOLDEN_SEEDS),
    }
    write_trace(args.output, header, records)
    print(
        f"RECORD-REPLAY OK: episodes={header['episodes']} ticks={header['total_ticks']} "
        f"records={len(records)} output={args.output.as_posix()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
