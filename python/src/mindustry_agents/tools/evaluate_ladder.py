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
    jar_path,
    repo_root,
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
    "dev-v20": "bootstrap-defense-v1-dev-v20.json",
    "dev-v21": "bootstrap-defense-v1-dev-v21.json",
    "dev-v22": "bootstrap-defense-v1-dev-v22.json",
    "dev-v23": "bootstrap-defense-v1-dev-v23.json",
    "dev-v24": "bootstrap-defense-v1-dev-v24.json",
    "dev-v25": "bootstrap-defense-v1-dev-v25.json",
    "dev-v26": "bootstrap-defense-v1-dev-v26.json",
    "dev-v27": "bootstrap-defense-v1-dev-v27.json",
    "dev-v28": "bootstrap-defense-v1-dev-v28.json",
    "dev-v29": "bootstrap-defense-v1-dev-v29.json",
    "dev-v30": "bootstrap-defense-v1-dev-v30.json",
    "dev-v31": "bootstrap-defense-v1-dev-v31.json",
    "dev-v32": "bootstrap-defense-v1-dev-v32.json",
    "dev-v33": "bootstrap-defense-v1-dev-v33.json",
    "dev-v34": "bootstrap-defense-v1-dev-v34.json",
    "held-out": "bootstrap-defense-v1-held-out-v1.json",
}
POLICY_VERSIONS = {
    "random-valid": "random-valid-splitmix64-v1",
    "greedy-utility": "pure-greedy-utility-v1",
    "role-assignment": "fixed-miner-builder-defender-v1",
    "frozen-expert": "frozen-m6-expert-v1",
    "adaptive-v1": "adaptive-v1",
}
RUNTIME_PROVENANCE_SCHEMA = "mindustry_rl_runtime_provenance_v1"


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
    runtime_provenance: dict[str, Any] | None = None,
) -> list[tuple[int, dict[str, Any]]]:
    records = []
    with RlServerProcess(
        LaunchConfig(
            port=base_port + partition_index,
            java=java,
            build_if_missing=False,
        )
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
                **(
                    {"runtime_provenance": runtime_provenance}
                    if runtime_provenance is not None
                    else {}
                ),
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


def _load_direct_contracts(paths: list[Path]) -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    seen: dict[int, str] = {}
    for path in paths:
        contract = load_seed_set(path)
        seed_set_id = str(contract["seed_set_id"])
        if seed_set_id in contracts:
            raise ValueError(f"duplicate direct seed set id: {seed_set_id}")
        for seed in contract["seeds"]:
            if seed in seen:
                raise ValueError(
                    f"seed {seed} appears in both {seen[seed]} and "
                    f"{seed_set_id} seed sets"
                )
            seen[seed] = seed_set_id
        contracts[seed_set_id] = contract
    return contracts


def _runtime_provenance(root: Path, config_path: Path) -> dict[str, Any]:
    from mindustry_agents.training.ppo_selector import _git_evidence, _sha256

    root = root.resolve()
    config_path = config_path.resolve()
    server_jar = jar_path(root).resolve()
    try:
        config_relative = config_path.relative_to(root).as_posix()
        jar_relative = server_jar.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(
            "runtime config and rl-server jar must be inside the repository"
        ) from exc
    repository = _git_evidence(root)
    return {
        "schema": RUNTIME_PROVENANCE_SCHEMA,
        "config": {
            "path": config_relative,
            "sha256": _sha256(config_path),
        },
        "repository": repository,
        "rl_server_jar": {
            "path": jar_relative,
            "sha256": _sha256(server_jar),
        },
    }


def _jobs(
    contracts: dict[str, dict[str, Any]],
    seed_set_names: list[str],
    policies: list[str],
) -> list[dict[str, Any]]:
    jobs = []
    for seed_set_name in seed_set_names:
        contract = contracts[seed_set_name]
        for policy in policies:
            if policy == "frozen-expert" and contract["split"] != "fixed":
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
    runtime_provenance: dict[str, Any] | None = None,
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
        ordered.extend(
            _run_partition(
                index,
                cell,
                base_port=port,
                java=java,
                runtime_provenance=runtime_provenance,
            )
        )
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
    seed_source = parser.add_mutually_exclusive_group()
    seed_source.add_argument(
        "--seed-sets",
        nargs="+",
        choices=tuple(SEED_SET_FILES),
    )
    seed_source.add_argument(
        "--seed-set-file",
        type=Path,
        action="append",
        help="repeatable explicit seed-set contract path",
    )
    parser.add_argument(
        "--seed-set-split",
        choices=("fixed", "dev", "held-out"),
        help="declared split required with --seed-set-file",
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
        "--runtime-config",
        type=Path,
        help="governed runtime config required with --seed-set-file",
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

    try:
        runtime_provenance = None
        if args.seed_set_file:
            if args.runtime_config is None:
                parser.error("--runtime-config is required with --seed-set-file")
            if args.seed_set_split is None:
                parser.error("--seed-set-split is required with --seed-set-file")
            if args.seed_set_split == "held-out" and not args.allow_held_out_final:
                parser.error("held-out execution requires --allow-held-out-final")
            if args.allow_held_out_final and args.seed_set_split != "held-out":
                parser.error(
                    "--allow-held-out-final is only valid with a held-out seed set"
                )
            visibly_held_out = any(
                "held-out" in path.name.lower() for path in args.seed_set_file
            )
            if visibly_held_out and not (
                args.seed_set_split == "held-out" and args.allow_held_out_final
            ):
                parser.error(
                    "a held-out seed-set filename requires --seed-set-split "
                    "held-out and --allow-held-out-final"
                )
            contracts = _load_direct_contracts(args.seed_set_file)
            mismatched = [
                seed_set_id
                for seed_set_id, contract in contracts.items()
                if contract["split"] != args.seed_set_split
            ]
            if mismatched:
                parser.error(
                    "direct seed-set contract split does not match "
                    f"--seed-set-split {args.seed_set_split}: {mismatched}"
                )
            seed_set_names = list(contracts)
        else:
            contracts = _load_contracts(args.config_dir)
            seed_set_names = args.seed_sets or ["fixed", "dev"]
        has_held_out = any(
            contract["split"] == "held-out"
            for contract in (contracts[name] for name in seed_set_names)
        )
        if has_held_out and not args.allow_held_out_final:
            parser.error("held-out execution requires --allow-held-out-final")
        if args.allow_held_out_final and not has_held_out:
            parser.error(
                "--allow-held-out-final is only valid with a held-out seed set"
            )
        if args.seed_set_file:
            runtime_provenance = _runtime_provenance(
                repo_root(), args.runtime_config
            )
        jobs = _jobs(contracts, seed_set_names, args.policies)
        records = _run_jobs(
            jobs,
            workers=args.workers,
            port=args.port,
            java=args.java,
            runtime_provenance=runtime_provenance,
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
            {
                "aggregates": aggregates,
                "promotions": promotions,
                **(
                    {"runtime_provenance": runtime_provenance}
                    if runtime_provenance is not None
                    else {}
                ),
            },
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
