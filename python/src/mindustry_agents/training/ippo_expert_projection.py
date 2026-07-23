"""ADR-0089 public-only shared-expert candidate-projection diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.training.ippo_ppo import sha256_path


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def classify_projection(
    episodes: list[dict[str, Any]],
    classification: dict[str, Any],
    replay: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Apply only ADR-0089's frozen integer/fraction thresholds."""

    rows = [row for episode in episodes for row in episode["projection_rows"]]
    winning_rows = [
        row
        for episode in episodes
        if episode["outcome"] == "win"
        for row in episode["projection_rows"]
    ]
    unique = sum(int(row["match_count"]) == 1 for row in rows)
    winning_unique = sum(int(row["match_count"]) == 1 for row in winning_rows)
    overall_fraction = unique / len(rows) if rows else 0.0
    winning_fraction = winning_unique / len(winning_rows) if winning_rows else 0.0
    source_wins = sum(episode["outcome"] == "win" for episode in episodes)
    projection_supported = (
        overall_fraction
        >= float(classification["minimum_unique_projection_fraction_all"])
        and winning_fraction
        >= float(
            classification["minimum_unique_projection_fraction_winning_episodes"]
        )
    )
    replay_wins = 0
    replay_retention = 0.0
    replay_supported = False
    if replay is not None:
        replay_wins = sum(episode["outcome"] == "win" for episode in replay)
        replay_retention = replay_wins / source_wins if source_wins else 0.0
        replay_supported = (
            all(episode["all_actions_accepted"] for episode in replay)
            and all(episode["semantic_sequence_parity"] for episode in replay)
            and replay_wins >= int(classification["minimum_projected_replay_wins"])
            and replay_retention
            >= float(
                classification[
                    "minimum_projected_replay_retention_fraction_of_source_wins"
                ]
            )
        )
    passed = projection_supported and replay_supported
    return {
        "source_episodes": len(episodes),
        "source_wins": source_wins,
        "selection_rows": len(rows),
        "unique_projection_rows": unique,
        "unique_projection_fraction_all": overall_fraction,
        "winning_selection_rows": len(winning_rows),
        "winning_unique_projection_rows": winning_unique,
        "unique_projection_fraction_winning_episodes": winning_fraction,
        "projection_thresholds_passed": projection_supported,
        "projected_replay_ran": replay is not None,
        "projected_replay_wins": replay_wins,
        "projected_replay_retention_fraction": replay_retention,
        "projected_replay_thresholds_passed": replay_supported,
        "passed": passed,
        "outcome": classification["pass"] if passed else classification["fail"],
    }


def _collect_episode(env: RlServerProcess, seed: int) -> dict[str, Any]:
    reset = env.reset(
        seed,
        scenario_id="bootstrap-defense-v1",
        scenario_version=2,
        agent_count=3,
        options={
            "shared_expert_policy": True,
            "shared_expert_projection_diagnostic": True,
        },
    )
    tick = reset.tick
    outcome = reset.outcome
    rows = list(reset.shared_expert_projection)
    trace = [
        {
            "tick": tick,
            "state_hash": reset.state_hash,
            "projection_rows": list(reset.shared_expert_projection),
        }
    ]
    while outcome == "running" and tick < int(reset.metadata["tick_cap"]):
        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=int(reset.metadata["tick_cap"]) - tick,
            agent_actions=[],
            stop_on_decision_event=True,
        )
        rows.extend(response.shared_expert_projection)
        trace.append(
            {
                "tick": response.tick,
                "state_hash": response.state_hash,
                "projection_rows": list(response.shared_expert_projection),
                "outcome": response.outcome,
            }
        )
        tick = response.tick
        outcome = response.outcome
    return {
        "seed": seed,
        "outcome": outcome,
        "tick": tick,
        "projection_rows": rows,
        "trace_sha256": _canonical_digest(trace),
    }


def _collect_source(
    *,
    seeds: list[int],
    port: int,
    java: str,
) -> list[dict[str, Any]]:
    with RlServerProcess(LaunchConfig(port=port, java=java)) as env:
        env.handshake("m9-shared-expert-projection-source")
        rows = [_collect_episode(env, seed) for seed in seeds]
        replay = _collect_episode(env, seeds[0])
    if replay != rows[0]:
        raise AssertionError("shared-expert projection terminal-reset replay diverged")
    return rows


def _ordinary_actions(
    observations: list[dict[str, Any]],
    masks: list[dict[str, Any]],
    queues: dict[int, list[dict[str, Any]]],
    offsets: dict[int, int],
) -> list[dict[str, Any]]:
    actions = []
    for agent_id, (observation, mask) in enumerate(zip(observations, masks)):
        if mask.get("continue_current_task", False):
            action = {"type": "CONTINUE_CURRENT_TASK"}
        elif observation.get("unit", {}).get("dead", False):
            action = {"type": "WAIT"}
        elif offsets[agent_id] < len(queues[agent_id]):
            label = queues[agent_id][offsets[agent_id]]
            if int(label["match_count"]) != 1:
                raise AssertionError(
                    f"unprojected expert label for agent {agent_id}: {label}"
                )
            matches = [
                int(candidate["index"])
                for candidate in observation.get("task_candidates", [])
                if candidate.get("task_type") == label["task_type"]
                and candidate.get("target") == label["matched_candidate_target"]
                and int(candidate["index"]) < len(mask.get("candidate_task", []))
                and mask["candidate_task"][int(candidate["index"])]
            ]
            if len(matches) != 1:
                raise AssertionError(
                    f"replay label has {len(matches)} actor-valid matches: {label}"
                )
            action = {
                "type": "SELECT_CANDIDATE_TASK",
                "candidate_index": matches[0],
            }
            offsets[agent_id] += 1
        elif mask.get("wait", False):
            action = {"type": "WAIT"}
        else:
            raise AssertionError(f"agent {agent_id} has no legal replay action")
        actions.append({"agent_id": agent_id, "task_action": action})
    return actions


