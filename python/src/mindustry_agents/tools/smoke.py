"""M1 smoke test: one reset/step/close against a live rl-server JVM.

Launches one JVM, handshakes, resets with a fixed seed, steps 600 ticks in
10 chunks of 60, and prints the acceptance transcript (engine identity,
protocol version, episode, seed, reset tick + hash, per-chunk tick + hash,
final observation, and a timing summary). Exits 0 iff the tick advances
exactly 600.

Run: ``python -m mindustry_agents.tools.smoke [--port N] [--seed S]``
"""

from __future__ import annotations

import argparse
import sys

from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess

CHUNK = 60
CHUNKS = 10
TOTAL_TICKS = CHUNK * CHUNKS


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="rl-server M1 smoke test")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--java", default="java")
    args = parser.parse_args(argv)

    print("== rl-server M1 smoke ==")
    with RlServerProcess(LaunchConfig(port=args.port, java=args.java)) as env:
        print(f"launched pid={env.pid} port={args.port}")

        hs = env.handshake()
        print(
            f"handshake: engine={hs.engine_version} commit={hs.engine_commit}\n"
            f"           arc={hs.arc_version} protocol_version={hs.protocol_version} "
            f"jvm_pid={hs.process_id}"
        )
        if hs.protocol_version != 1:
            print(f"FAIL: unexpected protocol version {hs.protocol_version}", file=sys.stderr)
            return 1

        rr = env.reset(root_seed=args.seed, agent_count=2)
        print(
            f"reset:  episode={rr.episode_id} seed={args.seed} tick={rr.tick} "
            f"agents={len(rr.initial_observations)}"
        )
        print(f"        initial_hash={rr.state_hash}")
        print(f"        initial_obs={rr.initial_observations[0]}")
        if rr.tick != 0:
            print(f"FAIL: reset tick is {rr.tick}, expected 0", file=sys.stderr)
            return 1

        tick = rr.tick
        total_engine_ms = 0.0
        total_obs_ms = 0.0
        last: object = None
        for i in range(CHUNKS):
            sr = env.step(rr.episode_id, expected_tick=tick, ticks_to_advance=CHUNK)
            if sr.tick != tick + CHUNK:
                print(
                    f"FAIL: chunk {i}: tick {sr.tick} != expected {tick + CHUNK}",
                    file=sys.stderr,
                )
                return 1
            tick = sr.tick
            total_engine_ms += sr.timing["engine_ms"]
            total_obs_ms += sr.timing["observation_ms"]
            last = sr
            print(
                f"step {i:2d}: {sr.previous_tick:4d} -> {sr.tick:4d}  "
                f"hash={sr.state_hash[:24]}  engine_ms={sr.timing['engine_ms']:.2f}"
            )

        assert last is not None
        print(f"final:  tick={last.tick} obs={last.observations[0]}")
        print(f"        team_state={last.team_state}")
        print(f"        final_hash={last.state_hash}")

        if tick != TOTAL_TICKS:
            print(f"FAIL: final tick {tick} != {TOTAL_TICKS}", file=sys.stderr)
            return 1

        secs = total_engine_ms / 1000.0
        tps = TOTAL_TICKS / secs if secs > 0 else float("inf")
        print(
            f"timing: engine={total_engine_ms:.1f} ms  observation={total_obs_ms:.1f} ms  "
            f"~{tps:,.0f} ticks/sec (engine-only)"
        )

        h = env.health()
        print(f"health: ok={h.ok} uptime_ticks={h.uptime_ticks} episode={h.episode_id}")

    print("SMOKE OK: tick advanced exactly", TOTAL_TICKS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
