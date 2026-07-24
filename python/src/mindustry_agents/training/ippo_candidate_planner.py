"""Governed public evaluation for the M9 candidate-native planner."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

from mindustry_agents.policies import (
    CandidateNativePlanner,
    CandidateNativePlannerV2,
    CandidateNativePlannerV3,
    CandidateNativePlannerV4,
)
from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PROTOCOL = (
    ROOT / "configs/evaluation/m9-candidate-native-planner-v1-protocol.json"
)
PROTOCOL_SCHEMAS = {
    "4c1981c4ced305a2966153b6279acd8745e10bd59db7e365e1a91ba763cccedc": (
        "m9_candidate_native_planner_protocol_v1"
    ),
    "411c40c69ac7419fa0920a2270d5b4537a5b0885af52d0abf12a396f0b8a5246": (
        "m9_candidate_native_planner_protocol_v2"
    ),
    "fc8be8ce0bf630152a3f9fa1775ea39b47af741ed894249c275743391f9ff0b8": (
        "m9_candidate_native_planner_protocol_v3"
    ),
    "ffb5bff61b76161e5c7bef3fd520306049ee04a398ba23835af575cd8a7cf1a7": (
        "m9_candidate_native_planner_protocol_v4"
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_protocol(path: Path) -> tuple[dict[str, Any], list[int]]:
    digest = _sha256(path)
    expected_schema = PROTOCOL_SCHEMAS.get(digest)
    if expected_schema is None:
        raise ValueError("candidate-native planner protocol digest is not accepted")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("schema") != expected_schema:
        raise ValueError("unsupported candidate-native planner protocol")
    if protocol.get("data_classification") != "public_dev_only":
        raise ValueError("planner protocol is not public-dev-only")
    authority = protocol.get("authority", {})
    prohibited = (
        "may_modify_model",
        "may_train",
        "may_select_checkpoint",
        "may_promote",
        "may_access_confirmation",
        "may_access_held_out",
        "may_authorize_v7",
    )
    if any(authority.get(key) is not False for key in prohibited):
        raise ValueError("planner protocol grants prohibited authority")
    if expected_schema == "m9_candidate_native_planner_protocol_v2":
        if (
            protocol.get("parent_protocol_sha256")
            != next(iter(PROTOCOL_SCHEMAS))
            or protocol.get("sole_behavior_change")
            != "at_most_one_build_schematic_selection_per_atomic_bundle"
            or protocol.get("planner", {}).get("additional_bundle_constraint")
            != {
                "task_type": "BUILD_SCHEMATIC",
                "maximum_simultaneous_selections": 1,
                "evidence": (
                    "v1_emitted_one_reservation_overlap_rejection_at_"
                    "tick_250_on_each_public_root"
                ),
            }
        ):
            raise ValueError("planner v2 inheritance contract drift")
    if expected_schema == "m9_candidate_native_planner_protocol_v3":
        if (
            protocol.get("parent_protocol_sha256")
            != (
                "411c40c69ac7419fa0920a2270d5b4537a5b0885af52d0ab"
                "f12a396f0b8a5246"
            )
            or protocol.get("sole_behavior_change")
            != (
                "defer_new_build_schematic_while_any_build_line_or_"
                "schematic_task_is_active"
            )
            or protocol.get("planner", {}).get(
                "additional_active_task_constraint"
            )
            != {
                "new_task_type": "BUILD_SCHEMATIC",
                "defer_when_task_board_contains_type": [
                    "BUILD_LINE",
                    "BUILD_SCHEMATIC",
                ],
                "active_statuses": ["CLAIMED", "RUNNING", "BLOCKED"],
                "fallback": (
                    "unchanged_nonconflicting_allocator_without_"
                    "deferred_candidates"
                ),
                "evidence": (
                    "v2_tick_250_selection_overlapped_active_T2_"
                    "build_line_on_every_public_root"
                ),
            }
        ):
            raise ValueError("planner v3 inheritance contract drift")
    if expected_schema == "m9_candidate_native_planner_protocol_v4":
        if (
            protocol.get("parent_protocol_sha256")
            != (
                "fc8be8ce0bf630152a3f9fa1775ea39b47af741ed894249c"
                "275743391f9ff0b8"
            )
            or protocol.get("sole_behavior_change")
            != (
                "prioritize_actionable_supply_over_harvest_during_"
                "active_build_defer"
            )
            or protocol.get("planner", {}).get(
                "active_build_fallback_priority"
            )
            != {
                "preconditions": [
                    "active_build_defer_true",
                    "defense_turret_coverage_greater_than_zero",
                    "defense_ammo_coverage_less_than_one",
                ],
                "task_order": ["SUPPLY_TURRET", "HARVEST_RESOURCE"],
                "evidence": (
                    "v3_replaced_rejected_tick_250_fortification_with_"
                    "harvest_while_two_actionable_supply_targets_existed"
                ),
            }
        ):
            raise ValueError("planner v4 inheritance contract drift")

    seed_spec = protocol["seed_set"]
    seed_path = ROOT / seed_spec["path"]
    if _sha256(seed_path) != seed_spec["sha256"]:
        raise ValueError("planner seed-set digest drift")
    seed_document = json.loads(seed_path.read_text(encoding="utf-8"))
    if seed_document.get("split") != "dev":
        raise ValueError("planner seed set is not public development data")
    seeds = [int(seed) for seed in seed_document["seeds"]]
    if len(seeds) != int(seed_spec["episodes"]) or len(seeds) != len(set(seeds)):
        raise ValueError("planner seed-set cardinality drift")
    return protocol, seeds


def _eligible(
    observation: dict[str, Any], action_mask: dict[str, Any]
) -> bool:
    if observation.get("unit", {}).get("dead", False):
        return False
    if action_mask.get("continue_current_task", False) or action_mask.get(
        "abandon", False
    ):
        return True
    masks = action_mask.get("candidate_task", [])
    return any(
        candidate.get("task_type") != "WAIT"
        and candidate.get("valid") is not False
        and int(candidate.get("index", -1)) < len(masks)
        and int(candidate.get("index", -1)) >= 0
        and masks[int(candidate["index"])]
        for candidate in observation.get("task_candidates", [])
    )


def _bundle_conflicts(
    actions: list[dict[str, Any]], observations: list[dict[str, Any]]
) -> int:
    exclusive_ids: set[str] = set()
    semantics: set[tuple[str, str]] = set()
    conflicts = 0
    for action in actions:
        task_action = action["task_action"]
        if task_action["type"] != "SELECT_CANDIDATE_TASK":
            continue
        agent_id = int(action["agent_id"])
        index = int(task_action["candidate_index"])
        candidate = observations[agent_id]["task_candidates"][index]
        semantic = (
            str(candidate.get("task_type", "")),
            str(candidate.get("target", "")),
        )
        if semantic in semantics:
            conflicts += 1
        semantics.add(semantic)
        if candidate.get("exclusive", False):
            task_id = str(candidate.get("task_id", ""))
            if task_id in exclusive_ids:
                conflicts += 1
            exclusive_ids.add(task_id)
    return conflicts


def _episode(
    env: RlServerProcess,
    *,
    seed: int,
    scenario_id: str,
    scenario_version: int,
    planner_version: int,
) -> dict[str, Any]:
    reset = env.reset(
        seed,
        scenario_id=scenario_id,
        scenario_version=scenario_version,
        agent_count=3,
    )
    planner = {
        1: CandidateNativePlanner,
        2: CandidateNativePlannerV2,
        3: CandidateNativePlannerV3,
        4: CandidateNativePlannerV4,
    }[planner_version]()
    observations = reset.initial_observations
    masks = reset.action_masks
    board: list[dict[str, Any]] = []
    tick = reset.tick
    outcome = "running"
    tick_cap = int(reset.metadata["tick_cap"])
    trace: list[dict[str, Any]] = []
    rejected_actions = 0
    cross_seat_conflicts = 0
    eligible_slots = 0
    non_wait_slots = 0
    selections = 0

    while outcome == "running" and tick < tick_cap:
        actions = planner.actions(observations, masks, board)
        if len(actions) != len(observations):
            raise AssertionError("planner did not emit exactly one action per seat")
        action_types = [action["task_action"]["type"] for action in actions]
        if any(
            action_type
            not in {
                "SELECT_CANDIDATE_TASK",
                "CONTINUE_CURRENT_TASK",
                "ABANDON",
                "WAIT",
            }
            for action_type in action_types
        ):
            raise AssertionError("planner emitted a nonordinary action")
        for agent_id, (observation, action_mask) in enumerate(
            zip(observations, masks, strict=True)
        ):
            if not _eligible(observation, action_mask):
                continue
            eligible_slots += 1
            if actions[agent_id]["task_action"]["type"] != "WAIT":
                non_wait_slots += 1
        selections += action_types.count("SELECT_CANDIDATE_TASK")
        cross_seat_conflicts += _bundle_conflicts(actions, observations)
        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, tick_cap - tick),
            agent_actions=actions,
            stop_on_decision_event=True,
        )
        planner.observe_action_results(response.action_results)
        rejected_actions += sum(
            not result.get("accepted", False)
            for result in response.action_results
        )
        trace.append(
            {
                "tick": tick,
                "next_tick": response.tick,
                "actions": actions,
                "action_results": response.action_results,
                "state_hash": response.state_hash,
                "outcome": response.outcome,
            }
        )
        observations = response.observations
        masks = response.action_masks
        board = response.task_board
        tick = response.tick
        outcome = response.outcome

    coverage = non_wait_slots / eligible_slots if eligible_slots else 1.0
    return {
        "seed": seed,
        "outcome": outcome,
        "tick": tick,
        "trace": trace,
        "trace_sha256": _canonical_sha256(trace),
        "rejected_actions": rejected_actions,
        "cross_seat_exclusive_conflicts": cross_seat_conflicts,
        "eligible_slots": eligible_slots,
        "non_wait_slots": non_wait_slots,
        "non_wait_selection_coverage": coverage,
        "selections": selections,
    }


def _run_fresh(
    *,
    java: str,
    port: int,
    seeds: list[int],
    scenario_id: str,
    scenario_version: int,
    planner_version: int,
) -> dict[str, Any]:
    with RlServerProcess(LaunchConfig(port=port, java=java)) as env:
        env.handshake("m9-candidate-native-planner-v1")
        episodes = [
            _episode(
                env,
                seed=seed,
                scenario_id=scenario_id,
                scenario_version=scenario_version,
                planner_version=planner_version,
            )
            for seed in seeds
        ]
        reset_replay = _episode(
            env,
            seed=seeds[0],
            scenario_id=scenario_id,
            scenario_version=scenario_version,
            planner_version=planner_version,
        )
    replay_equal = reset_replay["trace"] == episodes[0]["trace"]
    return {
        "episodes": episodes,
        "terminal_reset_replay_equal": replay_equal,
        "canonical_sha256": _canonical_sha256(episodes),
    }


def _summarize(
    protocol: dict[str, Any],
    first: dict[str, Any],
    second: dict[str, Any],
) -> dict[str, Any]:
    episodes = first["episodes"]
    wins = sum(episode["outcome"] == "win" for episode in episodes)
    rejected = sum(episode["rejected_actions"] for episode in episodes)
    conflicts = sum(
        episode["cross_seat_exclusive_conflicts"] for episode in episodes
    )
    eligible = sum(episode["eligible_slots"] for episode in episodes)
    non_wait = sum(episode["non_wait_slots"] for episode in episodes)
    coverage = non_wait / eligible if eligible else 1.0
    exact = first == second
    classification = protocol["classification"]
    minimum_retained = math.ceil(
        float(classification["minimum_source_expert_win_retention_fraction"])
        * int(classification["source_expert_wins"])
    )
    passed = (
        exact
        and first["terminal_reset_replay_equal"]
        and rejected == 0
        and conflicts == 0
        and wins >= int(classification["minimum_wins"])
        and wins >= minimum_retained
        and coverage >= float(classification["minimum_non_wait_selection_coverage"])
    )
    return {
        "episodes": len(episodes),
        "wins": wins,
        "losses": len(episodes) - wins,
        "rejected_actions": rejected,
        "cross_seat_exclusive_conflicts": conflicts,
        "eligible_slots": eligible,
        "non_wait_slots": non_wait,
        "non_wait_selection_coverage": coverage,
        "fresh_jvm_reports_equal": exact,
        "terminal_reset_replay_equal": first["terminal_reset_replay_equal"],
        "minimum_retained_wins": minimum_retained,
        "classification": (
            classification["pass"] if passed else classification["fail"]
        ),
        "passed": passed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the frozen M9 candidate-native planner"
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "runs/m9-candidate-native-planner-v1-result.json",
    )
    args = parser.parse_args(argv)

    try:
        protocol, seeds = _load_protocol(args.protocol)
        planner_version = {
            "m9_candidate_native_planner_protocol_v1": 1,
            "m9_candidate_native_planner_protocol_v2": 2,
            "m9_candidate_native_planner_protocol_v3": 3,
            "m9_candidate_native_planner_protocol_v4": 4,
        }[protocol["schema"]]
        values = {
            "java": args.java,
            "port": args.port,
            "seeds": seeds,
            "scenario_id": str(protocol["scenario_id"]),
            "scenario_version": int(protocol["scenario_version"]),
            "planner_version": planner_version,
        }
        first = _run_fresh(**values)
        second = _run_fresh(**values)
        summary = _summarize(protocol, first, second)
        report = {
            "schema": f"m9_candidate_native_planner_result_v{planner_version}",
            "data_classification": "public_dev_only",
            "protocol_sha256": _sha256(args.protocol),
            "summary": summary,
            "fresh_runs": [first, second],
            "confirmation_or_held_out_access": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"M9 CANDIDATE-NATIVE PLANNER FAIL: {exc}", file=sys.stderr)
        return 1

    print(
        "M9 CANDIDATE-NATIVE PLANNER "
        f"{'OK' if summary['passed'] else 'REJECTED'} "
        f"wins={summary['wins']}/{summary['episodes']} "
        f"coverage={summary['non_wait_selection_coverage']:.6f} "
        f"output={args.output}"
    )
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
