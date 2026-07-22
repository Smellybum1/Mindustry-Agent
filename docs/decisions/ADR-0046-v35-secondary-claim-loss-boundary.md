# ADR-0046: V35 secondary-seat claim-loss boundary

**Status:** Accepted

## Context

V34 correctly identified that final atomic claim loss must wake an unassigned
seat, but its all-seat implementation failed the complete public pretraining
gate. Although survival remained 5/5, proactive-staging starts fell from the
accepted V32 count of five to zero.

The follow-up public diagnostic makes the scope error exact. Claim-loss counts
by fixed seat were `[[9,0,0], [14,0,0], [10,0,0], [10,0,0], [9,0,0]]` across
the five public seeds: every loss affected learned seat 0. The reusable defect
is disjoint. In all ten V32 dev-v1 wins, scripted seat 1 loses the same harvest
claim at tick 254 and then remains unassigned until tick 660. No reusable or
public evidence identifies seat 2 as requiring a wake.

The smallest causal intervention is therefore a fixed-seat scheduling repair:
wake scripted seat 1 after final atomic claim loss while preserving learned
seat 0 and scripted seat 2 exactly.

## Decision

1. V35 holds V32's candidate generation, scripted partner policies, learned
   policy, reward, teacher corpus/filter/caps, warmup and rehearsal schedules,
   PPO budget, architecture, optimizer values, RNG values, train/reusable roots,
   selection, and held-out identity exact.
2. When final same-tick resolution determines that a mask-valid pending
   selection from fixed seat 1 is not the authoritative owner, the adapter
   retains the existing `claim_lost` action result and advances the coordination
   decision revision with structured boundary reason `claim_lost`.
3. Identical losses from fixed seats 0 and 2 preserve V32 scheduling and do not
   advance the revision. This is an evidence-scoped partner correction, not a
   general claim protocol change.
4. The loss creates no assignment, emits no synthetic board event, changes no
   winner state, and retains existing duplicate-work telemetry and exact-zero
   invalid-action reward treatment.
5. With stop-on-event enabled and at least one tick requested, a seat-1 loss
   advances exactly one fixed engine tick before returning. A focused live check
   must also prove a seat-0 loss does not wake, preserving the public sequence.
6. The complete five-seed candidate command, including its positive staging
   assertion, is a hard pretraining boundary. Survival alone cannot waive it.
7. V35 changes reusable rollout sequences and must retrain from scratch. Replica
   A must reach at least 9/10 reusable construction wins with mean idle below
   0.25 before replica B. Passing twins must reproduce all governed hashes and
   direct lineage.
8. Retire V34's unopened dev-v30. Freeze dev-v31 at globally disjoint roots
   `284001..284160`; it remains unopened until exact replicas and both reusable
   permanent-greedy and matched-greedy scorecards pass. Held-out-v4 stays sealed.
9. Training may begin only after focused scope/live checks, the pinned Java
   build, complete candidate gate, smoke, determinism, and negative replay pass
   from a committed implementation packet.

## Alternatives

- Retrying the all-seat wake was rejected by V34's staging regression.
- Waking learned seat 0 was rejected because every public loss is on that seat
  and the observed sequence change removed the accepted staging behavior.
- Waking seat 2 was rejected because neither reusable nor public evidence shows
  the target defect there.
- More partner tasks or defense staging were rejected by V33's survival loss.
- Treating loss as invalid or emitting fake board lifecycle was rejected for the
  same atomic-authority reasons recorded by ADR-0045.

## Consequences

- V35 deliberately introduces fixed-seat scheduling asymmetry at the external
  decision seam. That asymmetry matches the M8 single-learned-seat deployment;
  M9 must revisit it when all seats become learned.
- Permanent reusable baselines must be refreshed under V35 because scripted
  seat-1 sequences can change.
- Engine pins, fixed stepping, simulation-thread ownership, structured-
  authoritative communication, and one-environment-per-JVM remain unchanged.

