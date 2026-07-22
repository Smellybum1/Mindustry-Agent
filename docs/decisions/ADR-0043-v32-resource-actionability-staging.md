# ADR-0043: V32 resource actionability and proactive staging

**Status:** Accepted

## Context

V31 is reproducible and wins 9/10 reusable episodes, but corrected preflight
rejects it on permanent-greedy idle and abandonment plus matched-greedy
abandonment. Its reusable structured traces isolate both mechanisms.

All 13 non-forced learned-seat abandons are `SUPPLY_TURRET` tasks selected with
an estimated one-copper cost and blocked one tick later by `CORE_SHORT`. The
catalog deliberately keeps supply work visible at zero core copper, while the
soft reservation ledger retains the episode high-water capacity. That makes a
task reservable even when neither the core nor the selecting unit can currently
supply a single copper. The existing resource-scoped retry then prevents a
target cycle, but only after the avoidable task has started and abandoned.

The available-idle evidence is equally explicit. Across reusable dev-v1, every
available learned-seat WAIT run has a catalog containing only WAIT. These runs
begin after ordinary objectives are complete, with no enemy present and before
the existing defend-lead boundary. On seed 2001, for example, the seat is
forced to WAIT from tick 4058 through 4323 while core copper rises from 302 to
326 and time-to-wave falls from 476 to 211. This is not a learned WAIT preference:
all nine ordinary selector actions are masked. Positioning at the already named
defense region is useful, nonexclusive work during exactly this otherwise empty
interval.

## Decision

1. V32 changes the engine-free candidate/actionability boundary in two fixed
   ways. A `SUPPLY_TURRET` candidate is valid only when current core copper is
   positive or the selecting unit carries positive copper; otherwise it remains
   visible but masked with reason `resources_unavailable:copper`.
2. After generating every ordinary task, if the pending catalog is empty, no
   enemy is present, and time-to-wave is strictly greater than the existing
   `defendLeadTicks`, add one nonexclusive `DEFEND_REGION` staging candidate.
   It has priority `1.0` and estimated duration
   `ceil(timeToNextWave - defendLeadTicks)`, so it ends exactly at the existing
   active-defense boundary. Ordinary work always takes precedence.
3. Staging uses the existing named region, `DefendRegion` skill, task type,
   typed action seam, board lifecycle, telemetry, masks, and canonical hashes.
   It adds no raw movement action, hidden information, wall-clock pacing, or
   reward component.
4. V32 otherwise holds V31 exact: tick-0 schematic prior, reward, teacher
   corpus/filter/caps, warmup and rehearsal schedules, PPO budget, architecture,
   optimizer values, RNG values, train/reusable roots, selection, and held-out
   identity. Candidate ID, runtime/quality labels, actionability catalog, and
   confirmation path are the only differences.
5. Replica A must reach at least 9/10 reusable construction wins with mean idle
   below 0.25 before replica B. Passing replicas must reproduce checkpoint,
   frontier, model, replay, teacher reports/schedules, canonical full-run digest,
   and direct lineage.
6. Retire V31's unopened dev-v27. Freeze dev-v28 at globally disjoint roots
   `281001..281160`; it remains unopened until exact replicas and both reusable
   permanent-greedy and matched-greedy scorecards pass. Held-out-v4 stays sealed.
7. Training may begin only after exact-config reward adversaries, the Python and
   Java suites, pinned build, candidate actionability/staging live checks,
   five-seed candidate gate, smoke, and determinism including negative replay
   pass from a committed packet.

## Alternatives

- Reclassifying resource-short abandonment as forced was rejected. The terminal
  action is automatic, but the avoidable zero-source selection is policy
  liability under the accepted scorecard contract.
- Excluding only-WAIT periods from idle was rejected because it would weaken a
  promotion metric after seeing a candidate result.
- More reward, teacher, or logit coefficients were rejected: V24-V31 already
  exercise those lines, while a masked-only state cannot be repaired by logits.
- Extra harvesting was rejected because two partner seats are already mining in
  the observed gaps. Defense staging is distinct, useful, nonexclusive work and
  ends at the pre-existing safety boundary.

## Consequences

- V32 changes decision sequences and must retrain from scratch; V31 checkpoints
  cannot become promotion evidence under the new runtime.
- Permanent reusable baselines must be refreshed after the runtime change before
  any V32 preflight, with their source hashes carried forward.
- Engine pins, external fixed stepping, simulation-thread ownership,
  structured-authoritative communication, and one-environment-per-JVM remain
  unchanged.

No V32 runtime implementation, candidate outcomes, teacher collection, or model
work occurred before this precommit.

The immutable config SHA-256 is
`cf5f42da2cf2d99a14ad7671d766b10ca6cbc8695f7ef3f3f22cf8ee49823fa5`.
The precommit governance addition brings the Python suite to 157 passing tests;
runtime and full pretraining gates are not yet claimed.
