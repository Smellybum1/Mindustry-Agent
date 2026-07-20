"""Vectorized stepping of M rl-server worlds via a :class:`ProcessSupervisor`.

:class:`VectorCollector` steps every child in the pool for the same number of
engine ticks and gathers the per-child outcomes. Each JVM is an independent
process with a blocking loopback socket, so the cheapest correct way to overlap
their round-trips is a small thread per child (the GIL is released during socket
I/O and during the JVM's engine compute). This keeps the collector simple and
correct while still overlapping the JVMs' work; it reports aggregate ticks/sec.

A crashed child is transparently replaced by the supervisor (its slot returns a
truncated outcome for that step); :meth:`reset_all` brings replaced slots back
into an episode. Standard-library only (ADR-0007).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

from mindustry_agents.process.supervisor import (
    ProcessSupervisor,
    ResetOutcome,
    StepOutcome,
)


@dataclass
class VectorStepResult:
    outcomes: list[StepOutcome]
    ticks_advanced: int          # ticks * live_children
    wall_time_s: float
    ticks_per_sec: float         # aggregate across the pool


class VectorCollector:
    """Step all children of a supervisor in lockstep, overlapping their I/O."""

    def __init__(self, supervisor: ProcessSupervisor):
        self.sup = supervisor

    @property
    def size(self) -> int:
        return self.sup.size

    def reset_all(
        self,
        seed: Optional[int] = None,
        options: Optional[dict[str, Any]] = None,
    ) -> list[ResetOutcome]:
        """Reset every child concurrently. ``seed`` ``None`` uses each child's
        own recorded seed (so the pool spans a seed range)."""
        results: list[Optional[ResetOutcome]] = [None] * self.size
        self._parallel(
            lambda i: results.__setitem__(i, self.sup.reset(i, seed=seed, options=options))
        )
        return [r for r in results if r is not None]

    def step_all(
        self,
        actions: Optional[list[list[dict[str, Any]]]] = None,
        ticks: int = 1,
    ) -> VectorStepResult:
        """Step every child by ``ticks`` engine updates, overlapping round-trips.

        ``actions`` is an optional list (one action-bundle per child); ``None``
        sends empty no-op bundles. Returns aggregate timing.
        """
        outcomes: list[Optional[StepOutcome]] = [None] * self.size

        def _one(i: int) -> None:
            bundle = actions[i] if actions is not None and i < len(actions) else None
            outcomes[i] = self.sup.step(i, bundle, ticks=ticks)

        start = time.perf_counter()
        self._parallel(_one)
        wall = time.perf_counter() - start

        final = [o for o in outcomes if o is not None]
        live = sum(1 for o in final if not o.crashed)
        ticks_advanced = ticks * live
        tps = ticks_advanced / wall if wall > 0 else float("inf")
        return VectorStepResult(
            outcomes=final,
            ticks_advanced=ticks_advanced,
            wall_time_s=wall,
            ticks_per_sec=tps,
        )

    def _parallel(self, fn) -> None:
        """Run ``fn(index)`` for each child on its own thread; join all."""
        if self.size == 1:
            fn(0)
            return
        errors: list[Optional[BaseException]] = [None] * self.size

        def _wrap(i: int) -> None:
            try:
                fn(i)
            except BaseException as exc:  # noqa: BLE001
                errors[i] = exc

        threads = [
            threading.Thread(target=_wrap, args=(i,), name=f"vec-{i}")
            for i in range(self.size)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        for exc in errors:
            if exc is not None:
                raise exc
