"""M1/M3 determinism harness: same seed + same schedule => identical state hashes.

Three checks (all must pass for exit 0):

1. **Cross-process**: two *fresh* JVM instances, run sequentially with the same
   seed and step schedule, must produce identical hashes at every boundary
   (reset + each plain chunk + each scripted skill step). This is the core
   determinism guarantee (AGENTS.md §3.6). Since M3 the schedule includes the
   scripted mine/deliver trace, so this now covers the skill state machines and
   their engine effects (mining accrual, deferred transfers, core handoff).
2. **Reset purity**: inside a single JVM, ``reset(seed)`` twice must yield the
   same initial hash (no cross-episode state leakage — agent units are respawned).
3. **Tick exactness**: every chunk advances the tick by exactly the requested
   amount.

Run: ``python -m mindustry_agents.tools.determinism [--port N] [--seed S]``
"""

from __future__ import annotations

import argparse
import sys

from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess
from mindustry_agents.tools import skill_trace

CHUNK = 60
CHUNKS = 10
SEED = 12345

# Scenario phase: step past wave 1 (spawn tick 2700), then place a wall in the
# approach lane at tick 2880. The remaining window proves the tile-change refresh
# and enemy re-path are deterministic, not merely static-map flow-field movement.
WALL_TICK = 2880
POSTWAVE_TARGET = 3300
WALL_TILE = (33, 24)


def _test_wall_action() -> list[dict]:
    return [
        {
            "agent_id": 0,
            "command": {
                "type": "TEST_PLACE_WALL",
                "tile_x": WALL_TILE[0],
                "tile_y": WALL_TILE[1],
            },
        }
    ]


def run_schedule(env: RlServerProcess, seed: int) -> list[tuple[str, str]]:
    """Reset with ``seed``, step the plain chunks, replay the scripted skill trace,
    then idle past wave 1 while enemies spawn/move; return labelled hashes at every
    boundary."""
    hashes: list[tuple[str, str]] = []
    rr = env.reset(root_seed=seed, agent_count=2)
    if rr.tick != 0:
        raise AssertionError(f"reset tick {rr.tick} != 0")
    hashes.append(("reset@0", rr.state_hash))
    tick = 0
    for _ in range(CHUNKS):
        sr = env.step(rr.episode_id, expected_tick=tick, ticks_to_advance=CHUNK)
        if sr.tick != tick + CHUNK:
            raise AssertionError(f"tick {sr.tick} != {tick + CHUNK} (non-exact advance)")
        tick = sr.tick
        hashes.append((f"tick@{tick}", sr.state_hash))

    # M3: the scripted mine/deliver trace — exercises the skill FSMs deterministically.
    for label, actions, ticks in skill_trace.scripted_steps():
        sr = env.step(
            rr.episode_id, expected_tick=tick, ticks_to_advance=ticks, agent_actions=actions
        )
        if sr.tick != tick + ticks:
            raise AssertionError(f"tick {sr.tick} != {tick + ticks} (non-exact advance)")
        tick = sr.tick
        hashes.append((f"{label}@{tick}", sr.state_hash))

    # Scenario phase 1: idle until the daggers are moving toward the lane wall.
    while tick < WALL_TICK:
        step = min(CHUNK, WALL_TICK - tick)
        sr = env.step(rr.episode_id, expected_tick=tick, ticks_to_advance=step)
        if sr.tick != tick + step:
            raise AssertionError(f"tick {sr.tick} != {tick + step} (non-exact advance)")
        tick = sr.tick
        hashes.append((f"wave@{tick}", sr.state_hash))

    before_dist = float(sr.observations[0]["team"]["enemy_nearest_core_dist"])

    # M4.1: place a pathfinding-relevant wall after wave 1 has spawned. This test
    # hook is JVM-property gated and replaced by the legal BUILD skill in M4.2.
    sr = env.step(
        rr.episode_id,
        expected_tick=tick,
        ticks_to_advance=1,
        agent_actions=_test_wall_action(),
    )
    if not sr.action_results or not sr.action_results[0].get("accepted"):
        raise AssertionError(f"test wall placement rejected: {sr.action_results}")
    tick = sr.tick
    hashes.append((f"wall@{tick}", sr.state_hash))

    # Continue while the daggers encounter and route around the new wall. Their
    # nearest-core distance must keep falling, proving the refreshed field is live.
    while tick < POSTWAVE_TARGET:
        step = min(CHUNK, POSTWAVE_TARGET - tick)
        sr = env.step(rr.episode_id, expected_tick=tick, ticks_to_advance=step)
        if sr.tick != tick + step:
            raise AssertionError(f"tick {sr.tick} != {tick + step} (non-exact advance)")
        tick = sr.tick
        hashes.append((f"repath@{tick}", sr.state_hash))
    after_dist = float(sr.observations[0]["team"]["enemy_nearest_core_dist"])
    if not 0 <= after_dist < before_dist:
        raise AssertionError(
            f"daggers did not continue around wall: nearest-core distance {before_dist} -> {after_dist}"
        )
    return hashes


