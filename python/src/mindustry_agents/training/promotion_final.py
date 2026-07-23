"""One-way M8.5 held-out promotion evaluation with exclusive attempt archival."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch

from mindustry_agents.evaluation.ladder import (
    aggregate_records,
    ladder_episode_record,
    load_seed_set,
)
from mindustry_agents.evaluation.promotion import (
    paired_scorecard_non_regression,
    win_rate_comparison,
)
from mindustry_agents.policies import PureGreedyUtilityPolicy, RandomValidPolicy
from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.tools.utility_expert import run_utility_episode
from mindustry_agents.training.checkpoint_interpolation import (
    ALLOWED_DIRTY_PATHS,
)
from mindustry_agents.training.checkpoint_lineage import validate_lineage_manifest
from mindustry_agents.training.model import build_selector_model
from mindustry_agents.training.ppo_selector import (
    _configure_torch,
    _git_evidence,
    _policy_logit_adjustment,
    _scripted_partner_opening,
    _sha256,
    load_checkpoint,
    REWARD_SCHEMA,
    rollout_episode,
)
from mindustry_agents.training.promotion import (
    CANDIDATE_POLICY,
    GREEDY_MIXED,
    _record,
    rollout_control_episode,
)

FINAL_SCHEMA = "selector_promotion_held_out_final_v1"
ATTEMPT_SCHEMA = "selector_promotion_held_out_attempt_v1"
PERMANENT_POLICIES = ("random-valid", "greedy-utility")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _unexpected_dirty(status: list[str]) -> list[str]:
    return [
        line
        for line in status
        if line[3:].replace("\\", "/") not in ALLOWED_DIRTY_PATHS
    ]


def _permanent_record(
    env: RlServerProcess,
    *,
    policy_name: str,
    seed: int,
    seed_set: dict[str, Any],
) -> dict[str, Any]:
    if policy_name == "random-valid":
        policy = RandomValidPolicy(seed)
        policy_version = "random-valid-splitmix64-v1"
    elif policy_name == "greedy-utility":
        policy = PureGreedyUtilityPolicy()
        policy_version = "pure-greedy-utility-v1"
    else:
        raise ValueError(f"unknown permanent policy: {policy_name}")
    result = run_utility_episode(
        env,
        seed,
        scenario_id=str(seed_set["scenario_id"]),
        scenario_version=int(seed_set["scenario_version"]),
        require_win=False,
        policy=policy,
        policy_name=policy_name,
    )
    manifest = {
        "policy": policy_name,
        "policy_version": policy_version,
        "scenario_id": seed_set["scenario_id"],
        "scenario_version": int(seed_set["scenario_version"]),
        "root_seed": seed,
        "seed_set_id": seed_set["seed_set_id"],
        "seed_set_version": int(seed_set["seed_set_version"]),
        "agent_count": 3,
        "evaluation_role": "permanent-held-out-comparator",
    }
    return ladder_episode_record(result, manifest, seed_set)


def held_out_final_decision(
    records: list[dict[str, Any]],
    aggregates: list[dict[str, Any]],
    *,
    reward_adversaries_passed: bool,
) -> dict[str, Any]:
    """Apply the frozen M8.5 held-out win and teammate-quality rules."""

    by_policy = {str(item["policy"]): item for item in aggregates}
    candidate = by_policy[CANDIDATE_POLICY]
    if candidate["seed_set"]["split"] != "held-out":
        raise ValueError("final promotion decision requires held-out records")
    permanent = [
        win_rate_comparison(
            candidate,
            by_policy[policy],
            require_ci_separation=True,
        )
        for policy in PERMANENT_POLICIES
    ]
    matched = win_rate_comparison(
        candidate,
        by_policy[GREEDY_MIXED],
        require_ci_separation=False,
    )
    scorecards = [
        paired_scorecard_non_regression(
            records,
            candidate_policy=CANDIDATE_POLICY,
            baseline_policy=baseline,
        )
        for baseline in ("greedy-utility", GREEDY_MIXED)
    ]
    promoted = bool(
        reward_adversaries_passed
        and all(item["passed"] for item in permanent)
        and matched["passed"]
        and all(item["passed"] for item in scorecards)
    )
    return {
        "schema": FINAL_SCHEMA,
        "split": candidate["seed_set"]["split"],
        "candidate": CANDIDATE_POLICY,
        "permanent_win_rate_ci_comparisons": permanent,
        "matched_greedy_win_rate_comparison": matched,
        "scorecard_non_regression": scorecards,
        "reward_adversaries_passed": reward_adversaries_passed,
        "promoted": promoted,
        "status": "promoted" if promoted else "not_promoted",
    }


def _validate_dev_preflight(
    *,
    preflight_path: Path,
    checkpoint_path: Path,
    config_path: Path,
    lineage: dict[str, Any],
    repository: dict[str, Any],
) -> dict[str, Any]:
    preflight = _load_json(preflight_path)
    if preflight.get("schema") != "selector_promotion_preflight_v1":
        raise ValueError("dev preflight schema mismatch")
    if preflight.get("split") != "dev" or not preflight.get(
        "eligible_for_held_out", False
    ):
        raise ValueError("dev preflight is not eligible for held-out")
    if preflight.get("checkpoint", {}).get("sha256") != _sha256(checkpoint_path):
        raise ValueError("dev preflight checkpoint hash mismatch")
    if preflight.get("checkpoint", {}).get("config_sha256") != _sha256(config_path):
        raise ValueError("dev preflight config hash mismatch")
    if preflight.get("lineage", {}).get(
        "lineage_reproducibility_sha256"
    ) != lineage["lineage_reproducibility_sha256"]:
        raise ValueError("dev preflight lineage hash mismatch")
    preflight_repository = preflight.get("repository", {})
    if (
        preflight_repository.get("commit") != repository["commit"]
        or not preflight_repository.get("frozen", False)
    ):
        raise ValueError("dev preflight repository is not the active frozen commit")
    if not preflight.get("reward_adversaries_passed", False):
        raise ValueError("dev preflight reward adversaries did not pass")
    for source, hash_key in (
        ("baseline_aggregate", "baseline_aggregate_sha256"),
        ("baseline_records", "baseline_records_sha256"),
        ("reward_report", "reward_report_sha256"),
    ):
        path = Path(preflight["sources"][source])
        if _sha256(path) != preflight["sources"][hash_key]:
            raise ValueError(f"dev preflight source changed: {source}")
    return preflight


def _create_attempt(path: Path, evidence: dict[str, Any]) -> None:
    """Create the permanent one-way marker; an existing marker forbids reruns."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(evidence, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(
                json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            )


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description="One-way M8.5 held-out final")
    parser.add_argument("--allow-held-out-final", action="store_true")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--lineage-manifest", type=Path, required=True)
    parser.add_argument("--dev-preflight", type=Path, required=True)
    parser.add_argument(
        "--seed-set",
        type=Path,
        default=root / "configs/evaluation/bootstrap-defense-v1-held-out-v1.json",
    )
    parser.add_argument(
        "--attempt",
        type=Path,
        default=root / "runs/m8-promotion-held-out-final.attempt.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "runs/m8-promotion-held-out-final.jsonl",
    )
    parser.add_argument(
        "--aggregate-output",
        type=Path,
        default=root / "runs/m8-promotion-held-out-final-aggregate.json",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=root / "runs/m8-promotion-held-out-final-report.json",
    )
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    if not args.allow_held_out_final:
        parser.error("held-out execution requires --allow-held-out-final")

    checkpoint_path = args.checkpoint.resolve()
    config_path = args.config.resolve()
    lineage_path = args.lineage_manifest.resolve()
    preflight_path = args.dev_preflight.resolve()
    outputs = [
        args.attempt.resolve(),
        args.output.resolve(),
        args.aggregate_output.resolve(),
        args.report_output.resolve(),
    ]
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        parser.error(
            "held-out final is one-way; artifacts already exist: " + str(existing)
        )

    repository = _git_evidence(root)
    unexpected_dirty = _unexpected_dirty(repository["status"])
    if unexpected_dirty:
        raise ValueError("held-out final requires a frozen repository")
    lineage = validate_lineage_manifest(
        manifest_path=lineage_path,
        config_path=config_path,
        checkpoint_path=checkpoint_path,
    )
    preflight = _validate_dev_preflight(
        preflight_path=preflight_path,
        checkpoint_path=checkpoint_path,
        config_path=config_path,
        lineage=lineage,
        repository=repository,
    )
    config = _load_json(config_path)
    _configure_torch(config)
    model = build_selector_model(config)
    reward_schema = str(config.get("reward_schema", REWARD_SCHEMA))
    checkpoint = load_checkpoint(
        checkpoint_path, model, reward_schema=reward_schema
    )
    if checkpoint.get("config_sha256") != _sha256(config_path):
        raise ValueError("held-out checkpoint config hash mismatch")

    attempt = {
        "schema": ATTEMPT_SCHEMA,
        "status": "started",
        "repository_commit": repository["commit"],
        "checkpoint_sha256": _sha256(checkpoint_path),
        "config_sha256": _sha256(config_path),
        "lineage_manifest_sha256": _sha256(lineage_path),
        "lineage_reproducibility_sha256": lineage[
            "lineage_reproducibility_sha256"
        ],
        "dev_preflight_sha256": _sha256(preflight_path),
        "held_out_seed_set_path": str(args.seed_set.resolve()),
    }
    _create_attempt(args.attempt.resolve(), attempt)

    # This is the first read of held-out membership. The exclusive marker above
    # makes the action permanent before any episode outcome can be observed.
    seed_set = load_seed_set(args.seed_set.resolve())
    if seed_set["split"] != "held-out":
        raise ValueError("final seed set is not held-out")
    if (
        seed_set["seed_set_id"] != config["held_out_seed_set_id"]
        or int(seed_set["seed_set_version"])
        != int(config["held_out_seed_set_version"])
    ):
        raise ValueError("held-out seed-set identity/version mismatch")

    records: list[dict[str, Any]] = []
    generator = torch.Generator().manual_seed(int(config["action_sampling_seed"]))
    policy_logit_adjustment = _policy_logit_adjustment(config)
    scripted_partner_opening = _scripted_partner_opening(config)
    with RlServerProcess(
        LaunchConfig(port=args.port, java=args.java, build_if_missing=False)
    ) as env:
        env.handshake("m8.5-held-out-final")
        for policy in (CANDIDATE_POLICY, *PERMANENT_POLICIES, GREEDY_MIXED):
            for raw_seed in seed_set["seeds"]:
                seed = int(raw_seed)
                if policy == CANDIDATE_POLICY:
                    rollout = rollout_episode(
                        env,
                        model,
                        seed=seed,
                        scenario_id=str(seed_set["scenario_id"]),
                        scenario_version=int(seed_set["scenario_version"]),
                        evaluation=True,
                        action_generator=generator,
                        reward_schema=reward_schema,
                        quality_reward=config.get("quality_reward"),
                        policy_logit_adjustment=policy_logit_adjustment,
                        scripted_partner_opening=scripted_partner_opening,
                    )
                    record = _record(
                        rollout,
                        policy=policy,
                        seed_set=seed_set,
                        checkpoint_sha256=attempt["checkpoint_sha256"],
                    )
                elif policy == GREEDY_MIXED:
                    rollout = rollout_control_episode(
                        env,
                        seed=seed,
                        scenario_id=str(seed_set["scenario_id"]),
                        scenario_version=int(seed_set["scenario_version"]),
                        control=policy,
                        scripted_partner_opening=scripted_partner_opening,
                    )
                    record = _record(
                        rollout,
                        policy=policy,
                        seed_set=seed_set,
                        checkpoint_sha256=attempt["checkpoint_sha256"],
                    )
                else:
                    record = _permanent_record(
                        env,
                        policy_name=policy,
                        seed=seed,
                        seed_set=seed_set,
                    )
                records.append(record)

    aggregates = aggregate_records(records)
    report = held_out_final_decision(
        records,
        aggregates,
        reward_adversaries_passed=bool(preflight["reward_adversaries_passed"]),
    )
    report.update(
        {
            "repository": repository,
            "checkpoint": {
                "path": str(checkpoint_path),
                "sha256": attempt["checkpoint_sha256"],
                "config_sha256": attempt["config_sha256"],
            },
            "lineage": lineage,
            "dev_preflight": {
                "path": str(preflight_path),
                "sha256": attempt["dev_preflight_sha256"],
            },
            "held_out_seed_set": {
                "id": seed_set["seed_set_id"],
                "version": int(seed_set["seed_set_version"]),
                "sha256": _sha256(args.seed_set.resolve()),
            },
        }
    )
    _write_jsonl(args.output.resolve(), records)
    args.aggregate_output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.aggregate_output.resolve().write_text(
        json.dumps({"aggregates": aggregates}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.report_output.resolve().write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    attempt.update(
        {
            "status": "completed",
            "records_sha256": _sha256(args.output.resolve()),
            "aggregate_sha256": _sha256(args.aggregate_output.resolve()),
            "report_sha256": _sha256(args.report_output.resolve()),
            "promotion_status": report["status"],
        }
    )
    args.attempt.resolve().write_text(
        json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"held_out_final={report['status']} checkpoint="
        f"{attempt['checkpoint_sha256'][:16]}"
    )
    print("M8-PROMOTION-HELD-OUT-FINAL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