def _replay_episode(
    env: RlServerProcess,
    source: dict[str, Any],
) -> dict[str, Any]:
    reset = env.reset(
        int(source["seed"]),
        scenario_id="bootstrap-defense-v1",
        scenario_version=2,
        agent_count=3,
    )
    queues = {
        agent_id: [
            row
            for row in source["projection_rows"]
            if int(row["agent_id"]) == agent_id
        ]
        for agent_id in range(3)
    }
    offsets = {agent_id: 0 for agent_id in range(3)}
    observations = reset.initial_observations
    masks = reset.action_masks
    tick = reset.tick
    outcome = reset.outcome
    accepted = True
    trace = []
    while outcome == "running" and tick < int(reset.metadata["tick_cap"]):
        actions = _ordinary_actions(observations, masks, queues, offsets)
        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=int(reset.metadata["tick_cap"]) - tick,
            agent_actions=actions,
            stop_on_decision_event=True,
        )
        accepted = accepted and all(
            result.get("accepted", False) for result in response.action_results
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
        tick = response.tick
        outcome = response.outcome
    parity = all(offsets[agent_id] == len(queues[agent_id]) for agent_id in range(3))
    return {
        "seed": source["seed"],
        "outcome": outcome,
        "tick": tick,
        "all_actions_accepted": accepted,
        "semantic_sequence_parity": parity,
        "consumed_labels": sum(offsets.values()),
        "expected_labels": sum(len(queue) for queue in queues.values()),
        "trace_sha256": _canonical_digest(trace),
    }


def _replay_source(
    *,
    source: list[dict[str, Any]],
    port: int,
    java: str,
) -> list[dict[str, Any]]:
    with RlServerProcess(LaunchConfig(port=port, java=java)) as env:
        env.handshake("m9-shared-expert-projection-replay")
        rows = [_replay_episode(env, episode) for episode in source]
        replay = _replay_episode(env, source[0])
    if replay != rows[0]:
        raise AssertionError("projected ordinary-path terminal-reset replay diverged")
    return rows


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=root
        / "configs/evaluation/m9-shared-expert-candidate-projection-protocol.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "runs/m9-shared-expert-candidate-projection-result.json",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--java", default="java")
    args = parser.parse_args(argv)
    try:
        protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
        seed_path = root / protocol["seed_set"]["path"]
        if sha256_path(seed_path) != protocol["seed_set"]["sha256"]:
            raise ValueError("projection seed document hash drifted")
        if sha256_path(
            root / protocol["source_expert"]["frozen_baseline_report"]
        ) != protocol["source_expert"]["frozen_baseline_report_sha256"]:
            raise ValueError("projection source baseline hash drifted")
        seeds = [
            int(seed)
            for seed in json.loads(seed_path.read_text(encoding="utf-8"))["seeds"]
        ]
        source_a = _collect_source(seeds=seeds, port=args.port, java=args.java)
        source_b = _collect_source(seeds=seeds, port=args.port, java=args.java)
        if source_a != source_b:
            raise AssertionError("fresh-JVM source projection reports diverged")
        provisional = classify_projection(
            source_a, protocol["classification"], replay=None
        )
        replay_a = None
        replay_b = None
        if provisional["projection_thresholds_passed"]:
            replay_a = _replay_source(
                source=source_a, port=args.port, java=args.java
            )
            replay_b = _replay_source(
                source=source_a, port=args.port, java=args.java
            )
            if replay_a != replay_b:
                raise AssertionError("fresh-JVM projected replay reports diverged")
        classification = classify_projection(
            source_a, protocol["classification"], replay_a
        )
        report = {
            "schema": "m9_shared_expert_candidate_projection_result_v1",
            "protocol_sha256": sha256_path(args.protocol),
            "source": source_a,
            "projected_replay": replay_a,
            "classification": classification,
            "fresh_jvm_source_equal": True,
            "fresh_jvm_replay_equal": replay_a is not None and replay_a == replay_b,
            "confirmation_or_held_out_access": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"M9 EXPERT-PROJECTION FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "M9 EXPERT-PROJECTION "
        f"{'OK' if classification['passed'] else 'UNSUPPORTED'} "
        f"unique={classification['unique_projection_rows']}/"
        f"{classification['selection_rows']} "
        f"wins={classification['projected_replay_wins']}/40"
    )
    return 0 if classification["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
