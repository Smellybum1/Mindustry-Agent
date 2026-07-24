"""Run ADR-0121's immutable semantic-target disagreement diagnostic."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from mindustry_agents.policies import CandidateNativePlannerV11
from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.training.candidate_critical_disagreement import (
    _load_model,
    validate_inputs as validate_critical_inputs,
)
from mindustry_agents.training.candidate_distill import (
    _canonical_sha256,
    _configure_torch,
    _git_commit,
    _write_json,
)
from mindustry_agents.training.candidate_distill_agreement import action_task
from mindustry_agents.training.candidate_on_policy_relabel import teacher_labels
from mindustry_agents.training.ippo import (
    SharedRecurrentSelector,
    SharedSeatState,
    commit_all_seat_boundary,
    decide_all_seats,
    model_state_digest,
)
from mindustry_agents.training.ippo_ppo import sha256_path
from mindustry_agents.training.selector import TASK_TYPES, UTILITY_FIELDS


PROTOCOL_RELATIVE = (
    "configs/evaluation/m9-candidate-semantic-target-diagnostic-protocol.json"
)
PROTOCOL_SHA256 = (
    "8003d7ef159cf9940d1898aa7c2bc380dda8d1846e5a26ddd58c6ef0a9827ee9"
)
SOURCE_RESULT_SHA256 = (
    "464ab91a13c4ca370b0b4fb5f016e45b96c23a3a56ff3ebdac38342adde7b4a1"
)
FEATURE_NAMES = (
    *UTILITY_FIELDS,
    *(f"task_type:{name}" for name in TASK_TYPES),
    "priority",
    "estimated_ticks",
    "estimated_copper",
    "helpers_requested",
    "dependency_count",
    "exclusive",
    "semantic_task_active",
    "semantic_task_owned_by_other",
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
    """Fail closed over the prospective protocol and rejected source."""

    protocol_path = root / PROTOCOL_RELATIVE
    if sha256_path(protocol_path) != PROTOCOL_SHA256:
        raise ValueError("M9 semantic-target protocol hash drifted")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    execution = protocol.get("execution", {})
    expected_execution = {
        "fresh_jvm_runs": 2,
        "student_controls_environment": True,
        "student_action_mode": "deterministic_argmax",
        "teacher_labels_same_pre_action_student_visited_boundary": True,
        "teacher_action_execution": False,
        "eligible_boundary": (
            "alive_and_no_forced_task_action_and_teacher_action_"
            "authoritatively_legal"
        ),
        "scope": "all_disagreements_with_same_task_family_subset",
        "semantic_candidate_identity_fields": [
            "task_type",
            "task_id",
            "target",
        ],
        "feature_comparison": "exact_37_float_selector_candidate_row",
        "terminal_reset_replay": True,
        "exact_report_identity_required": True,
        "measurements": [
            "semantic_target_pair_confusion_by_outcome",
            "task_id_pair_confusion_by_outcome",
            "same_family_disagreements_by_agent_and_outcome",
            "same_family_exact_feature_row_aliases_by_outcome",
            "same_family_feature_delta_fields_by_outcome",
            "first_same_family_disagreement_on_losses",
        ],
    }
    expected_classification = {
        "top_semantic_target_pairs": 3,
        "minimum_top_target_pair_fraction_for_concentration": 0.5,
        "minimum_exact_feature_alias_fraction": 0.5,
        "target_pair_concentration_signal": (
            "top_three_semantic_target_pairs_cover_threshold_of_"
            "same_family_disagreements"
        ),
        "feature_alias_signal": (
            "exact_37_float_rows_cover_threshold_of_"
            "same_family_disagreements"
        ),
        "feature_distinguishable_ranking_signal": (
            "same_family_disagreements_exist_and_feature_alias_signal_is_false"
        ),
    }
    if (
        protocol.get("schema")
        != "m9_candidate_semantic_target_diagnostic_protocol_v1"
        or protocol.get("data_classification") != "public_dev_only"
        or protocol.get("split") != "dev"
        or protocol.get("authority") != _expected_authority()
        or execution != expected_execution
        or protocol.get("classification") != expected_classification
    ):
        raise ValueError("M9 semantic-target authority drifted")

    source_path = root / str(protocol["source_diagnostic_result"])
    if (
        protocol.get("source_diagnostic_result_sha256")
        != SOURCE_RESULT_SHA256
        or sha256_path(source_path) != SOURCE_RESULT_SHA256
    ):
        raise ValueError("M9 semantic-target source result drifted")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if (
        source.get("classification", {}).get(
            "concentrated_critical_error_signal"
        )
        is not True
        or source.get("fresh_jvm_reports_equal") is not True
        or source.get("terminal_reset_replay_equal") is not True
        or source.get("confirmation_or_held_out_access") is not False
    ):
        raise ValueError("M9 semantic-target source signal is invalid")

    critical_protocol, config, seeds = validate_critical_inputs(root)
    critical_checkpoint = critical_protocol["checkpoints"][1]
    if (
        any(
            critical_checkpoint.get(key) != value
            for key, value in protocol.get("checkpoint", {}).items()
        )
        or protocol.get("seed_set") != critical_protocol["seed_set"]
        or protocol.get("seed_set_sha256")
        != critical_protocol["seed_set_sha256"]
        or protocol.get("scenario_id") != config["scenario_id"]
        or int(protocol.get("scenario_version", -1))
        != int(config["scenario_version"])
    ):
        raise ValueError("M9 semantic-target frozen source drifted")
    return protocol, config, seeds


def classify(
    report: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    """Apply ADR-0121's exact target concentration and alias thresholds."""

    if (
        int(rules.get("top_semantic_target_pairs", -1)) != 3
        or float(
            rules.get(
                "minimum_top_target_pair_fraction_for_concentration",
                -1.0,
            )
        )
        != 0.5
        or float(rules.get("minimum_exact_feature_alias_fraction", -1.0))
        != 0.5
    ):
        raise ValueError("M9 semantic-target thresholds drifted")
    same_family = int(report.get("same_family_disagreements", 0))
    aliases = int(report.get("same_family_exact_feature_row_aliases", -1))
    if same_family <= 0 or not 0 <= aliases <= same_family:
        raise ValueError("M9 semantic-target metrics are invalid")
    target_counts: Counter[str] = Counter()
    for key, value in report[
        "semantic_target_pair_confusion_by_outcome"
    ].items():
        target_counts[key.rsplit(":", 1)[0]] += int(value)
    top_fraction = (
        sum(value for _, value in target_counts.most_common(3)) / same_family
    )
    alias_fraction = aliases / same_family
    target_signal = top_fraction >= 0.5
    alias_signal = alias_fraction >= 0.5
    distinguishable_signal = not alias_signal
    return {
        "top_three_semantic_target_pair_fraction": top_fraction,
        "exact_feature_alias_fraction": alias_fraction,
        "target_pair_concentration_signal": target_signal,
        "feature_alias_signal": alias_signal,
        "feature_distinguishable_ranking_signal": distinguishable_signal,
        "active_signals": [
            name
            for name, active in (
                ("target_pair_concentration_signal", target_signal),
                ("feature_alias_signal", alias_signal),
                (
                    "feature_distinguishable_ranking_signal",
                    distinguishable_signal,
                ),
            )
            if active
        ],
        "successor_training_authorized": False,
        "checkpoint_selection_authorized": False,
        "promotion_authorized": False,
    }


