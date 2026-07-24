# ADR-0096: Reject M9 candidate-native planner v3

**Status:** Accepted

## Context

V3 at implementation `5bde1ff730716190be2dfe8733fb1f553366b8bd`
closes the known structural defect: two fresh JVMs and reset replay are exact,
all actions are accepted, no bundle conflict occurs, and non-WAIT coverage is
6,394/6,428 (`99.4711%`). Survival falls from 13/40 to 3/40.

The public tick-250 boundary explains the regression. With the build line
RUNNING and the initial schematic complete, the idle seat has one deferred
fortification, two valid underfilled-turret supply targets, and harvest. V3's
inherited opening role order chooses harvest over supply. It therefore removes
the invalid build without replacing it with immediate defense readiness.

Full report SHA-256 is
`b94f02d2183aa4db88ada9f3f7d112c78e64015aad9ae85b0784c4362605605c`;
compact result SHA-256 is
`9af4d952fc690c53cacfc48ea68bf8defb6ddd7439d5dc5d86ebc7b47242f84d`.

## Decision

1. Reject v3 as a supervision source and preserve its exact evidence.
2. Keep its zero-rejection active-build constraint.
3. Permit one separately frozen successor coordinate: during that active-build
   defer state, prioritize an actionable underfilled-turret supply candidate
   over harvest. Do not change any other phase or role ordering.
4. Do not train, authorize v7, or access restricted data.

## Consequences

- Structural validity alone is insufficient; the substitute task must preserve
  defense readiness.
- No confirmation or held-out data was accessed.
