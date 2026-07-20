"""M7.4 fixed/probe comparison for adaptive planning and the frozen macro."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess
from mindustry_agents.tools.scripted_demo import ExpertEpisode
from mindustry_agents.tools.utility_expert import UtilityExpertEpisode

FIXED = "bootstrap-defense-v0"
PROBE = "bootstrap-defense-adaptive-probe"


def _adaptive(env, seed: int, scenario_id: str) -> dict[str, Any]:
    result = UtilityExpertEpisode(env, seed, scenario_id=scenario_id).run()
    return {
        "scenario_id": scenario_id,
        "policy": "adaptive-v1",
        "outcome": result.outcome,
        "tick": result.tick,
        "defense_ready_tick": result.defense_ready_tick,
        "idle_fraction": float(result.metrics["idle_fraction"]),
        "line_complete_tick": result.line_complete_tick,
        "failure": "",
        "decision_reasons": result.metrics.get("decision_wakeup_reasons", {}),
    }


def _frozen(env, seed: int, scenario_id: str) -> dict[str, Any]:
    episode = ExpertEpisode(env, seed, scenario_id=scenario_id)
    failure = ""
    result = None
    try:
        result = episode.run()
    except AssertionError as exc:
        failure = str(exc)
        while (
            episode.tick < episode.layout.tick_cap
            and (
                episode.step_response is None
                or episode.step_response.outcome == "running"
            )
        ):
            episode.step(min(30, episode.layout.tick_cap - episode.tick))

    if result is not None:
        return {
            "scenario_id": scenario_id,
            "policy": "frozen-m6",
            "outcome": result.outcome,
            "tick": result.tick,
            "defense_ready_tick": result.defense_ready_tick,
            "idle_fraction": float(result.metrics["idle_fraction"]),
            "line_complete_tick": result.line_complete_tick,
            "failure": "",
            "decision_reasons": {},
        }

    response = episode.step_response
    if response is None:
        raise AssertionError(f"frozen {scenario_id} failed without a response")
    return {
        "scenario_id": scenario_id,
        "policy": "frozen-m6",
        "outcome": response.outcome,
        "tick": response.tick,
        # A never-achieved milestone is censored at the authoritative tick cap.
        "defense_ready_tick": episode.layout.tick_cap,
        "idle_fraction": float(response.coordination_metrics["idle_fraction"]),
        "line_complete_tick": episode.line_complete_tick,
        "failure": failure,
        "decision_reasons": {},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check M7.4 adaptive planning")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--java", default="java")
    parser.add_argument(
        "--output", default="runs/adaptive-planning-check.json"
    )
    args = parser.parse_args(argv)

    try:
        with RlServerProcess(LaunchConfig(port=args.port, java=args.java)) as env:
            env.handshake("m7.4-adaptive-planning-check")
            rows = [
                _adaptive(env, args.seed, FIXED),
                _frozen(env, args.seed, FIXED),
                _adaptive(env, args.seed, PROBE),
                _frozen(env, args.seed, PROBE),
            ]

        by_key = {(row["scenario_id"], row["policy"]): row for row in rows}
        if by_key[(FIXED, "adaptive-v1")]["outcome"] != "win":
            raise AssertionError("adaptive policy did not win the fixed scenario")
        if by_key[(FIXED, "frozen-m6")]["outcome"] != "win":
            raise AssertionError("frozen baseline no longer wins the fixed scenario")
        if by_key[(PROBE, "adaptive-v1")]["outcome"] != "win":
            raise AssertionError("adaptive policy did not win the delayed-loadout probe")
        if not by_key[(PROBE, "frozen-m6")]["failure"]:
            raise AssertionError("frozen macro unexpectedly completed the adaptive probe")

        observed_reasons: set[str] = set()
        for row in rows:
            observed_reasons.update(row["decision_reasons"])
        required_reasons = {"task_terminal", "wave_spawn", "wave_clear", "core_damage"}
        missing = sorted(required_reasons - observed_reasons)
        if missing:
            raise AssertionError(f"missing event-driven decision reasons: {missing}")

        adaptive_rows = [row for row in rows if row["policy"] == "adaptive-v1"]
        frozen_rows = [row for row in rows if row["policy"] == "frozen-m6"]
        summary = {
            "seed": args.seed,
            "adaptive_idle_fraction_mean": statistics.fmean(
                row["idle_fraction"] for row in adaptive_rows
            ),
            "frozen_idle_fraction_mean": statistics.fmean(
                row["idle_fraction"] for row in frozen_rows
            ),
            "adaptive_defense_ready_mean": statistics.fmean(
                row["defense_ready_tick"] for row in adaptive_rows
            ),
            "frozen_defense_ready_mean": statistics.fmean(
                row["defense_ready_tick"] for row in frozen_rows
            ),
            "required_decision_reasons": sorted(required_reasons),
        }
        if summary["adaptive_idle_fraction_mean"] >= summary["frozen_idle_fraction_mean"]:
            raise AssertionError(f"adaptive idle fraction did not improve: {summary}")
        if summary["adaptive_defense_ready_mean"] >= summary["frozen_defense_ready_mean"]:
            raise AssertionError(f"adaptive defense readiness did not improve: {summary}")

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps({"rows": rows, "summary": summary}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"ADAPTIVE-PLANNING FAIL: {exc}", file=sys.stderr)
        return 1

    print("| scenario | policy | outcome | ready | idle | failure |")
    print("|:---|:---|:---:|---:|---:|:---|")
    for row in rows:
        failure = row["failure"] or "-"
        print(
            f"| {row['scenario_id']} | {row['policy']} | {row['outcome']} | "
            f"{row['defense_ready_tick']} | {row['idle_fraction']:.3f} | {failure} |"
        )
    print(
        "ADAPTIVE-PLANNING OK: "
        f"idle {summary['adaptive_idle_fraction_mean']:.3f} < "
        f"{summary['frozen_idle_fraction_mean']:.3f}; defense-ready "
        f"{summary['adaptive_defense_ready_mean']:.1f} < "
        f"{summary['frozen_defense_ready_mean']:.1f}; output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
