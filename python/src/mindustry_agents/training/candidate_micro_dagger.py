"""Governed maximal-freshness intra-update DAgger for M9."""

from __future__ import annotations

import argparse
import copy
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
    distillation_update,
    load_distillation_config,
)
from mindustry_agents.training.candidate_on_policy_relabel import (
    _aggregate,
    _git_commit,
    _reproducibility_evidence,
    _selection_key,
    _student_episode,
)
from mindustry_agents.training.ippo import (
    IPPO_MODEL_ARCHITECTURE,
    SharedRecurrentSelector,
    model_state_digest,
)
from mindustry_agents.training.ippo_artifacts import (
    load_ippo_checkpoint,
    save_ippo_checkpoint,
)
from mindustry_agents.training.ippo_diverse_roots import (
    diverse_training_seed_schedule,
)
from mindustry_agents.training.ippo_ppo import (
    IPPOTransition,
    sha256_path,
)


CONFIG_SHA256 = (
    "127c7290b6c3c9435933542968f309ec5b62db3463fd4c2e3500d608cc863374"
)
PROTOCOL_SHA256 = (
    "50a754dde6f3effdb95485aaba5c59dddacbb53aec48895835c7def3c9eec15e"
)
SOURCE_CONFIG_SHA256 = (
    "9fc15d1a0dd256452873fe7953374bb251ad1fbf172add0eb399d2c3541457e0"
)
SOURCE_RESULT_SHA256 = (
    "47ced62d5b7e3c15c980415bc3c05974bfacfd1ccbfd7e2af6c7f474486af590"
)
SOURCE_MANIFEST_SHA256 = (
    "cd88deac884ee8513857e979d3eeea33e5d4ea925d220cdef455edb1b992c3c0"
)
SOURCE_CANONICAL_RUN_SHA256 = (
    "c3a283d3a8b703004a93800f02ee28040c3132086a81e566980008cf2cd8974e"
)
SOURCE_CHECKPOINT_FILE_SHA256 = (
    "40bc070d91b1e37dbb58b360325dfde7b94b10aaec61dabcdb5570bf55dc5fed"
)
SOURCE_CHECKPOINT_CONTENT_SHA256 = (
    "14197b4d3583cf599917a98c2b1cbd5925ca7bc7b93be550edd4cade3a3f1fe9"
)
SOURCE_MODEL_SHA256 = (
    "c13e3858bd37c89ff5582a3e861c709808f6a3088e444fed8da5130362332c14"
)
SOURCE_OPTIMIZER_SHA256 = (
    "12e82a785787318df98ba7919f09a300e5372ae196017b3491a56db5dc5468ad"
)
COMPARISON_RESULT_SHA256 = (
    "ebea0b741abbf2b7e3d995af1f87d7528ddee08d94089db4f837f40c730e60ee"
)
SYNTHESIS_RESULT_SHA256 = (
    "156e12d2fb8b8e46b020cbd3b932f8e4e9f7043210169910fdf5da32518ca766"
)
TRAIN_SET_SHA256 = (
    "2e4d5b853ba9c8a6b568b107537756e257d3c19205af71c0445ea5ea730088c4"
)
DEV_SET_SHA256 = (
    "5d834a1ea8db828e05f2e7343a88cea1ba49721bd1570d1f435ca73778fb6b83"
)


