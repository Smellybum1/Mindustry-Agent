"""Milestone 4 live acceptance: one-agent defended wave and omitted-defense loss."""

from __future__ import annotations

import argparse
import sys

from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
)

WAVE1_TICK = 2700
WAVE2_TICK = 4500
TICK_CAP = 9000
CORE_FULL_HEALTH = 1100.0


def _skill(step) -> dict:
    return step.observations[0]["skill"]


def _team(step) -> dict:
    return step.observations[0]["team"]


def _drive_skill(env, episode: str, tick: int, action: dict, chunk: int, limit: int):
    actions = [{"agent_id": 0, "command": action}]
    for _ in range(limit):
        step = env.step(
            episode,
            expected_tick=tick,
            ticks_to_advance=chunk,
            agent_actions=actions,
        )
        actions = []
        tick = step.tick
        if _skill(step)["status"] in {"SUCCEEDED", "BLOCKED", "FAILED"}:
            return step, tick
    raise AssertionError(
        f"{action['type']} did not terminate within {chunk * limit} ticks: "
        f"skill={_skill(step)} unit={step.observations[0]['unit']}"
    )


def _defended_run(env, seed: int) -> bool:
    rr = env.reset(root_seed=seed, agent_count=1)
    episode = rr.episode_id
    tick = rr.tick
    copper_before = int(rr.initial_observations[0]["team"]["copper"])

    step, tick = _drive_skill(
        env,
        episode,
        tick,
        {"type": "MINE", "tile_x": 32, "tile_y": 32, "amount": 20},
        30,
        40,
    )
    mined = int(step.observations[0]["unit"]["item_amount"])
    if _skill(step)["status"] != "SUCCEEDED" or mined < 18:
        print(f"FAIL: setup mining failed: skill={_skill(step)} cargo={mined}", file=sys.stderr)
        return False
    step, tick = _drive_skill(
        env, episode, tick, {"type": "DELIVER_CORE"}, 10, 20
    )
    delivered_total = int(_team(step)["copper"])
    if _skill(step)["status"] != "SUCCEEDED" or delivered_total != copper_before + mined:
        print(f"FAIL: setup delivery failed: {_skill(step)} team={_team(step)}", file=sys.stderr)
        return False

    step, tick = _drive_skill(
        env,
        episode,
        tick,
        {"type": "SCHEMATIC", "name": "east_duo_v1", "tile_x": 32, "tile_y": 24},
        30,
        30,
    )
    if _skill(step)["status"] != "SUCCEEDED" or _skill(step)["reason"] != "BUILT":
        print(f"FAIL: one-agent schematic failed: {_skill(step)}", file=sys.stderr)
        return False

    # The base schematic remains the authoritative seven-block build. Add a legal
    # closed core bulwark so the flat map's open walk-around routes cannot
    # touch the core before the finite starting magazines clear wave 1.
    reinforcement_tiles = (
        [(26, y) for y in range(22, 27)]
        + [(22, y) for y in range(22, 27)]
        + [(x, 22) for x in range(23, 26)]
        + [(x, 26) for x in range(23, 26)]
        + [(27, y) for y in range(21, 28)]
    )
    for tile_x, tile_y in reinforcement_tiles:
        step, tick = _drive_skill(
            env,
            episode,
            tick,
            {
                "type": "BUILD",
                "block": "copper-wall",
                "tile_x": tile_x,
                "tile_y": tile_y,
                "rotation": 0,
            },
            30,
            20,
        )
        if _skill(step)["status"] != "SUCCEEDED":
            print(
                f"FAIL: lane reinforcement failed at ({tile_x},{tile_y}): {_skill(step)}",
                file=sys.stderr,
            )
            return False

    delivered = 0
    for tile_y in (23, 25):
        step, tick = _drive_skill(
            env,
            episode,
            tick,
            {
                "type": "SUPPLY",
                "item": "copper",
                "tile_x": 32,
                "tile_y": tile_y,
                "amount": 30,
            },
            10,
            10,
        )
        skill = _skill(step)
        if skill["status"] != "SUCCEEDED" or skill["reason"] != "SUPPLIED":
            print(f"FAIL: one-agent supply failed at y={tile_y}: {skill}", file=sys.stderr)
            return False
        delivered += int(skill.get("delivered", 0))

    copper_after = int(_team(step)["copper"])
    ammo_before_wave = [int(t["total_ammo"]) for t in _team(step)["turrets"]]
    expected_spend = 100 + len(reinforcement_tiles) * 6 + 30
    ledger_spend = copper_before + mined - copper_after
    if ledger_spend != expected_spend or delivered != 30 or ammo_before_wave != [30, 30]:
        print(
            f"FAIL: defended setup ledger mismatch copper={copper_before}->{copper_after} "
            f"delivered={delivered} ammo={ammo_before_wave}",
            file=sys.stderr,
        )
        return False

    defend = [
        {
            "agent_id": 0,
            "command": {
                "type": "DEFEND",
                "x": 260,
                "y": 196,
                "radius": 180,
                "ticks": 3600,
            },
        }
    ]
    agent_hits = 0
    while tick < WAVE1_TICK + 1:
        advance = min(120, WAVE1_TICK + 1 - tick)
        step = env.step(
            episode,
            expected_tick=tick,
            ticks_to_advance=advance,
            agent_actions=defend,
        )
        defend = []
        tick = step.tick
        agent_hits += sum(event.get("agent_id") == 0 for event in step.game_events)

    if int(_team(step)["enemy_count"]) <= 0:
        print("FAIL: defended run did not spawn wave 1", file=sys.stderr)
        return False

    while tick < WAVE2_TICK and int(_team(step)["enemy_count"]) > 0:
        step = env.step(episode, expected_tick=tick, ticks_to_advance=30)
        tick = step.tick
        agent_hits += sum(
            event.get("type") == "unit_damage" and event.get("agent_id") == 0
            for event in step.game_events
        )

    core_health = float(_team(step)["core_health"])
    remaining = int(_team(step)["enemy_count"])
    ammo_after_wave = [int(t["total_ammo"]) for t in _team(step)["turrets"]]
    if remaining != 0:
        print(
            f"FAIL: defended wave 1 was not cleared before wave 2 "
            f"(remaining={remaining})",
            file=sys.stderr,
        )
        return False
    if core_health != CORE_FULL_HEALTH:
        print(
            f"FAIL: defended core was damaged: {core_health}; clear_tick={tick} "
            f"ammo={ammo_after_wave} agent_hits={agent_hits}",
            file=sys.stderr,
        )
        return False
    if step.outcome != "running":
        print(f"FAIL: defended run terminated unexpectedly: {step.outcome}", file=sys.stderr)
        return False
    print(
        f"defended: built={7 + len(reinforcement_tiles)} supplied={delivered} "
        f"mined={mined} copper={copper_before}->{copper_after} "
        f"ammo={ammo_before_wave}->{ammo_after_wave} wave1_clear_tick={tick} "
        f"agent_hits={agent_hits} core_health={core_health:.0f}"
    )
    return True


def _omitted_defense_run(env, seed: int) -> bool:
    rr = env.reset(root_seed=seed, agent_count=1)
    episode = rr.episode_id
    tick = rr.tick
    step = None
    while tick < TICK_CAP:
        step = env.step(episode, expected_tick=tick, ticks_to_advance=30)
        tick = step.tick
        if any(step.terminations) or any(step.truncations):
            break
    assert step is not None
    if step.outcome != "loss" or tick >= TICK_CAP:
        print(
            f"FAIL: defense-omitted run did not lose before cap: "
            f"outcome={step.outcome} tick={tick}",
            file=sys.stderr,
        )
        return False
    print(f"omitted:  outcome=loss tick={tick} core_health={_team(step)['core_health']:.0f}")
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Milestone 4 live acceptance")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--java", default="java")
    args = parser.parse_args(argv)

    print("== Milestone 4 acceptance ==")
    with RlServerProcess(LaunchConfig(port=args.port, java=args.java)) as env:
        env.handshake()
        if not _defended_run(env, args.seed):
            return 1
        if not _omitted_defense_run(env, args.seed):
            return 1

    print("M4 ACCEPTANCE OK: one agent protects an untouched core; omission still loses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
