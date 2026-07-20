"""Evaluate the public candidate/mask/action seam with the pure greedy policy."""

from __future__ import annotations

import argparse
import sys

from mindustry_agents.evaluation.scripted import EVALUATION_SEEDS
from mindustry_agents.policies import GreedyUtilityPolicy
from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess
from mindustry_agents.tools.expert_common import ScenarioLayout


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check the M7.3 public candidate policy")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--java", default="java")
    parser.add_argument("--seeds", nargs="*", type=int, default=list(EVALUATION_SEEDS))
    args = parser.parse_args(argv)
    if not args.seeds:
        parser.error("--seeds must not be empty")

    policy = GreedyUtilityPolicy()
    rows = []
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
                    actions = [
                        policy.action(agent_id, observations[agent_id], masks[agent_id])
                        for agent_id in range(len(observations))
                    ]
                    selections += sum(
                        action["task_action"]["type"] == "SELECT_CANDIDATE_TASK"
                        for action in actions
                    )
                    response = env.step(
                        episode,
                        expected_tick=tick,
                        ticks_to_advance=min(30, layout.tick_cap - tick),
                        agent_actions=actions,
                    )
                    rejected += sum(
                        not result.get("accepted", False)
                        for result in response.action_results
                    )
                    tick = response.tick
                    observations = response.observations
                    masks = response.action_masks
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
    except Exception as exc:
        print(f"CANDIDATE-POLICY FAIL: {exc}", file=sys.stderr)
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
    print(f"CANDIDATE-POLICY OK: wins={wins}/{len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
