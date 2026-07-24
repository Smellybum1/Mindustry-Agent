"""Run ADR-0119's student-controlled critical-disagreement diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
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
    CONFIG_SHA256 as RELABEL_CONFIG_SHA256,
    DEV_MAXIMUM,
    DEV_MINIMUM,
    DEV_SET_SHA256,
    teacher_labels,
)
from mindustry_agents.training.ippo import (
    SharedRecurrentSelector,
    SharedSeatState,
    commit_all_seat_boundary,
    decide_all_seats,
    model_state_digest,
)
from mindustry_agents.training.ippo_artifacts import load_ippo_checkpoint
from mindustry_agents.training.ippo_ppo import sha256_path


PROTOCOL_RELATIVE = (
    "configs/evaluation/"
    "m9-candidate-on-policy-critical-disagreement-protocol.json"
)
PROTOCOL_SHA256 = (
    "aed6d1b231cc0992a31febb9927497879af2d6b813abaa457e499b8afb5535e0"
)
DISTILL_RESULT_SHA256 = (
    "47ced62d5b7e3c15c980415bc3c05974bfacfd1ccbfd7e2af6c7f474486af590"
)
RELABEL_RESULT_SHA256 = (
    "ebea0b741abbf2b7e3d995af1f87d7528ddee08d94089db4f837f40c730e60ee"
)


def _expected_authority() -> dict[str, bool]:
    return {
        "may_select_or_repair_checkpoint": False,
        "may_train_or_modify_model": False,
        "may_precommit_successor_after_result": True,
        "may_promote": False,
        "may_authorize_mappo": False,
        "may_access_confirmation": False,
        "may_access_held_out": False,
        "may_authorize_human_session": False,
    }


def validate_inputs(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[int]]:
    """Validate all frozen public sources before starting a JVM."""

    protocol_path = root / PROTOCOL_RELATIVE
    if sha256_path(protocol_path) != PROTOCOL_SHA256:
        raise ValueError("M9 critical-disagreement protocol hash drifted")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    execution = protocol.get("execution", {})
    expected_execution = {
        "fresh_jvm_runs_per_checkpoint": 2,
        "student_controls_environment": True,
        "student_action_mode": "deterministic_argmax",
        "teacher_labels_same_pre_action_student_visited_boundary": True,
        "teacher_action_execution": False,
        "eligible_boundary": (
            "alive_and_no_forced_task_action_and_teacher_action_"
            "authoritatively_legal"
        ),
        "forced_controls": (
            "executed_student_action_but_excluded_from_disagreement"
        ),
        "terminal_reset_replay": True,
        "exact_report_identity_required": True,
        "measurements": [
            "eligible_labels_and_top1_disagreements",
            "first_disagreement_tick_and_task_pair_per_episode",
            "teacher_task_to_student_task_confusion_by_outcome",
            "teacher_action_to_student_action_confusion_by_outcome",
            "rejected_student_actions_by_task_and_outcome",
            "episodes_with_rejection_by_outcome",
        ],
    }
    if (
        protocol.get("schema")
        != "m9_candidate_on_policy_critical_disagreement_protocol_v1"
        or protocol.get("data_classification") != "public_dev_only"
        or protocol.get("split") != "dev"
        or protocol.get("seed_set_sha256") != DEV_SET_SHA256
        or protocol.get("teacher_policy")
        != "candidate-native-planner-v11-single-defender"
        or protocol.get("authority") != _expected_authority()
        or execution != expected_execution
    ):
        raise ValueError("M9 critical-disagreement authority drifted")

    checkpoints = protocol.get("checkpoints", [])
    if [int(item.get("lineage_update", -1)) for item in checkpoints] != [
        32,
        64,
    ]:
        raise ValueError("M9 critical-disagreement checkpoint order drifted")
    expected_results = {
        32: DISTILL_RESULT_SHA256,
        64: RELABEL_RESULT_SHA256,
    }
    for checkpoint in checkpoints:
        update = int(checkpoint["lineage_update"])
        result_path = root / str(checkpoint["source_result"])
        checkpoint_path = root / str(checkpoint["path"])
        if (
            checkpoint["source_result_sha256"] != expected_results[update]
            or sha256_path(result_path) != expected_results[update]
            or sha256_path(checkpoint_path) != checkpoint["file_sha256"]
        ):
            raise ValueError(
                "M9 critical-disagreement source identity drifted"
            )
        result = json.loads(result_path.read_text(encoding="utf-8"))
        replica = result.get("replica_a", {})
        row = (
            replica.get("final_public_dev")
            if update == 32
            else replica.get("best_public_dev")
        )
        if (
            replica.get("construction_passed") is not False
            or replica.get("selected_checkpoint") is not None
            or result.get("replica_b_authorized") is not False
            or result.get("confirmation_or_held_out_access") is not False
            or row.get("checkpoint_content_sha256")
            != checkpoint["content_sha256"]
            or row.get("model_state_sha256")
            != checkpoint["model_state_sha256"]
            or int(row.get("wins", -1))
            != int(checkpoint["autonomous_public_dev_wins"])
        ):
            raise ValueError(
                "M9 critical-disagreement rejected source is invalid"
            )

    source_config = load_distillation_config(
        root / "configs/training/m9-candidate-native-distill-v1.json"
    )
    if source_config["dev_seed_set"] != protocol["seed_set"]:
        raise ValueError("M9 critical-disagreement dev path drifted")
    dev_set, _ = _load_seed_set(
        root,
        str(protocol["seed_set"]),
        split="dev",
        count=40,
        lower=DEV_MINIMUM,
        upper=DEV_MAXIMUM,
    )
    return protocol, source_config, [int(seed) for seed in dev_set["seeds"]]


def classify(
    update_64: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    """Apply ADR-0119's exact concentration thresholds."""

    if (
        int(rules.get("top_task_pairs", -1)) != 3
        or float(
            rules.get(
                "minimum_top_task_pair_disagreement_fraction_for_concentration",
                -1.0,
            )
        )
        != 0.5
        or float(
            rules.get(
                "minimum_dominant_first_pair_loss_fraction_for_concentration",
                -1.0,
            )
        )
        != 0.5
        or float(
            rules.get(
                "minimum_loss_minus_win_rejection_episode_fraction", -1.0
            )
        )
        != 0.25
    ):
        raise ValueError(
            "M9 critical-disagreement classification thresholds drifted"
        )
    labels = int(update_64.get("eligible_labels", 0))
    disagreements = int(update_64.get("top1_disagreements", -1))
    episodes = update_64.get("episodes_by_outcome", {})
    wins = int(episodes.get("win", 0))
    losses = int(episodes.get("loss", 0))
    if (
        labels <= 0
        or not 0 <= disagreements <= labels
        or wins + losses != 40
        or wins <= 0
        or losses <= 0
    ):
        raise ValueError("M9 critical-disagreement metrics are invalid")

    task_counts: Counter[str] = Counter()
    for key, value in update_64[
        "teacher_task_to_student_task_confusion_by_outcome"
    ].items():
        task_counts[key.rsplit(":", 1)[0]] += int(value)
    top_three = sum(
        value for _, value in task_counts.most_common(3)
    )
    top_fraction = top_three / max(1, disagreements)
    first_loss = Counter(
        update_64["first_disagreement_task_pair_on_losses"]
    )
    dominant_first = max(first_loss.values(), default=0)
    dominant_first_fraction = dominant_first / losses
    rejection_episodes = update_64["episodes_with_rejection_by_outcome"]
    loss_rejection_fraction = int(rejection_episodes.get("loss", 0)) / losses
    win_rejection_fraction = int(rejection_episodes.get("win", 0)) / wins
    rejection_excess = loss_rejection_fraction - win_rejection_fraction
    concentrated = (
        top_fraction >= 0.5 or dominant_first_fraction >= 0.5
    )
    rejection_signal = rejection_excess >= 0.25
    diffuse = not concentrated and not rejection_signal
    return {
        "top_three_task_pair_disagreement_fraction": top_fraction,
        "dominant_first_pair_loss_fraction": dominant_first_fraction,
        "loss_rejection_episode_fraction": loss_rejection_fraction,
        "win_rejection_episode_fraction": win_rejection_fraction,
        "loss_minus_win_rejection_episode_fraction": rejection_excess,
        "concentrated_critical_error_signal": concentrated,
        "rejection_association_signal": rejection_signal,
        "diffuse_residual_signal": diffuse,
        "active_signals": [
            name
            for name, active in (
                ("concentrated_critical_error_signal", concentrated),
                ("rejection_association_signal", rejection_signal),
                ("diffuse_residual_signal", diffuse),
            )
            if active
        ],
        "successor_training_authorized": False,
        "checkpoint_selection_authorized": False,
        "promotion_authorized": False,
    }


