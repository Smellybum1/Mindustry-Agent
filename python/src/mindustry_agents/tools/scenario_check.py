"""Scenario phase check: deterministic enemy waves + undefended-core loss.

Runs against a live rl-server JVM loading the full ``bootstrap-defense-v0`` world
(48x48, core at (24,24), east enemy spawn at (46,24), 3-wave dagger schedule at
ticks 2700/4500/6300). It leaves the core **undefended** (agents idle) and asserts:

1. **Waves spawn** — after wave 1's tick (2700) the live wave-team (crux) unit
   count is > 0 (``enemy_count`` in the world observation).
2. **The pathfinder works** — the nearest enemy's distance to the core strictly
   decreases over the following ticks: the daggers actually march the lane toward
   the core (this is the deterministic synchronous flow-field convergence in
   action, docs/UPSTREAM_PATCHES.md).
3. **Undefended loss** — stepping on, the episode terminates with
   ``outcome == "loss"`` (core destroyed) strictly before the tick cap (9000),
   matching the "must build to win" property (docs/SCENARIOS.md arithmetic (c)).

Run: ``python -m mindustry_agents.tools.scenario_check [--port N] [--seed S]``
"""

from __future__ import annotations

import argparse
import sys

from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess

# Wave/termination constants mirror scenarios/bootstrap-defense-v0/scenario.json;
# metadata from the reset response is authoritative and checked against these.
WAVE1_TICK = 2700
TICK_CAP = 9000
WIN_TICK = 8100


def _world(step) -> dict:
    """The shared world/team view (carried under each agent obs' ``team`` key)."""
    return step.observations[0]["team"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="rl-server scenario phase check")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--java", default="java")
    args = parser.parse_args(argv)

    print("== rl-server scenario check (bootstrap-defense-v0, undefended) ==")
    with RlServerProcess(LaunchConfig(port=args.port, java=args.java)) as env:
        print(f"launched pid={env.pid} port={args.port} seed={args.seed}")
        env.handshake()
        rr = env.reset(root_seed=args.seed, agent_count=1)
        md = rr.metadata
        print(f"reset:  episode={rr.episode_id} tick={rr.tick} metadata={md}")
        if rr.tick != 0:
            print(f"FAIL: reset tick {rr.tick} != 0", file=sys.stderr)
            return 1
        # sanity-check the JSON-driven wave/termination metadata
        for key, want in (("initial_wave_tick", WAVE1_TICK), ("win_tick", WIN_TICK), ("tick_cap", TICK_CAP)):
            if md.get(key) != want:
                print(f"FAIL: metadata {key}={md.get(key)} != {want}", file=sys.stderr)
                return 1

        episode = rr.episode_id
        tick = 0

        def advance(to_tick: int, chunk: int = 60):
            nonlocal tick
            last = None
            while tick < to_tick:
                step = min(chunk, to_tick - tick)
                last = env.step(episode, expected_tick=tick, ticks_to_advance=step)
                if last.tick != tick + step:
                    raise AssertionError(f"tick {last.tick} != {tick + step} (non-exact advance)")
                tick = last.tick
            return last

        # --- Phase 1: fast-forward to just past wave 1 and confirm daggers spawned ---
        sr = advance(WAVE1_TICK + 60)
        w = _world(sr)
        enemy_count = int(w["enemy_count"])
        dist_start = float(w["enemy_nearest_core_dist"])
        print(f"post-wave-1 @tick {sr.tick}: enemy_count={enemy_count} "
              f"nearest_core_dist={dist_start:.1f} core_health={w['core_health']:.0f}")
        if enemy_count <= 0:
            print("FAIL: no enemies spawned after wave 1 tick", file=sys.stderr)
            return 1
        if dist_start < 0:
            print("FAIL: no enemy distance reported (daggers missing)", file=sys.stderr)
            return 1

        # --- Phase 2: confirm the daggers MOVE toward the core (pathfinder works) ---
        sr = advance(sr.tick + 300)
        w = _world(sr)
        dist_moved = float(w["enemy_nearest_core_dist"])
        print(f"moved      @tick {sr.tick}: enemy_count={int(w['enemy_count'])} "
              f"nearest_core_dist={dist_moved:.1f} core_health={w['core_health']:.0f}")
        if not (dist_moved < dist_start - 1.0):
            print(
                f"FAIL: enemies did not advance toward the core "
                f"({dist_start:.1f} -> {dist_moved:.1f}); the flow-field pathfinder is not driving movement",
                file=sys.stderr,
            )
            return 1
        print(f"  PATHFINDER OK: nearest enemy closed {dist_start - dist_moved:.1f} units on the core")

        # --- Phase 3: run on (undefended) until the core dies; assert loss < tick cap ---
        loss_tick = None
        outcome = sr.outcome
        while tick < TICK_CAP:
            sr = env.step(episode, expected_tick=tick, ticks_to_advance=30)
            tick = sr.tick
            outcome = sr.outcome
            if any(sr.terminations) or any(sr.truncations):
                loss_tick = sr.tick
                break

        w = _world(sr)
        print(f"terminal   @tick {sr.tick}: outcome={outcome} "
              f"terminations={sr.terminations} truncations={sr.truncations} "
              f"core_health={w['core_health']:.0f}")

        if outcome != "loss":
            print(f"FAIL: undefended episode did not end in loss (outcome={outcome})", file=sys.stderr)
            return 1
        if loss_tick is None or loss_tick >= TICK_CAP:
            print(f"FAIL: loss not reached before tick cap {TICK_CAP} (loss_tick={loss_tick})", file=sys.stderr)
            return 1

        contact_ticks = loss_tick - WAVE1_TICK
        print(
            f"  UNDEFENDED LOSS OK: core destroyed at tick {loss_tick} "
            f"({contact_ticks} ticks / {contact_ticks / 60.0:.1f}s after wave 1 spawn)"
        )

    print("\nSCENARIO OK: waves spawn, daggers path to the core, undefended core is lost before the cap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
