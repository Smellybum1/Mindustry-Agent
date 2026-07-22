# ADR-0052: V39 structured partner-intent duplication risk

**Status:** Accepted

## Context

V38 reproduces exactly at 9/10 reusable wins, but its frozen dual scorecards
remain ineligible. Permanent-greedy announcements, duplicates, and idle are
uncertain; matched-greedy duplicates and recovery are uncertain. Four
parity-controlled V39 diagnostics reject rendered-WAIT suppression, learned
claim-loss wake, exact-death recovery bias, and supply-only collision
rewriting. No confirmation or held-out membership was used.

The reusable decision trace contains 20 duplicate incidents. Every incident is
an authoritative same-task `CLAIMED -> CLAIMED` transition: 18 are supply
collisions and two are harvest collisions. Existing broad partner-intent
masking changed 48 choices and fell to 7/10 because it forced the learned seat
away from the partner's task even when the replacement was strategically
worse. The current learned model already receives a normalized
`duplication_risk` candidate feature, but that feature reflects established
board state only. The deterministic fixed-seat actions are computed before the
learned selector at the same structured boundary, so their exact selected task
identities are available without another engine read or speculative text
interpretation.

The missing coordinate is evidence, not enforcement: let the learned selector
observe that a fixed partner intends the exact same task, while preserving its
ordinary mask and authority to select that task anyway.

## Decision

1. V39 holds V38 exact except for one selector-input coordinate. Before the
   learned seat selects, exact task IDs selected by fixed scripted seats 1 and
   2 at that same boundary raise the matching learned candidate's existing
   normalized `utility_features.duplication_risk` input to `1.0`.
2. Matching is exact `task_id` equality. Task type, target text, candidate
   index, rendered announcement, or heuristic similarity cannot substitute.
   A malformed selected-candidate index or missing/non-string task ID fails
   closed. Non-`SELECT_CANDIDATE_TASK` fixed actions add no intended task.
3. The feature is derived solely from the structured fixed-seat action bundle
   that is already computed before learned selection. It does not read mutable
   game state outside the simulation boundary, mutate an observation, create a
   task-board event, or apply an action early.
4. V39 does not mask, force, redirect, suppress, reorder, or rewrite any
   learned or scripted action. The server catalog, authoritative action mask,
   task lifecycle, fixed seat-2 harvest opening, fixed seat-1 claim-loss wake,
   V38 owned-schematic staging, reward, action vocabulary, feature dimensions,
   model architecture, optimizer, roots, budgets, RNGs, and checkpoint ranking
   remain exact.
5. The coordinate is explicitly configured as
   `fixed_partner_selected_task_duplication_risk_v1`. Configurations that omit
   it retain byte-for-byte V38 feature construction and historical checkpoint
   behavior.
6. Before model work, focused tests must prove exact-task positive exposure,
   nonmatching and non-select negative cases, two-partner idempotence,
   malformed-action rejection, nonmutation, and historical no-config parity.
   A replay diagnostic with the V38 checkpoint must archive which choices the
   feature changes and must retain full action/tick/state/outcome parity when
   the feature is disabled.
7. The complete pretraining boundary remains required: Python and pinned Java
   suites, the public candidate-policy survival/staging gate, smoke,
   cross-process/reset/seed determinism, golden replay plus negative control,
   and all exact-config reward adversaries. Any public survival or required
   staging regression rejects V39 before training.
8. Replica A uses the exact V38 train/dev roots, teacher, reward, model,
   optimizer, 2,048-episode/32-update budget, and RNGs. It must reach at least
   9/10 reusable construction wins with mean idle below `0.25` before replica
   B. Passing twins must match every governed checkpoint, model, replay,
   frontier, teacher, full-run, and direct-lineage digest.
9. ADR-0051 remains authoritative. The changed config hash requires fresh
   selected-only permanent baselines with exact repository/config/JAR
   provenance. Reusable observed win comparisons and both frozen scorecards
   must pass; uncertainty is failure.
10. Dev-v34 remains retired unopened and unconsumed. After this precommit is
    committed, primary-only construction may freeze dev-v35 under a committed
    value-free umbrella. No dev-v35 membership may be delegated, rendered, or
    consumed before exact replicas and reusable scorecards pass. Held-out-v5
    remains the sealed, unconsumed final set and may not be read before a fully
    eligible dev-v35 confirmation.

## Alternatives

- Partner-intent masking and collision redirection remain rejected because
  they enforce a replacement and already reduced reusable survival.
- Adding a new feature dimension is unnecessary: `duplication_risk` already
  represents this exact semantic and remains normalized in `[0,1]`.
- Learned claim-loss wake, rendered-WAIT suppression, exact-death recovery
  bias, and supply-only rerouting remain rejected by ADR-0050's recorded
  diagnostics.
- Sequentially applying scripted actions before learned selection is rejected;
  it would change the external action boundary and expose post-action state.

## Consequences

- V39 must retrain because candidate features can differ at same-boundary
  partner intent, even though the model shape and server runtime stay exact.
- Structured intent becomes learnable evidence rather than an orchestration
  override. The learned selector may still choose the same task when its
  learned value outweighs duplication risk.
- Permanent baselines are behaviorally unchanged by the selector-only feature,
  but ADR-0051 provenance still requires refreshing them for the V39 config.
- This ADR authorizes implementation gates and the value-free dev-v35 freeze;
  it does not authorize replica A until those gates are green, confirmation
  consumption, or held-out access.

The precommit packet passes 177 Python tests. All 44 exact-config reward
adversaries pass for config SHA-256
`0b883c41ab297a132aa40c9c43bd5760c13a7afb5d6239fe9666d00b80f2f995`;
the ignored report SHA-256 is
`7bd71c1c9b5de869bab1d852fb26244c1c313f56797ce9dff0287147b531ef76`.
No V39 feature implementation, dev-v35 membership construction, baseline
episode, or model work preceded this decision.
