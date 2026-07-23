# ADR-0069: Supersede the M9 entry gate after the M8 one-brain ceiling

**Status:** Accepted

## Context

ADR-0013, ADR-0017, and ADR-0019 require a promoted M8 selector before M9 may
begin unless a later accepted ADR explicitly changes that dependency. M8
implemented the complete governed one-seat learning and promotion path, but no
candidate met every promotion requirement. V49 fixed the strongest unchanged
V47 checkpoint and evaluated it prospectively on 160 fresh public roots. It won
123/160, compared with permanent greedy's 82/160, and passed every win,
control, matched-scorecard, reward, lineage, and reproducibility gate.
Permanent-greedy idle nevertheless exceeded its precommitted operational
non-inferiority margin.

Public attribution places the remaining idle gap in no-transfer and seat-1
contexts while final seat 2 is favorable. Forty-nine governed M8 variants have
therefore exhausted the justified one-brain and transfer-local hypotheses. The
remaining mechanism is the fixed one-learned-seat model scope itself, which M9
is explicitly intended to remove.

On 2026-07-23 the project owner authorized this direction change.

## Decision

1. The M9 entry dependency in ADR-0013 item 8, ADR-0017 item 7, and ADR-0019
   item 8 is superseded. M9.1 may begin without an M8 promotion.
2. This does not promote V49 or complete M8.5. M8 remains an implemented,
   reproducible, unsuccessful promotion line; its unchecked exit criterion
   stays unchecked.
3. M9 begins at ADR-0008's required first step: parameter-shared IPPO before
   MAPPO. The first implementation boundary is all-seat action authority with
   one shared actor/critic parameter set, an explicit seat-role embedding, and
   separate reset-local recurrent state per seat.
4. All learned seat actions for one boundary are computed from the same
   authoritative pre-step observation and submitted in one atomic action
   bundle in deterministic agent-id order. Only the simulation thread may
   apply the bundle or read the resulting mutable game state.
5. The first boundary uses ordinary selector actions only. M8's expert-DEFER
   control is excluded because an adaptive scripted fallback would make
   "all seats learned" false. M8 checkpoints are evidence and initialization
   references only; they are not relabeled as M9 results.
6. Recurrent state is private to each seat, initialized to zero on environment
   reset, reset when that seat dies, and never copied between seats. The
   parameter-shared model is the only shared learned object.
7. Fresh public governance is reserved for M9:
   `bootstrap-defense-v1-m9-train-v1` contains 64 train roots in
   `[18_000_000_000,19_000_000_000)`, and
   `bootstrap-defense-v1-m9-dev-v1` contains 40 development roots in
   `[19_000_000_000,20_000_000_000)`. Neither set is a confirmation or
   held-out set. Their exact documents are committed before model work.
8. The M8 held-out-v7 set remains sealed and M8-only. M9 must not read, reuse,
   rename, or derive a split from it. Any M9 confirmation or held-out set
   requires a later value-free precommit after a public candidate qualifies.
9. Before any M9 training episode, the implementation boundary must be
   committed and pass:
   - unit tests for parameter identity, role sensitivity, recurrent-state
     isolation/reset, alive-seat masking, deterministic agent order, and
     atomic action bundling;
   - a real-JVM teacher-controlled parity probe that traverses the all-seat
     learned action path without changing the accepted scripted decisions;
   - full Python tests, pinned custom Java checks, smoke, determinism, golden
     replay, and exact-config reward adversaries.
10. A separate immutable training config and reward-audit update must be
    committed after that boundary and before replica A. The first IPPO result
    remains development evidence only. MAPPO is still prohibited until IPPO
    beats the fixed-role scripted baseline on at least one randomized scenario
    family, as ADR-0008 requires.
11. Engine and Arc pins, one environment per JVM, external fixed stepping,
    structured-authoritative communication, framework-neutral environment
    boundaries, and every accepted threading rule remain unchanged.

## Alternatives considered

- Continue M8 with another one-brain wrapper: rejected because V49's public
  attribution does not support a transfer-local mechanism and the fixed-seat
  scope is now the architectural ceiling.
- Mark M8 complete by relaxing its scorecard: rejected. The frozen result is
  honest evidence and remains not promoted.
- Start MAPPO immediately: rejected by ADR-0008; it would add a centralized
  critic before the shared-actor path is independently validated.
- Reuse held-out-v7 for M9: rejected because it is a sealed M8 final and because
  cross-milestone reuse would contaminate both claims.

## Consequences

- Roadmap progress can continue without falsifying M8's result.
- M9.1 first validates the new all-seat authority and recurrent-state boundary,
  then freezes the exact optimization experiment.
- The smallest new learned scope is materially larger than M8, so telemetry
  must prove three-seat learned authority and one shared parameter set on every
  governed run.
- Human co-op evidence remains deferred until a promotable learned runtime is
  available; this decision does not consume the user's offered session.

## Reversal conditions

Reinstate the M9 entry block if the all-seat path cannot preserve deterministic
atomic stepping or if it requires an engine-threading exception. Advance to
MAPPO only after the ADR-0008 IPPO gate is met and recorded.