def _fresh_run(port: int, java: str, seed: int) -> list[tuple[str, str]]:
    config = LaunchConfig(
        port=port,
        java=java,
        jvm_args=("-Dmindustry.rl.testHooks=true",),
    )
    with RlServerProcess(config) as env:
        env.handshake()
        return run_schedule(env, seed)


def _diff(a: list[tuple[str, str]], b: list[tuple[str, str]]) -> list[str]:
    problems = []
    for (la, ha), (lb, hb) in zip(a, b):
        mark = "ok " if ha == hb else "MISMATCH"
        if ha != hb:
            problems.append(f"  [{mark}] {la}: {ha}  !=  {hb}")
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="rl-server M1 determinism harness")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--java", default="java")
    args = parser.parse_args(argv)

    print("== rl-server M1 determinism ==")
    print(f"seed={args.seed} schedule={CHUNKS}x{CHUNK} ticks")

    # --- Check 1: two fresh JVM instances -------------------------------
    print("\n[1] cross-process (two fresh JVMs, same seed)")
    run_a = _fresh_run(args.port, args.java, args.seed)
    print(f"    JVM A: {len(run_a)} hashes, final={run_a[-1][1][:24]}")
    run_b = _fresh_run(args.port, args.java, args.seed)
    print(f"    JVM B: {len(run_b)} hashes, final={run_b[-1][1][:24]}")

    cross_ok = [h for _, h in run_a] == [h for _, h in run_b]
    if cross_ok:
        print("    PASS: all hashes identical across processes")
    else:
        print("    FAIL: cross-process hash mismatch", file=sys.stderr)
        for line in _diff(run_a, run_b):
            print(line, file=sys.stderr)

    # --- Check 2: reset purity within one JVM ---------------------------
    print("\n[2] reset purity (two resets in one JVM, same seed)")
    with RlServerProcess(LaunchConfig(port=args.port, java=args.java)) as env:
        env.handshake()
        first = env.reset(root_seed=args.seed, agent_count=2)
        second = env.reset(root_seed=args.seed, agent_count=2)
        purity_ok = first.state_hash == second.state_hash
        print(f"    reset#1 initial_hash={first.state_hash[:24]}")
        print(f"    reset#2 initial_hash={second.state_hash[:24]}")
        if purity_ok:
            print("    PASS: repeated reset produces identical initial hash")
        else:
            print("    FAIL: reset is not pure (state leaked across episodes)", file=sys.stderr)

    # --- Check 3: also confirm reset purity matches the cross-process reset hash
    reset_consistent = run_a[0][1] == first.state_hash
    if not reset_consistent:
        print(
            f"    NOTE: fresh-JVM reset hash {run_a[0][1][:24]} != "
            f"in-JVM reset hash {first.state_hash[:24]}",
            file=sys.stderr,
        )

    # --- Check 4: seed sensitivity (now that enemy waves are live) --------
    # Same seed -> identical (covered by check 1); a *different* seed must now
    # diverge, because the wave spawn spread is seeded from root_seed.
    print("\n[4] seed sensitivity (different seed => different post-wave hash)")
    other_seed = args.seed + 987654321
    run_c = _fresh_run(args.port, args.java, other_seed)
    same_pre_wave = run_a[0][1] == run_c[0][1]  # reset hash: seed-independent (no RNG yet)
    seed_sensitive = run_a[-1][1] != run_c[-1][1]
    print(f"    seed {args.seed}: final={run_a[-1][1][:24]}")
    print(f"    seed {other_seed}: final={run_c[-1][1][:24]}")
    if seed_sensitive:
        print("    PASS: different seeds diverge once enemies spawn (spawn spread is seeded)")
    else:
        print("    FAIL: different seeds produced identical post-wave hashes", file=sys.stderr)
    if same_pre_wave:
        print("    (note: reset hashes match -- nothing consumes root_seed before wave 1)")

    ok = cross_ok and purity_ok and reset_consistent and seed_sensitive
    print("\nDETERMINISM", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
