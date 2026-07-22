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
2. For the fixed M8 learned seat 0 only, after generating every ordinary task,
   if the pending catalog is empty, no enemy is present, and time-to-wave is
   strictly greater than the existing `defendLeadTicks`, add one nonexclusive
   `DEFEND_REGION` staging candidate. Scripted partner catalogs remain exact.
   The candidate has priority `1.0` and estimated duration
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
The precommit governance addition brings the Python suite to 157 passing tests.

The first live implementation gate exposed an overbroad interpretation before
training: offering staging to all three scripted seats changed public seed
23456 from a win to a loss. Core copper never reached the new supply-mask
boundary in that episode, while all three seats staged. The rule is therefore
fixed to learned seat 0 as stated above; this is the seat whose reusable idle
evidence justified the intervention and preserves partner behavior. No V32
model work or exclusive evidence preceded this correction.

The corrected implementation passes its engine-free boundary tests and live
actionability/staging checks, the pinned 112-test Java build, the five-seed candidate
gate, smoke, determinism, negative replay, the full 157-test Python suite, and
all 44 exact-config reward adversaries. The adversary report is
`runs/m8-selector-v32-precommit/reward-adversaries.json`, SHA-256
`49d18508bbd825bdf605dc47d6a494b6231bc5bc251e07665681544892e8d9c4`.
No V32 model work or unopened evaluation evidence preceded these gates.

## Outcome

Two independent pinned replicas reproduce selected update 28 exactly at 10/10
reusable construction wins, mean return `5.58316`, mean core health `639.2`,
and mean idle `0.06066571`. Checkpoint, model-state, replay, canonical full-run,
and direct-lineage hashes are respectively
`72e10ec9dcf9b30c8069d1e4ec03b65e5758acd965c6ba2429879a00b9d75a1e`,
`dae302b62259866f1a727a28f14a0441fd578d88d9f2b35667ddc986b2df2db8`,
`837102913ff2596d25ae97702d68c090bb0bf04d6785a9b443b21bcb7d9f6622`,
`f4495f671fd72430427478157288b3cb6dd7d044e224ea54a3813a09a2e7bbcb`,
and `3744c81c88dd435f0fe43480f4c3c5d487dbf1afd972cbfed4255af21bd7c8a7`.

Fresh V32-runtime permanent baselines and matched controls show learned 10/10,
permanent random 5/10, permanent greedy 8/10, matched random 4/10, and matched
greedy 0/10. All win-rate comparisons pass, and the resource-actionability
change reduces non-forced abandonment to exact zero against both greedy
scorecards. The candidate nevertheless fails corrected scorecard parity:
permanent-greedy idle is definitively worse by `+0.02116306` with paired 95%
interval `[+0.00659211,+0.03839977]`; permanent announcements and recovery are
uncertain, and matched-greedy recovery is uncertain. The preflight report
hashes to `7a1e6192f3b7052d4ff89f75bb6ef56450b3a984949925b5a44cf45548b239e1`.

V32 is rejected. Dev-v28 remains unopened and is retired, held-out-v4 remains
sealed, and M8.5 is unmet.
