"""Governed disagreement-weighted student-state continuation for M9."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import fmean
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
    load_distillation_config,
)
from mindustry_agents.training.candidate_on_policy_relabel import (
    CONFIG_SHA256 as SOURCE_CHECKPOINT_CONFIG_SHA256,
    SOURCE_CONFIG_RELATIVE as DISTILL_CONFIG_RELATIVE,
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
from mindustry_agents.training.ippo_ppo import IPPOTransition, sha256_path


CONFIG_SHA256 = (
    "c2401782578d2e8a3a3277fa8920d17fcee23f7cda89e92a9e1d09cfb166f459"
)
PROTOCOL_SHA256 = (
    "a42b1cd24a78f67404868835642c4c4a77143865f0e101bea57f6d197b88cab3"
)
SOURCE_RESULT_SHA256 = (
    "ebea0b741abbf2b7e3d995af1f87d7528ddee08d94089db4f837f40c730e60ee"
)
DIAGNOSTIC_RESULT_SHA256 = (
    "959e55f140fce098ac9b51ed69f247408c516bbf63bcc510617ab93af2d6cb88"
)
TRAIN_SET_SHA256 = (
    "2e4d5b853ba9c8a6b568b107537756e257d3c19205af71c0445ea5ea730088c4"
)
DEV_SET_SHA256 = (
    "5d834a1ea8db828e05f2e7343a88cea1ba49721bd1570d1f435ca73778fb6b83"
)
SOURCE_CHECKPOINT_FILE_SHA256 = (
    "cbfde7e932e718f49b6e80f79bfd2b0072fa2bb7fd1f04e4ca0d7da9ee8ed408"
)
SOURCE_CHECKPOINT_CONTENT_SHA256 = (
    "55005ab5a0591b2688e32a4819678088f0f8701de920dbf788202539c046b865"
)
SOURCE_MODEL_SHA256 = (
    "7838b9392b32d7dc5867dd53ffed78a77f9094f3492cf0b2ac4406ec551ae0d1"
)
SOURCE_OPTIMIZER_SHA256 = (
    "f3bdf93bf2dfae69842b87ca69f124c1bdda074b05422c02198530a5fdb687bc"
)
SOURCE_MANIFEST_SHA256 = (
    "f34c50a024f05d6084a8661fb627fa8c3c5cd223dc45bd03273258877f489952"
)
HARD_EXAMPLE_WEIGHT = 4.0
ORDINARY_EXAMPLE_WEIGHT = 1.0


def load_hard_example_config(path: Path) -> dict[str, Any]:
    """Load ADR-0123's immutable weighted continuation."""

    if sha256_path(path) != CONFIG_SHA256:
        raise ValueError("M9 hard-example relabel config digest drifted")
    config = json.loads(path.read_text(encoding="utf-8"))
    if (
        config.get("schema")
        != "m9_candidate_native_hard_example_relabel_config_v1"
        or config.get("candidate_version")
        != "m9-candidate-native-hard-example-relabel-v1"
        or config.get("model_architecture") != IPPO_MODEL_ARCHITECTURE
        or config.get("confirmation_seed_set") is not None
        or config.get("held_out_seed_set") is not None
        or int(config.get("torch_threads", 0)) != 1
        or int(config.get("continuation_updates", 0)) != 32
        or int(config.get("episodes_per_update", 0)) != 64
        or str(config.get("train_seed_set_sha256")) != TRAIN_SET_SHA256
        or str(config.get("dev_seed_set_sha256")) != DEV_SET_SHA256
    ):
        raise ValueError("M9 hard-example relabel config contract drifted")
    expected = {
        "schema": "candidate_native_student_state_disagreement_weighted_nll_v1",
        "student_controls_environment": True,
        "student_action_mode": "deterministic_argmax",
        "teacher_labels_same_pre_action_student_visited_boundary": True,
        "teacher_action_execution": False,
        "transition_filter": (
            "alive_and_no_forced_task_action_and_teacher_action_"
            "authoritatively_legal"
        ),
        "forced_controls": (
            "student_forced_action_executed_but_excluded_from_actor_loss"
        ),
        "dataset": "current_update_student_visited_boundaries_only",
        "disagreement_reference": (
            "pre_update_deterministic_student_action_at_collected_boundary"
        ),
        "hard_example_condition": (
            "student_action_index_differs_from_teacher_label"
        ),
        "hard_example_weight": HARD_EXAMPLE_WEIGHT,
        "ordinary_example_weight": ORDINARY_EXAMPLE_WEIGHT,
        "weight_assignment": (
            "recorded_during_collection_and_not_recomputed_after_optimizer_steps"
        ),
        "loss": (
            "sum_example_weight_times_teacher_nll_divided_by_"
            "sum_example_weight_per_minibatch"
        ),
        "hidden_input": (
            "current_student_private_hidden_at_boundary_detached"
        ),
        "hidden_state_reset": "episode_reset_or_authoritative_seat_death",
        "target_identifiers_added": False,
        "feature_schema_change": False,
        "planner_change": False,
        "cross_agent_state": False,
        "critic_loss": False,
        "reward_loss": False,
        "ppo_loss": False,
        "mappo_loss": False,
        "entropy_loss": False,
        "extra_rng": False,
    }
    if config.get("hard_example_relabeling") != expected:
        raise ValueError("M9 hard-example relabel learning contract drifted")
    return config


