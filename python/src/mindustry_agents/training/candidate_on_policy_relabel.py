"""Governed student-state teacher relabeling construction for M9."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any, Sequence

import torch

from mindustry_agents.policies import CandidateNativePlannerV11
from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.training.candidate_distill import (
    CONFIG_SHA256 as SOURCE_CONFIG_SHA256,
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
from mindustry_agents.training.ippo import (
    IPPO_MODEL_ARCHITECTURE,
    SharedRecurrentSelector,
    SharedSeatState,
    _action_index,
    canonical_teacher_bundle,
    commit_all_seat_boundary,
    decide_all_seats,
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
    "7fadf9ae9130775fffebe52b86407dfeafaf47ea5e1383524818a6d0012d72d4"
)
PROTOCOL_SHA256 = (
    "548ba5fe1478c6cdfb40fc2c2c390a9af57f2cbd1e14d9fb9f6c620ffac38d31"
)
SOURCE_RESULT_SHA256 = (
    "47ced62d5b7e3c15c980415bc3c05974bfacfd1ccbfd7e2af6c7f474486af590"
)
DIAGNOSTIC_RESULT_SHA256 = (
    "7909e6a2013258d288c5b951748947818f05188b355851271fed5bdfcdfdede9"
)
TRAIN_SET_SHA256 = (
    "2e4d5b853ba9c8a6b568b107537756e257d3c19205af71c0445ea5ea730088c4"
)
DEV_SET_SHA256 = (
    "5d834a1ea8db828e05f2e7343a88cea1ba49721bd1570d1f435ca73778fb6b83"
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
SOURCE_MANIFEST_SHA256 = (
    "cd88deac884ee8513857e979d3eeea33e5d4ea925d220cdef455edb1b992c3c0"
)
SOURCE_MANIFEST_RELATIVE = (
    "runs/m9-candidate-distill-a/candidate-distill-run.manifest.json"
)
SOURCE_CONFIG_RELATIVE = (
    "configs/training/m9-candidate-native-distill-v1.json"
)


@dataclass(frozen=True)
class RelabelEpisode:
    seed: int
    outcome: str
    tick: int
    core_health: float
    transitions: tuple[IPPOTransition, ...]
    eligible_labels: int
    forced_controls: int
    student_teacher_matches: int
    rejected_student_actions: int
    trace_sha256: str


def _git_commit(root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()


def load_on_policy_relabel_config(path: Path) -> dict[str, Any]:
    """Load ADR-0117's exact continuation construction."""

    if sha256_path(path) != CONFIG_SHA256:
        raise ValueError("M9 on-policy relabel config digest drifted")
    config = json.loads(path.read_text(encoding="utf-8"))
    if (
        config.get("schema")
        != "m9_candidate_native_on_policy_relabel_config_v1"
        or config.get("candidate_version")
        != "m9-candidate-native-on-policy-relabel-v1"
        or config.get("model_architecture") != IPPO_MODEL_ARCHITECTURE
        or config.get("confirmation_seed_set") is not None
        or config.get("held_out_seed_set") is not None
        or int(config.get("torch_threads", 0)) != 1
        or int(config.get("continuation_updates", 0)) != 32
        or int(config.get("episodes_per_update", 0)) != 64
        or str(config.get("train_seed_set_sha256")) != TRAIN_SET_SHA256
        or str(config.get("dev_seed_set_sha256")) != DEV_SET_SHA256
    ):
        raise ValueError("M9 on-policy relabel config contract drifted")
    expected = {
        "schema": "candidate_native_student_state_relabel_nll_v1",
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
        "loss": "mean_negative_log_probability_of_teacher_action",
        "dataset": "current_update_student_visited_boundaries_only",
        "hidden_input": (
            "current_student_private_hidden_at_boundary_detached"
        ),
        "hidden_state_reset": "episode_reset_or_authoritative_seat_death",
        "cross_agent_state": False,
        "critic_loss": False,
        "ppo_loss": False,
        "entropy_loss": False,
        "extra_rng": False,
    }
    if config.get("on_policy_relabeling") != expected:
        raise ValueError("M9 on-policy relabel learning contract drifted")
    return config


