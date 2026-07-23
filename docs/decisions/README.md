# Architectural Decision Records

Accepted decisions for `mindustry-coop-agents`. These are **settled** — do not
relitigate them in code review; supersede with a new ADR if circumstances change.

| ADR | Title |
|---|---|
| [0001](ADR-0001-exact-engine-fork-monorepo.md) | Exact-engine fork-based monorepo |
| [0002](ADR-0002-external-fixed-step.md) | External fixed-step application |
| [0003](ADR-0003-one-env-per-jvm.md) | One environment per JVM; parallelism via processes |
| [0004](ADR-0004-transport-json-then-protobuf.md) | Transport: length-prefixed JSON now, Protobuf later |
| [0005](ADR-0005-structured-task-communication.md) | Structured task communication |
| [0006](ADR-0006-hierarchical-control.md) | Hierarchical control over deterministic skills |
| [0007](ADR-0007-pettingzoo-framework-neutral-env.md) | PettingZoo facade; framework-neutral env |
| [0008](ADR-0008-ippo-before-mappo-scripted-first.md) | Scripted first; IPPO before MAPPO |
| [0009](ADR-0009-reference-runtime-linux-wsl2.md) | Reference runtime = Linux/WSL2 |
| [0010](ADR-0010-upstream-patch-policy.md) | Upstream patch policy |
| [0011](ADR-0011-rl-dependency-boundary.md) | RL dependencies are training-only and Linux CPU locked |
| [0012](ADR-0012-scenario-variation-and-seed-governance.md) | Bounded scenario variation and seed governance |
| [0013](ADR-0013-post-failure-held-out-renewal.md) | Post-failure held-out renewal |
| [0014](ADR-0014-one-way-dev-confirmation.md) | One-way development confirmation after uncertain scorecards |
| [0015](ADR-0015-v7-cross-commit-blend.md) | V7 cross-commit blend and one-way confirmation |
| [0016](ADR-0016-v8-wait-logit-adjustment.md) | V8 WAIT-logit adjustment and one-way confirmation |
| [0017](ADR-0017-second-post-failure-renewal.md) | Second post-failure held-out renewal |
| [0018](ADR-0018-v9-final-wait-bias.md) | V9 final WAIT-bias step and enlarged confirmation |
| [0019](ADR-0019-third-post-failure-and-preflight-parity.md) | Third post-failure renewal and preflight parity |
| [0020](ADR-0020-v10-full-boundary-teacher-distillation.md) | V10 full-boundary teacher distillation |
| [0021](ADR-0021-v11-v6-v10-blend.md) | V11 V6/V10 governed blend |
| [0022](ADR-0022-v12-quality-aligned-reward.md) | V12 quality-aligned reward v2 |
| [0023](ADR-0023-v13-quality-gated-checkpoint-selection.md) | V13 quality-gated checkpoint selection |
| [0024](ADR-0024-scorecard-v2-forced-abandonment.md) | Scorecard v2 forced-abandonment semantics |
| [0025](ADR-0025-v14-corrected-abandon-boundary-retraining.md) | V14 corrected-abandon-boundary retraining |
| [0026](ADR-0026-v15-stronger-quality-pressure.md) | V15 stronger idle and abandonment pressure |
| [0027](ADR-0027-v16-high-slope-capped-idle.md) | V16 high-slope capped idle pressure |
| [0028](ADR-0028-v17-doubled-capped-idle-slope.md) | V17 doubled capped idle slope |
| [0029](ADR-0029-v18-scorecard-aligned-quality.md) | V18 scorecard-aligned quality reward |
| [0030](ADR-0030-v19-unsaturated-idle-gradient.md) | V19 unsaturated idle gradient |
| [0031](ADR-0031-v20-low-full-boundary-teacher.md) | V20 low full-boundary teacher regularization |
| [0032](ADR-0032-v21-corrected-wait-release-boundary.md) | V21 corrected WAIT-release-boundary retraining |
| [0033](ADR-0033-v22-retry-eligibility-and-agent-loss-boundaries.md) | V22 retry eligibility and agent-loss boundaries |
| [0034](ADR-0034-v23-available-seat-idle-accounting.md) | V23 available-seat idle-accounting retraining |
| [0035](ADR-0035-v24-resource-scoped-retry-boundary.md) | V24 resource-scoped retry-boundary retraining |
| [0036](ADR-0036-v25-moderate-full-boundary-teacher.md) | V25 moderate full-boundary teacher regularization |
| [0037](ADR-0037-v26-final-full-boundary-teacher-step.md) | V26 final full-boundary teacher step |
| [0038](ADR-0038-v27-successful-teacher-trajectory-warmup.md) | V27 successful teacher-trajectory warmup |
| [0039](ADR-0039-v28-successful-teacher-trajectory-rehearsal.md) | V28 successful teacher-trajectory rehearsal |
| [0040](ADR-0040-v29-diverse-successful-teacher-corpus.md) | V29 diverse successful teacher corpus |
| [0041](ADR-0041-v30-budgeted-diverse-teacher-corpus.md) | V30 budgeted diverse successful teacher corpus |
| [0042](ADR-0042-v31-initial-schematic-prior.md) | V31 initial schematic prior |
| [0043](ADR-0043-v32-resource-actionability-staging.md) | V32 resource actionability and proactive staging |
| [0044](ADR-0044-v33-secondary-seat-staging.md) | V33 targeted secondary-seat staging |
| [0045](ADR-0045-v34-claim-loss-decision-boundary.md) | V34 atomic claim-loss decision boundary |
| [0046](ADR-0046-v35-secondary-claim-loss-boundary.md) | V35 secondary-seat claim-loss boundary |
| [0047](ADR-0047-v36-build-line-opening-prior.md) | V36 collision-free build-line opening prior |
| [0048](ADR-0048-v37-seat2-harvest-opening.md) | V37 fixed seat-2 harvest opening |
| [0049](ADR-0049-sealed-seed-membership-exposure.md) | Retire membership-exposed sealed seed sets |
| [0050](ADR-0050-v38-owned-schematic-staging.md) | V38 learned-seat staging beside partner-owned schematics |
| [0051](ADR-0051-selected-only-baseline-runtime-provenance.md) | Selected-only baseline loading and runtime provenance |
| [0052](ADR-0052-v39-structured-partner-intent-risk.md) | V39 structured partner-intent duplication risk |
| [0053](ADR-0053-v39-sealed-test-read-repair.md) | V39 sealed-test read repair and replacement final |
| [0054](ADR-0054-v40-partner-intent-teacher-conflict-filter.md) | V40 partner-intent teacher-conflict filter |
| [0055](ADR-0055-v41-adjacent-frontier-midpoint.md) | V41 adjacent-frontier midpoint |
| [0056](ADR-0056-v42-partner-intent-teacher-conflict-relabel.md) | V42 partner-intent teacher-conflict relabel |
| [0057](ADR-0057-m10-human-control-and-demo-candidate-parity.md) | M10 human control and demo candidate-path parity |
| [0058](ADR-0058-m10-human-evidence-governance.md) | M10 pin-compatible human evidence governance |
| [0059](ADR-0059-m10-paired-human-acceptance-protocol.md) | M10 paired absent/scripted/learned acceptance protocol |
| [0060](ADR-0060-v43-candidate-set-context-actor.md) | V43 candidate-set-context actor |
| [0061](ADR-0061-v44-lagged-boundary-context.md) | V44 lagged-boundary context |
| [0062](ADR-0062-v45-residual-lagged-context.md) | V45 residual lagged context |
| [0063](ADR-0063-v46-expert-defer-control.md) | V46 bounded expert-defer control |
| [0064](ADR-0064-m8-reusable-scorecard-power.md) | M8 reusable-scorecard power correction |
| [0065](ADR-0065-v47-single-brain-death-failover.md) | V47 single-brain death failover |
| [0066](ADR-0066-v48-per-seat-history-cache.md) | V48 per-seat scripted history cache |
| [0067](ADR-0067-retire-held-out-v6-after-manifest-read.md) | Retire held-out-v6 after manifest read |
| [0068](ADR-0068-v49-prospective-scorecard-noninferiority.md) | V49 prospective scorecard non-inferiority |
| [0069](ADR-0069-m9-entry-gate-supersession.md) | Supersede the M9 entry gate after the M8 one-brain ceiling |
| [0070](ADR-0070-m9-ippo-v1-optimization-precommit.md) | Freeze the first M9 IPPO optimization and public comparison |
| [0071](ADR-0071-forced-control-critic-transitions.md) | Keep forced-control transitions in critic targets while masking actor loss |
| [0072](ADR-0072-m9-ippo-v1-public-construction-rejection.md) | Reject M9 IPPO v1 at public construction |
| [0073](ADR-0073-m9-ippo-v2-sequence16-precommit.md) | Freeze M9 IPPO v2 sequence-16 learning |
| [0074](ADR-0074-m9-ippo-v2-sequence16-rejection.md) | Reject M9 IPPO v2 at public construction |
| [0075](ADR-0075-m9-ippo-v3-diverse2048-precommit.md) | Freeze M9 IPPO v3 diverse one-use roots |
| [0076](ADR-0076-m9-ippo-v3-diverse2048-rejection.md) | Reject M9 IPPO v3 at public construction |
| [0077](ADR-0077-m9-v3-policy-mode-diagnostic-precommit.md) | Freeze the immutable-v3 policy-mode diagnostic |
| [0078](ADR-0078-m9-v3-policy-mode-diagnostic-result.md) | Accept the v3 categorical-sampling diagnostic signal |
| [0079](ADR-0079-m9-ippo-v4-entropy-anneal-precommit.md) | Freeze M9 IPPO v4 entropy annealing |
| [0080](ADR-0080-m9-ippo-v4-entropy-anneal-rejection.md) | Reject M9 IPPO v4 at public construction |

Each ADR follows: Context / Decision / Alternatives / Consequences / Reversal
conditions.