def _load_protocol(
    root: Path, config: dict[str, Any]
) -> dict[str, Any]:
    path = root / str(config["public_evaluation_protocol"])
    if sha256_path(path) != PROTOCOL_SHA256:
        raise ValueError("M9 hard-example relabel protocol digest drifted")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    authority = protocol.get("downstream_authority", {})
    source = protocol.get("source_checkpoint", {})
    replica = protocol.get("replica_policy", {})
    if (
        protocol.get("schema")
        != "m9_candidate_native_hard_example_relabel_public_protocol_v1"
        or protocol.get("candidate_version") != config["candidate_version"]
        or protocol.get("seed_set") != config["dev_seed_set"]
        or protocol.get("seed_set_sha256") != DEV_SET_SHA256
        or source.get("content_sha256")
        != SOURCE_CHECKPOINT_CONTENT_SHA256
        or source.get("model_state_sha256") != SOURCE_MODEL_SHA256
        or source.get("optimizer_state_sha256")
        != SOURCE_OPTIMIZER_SHA256
        or source.get("selected_or_promoted") is not False
        or source.get("repaired") is not False
        or protocol.get("source_diagnostic", {}).get("sha256")
        != DIAGNOSTIC_RESULT_SHA256
        or protocol.get("source_diagnostic", {}).get("accepted_signal")
        != "feature_distinguishable_ranking_signal"
        or replica.get(
            "replica_b_authorized_only_after_replica_a_construction_passes"
        )
        is not True
        or replica.get(
            "replica_b_prohibited_after_replica_a_construction_failure"
        )
        is not True
        or any(
            authority.get(key) is not False
            for key in (
                "may_select_or_repair_source_checkpoint",
                "may_change_planner",
                "may_add_target_identifiers",
                "may_use_reward_or_ppo_or_mappo",
                "may_promote",
                "may_access_confirmation",
                "may_access_held_out",
                "may_authorize_human_session",
            )
        )
    ):
        raise ValueError("M9 hard-example relabel public authority drifted")
    return protocol