def _load_protocol(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    path = root / str(config["public_evaluation_protocol"])
    if sha256_path(path) != PROTOCOL_SHA256:
        raise ValueError("M9 on-policy relabel protocol digest drifted")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    authority = protocol.get("downstream_authority", {})
    if (
        protocol.get("schema")
        != "m9_candidate_native_on_policy_relabel_public_protocol_v1"
        or protocol.get("seed_set") != config["dev_seed_set"]
        or protocol.get("seed_set_sha256") != DEV_SET_SHA256
        or protocol.get("source_diagnostic", {}).get("sha256")
        != DIAGNOSTIC_RESULT_SHA256
        or protocol.get("source_diagnostic", {}).get("accepted_signal")
        != "closed_loop_shift_signal"
        or any(
            authority.get(key) is not False
            for key in (
                "may_promote",
                "may_authorize_mappo",
                "may_access_confirmation",
                "may_access_held_out",
                "may_authorize_human_session",
            )
        )
    ):
        raise ValueError("M9 on-policy relabel public authority drifted")
    return protocol


def _load_source(
    root: Path, config: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    source = config["source_checkpoint"]
    result_path = root / str(source["source_result"])
    diagnostic_path = root / str(source["diagnostic_result"])
    checkpoint_path = root / str(source["path"])
    manifest_path = root / SOURCE_MANIFEST_RELATIVE
    if (
        source.get("source_result_sha256") != SOURCE_RESULT_SHA256
        or sha256_path(result_path) != SOURCE_RESULT_SHA256
        or source.get("diagnostic_result_sha256")
        != DIAGNOSTIC_RESULT_SHA256
        or sha256_path(diagnostic_path) != DIAGNOSTIC_RESULT_SHA256
        or source.get("file_sha256") != SOURCE_CHECKPOINT_FILE_SHA256
        or sha256_path(checkpoint_path) != SOURCE_CHECKPOINT_FILE_SHA256
        or sha256_path(manifest_path) != SOURCE_MANIFEST_SHA256
        or source.get("content_sha256")
        != SOURCE_CHECKPOINT_CONTENT_SHA256
        or source.get("model_state_sha256") != SOURCE_MODEL_SHA256
        or source.get("optimizer_state_sha256")
        != SOURCE_OPTIMIZER_SHA256
        or source.get("source_config_sha256") != SOURCE_CONFIG_SHA256
        or source.get("load_model_state") is not True
        or source.get("load_optimizer_state") is not True
        or source.get("selected_or_promoted") is not False
    ):
        raise ValueError("M9 on-policy relabel source identity drifted")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        result.get("replica_a", {}).get("construction_passed") is not False
        or result.get("replica_a", {}).get("selected_checkpoint") is not None
        or result.get("replica_b_authorized") is not False
        or result.get("confirmation_or_held_out_access") is not False
        or diagnostic.get("classification", {}).get(
            "closed_loop_shift_signal"
        )
        is not True
        or diagnostic.get("classification", {}).get(
            "successor_training_authorized"
        )
        is not False
        or diagnostic.get("confirmation_or_held_out_access") is not False
        or manifest.get("construction_passed") is not False
        or manifest.get("canonical_run_sha256")
        != result["replica_a"]["canonical_run_sha256"]
    ):
        raise ValueError("M9 on-policy relabel source evidence is invalid")
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
        root / SOURCE_CONFIG_RELATIVE
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
        or payload["model_state_sha256"] != SOURCE_MODEL_SHA256
        or payload["optimizer_state_sha256"] != SOURCE_OPTIMIZER_SHA256
        or model_state_digest(model) != SOURCE_MODEL_SHA256
    ):
        raise ValueError("M9 on-policy relabel loaded source drifted")
    return model, optimizer, payload


