# ADR-0006: Hierarchical control over deterministic skills

**Status:** Accepted

## Context

Training raw keyboard/mouse control, per-frame cursor movement, and every tile
coordinate/block type end-to-end is intractable and wasteful when the engine
already provides pathfinding, build-plan queues, and unit commands.

## Decision

Split control into **learned/scripted high-level task selection and
coordination** over **deterministic low-level skills** implemented as state
machines using existing game mechanics. The learned component decides *what
useful work to do and whom to cooperate with*; existing game logic handles *how*
to traverse a route or execute a legal build plan. **No raw-input training.**
Skills return typed status (`agentcore.SkillStatus`) plus reason code, progress,
and next-retry tick. Training and demo modes share the same skills.

## Alternatives considered

- **End-to-end raw control**: rejected — enormous action space, poor sample
  efficiency, reinvents engine capabilities (brief §4.2).
- **Fully scripted, no learning ever**: rejected as the end state — scripted
  baselines come first (ADR-0008), but learned task selection is the goal.

## Consequences

- Tractable high-level action space (candidate tasks, not coordinates).
- Skill correctness is unit-testable independent of the policy.
- Requires a clean skill/task interface in `agent-core`.

## Reversal conditions

Introduce finer-grained learned control only for a specific skill if scripted
behaviour proves a hard performance ceiling for that skill.
