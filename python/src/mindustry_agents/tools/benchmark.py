"""M2 benchmark: single-env speed, 1/2/4-JVM scaling, and protocol overhead.

Three layers, measured separately (brief §24 — never conflate layers):

(a) **single-env** — engine-only ticks/sec (``--steps`` chunks of ``--chunk``
    no-op ticks, warm JVM), plus reset latency (median).
(b) **scaling** — aggregate ticks/sec with 1, 2, and 4 concurrent JVMs, stepped
    in lockstep by a :class:`VectorCollector`; reports per-JVM efficiency.
(c) **protocol overhead** — client round-trip wall time minus the server-reported
    engine+observation time, as a percentage of round-trip (Gate 6 target < 10%).

Prints a markdown table to stdout; total runtime is a couple of minutes (well
under the 10-minute budget). The 4-JVM ceiling is deliberate: this is a shared
workstation (see ``docs/BENCHMARKS.md`` M2 notes).

Run: ``python -m mindustry_agents.tools.benchmark [--java java] [--base-port N]``
"""

from __future__ import annotations

import argparse
import os
import platform
import statistics
import time

from mindustry_agents.env.vector import VectorCollector
from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess
from mindustry_agents.process.supervisor import (
    ProcessSupervisor,
    SupervisorConfig,
    _is_port_free,
)


def _probe_free_port(start: int) -> int:
    for candidate in range(start, start + 2000):
        if _is_port_free(candidate):
            return candidate
    raise RuntimeError(f"no free loopback port near {start}")


def bench_single_env(
    port: int, java: str, steps: int, chunk: int, reset_samples: int
) -> dict:
    """Single-env engine ticks/sec, protocol overhead, and reset latency."""
    port = _probe_free_port(port)
    with RlServerProcess(LaunchConfig(port=port, java=java)) as env:
        env.handshake()
        rr = env.reset(root_seed=12345, agent_count=2)
        episode = rr.episode_id
        tick = 0

        # Warmup (JIT) — a few untimed chunks.
        for _ in range(5):
            sr = env.step(episode, expected_tick=tick, ticks_to_advance=chunk)
            tick = sr.tick

        engine_ms = 0.0
        obs_ms = 0.0
        wall_ms = 0.0
        for _ in range(steps):
            t0 = time.perf_counter()
            sr = env.step(episode, expected_tick=tick, ticks_to_advance=chunk)
            wall_ms += (time.perf_counter() - t0) * 1000.0
            tick = sr.tick
            engine_ms += float(sr.timing["engine_ms"])
            obs_ms += float(sr.timing["observation_ms"])

        total_ticks = steps * chunk
        engine_tps = total_ticks / (engine_ms / 1000.0) if engine_ms > 0 else float("inf")
        wrapper_tps = total_ticks / (wall_ms / 1000.0) if wall_ms > 0 else float("inf")
        overhead_ms = wall_ms - (engine_ms + obs_ms)
        overhead_pct = 100.0 * overhead_ms / wall_ms if wall_ms > 0 else 0.0

        # Reset latency distribution.
        latencies = []
        for _ in range(reset_samples):
            t0 = time.perf_counter()
            env.reset(root_seed=12345, agent_count=2)
            latencies.append((time.perf_counter() - t0) * 1000.0)

    return {
        "total_ticks": total_ticks,
        "engine_ms": engine_ms,
        "obs_ms": obs_ms,
        "wall_ms": wall_ms,
        "engine_tps": engine_tps,
        "wrapper_tps": wrapper_tps,
        "overhead_ms_per_step": overhead_ms / steps,
        "overhead_pct": overhead_pct,
        "reset_median_ms": statistics.median(latencies),
        "reset_max_ms": max(latencies),
    }


