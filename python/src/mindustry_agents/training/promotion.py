"""M8.5 train/dev-only mixed-seat ablations and held-out preflight."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch

from mindustry_agents.evaluation.ladder import (
    aggregate_records,
    ladder_episode_record,
    load_seed_set,
)
from mindustry_agents.evaluation.promotion import promotion_preflight
from mindustry_agents.policies import (
    GreedyUtilityPolicy,
    PureGreedyUtilityPolicy,
    RandomValidPolicy,
)
from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.tools.expert_common import EpisodeResult
from mindustry_agents.training.model import SelectorActorCritic
from mindustry_agents.training.checkpoint_interpolation import (
    validate_lineage_manifest,
)
from mindustry_agents.training.ppo_selector import (
    LEARNED_SEAT,
    EpisodeRollout,
    _canonical_scripted_action,
    _configure_torch,
    _git_evidence,
    _scripted_index,
    _sha256,
    load_checkpoint,
    rollout_episode,
)
from mindustry_agents.training.selector import (
    SelectorHistory,
    build_selector_features,
)

CANDIDATE_POLICY = "learned-selector-v2"
GREEDY_MIXED = "greedy-mixed-seat0"
RANDOM_MIXED = "random-mixed-seat0"
PERMANENT_BASELINES = ("random-valid", "greedy-utility")
ALLOWED_DIRTY_PATHS = frozenset(
    {
        "AGENTS.md",
        "annotations/src/main/resources/classids.properties",
        "core/src/mindustry/ai/BlockIndexer.java",
        "core/src/mindustry/entities/Units.java",
    }
)


def rollout_control_episode(
    env: RlServerProcess,
    *,
    seed: int,
    scenario_id: str,
    scenario_version: int,
    control: str,
) -> EpisodeRollout:
    """Run one matched seat-0 control with the learned seat's scripted lifecycle."""

    reset = env.reset(
        seed,
        scenario_id=scenario_id,
        scenario_version=scenario_version,
        agent_count=3,
    )
    observations = reset.initial_observations
    masks = reset.action_masks
    metadata = reset.metadata
    episode_id = reset.episode_id
    tick = reset.tick
    board: list[dict[str, Any]] = []
    boundary_reasons: list[str] = []
    history = SelectorHistory()
    adaptive = GreedyUtilityPolicy()
    selector = (
        PureGreedyUtilityPolicy()
        if control == GREEDY_MIXED
        else RandomValidPolicy(seed)
    )
    trace: list[dict[str, Any]] = []
    task_events: list[dict[str, Any]] = []
    game_events: list[dict[str, Any]] = []
    agent_loss_ticks: dict[int, int] = {}
    previous_dead = [bool(item["unit"]["dead"]) for item in observations]
    outcome = "running"
    final_metrics: dict[str, Any] = {}

    while outcome == "running" and tick < int(metadata["tick_cap"]):
        bundle = adaptive.actions(observations, masks)
        lifecycle_action = bundle[LEARNED_SEAT]
        lifecycle_type = lifecycle_action.get("task_action", {}).get("type")
        features = build_selector_features(
            observations,
            masks,
            metadata,
            task_board=board,
            boundary_reasons=boundary_reasons,
            history=history,
            agent_id=LEARNED_SEAT,
        )
        forced = (
            features.forced_task_action is not None
            or not features.policy_loss_mask
            or lifecycle_type == "ABANDON"
        )
        if forced:
            selected_action = lifecycle_action
        else:
            selected_action = selector.action(
                LEARNED_SEAT, observations[LEARNED_SEAT], masks[LEARNED_SEAT]
            )
            selected_action = _canonical_scripted_action(
                selected_action, observations[LEARNED_SEAT]["task_candidates"]
            )
        bundle[LEARNED_SEAT] = selected_action
        selected_index = _scripted_index(
            selected_action, observations[LEARNED_SEAT]["task_candidates"]
        )

        response = env.step(
            episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, int(metadata["tick_cap"]) - tick),
            agent_actions=bundle,
            stop_on_decision_event=True,
        )
        adaptive.observe_action_results(response.action_results)
        selector.observe_action_results(response.action_results)
        task_events.extend(response.task_events)
        game_events.extend(response.game_events)
        for event in response.game_events:
            if event.get("type") == "unit_destroy" and int(
                event.get("agent_id", -1)
            ) >= 0:
                agent_loss_ticks[int(event["agent_id"])] = int(event["tick"])
        for agent_id, observation in enumerate(response.observations):
            dead = bool(observation["unit"]["dead"])
            if (
                dead
                and not previous_dead[agent_id]
                and agent_id not in agent_loss_ticks
            ):
                agent_loss_ticks[agent_id] = response.tick
            previous_dead[agent_id] = dead

        if selected_action["task_action"]["type"] == "SELECT_CANDIDATE_TASK":
            selected_task_type = observations[LEARNED_SEAT]["task_candidates"][
                selected_index
            ]["task_type"]
            if any(
                int(item.get("agent_id", -1)) == LEARNED_SEAT
                and item.get("accepted", False)
                for item in response.action_results
            ):
                history.record_selection(selected_task_type, tick)

        reasons = list(response.decision_boundary.get("reasons", []))
        trace.append(
            {
                "tick": tick,
                "advanced_ticks": int(
                    response.decision_boundary.get(
                        "advanced_ticks", response.tick - tick
                    )
                ),
                "action": selected_action["task_action"],
                "action_index": selected_index,
                "forced": forced,
                "boundary_reasons": reasons,
                "state_hash": response.state_hash,
                "outcome": response.outcome,
            }
        )
        observations = response.observations
        masks = response.action_masks
        board = response.task_board
        boundary_reasons = reasons
        tick = response.tick
        outcome = response.outcome
        final_metrics = response.coordination_metrics

    return EpisodeRollout(
        seed=seed,
        outcome=outcome,
        tick=tick,
        core_health=float(observations[0]["team"]["core_health"]),
        transitions=[],
        reward_components={},
        trace=trace,
        coordination_metrics=final_metrics,
        task_events=task_events,
        game_events=game_events,
        agent_loss_ticks=agent_loss_ticks,
    )


