"""Evaluate the public candidate/mask/action seam with the pure greedy policy."""

from __future__ import annotations

import argparse
import sys
import traceback
from typing import Any

from mindustry_agents.evaluation.scripted import EVALUATION_SEEDS
from mindustry_agents.policies import GreedyUtilityPolicy
from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess
from mindustry_agents.tools.expert_common import ScenarioLayout
from mindustry_agents.tools.utility_expert import UtilityExpertEpisode


def _blocked_assignment(response, observations):
    for agent_id, observation in enumerate(observations):
        skill = observation.get("skill", {})
        retry_tick = int(skill.get("next_retry_tick", -1))
        if skill.get("status") != "BLOCKED" or retry_tick <= response.tick:
            continue
        task = next(
            (
                item
                for item in response.task_board
                if int(item.get("owner_agent_id", -1)) == agent_id
                and item.get("status") == "BLOCKED"
            ),
            None,
        )
        if task is not None:
            return agent_id, task, retry_tick
    return None


def _matching_candidate(
    observation: dict[str, Any], task: dict[str, Any]
) -> dict[str, Any]:
    matches = [
        candidate
        for candidate in observation.get("task_candidates", [])
        if candidate.get("task_type") == task.get("task_type")
        and candidate.get("target") == task.get("target")
    ]
    if len(matches) != 1:
        raise AssertionError(
            "expected one regenerated blocked candidate for "
            f"{task.get('task_type')} {task.get('target')!r}, got {matches}"
        )
    return matches[0]


