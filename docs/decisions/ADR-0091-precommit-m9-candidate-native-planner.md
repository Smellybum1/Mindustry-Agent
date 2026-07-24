# ADR-0091: Precommit M9 candidate-native planner v1

**Status:** Accepted

## Context

ADR-0090 closes direct projection from `ExpertCoordinationDriver`: only
65/3,833 internal expert selections matched one same-boundary ordinary
candidate. The next supervision source must therefore originate on the
authoritative candidate/mask action surface instead of repairing the legacy
expert's private tasks.

Public architecture evidence also identifies a concrete defect in the ordinary
greedy comparator. Each seat independently chooses its highest-utility
candidate. At the randomized M9 opening boundary all seats can choose the same
exclusive schematic, so the atomic team bundle rejects the collisions while
the line and economy candidates go unclaimed. A useful teacher must coordinate
the bundle before submitting it.

## Decision

1. Freeze `candidate-native-planner-v1` under
   `configs/evaluation/m9-candidate-native-planner-v1-protocol.json`, SHA-256
   `4c1981c4ced305a2966153b6279acd8745e10bd59db7e365e1a91ba763cccedc`.
2. The planner may consume only authoritative per-seat observations and action
   masks, the structured task board, prior accepted action results, and bounded
   reset-local private state. It may not read mutable engine state, any
   `ExpertCoordinationDriver` state or decision, a future outcome, or governed
   confirmation/held-out membership.
3. Every action must use the ordinary external candidate path. In deterministic
   agent-id order the planner handles forced dead-seat WAIT, bounded blocked
   replans, wave preemption, accepted work continuation, combat
   defense/logistics allocation, distinct opening line/schematic/harvest
   allocation, readiness-priority allocation, a nonconflicting utility
   fallback, then WAIT.
4. The planner must reserve each exclusive task id and each task-type/semantic-
   target pair across the atomic bundle. Ties are resolved only by frozen phase
   priority, descending candidate utility, ascending candidate index, then
   ascending agent id.
5. Evaluate only the existing 40 public M9 dev-v1 roots. Run two fresh JVMs and
   a terminal-reset replay. Canonical reports must be byte-identical, all
   submitted actions accepted, no nonordinary fallback used, and no cross-seat
   exclusive conflict emitted.
6. Classify the planner as a supported supervision source only at 30/40 wins,
   at least 80% retention of the frozen 36-win source expert, and at least 95%
   non-WAIT selection coverage at unforced boundaries. Failure rejects this
   planner version and requires a separately precommitted successor.
7. Commit the protocol and this ADR before implementation. Commit the
   implementation and focused tests before the first governed 40-root run.
8. This decision does not authorize v7 model construction, training,
   checkpoint selection, MAPPO, confirmation access, or held-out access. A
   passing planner would authorize only a separate prospective supervision
   corpus and v7 recipe.

## Alternatives

- Task-type-only projection from the legacy expert remains rejected by
  ADR-0090 because multiple semantically different candidates share a type.
- Independent per-seat utility maximization is rejected as the supervision
  source because its collisions are the observed architecture defect.
- A post-result search over role tables or thresholds is rejected. Any failed
  planner revision must be explained from public traces and frozen separately.
- Training directly from public-dev decisions is rejected; this gate validates
  the planner, not a model or training corpus.

## Consequences

- The next implementation is a small deterministic team allocator over the
  existing authoritative action surface.
- External fixed stepping, simulation-thread ownership, structured
  communication, engine pins, reward definitions, actor vocabulary, and all
  sealed-set boundaries remain unchanged.
- No restricted data has been accessed.
