"""Governed contiguous truncated-BPTT teacher relabeling for M9."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
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
    SOURCE_CONFIG_RELATIVE as DISTILL_CONFIG_RELATIVE,
    _aggregate,
    _git_commit,
    _reproducibility_evidence,
    _selection_key,
    teacher_labels,
)
from mindustry_agents.training.ippo import (
    IPPO_MODEL_ARCHITECTURE,
    SharedRecurrentSelector,
    SharedSeatState,
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
from mindustry_agents.training.ippo_ppo import (
    IPPOEpisodeRollout,
    IPPOTransition,
    ippo_sequence_windows,
    sha256_path,
)


CONFIG_SHA256 = (
    "b7e17a6e74b6d18a261d7d4845dcff8d808ffef830641e0c4fb21dbe327233d1"
)
PROTOCOL_SHA256 = (
    "b79f6da9c24863d0765e127678f45471ca78fe9a215a26fe0fa15105951a261e"
)
SOURCE_CONFIG_SHA256 = (
    "7fadf9ae9130775fffebe52b86407dfeafaf47ea5e1383524818a6d0012d72d4"
)
SOURCE_RESULT_SHA256 = (
    "ebea0b741abbf2b7e3d995af1f87d7528ddee08d94089db4f837f40c730e60ee"
)
SOURCE_DIAGNOSTIC_SHA256 = (
    "af4725e0fa034761d3cb69e46cfc2c05014724e8c6533544cfaccad416d2c7df"
)
SOURCE_MANIFEST_SHA256 = (
    "f34c50a024f05d6084a8661fb627fa8c3c5cd223dc45bd03273258877f489952"
)
SOURCE_CANONICAL_RUN_SHA256 = (
    "1cf33117526a04c8053bc66ce786945964a88e1d32a1de3227bd2af042524c81"
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
TRAIN_SET_SHA256 = (
    "2e4d5b853ba9c8a6b568b107537756e257d3c19205af71c0445ea5ea730088c4"
)
DEV_SET_SHA256 = (
    "5d834a1ea8db828e05f2e7343a88cea1ba49721bd1570d1f435ca73778fb6b83"
)
SEQUENCE_LENGTH = 16
SEQUENCES_PER_MINIBATCH = 16


@dataclass(frozen=True)
class SequenceRelabelEpisode:
    """One student-controlled episode with loss-masked recurrent context."""

    seed: int
    outcome: str
    tick: int
    core_health: float
    transitions: tuple[IPPOTransition, ...]
    eligible_labels: int
    context_transitions: int
    forced_controls: int
    student_teacher_matches: int
    rejected_student_actions: int
    trace_sha256: str


def _expected_learning_contract() -> dict[str, Any]:
    return {
        "schema": "candidate_native_student_state_sequence_relabel_nll_v1",
        "student_controls_environment": True,
        "student_action_mode": "deterministic_argmax",
        "teacher_labels_same_pre_action_student_visited_boundary": True,
        "teacher_action_execution": False,
        "context_transition": "every_alive_student_evaluated_seat_boundary",
        "supervised_transition": (
            "alive_and_no_forced_task_action_and_teacher_action_"
            "authoritatively_legal"
        ),
        "forced_controls": (
            "student_forced_action_executed_and_retained_as_loss_masked_"
            "recurrent_context"
        ),
        "dataset": "current_update_student_visited_boundaries_only",
        "sequence_length": SEQUENCE_LENGTH,
        "sequences_per_minibatch": SEQUENCES_PER_MINIBATCH,
        "window_order": (
            "episode_schedule_order_then_agent_id_then_boundary_order"
        ),
        "window_split": (
            "episode_or_authoritative_seat_reset_or_16_transitions"
        ),
        "window_overlap": False,
        "window_filter": (
            "retain_only_windows_with_at_least_one_supervised_transition"
        ),
        "initial_hidden": (
            "stored_student_rollout_hidden_at_window_start_detached"
        ),
        "hidden_output": (
            "recomputed_private_next_boundary_state_within_window"
        ),
        "padding": (
            "right_padded_and_excluded_from_context_and_loss_after_last_"
            "real_step"
        ),
        "loss": (
            "sum_teacher_action_negative_log_probability_divided_by_"
            "supervised_transitions_per_minibatch"
        ),
        "gradient_scope": (
            "supervised_loss_through_preceding_real_context_within_same_"
            "window_only"
        ),
        "cross_window_state": False,
        "cross_episode_state": False,
        "cross_agent_state": False,
        "critic_loss": False,
        "ppo_loss": False,
        "entropy_loss": False,
        "example_weighting": False,
        "ema": False,
        "replay": False,
        "extra_rng": False,
    }


def load_sequence_relabel_config(path: Path) -> dict[str, Any]:
    """Load ADR-0127's exact sequence-coherence construction."""

    if sha256_path(path) != CONFIG_SHA256:
        raise ValueError("M9 sequence relabel config digest drifted")
    config = json.loads(path.read_text(encoding="utf-8"))
    if (
        config.get("schema")
        != "m9_candidate_native_sequence_relabel_config_v1"
        or config.get("candidate_version")
        != "m9-candidate-native-sequence-relabel-v1"
        or config.get("model_architecture") != IPPO_MODEL_ARCHITECTURE
        or config.get("confirmation_seed_set") is not None
        or config.get("held_out_seed_set") is not None
        or int(config.get("torch_threads", 0)) != 1
        or int(config.get("continuation_updates", 0)) != 32
        or int(config.get("episodes_per_update", 0)) != 64
        or int(config.get("minibatch_size", 0))
        != SEQUENCE_LENGTH * SEQUENCES_PER_MINIBATCH
        or str(config.get("train_seed_set_sha256")) != TRAIN_SET_SHA256
        or str(config.get("dev_seed_set_sha256")) != DEV_SET_SHA256
        or config.get("sequence_relabeling")
        != _expected_learning_contract()
    ):
        raise ValueError("M9 sequence relabel config contract drifted")
    return config


