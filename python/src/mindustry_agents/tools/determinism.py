"""M1 determinism harness: same seed + same schedule => identical state hashes.

Three checks (all must pass for exit 0):

1. **Cross-process**: two *fresh* JVM instances, run sequentially with the same
   seed and step schedule, must produce identical hashes at every boundary
   (reset + each chunk). This is the core determinism guarantee (AGENTS.md §3.6).
2. **Reset purity**: inside a single JVM, ``reset(seed)`` twice must yield the
   same initial hash (no cross-episode state leakage).
3. **Tick exactness**: every chunk advances the tick by exactly the requested
   amount.

Run: ``python -m mindustry_agents.tools.determinism [--port N] [--seed S]``
"""

from __future__ import annotations

import argparse
import sys

from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess

CHUNK = 60
CHUNKS = 10
SEED = 12345


def run_schedule(env: RlServerProcess, seed: int) -> list[tuple[str, str]]:
    """Reset with ``seed`` then step ``CHUNKS`` chunks; return labelled hashes."""
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
    return hashes


def _fresh_run(port: int, java: str, seed: int) -> list[tuple[str, str]]:
    with RlServerProcess(LaunchConfig(port=port, java=java)) as env:
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

    ok = cross_ok and purity_ok and reset_consistent
    print("\nDETERMINISM", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
