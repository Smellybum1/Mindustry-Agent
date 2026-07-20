"""Validate scenario-v2 seed variation, determinism, and dev survival."""

from __future__ import annotations

import argparse
import json
import math
import platform
import sys
from pathlib import Path
from typing import Any

from mindustry_agents import protocol as P
from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess
from mindustry_agents.tools.utility_expert import run_utility_episode

DEFAULT_SEED_SET = Path(
    "configs/evaluation/bootstrap-defense-v1-dev-v1.json"
)
DEFAULT_OUTPUT = Path("runs/scenario-variation-check.json")


def _load_seed_set(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("split") == "held-out":
        raise ValueError("held-out seed sets are sealed and cannot be run by this tool")
    seeds = data.get("seeds")
    if not isinstance(seeds, list) or not seeds or any(
        not isinstance(seed, int) for seed in seeds
    ):
        raise ValueError("seed set must contain a non-empty integer seeds list")
    if len(seeds) != len(set(seeds)):
        raise ValueError("seed set contains duplicates")
    return data


def _validate_governance(path: Path, selected: dict[str, Any]) -> None:
    sets = []
    for candidate in sorted(path.parent.glob("bootstrap-defense-v1-*-v1.json")):
        data = json.loads(candidate.read_text(encoding="utf-8"))
        if (
            data.get("scenario_id") == selected["scenario_id"]
            and int(data.get("scenario_version", -1)) == selected["scenario_version"]
        ):
            sets.append(data)
    by_split = {data.get("split"): data for data in sets}
    if set(by_split) != {"train", "dev", "held-out"}:
        raise ValueError("seed governance requires exactly train/dev/held-out v1 sets")
    seen: set[int] = set()
    for split in ("train", "dev", "held-out"):
        seeds = by_split[split].get("seeds", [])
        overlap = seen.intersection(seeds)
        if overlap:
            raise ValueError(f"seed sets overlap at {sorted(overlap)}")
        seen.update(seeds)


def _snapshot(reset) -> dict[str, Any]:
    metadata = reset.metadata
    return {
        "state_hash": reset.state_hash,
        "scenario_id": metadata["scenario_id"],
        "scenario_version": int(metadata["scenario_version"]),
        "root_seed": int(metadata["root_seed"]),
        "wave_ticks": metadata["wave_ticks"],
        "ore_patches": metadata["ore_patches"],
        "variation": metadata["variation"],
    }


def _capture_resets(config: LaunchConfig, seed_set: dict[str, Any]) -> dict[int, dict[str, Any]]:
    snapshots: dict[int, dict[str, Any]] = {}
    with RlServerProcess(config) as env:
        env.handshake("m7.5-scenario-variation-reset-probe")
        rejected = env.reset(
            seed_set["seeds"][0],
            scenario_id=seed_set["scenario_id"],
            scenario_version=seed_set["scenario_version"] - 1,
            agent_count=3,
        )
        if not isinstance(rejected, P.ErrorResponse) or rejected.code != (
            "scenario_version_mismatch"
        ):
            raise AssertionError("scenario-version mismatch was not rejected")
        for seed in seed_set["seeds"]:
            first = env.reset(
                seed,
                scenario_id=seed_set["scenario_id"],
                scenario_version=seed_set["scenario_version"],
                agent_count=3,
            )
            second = env.reset(
                seed,
                scenario_id=seed_set["scenario_id"],
                scenario_version=seed_set["scenario_version"],
                agent_count=3,
            )
            first_snapshot = _snapshot(first)
            if first_snapshot != _snapshot(second):
                raise AssertionError(f"same-JVM reset mismatch for seed {seed}")
            trace_tick = int(first.metadata["wave_ticks"][0]) + 120
            traced = env.step(
                second.episode_id,
                expected_tick=0,
                ticks_to_advance=trace_tick,
            )
            first_snapshot["idle_trace_tick"] = trace_tick
            first_snapshot["idle_trace_hash"] = traced.state_hash
            snapshots[seed] = first_snapshot
    return snapshots


def _assert_variation_coverage(snapshots: dict[int, dict[str, Any]]) -> None:
    variations = [snapshot["variation"] for snapshot in snapshots.values()]
    if not all(variation.get("enabled", False) for variation in variations):
        raise AssertionError("scenario-v2 variation is not enabled for every seed")
    axes = {
        "ore": {
            json.dumps(variation["ore_patch_jitter"], sort_keys=True)
            for variation in variations
        },
        "timing": {
            (variation["wave_initial_offset_ticks"], variation["wave_spacing_offset_ticks"])
            for variation in variations
        },
        "composition": {
            tuple(variation["wave_count_deltas"]) for variation in variations
        },
        "loadout": {variation["resolved_copper_loadout"] for variation in variations},
        "lane": {variation["second_lane_enabled"] for variation in variations},
    }
    missing = [name for name, values in axes.items() if len(values) < 2]
    if missing:
        raise AssertionError(f"dev seeds do not exercise variation axes: {missing}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate bounded scenario-v2 variation and adaptive dev survival"
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--java", default="java")
    parser.add_argument("--seed-set", type=Path, default=DEFAULT_SEED_SET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    try:
        seed_set = _load_seed_set(args.seed_set)
        _validate_governance(args.seed_set, seed_set)
        config = LaunchConfig(port=args.port, java=args.java)
        snapshots = _capture_resets(config, seed_set)
        _assert_variation_coverage(snapshots)

        rows = []
        with RlServerProcess(config) as env:
            handshake = env.handshake("m7.5-scenario-variation-dev")
            for seed in seed_set["seeds"]:
                reset = env.reset(
                    seed,
                    scenario_id=seed_set["scenario_id"],
                    scenario_version=seed_set["scenario_version"],
                    agent_count=3,
                )
                expected_reset = {
                    key: value
                    for key, value in snapshots[seed].items()
                    if not key.startswith("idle_trace_")
                }
                if _snapshot(reset) != expected_reset:
                    raise AssertionError(f"fresh-JVM reset mismatch for seed {seed}")
                traced = env.step(
                    reset.episode_id,
                    expected_tick=0,
                    ticks_to_advance=snapshots[seed]["idle_trace_tick"],
                )
                if traced.state_hash != snapshots[seed]["idle_trace_hash"]:
                    raise AssertionError(f"fresh-JVM action-trace mismatch for seed {seed}")
                result = run_utility_episode(
                    env,
                    seed,
                    scenario_id=seed_set["scenario_id"],
                    scenario_version=seed_set["scenario_version"],
                    require_win=False,
                )
                rows.append(
                    {
                        "seed": seed,
                        "outcome": result.outcome,
                        "tick": result.tick,
                        "core_health": result.core_health,
                        "line_complete_tick": result.line_complete_tick,
                        "defense_ready_tick": result.defense_ready_tick,
                        "idle_fraction": float(result.metrics.get("idle_fraction", 0.0)),
                        "initial_state_hash": snapshots[seed]["state_hash"],
                        "idle_trace_tick": snapshots[seed]["idle_trace_tick"],
                        "idle_trace_hash": snapshots[seed]["idle_trace_hash"],
                        "variation": snapshots[seed]["variation"],
                    }
                )

        wins = sum(row["outcome"] == "win" for row in rows)
        required = math.ceil(len(rows) * 0.8)
        if wins < required:
            raise AssertionError(
                f"adaptive dev win rate below 80%: {wins}/{len(rows)} (need {required})"
            )
        report = {
            "manifest": {
                "engine_tag": handshake.engine_version,
                "engine_commit": handshake.engine_commit,
                "arc_hash": handshake.arc_version,
                "protocol_version": handshake.protocol_version,
                "scenario_id": seed_set["scenario_id"],
                "scenario_version": seed_set["scenario_version"],
                "seed_set_id": seed_set["seed_set_id"],
                "seed_set_version": seed_set["seed_set_version"],
                "policy": "greedy-utility-expert-v1",
                "agent_count": 3,
                "python": platform.python_version(),
            },
            "summary": {
                "episodes": len(rows),
                "wins": wins,
                "win_rate": wins / len(rows),
                "core_health_min": min(row["core_health"] for row in rows),
                "core_health_mean": sum(row["core_health"] for row in rows) / len(rows),
            },
            "episodes": rows,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except Exception as exc:
        print(f"SCENARIO-VARIATION FAIL: {exc}", file=sys.stderr)
        return 1

    print("| seed | outcome | core hp | line | defense ready | idle | lane 2 |")
    print("|---:|:---:|---:|---:|---:|---:|:---:|")
    for row in rows:
        print(
            f"| {row['seed']} | {row['outcome']} | {row['core_health']:.0f} "
            f"| {row['line_complete_tick']} | {row['defense_ready_tick']} "
            f"| {row['idle_fraction']:.3f} "
            f"| {row['variation']['second_lane_enabled']} |"
        )
    print(
        f"SCENARIO-VARIATION OK: wins={wins}/{len(rows)} "
        "same-seed resets/action traces match across fresh JVMs "
        f"output={args.output.as_posix()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