def _load_protocol(
    root: Path, config: dict[str, Any]
) -> dict[str, Any]:
    path = root / str(config["public_evaluation_protocol"])
    if sha256_path(path) != PROTOCOL_SHA256:
        raise ValueError("M9 sequence relabel protocol digest drifted")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    source = protocol.get("source_checkpoint", {})
    diagnostic = protocol.get("source_diagnostic", {})
    isolated = protocol.get("isolated_learning_change", {})
    replica = protocol.get("replica_policy", {})
    authority = protocol.get("downstream_authority", {})
    if (
        protocol.get("schema")
        != "m9_candidate_native_sequence_relabel_public_protocol_v1"
        or protocol.get("candidate_version") != config["candidate_version"]
        or protocol.get("data_classification")
        != "public_train_and_dev_only"
        or protocol.get("config_sha256") != CONFIG_SHA256
        or protocol.get("seed_set") != config["dev_seed_set"]
        or protocol.get("seed_set_sha256") != DEV_SET_SHA256
        or source.get("content_sha256")
        != SOURCE_CHECKPOINT_CONTENT_SHA256
        or source.get("model_state_sha256") != SOURCE_MODEL_SHA256
        or source.get("optimizer_state_sha256")
        != SOURCE_OPTIMIZER_SHA256
        or source.get("construction_passed") is not False
        or source.get("selected_or_promoted") is not False
        or source.get("repaired") is not False
        or diagnostic.get("sha256") != SOURCE_DIAGNOSTIC_SHA256
        or diagnostic.get("accepted_signal") != "low_correction_signal"
        or diagnostic.get("correct_all_wins") != [9, 9]
        or isolated.get("name")
        != "contiguous_truncated_bptt_teacher_nll"
        or isolated.get("sequence_length") != SEQUENCE_LENGTH
        or isolated.get("sequences_per_minibatch")
        != SEQUENCES_PER_MINIBATCH
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
        or any(
            authority.get(key) is not False
            for key in (
                "may_select_or_repair_source_checkpoint",
                "may_change_planner_features_masks_or_candidates",
                "may_add_ema_or_replay_or_change_learning_rate",
                "may_use_reward_or_ppo_or_mappo",
                "may_promote",
                "may_access_confirmation",
                "may_access_held_out",
                "may_authorize_human_session",
            )
        )
    ):
        raise ValueError("M9 sequence relabel public authority drifted")
    return protocol


