"""Run ADR-0115's immutable candidate-distillation agreement diagnostic."""

from __future__ import annotations

import argparse
import json
import math
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
    CONFIG_SHA256,
    DEV_MAXIMUM,
    DEV_MINIMUM,
    _canonical_sha256,
    _configure_torch,
    _git_commit,
    _load_seed_set,
    _write_json,
    load_distillation_config,
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
    "m9-candidate-distill-v1-agreement-diagnostic-protocol.json"
)
PROTOCOL_SHA256 = (
    "f779cd313fcd46da5335787b931f746f3d42881a722213392e302dc2e2e895d6"
)
SOURCE_RESULT_SHA256 = (
    "47ced62d5b7e3c15c980415bc3c05974bfacfd1ccbfd7e2af6c7f474486af590"
)
CONFIG_RELATIVE = "configs/training/m9-candidate-native-distill-v1.json"


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
    """Validate the frozen public sources before starting a JVM."""

    protocol_path = root / PROTOCOL_RELATIVE
    if sha256_path(protocol_path) != PROTOCOL_SHA256:
        raise ValueError("M9 distillation agreement protocol hash drifted")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    execution = protocol.get("execution", {})
    expected_execution = {
        "fresh_jvm_runs": 2,
        "teacher_controls_environment": True,
        "student_hidden_state": "private_per_seat_zero_on_reset_or_death",
        "eligible_boundary": (
            "alive_and_no_forced_task_action_and_teacher_action_"
            "authoritatively_legal"
        ),
        "forced_controls": "executed_but_excluded_from_agreement",
        "student_action_mode": "deterministic_argmax",
        "measurements": [
            "eligible_labels",
            "teacher_label_nll",
            "top1_agreement",
            "teacher_task_to_student_task_confusion",
            "teacher_action_to_student_action_confusion",
        ],
        "terminal_reset_replay": True,
        "exact_report_identity_required": True,
    }
    if (
        protocol.get("schema")
        != "m9_candidate_native_distillation_agreement_diagnostic_protocol_v1"
        or protocol.get("candidate_version")
        != "m9-candidate-native-distill-v1"
        or protocol.get("data_classification") != "public_dev_only"
        or protocol.get("split") != "dev"
        or protocol.get("teacher_policy")
        != "candidate-native-planner-v11-single-defender"
        or protocol.get("authority") != _expected_authority()
        or execution != expected_execution
    ):
        raise ValueError("M9 distillation agreement authority drifted")

    result_path = root / str(protocol["source_result"])
    if (
        str(protocol.get("source_result_sha256")) != SOURCE_RESULT_SHA256
        or sha256_path(result_path) != SOURCE_RESULT_SHA256
    ):
        raise ValueError("M9 distillation agreement source result drifted")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if (
        result.get("schema")
        != "m9_candidate_native_distillation_construction_result_v1"
        or result.get("replica_a", {}).get("construction_passed") is not False
        or result.get("replica_a", {}).get("selected_checkpoint") is not None
        or result.get("replica_b_authorized") is not False
        or result.get("confirmation_or_held_out_access") is not False
    ):
        raise ValueError("M9 distillation agreement source is not rejected")

    expected = {
        3: result["replica_a"]["best_public_dev"],
        32: result["replica_a"]["final_public_dev"],
    }
    checkpoints = protocol.get("checkpoints", [])
    if [int(item.get("update", -1)) for item in checkpoints] != [3, 32]:
        raise ValueError("M9 distillation agreement checkpoint order drifted")
    for checkpoint in checkpoints:
        update = int(checkpoint["update"])
        row = expected[update]
        path = root / str(checkpoint["path"])
        if (
            sha256_path(path) != checkpoint["file_sha256"]
            or checkpoint["file_sha256"] != row["checkpoint_file_sha256"]
            or checkpoint["content_sha256"]
            != row["checkpoint_content_sha256"]
            or int(checkpoint["autonomous_public_dev_wins"])
            != int(row["wins"])
        ):
            raise ValueError(
                "M9 distillation agreement checkpoint identity drifted"
            )

    config = load_distillation_config(root / CONFIG_RELATIVE)
    if config["dev_seed_set"] != protocol["seed_set"]:
        raise ValueError("M9 distillation agreement dev seed path drifted")
    dev_set, _ = _load_seed_set(
        root,
        str(protocol["seed_set"]),
        split="dev",
        count=40,
        lower=DEV_MINIMUM,
        upper=DEV_MAXIMUM,
    )
    return protocol, config, [int(seed) for seed in dev_set["seeds"]]