def _record(
    rollout: EpisodeRollout,
    *,
    policy: str,
    seed_set: dict[str, Any],
    checkpoint_sha256: str,
) -> dict[str, Any]:
    result = EpisodeResult(
        seed=rollout.seed,
        outcome=rollout.outcome,
        tick=rollout.tick,
        core_health=rollout.core_health,
        metrics=rollout.coordination_metrics,
        units_lost=len(rollout.agent_loss_ticks),
        task_events=rollout.task_events,
        game_events=rollout.game_events,
        agent_loss_ticks=rollout.agent_loss_ticks,
    )
    manifest = {
        "policy": policy,
        "policy_version": policy,
        "scenario_id": seed_set["scenario_id"],
        "scenario_version": int(seed_set["scenario_version"]),
        "root_seed": rollout.seed,
        "seed_set_id": seed_set["seed_set_id"],
        "seed_set_version": int(seed_set["seed_set_version"]),
        "checkpoint_sha256": checkpoint_sha256,
        "learned_seat_id": LEARNED_SEAT,
        "scripted_teammates": "adaptive-v1",
    }
    record = ladder_episode_record(result, manifest, seed_set)
    record["decision_trace"] = rollout.trace
    return record


def _load_baselines(path: Path, seed_set: dict[str, Any]) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return [
        item
        for item in document["aggregates"]
        if item["policy"] in PERMANENT_BASELINES
        and item["seed_set"]["id"] == seed_set["seed_set_id"]
        and int(item["seed_set"]["version"]) == int(seed_set["seed_set_version"])
    ]


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description="M8.5 mixed-seat dev preflight")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--lineage-manifest", type=Path, required=True)
    parser.add_argument(
        "--seed-set",
        type=Path,
        default=root / "configs/evaluation/bootstrap-defense-v1-dev-v1.json",
    )
    parser.add_argument(
        "--baseline-aggregate",
        type=Path,
        default=root / "runs/evaluation-ladder-aggregate.json",
    )
    parser.add_argument(
        "--reward-report",
        type=Path,
        default=root / "runs/m8-selector-v1/reward-adversaries.json",
    )
    parser.add_argument(
        "--output", type=Path, default=root / "runs/m8-promotion-dev.jsonl"
    )
    parser.add_argument(
        "--aggregate-output",
        type=Path,
        default=root / "runs/m8-promotion-dev-aggregate.json",
    )
    parser.add_argument(
        "--preflight-output",
        type=Path,
        default=root / "runs/m8-promotion-preflight.json",
    )
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    seed_set = load_seed_set(args.seed_set.resolve())
    if seed_set["split"] == "held-out":
        parser.error("held-out execution is forbidden until dev preflight passes")
    if seed_set["split"] != "dev":
        parser.error("M8.5 promotion preflight requires the governed dev split")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    _configure_torch(config)
    model = SelectorActorCritic(int(config["model_init_seed"]))
    checkpoint_payload = load_checkpoint(args.checkpoint.resolve(), model)
    checkpoint_sha256 = _sha256(args.checkpoint.resolve())
    checkpoint_config_match = checkpoint_payload.get("config_sha256") == _sha256(
        args.config.resolve()
    )
    lineage = validate_lineage_manifest(
        manifest_path=args.lineage_manifest,
        config_path=args.config,
        checkpoint_path=args.checkpoint,
    )
    reward_report = json.loads(args.reward_report.read_text(encoding="utf-8"))
    reward_passed = bool(reward_report.get("pass", False)) and all(
        item.get("pass", False) for item in reward_report.get("cases", [])
    )

    records = []
    generator = torch.Generator().manual_seed(int(config["action_sampling_seed"]))
    with RlServerProcess(
        LaunchConfig(port=args.port, java=args.java, build_if_missing=False)
    ) as env:
        env.handshake("m8.5-promotion-preflight")
        for policy in (CANDIDATE_POLICY, GREEDY_MIXED, RANDOM_MIXED):
            for seed in seed_set["seeds"]:
                if policy == CANDIDATE_POLICY:
                    rollout = rollout_episode(
                        env,
                        model,
                        seed=int(seed),
                        scenario_id=str(seed_set["scenario_id"]),
                        scenario_version=int(seed_set["scenario_version"]),
                        evaluation=True,
                        action_generator=generator,
                    )
                else:
                    rollout = rollout_control_episode(
                        env,
                        seed=int(seed),
                        scenario_id=str(seed_set["scenario_id"]),
                        scenario_version=int(seed_set["scenario_version"]),
                        control=policy,
                    )
                records.append(
                    _record(
                        rollout,
                        policy=policy,
                        seed_set=seed_set,
                        checkpoint_sha256=checkpoint_sha256,
                    )
                )

    mixed_aggregates = aggregate_records(records)
    baseline_aggregates = _load_baselines(args.baseline_aggregate, seed_set)
    if len(baseline_aggregates) != len(PERMANENT_BASELINES):
        raise RuntimeError("permanent dev baselines are missing or stale")
    preflight = promotion_preflight(
        records,
        [*baseline_aggregates, *mixed_aggregates],
        candidate_policy=CANDIDATE_POLICY,
        win_rate_baselines=(*PERMANENT_BASELINES, RANDOM_MIXED, GREEDY_MIXED),
        scorecard_baseline=GREEDY_MIXED,
        reward_adversaries_passed=reward_passed,
    )
    repository = _git_evidence(root)
    unexpected_dirty = [
        line
        for line in repository["status"]
        if line[3:].replace("\\", "/") not in ALLOWED_DIRTY_PATHS
    ]
    preflight.update(
        {
            "checkpoint": {
                "path": str(args.checkpoint.resolve()),
                "sha256": checkpoint_sha256,
                "config_sha256": checkpoint_payload.get("config_sha256"),
                "config_match": checkpoint_config_match,
            },
            "lineage": lineage,
            "repository": {
                **repository,
                "unexpected_dirty": unexpected_dirty,
                "frozen": not unexpected_dirty,
            },
            "sources": {
                "baseline_aggregate": str(args.baseline_aggregate.resolve()),
                "baseline_aggregate_sha256": _sha256(args.baseline_aggregate.resolve()),
                "reward_report": str(args.reward_report.resolve()),
                "reward_report_sha256": _sha256(args.reward_report.resolve()),
            },
        }
    )
    preflight["eligible_for_held_out"] = bool(
        preflight["eligible_for_held_out"]
        and checkpoint_config_match
        and not unexpected_dirty
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(
            json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n"
            for item in records
        ),
        encoding="utf-8",
    )
    args.aggregate_output.write_text(
        json.dumps(
            {"aggregates": [*baseline_aggregates, *mixed_aggregates]},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    args.preflight_output.write_text(
        json.dumps(preflight, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for item in preflight["win_rate_comparisons"]:
        print(
            f"{item['candidate']} vs {item['baseline']}: {item['status']}"
        )
    print(
        "held_out_eligible="
        f"{preflight['eligible_for_held_out']} checkpoint={checkpoint_sha256[:16]}"
    )
    print("M8-PROMOTION-PREFLIGHT OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