def _load_source(
    root: Path, config: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    source = config["source_checkpoint"]
    result_path = root / str(source["source_result"])
    diagnostic_path = root / str(config["source_diagnostic"]["result"])
    manifest_path = root / str(source["source_manifest"])
    checkpoint_path = root / str(source["path"])
    source_config_path = root / str(source["source_config"])
    if (
        source.get("source_config_sha256") != SOURCE_CONFIG_SHA256
        or sha256_path(source_config_path) != SOURCE_CONFIG_SHA256
        or source.get("source_result_sha256") != SOURCE_RESULT_SHA256
        or sha256_path(result_path) != SOURCE_RESULT_SHA256
        or source.get("source_manifest_sha256")
        != SOURCE_MANIFEST_SHA256
        or sha256_path(manifest_path) != SOURCE_MANIFEST_SHA256
        or source.get("source_canonical_run_sha256")
        != SOURCE_CANONICAL_RUN_SHA256
        or source.get("file_sha256") != SOURCE_CHECKPOINT_FILE_SHA256
        or sha256_path(checkpoint_path) != SOURCE_CHECKPOINT_FILE_SHA256
        or source.get("content_sha256")
        != SOURCE_CHECKPOINT_CONTENT_SHA256
        or source.get("model_state_sha256") != SOURCE_MODEL_SHA256
        or source.get("optimizer_state_sha256")
        != SOURCE_OPTIMIZER_SHA256
        or config["source_diagnostic"].get("sha256")
        != SOURCE_DIAGNOSTIC_SHA256
        or sha256_path(diagnostic_path) != SOURCE_DIAGNOSTIC_SHA256
        or source.get("load_model_state") is not True
        or source.get("load_optimizer_state") is not True
        or source.get("construction_passed") is not False
        or source.get("selected_or_promoted") is not False
        or source.get("repaired") is not False
    ):
        raise ValueError("M9 sequence relabel source identity drifted")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    final = result.get("replica_a", {}).get("final_public_dev", {})
    if (
        result.get("replica_a", {}).get("construction_passed") is not False
        or result.get("replica_a", {}).get("selected_checkpoint") is not None
        or result.get("replica_b_authorized") is not False
        or result.get("confirmation_or_held_out_access") is not False
        or final.get("checkpoint_content_sha256")
        != SOURCE_CHECKPOINT_CONTENT_SHA256
        or diagnostic.get("classification", {}).get(
            "low_correction_signal"
        )
        is not True
        or diagnostic.get("successor_training_authorized") is not False
        or diagnostic.get("confirmation_or_held_out_access") is not False
        or manifest.get("construction_passed") is not False
        or manifest.get("selected_checkpoint") is not None
        or manifest.get("canonical_run_sha256")
        != SOURCE_CANONICAL_RUN_SHA256
    ):
        raise ValueError("M9 sequence relabel source evidence is invalid")
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
        expected_config_sha256=SOURCE_CONFIG_SHA256,
    )
    if (
        int(payload["update"]) != 64
        or payload["checkpoint_content_sha256"]
        != SOURCE_CHECKPOINT_CONTENT_SHA256
        or payload["model_state_sha256"] != SOURCE_MODEL_SHA256
        or payload["optimizer_state_sha256"]
        != SOURCE_OPTIMIZER_SHA256
        or model_state_digest(model) != SOURCE_MODEL_SHA256
    ):
        raise ValueError("M9 sequence relabel loaded source drifted")
    return model, optimizer, payload