def action_task(index: int, observation: dict[str, Any]) -> str:
    """Render an ordinary action index as its structured task family."""

    if index == 8:
        return "CONTINUE_CURRENT_TASK"
    if index == 9:
        return "WAIT"
    candidates = observation.get("task_candidates", [])
    if index < 0 or index >= len(candidates):
        raise ValueError("M9 agreement action index has no candidate")
    task_type = str(candidates[index].get("task_type", ""))
    if not task_type:
        raise ValueError("M9 agreement candidate has no task type")
    return task_type


def classify(
    checkpoints: Sequence[dict[str, Any]],
    rules: dict[str, Any],
) -> dict[str, Any]:
    """Apply the exact ADR-0115 signal thresholds."""

    minimum = float(
        rules.get("teacher_forced_fit_retained", {}).get(
            "minimum_top1_agreement", -1.0
        )
    )
    maximum = float(
        rules.get("teacher_forced_fit_retained", {}).get(
            "maximum_teacher_label_nll", -1.0
        )
    )
    if minimum != 0.9 or maximum != 0.35:
        raise ValueError("M9 distillation agreement thresholds drifted")
    if [int(item.get("update", -1)) for item in checkpoints] != [3, 32]:
        raise ValueError("M9 distillation agreement result order drifted")

    retained = []
    for item in checkpoints:
        labels = int(item.get("eligible_labels", 0))
        top1 = float(item.get("top1_agreement", -1.0))
        nll = float(item.get("teacher_label_nll", -1.0))
        wins = int(item.get("autonomous_public_dev_wins", -1))
        if (
            labels <= 0
            or not 0.0 <= top1 <= 1.0
            or not math.isfinite(nll)
            or nll < 0.0
            or not 0 <= wins <= 40
        ):
            raise ValueError("M9 distillation agreement metrics are invalid")
        retained.append(top1 >= minimum and nll <= maximum)

    closed_loop = any(
        fit and int(item["autonomous_public_dev_wins"]) < 30
        for fit, item in zip(retained, checkpoints, strict=True)
    )
    forgetting = (
        float(checkpoints[1]["top1_agreement"])
        <= float(checkpoints[0]["top1_agreement"]) - 0.05
    )
    generalization_gap = not any(retained)
    signals = {
        "teacher_forced_fit_retained_by_update": {
            "3": retained[0],
            "32": retained[1],
        },
        "closed_loop_shift_signal": closed_loop,
        "forgetting_signal": forgetting,
        "generalization_gap_signal": generalization_gap,
    }
    active = [
        name
        for name in (
            "closed_loop_shift_signal",
            "forgetting_signal",
            "generalization_gap_signal",
        )
        if signals[name]
    ]
    return {
        **signals,
        "active_signals": active,
        "successor_training_authorized": False,
        "checkpoint_selection_authorized": False,
        "promotion_authorized": False,
    }


def _prediction(
    model: SharedRecurrentSelector,
    decision: Any,
    agent_id: int,
) -> int:
    features = decision.features[agent_id]
    with torch.no_grad():
        _, logits, _, _ = model(
            torch.tensor([features.candidates], dtype=torch.float32),
            torch.tensor([features.scalars], dtype=torch.float32),
            torch.tensor(
                [features.candidate_present], dtype=torch.bool
            ),
            torch.tensor([features.action_mask], dtype=torch.bool),
            torch.tensor([agent_id], dtype=torch.long),
            decision.hidden_inputs[agent_id][None, :],
        )
    return int(torch.argmax(logits[0]).item())


