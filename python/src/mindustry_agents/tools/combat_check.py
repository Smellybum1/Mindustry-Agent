"""Live M4.6 check for deterministic defense and emergency retreat."""

from __future__ import annotations

import argparse
import sys

from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess

WAVE1_TICK = 2700
DEFEND_X = 308
DEFEND_Y = 196


def _world(step) -> dict:
    return step.observations[0]["team"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="rl-server M4.6 combat/retreat check")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--java", default="java")
    args = parser.parse_args(argv)

    print("== rl-server combat + retreat check ==")
    with RlServerProcess(LaunchConfig(port=args.port, java=args.java)) as env:
        env.handshake()

        # RETREAT must cancel an engine-owned build queue and preserve cargo.
        rr = env.reset(root_seed=args.seed, agent_count=1)
        episode = rr.episode_id
        sr = env.step(
            episode,
            expected_tick=0,
            ticks_to_advance=1,
            agent_actions=[
                {
                    "agent_id": 0,
                    "command": {
                        "type": "BUILD",
                        "block": "copper-wall",
                        "tile_x": 30,
                        "tile_y": 24,
                    },
                }
            ],
        )
        queued = int(sr.observations[0]["unit"]["build_queue_depth"])
        plan = sr.observations[0]["unit"].get("build_plan", {})
        progress_before = float(sr.observations[0]["unit"]["build_plan_progress"])
        plan_hash = sr.state_hash
        cargo_before = int(sr.observations[0]["unit"]["item_amount"])
        if queued <= 0:
            print("FAIL: live build plan was not queued before retreat", file=sys.stderr)
            return 1
        if plan.get("block") != "copper-wall" or plan.get("tile_x") != 30:
            print(f"FAIL: current build-plan observation is wrong: {plan}", file=sys.stderr)
            return 1

        tick = sr.tick
        sr = env.step(episode, expected_tick=tick, ticks_to_advance=1)
        tick = sr.tick
        progress_after = float(sr.observations[0]["unit"]["build_plan_progress"])
        if progress_after <= progress_before or sr.state_hash == plan_hash:
            print(
                f"FAIL: build plan/hash did not advance: progress "
                f"{progress_before} -> {progress_after}",
                file=sys.stderr,
            )
            return 1

        sr = env.step(
            episode,
            expected_tick=tick,
            ticks_to_advance=1,
            agent_actions=[{"agent_id": 0, "command": {"type": "RETREAT"}}],
        )
        tick = sr.tick
        if int(sr.observations[0]["unit"]["build_queue_depth"]) != 0:
            print("FAIL: RETREAT did not cancel the live build queue", file=sys.stderr)
            return 1
        while sr.observations[0]["skill"]["status"] == "RUNNING" and tick < 180:
            sr = env.step(episode, expected_tick=tick, ticks_to_advance=10)
            tick = sr.tick
        retreat = sr.observations[0]["skill"]
        cargo_after = int(sr.observations[0]["unit"]["item_amount"])
        if retreat["status"] != "SUCCEEDED" or retreat["reason"] != "RETREATED":
            print(f"FAIL: RETREAT did not reach the core: {retreat}", file=sys.stderr)
            return 1
        if cargo_after != cargo_before:
            print(f"FAIL: RETREAT changed cargo {cargo_before} -> {cargo_after}", file=sys.stderr)
            return 1
        print(
            f"retreat: cancelled queue={queued} plan_progress="
            f"{progress_before:.3f}->{progress_after:.3f} cargo={cargo_after} tick={tick}"
        )

        # DEFEND positions before wave 1, then uses engine aim/fire against daggers.
        rr = env.reset(root_seed=args.seed, agent_count=1)
        episode = rr.episode_id
        tick = 0
        sr = env.step(
            episode,
            expected_tick=tick,
            ticks_to_advance=120,
            agent_actions=[
                {
                    "agent_id": 0,
                    "command": {
                        "type": "NAVIGATE",
                        "x": DEFEND_X,
                        "y": DEFEND_Y,
                        "tolerance": 4,
                    },
                }
            ],
        )
        tick = sr.tick
        if sr.observations[0]["skill"]["status"] != "SUCCEEDED":
            print(f"FAIL: defender did not reach anchor: {sr.observations[0]['skill']}", file=sys.stderr)
            return 1
        first_wave_boundary = WAVE1_TICK + 1
        while tick < first_wave_boundary:
            step = min(300, first_wave_boundary - tick)
            sr = env.step(episode, expected_tick=tick, ticks_to_advance=step)
            tick = sr.tick

        health_before = float(_world(sr)["enemy_total_health"])
        if int(_world(sr)["enemy_count"]) <= 0 or health_before <= 0:
            print("FAIL: wave 1 enemies were not present at the combat boundary", file=sys.stderr)
            return 1

        action = [
            {
                "agent_id": 0,
                "command": {
                    "type": "DEFEND",
                    "x": DEFEND_X,
                    "y": DEFEND_Y,
                    "radius": 160,
                    "ticks": 600,
                },
            }
        ]
        agent_events: list[dict] = []
        for _ in range(20):
            sr = env.step(
                episode,
                expected_tick=tick,
                ticks_to_advance=30,
                agent_actions=action,
            )
            action = []
            tick = sr.tick
            agent_events.extend(
                event
                for event in sr.game_events
                if event.get("type") == "unit_damage" and event.get("agent_id") == 0
            )
            if agent_events and float(_world(sr)["enemy_total_health"]) < health_before:
                break

        health_after = float(_world(sr)["enemy_total_health"])
        if not agent_events:
            print("FAIL: DEFEND produced no agent-attributed damage event", file=sys.stderr)
            return 1
        if not health_after < health_before:
            print(
                f"FAIL: enemy health did not drop {health_before} -> {health_after}; "
                f"events={agent_events}",
                file=sys.stderr,
            )
            return 1
        event = agent_events[0]
        print(
            f"defend: target={event['target_unit_id']} damage={event['nominal_damage']:.0f} "
            f"enemy_health={health_before:.0f}->{health_after:.0f} tick={tick}"
        )

    print("COMBAT OK: retreat cancels plans; deterministic engine fire damages wave units")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