def teacher_labels(
    decision: Any,
    teacher: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> dict[int, int]:
    """Return only actor-authoritative planner labels at this boundary."""

    canonical = canonical_teacher_bundle(teacher, observations)
    labels = {}
    for agent_id in decision.evaluation_order:
        features = decision.features[agent_id]
        action = canonical[agent_id]
        action_type = action.get("task_action", {}).get("type")
        label = _action_index(
            action, observations[agent_id].get("task_candidates", [])
        )
        if (
            features.forced_task_action is None
            and action_type
            in {
                "SELECT_CANDIDATE_TASK",
                "CONTINUE_CURRENT_TASK",
                "WAIT",
            }
            and bool(features.action_mask[label])
        ):
            labels[agent_id] = label
    return labels


def _student_episode(
    env: RlServerProcess,
    model: SharedRecurrentSelector,
    config: dict[str, Any],
    *,
    seed: int,
) -> RelabelEpisode:
    reset = env.reset(
        seed,
        scenario_id=str(config["scenario_id"]),
        scenario_version=int(config["scenario_version"]),
        agent_count=3,
    )
    planner = CandidateNativePlannerV11()
    state = SharedSeatState.fresh()
    observations = reset.initial_observations
    masks = reset.action_masks
    metadata = reset.metadata
    board: list[dict[str, Any]] = []
    reasons: list[str] = []
    tick = reset.tick
    outcome = reset.outcome
    transitions: list[IPPOTransition] = []
    forced = 0
    matches = 0
    rejected = 0
    trace: list[dict[str, Any]] = []

    while outcome == "running" and tick < int(metadata["tick_cap"]):
        teacher = planner.actions(observations, masks, board)
        decision = decide_all_seats(
            model,
            state,
            observations,
            masks,
            metadata,
            task_board=board,
            boundary_reasons=reasons,
            evaluation=True,
        )
        labels = teacher_labels(decision, teacher, observations)
        forced += len(decision.evaluation_order) - len(labels)
        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, int(metadata["tick_cap"]) - tick),
            agent_actions=decision.agent_actions,
            stop_on_decision_event=True,
        )
        rejected += sum(
            not result.get("accepted", False)
            for result in response.action_results
        )
        commit_all_seat_boundary(
            state,
            decision,
            response.action_results,
            observations,
            tick=tick,
        )
        advanced = int(
            response.decision_boundary.get(
                "advanced_ticks", response.tick - tick
            )
        )
        done = response.outcome != "running"
        for agent_id, label in labels.items():
            features = decision.features[agent_id]
            matches += decision.action_indices[agent_id] == label
            transitions.append(
                IPPOTransition(
                    agent_id=agent_id,
                    candidates=torch.tensor(
                        features.candidates, dtype=torch.float32
                    ),
                    scalars=torch.tensor(
                        features.scalars, dtype=torch.float32
                    ),
                    candidate_present=torch.tensor(
                        features.candidate_present, dtype=torch.bool
                    ),
                    action_mask=torch.tensor(
                        features.action_mask, dtype=torch.bool
                    ),
                    hidden_input=decision.hidden_inputs[agent_id],
                    action=label,
                    old_log_prob=0.0,
                    old_value=decision.old_values[agent_id],
                    team_reward=0.0,
                    individual_reward=0.0,
                    advanced_ticks=advanced,
                    done=done,
                    policy_loss_mask=True,
                    recurrent_reset=decision.recurrent_resets[agent_id],
                )
            )
        trace.append(
            {
                "tick": tick,
                "next_tick": response.tick,
                "student_actions": decision.agent_actions,
                "teacher_actions": canonical_teacher_bundle(
                    teacher, observations
                ),
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

    if outcome == "running" or not transitions:
        raise RuntimeError("M9 on-policy relabel episode was incomplete")
    return RelabelEpisode(
        seed=seed,
        outcome=outcome,
        tick=tick,
        core_health=float(observations[0]["team"]["core_health"]),
        transitions=tuple(transitions),
        eligible_labels=len(transitions),
        forced_controls=forced,
        student_teacher_matches=matches,
        rejected_student_actions=rejected,
        trace_sha256=_canonical_sha256(trace),
    )


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


def _selection_key(row: dict[str, Any]) -> tuple[float, ...]:
    return (
        float(row["wins"]),
        float(row["mean_core_health"]),
        -float(row["mean_team_idle_fraction"]),
        -float(row["continuation_update"]),
    )


def validate_preflight(
    path: Path, root: Path, config: dict[str, Any]
) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    if (
        result.get("schema")
        != "m9_candidate_native_on_policy_relabel_preflight_v1"
        or result.get("passed") is not True
        or result.get("implementation_commit") != _git_commit(root)
        or result.get("config_sha256") != CONFIG_SHA256
        or result.get("protocol_sha256") != PROTOCOL_SHA256
        or result.get("confirmation_or_held_out_access") is not False
    ):
        raise ValueError("M9 on-policy relabel preflight is invalid")
    return result


def _reproducibility_evidence(
    manifest: dict[str, Any],
) -> dict[str, Any]:
    evidence = copy.deepcopy(manifest)
    evidence.pop("preflight_sha256", None)
    evidence.pop("canonical_run_sha256", None)
    selected = evidence.get("selected_checkpoint")
    if selected is not None:
        selected.pop("path", None)
    return evidence


def train(
    config_path: Path,
    output_dir: Path,
    preflight_path: Path,
    *,
    java: str,
    port: int,
) -> dict[str, Any]:
    """Run one non-resumable ADR-0117 continuation replica."""

    root = repo_root()
    config = load_on_policy_relabel_config(config_path)
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
        raise ValueError("M9 on-policy relabel seed-set digest drifted")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("M9 on-policy relabel output directory is not empty")
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
        env.handshake("m9-candidate-native-on-policy-relabel-v1")
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
                        "M9 RELABEL TRAIN "
                        f"update={continuation_update}/32 "
                        f"episode={index}/64",
                        flush=True,
                    )
            labels = [
                transition
                for episode in episodes
                for transition in episode.transitions
            ]
            model.train()
            metrics = distillation_update(
                model, optimizer, labels, config, generator
            )
            update_row = {
                "continuation_update": continuation_update,
                "lineage_update": 32 + continuation_update,
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
                "student_trace_digest": _canonical_sha256(
                    [episode.trace_sha256 for episode in episodes]
                ),
            }
            updates.append(update_row)
            lineage_update = 32 + continuation_update
            checkpoint_path = (
                output_dir
                / f"candidate-on-policy-relabel-update-{lineage_update}.pt"
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
                        "m9_candidate_native_on_policy_relabel_progress_v1"
                    ),
                    "continuation_update": continuation_update,
                    "train_episodes": continuation_update * 64,
                    "latest_dev": row,
                    "complete": False,
                },
            )
            print(
                "M9 RELABEL DEV "
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
        "schema": "m9_candidate_native_on_policy_relabel_run_v1",
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
                replay_env.handshake("m9-relabel-checkpoint-replay")
                replay_summaries.append(
                    _evaluate_episode(
                        replay_env,
                        replay_model,
                        config,
                        seed=dev_seeds[0],
                    )
                )
        if replay_summaries[0] != replay_summaries[1]:
            raise RuntimeError("M9 relabel checkpoint replay diverged")
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
        output_dir / "candidate-on-policy-relabel-run.manifest.json",
        manifest,
    )
    _write_json(
        output_dir / "progress.json",
        {
            "schema": "m9_candidate_native_on_policy_relabel_progress_v1",
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
        raise RuntimeError("M9 on-policy relabel replicas diverged")
    for document, canonical in zip(documents, evidence, strict=True):
        if document.get("canonical_run_sha256") != _canonical_sha256(
            canonical
        ):
            raise ValueError("M9 on-policy relabel run digest is invalid")
    selected = [item.get("selected_checkpoint") for item in documents]
    if (selected[0] is None) != (selected[1] is None):
        raise RuntimeError("M9 on-policy relabel selection diverged")
    if selected[0] is not None:
        for manifest, checkpoint in zip(
            (first, second), selected, strict=True
        ):
            path = repo_root() / checkpoint["path"]
            if sha256_path(path) != checkpoint["file_sha256"]:
                raise ValueError(
                    f"M9 relabel checkpoint integrity failed: {manifest}"
                )
        if (
            selected[0]["checkpoint_content_sha256"]
            != selected[1]["checkpoint_content_sha256"]
        ):
            raise RuntimeError("M9 relabel checkpoint content diverged")
    result = {
        "schema": (
            "m9_candidate_native_on_policy_relabel_replica_comparison_v1"
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
        / "configs/training/m9-candidate-native-on-policy-relabel-v1.json",
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
                "M9 RELABEL REPLICAS OK "
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
        print(f"M9 RELABEL FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "M9 RELABEL COMPLETE "
        f"construction={manifest['construction_passed']} "
        f"selected={manifest.get('selected_checkpoint', {}).get('update')}"
    )
    return 0 if manifest["construction_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
