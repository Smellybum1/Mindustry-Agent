"""Governed construction runner for ADR-0133's trajectory-plan candidate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import torch

from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.training.candidate_distill import (
    DEV_MAXIMUM,
    DEV_MINIMUM,
    TRAIN_MAXIMUM,
    TRAIN_MINIMUM,
    _canonical_sha256,
    _configure_torch,
    _evaluate_episode,
    _load_seed_set,
    _write_json,
)
from mindustry_agents.training.candidate_on_policy_relabel import (
    _aggregate,
    _git_commit,
    _reproducibility_evidence,
    _selection_key,
)
from mindustry_agents.training.candidate_trajectory_plan import (
    CONFIG_SHA256,
    MODEL_ARCHITECTURE,
    MODEL_SCHEMA,
    PROTOCOL_SHA256,
    SOURCE_CONTENT_SHA256,
    SOURCE_MODEL_SHA256,
    SOURCE_OPTIMIZER_SHA256,
    TrajectoryPlanSelector,
    collect_trajectory_plan_episode,
    load_trajectory_plan_config,
    source_model_and_optimizer,
    trajectory_plan_update,
    validate_protocol,
)
from mindustry_agents.training.ippo import model_state_digest
from mindustry_agents.training.ippo_artifacts import _json_digest, _state_digest
from mindustry_agents.training.ippo_diverse_roots import (
    diverse_training_seed_schedule,
)
from mindustry_agents.training.ippo_ppo import sha256_path


CHECKPOINT_SCHEMA = "m9_candidate_native_trajectory_plan_checkpoint_v1"
TRAIN_SET_SHA256 = (
    "2e4d5b853ba9c8a6b568b107537756e257d3c19205af71c0445ea5ea730088c4"
)
DEV_SET_SHA256 = (
    "5d834a1ea8db828e05f2e7343a88cea1ba49721bd1570d1f435ca73778fb6b83"
)


def save_checkpoint(
    path: Path,
    model: TrajectoryPlanSelector,
    optimizer: torch.optim.Optimizer,
    *,
    update: int,
    parent_checkpoint_content_sha256: str,
) -> dict[str, Any]:
    optimizer_state = optimizer.state_dict()
    identity = {
        "schema": CHECKPOINT_SCHEMA,
        "config_sha256": CONFIG_SHA256,
        "model_schema": MODEL_SCHEMA,
        "model_architecture": MODEL_ARCHITECTURE,
        "update": update,
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
        "update": update,
        "parent_checkpoint_content_sha256": (
            parent_checkpoint_content_sha256
        ),
    }


def load_checkpoint(
    path: Path,
    model: TrajectoryPlanSelector,
    optimizer: torch.optim.Optimizer | None = None,
) -> dict[str, Any]:
    payload = torch.load(path, map_location="cpu", weights_only=False)
    identity = {
        key: payload.get(key)
        for key in (
            "schema",
            "config_sha256",
            "model_schema",
            "model_architecture",
            "update",
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
        raise ValueError("M9 trajectory-plan checkpoint identity drifted")
    model.load_state_dict(payload["model_state"])
    if model_state_digest(model) != payload["model_state_sha256"]:
        raise ValueError("M9 trajectory-plan checkpoint model drifted")
    if optimizer is not None:
        optimizer.load_state_dict(payload["optimizer_state"])
    return payload


def validate_preflight(path: Path, root: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    if (
        result.get("schema")
        != "m9_candidate_native_trajectory_plan_preflight_v1"
        or result.get("passed") is not True
        or result.get("implementation_commit") != _git_commit(root)
        or result.get("config_sha256") != CONFIG_SHA256
        or result.get("protocol_sha256") != PROTOCOL_SHA256
        or result.get("confirmation_or_held_out_access") is not False
    ):
        raise ValueError("M9 trajectory-plan preflight is invalid")
    return result


def _validate_source_documents(
    root: Path, config: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = config["source_checkpoint"]
    result = json.loads(
        (root / str(source["source_result"])).read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (root / str(source["source_manifest"])).read_text(encoding="utf-8")
    )
    diagnostic = json.loads(
        (root / str(config["source_diagnostic"]["path"])).read_text(
            encoding="utf-8"
        )
    )
    if (
        result.get("replica_a", {}).get("construction_passed") is not False
        or result.get("replica_b_authorized") is not False
        or result.get("confirmation_or_held_out_access") is not False
        or manifest.get("canonical_run_sha256")
        != source["source_canonical_run_sha256"]
        or diagnostic.get("classification")
        != config["source_diagnostic"]["accepted_signal"]
        or diagnostic.get("confirmation_or_held_out_access") is not False
    ):
        raise ValueError("M9 trajectory-plan rejected source is invalid")
    return result, diagnostic


def train(
    config_path: Path,
    output_dir: Path,
    preflight_path: Path,
    *,
    java: str,
    port: int,
) -> dict[str, Any]:
    root = repo_root()
    config = load_trajectory_plan_config(config_path)
    validate_protocol(root, config)
    source_result, source_diagnostic = _validate_source_documents(root, config)
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
        raise ValueError("M9 trajectory-plan seed identity drifted")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("M9 trajectory-plan output directory is not empty")
    output_dir.mkdir(parents=True, exist_ok=True)

    schedule = diverse_training_seed_schedule(
        train_set["seeds"], shuffle_seed=int(config["shuffle_seed"])
    )
    model, optimizer, source_payload = source_model_and_optimizer(root, config)
    initial_model_digest = model_state_digest(model)
    generator = torch.Generator().manual_seed(int(config["shuffle_seed"]))
    updates: list[dict[str, Any]] = []
    selection: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    dev_by_update: list[list[dict[str, Any]]] = []
    parent = str(source_payload["checkpoint_content_sha256"])
    dev_seeds = [int(seed) for seed in dev_set["seeds"]]

    with RlServerProcess(
        LaunchConfig(
            port=port,
            java=java,
            build_if_missing=False,
            log_dir=output_dir,
            log_name="rl-server",
        )
    ) as env:
        env.handshake("m9-candidate-native-trajectory-plan-v1")
        for continuation_update in range(
            1, int(config["continuation_updates"]) + 1
        ):
            start = (continuation_update - 1) * int(
                config["episodes_per_update"]
            )
            seeds = schedule[
                start : start + int(config["episodes_per_update"])
            ]
            model.eval()
            episodes = []
            for index, seed in enumerate(seeds, start=1):
                episodes.append(
                    collect_trajectory_plan_episode(
                        env, model, config, seed=int(seed)
                    )
                )
                if index % 8 == 0:
                    print(
                        "M9 TRAJECTORY PLAN TRAIN "
                        f"update={continuation_update}/32 "
                        f"episode={index}/64",
                        flush=True,
                    )
            labels = sum(item.eligible_labels for item in episodes)
            model.train()
            metrics = trajectory_plan_update(
                model, optimizer, episodes, config, generator
            )
            lineage_update = 64 + continuation_update
            update_row = {
                "continuation_update": continuation_update,
                "lineage_update": lineage_update,
                **metrics,
                "student_wins": sum(
                    item.outcome == "win" for item in episodes
                ),
                "student_teacher_top1_before_update": sum(
                    item.student_teacher_matches for item in episodes
                )
                / max(1, labels),
                "collected_context_transitions": sum(
                    item.context_transitions for item in episodes
                ),
                "forced_controls": sum(
                    item.forced_controls for item in episodes
                ),
                "rejected_student_actions": sum(
                    item.rejected_student_actions for item in episodes
                ),
                "student_trace_digest": _canonical_sha256(
                    [item.trace_sha256 for item in episodes]
                ),
            }
            updates.append(update_row)
            checkpoint = save_checkpoint(
                output_dir
                / f"candidate-trajectory-plan-update-{lineage_update}.pt",
                model,
                optimizer,
                update=lineage_update,
                parent_checkpoint_content_sha256=parent,
            )
            parent = str(checkpoint["checkpoint_content_sha256"])
            checkpoints.append(checkpoint)
            model.eval()
            dev = [
                _evaluate_episode(env, model, config, seed=seed)
                for seed in dev_seeds
            ]
            dev_by_update.append(dev)
            row = {
                "continuation_update": continuation_update,
                "lineage_update": lineage_update,
                **_aggregate(dev),
                "checkpoint_content_sha256": checkpoint[
                    "checkpoint_content_sha256"
                ],
                "model_state_sha256": checkpoint["model_state_sha256"],
                "optimizer_state_sha256": checkpoint[
                    "optimizer_state_sha256"
                ],
            }
            row["eligible"] = (
                row["wins"]
                >= int(config["checkpoint_selection"]["minimum_wins"])
                and row["mean_team_idle_fraction"]
                < float(
                    config["checkpoint_selection"][
                        "maximum_mean_team_idle_fraction_exclusive"
                    ]
                )
            )
            selection.append(row)
            _write_json(
                output_dir / "progress.json",
                {
                    "schema": "m9_candidate_native_trajectory_plan_progress_v1",
                    "continuation_update": continuation_update,
                    "train_episodes": continuation_update * 64,
                    "latest_dev": row,
                    "complete": False,
                },
            )
            print(
                "M9 TRAJECTORY PLAN DEV "
                f"update={continuation_update}/32 "
                f"wins={row['wins']}/40 "
                f"idle={row['mean_team_idle_fraction']:.6f} "
                f"eligible={row['eligible']}",
                flush=True,
            )

    eligible = [
        index for index, row in enumerate(selection) if row["eligible"]
    ]
    selected_index = (
        max(eligible, key=lambda index: _selection_key(selection[index]))
        if eligible
        else None
    )
    manifest: dict[str, Any] = {
        "schema": "m9_candidate_native_trajectory_plan_run_v1",
        "implementation_commit": _git_commit(root),
        "config_sha256": CONFIG_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_checkpoint": {
            "checkpoint_content_sha256": SOURCE_CONTENT_SHA256,
            "model_state_sha256": SOURCE_MODEL_SHA256,
            "optimizer_state_sha256": SOURCE_OPTIMIZER_SHA256,
            "selected_or_promoted": False,
            "repaired": False,
        },
        "source_result": source_result,
        "source_diagnostic": source_diagnostic,
        "preflight_sha256": sha256_path(preflight_path),
        "preflight": preflight,
        "train_seed_set_sha256": sha256_path(train_path),
        "dev_seed_set_sha256": sha256_path(dev_path),
        "initial_model_state_sha256": initial_model_digest,
        "optimizer_updates": updates,
        "checkpoint_selection": selection,
        "construction_passed": selected_index is not None,
        "confirmation_or_held_out_access": False,
    }
    if selected_index is not None:
        selected = checkpoints[selected_index]
        manifest["selected_checkpoint"] = {
            **{
                key: selected[key]
                for key in (
                    "file_sha256",
                    "checkpoint_content_sha256",
                    "model_state_sha256",
                    "optimizer_state_sha256",
                    "update",
                    "parent_checkpoint_content_sha256",
                )
            },
            "path": str(
                Path(selected["path"]).relative_to(root).as_posix()
            ),
            "continuation_update": selected_index + 1,
        }
        manifest["dev"] = dev_by_update[selected_index]
        replay_summaries = []
        for model_seed in (1, 2):
            replay_model = TrajectoryPlanSelector(
                model_seed,
                plan_head_seed=int(config["plan_head_init_seed"]),
            )
            load_checkpoint(Path(selected["path"]), replay_model)
            with RlServerProcess(
                LaunchConfig(
                    port=port,
                    java=java,
                    build_if_missing=False,
                )
            ) as replay_env:
                replay_env.handshake("m9-trajectory-plan-checkpoint-replay")
                replay_summaries.append(
                    _evaluate_episode(
                        replay_env,
                        replay_model,
                        config,
                        seed=dev_seeds[0],
                    )
                )
        if replay_summaries[0] != replay_summaries[1]:
            raise RuntimeError(
                "M9 trajectory-plan checkpoint replay diverged"
            )
        manifest["deterministic_checkpoint_verification"] = {
            "fresh_runs": 2,
            "seed": dev_seeds[0],
            "summary": replay_summaries[0],
            "bit_exact": True,
        }
    manifest["canonical_run_sha256"] = _canonical_sha256(
        _reproducibility_evidence(manifest)
    )
    _write_json(
        output_dir / "candidate-trajectory-plan-run.manifest.json",
        manifest,
    )
    _write_json(
        output_dir / "progress.json",
        {
            "schema": "m9_candidate_native_trajectory_plan_progress_v1",
            "continuation_update": 32,
            "train_episodes": 2048,
            "complete": True,
            "construction_passed": manifest["construction_passed"],
            "selected_continuation_update": (
                manifest.get("selected_checkpoint", {}).get(
                    "continuation_update"
                )
            ),
        },
    )
    return manifest


def compare_replicas(first: Path, second: Path) -> dict[str, Any]:
    documents = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (first, second)
    ]
    canonical = [
        str(item.get("canonical_run_sha256", "")) for item in documents
    ]
    checkpoints = [
        [
            (
                row["checkpoint_content_sha256"],
                row["model_state_sha256"],
                row["optimizer_state_sha256"],
            )
            for row in item["checkpoint_selection"]
        ]
        for item in documents
    ]
    equal = canonical[0] == canonical[1] and checkpoints[0] == checkpoints[1]
    return {
        "schema": "m9_candidate_native_trajectory_plan_replica_compare_v1",
        "replicas_equal": equal,
        "canonical_run_sha256": canonical,
        "checkpoint_lineage_equal": checkpoints[0] == checkpoints[1],
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
            / "configs/training/m9-candidate-native-trajectory-plan-v1.json"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "runs/m9-candidate-trajectory-plan-a",
    )
    parser.add_argument(
        "--preflight",
        type=Path,
        default=(
            root
            / "configs/evaluation/"
            "m9-candidate-native-trajectory-plan-v1-preflight-result.json"
        ),
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
        print(f"M9 TRAJECTORY PLAN FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "M9 TRAJECTORY PLAN COMPLETE "
        f"construction={manifest['construction_passed']} "
        f"canonical={manifest['canonical_run_sha256']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
