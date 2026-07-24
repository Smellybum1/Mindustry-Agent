"""Run ADR-0131's public-only planner trajectory-divergence diagnostic."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Sequence

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
    load_on_policy_relabel_config,
)
from mindustry_agents.training.ippo import (
    SharedRecurrentSelector,
    SharedSeatState,
    _action_index,
    canonical_teacher_bundle,
    commit_all_seat_boundary,
    decide_all_seats,
    model_state_digest,
)
from mindustry_agents.training.ippo_artifacts import load_ippo_checkpoint
from mindustry_agents.training.ippo_ppo import sha256_path


PROTOCOL_RELATIVE = (
    "configs/evaluation/m9-planner-trajectory-divergence-v1-protocol.json"
)
PROTOCOL_SHA256 = (
    "bcd572fa49d859d56c780c55a389577835eccf59a9382887bff68ec834778d6a"
)
POLICIES = ("student", "planner")
SAMPLE_PERIOD_TICKS = 60
WAIT_TOKEN = "WAIT"


def _expected_downstream_authority() -> dict[str, bool]:
    return {
        "may_train": False,
        "may_select_repair_or_promote_checkpoint": False,
        "may_change_planner_features_masks_or_candidates": False,
        "may_use_reward_ppo_or_mappo": False,
        "may_access_confirmation": False,
        "may_access_held_out": False,
        "may_authorize_human_session": False,
        "trajectory_supervision_signal_may_authorize_only_new_prospective_adr": (
            True
        ),
    }


def validate_inputs(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[int]]:
    """Fail closed over the frozen public inputs before a JVM starts."""

    protocol_path = root / PROTOCOL_RELATIVE
    if sha256_path(protocol_path) != PROTOCOL_SHA256:
        raise ValueError("M9 planner-trajectory protocol hash drifted")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    source = protocol.get("source_checkpoint", {})
    measurement = protocol.get("trajectory_measurement", {})
    validity = protocol.get("validity_requirements", {})
    replica = protocol.get("replica_policy", {})
    if (
        protocol.get("schema")
        != "m9_planner_trajectory_divergence_protocol_v1"
        or protocol.get("diagnostic")
        != "m9-planner-trajectory-divergence-v1"
        or protocol.get("data_classification") != "public_dev_only"
        or protocol.get("split") != "dev"
        or protocol.get("seed_set_sha256") != DEV_SET_SHA256
        or int(source.get("lineage_update", -1)) != 64
        or source.get("construction_passed") is not False
        or source.get("selected_or_promoted") is not False
        or source.get("repaired") is not False
        or protocol.get("planner_policy", {}).get("candidate")
        != "candidate-native-planner-v11-single-defender"
        or protocol.get("planner_policy", {}).get("action_authority")
        != "complete_canonical_bundle"
        or measurement.get("sample_period_ticks") != SAMPLE_PERIOD_TICKS
        or measurement.get("initial_per_seat_token") != WAIT_TOKEN
        or measurement.get("target_identifiers_recorded") is not False
        or measurement.get("raw_observations_published") is not False
        or validity.get("student_baseline_wins_exact") != 13
        or float(validity.get("student_baseline_mean_core_health_exact", -1))
        != 242.975
        or validity.get("planner_wins_exact") != 32
        or replica.get("fresh_jvm_reports") != 2
        or replica.get("exact_root_and_aggregate_identity_required") is not True
        or protocol.get("downstream_authority")
        != _expected_downstream_authority()
    ):
        raise ValueError("M9 planner-trajectory authority drifted")

    bound_paths = {
        "config_sha256": source["config_path"],
        "file_sha256": source["path"],
        "source_result_sha256": source["source_result"],
        "source_manifest_sha256": source["source_manifest"],
    }
    for digest_key, relative in bound_paths.items():
        if sha256_path(root / str(relative)) != source[digest_key]:
            raise ValueError("M9 planner-trajectory source identity drifted")
    causal = protocol.get("bound_causal_result", {})
    if (
        sha256_path(root / str(causal.get("path", "")))
        != causal.get("sha256")
        or causal.get("classification") != "low_correction_signal"
        or causal.get("correct_all_wins") != [9, 9]
    ):
        raise ValueError("M9 planner-trajectory causal evidence drifted")

    manifest = json.loads(
        (root / str(source["source_manifest"])).read_text(encoding="utf-8")
    )
    result = json.loads(
        (root / str(source["source_result"])).read_text(encoding="utf-8")
    )
    replica_a = result.get("replica_a", {})
    final = replica_a.get("final_public_dev", {})
    if (
        manifest.get("canonical_run_sha256")
        != source["source_canonical_run_sha256"]
        or replica_a.get("construction_passed") is not False
        or replica_a.get("selected_checkpoint") is not None
        or result.get("replica_b_authorized") is not False
        or result.get("confirmation_or_held_out_access") is not False
        or final.get("checkpoint_content_sha256") != source["content_sha256"]
        or final.get("model_state_sha256") != source["model_state_sha256"]
        or int(final.get("wins", -1))
        != int(source["expected_public_dev_wins"])
        or float(final.get("mean_core_health", -1.0))
        != float(source["expected_mean_core_health"])
    ):
        raise ValueError("M9 planner-trajectory rejected source is invalid")

    config_path = root / str(source["config_path"])
    continuation_config = load_on_policy_relabel_config(config_path)
    if (
        continuation_config["dev_seed_set"] != protocol["seed_set"]
        or continuation_config["scenario_id"] != protocol["scenario_id"]
        or int(continuation_config["scenario_version"])
        != int(protocol["scenario_version"])
    ):
        raise ValueError("M9 planner-trajectory public config drifted")
    config = load_distillation_config(
        root / "configs/training/m9-candidate-native-distill-v1.json"
    )
    if (
        config["dev_seed_set"] != protocol["seed_set"]
        or config["scenario_id"] != protocol["scenario_id"]
        or int(config["scenario_version"])
        != int(protocol["scenario_version"])
    ):
        raise ValueError("M9 planner-trajectory runtime config drifted")
    seed_set, _ = _load_seed_set(
        root,
        str(protocol["seed_set"]),
        split="dev",
        count=40,
        lower=DEV_MINIMUM,
        upper=DEV_MAXIMUM,
    )
    return protocol, config, [int(seed) for seed in seed_set["seeds"]]


def _load_model(
    root: Path,
    source: dict[str, Any],
    config: dict[str, Any],
) -> SharedRecurrentSelector:
    model = SharedRecurrentSelector(int(config["model_init_seed"]))
    payload = load_ippo_checkpoint(
        root / str(source["path"]),
        model,
        expected_config_sha256=str(source["config_sha256"]),
    )
    if (
        int(payload["update"]) != int(source["lineage_update"])
        or payload["checkpoint_content_sha256"] != source["content_sha256"]
        or payload["model_state_sha256"] != source["model_state_sha256"]
        or payload["optimizer_state_sha256"]
        != source["optimizer_state_sha256"]
        or model_state_digest(model) != source["model_state_sha256"]
    ):
        raise ValueError("M9 planner-trajectory loaded checkpoint drifted")
    model.eval()
    return model


def _accepted_agents(action_results: Sequence[dict[str, Any]]) -> set[int]:
    return {
        int(item["agent_id"])
        for item in action_results
        if item.get("accepted", False)
        and type(item.get("agent_id")) is int
    }


def _apply_actor_tokens(
    tokens: list[str],
    actions: Sequence[dict[str, Any]],
    observations: Sequence[dict[str, Any]],
    accepted: set[int],
    *,
    actor_authoritative: set[int],
) -> None:
    """Apply accepted SELECT/WAIT task-family identities in place."""

    for agent_id in sorted(actor_authoritative & accepted):
        action = actions[agent_id]
        action_type = action.get("task_action", {}).get("type")
        if action_type == "WAIT":
            tokens[agent_id] = WAIT_TOKEN
        elif action_type == "SELECT_CANDIDATE_TASK":
            index = _action_index(
                action, observations[agent_id].get("task_candidates", [])
            )
            family = action_task(index, observations[agent_id])
            if family in {"CONTINUE_CURRENT_TASK", WAIT_TOKEN}:
                raise ValueError(
                    "M9 planner-trajectory SELECT token is not a task family"
                )
            tokens[agent_id] = family


def _append_grid(
    trajectory: list[list[str]],
    tokens: Sequence[str],
    *,
    next_grid_tick: int,
    boundary_tick: int,
) -> int:
    while next_grid_tick <= boundary_tick:
        trajectory.append(list(tokens))
        next_grid_tick += SAMPLE_PERIOD_TICKS
    return next_grid_tick


def _planner_actor_authoritative(
    observation: dict[str, Any],
    action_mask: dict[str, Any],
    action: dict[str, Any],
) -> bool:
    if observation.get("unit", {}).get("dead", False):
        return False
    action_type = action.get("task_action", {}).get("type")
    if action_type == "SELECT_CANDIDATE_TASK":
        return True
    if action_type != "WAIT":
        return False
    if action_mask.get("continue_current_task", False) or action_mask.get(
        "abandon", False
    ):
        return True
    candidate_mask = action_mask.get("candidate_task", [])
    return any(
        candidate.get("task_type") != WAIT_TOKEN
        and candidate.get("valid") is not False
        and 0 <= int(candidate.get("index", -1)) < len(candidate_mask)
        and candidate_mask[int(candidate["index"])]
        for candidate in observation.get("task_candidates", [])
    )


def _student_episode(
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
    state = SharedSeatState.fresh()
    observations = reset.initial_observations
    masks = reset.action_masks
    metadata = reset.metadata
    board: list[dict[str, Any]] = []
    reasons: list[str] = []
    tick = reset.tick
    state_hash = reset.state_hash
    outcome = reset.outcome
    tokens = [WAIT_TOKEN, WAIT_TOKEN, WAIT_TOKEN]
    trajectory: list[list[str]] = []
    next_grid_tick = reset.tick + SAMPLE_PERIOD_TICKS
    trace: list[dict[str, Any]] = []

    while outcome == "running" and tick < int(metadata["tick_cap"]):
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
        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, int(metadata["tick_cap"]) - tick),
            agent_actions=decision.agent_actions,
            stop_on_decision_event=True,
        )
        actor_authoritative = {
            agent_id
            for agent_id in decision.evaluation_order
            if decision.features[agent_id].forced_task_action is None
        }
        accepted = _accepted_agents(response.action_results)
        _apply_actor_tokens(
            tokens,
            decision.agent_actions,
            observations,
            accepted,
            actor_authoritative=actor_authoritative,
        )
        next_grid_tick = _append_grid(
            trajectory,
            tokens,
            next_grid_tick=next_grid_tick,
            boundary_tick=response.tick,
        )
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
                "action_types": [
                    item.get("task_action", {}).get("type")
                    for item in decision.agent_actions
                ],
                "accepted_agents": sorted(accepted),
                "joint_task_family": list(tokens),
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

    if outcome not in {"win", "loss"} or not trajectory:
        raise RuntimeError("M9 planner-trajectory student episode incomplete")
    return {
        "seed": seed,
        "policy": "student",
        "outcome": outcome,
        "reset_tick": reset.tick,
        "terminal_tick": tick,
        "terminal_state_hash": state_hash,
        "core_health": float(observations[0]["team"]["core_health"]),
        "grid_samples": len(trajectory),
        "joint_task_family_trajectory": trajectory,
        "trace_sha256": _canonical_sha256(trace),
    }


def _planner_episode(
    env: RlServerProcess,
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
    observations = reset.initial_observations
    masks = reset.action_masks
    metadata = reset.metadata
    board: list[dict[str, Any]] = []
    tick = reset.tick
    state_hash = reset.state_hash
    outcome = reset.outcome
    tokens = [WAIT_TOKEN, WAIT_TOKEN, WAIT_TOKEN]
    trajectory: list[list[str]] = []
    next_grid_tick = reset.tick + SAMPLE_PERIOD_TICKS
    trace: list[dict[str, Any]] = []

    while outcome == "running" and tick < int(metadata["tick_cap"]):
        actions = canonical_teacher_bundle(
            planner.actions(observations, masks, board),
            observations,
        )
        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, int(metadata["tick_cap"]) - tick),
            agent_actions=actions,
            stop_on_decision_event=True,
        )
        planner.observe_action_results(response.action_results)
        accepted = _accepted_agents(response.action_results)
        actor_authoritative = {
            agent_id
            for agent_id, (observation, action_mask, action) in enumerate(
                zip(observations, masks, actions, strict=True)
            )
            if _planner_actor_authoritative(
                observation, action_mask, action
            )
        }
        _apply_actor_tokens(
            tokens,
            actions,
            observations,
            accepted,
            actor_authoritative=actor_authoritative,
        )
        next_grid_tick = _append_grid(
            trajectory,
            tokens,
            next_grid_tick=next_grid_tick,
            boundary_tick=response.tick,
        )
        trace.append(
            {
                "tick": tick,
                "next_tick": response.tick,
                "action_types": [
                    item.get("task_action", {}).get("type") for item in actions
                ],
                "accepted_agents": sorted(accepted),
                "joint_task_family": list(tokens),
                "pre_state_hash": state_hash,
                "post_state_hash": response.state_hash,
                "outcome": response.outcome,
            }
        )
        observations = response.observations
        masks = response.action_masks
        board = response.task_board
        tick = response.tick
        state_hash = response.state_hash
        outcome = response.outcome

    if outcome not in {"win", "loss"} or not trajectory:
        raise RuntimeError("M9 planner-trajectory planner episode incomplete")
    return {
        "seed": seed,
        "policy": "planner",
        "outcome": outcome,
        "reset_tick": reset.tick,
        "terminal_tick": tick,
        "terminal_state_hash": state_hash,
        "core_health": float(observations[0]["team"]["core_health"]),
        "grid_samples": len(trajectory),
        "joint_task_family_trajectory": trajectory,
        "trace_sha256": _canonical_sha256(trace),
    }


def compress_joint_tokens(
    sequence: Sequence[Sequence[str]],
) -> list[list[str]]:
    compressed: list[list[str]] = []
    for token in sequence:
        value = list(token)
        if not compressed or value != compressed[-1]:
            compressed.append(value)
    return compressed


def levenshtein_distance(
    left: Sequence[Sequence[str]],
    right: Sequence[Sequence[str]],
) -> int:
    """Return deterministic unit-cost Levenshtein distance."""

    previous = list(range(len(right) + 1))
    for left_index, left_token in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_token in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1]
                    + (list(left_token) != list(right_token)),
                )
            )
        previous = current
    return previous[-1]


def compare_root_trajectories(
    student: dict[str, Any],
    planner: dict[str, Any],
) -> dict[str, Any]:
    if int(student["seed"]) != int(planner["seed"]):
        raise ValueError("M9 planner-trajectory paired seed order drifted")
    if int(student["reset_tick"]) != int(planner["reset_tick"]):
        raise ValueError("M9 planner-trajectory paired reset tick drifted")
    reset_tick = int(student["reset_tick"])
    minimum_terminal = min(
        int(student["terminal_tick"]), int(planner["terminal_tick"])
    )
    common_samples = (
        minimum_terminal - reset_tick
    ) // SAMPLE_PERIOD_TICKS
    student_tokens = student["joint_task_family_trajectory"][:common_samples]
    planner_tokens = planner["joint_task_family_trajectory"][:common_samples]
    if (
        common_samples <= 0
        or len(student_tokens) != common_samples
        or len(planner_tokens) != common_samples
    ):
        raise ValueError("M9 planner-trajectory common grid length drifted")
    mismatches = sum(
        left != right
        for left, right in zip(student_tokens, planner_tokens, strict=True)
    )
    student_compressed = compress_joint_tokens(student_tokens)
    planner_compressed = compress_joint_tokens(planner_tokens)
    edit_distance = levenshtein_distance(
        student_compressed, planner_compressed
    )
    maximum_length = max(len(student_compressed), len(planner_compressed))
    normalized = edit_distance / maximum_length if maximum_length else 0.0
    return {
        "seed": int(student["seed"]),
        "student_outcome": student["outcome"],
        "planner_outcome": planner["outcome"],
        "minimum_terminal_tick": minimum_terminal,
        "common_grid_samples": common_samples,
        "mismatched_grid_samples": mismatches,
        "occupancy_mismatch_fraction": mismatches / common_samples,
        "student_compressed_tokens": len(student_compressed),
        "planner_compressed_tokens": len(planner_compressed),
        "compressed_levenshtein_distance": edit_distance,
        "normalized_compressed_sequence_distance": normalized,
    }


def paired_report(
    students: Sequence[dict[str, Any]],
    planners: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    if len(students) != len(planners) or not students:
        raise ValueError("M9 planner-trajectory paired roots drifted")
    roots = [
        compare_root_trajectories(student, planner)
        for student, planner in zip(students, planners, strict=True)
    ]
    primary = [
        item
        for item in roots
        if item["student_outcome"] == "loss"
        and item["planner_outcome"] == "win"
    ]
    both_win = sum(
        item["student_outcome"] == "win"
        and item["planner_outcome"] == "win"
        for item in roots
    )
    student_only = sum(
        item["student_outcome"] == "win"
        and item["planner_outcome"] == "loss"
        for item in roots
    )
    both_loss = sum(
        item["student_outcome"] == "loss"
        and item["planner_outcome"] == "loss"
        for item in roots
    )
    return {
        "both_win": both_win,
        "student_only_win": student_only,
        "planner_only_win": len(primary),
        "both_loss": both_loss,
        "median_primary_occupancy_mismatch": (
            statistics.median(
                item["occupancy_mismatch_fraction"] for item in primary
            )
            if primary
            else 0.0
        ),
        "median_primary_normalized_compressed_sequence_distance": (
            statistics.median(
                item["normalized_compressed_sequence_distance"]
                for item in primary
            )
            if primary
            else 0.0
        ),
        "roots": roots,
        "primary_roots": primary,
        "root_digest": _canonical_sha256(roots),
    }


def _aggregate(episodes: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not episodes:
        raise ValueError("M9 planner-trajectory has no episodes")
    return {
        "episodes": len(episodes),
        "wins": sum(item["outcome"] == "win" for item in episodes),
        "losses": sum(item["outcome"] == "loss" for item in episodes),
        "mean_core_health": sum(
            float(item["core_health"]) for item in episodes
        )
        / len(episodes),
        "roots": list(episodes),
        "root_digest": _canonical_sha256(episodes),
    }


def _run_once(
    root: Path,
    protocol: dict[str, Any],
    config: dict[str, Any],
    seeds: Sequence[int],
    *,
    java: str,
    port: int,
    run_index: int,
    log_dir: Path,
) -> dict[str, Any]:
    model = _load_model(root, protocol["source_checkpoint"], config)
    initial_digest = model_state_digest(model)
    reports: dict[str, Any] = {}
    with RlServerProcess(
        LaunchConfig(
            port=port,
            java=java,
            build_if_missing=False,
            log_dir=log_dir,
            log_name=f"planner-trajectory-jvm-{run_index}",
        )
    ) as env:
        env.handshake("m9-planner-trajectory-divergence")
        for policy in POLICIES:
            episodes = []
            for index, seed in enumerate(seeds, start=1):
                episode = (
                    _student_episode(env, model, config, seed=int(seed))
                    if policy == "student"
                    else _planner_episode(env, config, seed=int(seed))
                )
                episodes.append(episode)
                if index % 10 == 0:
                    print(
                        f"M9 TRAJECTORY policy={policy} JVM={run_index}/2 "
                        f"episode={index}/{len(seeds)}",
                        flush=True,
                    )
            replay = (
                _student_episode(env, model, config, seed=int(seeds[0]))
                if policy == "student"
                else _planner_episode(env, config, seed=int(seeds[0]))
            )
            if replay != episodes[0]:
                raise RuntimeError(
                    "M9 planner-trajectory terminal replay diverged"
                )
            reports[policy] = {
                **_aggregate(episodes),
                "terminal_reset_replay_equal": True,
            }
    if model_state_digest(model) != initial_digest:
        raise RuntimeError("M9 planner-trajectory mutated immutable model")
    return {
        "policies": reports,
        "paired": paired_report(
            reports["student"]["roots"], reports["planner"]["roots"]
        ),
        "model_state_sha256": initial_digest,
        "optimizer_state_sha256": protocol["source_checkpoint"][
            "optimizer_state_sha256"
        ],
        "model_or_optimizer_modified": False,
        "terminal_reset_replay_equal": True,
    }


def classify(
    paired: dict[str, Any],
    rules: dict[str, Any],
    *,
    valid: bool,
) -> dict[str, Any]:
    expected = {
        "precedence": [
            "invalid",
            "trajectory_supervision_signal",
            "low_trajectory_signal",
            "mixed_trajectory_signal",
        ],
        "trajectory_supervision_signal": {
            "minimum_planner_only_wins": 15,
            "minimum_median_paired_root_occupancy_mismatch": 0.5,
            "minimum_median_paired_root_compressed_sequence_distance": 0.5,
        },
        "low_trajectory_signal": {
            "maximum_planner_only_wins": 9,
            "maximum_median_paired_root_occupancy_mismatch": 0.25,
        },
        "low_rule": (
            "planner_only_wins_at_most_maximum_or_median_paired_root_"
            "occupancy_mismatch_at_most_maximum"
        ),
        "otherwise": "mixed_trajectory_signal",
        "invalid": (
            "any_source_hash_mismatch_or_baseline_reproduction_failure_or_"
            "fresh_jvm_report_mismatch_or_terminal_reset_replay_mismatch_or_"
            "grid_length_mismatch"
        ),
    }
    if rules != expected:
        raise ValueError("M9 planner-trajectory classification drifted")
    planner_only = int(paired["planner_only_win"])
    occupancy = float(paired["median_primary_occupancy_mismatch"])
    distance = float(
        paired["median_primary_normalized_compressed_sequence_distance"]
    )
    strong = (
        valid
        and planner_only >= 15
        and occupancy >= 0.5
        and distance >= 0.5
    )
    low = valid and (planner_only <= 9 or occupancy <= 0.25)
    if not valid:
        signal = "invalid"
    elif strong:
        signal = "trajectory_supervision_signal"
    elif low:
        signal = "low_trajectory_signal"
    else:
        signal = "mixed_trajectory_signal"
    return {
        "valid": valid,
        "signal": signal,
        "trajectory_supervision_signal": strong,
        "low_trajectory_signal": low and not strong,
        "mixed_trajectory_signal": valid and not strong and not low,
        "planner_only_wins": planner_only,
        "median_primary_occupancy_mismatch": occupancy,
        "median_primary_normalized_compressed_sequence_distance": distance,
        "training_authorized": False,
        "new_prospective_adr_authorized": strong,
        "checkpoint_selection_or_promotion_authorized": False,
    }


def run(output: Path, *, java: str, port: int) -> dict[str, Any]:
    root = repo_root()
    protocol, config, seeds = validate_inputs(root)
    _configure_torch(config)
    reports = [
        _run_once(
            root,
            protocol,
            config,
            seeds,
            java=java,
            port=port,
            run_index=index,
            log_dir=output.parent,
        )
        for index in (1, 2)
    ]
    reports_equal = reports[0] == reports[1]
    first = reports[0]
    student = first["policies"]["student"]
    planner = first["policies"]["planner"]
    source = protocol["source_checkpoint"]
    valid = (
        reports_equal
        and first["terminal_reset_replay_equal"]
        and int(student["wins"]) == int(source["expected_public_dev_wins"])
        and float(student["mean_core_health"])
        == float(source["expected_mean_core_health"])
        and int(planner["wins"])
        == int(protocol["planner_policy"]["expected_public_dev_wins"])
        and first["model_state_sha256"] == source["model_state_sha256"]
        and first["optimizer_state_sha256"]
        == source["optimizer_state_sha256"]
        and first["model_or_optimizer_modified"] is False
    )
    result = {
        "schema": "m9_planner_trajectory_divergence_result_v1",
        "implementation_commit": _git_commit(root),
        "protocol_sha256": PROTOCOL_SHA256,
        "data_classification": "public_dev_only",
        "report": first,
        "classification": classify(
            first["paired"], protocol["classification"], valid=valid
        ),
        "fresh_jvm_reports_equal": reports_equal,
        "terminal_reset_replay_equal": first[
            "terminal_reset_replay_equal"
        ],
        "model_or_optimizer_modified": False,
        "target_identifiers_recorded": False,
        "raw_observations_published": False,
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
        default=(
            root / "runs/m9-planner-trajectory-divergence-v1.json"
        ),
    )
    args = parser.parse_args(argv)
    try:
        result = run(args.output.resolve(), java=args.java, port=args.port)
    except Exception as error:
        print(f"M9 PLANNER TRAJECTORY FAIL: {error}", file=sys.stderr)
        return 1
    classification = result["classification"]
    distance = classification[
        "median_primary_normalized_compressed_sequence_distance"
    ]
    print(
        "M9 PLANNER TRAJECTORY "
        f"{'PASS' if classification['valid'] else 'INVALID'} "
        f"signal={classification['signal']} "
        f"planner_only={classification['planner_only_wins']} "
        f"occupancy={classification['median_primary_occupancy_mismatch']:.6f} "
        "distance="
        f"{distance:.6f} "
        f"canonical={result['canonical_report_sha256']}",
        flush=True,
    )
    return 0 if classification["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
