"""Freeze ADR-0070's public fixed-role shared-expert baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from statistics import fmean
from typing import Any

from mindustry_agents import ENGINE_COMMIT, ENGINE_TAG, PROTOCOL_VERSION
from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.training.ippo_ppo import (
    IPPO_V1_PROTOCOL_SHA256,
    load_ippo_v1_config,
    sha256_path,
)
from mindustry_agents.training.ippo_reward import IPPOReward


def _json_digest(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _project_commit(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _run_episode(
    env: RlServerProcess, seed: int, config: dict[str, Any]
) -> dict[str, Any]:
    reset = env.reset(
        seed,
        scenario_id=str(config["scenario_id"]),
        scenario_version=int(config["scenario_version"]),
        agent_count=int(config["agent_count"]),
        options={"shared_expert_policy": True},
    )
    observations = reset.initial_observations
    previous_team = dict(observations[0]["team"])
    metadata = reset.metadata
    tick = reset.tick
    outcome = reset.outcome
    reward = IPPOReward(
        config["team_quality_reward"], config["individual_shaping"]
    )
    shared_return = 0.0
    trace: list[dict[str, Any]] = []
    final_metrics: dict[str, Any] = {}
    while outcome == "running" and tick < int(metadata["tick_cap"]):
        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, int(metadata["tick_cap"]) - tick),
            agent_actions=[],
            stop_on_decision_event=True,
        )
        current_team = dict(response.observations[0]["team"])
        advanced_ticks = int(
            response.decision_boundary.get(
                "advanced_ticks", response.tick - tick
            )
        )
        breakdown = reward.observe(
            previous_team,
            current_team,
            advanced_ticks=advanced_ticks,
            tick_cap=int(metadata["tick_cap"]),
            outcome=response.outcome,
            task_events=response.task_events,
            game_events=response.game_events,
            boundary_reasons=list(
                response.decision_boundary.get("reasons", [])
            ),
            coordination_metrics=response.coordination_metrics,
        )
        shared_return += breakdown.team.total
        trace.append(
            {
                "tick": tick,
                "next_tick": response.tick,
                "state_hash": response.state_hash,
                "outcome": response.outcome,
                "shared_decision_digest": response.coordination_metrics.get(
                    "shared_decision_digest"
                ),
                "shared_decision_count": response.coordination_metrics.get(
                    "shared_decision_count"
                ),
            }
        )
        observations = response.observations
        previous_team = current_team
        tick = response.tick
        outcome = response.outcome
        final_metrics = response.coordination_metrics
    if outcome == "running":
        raise RuntimeError("shared expert did not reach a terminal outcome")
    return {
        "seed": seed,
        "outcome": outcome,
        "tick": tick,
        "core_health": float(observations[0]["team"]["core_health"]),
        "team_return": shared_return,
        "team_idle_fraction": float(final_metrics["idle_fraction"]),
        "shared_decision_count": int(final_metrics["shared_decision_count"]),
        "shared_decision_digest": str(final_metrics["shared_decision_digest"]),
        "trace_sha256": _json_digest(trace),
    }


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=root / "configs/training/m9-ippo-v1.json",
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=root / "configs/evaluation/m9-ippo-v1-public-protocol.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "runs/m9-ippo-v1-shared-expert-baseline.json",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--java", default="java")
    args = parser.parse_args(argv)
    try:
        config = load_ippo_v1_config(args.config)
        if sha256_path(args.protocol) != IPPO_V1_PROTOCOL_SHA256:
            raise ValueError("M9 IPPO public protocol hash drifted")
        protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
        if protocol["baseline"] != {
            "policy": "shared-expert-v1",
            "implementation": "agentcore.coordination.ExpertCoordinationDriver",
            "control_path": "server_shared_expert_policy",
            "frozen_before_candidate_training": True,
        }:
            raise ValueError("M9 IPPO baseline contract drifted")
        seed_path = root / protocol["seed_set"]
        seed_set = json.loads(seed_path.read_text(encoding="utf-8"))
        if (
            seed_set.get("split") != "dev"
            or seed_set.get("scenario_version") != 2
            or len(seed_set.get("seeds", [])) != 40
        ):
            raise ValueError("M9 IPPO public dev document is invalid")
        rows = []
        with RlServerProcess(
            LaunchConfig(port=args.port, java=args.java)
        ) as env:
            env.handshake("m9-ippo-v1-shared-expert-baseline")
            for seed in seed_set["seeds"]:
                rows.append(_run_episode(env, int(seed), config))
            replay = _run_episode(env, int(seed_set["seeds"][0]), config)
        if replay != rows[0]:
            raise AssertionError("shared expert terminal-reset replay diverged")
        report = {
            "schema": "m9_ippo_public_baseline_v1",
            "candidate_version": config["candidate_version"],
            "policy": protocol["baseline"]["policy"],
            "implementation": protocol["baseline"]["implementation"],
            "seed_set": {
                "id": seed_set["seed_set_id"],
                "version": seed_set["seed_set_version"],
                "split": seed_set["split"],
                "sha256": sha256_path(seed_path),
            },
            "manifest": {
                "project_commit": _project_commit(root),
                "engine_tag": ENGINE_TAG,
                "engine_commit": ENGINE_COMMIT,
                "protocol_version": PROTOCOL_VERSION,
                "config_sha256": sha256_path(args.config),
                "public_protocol_sha256": sha256_path(args.protocol),
                "rl_server_jar_sha256": sha256_path(
                    root / "rl-server/build/libs/rl-server.jar"
                ),
            },
            "episodes": rows,
            "aggregate": {
                "episodes": len(rows),
                "wins": sum(row["outcome"] == "win" for row in rows),
                "mean_team_return": fmean(row["team_return"] for row in rows),
                "mean_core_health": fmean(row["core_health"] for row in rows),
                "mean_team_idle_fraction": fmean(
                    row["team_idle_fraction"] for row in rows
                ),
            },
            "terminal_reset_replay_equal": True,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception as error:
        print(f"M9 IPPO BASELINE FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "M9 IPPO BASELINE OK "
        f"wins={report['aggregate']['wins']}/40 "
        f"idle={report['aggregate']['mean_team_idle_fraction']:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