def _student_sequence_episode(
    env: RlServerProcess,
    model: SharedRecurrentSelector,
    config: dict[str, Any],
    *,
    seed: int,
) -> SequenceRelabelEpisode:
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
    labels_seen = 0
    matches = 0
    forced = 0
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
            not item.get("accepted", False)
            for item in response.action_results
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
        for agent_id in decision.evaluation_order:
            features = decision.features[agent_id]
            supervised = agent_id in labels
            action = (
                int(labels[agent_id])
                if supervised
                else int(decision.action_indices[agent_id])
            )
            if supervised:
                labels_seen += 1
                matches += (
                    int(decision.action_indices[agent_id]) == action
                )
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
                    action=action,
                    old_log_prob=0.0,
                    old_value=decision.old_values[agent_id],
                    team_reward=0.0,
                    individual_reward=0.0,
                    advanced_ticks=advanced,
                    done=done,
                    policy_loss_mask=supervised,
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

    if outcome == "running" or not transitions or labels_seen <= 0:
        raise RuntimeError("M9 sequence relabel episode was incomplete")
    return SequenceRelabelEpisode(
        seed=seed,
        outcome=outcome,
        tick=tick,
        core_health=float(observations[0]["team"]["core_health"]),
        transitions=tuple(transitions),
        eligible_labels=labels_seen,
        context_transitions=len(transitions) - labels_seen,
        forced_controls=forced,
        student_teacher_matches=matches,
        rejected_student_actions=rejected,
        trace_sha256=_canonical_sha256(trace),
    )


def _flatten_episodes(
    episodes: Sequence[SequenceRelabelEpisode | IPPOEpisodeRollout],
) -> list[IPPOTransition]:
    return [
        transition
        for episode in episodes
        for transition in episode.transitions
    ]


def supervised_sequence_windows(
    episodes: Sequence[SequenceRelabelEpisode | IPPOEpisodeRollout],
    *,
    sequence_length: int,
) -> tuple[
    list[IPPOTransition],
    tuple[tuple[int, ...], ...],
    dict[str, int],
]:
    """Partition context exactly, then omit windows without teacher labels."""

    rollouts = [
        IPPOEpisodeRollout(
            seed=int(episode.seed),
            outcome=str(episode.outcome),
            transitions=tuple(episode.transitions),
        )
        for episode in episodes
    ]
    transitions = _flatten_episodes(rollouts)
    all_windows = ippo_sequence_windows(
        rollouts, sequence_length=sequence_length
    )
    retained = tuple(
        window
        for window in all_windows
        if any(transitions[index].policy_loss_mask for index in window)
    )
    retained_indices = {
        index for window in retained for index in window
    }
    if not retained:
        raise ValueError("M9 sequence relabel update has no supervised windows")
    if any(
        not any(transitions[index].policy_loss_mask for index in window)
        for window in retained
    ):
        raise AssertionError("M9 sequence relabel retained an empty window")
    return (
        transitions,
        retained,
        {
            "all_windows": len(all_windows),
            "retained_windows": len(retained),
            "dropped_zero_label_windows": len(all_windows) - len(retained),
            "retained_transitions": len(retained_indices),
            "dropped_context_transitions": (
                len(transitions) - len(retained_indices)
            ),
        },
    )


def _sequence_minibatch_nll(
    model: SharedRecurrentSelector,
    transitions: Sequence[IPPOTransition],
    windows: Sequence[tuple[int, ...]],
) -> tuple[torch.Tensor, int, int, int]:
    if not windows:
        raise ValueError("M9 sequence relabel minibatch is empty")
    hidden_rows = [
        transitions[window[0]].hidden_input.reshape(1, -1).detach()
        for window in windows
    ]
    nll_values: list[torch.Tensor] = []
    correct = 0
    real = 0
    maximum = max(len(window) for window in windows)
    for step in range(maximum):
        rows = [
            row for row, window in enumerate(windows) if step < len(window)
        ]
        items = [transitions[windows[row][step]] for row in rows]
        candidates = torch.stack([item.candidates for item in items])
        scalars = torch.stack([item.scalars for item in items])
        present = torch.stack([item.candidate_present for item in items])
        masks = torch.stack([item.action_mask for item in items])
        agent_ids = torch.tensor(
            [item.agent_id for item in items], dtype=torch.long
        )
        hidden = torch.cat([hidden_rows[row] for row in rows], dim=0)
        _, logits, _, next_hidden = model(
            candidates,
            scalars,
            present,
            masks,
            agent_ids,
            hidden,
        )
        for position, row in enumerate(rows):
            hidden_rows[row] = next_hidden[position : position + 1]
        for position, item in enumerate(items):
            real += 1
            if not item.policy_loss_mask:
                continue
            if not bool(item.action_mask[item.action]):
                raise ValueError(
                    "M9 sequence relabel teacher label is outside its mask"
                )
            log_probabilities = torch.log_softmax(
                logits[position], dim=-1
            )
            nll_values.append(-log_probabilities[item.action])
            correct += int(
                int(torch.argmax(logits[position]).item()) == item.action
            )
    if not nll_values:
        raise ValueError("M9 sequence relabel minibatch has no teacher labels")
    loss = torch.stack(nll_values).mean()
    return loss, len(nll_values), correct, real