def bench_scaling(
    java: str, base_port: int, pools, iters: int, chunk: int
) -> list[dict]:
    """Aggregate ticks/sec for each pool size in ``pools`` (e.g. 1, 2, 4)."""
    results = []
    for n in pools:
        cfg = SupervisorConfig(
            pool_size=n,
            base_port=_probe_free_port(base_port),
            java=java,
            step_timeout_s=60.0,
        )
        with ProcessSupervisor(cfg) as sup:
            vec = VectorCollector(sup)
            vec.reset_all(seed=12345)
            # Warmup.
            for _ in range(3):
                vec.step_all(ticks=chunk)

            wall = 0.0
            for _ in range(iters):
                r = vec.step_all(ticks=chunk)
                wall += r.wall_time_s
            agg_ticks = n * chunk * iters
            agg_tps = agg_ticks / wall if wall > 0 else float("inf")
        results.append(
            {
                "jvms": n,
                "agg_ticks": agg_ticks,
                "wall_s": wall,
                "agg_tps": agg_tps,
                "per_jvm_tps": agg_tps / n,
            }
        )
    return results


def _print_report(single: dict, scaling: list[dict]) -> None:
    base_tps = scaling[0]["agg_tps"] if scaling else 1.0
    print("\n== M2 benchmark report ==\n")
    print(f"Machine: {platform.processor() or platform.machine()} / "
          f"{platform.system()} {platform.release()} / cores={os.cpu_count()}")
    print(f"Python: {platform.python_version()}\n")

    print("### Single-env (layer 1/4/7)\n")
    print("| Metric | Value |")
    print("|---|---|")
    print(f"| Engine-only ticks/sec | {single['engine_tps']:,.0f} |")
    print(f"| Python-wrapper ticks/sec (end-to-end, 1 env) | {single['wrapper_tps']:,.0f} |")
    print(f"| Reset latency median | {single['reset_median_ms']:.2f} ms |")
    print(f"| Reset latency max | {single['reset_max_ms']:.2f} ms |")

    print("\n### Protocol overhead (layer 5+6)\n")
    print("| Metric | Value |")
    print("|---|---|")
    print(f"| Round-trip minus engine+obs | {single['overhead_ms_per_step']:.3f} ms/step |")
    print(f"| Overhead as % of round-trip | {single['overhead_pct']:.1f}% |")

    print("\n### Scaling (layer 9, aggregate)\n")
    print("| JVMs | Aggregate ticks/sec | Per-JVM ticks/sec | Scaling efficiency |")
    print("|---|---|---|---|")
    for r in scaling:
        ideal = base_tps * r["jvms"]
        eff = 100.0 * r["agg_tps"] / ideal if ideal > 0 else 0.0
        print(
            f"| {r['jvms']} | {r['agg_tps']:,.0f} | {r['per_jvm_tps']:,.0f} | {eff:.0f}% |"
        )
    print()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="rl-server M2 benchmark")
    parser.add_argument("--java", default="java")
    parser.add_argument("--base-port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--chunk", type=int, default=60)
    parser.add_argument("--reset-samples", type=int, default=30)
    parser.add_argument("--scale-iters", type=int, default=100)
    parser.add_argument("--pools", type=int, nargs="+", default=[1, 2, 4])
    args = parser.parse_args(argv)

    print("== rl-server M2 benchmark ==")
    print(f"single-env: {args.steps}x{args.chunk} ticks; scaling pools={args.pools}")

    t_start = time.perf_counter()
    print("\n[1/2] single-env + protocol overhead ...")
    single = bench_single_env(
        args.base_port, args.java, args.steps, args.chunk, args.reset_samples
    )
    print(
        f"    engine={single['engine_tps']:,.0f} tps  "
        f"overhead={single['overhead_pct']:.1f}%  "
        f"reset_median={single['reset_median_ms']:.2f} ms"
    )

    print(f"\n[2/2] scaling {args.pools} JVMs ...")
    scaling = bench_scaling(
        args.java, args.base_port, args.pools, args.scale_iters, args.chunk
    )
    for r in scaling:
        print(f"    {r['jvms']} JVM(s): {r['agg_tps']:,.0f} agg ticks/sec")

    _print_report(single, scaling)
    print(f"benchmark wall time: {time.perf_counter() - t_start:.1f} s")
    print("BENCHMARK OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
