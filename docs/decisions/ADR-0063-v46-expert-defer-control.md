# ADR-0063: V46 bounded expert-defer control

**Status:** Accepted

## Context

V45 reproducibly reaches 10/10 reusable wins and improves every remaining
scorecard mean, but its permanent announcements/idle and matched recovery
intervals still cross zero. It is rejected before confirmation. Dev-v41 is
retired unopened and unconsumed; held-out-v6 remains sealed and unconsumed.

The decisive reusable outlier is outside the selector's ordinary authority.
On root 2004, V45 makes five SELECT decisions and then records 65 WAIT actions;
all 65 are forced (`policy_loss_mask=false`). The transition into that state
follows the only legal non-WAIT defense candidate, and the adaptive scripted
expert selects the same defense action. More selector memory cannot act during
the forced interval.

The project owner has explicitly authorized a learned-control scope expansion.
The smallest expansion that preserves the server protocol and every accepted
safety rule is one-boundary deferral to the already-computed deterministic
adaptive expert. This gives the learned brain access to stateful scripted
lifecycle judgment without permitting raw engine mutation or policy control of
forced safety actions.

## Decision

1. V46 keeps V45's runtime, typed server action vocabulary, masks, reward,
   roots, training budget, optimizer, RNG values, partner intent, teacher
   relabeling, scripted partner opening, engine pins, and ordinary ten-action
   actor exact.
2. Policy action schema `selector_control_actions_v2_expert_defer` adds index 10
   `DEFER_TO_SCRIPTED_EXPERT`. The action is training/runtime-adapter metadata,
   not a new protocol message. It translates to the canonical adaptive-v1
   seat-0 action already computed from the same immutable boundary.
3. DEFER is legal only at an otherwise unforced policy boundary when the expert
   proposes a legal ordinary non-WAIT action. It cannot override deterministic
   ABANDON, blocked replan, death, termination, truncation, a single-legal-action
   boundary, or any other scripted safety/lifecycle force. Expert WAIT is not
   duplicatively exposed as DEFER.
4. The trajectory records both the policy control index and the effective
   submitted ordinary index/action. `SelectorHistory` advances with the
   effective submitted index (0..9), so authoritative temporal semantics remain
   V45-exact. Server observations, state hashes, and action application remain
   unchanged.
5. Feature schema `selector_features_v3_expert_defer` contains V45's exact
   160 scalars plus a ten-way one-hot of the same-boundary canonical expert
   proposal. The proposal is derived entirely from the already-computed
   structured action; it performs no engine read and never contains task ids,
   coordinates, prose, or mutable policy state.
6. Model schema `selector_actor_critic_v5_expert_defer_control` constructs the
   complete V45 model first in exact module order. A 10->16->16 expert-action
   encoder and 208->64->1 DEFER head are appended. The DEFER output layer starts
   at exact zero. The ordinary ten logits and critic remain V45-exact for the
   same seed and first 160 scalars.
7. Teacher warmup, rehearsal, and PPO teacher imitation remain defined only over
   ordinary actions 0..9. They neither label nor suppress DEFER. PPO/entropy
   alone optimize the control choice against the unchanged audited reward.
8. DEFER itself has no reward component. Telemetry records legal opportunities,
   chosen deferrals, effective actions, and defer fraction. Invalid selection
   fails to canonical WAIT through the existing invalid-action path and is
   charged exactly as before.
9. A checkpoint is ineligible if mean reusable expert-defer fraction exceeds
   `0.25` of unforced policy decisions. The same cap is mandatory in reusable,
   confirmation, and final preflight evidence. This keeps at least 75% of
   learned-seat policy decisions directly selected and prevents promotion by
   cloning the scripted expert.
10. Focused tests must prove V45 ordinary-logit/value equality, exact mask and
    translation rules, expert-WAIT/forced-action exclusion, effective-history
    recording, deterministic initialization, ordinary-only teacher loss,
    invalid fallback, telemetry, cap enforcement, reset isolation, and
    historical v1-v4 compatibility.
