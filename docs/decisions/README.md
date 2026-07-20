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
| [0012](ADR-0012-scenario-variation-and-seed-governance.md) | Bounded scenario variation and seed governance |

Each ADR follows: Context / Decision / Alternatives / Consequences / Reversal
conditions.