def _candidate(
    index: int,
    observation: dict[str, Any],
) -> dict[str, str]:
    if index == 8:
        return {
            "task_type": "CONTINUE_CURRENT_TASK",
            "task_id": "",
            "target": "",
        }
    if index == 9:
        return {"task_type": "WAIT", "task_id": "", "target": ""}
    candidates = observation.get("task_candidates", [])
    if index < 0 or index >= len(candidates):
        raise ValueError("M9 semantic-target action has no candidate")
    item = candidates[index]
    return {
        "task_type": action_task(index, observation),
        "task_id": str(item.get("task_id", "")),
        "target": str(item.get("target", "")),
    }


def _pair(left: str, right: str) -> str:
    return json.dumps([left, right], ensure_ascii=True, separators=(",", ":"))


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
    disagreements = 0
    same_family = 0
    aliases = 0
    target_pairs: Counter[str] = Counter()
    task_id_pairs: Counter[str] = Counter()
    agents: Counter[str] = Counter()
    delta_fields: Counter[str] = Counter()
    first_same: dict[str, Any] | None = None
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
        labels_by_agent = teacher_labels(decision, teacher, observations)
        for agent_id, label in labels_by_agent.items():
            labels += 1
            predicted = decision.action_indices[agent_id]
            if predicted == label:
                continue
            disagreements += 1
            teacher_item = _candidate(label, observations[agent_id])
            student_item = _candidate(predicted, observations[agent_id])
            if teacher_item["task_type"] != student_item["task_type"]:
                continue
            same_family += 1
            target_pair = _pair(
                teacher_item["target"], student_item["target"]
            )
            task_id_pair = _pair(
                teacher_item["task_id"], student_item["task_id"]
            )
            target_pairs[target_pair] += 1
            task_id_pairs[task_id_pair] += 1
            agents[str(agent_id)] += 1
            teacher_row = decision.features[agent_id].candidates[label]
            student_row = decision.features[agent_id].candidates[predicted]
            if teacher_row == student_row:
                aliases += 1
            else:
                for name, left, right in zip(
                    FEATURE_NAMES,
                    teacher_row,
                    student_row,
                    strict=True,
                ):
                    if left != right:
                        delta_fields[name] += 1
            if first_same is None:
                first_same = {
                    "tick": tick,
                    "agent_id": agent_id,
                    "teacher_action_index": label,
                    "student_action_index": predicted,
                    "teacher_candidate": teacher_item,
                    "student_candidate": student_item,
                    "exact_feature_row_alias": teacher_row == student_row,
                }

        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, int(metadata["tick_cap"]) - tick),
            agent_actions=decision.agent_actions,
            stop_on_decision_event=True,
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
        raise RuntimeError("M9 semantic-target episode was incomplete")
    return {
        "seed": seed,
        "outcome": outcome,
        "tick": tick,
        "core_health": float(observations[0]["team"]["core_health"]),
        "eligible_labels": labels,
        "disagreements": disagreements,
        "same_family_disagreements": same_family,
        "exact_feature_row_aliases": aliases,
        "target_pairs": dict(sorted(target_pairs.items())),
        "task_id_pairs": dict(sorted(task_id_pairs.items())),
        "same_family_by_agent": dict(sorted(agents.items())),
        "feature_delta_fields": dict(sorted(delta_fields.items())),
        "first_same_family_disagreement": first_same,
        "trace_sha256": _canonical_sha256(trace),
    }


