"""Run ADR-0125's public-only planner-correction causal diagnostic."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import replace
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
    _canonical_sha256,
    _configure_torch,
    _git_commit,
    _load_seed_set,
    _write_json,
    load_distillation_config,
)
from mindustry_agents.training.candidate_distill_agreement import action_task
from mindustry_agents.training.candidate_on_policy_relabel import (
    DEV_MAXIMUM,
    DEV_MINIMUM,
    DEV_SET_SHA256,
    teacher_labels,
)
from mindustry_agents.training.ippo import (
    AllSeatDecision,
    SharedRecurrentSelector,
    SharedSeatState,
    _action_index,
    _feature_tensors,
    canonical_teacher_bundle,
    commit_all_seat_boundary,
    decide_all_seats,
    model_state_digest,
)
from mindustry_agents.training.ippo_artifacts import load_ippo_checkpoint
from mindustry_agents.training.ippo_ppo import sha256_path


PROTOCOL_RELATIVE = (
    "configs/evaluation/m9-planner-correction-causality-v1-protocol.json"
)
PROTOCOL_SHA256 = (
    "aee96892e4ceb131da7743afabc2d41fbb08be41e53b9b79c22158af3530cad6"
)
CONFIG_PATHS = {
    64: "configs/training/m9-candidate-native-on-policy-relabel-v1.json",
    96: "configs/training/m9-candidate-native-hard-example-relabel-v1.json",
}
MODES = ("baseline", "correct_first", "correct_all")


def _expected_authority() -> dict[str, bool]:
    return {
        "may_select_or_repair_checkpoint": False,
        "may_train_or_modify_model_or_optimizer": False,
        "may_change_planner_features_masks_or_candidates": False,
        "may_sweep_correction_strength_or_first_k": False,
        "may_use_reward_or_ppo_or_mappo": False,
        "may_precommit_successor_after_valid_result": True,
        "may_promote": False,
        "may_access_confirmation": False,
        "may_access_held_out": False,
        "may_authorize_human_session": False,
    }


def validate_inputs(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[int]]:
    """Fail closed over every prospective public source before a JVM starts."""

    protocol_path = root / PROTOCOL_RELATIVE
    if sha256_path(protocol_path) != PROTOCOL_SHA256:
        raise ValueError("M9 planner-correction protocol hash drifted")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    execution = protocol.get("execution", {})
    classification = protocol.get("classification", {})
    if (
        protocol.get("schema")
        != "m9_planner_correction_causality_protocol_v1"
        or protocol.get("diagnostic")
        != "m9-planner-correction-causality-v1"
        or protocol.get("data_classification") != "public_dev_only"
        or protocol.get("split") != "dev"
        or protocol.get("seed_set_sha256") != DEV_SET_SHA256
        or protocol.get("teacher_policy")
        != "candidate-native-planner-v11-single-defender"
        or protocol.get("authority") != _expected_authority()
        or execution.get("fresh_jvm_reports") != 2
        or execution.get("terminal_reset_replay") is not True
        or execution.get("exact_report_identity_required") is not True
        or execution.get("student_action_mode") != "deterministic_argmax"
        or execution.get("mode_order") != list(MODES)
        or execution.get("pre_terminal_window_ticks") != 600
        or classification.get("correct_first_role")
        != "descriptive_front_loaded_versus_diffuse_localization_only"
    ):
        raise ValueError("M9 planner-correction authority drifted")
    if [int(item.get("lineage_update", -1)) for item in protocol["checkpoints"]] != [
        64,
        96,
    ]:
        raise ValueError("M9 planner-correction checkpoint order drifted")

    for checkpoint in protocol["checkpoints"]:
        update = int(checkpoint["lineage_update"])
        config_path = root / CONFIG_PATHS[update]
        result_path = root / str(checkpoint["source_result"])
        manifest_path = root / str(checkpoint["source_manifest"])
        checkpoint_path = root / str(checkpoint["path"])
        if (
            sha256_path(config_path) != checkpoint["config_sha256"]
            or sha256_path(result_path) != checkpoint["source_result_sha256"]
            or sha256_path(manifest_path)
            != checkpoint["source_manifest_sha256"]
            or sha256_path(checkpoint_path) != checkpoint["file_sha256"]
        ):
            raise ValueError("M9 planner-correction source identity drifted")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        result = json.loads(result_path.read_text(encoding="utf-8"))
        replica = result.get("replica_a", {})
        final = replica.get("final_public_dev", {})
        if (
            manifest.get("canonical_run_sha256")
            != checkpoint["source_canonical_run_sha256"]
            or replica.get("construction_passed") is not False
            or replica.get("selected_checkpoint") is not None
            or result.get("replica_b_authorized") is not False
            or result.get("confirmation_or_held_out_access") is not False
            or checkpoint.get("construction_passed") is not False
            or checkpoint.get("selected_or_promoted") is not False
            or checkpoint.get("repaired") is not False
            or final.get("checkpoint_content_sha256")
            != checkpoint["content_sha256"]
            or final.get("model_state_sha256")
            != checkpoint["model_state_sha256"]
            or int(final.get("wins", -1))
            != int(checkpoint["autonomous_public_dev_wins"])
            or float(final.get("mean_core_health", -1.0))
            != float(checkpoint["autonomous_public_dev_mean_core_health"])
        ):
            raise ValueError(
                "M9 planner-correction rejected source is invalid"
            )

    source_config = load_distillation_config(
        root / "configs/training/m9-candidate-native-distill-v1.json"
    )
    if (
        source_config["dev_seed_set"] != protocol["seed_set"]
        or source_config["scenario_id"] != protocol["scenario_id"]
        or int(source_config["scenario_version"])
        != int(protocol["scenario_version"])
    ):
        raise ValueError("M9 planner-correction public source drifted")
    dev_set, _ = _load_seed_set(
        root,
        str(protocol["seed_set"]),
        split="dev",
        count=40,
        lower=DEV_MINIMUM,
        upper=DEV_MAXIMUM,
    )
    return protocol, source_config, [int(seed) for seed in dev_set["seeds"]]


def _load_model(
    root: Path,
    checkpoint: dict[str, Any],
    config: dict[str, Any],
) -> SharedRecurrentSelector:
    model = SharedRecurrentSelector(int(config["model_init_seed"]))
    payload = load_ippo_checkpoint(
        root / str(checkpoint["path"]),
        model,
        expected_config_sha256=str(checkpoint["config_sha256"]),
    )
    if (
        int(payload["update"]) != int(checkpoint["lineage_update"])
        or payload["checkpoint_content_sha256"]
        != checkpoint["content_sha256"]
        or model_state_digest(model) != checkpoint["model_state_sha256"]
    ):
        raise ValueError("M9 planner-correction loaded checkpoint drifted")
    model.eval()
    return model


def _semantic_identity(
    index: int,
    observation: dict[str, Any],
) -> dict[str, str] | None:
    if index == 8:
        return None
    if index == 9:
        return {"task_type": "WAIT", "task_id": "", "target": ""}
    candidates = observation.get("task_candidates", [])
    if index < 0 or index >= len(candidates):
        raise ValueError("M9 planner-correction action has no candidate")
    candidate = candidates[index]
    return {
        "task_type": action_task(index, observation),
        "task_id": str(candidate.get("task_id", "")),
        "target": str(candidate.get("target", "")),
    }


def _legal_logit_metrics(
    model: SharedRecurrentSelector,
    decision: AllSeatDecision,
    agent_id: int,
    planner_label: int,
) -> dict[str, float]:
    features = decision.features[agent_id]
    with torch.no_grad():
        _, masked_logits, _, _ = model(
            *_feature_tensors(features),
            torch.tensor([agent_id], dtype=torch.long),
            decision.hidden_inputs[agent_id].reshape(1, -1),
        )
    legal = [
        index
        for index, allowed in enumerate(features.action_mask)
        if bool(allowed)
    ]
    if len(legal) < 2:
        raise RuntimeError(
            "M9 planner-correction needs two legal actions for a margin"
        )
    values = masked_logits[0]
    ordered = sorted(
        (float(values[index].item()), index) for index in legal
    )
    top_value, top_index = ordered[-1]
    second_value = ordered[-2][0]
    student_index = int(decision.action_indices[agent_id])
    if top_index != student_index:
        raise RuntimeError("M9 planner-correction student argmax drifted")
    return {
        "student_top1_minus_top2_legal_logit_margin": (
            top_value - second_value
        ),
        "planner_action_minus_student_action_legal_logit_margin": (
            float(values[planner_label].item())
            - float(values[student_index].item())
        ),
    }


def corrected_decision(
    decision: AllSeatDecision,
    teacher: list[dict[str, Any]],
    labels: dict[int, int],
    observations: list[dict[str, Any]],
) -> AllSeatDecision:
    """Replace the complete actor-authoritative bundle, preserving forced seats."""

    canonical = canonical_teacher_bundle(teacher, observations)
    actions = list(decision.agent_actions)
    indices = dict(decision.action_indices)
    for agent_id, label in labels.items():
        actions[agent_id] = canonical[agent_id]
        indices[agent_id] = int(label)
    return replace(
        decision,
        agent_actions=actions,
        action_indices=indices,
    )


def _accepted_agents(action_results: Sequence[dict[str, Any]]) -> set[int]:
    return {
        int(item["agent_id"])
        for item in action_results
        if item.get("accepted", False)
        and type(item.get("agent_id")) is int
    }


def _paired_exact_binomial_p_value(
    baseline_only_wins: int,
    corrected_only_wins: int,
) -> float:
    """Return the two-sided exact-binomial McNemar p-value."""

    if baseline_only_wins < 0 or corrected_only_wins < 0:
        raise ValueError("paired discordant counts cannot be negative")
    discordant = baseline_only_wins + corrected_only_wins
    if discordant == 0:
        return 1.0
    tail = min(baseline_only_wins, corrected_only_wins)
    probability = sum(
        math.comb(discordant, value) for value in range(tail + 1)
    ) / (2**discordant)
    return min(1.0, 2.0 * probability)


def paired_outcomes(
    baseline: Sequence[dict[str, Any]],
    corrected: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    if len(baseline) != len(corrected) or len(baseline) != 40:
        raise ValueError("M9 planner-correction paired roots drifted")
    counts = {
        "both_win": 0,
        "baseline_only_win": 0,
        "correct_all_only_win": 0,
        "both_loss": 0,
    }
    transitions = []
    for left, right in zip(baseline, corrected, strict=True):
        if int(left["seed"]) != int(right["seed"]):
            raise ValueError("M9 planner-correction paired seed order drifted")
        left_win = left["outcome"] == "win"
        right_win = right["outcome"] == "win"
        if left_win and right_win:
            key = "both_win"
        elif left_win:
            key = "baseline_only_win"
        elif right_win:
            key = "correct_all_only_win"
        else:
            key = "both_loss"
        counts[key] += 1
        transitions.append(
            {
                "seed": int(left["seed"]),
                "baseline_outcome": left["outcome"],
                "correct_all_outcome": right["outcome"],
            }
        )
    return {
        **counts,
        "exact_mcnemar_binomial_p_value": _paired_exact_binomial_p_value(
            counts["baseline_only_win"],
            counts["correct_all_only_win"],
        ),
        "transitions": transitions,
    }


def _episode(
    env: RlServerProcess,
    model: SharedRecurrentSelector,
    config: dict[str, Any],
    *,
    seed: int,
    mode: str,
) -> dict[str, Any]:
    if mode not in MODES:
        raise ValueError("M9 planner-correction mode drifted")
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
    reset_tick = reset.tick
    tick = reset.tick
    state_hash = reset.state_hash
    outcome = reset.outcome
    eligible_boundaries = 0
    eligible_labels = 0
    forced_controls = 0
    disagreement_ticks: list[int] = []
    disagreement_records: list[dict[str, Any]] = []
    correction_records: list[dict[str, Any]] = []
    corrected_once = False
    task_switches = 0
    same_family_retargets = 0
    identities: list[dict[str, str] | None] = [None, None, None]
    identity_start_ticks: list[int | None] = [None, None, None]
    commitment_durations: list[int] = []
    trace: list[dict[str, Any]] = []

    while outcome == "running" and tick < int(metadata["tick_cap"]):
        teacher = planner.actions(observations, masks, board)
        canonical_teacher = canonical_teacher_bundle(teacher, observations)
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
        forced_controls += len(decision.evaluation_order) - len(labels)
        if labels:
            eligible_boundaries += 1
        eligible_labels += len(labels)
        disagreements = {
            agent_id: label
            for agent_id, label in labels.items()
            if int(decision.action_indices[agent_id]) != int(label)
        }
        if disagreements:
            disagreement_ticks.append(tick)
        for agent_id, label in disagreements.items():
            student_index = int(decision.action_indices[agent_id])
            disagreement_records.append(
                {
                    "tick": tick,
                    "agent_id": agent_id,
                    "state_hash": state_hash,
                    "student_action_index": student_index,
                    "planner_action_index": int(label),
                    "student_semantic_identity": _semantic_identity(
                        student_index, observations[agent_id]
                    ),
                    "planner_semantic_identity": _semantic_identity(
                        int(label), observations[agent_id]
                    ),
                    **_legal_logit_metrics(
                        model, decision, agent_id, int(label)
                    ),
                }
            )

        apply_correction = bool(disagreements) and (
            mode == "correct_all"
            or (mode == "correct_first" and not corrected_once)
        )
        executed = decision
        correction_record: dict[str, Any] | None = None
        if apply_correction:
            executed = corrected_decision(
                decision, teacher, labels, observations
            )
            corrected_once = True
            correction_record = {
                "tick": tick,
                "pre_action_state_hash": state_hash,
                "disagreeing_agents": sorted(disagreements),
                "student_complete_bundle": decision.agent_actions,
                "planner_complete_actor_authoritative_bundle": (
                    canonical_teacher
                ),
                "executed_complete_bundle": executed.agent_actions,
            }

        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, int(metadata["tick_cap"]) - tick),
            agent_actions=executed.agent_actions,
            stop_on_decision_event=True,
        )
        accepted = _accepted_agents(response.action_results)
        for agent_id in sorted(labels):
            if agent_id not in accepted:
                continue
            identity = _semantic_identity(
                int(executed.action_indices[agent_id]),
                observations[agent_id],
            )
            if identity is None:
                continue
            prior = identities[agent_id]
            if prior is None:
                identities[agent_id] = identity
                identity_start_ticks[agent_id] = tick
            elif identity != prior:
                start = identity_start_ticks[agent_id]
                if start is None:
                    raise AssertionError("commitment start is missing")
                commitment_durations.append(tick - start)
                if identity["task_type"] != prior["task_type"]:
                    task_switches += 1
                else:
                    same_family_retargets += 1
                identities[agent_id] = identity
                identity_start_ticks[agent_id] = tick

        commit_all_seat_boundary(
            state,
            executed,
            response.action_results,
            observations,
            tick=tick,
        )
        if correction_record is not None:
            correction_record["post_action_state_hash"] = response.state_hash
            correction_records.append(correction_record)
        trace.append(
            {
                "tick": tick,
                "next_tick": response.tick,
                "mode": mode,
                "student_actions": decision.agent_actions,
                "teacher_actions": canonical_teacher,
                "executed_actions": executed.agent_actions,
                "corrected": apply_correction,
                "action_results": response.action_results,
                "pre_state_hash": state_hash,
                "post_state_hash": response.state_hash,
                "outcome": response.outcome,
            }
        )
        observations = response.observations
        masks = response.action_masks
        board = response.task_board
        reasons = list(response.decision_boundary.get("reasons", []))
        tick = response.tick
        state_hash = response.state_hash
        outcome = response.outcome

    if outcome not in {"win", "loss"} or eligible_labels <= 0:
        raise RuntimeError("M9 planner-correction episode was incomplete")
    for agent_id, identity in enumerate(identities):
        if identity is not None:
            start = identity_start_ticks[agent_id]
            if start is None:
                raise AssertionError("terminal commitment start is missing")
            commitment_durations.append(tick - start)
    live_ticks = tick - reset_tick
    if live_ticks <= 0:
        raise RuntimeError("M9 planner-correction live ticks are invalid")
    disagreements = len(disagreement_records)
    first_tick = disagreement_ticks[0] if disagreement_ticks else None
    return {
        "seed": seed,
        "mode": mode,
        "outcome": outcome,
        "terminal_tick": tick,
        "terminal_state_hash": state_hash,
        "core_health": float(observations[0]["team"]["core_health"]),
        "live_ticks": live_ticks,
        "eligible_boundaries": eligible_boundaries,
        "eligible_labels": eligible_labels,
        "disagreement_boundaries": len(disagreement_ticks),
        "disagreements": disagreements,
        "eligible_labels_per_1000_live_ticks": (
            1000.0 * eligible_labels / live_ticks
        ),
        "disagreements_per_1000_live_ticks": (
            1000.0 * disagreements / live_ticks
        ),
        "first_disagreement_tick": first_tick,
        "first_disagreement_fraction_remaining": (
            None
            if first_tick is None
            else (tick - first_tick) / live_ticks
        ),
        "disagreements_in_last_600_ticks_before_terminal": sum(
            value >= tick - 600 for value in disagreement_ticks
        ),
        "task_family_switches": task_switches,
        "same_family_retargets": same_family_retargets,
        "task_family_switches_per_1000_live_ticks": (
            1000.0 * task_switches / live_ticks
        ),
        "same_family_retargets_per_1000_live_ticks": (
            1000.0 * same_family_retargets / live_ticks
        ),
        "commitment_count": len(commitment_durations),
        "mean_commitment_duration_ticks": (
            sum(commitment_durations) / len(commitment_durations)
            if commitment_durations
            else 0.0
        ),
        "max_commitment_duration_ticks": max(
            commitment_durations, default=0
        ),
        "forced_controls": forced_controls,
        "correction_boundary_count": len(correction_records),
        "disagreement_records": disagreement_records,
        "correction_records": correction_records,
        "trace_sha256": _canonical_sha256(trace),
    }


def _aggregate(episodes: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if len(episodes) != 40:
        raise ValueError("M9 planner-correction needs exactly 40 roots")
    live_ticks = sum(int(item["live_ticks"]) for item in episodes)
    eligible_labels = sum(int(item["eligible_labels"]) for item in episodes)
    disagreements = sum(int(item["disagreements"]) for item in episodes)
    switches = sum(int(item["task_family_switches"]) for item in episodes)
    retargets = sum(int(item["same_family_retargets"]) for item in episodes)
    commitments = sum(int(item["commitment_count"]) for item in episodes)
    weighted_commitment_ticks = sum(
        float(item["mean_commitment_duration_ticks"])
        * int(item["commitment_count"])
        for item in episodes
    )
    return {
        "episodes": len(episodes),
        "wins": sum(item["outcome"] == "win" for item in episodes),
        "losses": sum(item["outcome"] == "loss" for item in episodes),
        "mean_core_health": (
            sum(float(item["core_health"]) for item in episodes)
            / len(episodes)
        ),
        "live_ticks": live_ticks,
        "eligible_boundaries": sum(
            int(item["eligible_boundaries"]) for item in episodes
        ),
        "eligible_labels": eligible_labels,
        "disagreement_boundaries": sum(
            int(item["disagreement_boundaries"]) for item in episodes
        ),
        "disagreements": disagreements,
        "eligible_labels_per_1000_live_ticks": (
            1000.0 * eligible_labels / live_ticks
        ),
        "disagreements_per_1000_live_ticks": (
            1000.0 * disagreements / live_ticks
        ),
        "disagreements_in_last_600_ticks_before_terminal": sum(
            int(item["disagreements_in_last_600_ticks_before_terminal"])
            for item in episodes
        ),
        "task_family_switches": switches,
        "same_family_retargets": retargets,
        "task_family_switches_per_1000_live_ticks": (
            1000.0 * switches / live_ticks
        ),
        "same_family_retargets_per_1000_live_ticks": (
            1000.0 * retargets / live_ticks
        ),
        "commitment_count": commitments,
        "mean_commitment_duration_ticks": (
            weighted_commitment_ticks / commitments
            if commitments
            else 0.0
        ),
        "max_commitment_duration_ticks": max(
            int(item["max_commitment_duration_ticks"]) for item in episodes
        ),
        "forced_controls": sum(
            int(item["forced_controls"]) for item in episodes
        ),
        "correction_boundary_count": sum(
            int(item["correction_boundary_count"]) for item in episodes
        ),
        "roots": list(episodes),
        "root_digest": _canonical_sha256(episodes),
    }


def _run_once(
    root: Path,
    checkpoint: dict[str, Any],
    config: dict[str, Any],
    seeds: Sequence[int],
    *,
    java: str,
    port: int,
    run_index: int,
    log_dir: Path,
) -> dict[str, Any]:
    model = _load_model(root, checkpoint, config)
    initial_digest = model_state_digest(model)
    update = int(checkpoint["lineage_update"])
    mode_reports: dict[str, Any] = {}
    with RlServerProcess(
        LaunchConfig(
            port=port,
            java=java,
            build_if_missing=False,
            log_dir=log_dir,
            log_name=f"planner-correction-u{update}-jvm-{run_index}",
        )
    ) as env:
        env.handshake("m9-planner-correction-causality")
        for mode in MODES:
            episodes = []
            for index, seed in enumerate(seeds, start=1):
                episodes.append(
                    _episode(
                        env,
                        model,
                        config,
                        seed=int(seed),
                        mode=mode,
                    )
                )
                if index % 10 == 0:
                    print(
                        f"M9 CORRECTION update={update} mode={mode} "
                        f"JVM={run_index}/2 episode={index}/{len(seeds)}",
                        flush=True,
                    )
            replay = _episode(
                env,
                model,
                config,
                seed=int(seeds[0]),
                mode=mode,
            )
            if replay != episodes[0]:
                raise RuntimeError(
                    "M9 planner-correction terminal replay diverged"
                )
            mode_reports[mode] = {
                **_aggregate(episodes),
                "terminal_reset_replay_equal": True,
            }
    if model_state_digest(model) != initial_digest:
        raise RuntimeError("M9 planner-correction mutated an immutable model")
    paired = paired_outcomes(
        mode_reports["baseline"]["roots"],
        mode_reports["correct_all"]["roots"],
    )
    return {
        "candidate": checkpoint["candidate"],
        "lineage_update": update,
        "expected_baseline_wins": int(
            checkpoint["autonomous_public_dev_wins"]
        ),
        "expected_baseline_mean_core_health": float(
            checkpoint["autonomous_public_dev_mean_core_health"]
        ),
        "modes": mode_reports,
        "baseline_to_correct_all_paired_outcomes": paired,
        "terminal_reset_replay_equal": True,
    }


def classify(
    checkpoint_reports: Sequence[dict[str, Any]],
    rules: dict[str, Any],
) -> dict[str, Any]:
    """Apply ADR-0125's exact two-checkpoint causal classification."""

    expected_rules = {
        "baseline_reproduction_required": (
            "each_checkpoint_baseline_exactly_matches_its_frozen_13_of_40_"
            "wins_and_mean_core_health_and_both_fresh_reports_match_root_by_"
            "root"
        ),
        "strong_correction_signal": (
            "baseline_reproduction_required_and_both_correct_all_cells_reach_"
            "at_least_28_of_40_wins"
        ),
        "low_correction_signal": (
            "baseline_reproduction_required_and_both_correct_all_cells_reach_"
            "at_most_21_of_40_wins"
        ),
        "mixed_correction_signal": (
            "baseline_reproduction_required_and_neither_strong_nor_low_"
            "correction_signal"
        ),
        "invalid": (
            "any_source_hash_mismatch_or_any_exact_report_reset_mismatch_or_"
            "baseline_reproduction_failure"
        ),
        "correct_first_role": (
            "descriptive_front_loaded_versus_diffuse_localization_only"
        ),
    }
    if rules != expected_rules or len(checkpoint_reports) != 2:
        raise ValueError("M9 planner-correction classification drifted")
    baseline_reproduced = all(
        int(item["modes"]["baseline"]["wins"])
        == int(item["expected_baseline_wins"])
        and float(item["modes"]["baseline"]["mean_core_health"])
        == float(item["expected_baseline_mean_core_health"])
        for item in checkpoint_reports
    )
    correct_all_wins = [
        int(item["modes"]["correct_all"]["wins"])
        for item in checkpoint_reports
    ]
    strong = baseline_reproduced and all(value >= 28 for value in correct_all_wins)
    low = baseline_reproduced and all(value <= 21 for value in correct_all_wins)
    mixed = baseline_reproduced and not strong and not low
    if not baseline_reproduced:
        signal = "invalid"
    elif strong:
        signal = "strong_correction_signal"
    elif low:
        signal = "low_correction_signal"
    else:
        signal = "mixed_correction_signal"
    return {
        "valid": baseline_reproduced,
        "baseline_reproduced": baseline_reproduced,
        "correct_all_wins": correct_all_wins,
        "strong_correction_signal": strong,
        "low_correction_signal": low,
        "mixed_correction_signal": mixed,
        "signal": signal,
        "correct_first_is_descriptive_only": True,
        "successor_training_authorized": False,
        "checkpoint_selection_authorized": False,
        "promotion_authorized": False,
    }