def _student_task(
    decision: Any,
    agent_id: int,
    observation: dict[str, Any],
) -> str:
    action_type = decision.agent_actions[agent_id].get(
        "task_action", {}
    ).get("type")
    if action_type in {
        "SELECT_CANDIDATE_TASK",
        "CONTINUE_CURRENT_TASK",
        "WAIT",
    }:
        return action_task(
            decision.action_indices[agent_id], observation
        )
    return str(action_type or "UNKNOWN")


def _episode(
    env: RlServerProcess,
    model: SharedRecurrentSelector,
    config: dict[str, Any],
    *,
    seed: int,
) -> dict[str, Any]:
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
    labels = 0
    matches = 0
    forced = 0
    first_disagreement: dict[str, Any] | None = None
    task_confusion: Counter[str] = Counter()
    action_confusion: Counter[str] = Counter()
    rejected_tasks: Counter[str] = Counter()
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
        teacher_by_agent = teacher_labels(
            decision, teacher, observations
        )
        forced += len(decision.evaluation_order) - len(teacher_by_agent)
        for agent_id, label in teacher_by_agent.items():
            labels += 1
            predicted = decision.action_indices[agent_id]
            if predicted == label:
                matches += 1
                continue
            teacher_name = action_task(label, observations[agent_id])
            student_name = _student_task(
                decision, agent_id, observations[agent_id]
            )
            task_pair = f"{teacher_name}->{student_name}"
            action_pair = f"{label}->{predicted}"
            task_confusion[task_pair] += 1
            action_confusion[action_pair] += 1
            if first_disagreement is None:
                first_disagreement = {
                    "tick": tick,
                    "agent_id": agent_id,
                    "task_pair": task_pair,
                    "action_pair": action_pair,
                }

        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, int(metadata["tick_cap"]) - tick),
            agent_actions=decision.agent_actions,
            stop_on_decision_event=True,
        )
        for agent_id, result in enumerate(response.action_results):
            if not result.get("accepted", False):
                rejected_tasks[
                    _student_task(
                        decision, agent_id, observations[agent_id]
                    )
                ] += 1
        commit_all_seat_boundary(
            state,
            decision,
            response.action_results,
            observations,
            tick=tick,
        )
        trace.append(
            {
                "tick": tick,
                "next_tick": response.tick,
                "student_actions": decision.agent_actions,
                "teacher_actions": teacher,
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

    if outcome == "running" or labels <= 0:
        raise RuntimeError(
            "M9 critical-disagreement episode was incomplete"
        )
    return {
        "seed": seed,
        "outcome": outcome,
        "tick": tick,
        "core_health": float(observations[0]["team"]["core_health"]),
        "eligible_labels": labels,
        "top1_matches": matches,
        "top1_disagreements": labels - matches,
        "forced_controls": forced,
        "first_disagreement": first_disagreement,
        "task_confusion": dict(sorted(task_confusion.items())),
        "action_confusion": dict(sorted(action_confusion.items())),
        "rejected_student_actions": sum(rejected_tasks.values()),
        "rejected_tasks": dict(sorted(rejected_tasks.items())),
        "trace_sha256": _canonical_sha256(trace),
    }


def _aggregate(episodes: Sequence[dict[str, Any]]) -> dict[str, Any]:
    labels = sum(int(item["eligible_labels"]) for item in episodes)
    matches = sum(int(item["top1_matches"]) for item in episodes)
    task_by_outcome: Counter[str] = Counter()
    action_by_outcome: Counter[str] = Counter()
    rejected_by_outcome: Counter[str] = Counter()
    first_loss: Counter[str] = Counter()
    rejection_episodes: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()
    for episode in episodes:
        outcome = str(episode["outcome"])
        outcomes[outcome] += 1
        for key, value in episode["task_confusion"].items():
            task_by_outcome[f"{key}:{outcome}"] += int(value)
        for key, value in episode["action_confusion"].items():
            action_by_outcome[f"{key}:{outcome}"] += int(value)
        for key, value in episode["rejected_tasks"].items():
            rejected_by_outcome[f"{key}:{outcome}"] += int(value)
        if int(episode["rejected_student_actions"]) > 0:
            rejection_episodes[outcome] += 1
        first = episode["first_disagreement"]
        if outcome == "loss" and first is not None:
            first_loss[str(first["task_pair"])] += 1
    return {
        "episodes": len(episodes),
        "wins": outcomes["win"],
        "losses": outcomes["loss"],
        "episodes_by_outcome": {
            "win": outcomes["win"],
            "loss": outcomes["loss"],
        },
        "eligible_labels": labels,
        "top1_matches": matches,
        "top1_disagreements": labels - matches,
        "top1_agreement": matches / labels,
        "forced_controls": sum(
            int(item["forced_controls"]) for item in episodes
        ),
        "teacher_task_to_student_task_confusion_by_outcome": dict(
            sorted(task_by_outcome.items())
        ),
        "teacher_action_to_student_action_confusion_by_outcome": dict(
            sorted(action_by_outcome.items())
        ),
        "first_disagreement_task_pair_on_losses": dict(
            sorted(first_loss.items())
        ),
        "rejected_student_actions_by_task_and_outcome": dict(
            sorted(rejected_by_outcome.items())
        ),
        "rejected_student_actions": sum(
            int(item["rejected_student_actions"]) for item in episodes
        ),
        "episodes_with_rejection_by_outcome": {
            "win": rejection_episodes["win"],
            "loss": rejection_episodes["loss"],
        },
        "episode_digest": _canonical_sha256(
            [
                {
                    "seed": item["seed"],
                    "outcome": item["outcome"],
                    "tick": item["tick"],
                    "core_health": item["core_health"],
                    "eligible_labels": item["eligible_labels"],
                    "top1_disagreements": item["top1_disagreements"],
                    "first_disagreement": item["first_disagreement"],
                    "rejected_student_actions": item[
                        "rejected_student_actions"
                    ],
                    "trace_sha256": item["trace_sha256"],
                }
                for item in episodes
            ]
        ),
    }


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
        raise ValueError(
            "M9 critical-disagreement loaded checkpoint drifted"
        )
    model.eval()
    return model


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
    with RlServerProcess(
        LaunchConfig(
            port=port,
            java=java,
            build_if_missing=False,
            log_dir=log_dir,
            log_name=f"critical-u{update}-jvm-{run_index}",
        )
    ) as env:
        env.handshake("m9-candidate-critical-disagreement")
        episodes = []
        for index, seed in enumerate(seeds, start=1):
            episodes.append(
                _episode(env, model, config, seed=int(seed))
            )
            if index % 10 == 0:
                print(
                    f"M9 CRITICAL update={update} "
                    f"JVM={run_index}/2 episode={index}/{len(seeds)}",
                    flush=True,
                )
        replay = _episode(env, model, config, seed=int(seeds[0]))
    if replay != episodes[0]:
        raise RuntimeError(
            "M9 critical-disagreement terminal replay diverged"
        )
    if model_state_digest(model) != initial_digest:
        raise RuntimeError(
            "M9 critical-disagreement mutated an immutable model"
        )
    return {
        "candidate": checkpoint["candidate"],
        "lineage_update": update,
        "autonomous_public_dev_wins": int(
            checkpoint["autonomous_public_dev_wins"]
        ),
        **_aggregate(episodes),
        "terminal_reset_replay_equal": True,
    }


def run(
    output: Path,
    *,
    java: str,
    port: int,
) -> dict[str, Any]:
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
                "M9 critical-disagreement fresh JVM reports diverged"
            )
        checkpoint_reports.append(reports[0])
    result = {
        "schema": "m9_candidate_on_policy_critical_disagreement_result_v1",
        "implementation_commit": _git_commit(root),
        "protocol_sha256": PROTOCOL_SHA256,
        "data_classification": "public_dev_only",
        "checkpoints": checkpoint_reports,
        "classification": classify(
            checkpoint_reports[1], protocol["classification"]
        ),
        "fresh_jvm_reports_equal": True,
        "terminal_reset_replay_equal": True,
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
        default=root
        / "runs/m9-candidate-on-policy-critical-disagreement.json",
    )
    args = parser.parse_args(argv)
    try:
        result = run(
            args.output.resolve(),
            java=args.java,
            port=args.port,
        )
    except Exception as error:
        print(f"M9 CRITICAL FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "M9 CRITICAL OK "
        f"signals={','.join(result['classification']['active_signals'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