The reusable diagnostic is `runs/m8-selector-v32-partner-idle.json`, SHA-256
`f4e466acfdf7a736b6b650433c6ab866c9768621d04bb9d1d973eccf29d2b511`.
The V34 public scope diagnostic is
`runs/m8-selector-v34-public-claim-diagnostic.json`, SHA-256
`7a1fc0d50117cefd40b8c955e6fa6327dfe2ee34f7338ff22339f1d60127ce7b`.
The immutable V35 config SHA-256 is
`180595d6a0f446e9a2e530fe8bc43c1996d74992c715365168ce59bc3e2d9d3b`.
The dev-v31 seed document SHA-256 is
`b8058d0c5fd04674d5183d0e110d3457b1f4f560d1ae970b9a13108d265e06b2`.
The precommit brings the Python suite to 160 passing tests. All 44 exact-config
reward adversaries pass; `runs/m8-selector-v35-precommit/reward-adversaries.json`
hashes to
`a126ca2424341732bdd17dcac469e48200efc1c4365eadea3bc97f353edadaa5`.
No V35 runtime implementation, live outcome, teacher collection, model work,
dev-v31 evidence, or held-out evidence preceded this precommit.

## Implementation checkpoint

The adapter implements Decision 2 with a fixed `agent.index == 1` guard at
final pending-selection resolution. `secondary-claim-wake-check` finds real
exclusive contests from the live authoritative catalog and proves both sides of
the contract: seat 1 loses `T1:harvest:copper:at-0` to seat 2 and returns
`claim_lost` after one fixed tick, while seat 0 loses the same task to seat 1
without triggering a boundary. In both cases the winner alone owns the running
task and no synthetic `CLAIM_LOST` board event exists.

The pinned Java build passes. The complete public candidate command also passes
5/5 with all five proactive-staging starts restored; core health by seed is
`[299,1100,263,1091,1091]`. From implementation commit `673042bfd0`, smoke,
cross-process/reset/seed determinism, the 664-checkpoint 16,200-tick golden
replay, and intentional one-line negative replay all pass. Every pretraining
boundary in Decision 9 is green; replica A is authorized. No model work has yet
begun, and dev-v31 plus held-out-v4 remain unopened.

## Outcome

V35's exact replicas both select update 8 at 9/10 reusable wins, mean return
`3.85778`, mean core health `721.8`, and mean idle `0.05600096`. Checkpoint,
model-state, checkpoint-replay, canonical full-run, and direct-lineage digests
are respectively `dd64ec3d8768f7f...`, `ce6f29fac599795d...`,
`9c49e3b0f58c1312...`, `515c292d12332566...`, and `56a70dc65f85f4b3...`.
The official manifest comparator and direct-lineage verifier both pass.

Fresh V35-runtime permanent baselines produce random 4/10 and greedy 8/10.
Reusable preflight beats every permanent and matched win-rate comparator, and
matched-greedy idle improves by `-0.11184187` with CI entirely below zero.
V35 nevertheless fails the dual scorecard: permanent-greedy idle regresses by
`+0.01815752` with 95% CI `[+0.00077632,+0.04116776]`. Permanent announcements
and recovery are uncertain; matched announcements miss exact non-regression by
an upper CI endpoint of `+0.00006397`, and matched duplicates are uncertain.

A reusable-only fixed-seat trace explains the remaining permanent idle gap.
Mean idle ticks are `[390.1,8.1,380.0]`; V35 corrected scripted seat 1, but the
learned seat now selects the `+1.0`-biased schematic at tick 0, loses the atomic
claim, and idles exactly 250 ticks in all ten episodes. Removing that prior from
the rejected checkpoint makes seat 0 choose `BUILD_LINE` at tick 0 on every
seed, but the retrospective off-contract run wins only 6/10. The checkpoint
cannot become successor evidence; a collision-free opening must retrain from
scratch under its own precommit.

V35 is rejected, dev-v31 is retired unopened, and held-out-v4 remains sealed.
The baseline records/aggregate hashes are `4c1c654cc32a0502...` and
`72d8a3dec8416859...`; the learned records/aggregate/preflight hashes are
`a75e8826c4f49938...`, `c7f0e58cef9e6144...`, and `fcea6fb297a90399...`.
The fixed-seat diagnostic is `runs/m8-selector-v35-seat0-idle.json`, SHA-256
`4ea36d7d149c5071070cda856b085da20f195b1bf246032e556ba607dbf428d0`.
No dev-v31 or held-out-v4 outcome was observed.