def _load_source(
    root: Path, config: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    source = config["source_checkpoint"]
    result_path = root / str(source["source_result"])
    diagnostic_path = root / str(source["diagnostic_result"])
    checkpoint_path = root / str(source["path"])
    manifest_path = root / str(source["source_manifest"])
    if (
        source.get("source_result_sha256") != SOURCE_RESULT_SHA256
        or sha256_path(result_path) != SOURCE_RESULT_SHA256
        or source.get("diagnostic_result_sha256")
        != DIAGNOSTIC_RESULT_SHA256
        or sha256_path(diagnostic_path) != DIAGNOSTIC_RESULT_SHA256
        or source.get("source_manifest_sha256")
        != SOURCE_MANIFEST_SHA256
        or sha256_path(manifest_path) != SOURCE_MANIFEST_SHA256
        or source.get("file_sha256") != SOURCE_CHECKPOINT_FILE_SHA256
        or sha256_path(checkpoint_path) != SOURCE_CHECKPOINT_FILE_SHA256
        or source.get("content_sha256")
        != SOURCE_CHECKPOINT_CONTENT_SHA256
        or source.get("model_state_sha256") != SOURCE_MODEL_SHA256
        or source.get("optimizer_state_sha256")
        != SOURCE_OPTIMIZER_SHA256
        or source.get("source_config_sha256")
        != SOURCE_CHECKPOINT_CONFIG_SHA256
        or source.get("load_model_state") is not True
        or source.get("load_optimizer_state") is not True
        or source.get("selected_or_promoted") is not False
        or source.get("repaired") is not False
    ):
        raise ValueError("M9 hard-example relabel source identity drifted")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        result.get("replica_a", {}).get("construction_passed") is not False
        or result.get("replica_a", {}).get("selected_checkpoint") is not None
        or result.get("replica_b_authorized") is not False
        or result.get("confirmation_or_held_out_access") is not False
        or diagnostic.get("classification", {}).get(
            "feature_distinguishable_ranking_signal"
        )
        is not True
        or diagnostic.get("successor_training_authorized") is not False
        or diagnostic.get("confirmation_or_held_out_access") is not False
        or manifest.get("construction_passed") is not False
        or manifest.get("selected_checkpoint") is not None
        or manifest.get("canonical_run_sha256")
        != result["replica_a"]["canonical_run_sha256"]
    ):
        raise ValueError("M9 hard-example relabel source evidence is invalid")
    return result, diagnostic, checkpoint_path


def _source_model_and_optimizer(
    root: Path,
    config: dict[str, Any],
) -> tuple[
    SharedRecurrentSelector,
    torch.optim.Optimizer,
    dict[str, Any],
]:
    source_config = load_distillation_config(
        root / DISTILL_CONFIG_RELATIVE
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
        expected_config_sha256=SOURCE_CHECKPOINT_CONFIG_SHA256,
    )
    if (
        int(payload["update"]) != 64
        or payload["checkpoint_content_sha256"]
        != SOURCE_CHECKPOINT_CONTENT_SHA256
        or payload["model_state_sha256"] != SOURCE_MODEL_SHA256
        or payload["optimizer_state_sha256"] != SOURCE_OPTIMIZER_SHA256
        or model_state_digest(model) != SOURCE_MODEL_SHA256
    ):
        raise ValueError("M9 hard-example relabel loaded source drifted")
    return model, optimizer, payload


