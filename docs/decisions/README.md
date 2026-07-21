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

Each ADR follows: Context / Decision / Alternatives / Consequences / Reversal
conditions.
