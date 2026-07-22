# ADR-0044: V33 targeted secondary-seat staging

**Status:** Accepted

## Context

V32 is exactly reproducible and wins 10/10 reusable episodes. Its resource
actionability rule eliminates non-forced abandonment, and its learned-seat
staging reduces seat 0 to a mean 4.2 idle ticks. Corrected reusable preflight
still rejects permanent-greedy idle by `+0.02116306`, however.

A fresh reusable-only diagnostic under the selected V32 checkpoint records mean
idle ticks by fixed seat as `[4.2, 408.8, 487.4]`. Under permanent greedy they
are `[274.8, 51.5, 298.8]`. Seat 0 is already 270.6 ticks better than the
baseline, seat 2 is 188.6 worse, and scripted seat 1 is 357.3 worse. Seat 1 is
therefore the dominant downstream source and alone exceeds the complete team
gap. Every learned-seat WAIT transition remains forced/masked-only, so another
learned reward or logit change cannot affect this scorecard.

V32's first implementation briefly offered staging to all three seats and
failed public seed 23456 before model work. That evidence rules out restoring
the broad rule. The smallest evidence-backed partner intervention is to extend
the existing candidate to fixed seat 1 while preserving seat 2 exactly.

## Decision

1. V33 changes the proactive-staging eligibility set from fixed learned seat 0
   to fixed seats 0 and 1. Seat 2 remains exact. For both eligible seats, the
   V32 conditions remain unchanged: every ordinary task has already been
   generated, the pending catalog is empty, no enemy is present, and
   time-to-wave is strictly greater than `defendLeadTicks`.
2. The staging candidate remains a priority-`1.0`, nonexclusive
   `DEFEND_REGION` task using the existing named region, structured lifecycle,
   typed action seam, telemetry, masks, and canonical hashes. Its duration
   remains `ceil(timeToNextWave - defendLeadTicks)`.
3. V33 otherwise holds V32 exact: resource actionability, tick-0 schematic
   prior, reward, teacher corpus/filter/caps, warmup and rehearsal schedules,
   PPO budget, architecture, optimizer values, RNG values, train/reusable roots,
   selection, and held-out identity. Candidate/runtime/quality labels,
   staging-seat eligibility, and confirmation path are the only differences.
4. The five-seed live candidate gate is a hard pretraining boundary because the
   rejected all-seat variant already demonstrated partner-policy sensitivity.
   Any regression rejects V33 before model work; it does not authorize another
   seat adjustment under this candidate identity.
5. Replica A must reach at least 9/10 reusable construction wins with mean idle
   below 0.25 before replica B. Passing replicas must reproduce checkpoint,
   frontier, model, replay, teacher reports/schedules, canonical full-run digest,
   and direct lineage.
6. Retire V32's unopened dev-v28. Freeze dev-v29 at globally disjoint roots
   `282001..282160`; it remains unopened until exact replicas and both reusable
   permanent-greedy and matched-greedy scorecards pass. Held-out-v4 stays sealed.
7. Training may begin only after exact-config reward adversaries, the Python and
   Java suites, pinned build, engine-free/live seat-scope checks, the five-seed
   candidate gate, smoke, and determinism including negative replay pass from a
   committed packet.

## Alternatives

- Extending staging to seat 2 or all seats was rejected. Seat 1 is the dominant
  gap, while the all-seat rule already regressed a public survival seed.
- More learned-seat reward, teacher, or logit pressure was rejected because
  learned seat 0 averages only 4.2 idle ticks and all of its remaining WAIT
  transitions are forced.
- Weakening the team scorecard or excluding scripted partners was rejected; the
  promotion contract judges the cooperating team actually deployed.
- Relabeling forced WAIT as non-idle was rejected because it would change the
  accepted metric after observing a candidate result.

## Consequences

- V33 changes partner decision sequences and must retrain from scratch. V32
  checkpoints cannot become V33 promotion evidence.
- Permanent reusable baselines must be refreshed under V33 before preflight.
- Engine pins, external fixed stepping, simulation-thread ownership,
  structured-authoritative communication, and one-environment-per-JVM remain
  unchanged.

The reusable diagnostic is
`runs/m8-selector-v32-reusable-idle-diagnostic.json`, SHA-256
`63cbeeaa11e75dba1af4ba60b2673231863f8c7af5d0e287d1fa2ebfce1bf7bd`.
The immutable V33 config SHA-256 is
`12a85586f1b823b4fce1ed49d9d6926d426a1727a3993e5d5a28c61dd5d05071`.
The precommit governance addition brings the Python suite to 158 passing tests.
All 44 exact-config reward adversaries pass; the report at
`runs/m8-selector-v33-precommit/reward-adversaries.json` hashes to
`3aa1b316161137e6d9ba4350d249567baff53cbac5e6aa3669517c96db3cef7f`.
No V33 runtime implementation, live candidate outcome, teacher collection,
model work, dev-v29 evidence, or held-out evidence preceded this precommit.

## Outcome

The engine-free scope tests and pinned build passed, but the first live
five-seed boundary rejected V33 before training. Public seed 23456 changed from
V32's win to a loss at tick 7593 with zero core health, producing only 4/5
wins. This repeats the survival regression first exposed by the overbroad V32
prototype and shows that extending defense staging to seat 1 is itself unsafe;
seat 2 was not required to trigger the failure.

Per Decision 4, this result rejects V33 and does not authorize a different seat
adjustment under the same identity. The uncommitted runtime experiment was
removed, the accepted V32 runtime restored, replica A never began, dev-v29 is
retired unopened, held-out-v4 remains sealed, and M8.5 is unmet.