def weighted_distillation_update(
    model: SharedRecurrentSelector,
    optimizer: torch.optim.Optimizer,
    transitions: Sequence[IPPOTransition],
    hard_example_flags: Sequence[bool],
    config: dict[str, Any],
    generator: torch.Generator,
) -> dict[str, float]:
    """Apply ADR-0123's normalized disagreement-weighted teacher NLL."""

    if not transitions:
        raise ValueError("M9 hard-example relabel update has no labels")
    if len(transitions) != len(hard_example_flags):
        raise ValueError("M9 hard-example relabel weights are misaligned")
    learning = config["hard_example_relabeling"]
    hard_weight = float(learning["hard_example_weight"])
    ordinary_weight = float(learning["ordinary_example_weight"])
    if hard_weight != HARD_EXAMPLE_WEIGHT or ordinary_weight != 1.0:
        raise ValueError("M9 hard-example relabel weights drifted")
    candidates = torch.stack([item.candidates for item in transitions])
    scalars = torch.stack([item.scalars for item in transitions])
    present = torch.stack([item.candidate_present for item in transitions])
    masks = torch.stack([item.action_mask for item in transitions])
    hidden = torch.stack([item.hidden_input for item in transitions]).detach()
    agent_ids = torch.tensor(
        [item.agent_id for item in transitions], dtype=torch.long
    )
    actions = torch.tensor(
        [item.action for item in transitions], dtype=torch.long
    )
    hard = torch.tensor(hard_example_flags, dtype=torch.bool)
    weights = torch.where(
        hard,
        torch.tensor(hard_weight, dtype=torch.float32),
        torch.tensor(ordinary_weight, dtype=torch.float32),
    )
    if not bool(
        masks[torch.arange(len(transitions)), actions].all().item()
    ):
        raise ValueError("M9 hard-example relabel label is outside its mask")
    batch_size = int(config["minibatch_size"])
    weighted_losses = 0.0
    unweighted_losses = 0.0
    batches = 0
    correct = 0
    hard_correct = 0
    ordinary_correct = 0
    presentations = 0
    hard_presentations = 0
    ordinary_presentations = 0
    weighted_presentations = 0.0
    for _ in range(int(config["epochs_per_update"])):
        order = torch.randperm(len(transitions), generator=generator)
        for start in range(0, len(transitions), batch_size):
            index = order[start : start + batch_size]
            _, logits, _, _ = model(
                candidates[index],
                scalars[index],
                present[index],
                masks[index],
                agent_ids[index],
                hidden[index],
            )
            log_probabilities = torch.log_softmax(logits, dim=-1)
            nll = -log_probabilities.gather(
                1, actions[index, None]
            ).squeeze(1)
            batch_weights = weights[index]
            weight_sum = batch_weights.sum()
            if float(weight_sum.item()) <= 0.0:
                raise ValueError(
                    "M9 hard-example relabel batch has no weight"
                )
            loss = (batch_weights * nll).sum() / weight_sum
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(), float(config["max_grad_norm"])
            )
            optimizer.step()
            predicted = torch.argmax(logits, dim=-1)
            correct_mask = predicted == actions[index]
            hard_batch = hard[index]
            ordinary_batch = ~hard_batch
            weighted_losses += float(loss.item())
            unweighted_losses += float(nll.mean().item())
            batches += 1
            correct += int(correct_mask.sum().item())
            hard_correct += int(
                (correct_mask & hard_batch).sum().item()
            )
            ordinary_correct += int(
                (correct_mask & ordinary_batch).sum().item()
            )
            presentations += len(index)
            hard_presentations += int(hard_batch.sum().item())
            ordinary_presentations += int(ordinary_batch.sum().item())
            weighted_presentations += float(weight_sum.item())
    hard_labels = int(hard.sum().item())
    ordinary_labels = len(transitions) - hard_labels
    total_weight = float(weights.sum().item())
    return {
        "teacher_nll": weighted_losses / max(1, batches),
        "weighted_teacher_nll": weighted_losses / max(1, batches),
        "unweighted_teacher_nll": unweighted_losses / max(1, batches),
        "batches": float(batches),
        "labels": float(len(transitions)),
        "hard_example_labels": float(hard_labels),
        "ordinary_example_labels": float(ordinary_labels),
        "total_example_weight": total_weight,
        "hard_example_weight_fraction": (
            hard_labels * hard_weight / total_weight
        ),
        "presentations": float(presentations),
        "hard_example_presentations": float(hard_presentations),
        "ordinary_example_presentations": float(ordinary_presentations),
        "weighted_presentations": weighted_presentations,
        "presentation_top1_accuracy": correct / max(1, presentations),
        "hard_example_presentation_top1_accuracy": (
            hard_correct / max(1, hard_presentations)
        ),
        "ordinary_presentation_top1_accuracy": (
            ordinary_correct / max(1, ordinary_presentations)
        ),
    }


def _aggregate(episodes: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "episodes": len(episodes),
        "wins": sum(item["outcome"] == "win" for item in episodes),
        "mean_core_health": fmean(
            float(item["core_health"]) for item in episodes
        ),
        "mean_team_idle_fraction": fmean(
            float(item["team_idle_fraction"]) for item in episodes
        ),
    }


