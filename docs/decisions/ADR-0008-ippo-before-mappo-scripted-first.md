# ADR-0008: Scripted baselines first; IPPO before MAPPO

**Status:** Accepted

## Context

It is tempting to jump straight to centralized multi-agent training. But without
scripted baselines and a validated environment, we cannot tell whether learning
helps, and we risk chasing reward exploits in an unproven stack.

## Decision

Build **scripted (and random-valid/heuristic) baselines before any learning**.
Then **IPPO (independent PPO, parameter-shared actor) before MAPPO** (centralized
critic). Learned single-agent task selection precedes multi-agent learning.

## Alternatives considered

- **MAPPO from the start**: rejected — more moving parts, harder to debug, no
  baseline to beat.
- **Skip scripted baselines**: rejected — they are the environment's acceptance
  test and the yardstick for "learning actually helps" (brief §16.1).

## Consequences

- Clear progression with measurable go/no-go gates at each stage.
- Scripted policies double as the demo expert and regression fixtures.
- Slower path to "learning", but far lower risk of building on a broken base.

## Reversal conditions

Advance to MAPPO only after IPPO beats fixed-role baselines on at least one
randomized scenario family (brief §25 M8 exit criteria).
