# ADR-0002: External fixed-step application

**Status:** Accepted

## Context

The stock Mindustry server runs a free-running wall-clock loop with a variable
delta. RL collection needs deterministic, reproducible stepping where the
controller decides exactly when and how far the simulation advances.

## Decision

A custom headless launcher in `rl-server` **replaces the wall-clock loop with an
externally controlled simulation loop**. One engine update == one game tick at a
**fixed delta of 1/60 s**. The controller applies a complete agent-action bundle
atomically at a decision boundary, then advances an exact number of ticks.

## Alternatives considered

- **Drive the stock server loop and sample asynchronously**: rejected —
  nondeterministic, wall-clock-coupled, unsafe to snapshot mid-frame.
- **Patch the engine's core `Time`/`Logic` deeply**: rejected as the first move —
  keep upstream edits tiny; prefer a custom `Application`/launcher that reuses
  `Logic` (brief §29, Risk 1).

## Consequences

- Reproducible episodes; exact tick counts; a foundation for state hashing.
- Requires care to eliminate hidden wall-clock dependencies (brief §29, Risk 2).
- All mutation happens on the simulation thread (see ADR and threading rule).

## Reversal conditions

If reusing the stock loop proves impossible to make deterministic, escalate to a
minimal documented engine patch (catalogued in `docs/UPSTREAM_PATCHES.md`) rather
than abandoning external stepping.
