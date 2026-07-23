"""Live stochastic rollout/reset gate for ADR-0070 before optimization."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.training.ippo import SharedRecurrentSelector
from mindustry_agents.training.ippo_ppo import load_ippo_v1_config
from mindustry_agents.training.ippo_rollout import rollout_ippo_episode


def _summary(evidence):
    return {
        "seed": evidence.rollout.seed,
        "outcome": evidence.rollout.outcome,
        "tick": evidence.tick,
        "core_health": evidence.core_health,
        "transitions": len(evidence.rollout.transitions),
        "shared_reward_components": evidence.shared_reward_components,
        "individual_reward_totals": list(evidence.individual_reward_totals),
        "trace_sha256": evidence.trace_sha256,
        "model_state_sha256": evidence.model_state_sha256,
    }


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=root / "configs/training/m9-ippo-v1.json",
    )
    parser.add_argument("--seed", type=int, default=18000000001)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--java", default="java")
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "runs/m9-ippo-rollout-check.json",
    )
    args = parser.parse_args(argv)
    try:
        config = load_ippo_v1_config(args.config)
        torch.set_num_threads(int(config["torch_threads"]))
        model = SharedRecurrentSelector(int(config["model_init_seed"]))
        rows = []
        evidences = []
        with RlServerProcess(
            LaunchConfig(port=args.port, java=args.java)
        ) as env:
            env.handshake("m9-ippo-rollout-check")
            for _ in range(2):
                generator = torch.Generator().manual_seed(
                    int(config["action_sampling_seed"])
                )
                evidence = rollout_ippo_episode(
                    env,
                    model,
                    config,
                    seed=args.seed,
                    evaluation=False,
                    action_generator=generator,
                )
                evidences.append(evidence)
                rows.append(_summary(evidence))
        if rows[0] != rows[1]:
            differing = {
                key: [rows[0].get(key), rows[1].get(key)]
                for key in sorted(set(rows[0]) | set(rows[1]))
                if rows[0].get(key) != rows[1].get(key)
            }
            mismatch = next(
                (
                    index
                    for index, (left, right) in enumerate(
                        zip(
                            evidences[0].trace,
                            evidences[1].trace,
                            strict=False,
                        )
                    )
                    if left != right
                ),
                min(len(evidences[0].trace), len(evidences[1].trace)),
            )
            raise AssertionError(
                "M9 stochastic terminal-reset rollout diverged: "
                + json.dumps(
                    {
                        "summary": differing,
                        "first_mismatch": mismatch,
                        "first": (
                            evidences[0].trace[mismatch]
                            if mismatch < len(evidences[0].trace)
                            else None
                        ),
                        "second": (
                            evidences[1].trace[mismatch]
                            if mismatch < len(evidences[1].trace)
                            else None
                        ),
                    },
                    sort_keys=True,
                )
            )
        report = {
            "schema": "m9_ippo_rollout_check_v1",
            "config": str(args.config.resolve().relative_to(root).as_posix()),
            "repeated_rollouts_equal": True,
            "episode": rows[0],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception as error:
        print(f"M9 IPPO ROLLOUT FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "M9 IPPO ROLLOUT OK "
        f"outcome={rows[0]['outcome']} transitions={rows[0]['transitions']} "
        f"trace={rows[0]['trace_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