11. The complete public/pretraining boundary and all exact-config reward
    adversaries must pass before dev-v42 construction or model work. Replica A
    retains the 256-episode warmup and 2,048-episode/32-update budget and must
    reach at least 9/10 reusable wins, idle below `0.25`, and mean DEFER at or
    below `0.25` before replica B.
12. Dev-v41 remains retired unopened and unconsumed. V46 reserves primary-only
    dev-v42 at 160 roots in `[10_000_000_000,11_000_000_000)`. Membership may
    be constructed value-free only after the committed implementation and full
    pretraining boundary. Held-out-v6 remains sealed under ADR-0053.

## Alternatives

- A GRU, longer boundary history, or another selector scorer cannot directly act
  during the 65 forced WAIT boundaries and is not authorized by V45 evidence.
- Giving the learned policy raw ABANDON, movement, retreat, pause, or safety
  override authority is broader and could violate deterministic lifecycle and
  human-safety invariants.
- Always falling back to the expert would be a scripted runtime patch, not a
  learned coordination brain. The learned DEFER decision and 25% cap prevent
  that outcome.
- Relaxing the reusable confidence gate after seeing V45 would be
  outcome-driven and would compromise the held-out claim.

## Consequences

- ADR-0063 narrowly supersedes the selector-only action count in ADR-0011 and
  `docs/M8_DESIGN.md`; it does not supersede their typed-action, mask, reward,
  determinism, threading, or promotion requirements.
- V46 remains one learned coordination brain and one environment per JVM. The
  expert is deterministic local code already required for teammates/teacher
  evidence; no model, service, dependency, or I/O path is added to the loop.
- The immutable config is
  `configs/training/m8-selector-v46-expert-defer-control.json`, SHA-256
  `b588ee43e66bd9d13a9bee5bacac08251cd4c49c3f8d5726eaf2675f06d5d835`.
- The value-free confirmation umbrella is
  `configs/evaluation/m8-selector-v46-confirmation-umbrella.json`, SHA-256
  `a78631d7ba9f1cd20d46da6dd44822f4440209b3c9d1d760c2607af1f1d64e71`.
- This precommit authorizes implementation and public/pretraining verification
  after commit. It does not authorize dev-v42 construction, model training,
  confirmation access, or held-out-v6 access.

## Implementation evidence

The policy-side adapter, feature v3, model v5, effective-action history,
ordinary-only teacher losses, validated telemetry, and all four 25% cap
enforcement points are implemented. V45's ordinary logits, masked logits, and
critic are bit-exact at V46 initialization; the separately encoded DEFER output
is exact zero.

Thirteen focused V46 tests and the complete 335-test embargo-safe Python suite
pass. Pinned Java/custom-module checks, public survival 5/5 with ten staging
starts, both focused coordination checks, smoke, accepted golden/negative
determinism, and all 44 exact-config reward adversaries pass. The reward report
SHA-256 is
`ec3acb4c1056207a1f83729cb62e5c38042164c5688e67c18c6d842d96a54b9e`.
Dev-v42 remains unconstructed; no V46 training/checkpoint, confirmation read,
or held-out read occurred.

The primary-only dev-v42 freezer is implemented on commit-bound atomic/no-read
primitives and covered by the now-339-test embargo-safe suite. It has not
executed and must be committed before membership construction.

The committed generator `e9a828a7d01ed7e9...` constructed dev-v42 value-free.
Its receipt binds membership
`8f518384f19c193fa793034a141c0a89c6973dbe788de87520a6b86b16bed865`
and implementation `173cd5c2a11f3237...`, and records zero membership reads.
Dev-v42 is frozen and unconsumed; the receipt-aware suite passes 340 tests.

Two pinned replicas select update 32 exactly at 10/10 public-dev wins, idle
`0.01033305`, and mean DEFER `0.18420177`. Checkpoint and full-run prefixes are
`93694e4d70ec56e4...` and `8d61abfa4ce4fe10...`. Direct-lineage validation now
binds the explicit control-v2 coordinate after failing closed on its initial
omission; all 341 tests pass. No reusable or restricted episode has run.