def load_micro_dagger_config(path: Path) -> dict[str, Any]:
    """Load ADR-0129's immutable micro-DAgger construction."""

    if sha256_path(path) != CONFIG_SHA256:
        raise ValueError("M9 micro-DAgger config digest drifted")
    config = json.loads(path.read_text(encoding="utf-8"))
    schedule = config.get("training_root_schedule", {})
    learning = config.get("micro_dagger", {})
    if (
        config.get("schema") != "m9_candidate_native_micro_dagger_config_v1"
        or config.get("candidate_version")
        != "m9-candidate-native-micro-dagger-v1"
        or config.get("model_architecture") != IPPO_MODEL_ARCHITECTURE
        or config.get("confirmation_seed_set") is not None
        or config.get("held_out_seed_set") is not None
        or int(config.get("torch_threads", 0)) != 1
        or int(config.get("macro_updates", 0)) != 32
        or int(config.get("unique_roots_per_macro_update", 0)) != 64
        or int(config.get("micro_updates_per_macro_update", 0)) != 8
        or int(config.get("episodes_per_micro_update", 0)) != 64
        or int(config.get("optimizer_epochs_per_micro_update", 0)) != 1
        or schedule.get("total_collection_episodes") != 16384
        or schedule.get("micro_recollection_count_per_root") != 8
        or learning.get("collection_model")
        != "current_post_previous_micro_update_model"
        or learning.get("micro_dataset_lifetime")
        != "discard_immediately_after_its_single_optimizer_epoch"
        or any(
            learning.get(key) is not False
            for key in (
                "cross_micro_replay",
                "example_weighting",
                "sequence_backpropagation",
                "ema",
                "learning_rate_schedule",
                "critic_loss",
                "ppo_loss",
                "entropy_loss",
                "extra_rng",
            )
        )
    ):
        raise ValueError("M9 micro-DAgger config contract drifted")
    return config


def _load_protocol(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    path = root / str(config["public_evaluation_protocol"])
    if sha256_path(path) != PROTOCOL_SHA256:
        raise ValueError("M9 micro-DAgger protocol digest drifted")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    isolated = protocol.get("isolated_schedule_change", {})
    replica = protocol.get("replica_policy", {})
    authority = protocol.get("downstream_authority", {})
    if (
        protocol.get("schema")
        != "m9_candidate_native_micro_dagger_public_protocol_v1"
        or protocol.get("config_sha256") != CONFIG_SHA256
        or protocol.get("data_classification")
        != "public_train_and_dev_only"
        or isolated.get("micro_updates_per_macro_update") != 8
        or isolated.get("total_collection_episodes") != 16384
        or isolated.get(
            "all_other_training_and_evaluation_coordinates_inherited_exactly"
        )
        is not True
        or replica.get(
            "replica_b_authorized_only_after_replica_a_construction_passes"
        )
        is not True
        or replica.get(
            "replica_b_prohibited_after_replica_a_construction_failure"
        )
        is not True
        or any(value is not False for value in authority.values())
    ):
        raise ValueError("M9 micro-DAgger public authority drifted")
    return protocol


def _load_source(root: Path, config: dict[str, Any]) -> Path:
    source = config["source_checkpoint"]
    paths = {
        "checkpoint": root / str(source["path"]),
        "config": root / str(source["source_config"]),
        "result": root / str(source["source_result"]),
        "manifest": root / str(source["source_manifest"]),
        "comparison": root / str(config["comparison_result"]["path"]),
        "synthesis": root / str(config["latest_public_synthesis"]["path"]),
    }
    expected = {
        "checkpoint": SOURCE_CHECKPOINT_FILE_SHA256,
        "config": SOURCE_CONFIG_SHA256,
        "result": SOURCE_RESULT_SHA256,
        "manifest": SOURCE_MANIFEST_SHA256,
        "comparison": COMPARISON_RESULT_SHA256,
        "synthesis": SYNTHESIS_RESULT_SHA256,
    }
    if any(sha256_path(paths[key]) != value for key, value in expected.items()):
        raise ValueError("M9 micro-DAgger source evidence drifted")
    result = json.loads(paths["result"].read_text(encoding="utf-8"))
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    if (
        source.get("content_sha256")
        != SOURCE_CHECKPOINT_CONTENT_SHA256
        or source.get("model_state_sha256") != SOURCE_MODEL_SHA256
        or source.get("optimizer_state_sha256") != SOURCE_OPTIMIZER_SHA256
        or source.get("load_model_state") is not True
        or source.get("load_optimizer_state") is not True
        or source.get("construction_passed") is not False
        or source.get("selected_or_promoted") is not False
        or source.get("repaired") is not False
        or result.get("replica_a", {}).get("construction_passed") is not False
        or result.get("replica_a", {}).get("selected_checkpoint") is not None
        or manifest.get("canonical_run_sha256")
        != SOURCE_CANONICAL_RUN_SHA256
        or manifest.get("construction_passed") is not False
    ):
        raise ValueError("M9 micro-DAgger rejected source is invalid")
    return paths["checkpoint"]


def _source_model_and_optimizer(
    root: Path, config: dict[str, Any]
) -> tuple[SharedRecurrentSelector, torch.optim.Optimizer, dict[str, Any]]:
    source_config = load_distillation_config(
        root / str(config["source_checkpoint"]["source_config"])
    )
    model = SharedRecurrentSelector(int(source_config["model_init_seed"]))
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=float(config["learning_rate"]),
        eps=float(config["adam_epsilon"]),
    )
    payload = load_ippo_checkpoint(
        root / str(config["source_checkpoint"]["path"]),
        model,
        optimizer,
        expected_config_sha256=SOURCE_CONFIG_SHA256,
    )
    if (
        int(payload["update"]) != 32
        or payload["checkpoint_content_sha256"]
        != SOURCE_CHECKPOINT_CONTENT_SHA256
        or model_state_digest(model) != SOURCE_MODEL_SHA256
        or payload["optimizer_state_sha256"] != SOURCE_OPTIMIZER_SHA256
    ):
        raise ValueError("M9 micro-DAgger loaded source drifted")
    return model, optimizer, payload


