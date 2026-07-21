"""Run the permanent M7.6 policy ladder and write deterministic artifacts."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any

from mindustry_agents.evaluation.ladder import (
    POLICY_ORDER,
    aggregate_records,
    held_out_promotions,
    ladder_episode_record,
    load_seed_set,
)
from mindustry_agents.policies import (
    GreedyUtilityPolicy,
    PureGreedyUtilityPolicy,
    RandomValidPolicy,
    RoleAssignmentPolicy,
)
from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
)
from mindustry_agents.tools.scripted_demo import run_frozen_episode
from mindustry_agents.tools.utility_expert import run_utility_episode

SEED_SET_FILES = {
    "fixed": "bootstrap-defense-v0-fixed-v1.json",
    "dev": "bootstrap-defense-v1-dev-v1.json",
    "dev-v2": "bootstrap-defense-v1-dev-v2.json",
    "dev-v3": "bootstrap-defense-v1-dev-v3.json",
    "dev-v4": "bootstrap-defense-v1-dev-v4.json",
    "dev-v5": "bootstrap-defense-v1-dev-v5.json",
    "dev-v6": "bootstrap-defense-v1-dev-v6.json",
    "dev-v7": "bootstrap-defense-v1-dev-v7.json",
    "dev-v8": "bootstrap-defense-v1-dev-v8.json",
    "dev-v9": "bootstrap-defense-v1-dev-v9.json",
    "dev-v10": "bootstrap-defense-v1-dev-v10.json",
    "dev-v11": "bootstrap-defense-v1-dev-v11.json",
    "dev-v12": "bootstrap-defense-v1-dev-v12.json",
    "dev-v13": "bootstrap-defense-v1-dev-v13.json",
    "dev-v14": "bootstrap-defense-v1-dev-v14.json",
    "dev-v15": "bootstrap-defense-v1-dev-v15.json",
    "dev-v16": "bootstrap-defense-v1-dev-v16.json",
    "dev-v17": "bootstrap-defense-v1-dev-v17.json",
    "dev-v18": "bootstrap-defense-v1-dev-v18.json",
    "dev-v19": "bootstrap-defense-v1-dev-v19.json",
    "held-out": "bootstrap-defense-v1-held-out-v1.json",
}
POLICY_VERSIONS = {
    "random-valid": "random-valid-splitmix64-v1",
    "greedy-utility": "pure-greedy-utility-v1",
    "role-assignment": "fixed-miner-builder-defender-v1",
    "frozen-expert": "frozen-m6-expert-v1",
    "adaptive-v1": "adaptive-v1",
}


def _policy(policy_name: str, seed: int):
    if policy_name == "random-valid":
        return RandomValidPolicy(seed)
    if policy_name == "greedy-utility":
        return PureGreedyUtilityPolicy()
    if policy_name == "role-assignment":
        return RoleAssignmentPolicy(("miner", "builder", "defender"))
    if policy_name == "adaptive-v1":
        return GreedyUtilityPolicy()
    raise ValueError(f"unknown public candidate policy: {policy_name}")


def _run_partition(
    partition_index: int,
    jobs: list[dict[str, Any]],
    *,
    base_port: int,
    java: str,
) -> list[tuple[int, dict[str, Any]]]:
    records = []
    with RlServerProcess(
        LaunchConfig(port=base_port + partition_index, java=java)
    ) as env:
        handshake = env.handshake(f"m7.6-ladder-worker-{partition_index}")
        engine = {
            "engine_tag": handshake.engine_version,
            "engine_commit": handshake.engine_commit,
            "arc_hash": handshake.arc_version,
            "protocol_version": handshake.protocol_version,
            "agent_count": 3,
            "python": platform.python_version(),
            "jvm_workers": 1,
            "episode_precondition": "same-seed-idle-through-wave-1-plus-120-v1",
        }
        for job in jobs:
            seed_set = job["seed_set"]
            seed = int(job["seed"])
            policy_name = str(job["policy"])
            precondition = env.reset(
                root_seed=seed,
                scenario_id=seed_set["scenario_id"],
                scenario_version=int(seed_set["scenario_version"]),
                agent_count=3,
            )
            trace_tick = int(precondition.metadata["wave_ticks"][0]) + 120
            env.step(
                precondition.episode_id,
                expected_tick=0,
                ticks_to_advance=trace_tick,
            )
            if policy_name == "frozen-expert":
                result = run_frozen_episode(env, seed)
            else:
                result = run_utility_episode(
                    env,
                    seed,
                    scenario_id=seed_set["scenario_id"],
                    scenario_version=int(seed_set["scenario_version"]),
                    require_win=False,
                    policy=_policy(policy_name, seed),
                    policy_name=policy_name,
                )
            manifest = {
                **engine,
                "scenario_id": seed_set["scenario_id"],
                "scenario_version": int(seed_set["scenario_version"]),
                "root_seed": seed,
                "seed_set_id": seed_set["seed_set_id"],
                "seed_set_version": int(seed_set["seed_set_version"]),
                "policy": policy_name,
                "policy_version": POLICY_VERSIONS[policy_name],
                "python_dependency_contract": "stdlib-only; no lockfile required",
                "training_config": "not-applicable-evaluation",
                "precondition_trace_tick": trace_tick,
            }
            records.append(
                (
                    int(job["order"]),
                    ladder_episode_record(result, manifest, seed_set),
                )
            )
    return records


def _load_contracts(root: Path) -> dict[str, dict[str, Any]]:
    contracts = {
        name: load_seed_set(root / filename)
        for name, filename in SEED_SET_FILES.items()
    }
    seen: dict[int, str] = {}
    for name, contract in contracts.items():
        for seed in contract["seeds"]:
            if seed in seen:
                raise ValueError(
                    f"seed {seed} appears in both {seen[seed]} and {name} seed sets"
                )
            seen[seed] = name
    return contracts


def _jobs(
    contracts: dict[str, dict[str, Any]],
    seed_set_names: list[str],
    policies: list[str],
) -> list[dict[str, Any]]:
    jobs = []
    for seed_set_name in seed_set_names:
        contract = contracts[seed_set_name]
        for policy in policies:
            if policy == "frozen-expert" and seed_set_name != "fixed":
                continue
            for seed in contract["seeds"]:
                jobs.append(
                    {
                        "order": len(jobs),
                        "policy": policy,
                        "seed": seed,
                        "seed_set": contract,
                    }
                )
    return jobs


def _run_jobs(
    jobs: list[dict[str, Any]],
    *,
    workers: int,
    port: int,
    java: str,
) -> list[dict[str, Any]]:
    cells: list[list[dict[str, Any]]] = []
    for job in jobs:
        key = (job["seed_set"]["seed_set_id"], job["policy"])
        if not cells or (
            cells[-1][0]["seed_set"]["seed_set_id"], cells[-1][0]["policy"]
        ) != key:
            cells.append([])
        cells[-1].append(job)

    if workers != 1:
        raise ValueError(
            "certified deterministic ladder requires --workers 1 "
            "(one JVM, below the project cap of four)"
        )
    ordered = []
    for index, cell in enumerate(cells):
        ordered.extend(_run_partition(index, cell, base_port=port, java=java))
    return [record for _, record in sorted(ordered)]


def _format_stat(stat: dict[str, Any], digits: int = 3) -> str:
    if stat["mean"] is None:
        return "n/a"
    low, high = stat["ci95"]
    return f"{stat['mean']:.{digits}f} [{low:.{digits}f},{high:.{digits}f}]"


def _print_table(aggregates: list[dict[str, Any]]) -> None:
    print(
        "| seed set | policy | N | wins | win rate 95% CI | core health | idle | "
        "duplicates | help ticks | announcements/transition | abandonment | recovery |"
    )
    print("|:---|:---|---:|---:|:---|:---|:---|:---|:---|:---|:---|:---|")
    for row in aggregates:
        score = row["scorecard"]
        print(
            f"| {row['seed_set']['id']} | {row['policy']} | {row['episodes']} "
            f"| {row['wins']} | {_format_stat(row['win_rate'])} "
            f"| {_format_stat(row['core_health'], 1)} "
            f"| {_format_stat(score['idle_fraction'])} "
            f"| {_format_stat(score['duplicate_work_incidents'], 2)} "
            f"| {_format_stat(score['time_to_help_ticks'], 1)} "
            f"| {_format_stat(score['announcements_per_meaningful_transition'])} "
            f"| {_format_stat(score['task_abandonment_rate'])} "
            f"| {_format_stat(score['recovery_time_after_agent_loss_ticks'], 1)} |"
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the M7.6 evaluation ladder")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--java", default="java")
    parser.add_argument(
        "--workers",
        type=int,
        choices=range(1, 5),
        default=1,
        help="certified mode requires 1; values above 4 are never accepted",
    )
    parser.add_argument(
        "--seed-sets",
        nargs="+",
        choices=tuple(SEED_SET_FILES),
        default=["fixed", "dev"],
    )
    parser.add_argument(
        "--policies", nargs="+", choices=POLICY_ORDER, default=list(POLICY_ORDER)
    )
    parser.add_argument(
        "--allow-held-out-final",
        action="store_true",
        help="one-way final evaluation; exact held-out manifests will be persisted",
    )
    parser.add_argument(
        "--config-dir", type=Path, default=Path("configs/evaluation")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("runs/evaluation-ladder.jsonl")
    )
    parser.add_argument(
        "--aggregate-output",
        type=Path,
        default=Path("runs/evaluation-ladder-aggregate.json"),
    )
    args = parser.parse_args(argv)

    if "held-out" in args.seed_sets and not args.allow_held_out_final:
        parser.error("held-out execution requires --allow-held-out-final")
    if args.allow_held_out_final and "held-out" not in args.seed_sets:
        parser.error("--allow-held-out-final is only valid with --seed-sets held-out")

    try:
        contracts = _load_contracts(args.config_dir)
        jobs = _jobs(contracts, args.seed_sets, args.policies)
        records = _run_jobs(
            jobs,
            workers=args.workers,
            port=args.port,
            java=args.java,
        )
        aggregates = aggregate_records(records)
        promotions = held_out_promotions(aggregates)
    except Exception as exc:
        print(f"EVALUATE-LADDER FAIL: {exc}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(
                json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            )
    args.aggregate_output.parent.mkdir(parents=True, exist_ok=True)
    args.aggregate_output.write_text(
        json.dumps(
            {"aggregates": aggregates, "promotions": promotions},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    _print_table(aggregates)
    if promotions:
        for promotion in promotions:
            print(
                f"promotion {promotion['candidate']} vs {promotion['baseline']}: "
                f"{promotion['status']}"
            )
    else:
        print("promotion: not evaluated (held-out seed set remains sealed)")
    print(
        f"EVALUATE-LADDER OK: episodes={len(records)} workers={args.workers} "
        f"jsonl={args.output.as_posix()} aggregate={args.aggregate_output.as_posix()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