def validate_preflight(
    path: Path, root: Path, config: dict[str, Any]
) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    if (
        result.get("schema")
        != "m9_candidate_native_hard_example_relabel_preflight_v1"
        or result.get("passed") is not True
        or result.get("implementation_commit") != _git_commit(root)
        or result.get("config_sha256") != CONFIG_SHA256
        or result.get("protocol_sha256") != PROTOCOL_SHA256
        or result.get("source_checkpoint_content_sha256")
        != SOURCE_CHECKPOINT_CONTENT_SHA256
        or result.get("confirmation_or_held_out_access") is not False
    ):
        raise ValueError("M9 hard-example relabel preflight is invalid")
    return result


def train(
    config_path: Path,
    output_dir: Path,
    preflight_path: Path,
    *,
    java: str,
    port: int,
) -> dict[str, Any]:
    """Run one non-resumable ADR-0123 continuation replica."""

    root = repo_root()
    config = load_hard_example_config(config_path)
    _load_protocol(root, config)
    source_result, diagnostic, _ = _load_source(root, config)
    preflight = validate_preflight(preflight_path, root, config)
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
        raise ValueError("M9 hard-example relabel seed-set digest drifted")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(
            "M9 hard-example relabel output directory is not empty"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    schedule = diverse_training_seed_schedule(
        train_set["seeds"], shuffle_seed=int(config["shuffle_seed"])
    )
    model, optimizer, source_payload = _source_model_and_optimizer(
        root, config
    )
    generator = torch.Generator().manual_seed(int(config["shuffle_seed"]))
    initial_model_digest = model_state_digest(model)
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
        env.handshake("m9-candidate-native-hard-example-relabel-v1")
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
                    _student_episode(env, model, config, seed=int(seed))
                )
                if index % 8 == 0:
                    print(
                        "M9 HARD-EXAMPLE TRAIN "
                        f"update={continuation_update}/32 "
                        f"episode={index}/64",
                        flush=True,
                    )
            labels = [
                transition
                for episode in episodes
                for transition in episode.transitions
            ]
            hard_examples = [
                flag
                for episode in episodes
                for flag in episode.hard_example_flags
            ]
            model.train()
            metrics = weighted_distillation_update(
                model,
                optimizer,
                labels,
                hard_examples,
                config,
                generator,
            )
            update_row = {
                "continuation_update": continuation_update,
                "lineage_update": 64 + continuation_update,
                **metrics,
                "student_wins": sum(
                    episode.outcome == "win" for episode in episodes
                ),
                "student_teacher_top1_before_update": sum(
                    episode.student_teacher_matches for episode in episodes
                )
                / max(1, len(labels)),
                "forced_controls": sum(
                    episode.forced_controls for episode in episodes
                ),
                "rejected_student_actions": sum(
                    episode.rejected_student_actions
                    for episode in episodes
                ),
                "student_trace_digest": (
                    _canonical_sha256(
                        [episode.trace_sha256 for episode in episodes]
                    )
                ),
            }
            updates.append(update_row)
            lineage_update = 64 + continuation_update
            checkpoint_path = (
                output_dir
                / f"candidate-hard-example-relabel-update-{lineage_update}.pt"
            )
            checkpoint = save_ippo_checkpoint(
                checkpoint_path,
                model,
                optimizer,
                update=lineage_update,
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
                >= int(
                    config["checkpoint_selection"]["minimum_wins"]
                )
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
                    "schema": (
                        "m9_candidate_native_hard_example_relabel_progress_v1"
                    ),
                    "continuation_update": continuation_update,
                    "train_episodes": continuation_update * 64,
                    "latest_dev": row,
                    "complete": False,
                },
            )
            print(
                "M9 HARD-EXAMPLE DEV "
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
        "schema": "m9_candidate_native_hard_example_relabel_run_v1",
        "implementation_commit": _git_commit(root),
        "config_sha256": CONFIG_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_result_sha256": SOURCE_RESULT_SHA256,
        "diagnostic_result_sha256": DIAGNOSTIC_RESULT_SHA256,
        "source_checkpoint": {
            "file_sha256": SOURCE_CHECKPOINT_FILE_SHA256,
            "checkpoint_content_sha256": (
                SOURCE_CHECKPOINT_CONTENT_SHA256
            ),
            "model_state_sha256": SOURCE_MODEL_SHA256,
            "optimizer_state_sha256": SOURCE_OPTIMIZER_SHA256,
            "selected_or_promoted": False,
            "repaired": False,
        },
        "source_result": source_result,
        "source_diagnostic": diagnostic,
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
            "path": str(Path(selected["path"]).relative_to(root).as_posix()),
            "continuation_update": selected_index + 1,
        }
        manifest["dev"] = dev_by_update[selected_index]
        replay_summaries = []
        for model_seed in (1, 2):
            replay_model = SharedRecurrentSelector(model_seed)
            load_ippo_checkpoint(
                Path(selected["path"]),
                replay_model,
                expected_config_sha256=CONFIG_SHA256,
            )
            with RlServerProcess(
                LaunchConfig(
                    port=port,
                    java=java,
                    build_if_missing=False,
                )
            ) as replay_env:
                replay_env.handshake("m9-hard-example-checkpoint-replay")
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
                "M9 hard-example relabel checkpoint replay diverged"
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
        output_dir / "candidate-hard-example-relabel-run.manifest.json",
        manifest,
    )
    _write_json(
        output_dir / "progress.json",
        {
            "schema": (
                "m9_candidate_native_hard_example_relabel_progress_v1"
            ),
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


def compare_replicas(
    first: Path, second: Path, *, output: Path | None = None
) -> dict[str, Any]:
    documents = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (first, second)
    ]
    evidence = [_reproducibility_evidence(item) for item in documents]
    if evidence[0] != evidence[1]:
        raise RuntimeError("M9 hard-example relabel replicas diverged")
    for document, canonical in zip(documents, evidence, strict=True):
        if document.get("canonical_run_sha256") != _canonical_sha256(
            canonical
        ):
            raise ValueError(
                "M9 hard-example relabel run digest is invalid"
            )
    selected = [item.get("selected_checkpoint") for item in documents]
    if (selected[0] is None) != (selected[1] is None):
        raise RuntimeError("M9 hard-example relabel selection diverged")
    if selected[0] is not None:
        for manifest, checkpoint in zip(
            (first, second), selected, strict=True
        ):
            path = repo_root() / checkpoint["path"]
            if sha256_path(path) != checkpoint["file_sha256"]:
                raise ValueError(
                    "M9 hard-example checkpoint integrity failed: "
                    f"{manifest}"
                )
        if (
            selected[0]["checkpoint_content_sha256"]
            != selected[1]["checkpoint_content_sha256"]
        ):
            raise RuntimeError(
                "M9 hard-example checkpoint content diverged"
            )
    result = {
        "schema": (
            "m9_candidate_native_hard_example_relabel_"
            "replica_comparison_v1"
        ),
        "construction_passed": bool(
            documents[0].get("construction_passed")
        ),
        "canonical_full_run_sha256": _canonical_sha256(evidence[0]),
        "selected_checkpoint_content_sha256": (
            selected[0].get("checkpoint_content_sha256")
            if selected[0] is not None
            else None
        ),
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
        "--config",
        type=Path,
        default=root
        / "configs/training/m9-candidate-native-hard-example-relabel-v1.json",
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
                *args.compare_runs,
                output=args.comparison_output,
            )
            print(
                "M9 HARD-EXAMPLE REPLICAS OK "
                f"construction={result['construction_passed']}"
            )
            return 0 if result["construction_passed"] else 2
        if args.output_dir is None or args.preflight is None:
            parser.error("--output-dir and --preflight are required")
        manifest = train(
            args.config.resolve(),
            args.output_dir.resolve(),
            args.preflight.resolve(),
            java=args.java,
            port=args.port,
        )
    except Exception as error:
        print(f"M9 HARD-EXAMPLE FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "M9 HARD-EXAMPLE COMPLETE "
        f"construction={manifest['construction_passed']} "
        f"selected={manifest.get('selected_checkpoint', {}).get('update')}"
    )
    return 0 if manifest["construction_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