def micro_dagger_optimizer_schedule(
    model: SharedRecurrentSelector,
    optimizer: torch.optim.Optimizer,
    micro_datasets: Sequence[Sequence[IPPOTransition]],
    config: dict[str, Any],
    generator: torch.Generator,
) -> list[dict[str, float]]:
    """Apply one flat-NLL epoch to each freshly collected micro dataset."""

    if len(micro_datasets) != int(config["micro_updates_per_macro_update"]):
        raise ValueError("M9 micro-DAgger dataset count drifted")
    return [
        _one_fresh_optimizer_epoch(
            model, optimizer, transitions, config, generator
        )
        for transitions in micro_datasets
    ]


def _one_fresh_optimizer_epoch(
    model: SharedRecurrentSelector,
    optimizer: torch.optim.Optimizer,
    transitions: Sequence[IPPOTransition],
    config: dict[str, Any],
    generator: torch.Generator,
) -> dict[str, float]:
    local = copy.deepcopy(config)
    local["epochs_per_update"] = 1
    return distillation_update(
        model, optimizer, transitions, local, generator
    )


def validate_preflight(
    path: Path, root: Path, config: dict[str, Any]
) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    if (
        result.get("schema")
        != "m9_candidate_native_micro_dagger_preflight_v1"
        or result.get("passed") is not True
        or result.get("implementation_commit") != _git_commit(root)
        or result.get("config_sha256") != CONFIG_SHA256
        or result.get("protocol_sha256") != PROTOCOL_SHA256
        or result.get("confirmation_or_held_out_access") is not False
    ):
        raise ValueError("M9 micro-DAgger preflight is invalid")
    return result


