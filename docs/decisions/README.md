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

Each ADR follows: Context / Decision / Alternatives / Consequences / Reversal
conditions.