def _sequence_distillation_update_contract(
    model: SharedRecurrentSelector,
    optimizer: torch.optim.Optimizer,
    episodes: Sequence[SequenceRelabelEpisode | IPPOEpisodeRollout],
    config: dict[str, Any],
    generator: torch.Generator,
    *,
    sequence_length: int,
    sequences_per_minibatch: int,
) -> dict[str, float]:
    """Apply the sequence NLL for exact-equivalence and governed probes."""

    if sequence_length < 1 or sequences_per_minibatch < 1:
        raise ValueError("M9 sequence relabel batch dimensions are invalid")
    transitions, windows, window_metrics = supervised_sequence_windows(
        episodes, sequence_length=sequence_length
    )
    labels = sum(item.policy_loss_mask for item in transitions)
    losses = 0.0
    batches = 0
    presentations = 0
    correct = 0
    real_presentations = 0
    padded_slots = 0
    for _ in range(int(config["epochs_per_update"])):
        order = torch.randperm(len(windows), generator=generator)
        for start in range(0, len(windows), sequences_per_minibatch):
            selected = [
                windows[int(index)]
                for index in order[
                    start : start + sequences_per_minibatch
                ]
            ]
            loss, active, batch_correct, real = _sequence_minibatch_nll(
                model, transitions, selected
            )
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(), float(config["max_grad_norm"])
            )
            optimizer.step()
            losses += float(loss.item())
            batches += 1
            presentations += active
            correct += batch_correct
            real_presentations += real
            padded_slots += len(selected) * sequence_length - real
    return {
        "teacher_nll": losses / max(1, batches),
        "batches": float(batches),
        "labels": float(labels),
        "presentations": float(presentations),
        "presentation_top1_accuracy": correct / max(1, presentations),
        "sequence_windows": float(window_metrics["retained_windows"]),
        "all_sequence_windows": float(window_metrics["all_windows"]),
        "dropped_zero_label_windows": float(
            window_metrics["dropped_zero_label_windows"]
        ),
        "retained_context_transitions": float(
            window_metrics["retained_transitions"] - labels
        ),
        "dropped_context_transitions": float(
            window_metrics["dropped_context_transitions"]
        ),
        "real_transition_presentations": float(real_presentations),
        "padded_transition_slots": float(padded_slots),
    }


def sequence_distillation_update(
    model: SharedRecurrentSelector,
    optimizer: torch.optim.Optimizer,
    episodes: Sequence[SequenceRelabelEpisode | IPPOEpisodeRollout],
    config: dict[str, Any],
    generator: torch.Generator,
) -> dict[str, float]:
    """Apply ADR-0127's deterministic contiguous teacher-label NLL."""

    learning = config["sequence_relabeling"]
    sequence_length = int(learning["sequence_length"])
    sequences_per_minibatch = int(learning["sequences_per_minibatch"])
    if (
        sequence_length != SEQUENCE_LENGTH
        or sequences_per_minibatch != SEQUENCES_PER_MINIBATCH
        or sequence_length * sequences_per_minibatch
        != int(config["minibatch_size"])
    ):
        raise ValueError("M9 sequence relabel minibatch contract drifted")
    return _sequence_distillation_update_contract(
        model,
        optimizer,
        episodes,
        config,
        generator,
        sequence_length=sequence_length,
        sequences_per_minibatch=sequences_per_minibatch,
    )


def validate_preflight(
    path: Path, root: Path, config: dict[str, Any]
) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    if (
        result.get("schema")
        != "m9_candidate_native_sequence_relabel_preflight_v1"
        or result.get("passed") is not True
        or result.get("implementation_commit") != _git_commit(root)
        or result.get("config_sha256") != CONFIG_SHA256
        or result.get("protocol_sha256") != PROTOCOL_SHA256
        or result.get("confirmation_or_held_out_access") is not False
    ):
        raise ValueError("M9 sequence relabel preflight is invalid")
    return result