def train(
    config_path: Path,
    output_dir: Path,
    preflight_path: Path,
    *,
    java: str,
    port: int,
) -> dict[str, Any]:
    root = repo_root()
    config = load_micro_dagger_config(config_path)
    _load_protocol(root, config)
    _load_source(root, config)
    preflight = validate_preflight(preflight_path, root, config)
    _configure_torch(config)
    train_set, train_path = _load_seed_set(
        root, str(config["train_seed_set"]), split="train", count=2048,
        lower=TRAIN_MINIMUM, upper=TRAIN_MAXIMUM,
    )
    dev_set, dev_path = _load_seed_set(
        root, str(config["dev_seed_set"]), split="dev", count=40,
        lower=DEV_MINIMUM, upper=DEV_MAXIMUM,
    )
    if (
        sha256_path(train_path) != TRAIN_SET_SHA256
        or sha256_path(dev_path) != DEV_SET_SHA256
    ):
        raise ValueError("M9 micro-DAgger seed-set drifted")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("M9 micro-DAgger output directory is not empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    schedule = diverse_training_seed_schedule(
        train_set["seeds"], shuffle_seed=int(config["shuffle_seed"])
    )
    model, optimizer, source_payload = _source_model_and_optimizer(root, config)
    generator = torch.Generator().manual_seed(int(config["shuffle_seed"]))
    parent = str(source_payload["checkpoint_content_sha256"])
    updates: list[dict[str, Any]] = []
    selection: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    dev_by_update: list[list[dict[str, Any]]] = []
    dev_seeds = [int(seed) for seed in dev_set["seeds"]]
    initial_model_digest = model_state_digest(model)

    with RlServerProcess(
        LaunchConfig(
            port=port, java=java, build_if_missing=False,
            log_dir=output_dir, log_name="rl-server",
        )
    ) as env:
        env.handshake("m9-candidate-native-micro-dagger-v1")
        for macro in range(1, 33):
            roots = schedule[(macro - 1) * 64 : macro * 64]
            micro_rows = []
            for micro in range(1, 9):
                model.eval()
                episodes = []
                for index, seed in enumerate(roots, start=1):
                    episodes.append(
                        _student_episode(env, model, config, seed=int(seed))
                    )
                    if index % 16 == 0:
                        print(
                            f"M9 MICRO TRAIN macro={macro}/32 "
                            f"micro={micro}/8 episode={index}/64",
                            flush=True,
                        )
                transitions = [
                    item for episode in episodes
                    for item in episode.transitions
                ]
                before = model_state_digest(model)
                model.train()
                metrics = _one_fresh_optimizer_epoch(
                    model, optimizer, transitions, config, generator
                )
                micro_rows.append({
                    "micro_update": micro,
                    **metrics,
                    "collection_model_state_sha256": before,
                    "post_update_model_state_sha256": model_state_digest(model),
                    "student_wins": sum(
                        episode.outcome == "win" for episode in episodes
                    ),
                    "forced_controls": sum(
                        episode.forced_controls for episode in episodes
                    ),
                    "rejected_student_actions": sum(
                        episode.rejected_student_actions
                        for episode in episodes
                    ),
                    "student_trace_digest": _canonical_sha256(
                        [episode.trace_sha256 for episode in episodes]
                    ),
                })
            updates.append({
                "macro_update": macro,
                "lineage_update": 32 + macro,
                "micro_updates": micro_rows,
            })
            checkpoint_path = (
                output_dir / f"candidate-micro-dagger-update-{32 + macro}.pt"
            )
            checkpoint = save_ippo_checkpoint(
                checkpoint_path, model, optimizer, update=32 + macro,
                parent_checkpoint_content_sha256=parent,
                config_sha256_value=CONFIG_SHA256,
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
                "macro_update": macro,
                "lineage_update": 32 + macro,
                **_aggregate(dev),
                "checkpoint_content_sha256":
                    checkpoint["checkpoint_content_sha256"],
                "model_state_sha256": checkpoint["model_state_sha256"],
                "optimizer_state_sha256":
                    checkpoint["optimizer_state_sha256"],
            }
            row["eligible"] = (
                row["wins"]
                >= int(config["checkpoint_selection"]["minimum_wins"])
                and row["mean_team_idle_fraction"]
                < float(config["checkpoint_selection"][
                    "maximum_mean_team_idle_fraction_exclusive"
                ])
            )
            selection.append(row)
            _write_json(output_dir / "progress.json", {
                "schema": "m9_candidate_native_micro_dagger_progress_v1",
                "macro_update": macro,
                "collection_episodes": macro * 512,
                "latest_dev": row,
                "complete": False,
            })
            print(
                f"M9 MICRO DEV macro={macro}/32 wins={row['wins']}/40 "
                f"idle={row['mean_team_idle_fraction']:.6f} "
                f"eligible={row['eligible']}",
                flush=True,
            )

    eligible = [i for i, row in enumerate(selection) if row["eligible"]]
    selected_index = (
        max(eligible, key=lambda i: _selection_key({
            **selection[i], "continuation_update": selection[i]["macro_update"]
        }))
        if eligible else None
    )
    manifest: dict[str, Any] = {
        "schema": "m9_candidate_native_micro_dagger_run_v1",
        "implementation_commit": _git_commit(root),
        "config_sha256": CONFIG_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_checkpoint_content_sha256":
            SOURCE_CHECKPOINT_CONTENT_SHA256,
        "preflight_sha256": sha256_path(preflight_path),
        "preflight": preflight,
        "train_seed_set_sha256": sha256_path(train_path),
        "dev_seed_set_sha256": sha256_path(dev_path),
        "initial_model_state_sha256": initial_model_digest,
        "macro_updates": updates,
        "checkpoint_selection": selection,
        "construction_passed": selected_index is not None,
        "confirmation_or_held_out_access": False,
    }
    if selected_index is not None:
        selected = checkpoints[selected_index]
        manifest["selected_checkpoint"] = {
            **{key: selected[key] for key in (
                "file_sha256", "checkpoint_content_sha256",
                "model_state_sha256", "optimizer_state_sha256", "update",
                "parent_checkpoint_content_sha256",
            )},
            "path": str(Path(selected["path"]).relative_to(root).as_posix()),
            "macro_update": selected_index + 1,
        }
        manifest["dev"] = dev_by_update[selected_index]
    else:
        manifest["selected_checkpoint"] = None
    manifest["canonical_run_sha256"] = _canonical_sha256(
        _reproducibility_evidence(manifest)
    )
    _write_json(
        output_dir / "candidate-micro-dagger-run.manifest.json", manifest
    )
    _write_json(output_dir / "progress.json", {
        "schema": "m9_candidate_native_micro_dagger_progress_v1",
        "macro_update": 32,
        "collection_episodes": 16384,
        "complete": True,
        "construction_passed": manifest["construction_passed"],
    })
    return manifest