def _aggregate(episodes: Sequence[dict[str, Any]]) -> dict[str, Any]:
    outcomes: Counter[str] = Counter()
    targets: Counter[str] = Counter()
    task_ids: Counter[str] = Counter()
    agents: Counter[str] = Counter()
    aliases: Counter[str] = Counter()
    deltas: Counter[str] = Counter()
    first_losses: Counter[str] = Counter()
    for episode in episodes:
        outcome = str(episode["outcome"])
        outcomes[outcome] += 1
        for key, value in episode["target_pairs"].items():
            targets[f"{key}:{outcome}"] += int(value)
        for key, value in episode["task_id_pairs"].items():
            task_ids[f"{key}:{outcome}"] += int(value)
        for key, value in episode["same_family_by_agent"].items():
            agents[f"agent_{key}:{outcome}"] += int(value)
        aliases[outcome] += int(episode["exact_feature_row_aliases"])
        for key, value in episode["feature_delta_fields"].items():
            deltas[f"{key}:{outcome}"] += int(value)
        first = episode["first_same_family_disagreement"]
        if outcome == "loss" and first is not None:
            first_losses[
                _pair(
                    first["teacher_candidate"]["target"],
                    first["student_candidate"]["target"],
                )
            ] += 1
    return {
        "episodes": len(episodes),
        "wins": outcomes["win"],
        "losses": outcomes["loss"],
        "eligible_labels": sum(
            int(item["eligible_labels"]) for item in episodes
        ),
        "disagreements": sum(
            int(item["disagreements"]) for item in episodes
        ),
        "same_family_disagreements": sum(
            int(item["same_family_disagreements"]) for item in episodes
        ),
        "same_family_exact_feature_row_aliases": sum(aliases.values()),
        "semantic_target_pair_confusion_by_outcome": dict(sorted(targets.items())),
        "task_id_pair_confusion_by_outcome": dict(sorted(task_ids.items())),
        "same_family_disagreements_by_agent_and_outcome": dict(
            sorted(agents.items())
        ),
        "same_family_exact_feature_row_aliases_by_outcome": dict(
            sorted(aliases.items())
        ),
        "same_family_feature_delta_fields_by_outcome": dict(
            sorted(deltas.items())
        ),
        "first_same_family_disagreement_on_losses": dict(
            sorted(first_losses.items())
        ),
        "episode_digest": _canonical_sha256(
            [
                {
                    "seed": item["seed"],
                    "outcome": item["outcome"],
                    "tick": item["tick"],
                    "core_health": item["core_health"],
                    "eligible_labels": item["eligible_labels"],
                    "disagreements": item["disagreements"],
                    "same_family_disagreements": item[
                        "same_family_disagreements"
                    ],
                    "first_same_family_disagreement": item[
                        "first_same_family_disagreement"
                    ],
                    "trace_sha256": item["trace_sha256"],
                }
                for item in episodes
            ]
        ),
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
    with RlServerProcess(
        LaunchConfig(
            port=port,
            java=java,
            build_if_missing=False,
            log_dir=log_dir,
            log_name=f"semantic-target-jvm-{run_index}",
        )
    ) as env:
        env.handshake("m9-candidate-semantic-target")
        episodes = []
        for index, seed in enumerate(seeds, start=1):
            episodes.append(_episode(env, model, config, seed=int(seed)))
            if index % 10 == 0:
                print(
                    f"M9 SEMANTIC TARGET JVM={run_index}/2 "
                    f"episode={index}/{len(seeds)}",
                    flush=True,
                )
        replay = _episode(env, model, config, seed=int(seeds[0]))
    if replay != episodes[0]:
        raise RuntimeError("M9 semantic-target terminal replay diverged")
    if model_state_digest(model) != initial_digest:
        raise RuntimeError("M9 semantic-target mutated an immutable model")
    return {
        "candidate": checkpoint["candidate"],
        "lineage_update": int(checkpoint["lineage_update"]),
        "autonomous_public_dev_wins": int(
            checkpoint["autonomous_public_dev_wins"]
        ),
        **_aggregate(episodes),
        "terminal_reset_replay_equal": True,
    }


def run(output: Path, *, java: str, port: int) -> dict[str, Any]:
    root = repo_root()
    protocol, config, seeds = validate_inputs(root)
    _configure_torch(config)
    reports = [
        _run_once(
            root,
            protocol["checkpoint"],
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
        raise RuntimeError("M9 semantic-target fresh JVM reports diverged")
    result = {
        "schema": "m9_candidate_semantic_target_diagnostic_result_v1",
        "implementation_commit": _git_commit(root),
        "protocol_sha256": PROTOCOL_SHA256,
        "data_classification": "public_dev_only",
        "checkpoint": reports[0],
        "classification": classify(
            reports[0], protocol["classification"]
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
        default=root / "runs/m9-candidate-semantic-target-diagnostic.json",
    )
    args = parser.parse_args(argv)
    try:
        result = run(args.output.resolve(), java=args.java, port=args.port)
    except Exception as error:
        print(f"M9 SEMANTIC TARGET FAIL: {error}", file=sys.stderr)
        return 1
    report = result["checkpoint"]
    print(
        "M9 SEMANTIC TARGET PASS "
        f"same_family={report['same_family_disagreements']} "
        f"aliases={report['same_family_exact_feature_row_aliases']} "
        f"canonical={result['canonical_report_sha256']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