def train(
    config_path: Path,
    output_dir: Path,
    preflight_path: Path,
    *,
    java: str,
    port: int,
) -> dict[str, Any]:
    """Run one non-resumable ADR-0127 continuation replica."""

    root = repo_root()
    config = load_sequence_relabel_config(config_path)
    _load_protocol(root, config)
    source_result, source_diagnostic, _ = _load_source(root, config)
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
        raise ValueError("M9 sequence relabel seed-set digest drifted")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("M9 sequence relabel output directory is not empty")
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
        env.handshake("m9-candidate-native-sequence-relabel-v1")
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
                    _student_sequence_episode(
                        env, model, config, seed=int(seed)
                    )
                )
                if index % 8 == 0:
                    print(
                        "M9 SEQUENCE TRAIN "
                        f"update={continuation_update}/32 "
                        f"episode={index}/64",
                        flush=True,
                    )
            labels = sum(
                episode.eligible_labels for episode in episodes
            )
            model.train()
            metrics = sequence_distillation_update(
                model, optimizer, episodes, config, generator
            )
            update_row = {
                "continuation_update": continuation_update,
                "lineage_update": 64 + continuation_update,
                **metrics,
                "student_wins": sum(
                    episode.outcome == "win" for episode in episodes
                ),
                "student_teacher_top1_before_update": sum(
                    episode.student_teacher_matches
                    for episode in episodes
                )
                / max(1, labels),
                "collected_context_transitions": sum(
                    episode.context_transitions for episode in episodes
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
            }
            updates.append(update_row)
            lineage_update = 64 + continuation_update
            checkpoint_path = (
                output_dir
                / f"candidate-sequence-relabel-update-{lineage_update}.pt"
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
                    "schema": (
                        "m9_candidate_native_sequence_relabel_progress_v1"
                    ),
                    "continuation_update": continuation_update,
                    "train_episodes": continuation_update * 64,
                    "latest_dev": row,
                    "complete": False,
                },
            )
            print(
                "M9 SEQUENCE DEV "
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
        "schema": "m9_candidate_native_sequence_relabel_run_v1",
        "implementation_commit": _git_commit(root),
        "config_sha256": CONFIG_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_result_sha256": SOURCE_RESULT_SHA256,
        "source_diagnostic_sha256": SOURCE_DIAGNOSTIC_SHA256,
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
                replay_env.handshake("m9-sequence-checkpoint-replay")
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
                "M9 sequence relabel checkpoint replay diverged"
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
        output_dir / "candidate-sequence-relabel-run.manifest.json",
        manifest,
    )
    _write_json(
        output_dir / "progress.json",
        {
            "schema": "m9_candidate_native_sequence_relabel_progress_v1",
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
        raise RuntimeError("M9 sequence relabel replicas diverged")
    for document, canonical in zip(documents, evidence, strict=True):
        if document.get("canonical_run_sha256") != _canonical_sha256(
            canonical
        ):
            raise ValueError("M9 sequence relabel run digest is invalid")
    selected = [item.get("selected_checkpoint") for item in documents]
    if (selected[0] is None) != (selected[1] is None):
        raise RuntimeError("M9 sequence relabel selection diverged")
    if selected[0] is not None:
        for manifest, checkpoint in zip(
            (first, second), selected, strict=True
        ):
            path = repo_root() / checkpoint["path"]
            if sha256_path(path) != checkpoint["file_sha256"]:
                raise ValueError(
                    "M9 sequence checkpoint integrity failed: "
                    f"{manifest}"
                )
        if (
            selected[0]["checkpoint_content_sha256"]
            != selected[1]["checkpoint_content_sha256"]
        ):
            raise RuntimeError("M9 sequence checkpoint content diverged")
    result = {
        "schema": (
            "m9_candidate_native_sequence_relabel_"
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
        / "configs/training/m9-candidate-native-sequence-relabel-v1.json",
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
                "M9 SEQUENCE REPLICAS OK "
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
        print(f"M9 SEQUENCE FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "M9 SEQUENCE COMPLETE "
        f"construction={manifest['construction_passed']} "
        f"selected={manifest.get('selected_checkpoint', {}).get('update')}"
    )
    return 0 if manifest["construction_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