def compare_replicas(
    first: Path, second: Path, *, output: Path | None = None
) -> dict[str, Any]:
    documents = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (first, second)
    ]
    evidence = [_reproducibility_evidence(item) for item in documents]
    if evidence[0] != evidence[1]:
        raise RuntimeError("M9 micro-DAgger replicas diverged")
    result = {
        "schema": "m9_candidate_native_micro_dagger_replica_comparison_v1",
        "construction_passed": bool(documents[0]["construction_passed"]),
        "canonical_full_run_sha256": _canonical_sha256(evidence[0]),
        "exact_replica": True,
        "confirmation_or_held_out_access": False,
    }
    if output is not None:
        _write_json(output, result)
    return result


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path,
        default=root / "configs/training/m9-candidate-native-micro-dagger-v1.json",
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--compare-runs", nargs=2, type=Path)
    parser.add_argument("--comparison-output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.compare_runs:
            result = compare_replicas(
                *args.compare_runs, output=args.comparison_output
            )
            return 0 if result["construction_passed"] else 2
        if args.output_dir is None or args.preflight is None:
            parser.error("--output-dir and --preflight are required")
        manifest = train(
            args.config.resolve(), args.output_dir.resolve(),
            args.preflight.resolve(), java=args.java, port=args.port,
        )
    except Exception as error:
        print(f"M9 MICRO-DAGGER FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "M9 MICRO-DAGGER COMPLETE "
        f"construction={manifest['construction_passed']}"
    )
    return 0 if manifest["construction_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
