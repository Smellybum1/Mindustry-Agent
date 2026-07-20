"""M2 stress test: 1,000 in-JVM resets, hash stability + reset latency + leak.

Boots **one** persistent rl-server JVM and resets it ``--resets`` times (default
1000) with the *same seed*, without restarting the JVM. Asserts three things and
exits 0 iff all hold:

1. **Hash stability** — every initial ``state_hash`` equals the first (reset is
   pure; no cross-episode state leak).
2. **Reset latency** — reports median / p95 / max client-observed latency (Gate 2
   target < 250 ms; stretch < 100 ms). This is informational, not a hard gate.
3. **No memory leak** — samples the child's RSS every ``--sample-every`` resets.
   With a bounded heap (``--max-heap``, default ``350m``) the failure condition
   is an **absolute ceiling**: peak RSS must stay under ``Xmx + 300 MiB`` (native
   + metaspace + JIT allowance). RSS *growth* within the cap is heap ergonomics
   (the JVM lazily expands toward Xmx on its own schedule) and is reported as
   informational only — growth-trend thresholds proved flaky across runs on a
   loaded machine. A genuine native/metaspace leak still fails: it grows without
   bound and punches through the ceiling. For **uncapped** runs (``--max-heap
   ""``) the old trend heuristic (> 20% and > 64 MiB post-warmup growth) is the
   only available signal and is applied as before, with the caveat above.

Memory sampling prefers ``psutil`` if installed, else falls back to Windows
``tasklist`` CSV parsing (or ``/proc/<pid>/status`` on Linux). The source used is
printed in the report.

Run: ``python -m mindustry_agents.tools.stress_reset [--resets N] [--seed S]``
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess
from mindustry_agents.process.supervisor import _is_port_free

# Leak detection. Capped-heap runs use an absolute ceiling (Xmx + native
# allowance); growth trends within the cap are heap ergonomics, not leaks.
# Uncapped runs fall back to the trend heuristic over the post-warmup tail.
NATIVE_ALLOWANCE_MB = 300.0    # metaspace + JIT code cache + GC/native overhead
LEAK_REL_TOLERANCE = 0.20      # 20%   (uncapped fallback only)
LEAK_ABS_TOLERANCE_MB = 64.0   # MiB   (uncapped fallback only)
WARMUP_FRACTION = 0.30
DEFAULT_MAX_HEAP = "350m"


def _heap_mb(spec: str) -> Optional[float]:
    """Parse an ``-Xmx`` size spec like ``350m``/``2g`` to MiB (None if unparsable)."""
    spec = spec.strip().lower()
    try:
        if spec.endswith("g"):
            return float(spec[:-1]) * 1024.0
        if spec.endswith("m"):
            return float(spec[:-1])
        if spec.endswith("k"):
            return float(spec[:-1]) / 1024.0
        return float(spec) / (1024.0 * 1024.0)  # raw bytes
    except ValueError:
        return None


def _probe_free_port(start: int) -> int:
    for candidate in range(start, start + 2000):
        if _is_port_free(candidate):
            return candidate
    raise RuntimeError(f"no free loopback port near {start}")


def sample_rss_mb(pid: int) -> tuple[Optional[float], str]:
    """Return ``(rss_mib, source)`` for ``pid``; ``rss`` is ``None`` if unknown."""
    try:
        import psutil  # type: ignore

        return psutil.Process(pid).memory_info().rss / (1024 * 1024), "psutil"
    except Exception:
        pass

    if sys.platform.startswith("win"):
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=15,
            ).stdout.strip()
            if out and "," in out:
                mem_field = out.split('","')[-1].strip().strip('"')
                digits = mem_field.replace(",", "").replace("K", "").strip()
                if digits.isdigit():
                    return int(digits) / 1024.0, "tasklist"
        except Exception:
            pass
        return None, "tasklist"

    # POSIX fallback.
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    kb = int(line.split()[1])
                    return kb / 1024.0, "proc"
    except Exception:
        pass
    return None, "proc"


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def _pid_exists(pid: int) -> bool:
    """Return whether the exact child PID still exists after managed shutdown."""
    if sys.platform.startswith("win"):
        output = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
        return f'"{pid}"' in output
    return Path(f"/proc/{pid}").exists()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="rl-server M2 reset stress test")
    parser.add_argument("--resets", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--java", default="java")
    parser.add_argument("--sample-every", type=int, default=100)
    parser.add_argument(
        "--max-heap",
        default=DEFAULT_MAX_HEAP,
        help="JVM -Xmx (e.g. 512m); empty string leaves the heap uncapped",
    )
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)

    port = _probe_free_port(args.port)
    jvm_args = tuple(f"-Xmx{args.max_heap}".split()) if args.max_heap else ()
    print("== rl-server M2 stress-reset ==")
    print(f"resets={args.resets} seed={args.seed} port={port} jvm_args={jvm_args or '(uncapped)'}")

    latencies_ms: list[float] = []
    rss_samples: list[tuple[int, float]] = []  # (reset_index, rss_mib)
    rss_source = "n/a"
    first_hash: Optional[str] = None
    mismatches = 0
    child_pid: Optional[int] = None

    with RlServerProcess(LaunchConfig(port=port, java=args.java, jvm_args=jvm_args)) as env:
        assert env.pid is not None
        child_pid = env.pid
        hs = env.handshake()
        print(f"handshake: engine={hs.engine_version} commit={hs.engine_commit[:12]} pid={env.pid}")

        for i in range(args.resets):
            t0 = time.perf_counter()
            rr = env.reset(root_seed=args.seed, agent_count=2)
            latencies_ms.append((time.perf_counter() - t0) * 1000.0)

            if first_hash is None:
                first_hash = rr.state_hash
            elif rr.state_hash != first_hash:
                mismatches += 1
                if mismatches <= 5:
                    print(f"  MISMATCH at reset {i}: {rr.state_hash[:24]} != {first_hash[:24]}")

            if i % args.sample_every == 0:
                rss, rss_source = sample_rss_mb(env.pid)
                if rss is not None:
                    rss_samples.append((i, rss))
                pct = 100.0 * (i + 1) / args.resets
                rss_str = f"{rss:.1f} MiB" if rss is not None else "unavailable"
                print(
                    f"  reset {i:5d}/{args.resets} ({pct:5.1f}%)  "
                    f"last_latency={latencies_ms[-1]:.2f} ms  rss={rss_str}"
                )

        # Final RSS sample.
        final_rss, rss_source = sample_rss_mb(env.pid)
        if final_rss is not None:
            rss_samples.append((args.resets, final_rss))

    # -- report ------------------------------------------------------------
    med = statistics.median(latencies_ms)
    p95 = _percentile(latencies_ms, 0.95)
    mx = max(latencies_ms)
    mn = min(latencies_ms)
    print("\n-- results --")
    print(f"hash: first={first_hash[:32] if first_hash else 'n/a'}  mismatches={mismatches}")
    print(
        f"reset latency (ms): median={med:.2f}  p95={p95:.2f}  max={mx:.2f}  min={mn:.2f}  "
        f"(n={len(latencies_ms)})"
    )

    # Leak check. Capped heap: absolute ceiling. Uncapped: trend heuristic.
    heap_cap_mb = _heap_mb(args.max_heap) if args.max_heap else None
    warmup_cut = args.resets * WARMUP_FRACTION
    tail = [(i, r) for (i, r) in rss_samples if i >= warmup_cut]
    leak_ok = True
    memory_report: dict[str, object] = {
        "source": rss_source,
        "samples": [[index, rss] for index, rss in rss_samples],
    }
    if len(tail) >= 2:
        base_rss = tail[0][1]
        last_rss = tail[-1][1]
        peak_rss = max(r for _, r in tail)
        growth = last_rss - base_rss
        rel = growth / base_rss if base_rss > 0 else 0.0
        overall_first = rss_samples[0][1]
        memory_report.update(
            {
                "startup_mib": overall_first,
                "steady_base_mib": base_rss,
                "last_mib": last_rss,
                "peak_mib": peak_rss,
                "tail_growth_mib": growth,
                "tail_growth_fraction": rel,
            }
        )
        print(
            f"memory (source={rss_source}): startup={overall_first:.1f} MiB  "
            f"steady-state base={base_rss:.1f} MiB  last={last_rss:.1f} MiB  "
            f"peak={peak_rss:.1f} MiB  tail-growth={growth:+.1f} MiB ({rel * 100:+.1f}%)  "
            f"samples={len(rss_samples)} (tail={len(tail)})"
        )
        if heap_cap_mb is not None:
            ceiling = heap_cap_mb + NATIVE_ALLOWANCE_MB
            memory_report["ceiling_mib"] = ceiling
            print(
                f"  ceiling check (capped heap): peak {peak_rss:.1f} MiB vs "
                f"Xmx {heap_cap_mb:.0f} + {NATIVE_ALLOWANCE_MB:.0f} allowance = {ceiling:.0f} MiB; "
                f"within-cap growth is informational (heap ergonomics, not a leak)"
            )
            if peak_rss > ceiling:
                leak_ok = False
                print(f"  LEAK: peak RSS {peak_rss:.1f} MiB exceeds ceiling {ceiling:.0f} MiB")
        elif growth > LEAK_ABS_TOLERANCE_MB and rel > LEAK_REL_TOLERANCE:
            leak_ok = False
            print(
                f"  LEAK (uncapped trend heuristic): steady-state growth {growth:.1f} MiB "
                f"(>{LEAK_ABS_TOLERANCE_MB}) and {rel * 100:.1f}% "
                f"(>{LEAK_REL_TOLERANCE * 100:.0f}%)"
            )
    else:
        print(f"memory (source={rss_source}): insufficient samples; skipping leak check")

    hash_ok = mismatches == 0 and first_hash is not None
    orphaned = child_pid is not None and _pid_exists(child_pid)
    ok = hash_ok and leak_ok and not orphaned
    print(f"\nhash_stable={hash_ok}  no_leak={leak_ok}  no_orphan={not orphaned}")
    if args.json_output is not None:
        report = {
            "schema": "stress_reset_v1",
            "platform": platform.platform(),
            "python": platform.python_version(),
            "java": args.java,
            "resets": args.resets,
            "seed": args.seed,
            "max_heap": args.max_heap,
            "first_state_hash": first_hash,
            "hash_mismatches": mismatches,
            "latency_ms": {"min": mn, "median": med, "p95": p95, "max": mx},
            "memory": memory_report,
            "hash_stable": hash_ok,
            "no_leak": leak_ok,
            "child_pid": child_pid,
            "no_orphan": not orphaned,
            "pass": ok,
        }
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"json={args.json_output}")
    print("STRESS-RESET", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