def run(output: Path, *, java: str, port: int) -> dict[str, Any]:
    root = repo_root()
    protocol, config, seeds = validate_inputs(root)
    _configure_torch(config)
    checkpoint_reports = []
    for checkpoint in protocol["checkpoints"]:
        reports = [
            _run_once(
                root,
                checkpoint,
                config,
                seeds,
                java=java,
                port=port,
                run_index=index,
                log_dir=output.parent,
            )
            for index in (1, 2)
        ]
        if reports[0] != reports[1]:
            raise RuntimeError(
                "M9 planner-correction fresh JVM reports diverged"
            )
        checkpoint_reports.append(reports[0])
    result = {
        "schema": "m9_planner_correction_causality_result_v1",
        "implementation_commit": _git_commit(root),
        "protocol_sha256": PROTOCOL_SHA256,
        "data_classification": "public_dev_only",
        "checkpoints": checkpoint_reports,
        "classification": classify(
            checkpoint_reports, protocol["classification"]
        ),
        "fresh_jvm_reports_equal": True,
        "terminal_reset_replay_equal": True,
        "model_or_optimizer_modified": False,
        "confirmation_or_held_out_access": False,
    }
    result["canonical_report_sha256"] = _canonical_sha256(result)
    _write_json(output, result)
    return result


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "runs/m9-planner-correction-causality-v1.json",
    )
    args = parser.parse_args(argv)
    try:
        result = run(args.output.resolve(), java=args.java, port=args.port)
    except Exception as error:
        print(f"M9 PLANNER CORRECTION FAIL: {error}", file=sys.stderr)
        return 1
    classification = result["classification"]
    print(
        "M9 PLANNER CORRECTION "
        f"{'PASS' if classification['valid'] else 'INVALID'} "
        f"signal={classification['signal']} "
        f"correct_all_wins={classification['correct_all_wins']} "
        f"canonical={result['canonical_report_sha256']}",
        flush=True,
    )
    return 0 if classification["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
