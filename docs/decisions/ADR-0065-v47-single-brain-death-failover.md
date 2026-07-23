# ADR-0065: V47 single-brain death failover

**Status:** Accepted

## Context

ADR-0064's 160-root public screen rejects V46 despite 96/160 wins because its
permanent-greedy announcement interval crosses zero and idle is unfavorable.
The larger sample localizes the problem rather than merely reducing interval
width.

The learned controller is hard-bound to agent 0. Once that unit dies,
`build_selector_features` correctly forces WAIT forever for that seat, even
while agents 1 or 2 remain alive and continue under scripted control. On 63
roots where seat 0 dies before tick 3000, candidate-minus-permanent-greedy idle
averages `+0.02701331` and announcements `+0.00769989`; V46 wins only 24.
On 94 roots with a later seat-0 death, idle averages `-0.01336557`,
announcements `-0.00519967`, and V46 wins 69. All 30 greedy-only wins contain a
seat-0 death. The worst traces contain more than 100 forced WAIT boundaries
after early death.

This is an authority-placement defect, not a missing score feature: the model
cannot act after its fixed body dies. The public diagnostic is
`configs/evaluation/m8-selector-v46-reusable-v2-death-failover-diagnostic.json`.
No confirmation, retired, or held-out membership was read.

## Decision

1. V47 retains exactly one learned coordination brain and at most one learned
   action per boundary. It starts on agent 0 and remains sticky while that unit
   is alive.
2. When the active learned unit is observed dead at an authoritative boundary,
   control transfers deterministically to the lowest-ID living agent. It never
   switches for score, workload, location, role, or model preference. If no
   unit is alive, the existing forced-WAIT/terminal path remains authoritative.
3. A transfer changes only which existing observation, mask, candidate table,
   canonical adaptive expert proposal, and task-action bundle slot pass through
   the learned selector. It adds no protocol action, mutable-state read, engine
   mutation, I/O path, or simulation-thread exception.
4. `SelectorHistory` resets on transfer. The new active unit's current
   health/position/cargo/skill/task candidates already occupy the frozen feature
   schema, so feature v3, model v5, reward v2, and control v2 remain exact.
5. Structured partner intent becomes the set of all living nonactive agents.
   The active agent is excluded, dead agents contribute no intended task, and
   teacher conflict relabeling remains otherwise exact.
6. The adaptive expert proposal is computed for the active learned agent.
   DEFER translation, forced safety/lifecycle priority, effective-action
   history, and the inclusive `0.25` mean-DEFER gate remain unchanged.
7. Training, evaluation, and matched random/greedy controls use the same
   deterministic active-seat sequence. Telemetry records active agent ID,
   transfer tick/from/to/reason, brain-active policy decisions, and proves
   `maximum_simultaneous_learned_seats=1`.
8. V47 changes only the adapter authority placement and its explicit manifest
   schema. Training roots, ten-root checkpoint-selection set, model, feature,
   reward, optimizer, warmup/rehearsal, PPO budget, RNG values, partner opening,
   engine pins, and ordinary/control action vocabulary remain V46-exact.
9. Focused tests must prove sticky lowest-ID failover, history reset, dynamic
   partner intent, active-seat teacher/DEFER translation, forced/terminal
   priority, one-brain telemetry, deterministic replay, reset isolation,
   matched-control parity, and unchanged V46 behavior when agent 0 survives.
10. The full public/pretraining boundary and exact-config reward adversaries
    must pass before confirmation membership or model work. Replica A must
    reach at least 9/10 construction wins, idle below `0.25`, and mean DEFER at
    or below `0.25`; exact replica B, direct lineage, fresh 160-root permanent
    baselines, mobile matched baselines, and both reusable-v2 scorecards remain
    mandatory.
11. V46 failed, so the dev-v43 reservation is cancelled without construction
    or membership read. V47 reserves dev-v44 at 160 roots in
    `[13_000_000_000,14_000_000_000)`. It may be constructed value-free only
    after the committed implementation and full pretraining boundary.
12. Dev-v42 remains retired unopened/unconsumed. Held-out-v6 remains sealed and
    unconsumed; no final access is authorized.

## Alternatives

- Learning all seats simultaneously is M9 and would abandon M8's one-brain
  proof. V47 keeps one active learned controller.
- Switching to whichever seat looks most useful is rejected because it expands
  policy authority and creates a new learned assignment problem.
- Continuing to optimize the dead seat is impossible; its mask is correctly
  forced by safety/lifecycle semantics.
- Relaxing permanent-greedy scorecards is rejected. V47 must pass the unchanged
  ADR-0064 rule.
- Reviving dev-v42 or constructing the cancelled dev-v43 reservation is
  prohibited.

## Consequences

- The learned brain gains temporal continuity across unit loss but never
  controls two agents at once. Remaining scripted seats and every server-side
  action check stay intact.
- Matching controls must adopt the same active-seat failover or comparisons
  would confound policy quality with controller uptime.
- The immutable V47 config is
  `configs/training/m8-selector-v47-single-brain-death-failover.json`, SHA-256
  `ff112f910c13603ccb8190a42dcf45027c65343233aae6d88894d7963704966f`.
- The value-free confirmation umbrella is
  `configs/evaluation/m8-selector-v47-confirmation-umbrella.json`, SHA-256
  `8e6fccc9d07de4efcac14dab34beb561f71aee0a4657a1309c6f6e73dca4c9f0`.
- This precommit authorizes implementation and public/pretraining verification
  after commit. It does not authorize dev-v44 construction, training,
  reusable-v2 evaluation, confirmation, or held-out access.

## Implementation evidence

The adapter, matched controls, lineage binding, reusable/final promotion gates,
and dynamic partner-intent path are implemented. A public live JVM gate on root
`11307756240` observes exact death-only transfers `0->1` at tick 2738 and
`1->2` at tick 4462, keeps
`maximum_simultaneous_learned_seats=1`, and survives to the tick-9000 win.
Focused V47 tests and the complete 348-test Python suite pass. Pinned Java
tests/custom-module compilation, public 5/5 survival with ten proactive staging
starts, secondary-claim wake, owned-schematic staging, smoke, cross-process and
reset determinism, the 664-checkpoint golden plus negative replay, and all 44
exact-config reward adversaries also pass. The adversary report SHA-256 is
`5e6aec4530d278234e650a334ffb9801214846b1a4165c1a3805dfe29c372826`.

Dev-v44 remains unconstructed and no V47 training episode has run. Membership
construction still requires this implementation/evidence boundary to be
committed first.

The primary-only dev-v44 freezer is now implemented on the committed atomic
no-read primitives. It pins the exact V47 implementation/config/umbrella,
public reusable-v2 hash, cancelled dev-v43 namespace, retired dev-v42 state,
and sealed held-out-v6 contract. Its receipt contains no membership values.
The complete embargo-safe suite passes 352 tests. The freezer has not executed;
commit it before membership construction.
