# ADR-0003: One environment per JVM; parallelism via processes

**Status:** Accepted

## Context

Mindustry exposes major services through global static state (`Vars.state`,
`Vars.world`, `Vars.logic`, pathfinders, content, entity groups). Hosting many
isolated worlds inside one JVM would require invasive refactoring and carries a
high state-leak risk.

## Decision

Assume **one independent Mindustry environment per JVM process**. Achieve
parallelism by running **multiple persistent JVM processes**. Reset an episode by
resetting the world **in-process, without restarting the JVM**; a process restart
is a crash/leak recovery mechanism, not the normal reset path.

## Alternatives considered

- **Multiple worlds per JVM (classloader isolation / refactor globals)**:
  rejected initially — huge refactor, leak-prone; revisit only if profiling
  proves process overhead is the bottleneck.
- **Restart the JVM every episode**: rejected — too slow for the reset-latency
  targets (brief §24 Gate 2).

## Consequences

- Simple, robust isolation; clean crash recovery per process.
- Content is initialized once per JVM; reset must scrub all per-episode state.
- Higher memory/process overhead; mitigated by the process supervisor (M2).

## Reversal conditions

Revisit multi-world-per-JVM only after the full system works and profiling shows
JVM process overhead is the dominant scaling limit.
