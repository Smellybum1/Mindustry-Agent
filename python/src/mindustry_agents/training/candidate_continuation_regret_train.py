"""Governed construction runner for ADR-0137 continuation regret."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

import torch

from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.training.candidate_continuation_regret import (
    CONFIG_SHA256,
    MODEL_ARCHITECTURE,
    MODEL_SCHEMA,
    PROTOCOL_SHA256,
    SOURCE_CONTENT_SHA256,
    ContinuationRegretSelector,
    ContinuationRootExample,
    ContinuationRuntimeState,
    collect_continuation_root,
    commit_boundary,
    continuation_update,
    load_continuation_config,
    planner_bundle_ranking,
    prepare_boundary,
    source_model_and_optimizer,
    validate_protocol,
)
from mindustry_agents.training.candidate_distill import (
    DEV_MAXIMUM,
    DEV_MINIMUM,
    TRAIN_MAXIMUM,
    TRAIN_MINIMUM,
    _canonical_sha256,
    _configure_torch,
    _load_seed_set,
    _write_json,
)
from mindustry_agents.training.candidate_on_policy_relabel import (
    _git_commit,
)
from mindustry_agents.training.ippo import AGENT_COUNT, model_state_digest
from mindustry_agents.training.ippo_artifacts import _json_digest, _state_digest
from mindustry_agents.training.ippo_diverse_roots import (
    diverse_training_seed_schedule,
)
from mindustry_agents.training.ippo_ppo import sha256_path


CHECKPOINT_SCHEMA = "m9_candidate_native_continuation_regret_checkpoint_v1"
TRAIN_SET_SHA256 = (
    "2e4d5b853ba9c8a6b568b107537756e257d3c19205af71c0445ea5ea730088c4"
)
DEV_SET_SHA256 = (
    "5d834a1ea8db828e05f2e7343a88cea1ba49721bd1570d1f435ca73778fb6b83"
)


def save_checkpoint(
    path: Path,
    model: ContinuationRegretSelector,
    optimizer: torch.optim.Optimizer,
    *,
    group: int,
    parent_checkpoint_content_sha256: str,
) -> dict[str, Any]:
    """Write one deterministic candidate-specific checkpoint."""

    optimizer_state = optimizer.state_dict()
    identity = {
        "schema": CHECKPOINT_SCHEMA,
        "config_sha256": CONFIG_SHA256,
        "model_schema": MODEL_SCHEMA,
        "model_architecture": MODEL_ARCHITECTURE,
        "group": group,
        "parent_checkpoint_content_sha256": (
            parent_checkpoint_content_sha256
        ),
        "model_state_sha256": model_state_digest(model),
        "optimizer_state_sha256": _state_digest(optimizer_state),
    }
    payload = {
        **identity,
        "checkpoint_content_sha256": _json_digest(identity),
        "model_state": model.state_dict(),
        "optimizer_state": optimizer_state,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary, _use_new_zipfile_serialization=False)
    temporary.replace(path)
    return {
        "path": path,
        "file_sha256": sha256_path(path),
        "checkpoint_content_sha256": payload["checkpoint_content_sha256"],
        "model_state_sha256": payload["model_state_sha256"],
        "optimizer_state_sha256": payload["optimizer_state_sha256"],
        "group": group,
        "parent_checkpoint_content_sha256": (
            parent_checkpoint_content_sha256
        ),
    }


def load_checkpoint(
    path: Path,
    model: ContinuationRegretSelector,
    optimizer: torch.optim.Optimizer | None = None,
) -> dict[str, Any]:
    """Load and verify one continuation-regret checkpoint."""

    payload = torch.load(path, map_location="cpu", weights_only=False)
    identity = {
        key: payload.get(key)
        for key in (
            "schema",
            "config_sha256",
            "model_schema",
            "model_architecture",
            "group",
            "parent_checkpoint_content_sha256",
            "model_state_sha256",
            "optimizer_state_sha256",
        )
    }
    if (
        identity["schema"] != CHECKPOINT_SCHEMA
        or identity["config_sha256"] != CONFIG_SHA256
        or identity["model_schema"] != MODEL_SCHEMA
        or identity["model_architecture"] != MODEL_ARCHITECTURE
        or _json_digest(identity) != payload.get("checkpoint_content_sha256")
        or _state_digest(payload["optimizer_state"])
        != payload["optimizer_state_sha256"]
    ):
        raise ValueError("M9 continuation checkpoint identity drifted")
    model.load_state_dict(payload["model_state"])
    model.freeze_source()
    if model_state_digest(model) != payload["model_state_sha256"]:
        raise ValueError("M9 continuation checkpoint model drifted")
    if optimizer is not None:
        optimizer.load_state_dict(payload["optimizer_state"])
    return payload


def validate_preflight(path: Path, root: Path) -> dict[str, Any]:
    """Require fresh exact-HEAD public training authority."""

    result = json.loads(path.read_text(encoding="utf-8"))
    if (
        result.get("schema")
        != "m9_candidate_native_continuation_regret_preflight_v1"
        or result.get("passed") is not True
        or result.get("implementation_commit") != _git_commit(root)
        or result.get("config_sha256") != CONFIG_SHA256
        or result.get("protocol_sha256") != PROTOCOL_SHA256
        or result.get("confirmation_or_held_out_access") is not False
    ):
        raise ValueError("M9 continuation preflight is invalid")
    return result


def _aggregate(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    count = max(1, len(rows))
    return {
        "wins": sum(item["outcome"] == "win" for item in rows),
        "mean_core_health": sum(float(item["core_health"]) for item in rows)
        / count,
        "mean_team_idle_fraction": sum(
            float(item["team_idle_fraction"]) for item in rows
        )
        / count,
        "rejected_learned_actions": sum(
            int(item["rejected_learned_actions"]) for item in rows
        ),
        "planner_bundle_exact_rate": sum(
            float(item["planner_bundle_exact_rate"]) for item in rows
        )
        / count,
        "mean_planner_rank_cost": sum(
            float(item["mean_planner_rank_cost"]) for item in rows
        )
        / count,
        "state_hash_trace_sha256": _canonical_sha256(
            [item["trace_sha256"] for item in rows]
        ),
    }


def evaluate_episode(
    env: RlServerProcess,
    model: ContinuationRegretSelector,
    config: dict[str, Any],
    *,
    seed: int,
) -> dict[str, Any]:
    """Evaluate one planner-free deterministic cost-model episode."""

    reset = env.reset(
        seed,
        scenario_id=str(config["scenario_id"]),
        scenario_version=int(config["scenario_version"]),
        agent_count=AGENT_COUNT,
    )
    runtime = ContinuationRuntimeState.fresh()
    from mindustry_agents.policies import CandidateNativePlannerV11

    observer = CandidateNativePlannerV11()
    observations = reset.initial_observations
    masks = reset.action_masks
    metadata = reset.metadata
    board: list[dict[str, Any]] = []
    reasons: list[str] = []
    tick = reset.tick
    outcome = reset.outcome
    metrics: dict[str, Any] = {}
    rejected = 0
    ranks: list[float] = []
    exact = 0
    trace: list[dict[str, Any]] = []
    while outcome == "running" and tick < int(metadata["tick_cap"]):
        prepared = prepare_boundary(
            model,
            runtime,
            observations,
            masks,
            metadata,
            task_board=board,
            boundary_reasons=reasons,
            selection="cost",
        )
        chosen = tuple(
            prepared.decision.action_indices[agent_id]
            for agent_id in range(AGENT_COUNT)
        )
        ranking = planner_bundle_ranking(
            observer, observations, masks, board
        )
        rank = ranking.fractional_rank.get(chosen, 1.0)
        ranks.append(rank)
        exact += int(chosen == ranking.ordered_action_indices[0])
        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, int(metadata["tick_cap"]) - tick),
            agent_actions=prepared.decision.agent_actions,
            stop_on_decision_event=True,
        )
        rejected += sum(
            not item.get("accepted", False)
            for item in response.action_results
        )
        commit_boundary(
            runtime,
            prepared,
            response.action_results,
            observations,
            tick=tick,
        )
        trace.append(
            {
                "tick": tick,
                "next_tick": response.tick,
                "bundle": chosen,
                "rank_cost": rank,
                "action_results": response.action_results,
                "state_hash": response.state_hash,
                "outcome": response.outcome,
            }
        )
        observations = response.observations
        masks = response.action_masks
        board = response.task_board
        reasons = list(response.decision_boundary.get("reasons", []))
        tick = response.tick
        outcome = response.outcome
        metrics = response.coordination_metrics
    if outcome == "running":
        raise RuntimeError("M9 continuation evaluation was incomplete")
    return {
        "seed": seed,
        "outcome": outcome,
        "tick": tick,
        "core_health": float(observations[0]["team"]["core_health"]),
        "team_idle_fraction": float(metrics["idle_fraction"]),
        "rejected_learned_actions": rejected,
        "planner_bundle_exact_rate": exact / max(1, len(ranks)),
        "mean_planner_rank_cost": sum(ranks) / max(1, len(ranks)),
        "trace_sha256": _canonical_sha256(trace),
    }


def _collection_metrics(
    roots: Sequence[ContinuationRootExample],
    model: ContinuationRegretSelector,
) -> dict[str, Any]:
    targets = torch.cat([item.targets for item in roots])
    achieved = torch.cat([item.achieved_horizons for item in roots])
    exact = 0
    rows = 0
    with torch.no_grad():
        for item in roots:
            hidden = model.continuation_hidden(
                item.prefix_global_inputs, item.prefix_commit_mask
            )
            outputs = model.cost_outputs(
                item.bundle_static_inputs, hidden
            )[0]
            exact += int(
                int(torch.argmin(outputs.mean(dim=-1)).item()) == 0
            )
            rows += 1
    return {
        "roots_collected": len(roots),
        "branch_rows": sum(item.branch_rows for item in roots),
        "planner_inadmissible_rows": sum(
            sum(item.planner_inadmissible) for item in roots
        ),
        "achieved_target_counts_by_horizon": {
            str(horizon): int((achieved[:, index] >= horizon).sum().item())
            for index, horizon in enumerate((1, 4, 8, 16))
        },
        "mean_targets_by_horizon": {
            str(horizon): float(targets[:, index].mean().item())
            for index, horizon in enumerate((1, 4, 8, 16))
        },
        "source_bundle_exact_rate": exact / max(1, rows),
        "selected_state_trace_sha256": _canonical_sha256(
            [item.selected_state_sha256 for item in roots]
        ),
        "branch_trace_sha256": _canonical_sha256(
            [item.branch_trace_sha256 for item in roots]
        ),
    }


def train(
    config_path: Path,
    output_dir: Path,
    preflight_path: Path,
    *,
    java: str,
    port: int,
) -> dict[str, Any]:
    """Run one non-resumable exact construction replica."""

    root = repo_root()
    config = load_continuation_config(config_path)
    validate_protocol(root, config)
    preflight = validate_preflight(preflight_path, root)
    _configure_torch(config)
    train_set, train_path = _load_seed_set(
        root,
        str(config["train_seed_set"]),
        split="train",
        count=2048,
        lower=TRAIN_MINIMUM,
        upper=TRAIN_MAXIMUM,
    )
    dev_set, dev_path = _load_seed_set(
        root,
        str(config["dev_seed_set"]),
        split="dev",
        count=40,
        lower=DEV_MINIMUM,
        upper=DEV_MAXIMUM,
    )
    if (
        sha256_path(train_path) != TRAIN_SET_SHA256
        or sha256_path(dev_path) != DEV_SET_SHA256
    ):
        raise ValueError("M9 continuation public seed identity drifted")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("M9 continuation output directory is not empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    schedule = diverse_training_seed_schedule(
        train_set["seeds"],
        shuffle_seed=int(config["rng"]["training_schedule_seed"]),
    )
    model, optimizer, source_payload = source_model_and_optimizer(root, config)
    initial_model = model_state_digest(model)
    generator = torch.Generator().manual_seed(
        int(config["rng"]["minibatch_seed"])
    )
    replay: list[ContinuationRootExample] = []
    groups: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    parent = SOURCE_CONTENT_SHA256
    with RlServerProcess(
        LaunchConfig(
            port=port,
            java=java,
            build_if_missing=False,
            log_dir=output_dir,
            log_name="rl-server",
        )
    ) as env:
        env.handshake("m9-candidate-native-continuation-regret-v1")
        for group in range(1, 33):
            seeds = schedule[(group - 1) * 64 : group * 64]
            current = []
            model.eval()
            for index, seed in enumerate(seeds, start=1):
                current.append(
                    collect_continuation_root(
                        env, model, config, seed=int(seed)
                    )
                )
                if index % 8 == 0:
                    print(
                        "M9 CONTINUATION COLLECT "
                        f"group={group}/32 root={index}/64",
                        flush=True,
                    )
            collection = _collection_metrics(current, model)
            replay.extend(current)
            model.train()
            update = continuation_update(
                model, optimizer, replay, config, generator
            )
            checkpoint = save_checkpoint(
                output_dir / f"continuation-regret-group-{group}.pt",
                model,
                optimizer,
                group=group,
                parent_checkpoint_content_sha256=parent,
            )
            parent = str(checkpoint["checkpoint_content_sha256"])
            checkpoints.append(checkpoint)
            row = {
                "group": group,
                **collection,
                **update,
                "checkpoint_content_sha256": checkpoint[
                    "checkpoint_content_sha256"
                ],
                "model_state_sha256": checkpoint["model_state_sha256"],
                "optimizer_state_sha256": checkpoint[
                    "optimizer_state_sha256"
                ],
            }
            groups.append(row)
            _write_json(
                output_dir / "progress.json",
                {
                    "schema": "m9_continuation_regret_progress_v1",
                    "group": group,
                    "roots_collected": group * 64,
                    "complete": False,
                    "latest": row,
                },
            )
            print(
                "M9 CONTINUATION UPDATE "
                f"group={group}/32 loss={update['mean_loss']:.6f}",
                flush=True,
            )
        model.eval()
        dev = [
            evaluate_episode(env, model, config, seed=int(seed))
            for seed in dev_set["seeds"]
        ]
    summary = _aggregate(dev)
    gate = config["construction_gate"]
    construction = (
        summary["wins"] >= int(gate["minimum_wins"])
        and summary["mean_team_idle_fraction"]
        < float(gate["maximum_mean_team_idle_fraction_exclusive"])
        and summary["rejected_learned_actions"]
        <= int(gate["maximum_rejected_learned_actions"])
    )
    final_checkpoint = checkpoints[-1]
    manifest: dict[str, Any] = {
        "schema": "m9_candidate_native_continuation_regret_run_v1",
        "implementation_commit": _git_commit(root),
        "config_sha256": CONFIG_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_checkpoint": {
            "checkpoint_content_sha256": source_payload[
                "checkpoint_content_sha256"
            ],
            "model_state_sha256": source_payload["model_state_sha256"],
            "optimizer_state_sha256": source_payload[
                "optimizer_state_sha256"
            ],
            "optimizer_loaded": False,
            "selected_or_promoted": False,
            "repaired": False,
        },
        "preflight_sha256": sha256_path(preflight_path),
        "preflight": preflight,
        "train_seed_set_sha256": sha256_path(train_path),
        "dev_seed_set_sha256": sha256_path(dev_path),
        "initial_model_state_sha256": initial_model,
        "optimizer_groups": groups,
        "final_checkpoint": {
            **{
                key: final_checkpoint[key]
                for key in (
                    "file_sha256",
                    "checkpoint_content_sha256",
                    "model_state_sha256",
                    "optimizer_state_sha256",
                    "group",
                    "parent_checkpoint_content_sha256",
                )
            },
            "path": str(
                Path(final_checkpoint["path"]).relative_to(root).as_posix()
            ),
        },
        "dev": dev,
        "final_public_dev": summary,
        "construction_passed": construction,
        "checkpoint_selection": False,
        "confirmation_or_held_out_access": False,
    }
    manifest["canonical_run_sha256"] = _canonical_sha256(
        {
            "config_sha256": CONFIG_SHA256,
            "protocol_sha256": PROTOCOL_SHA256,
            "initial_model_state_sha256": initial_model,
            "optimizer_groups": groups,
            "final_checkpoint_content_sha256": final_checkpoint[
                "checkpoint_content_sha256"
            ],
            "dev": dev,
            "construction_passed": construction,
        }
    )
    _write_json(
        output_dir / "continuation-regret-run.manifest.json", manifest
    )
    _write_json(
        output_dir / "progress.json",
        {
            "schema": "m9_continuation_regret_progress_v1",
            "group": 32,
            "roots_collected": 2048,
            "complete": True,
            "construction_passed": construction,
        },
    )
    return manifest


def compare_replicas(first: Path, second: Path) -> dict[str, Any]:
    """Compare two exact completed construction replicas."""

    documents = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (first, second)
    ]
    canonical = [
        str(item.get("canonical_run_sha256", "")) for item in documents
    ]
    lineages = [
        [
            (
                row["checkpoint_content_sha256"],
                row["model_state_sha256"],
                row["optimizer_state_sha256"],
            )
            for row in item["optimizer_groups"]
        ]
        for item in documents
    ]
    equal = canonical[0] == canonical[1] and lineages[0] == lineages[1]
    return {
        "schema": "m9_continuation_regret_replica_compare_v1",
        "replicas_equal": equal,
        "canonical_run_sha256": canonical,
        "checkpoint_lineage_equal": lineages[0] == lineages[1],
        "replica_b_valid": (
            equal
            and documents[0].get("construction_passed") is True
            and documents[1].get("construction_passed") is True
        ),
        "confirmation_or_held_out_access": False,
    }


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=(
            root
            / "configs/training/"
            "m9-candidate-native-continuation-regret-v1.json"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "runs/m9-candidate-continuation-regret-a",
    )
    parser.add_argument(
        "--preflight",
        type=Path,
        default=root / "runs/m9-candidate-continuation-regret-preflight.json",
    )
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    try:
        manifest = train(
            args.config.resolve(),
            args.output_dir.resolve(),
            args.preflight.resolve(),
            java=args.java,
            port=args.port,
        )
    except Exception as error:
        print(f"M9 CONTINUATION FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "M9 CONTINUATION COMPLETE "
        f"construction={manifest['construction_passed']} "
        f"canonical={manifest['canonical_run_sha256']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
