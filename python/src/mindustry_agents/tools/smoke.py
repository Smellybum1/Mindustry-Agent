"""M1/M3 smoke test: reset/step/close against a live rl-server JVM.

Launches one JVM, handshakes, resets with a fixed seed, steps 600 ticks in
10 chunks of 60 (the plain M1 phase), then runs the M3 scripted skill phase:
``agent_0`` mines copper and delivers it to the core while ``agent_1`` targets a
non-ore tile. It prints the acceptance transcript and — the core honesty check —
asserts the core copper increases by **exactly** the amount delivered, sourced
from real engine observations, with the full ledger printed. Exits 0 iff both the
600-tick advance and the mine/deliver ledger balance.

Run: ``python -m mindustry_agents.tools.smoke [--port N] [--seed S]``
"""

from __future__ import annotations

import argparse
import sys

from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess
from mindustry_agents.tools import skill_trace

CHUNK = 60
CHUNKS = 10
TOTAL_TICKS = CHUNK * CHUNKS


def _agent_obs(step, index):
    """Return the per-agent observation dict for ``index``."""
    return step.observations[index]


def _core_copper(step):
    """Read the core's copper count from the shared team view in agent_0's obs."""
    return int(step.observations[0]["team"]["copper"])


def _skill(step, index):
    return step.observations[index]["skill"]


def _cargo(step, index):
    return int(step.observations[index]["unit"]["item_amount"])


def run_skill_phase(env, episode_id: str, start_tick: int) -> int:
    """Run the scripted mine/deliver trace; assert the honesty ledger. 0 on success."""
    print("\n== M3 scripted skill phase ==")
    steps = skill_trace.scripted_steps()

    tick = start_tick
    last_status = {0: None, 1: None}
    core_before_mining = None
    agent1_blocked_reason = None
    pre_deliver = None  # last observation of the mine phase (before DELIVER executes)
    last = None

    for label, actions, ticks in steps:
        sr = env.step(episode_id, expected_tick=tick, ticks_to_advance=ticks, agent_actions=actions)
        if sr.tick != tick + ticks:
            print(f"FAIL: {label}: tick {sr.tick} != {tick + ticks}", file=sys.stderr)
            return 1
        tick = sr.tick
        if core_before_mining is None:
            core_before_mining = _core_copper(sr)

        if actions:
            print(f"  actions@{tick}: {sr.action_results}")

        for idx in (0, 1):
            sk = _skill(sr, idx)
            key = (sk["type"], sk["status"], sk["reason"])
            if key != last_status[idx]:
                print(
                    f"  agent_{idx} @tick {tick:4d}: {sk['type'] or '-':12s} "
                    f"{sk['status']:9s} reason={sk['reason']:14s} "
                    f"progress={sk['progress']:.2f} cargo={_cargo(sr, idx)}"
                )
                last_status[idx] = key
            if idx == 1 and sk["status"] == "BLOCKED":
                agent1_blocked_reason = sk["reason"]

        if label.startswith("mine"):
            pre_deliver = sr
        last = sr

    # --- honesty ledger: core delta must equal exactly the carried (mined) amount ---
    mined = _cargo(pre_deliver, 0)
    core_before_deliver = _core_copper(pre_deliver)
    core_after = _core_copper(last)
    cargo_after = _cargo(last, 0)
    delivered = core_after - core_before_deliver

    print("\n-- ledger (all values from real engine observations) --")
    print(f"  core copper before mining         : {core_before_mining}")
    print(f"  agent_0 cargo mined (pre-deliver)  : {mined}")
    print(f"  core copper before deliver         : {core_before_deliver}")
    print(f"  core copper after deliver          : {core_after}")
    print(f"  core delta (after - before deliver): {delivered}")
    print(f"  agent_0 cargo after deliver        : {cargo_after}")
    print(f"  agent_1 mine(non-ore) blocked      : {agent1_blocked_reason}")

    ok = True
    if mined <= 0:
        print(f"FAIL: agent_0 mined nothing (cargo={mined})", file=sys.stderr)
        ok = False
    if core_before_deliver != core_before_mining:
        print(
            f"FAIL: core copper changed during mining "
            f"({core_before_mining} -> {core_before_deliver}); mining leaked into core",
            file=sys.stderr,
        )
        ok = False
    if delivered != mined:
        print(
            f"FAIL: core gained {delivered} copper but agent delivered {mined} "
            f"(ledger does not balance)",
            file=sys.stderr,
        )
        ok = False
    if cargo_after != 0:
        print(f"FAIL: agent_0 still carries {cargo_after} after delivery", file=sys.stderr)
        ok = False
    if agent1_blocked_reason != "INVALID_TARGET":
        print(
            f"FAIL: agent_1 invalid-target mine did not BLOCK(INVALID_TARGET) "
            f"(got {agent1_blocked_reason})",
            file=sys.stderr,
        )
        ok = False

    if ok:
        print(
            f"  BALANCE OK: core copper increased by exactly {delivered}, "
            f"equal to the {mined} mined and delivered by agent_0 (cargo now 0)"
        )
    return 0 if ok else 1


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

        # --- M3 scripted skill phase (mine -> deliver, with honesty ledger) ---
        skill_rc = run_skill_phase(env, rr.episode_id, tick)
        if skill_rc != 0:
            print("SKILL PHASE FAILED", file=sys.stderr)
            return skill_rc

        h = env.health()
        print(f"health: ok={h.ok} uptime_ticks={h.uptime_ticks} episode={h.episode_id}")

    print("\nSMOKE OK: 600-tick advance + mine/deliver ledger balanced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