def _check_retry_eligibility(env, seed: int) -> tuple[int, int, int, str]:
    episode = UtilityExpertEpisode(env, seed, blocked_variant=True, require_win=False)
    episode._spend_for_blocked_variant()
    response = episode.response
    blocked = (
        _blocked_assignment(response, episode.observations)
        if response is not None
        else None
    )
    while blocked is None and episode.tick < episode.layout.tick_cap:
        boundary = (
            episode.layout.win_tick
            if episode.tick < episode.layout.win_tick
            else episode.layout.tick_cap
        )
        response = episode.step(
            min(30, boundary - episode.tick),
            episode._policy_actions(),
            event_driven=True,
        )
        blocked = _blocked_assignment(response, episode.observations)
        if response.outcome != "running" and blocked is None:
            break
    if blocked is None:
        raise AssertionError("blocked fixture produced no retryable skill result")

    agent_id, task, retry_tick = blocked
    block_tick = episode.tick
    abandoned = episode.step(
        1,
        [
            {
                "agent_id": agent_id,
                "task_action": {
                    "type": "ABANDON",
                    "reason": "resources_short_replan",
                },
            }
        ],
        event_driven=True,
    )
    if len(abandoned.action_results) != 1 or not abandoned.action_results[0].get(
        "accepted", False
    ):
        raise AssertionError(f"blocked task abandon failed: {abandoned.action_results}")

    candidate = _matching_candidate(episode.observations[agent_id], task)
    candidate_index = int(candidate["index"])
    if not candidate.get("valid", False):
        raise AssertionError(f"retry candidate unexpectedly invalid: {candidate}")
    if episode.action_masks[agent_id]["candidate_task"][candidate_index]:
        raise AssertionError("same blocked work remained selectable before next_retry_tick")
    other_legal = any(
        episode.action_masks[agent_id]["candidate_task"][int(item["index"])]
        and item.get("task_type") != "WAIT"
        and (
            item.get("task_type") != task.get("task_type")
            or item.get("target") != task.get("target")
        )
        for item in episode.observations[agent_id].get("task_candidates", [])
    )
    if not other_legal:
        raise AssertionError("retry mask left no alternative non-WAIT work selectable")

    rejected = episode.step(
        1,
        [
            {
                "agent_id": agent_id,
                "task_action": {
                    "type": "SELECT_CANDIDATE_TASK",
                    "candidate_index": candidate_index,
                },
            }
        ],
    )
    if len(rejected.action_results) != 1 or rejected.action_results[0].get(
        "reason"
    ) != "retry_not_due":
        raise AssertionError(
            f"masked retry bypass was not rejected precisely: {rejected.action_results}"
        )

    if episode.tick < retry_tick:
        episode.step(retry_tick - episode.tick)
    if episode.tick != retry_tick:
        raise AssertionError(
            f"retry boundary advanced to {episode.tick}, expected {retry_tick}"
        )
    candidate = _matching_candidate(episode.observations[agent_id], task)
    candidate_index = int(candidate["index"])
    if not episode.action_masks[agent_id]["candidate_task"][candidate_index]:
        raise AssertionError("same blocked work did not reopen at next_retry_tick")
    accepted = episode.step(
        1,
        [
            {
                "agent_id": agent_id,
                "task_action": {
                    "type": "SELECT_CANDIDATE_TASK",
                    "candidate_index": candidate_index,
                },
            }
        ],
    )
    if len(accepted.action_results) != 1 or not accepted.action_results[0].get(
        "accepted", False
    ):
        raise AssertionError(f"due retry was not accepted: {accepted.action_results}")
    return block_tick, retry_tick, agent_id, str(task["task_type"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check the adaptive public candidate policy")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--java", default="java")
    parser.add_argument("--seeds", nargs="*", type=int, default=list(EVALUATION_SEEDS))
    args = parser.parse_args(argv)
    if not args.seeds:
        parser.error("--seeds must not be empty")

    policy = GreedyUtilityPolicy()
    rows = []
    retry_row = None
    loss_releases = 0
    try:
        with RlServerProcess(LaunchConfig(port=args.port, java=args.java)) as env:
            env.handshake("m7.3-candidate-policy-check")
            for seed in args.seeds:
                reset = env.reset(seed, agent_count=3)
                layout = ScenarioLayout(reset.metadata)
                episode = reset.episode_id
                tick = reset.tick
                observations = reset.initial_observations
                masks = reset.action_masks
                selections = 0
                rejected = 0
                response = None
                while tick < layout.tick_cap:
                    boundary = (
                        layout.win_tick if tick < layout.win_tick else layout.tick_cap
                    )
                    actions = policy.actions(observations, masks)
                    selections += sum(
                        action["task_action"]["type"] == "SELECT_CANDIDATE_TASK"
                        for action in actions
                    )
                    response = env.step(
                        episode,
                        expected_tick=tick,
                        ticks_to_advance=min(30, boundary - tick),
                        agent_actions=actions,
                        stop_on_decision_event=True,
                    )
                    policy.observe_action_results(response.action_results)
                    loss_releases += sum(
                        event.get("act") == "ABANDON"
                        and event.get("reason_code") == "agent_death"
                        for event in response.task_events
                    )
                    rejected += sum(
                        not result.get("accepted", False)
                        for result in response.action_results
                    )
                    tick = response.tick
                    observations = response.observations
                    masks = response.action_masks
                    for agent_id, observation in enumerate(observations):
                        if not observation.get("unit", {}).get("dead", False):
                            continue
                        mask = masks[agent_id]
                        if (
                            any(mask.get("candidate_task", []))
                            or any(
                                mask.get(key, False)
                                for key in (
                                    "continue_current_task",
                                    "abandon",
                                    "request_help",
                                )
                            )
                            or not mask.get("wait", False)
                        ):
                            raise AssertionError(
                                f"dead agent {agent_id} has a non-WAIT action at "
                                f"tick {tick}: {mask}"
                            )
                    if response.outcome != "running":
                        break
                if response is None:
                    raise AssertionError(f"seed {seed} produced no step response")
                team = observations[0]["team"]
                rows.append(
                    (
                        seed,
                        response.outcome,
                        tick,
                        round(float(team["core_health"])),
                        int(team["copper"]),
                        len(team["turrets"]),
                        selections,
                        rejected,
                    )
                )
            retry_row = _check_retry_eligibility(env, args.seeds[0])
    except Exception as exc:
        print(f"CANDIDATE-POLICY FAIL: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1

    print("| seed | outcome | tick | core hp | copper | turrets | selections | rejected |")
    print("|---:|:---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        print(
            f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} "
            f"| {row[5]} | {row[6]} | {row[7]} |"
        )
    wins = sum(row[1] == "win" for row in rows)
    if wins != len(rows):
        print(f"CANDIDATE-POLICY FAIL: wins={wins}/{len(rows)}", file=sys.stderr)
        return 1
    if retry_row is None:
        raise AssertionError("retry eligibility check did not run")
    if 34567 in args.seeds and loss_releases <= 0:
        print(
            "CANDIDATE-POLICY FAIL: fixed loss seed emitted no structured task release",
            file=sys.stderr,
        )
        return 1
    print(
        "retry eligibility: "
        f"agent={retry_row[2]} task={retry_row[3]} "
        f"blocked={retry_row[0]} due={retry_row[1]}"
    )
    print(f"agent-loss releases: {loss_releases}")
    print(f"CANDIDATE-POLICY OK: wins={wins}/{len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
