# ADR-0045: V34 atomic claim-loss decision boundary

**Status:** Accepted

## Context

V32 is exactly reproducible and wins 10/10 reusable episodes, but its team idle
fraction is definitively worse than permanent greedy. V33 showed that assigning
extra defense staging to scripted seat 1 is unsafe: public seed 23456 regressed
to a loss before model work. A successor therefore must preserve V32's task
catalog and partner policy rather than creating busywork.

A fresh reusable-only trace of the selected V32 checkpoint isolates the
remaining seat-1 gap. In every one of the ten dev-v1 wins, seat 1 loses the
same simultaneous exclusive `SUPPLY_TURRET` claim at tick 250, then loses the
same `HARVEST_RESOURCE` claim at tick 254. The second mask-valid action returns
structured `accepted=false, reason=claim_lost`, but the coordination decision
revision does not advance. Stop-on-event therefore leaves the unassigned seat
idle until the unrelated `economy_operational` boundary at tick 660: 406 idle
ticks per episode.

The board's atomic ordering is correct. The winning task remains authoritative,
the loser must not receive an assignment or invalid-action penalty, and no fake
task lifecycle event should be emitted. The defect is solely that a resolved
atomic loss is not exposed as a decision boundary for immediate replanning.

## Decision

1. V34 holds V32's candidate generation, scripted partner policies, learned
   policy, reward, teacher corpus/filter/caps, warmup and rehearsal schedules,
   PPO budget, architecture, optimizer values, RNG values, train/reusable roots,
   selection, and held-out identity exact.
2. When final same-tick claim resolution determines that a mask-valid pending
   selection is not the authoritative owner, the adapter retains the existing
   `claim_lost` action result and increments the coordination decision revision
   with structured boundary reason `claim_lost`.
3. The loss creates no assignment, emits no synthetic board event, changes no
   winner state, and retains the existing duplicate-work telemetry. It remains
   excluded from invalid-action reward exactly as audited.
4. With stop-on-event enabled and at least one tick requested, the server still
   applies the complete atomic action bundle, advances exactly one fixed engine
   tick, and returns the new boundary. The losing seat can select from the next
   authoritative observation rather than waiting for an unrelated event.
5. V34 changes the rollout decision/action/reward sequence and must retrain from
   scratch. V32 checkpoints remain diagnostic history and cannot become V34
   promotion evidence.
6. The five-seed live candidate gate is a hard pretraining boundary. Replica A
   may start only after engine-free and live claim-loss checks, the pinned Java
   build, candidate gate, smoke, determinism, and negative replay pass from the
   committed packet.
7. Replica A must reach at least 9/10 reusable construction wins with mean idle
   below 0.25 before replica B. Passing replicas must reproduce checkpoint,
   frontier, model, replay, teacher reports/schedules, canonical full-run digest,
   and direct lineage.
8. Retire V33's unopened dev-v29. Freeze dev-v30 at globally disjoint roots
   `283001..283160`; it remains unopened until exact replicas and both reusable
   permanent-greedy and matched-greedy scorecards pass. Held-out-v4 stays sealed.

## Alternatives

- More defense staging was rejected by V33's public survival regression.
- More learned-seat reward, teacher, or logit pressure was rejected because the
  affected seat is scripted and learned seat 0 already averages only 4.2 idle
  ticks.
- Treating `claim_lost` as invalid was rejected because both simultaneous
  selections were mask-valid before atomic resolution.
- Emitting a synthetic `ABANDON`, `RELEASE`, or `CLAIM_LOST` board event was
  rejected because the loser never owned the final task. The action result and
  decision boundary express the outcome without falsifying board history.
- Weakening the team idle scorecard was rejected because it would redefine the
  accepted promotion contract after observing a failure.

## Consequences

- V34 is a runtime scheduling correction, not a policy intervention. It should
  remove the repeated 406-tick unassigned gap while preserving the task catalog
  and atomic claim winner.
- Permanent reusable baselines must be refreshed under V34 before preflight
  because their decision sequences can also contain simultaneous claim losses.
- Engine pins, external fixed stepping, simulation-thread ownership,
  structured-authoritative communication, and one-environment-per-JVM remain
  unchanged.

The reusable diagnostic is `runs/m8-selector-v32-partner-idle.json`, SHA-256
`f4e466acfdf7a736b6b650433c6ab866c9768621d04bb9d1d973eccf29d2b511`.
The immutable V34 config SHA-256 is
`d708d37b5f8659f62b507506f68c7038b305ed8e2c3d5532b4cc1b4dbfa4c5ec`.
The dev-v30 seed document SHA-256 is
`388db752bf7b370901e648df5eed52d60999607fa68c26a8208c8dbe8b9c2d41`.
The precommit governance addition brings the Python suite to 159 passing tests.
All 44 exact-config reward adversaries pass; the report at
`runs/m8-selector-v34-precommit/reward-adversaries.json` hashes to
`dc9f1b3886c610ec71b3a4c6bd25a4185b967206f4ede4569f5dd8aabf9c7da5`.
No V34 runtime implementation, live candidate outcome, teacher collection,
model work, dev-v30 evidence, or held-out evidence preceded this precommit.

## Outcome

The pinned Java build and focused live claim-loss check passed, and the public
policy still survived all five seeds. The complete candidate gate nevertheless
rejected V34 before training because proactive staging starts fell from V32's
required five to zero. The gate reported `five-seed candidate gate observed no
proactive staging`; per Decision 6, survival alone cannot waive that failure.

A temporary diagnostic counted final atomic losses by fixed seat for each
public seed: `[[9,0,0], [14,0,0], [10,0,0], [10,0,0], [9,0,0]]`. Every public
loss belonged to learned seat 0, whereas the reusable 406-tick defect belongs
to scripted seat 1. The all-seat boundary therefore perturbed the learned-seat
public sequence even though it targeted a downstream partner defect.

The uncommitted runtime/protocol/check experiment was removed, the accepted V32
runtime rebuilt, and its full candidate gate restored to 5/5 wins with five
proactive-staging starts. V34 is rejected, replica A never began, dev-v30 is
retired unopened, and held-out-v4 remains sealed. The public diagnostic is
`runs/m8-selector-v34-public-claim-diagnostic.json`, SHA-256
`7a1fc0d50117cefd40b8c955e6fa6327dfe2ee34f7338ff22339f1d60127ce7b`.
