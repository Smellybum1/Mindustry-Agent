# ADR-0094: Reject M9 candidate-native planner v2

**Status:** Accepted

## Context

ADR-0093 froze v2's sole change as at most one new BUILD_SCHEMATIC selection
per atomic bundle. Implementation commit
`077095399e368e15ebe94934fdb408c2ab9ec74a` passes all 458 Python tests.

The governed result is bit-identical to v1: 13/40 wins, 4,959/4,963 non-WAIT
eligible slots, exact fresh-JVM and terminal-reset replay, and one
`reservation_overlap` rejection at tick 250 in every episode. V2 does emit only
one new schematic at that boundary. Its fortification still overlaps the
already RUNNING `T2:build:copper_line_v1:at-0` task, so within-bundle
serialization does not cover reservations held by prior boundaries.

The full report SHA-256 is
`7d1e734bdacae51cb31b2634c380079714d4e465ac6c141ac40a633e85706dec`.
The compact result SHA-256 is
`59d9993c9779abf02ea4ab70410b0ce42d233ea34a62139c0a29cf08f8353efc`.

## Decision

1. Reject v2 as a candidate-native supervision source.
2. Preserve v2 and do not train, authorize v7, or access restricted data.
3. Accept one bounded successor coordinate: consult the already-authoritative
   structured task board and defer new schematic selections while a build-line
   or schematic task is CLAIMED, RUNNING, or BLOCKED.
4. Freeze that successor separately before implementation.

## Consequences

- Candidate collision handling must span prior accepted boundaries, not only
  the current atomic bundle.
- V2 supplies no evidence for changing combat roles or survival thresholds.
- No confirmation or held-out data was accessed.