def _episode(
    env: RlServerProcess,
    models: dict[int, SharedRecurrentSelector],
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
    states = {update: SharedSeatState.fresh() for update in models}
    planner = CandidateNativePlannerV11()
    observations = reset.initial_observations
    masks = reset.action_masks
    metadata = reset.metadata
    board: list[dict[str, Any]] = []
    reasons: list[str] = []
    tick = reset.tick
    outcome = reset.outcome
    forced_controls = 0
    trace: list[dict[str, Any]] = []
    measurements = {
        update: {
            "eligible_labels": 0,
            "top1_matches": 0,
            "teacher_nll_sum": 0.0,
            "task_confusion": Counter(),
            "action_confusion": Counter(),
        }
        for update in models
    }

    while outcome == "running" and tick < int(metadata["tick_cap"]):
        teacher = planner.actions(observations, masks, board)
        decisions = {
            update: decide_all_seats(
                model,
                states[update],
                observations,
                masks,
                metadata,
                task_board=board,
                boundary_reasons=reasons,
                evaluation=True,
                teacher_actions=teacher,
            )
            for update, model in models.items()
        }
        reference = decisions[min(decisions)]
        if any(
            decision.agent_actions != reference.agent_actions
            for decision in decisions.values()
        ):
            raise RuntimeError("M9 agreement teacher bundles diverged")

        boundary_forced = 0
        for agent_id in reference.evaluation_order:
            features = reference.features[agent_id]
            label = reference.action_indices[agent_id]
            action_type = reference.agent_actions[agent_id].get(
                "task_action", {}
            ).get("type")
            eligible = (
                features.forced_task_action is None
                and action_type
                in {
                    "SELECT_CANDIDATE_TASK",
                    "CONTINUE_CURRENT_TASK",
                    "WAIT",
                }
                and bool(features.action_mask[label])
            )
            if not eligible:
                boundary_forced += 1
                continue
            teacher_task = action_task(label, observations[agent_id])
            for update, model in models.items():
                decision = decisions[update]
                predicted = _prediction(model, decision, agent_id)
                student_task = action_task(predicted, observations[agent_id])
                row = measurements[update]
                row["eligible_labels"] += 1
                row["top1_matches"] += predicted == label
                row["teacher_nll_sum"] += -float(
                    decision.old_log_probabilities[agent_id]
                )
                row["task_confusion"][
                    f"{teacher_task}->{student_task}"
                ] += 1
                row["action_confusion"][f"{label}->{predicted}"] += 1
        forced_controls += boundary_forced

        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, int(metadata["tick_cap"]) - tick),
            agent_actions=reference.agent_actions,
            stop_on_decision_event=True,
        )
        if any(
            not result.get("accepted", False)
            for result in response.action_results
        ):
            raise RuntimeError("M9 agreement teacher action was rejected")
        planner.observe_action_results(response.action_results)
        for update, decision in decisions.items():
            commit_all_seat_boundary(
                states[update],
                decision,
                response.action_results,
                observations,
                tick=tick,
            )
        trace.append(
            {
                "tick": tick,
                "next_tick": response.tick,
                "actions": reference.agent_actions,
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

    if outcome == "running":
        raise RuntimeError("M9 agreement teacher episode was incomplete")
    return {
        "seed": seed,
        "outcome": outcome,
        "tick": tick,
        "core_health": float(observations[0]["team"]["core_health"]),
        "forced_controls": forced_controls,
        "trace_sha256": _canonical_sha256(trace),
        "checkpoints": {
            str(update): {
                "eligible_labels": int(row["eligible_labels"]),
                "top1_matches": int(row["top1_matches"]),
                "teacher_nll_sum": float(row["teacher_nll_sum"]),
                "task_confusion": dict(sorted(row["task_confusion"].items())),
                "action_confusion": dict(
                    sorted(row["action_confusion"].items())
                ),
            }
            for update, row in measurements.items()
        },
    }


def _merge_counts(
    episodes: Sequence[dict[str, Any]],
    update: int,
) -> dict[str, Any]:
    labels = 0
    matches = 0
    nll = 0.0
    task_confusion: Counter[str] = Counter()
    action_confusion: Counter[str] = Counter()
    for episode in episodes:
        row = episode["checkpoints"][str(update)]
        labels += int(row["eligible_labels"])
        matches += int(row["top1_matches"])
        nll += float(row["teacher_nll_sum"])
        task_confusion.update(row["task_confusion"])
        action_confusion.update(row["action_confusion"])
    if labels <= 0:
        raise RuntimeError("M9 agreement run produced no eligible labels")
    return {
        "eligible_labels": labels,
        "top1_matches": matches,
        "top1_agreement": matches / labels,
        "teacher_label_nll": nll / labels,
        "teacher_task_to_student_task_confusion": dict(
            sorted(task_confusion.items())
        ),
        "teacher_action_to_student_action_confusion": dict(
            sorted(action_confusion.items())
        ),
    }


def _load_models(
    root: Path,
    protocol: dict[str, Any],
    config: dict[str, Any],
) -> dict[int, SharedRecurrentSelector]:
    models = {}
    for checkpoint in protocol["checkpoints"]:
        update = int(checkpoint["update"])
        model = SharedRecurrentSelector(int(config["model_init_seed"]))
        payload = load_ippo_checkpoint(
            root / str(checkpoint["path"]),
            model,
            expected_config_sha256=CONFIG_SHA256,
        )
        if (
            int(payload["update"]) != update
            or payload["checkpoint_content_sha256"]
            != checkpoint["content_sha256"]
            or model_state_digest(model)
            != (
                "d23d2b4add58bae8af756e5476ba93398bbf036927268dab3d63dfccf61d0cde"
                if update == 3
                else "c13e3858bd37c89ff5582a3e861c709808f6a3088e444fed8da5130362332c14"
            )
        ):
            raise ValueError("M9 agreement loaded checkpoint identity drifted")
        model.eval()
        models[update] = model
    return models


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
    models = _load_models(root, protocol, config)
    initial_digests = {
        update: model_state_digest(model) for update, model in models.items()
    }
    with RlServerProcess(
        LaunchConfig(
            port=port,
            java=java,
            build_if_missing=False,
            log_dir=log_dir,
            log_name=f"agreement-jvm-{run_index}",
        )
    ) as env:
        env.handshake("m9-candidate-distill-v1-agreement")
        episodes = []
        for index, seed in enumerate(seeds, start=1):
            episodes.append(
                _episode(env, models, config, seed=int(seed))
            )
            if index % 10 == 0:
                print(
                    f"M9 AGREEMENT JVM={run_index}/2 "
                    f"episode={index}/{len(seeds)}",
                    flush=True,
                )
        replay = _episode(env, models, config, seed=int(seeds[0]))
    if replay != episodes[0]:
        raise RuntimeError("M9 agreement terminal reset replay diverged")
    if any(
        model_state_digest(model) != initial_digests[update]
        for update, model in models.items()
    ):
        raise RuntimeError("M9 agreement mutated an immutable model")

    checkpoints = []
    by_update = {
        int(item["update"]): item for item in protocol["checkpoints"]
    }
    for update in (3, 32):
        checkpoints.append(
            {
                "update": update,
                "autonomous_public_dev_wins": int(
                    by_update[update]["autonomous_public_dev_wins"]
                ),
                **_merge_counts(episodes, update),
            }
        )
    return {
        "teacher": {
            "episodes": len(episodes),
            "wins": sum(item["outcome"] == "win" for item in episodes),
            "losses": sum(item["outcome"] != "win" for item in episodes),
            "forced_controls": sum(
                int(item["forced_controls"]) for item in episodes
            ),
            "episode_digest": _canonical_sha256(
                [
                    {
                        "seed": item["seed"],
                        "outcome": item["outcome"],
                        "tick": item["tick"],
                        "core_health": item["core_health"],
                        "trace_sha256": item["trace_sha256"],
                    }
                    for item in episodes
                ]
            ),
        },
        "checkpoints": checkpoints,
        "terminal_reset_replay_equal": True,
    }


def run(
    output: Path,
    *,
    java: str,
    port: int,
) -> dict[str, Any]:
    """Execute both exact fresh-JVM reports and classify only their signals."""

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
    if reports[0] != reports[1]:
        raise RuntimeError("M9 agreement fresh JVM reports diverged")
    result = {
        "schema": "m9_candidate_native_distillation_agreement_result_v1",
        "implementation_commit": _git_commit(root),
        "protocol_sha256": PROTOCOL_SHA256,
        "source_result_sha256": SOURCE_RESULT_SHA256,
        "data_classification": "public_dev_only",
        **reports[0],
        "classification": classify(
            reports[0]["checkpoints"], protocol["classification"]
        ),
        "fresh_jvm_reports_equal": True,
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
        / "runs/m9-candidate-distill-v1-agreement-diagnostic.json",
    )
    args = parser.parse_args(argv)
    try:
        result = run(
            args.output.resolve(),
            java=args.java,
            port=args.port,
        )
    except Exception as error:
        print(f"M9 AGREEMENT FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "M9 AGREEMENT OK "
        f"signals={','.join(result['classification']['active_signals']) or 'none'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
