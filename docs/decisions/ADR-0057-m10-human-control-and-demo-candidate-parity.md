# ADR-0057: M10 human control requires demo candidate-path parity

**Status:** Accepted

## Context

M10.1 requires validated, confirmable, revocable human goals and overrides on
the same brain that trains. Training and evaluation select through the bounded
`EngineCandidates` table and `CoordinationAdapter` typed-action path. The
real-time plugin still drives `ExpertCoordinationDriver`, which shares scenario
plans, utility, board semantics, and skills but retains stage-local candidate
construction. `docs/CANDIDATE_GAPS.md` already records this remaining seam.

Directly adding `/agents goal` to the plugin driver could make a demo work while
creating a second policy/skill path that no learned selector can exercise. It
would also tempt command callbacks to read game state or mutate the board before
the simulation thread, violating the hard threading rule.

## Decision

1. M10 scripted/demo work may proceed while M8/M9 learning remains gated, but it
   neither authorizes a new learned candidate nor any confirmation/held-out
   access.
2. Before applying human goals, the real-time plugin must use the same public
   candidate ordering, masks, typed task actions, `CoordinationAdapter`, board,
   reservations, and skill execution path as the externally stepped runtime.
   A Java scripted fallback may choose among those candidates, but may not own a
   second candidate catalog or call skills directly.
3. Human control is structured in `agent-core`: commands, goals, assignments,
   autonomy, quiet state, snapshots, and application events. Rendered text is
   derived and nonauthoritative. The 13 coordination acts remain unchanged.
4. I/O callbacks may parse and enqueue immutable commands only. The simulation
   thread performs stateful validation and mutation before a policy boundary.
5. Human goals become ordinary candidates by wrapping a safe matching public
   candidate. `TaskOrigin.HUMAN` drives the existing `human_priority` feature;
   target/cost/capability/skill data remains sourced from the ordinary catalog.
   No match means a structured blocked result, never a fabricated action.
6. Explicit assignment is enforced through ordinary masks and claim authority,
   not direct board ownership. Release and cancellation use ordinary structural
   lifecycle transitions and reservation release.
7. `LOW`, `NORMAL`, `HIGH`, and quiet semantics are pinned by
   `docs/M10_DESIGN.md`. Emergency/safety lifecycle rules remain authoritative.
8. The empty-control default must preserve existing candidates, masks, decisions,
   action/state hashes, demo survival, and replay evidence exactly. Any later
   policy-visible control features require a new schema/version and learning
   governance.

## Alternatives

- Add commands only to `DemoCoordinator`/`ExpertCoordinationDriver`: rejected as
  a privileged demo-only brain.
- Have commands directly propose/claim board tasks or set skills: rejected
  because it bypasses candidate masks, atomic claims, and the learned seam.
- Encode intent in chat strings or task-id prefixes: rejected because structured
  communication is authoritative and identity must not depend on prose.
- Expand the coordination-act enum for control commands: rejected; commands are
  a separate control plane and resulting task lifecycle already has board acts.
- Start M9 partner learning first: rejected by ADR-0013 and successors; M9
  remains gated on an M8 promotion.

## Consequences

- M10.1 begins with a nontrivial demo-policy-port refactor rather than command
  parsing. This is required work, not optional cleanup.
- No-command parity supplies a strong regression oracle and keeps existing
  training evidence valid.
- Human goals inherit action validation, task arbitration, reservations,
  telemetry, and future learned-policy compatibility instead of duplicating
  them.
- Implementation must update architecture/protocol documentation and add the
  acceptance gates in `docs/M10_DESIGN.md` before the roadmap item is checked.

## Reversal conditions

Supersede this ADR only if the project replaces the public candidate/action seam
for both training and demo together. A demo-only shortcut is not a reversal
condition.
