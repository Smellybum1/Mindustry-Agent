# ADR-0087: Precommit M9 IPPO v6 successful-action margin alignment

**Status:** Accepted

## Context

ADR-0086 accepts that rejected v5 update 32 retained 62/160 categorical wins
while deterministic argmax remained 0/40. V5's chosen-action NLL did not make
successful sampled decisions reliably become the deterministic mode. The next
bounded mechanism should target action ordering directly rather than add
another probability objective.

## Decision

1. Freeze `m9-ippo-v6-success-margin`, derived from immutable v4 rather than
   v5. Its config is
   `configs/training/m9-ippo-v6-success-margin.json`, SHA-256
   `bd8e84acd0e340b61933677608395da3b8d214469e89841ecfa1fd47fde8114b`.
   Its public protocol is
   `configs/evaluation/m9-ippo-v6-success-margin-public-protocol.json`,
   SHA-256
   `f0adddd4c8b2127af68a55dff80610363a8b7c5e629049b5caba5a3a311b55ac`.
2. V6 changes exactly one learning mechanism from v4: add a
   success-conditioned strongest-alternative hinge loss to each existing PPO
   minibatch. V4's inclusive entropy schedule remains exact. V5's
   chosen-action NLL is absent.
3. A transition qualifies only when its current-update rollout has
   authoritative terminal outcome `win` and its existing `policy_loss_mask` is
   true. Forced controls, critic-only transitions, losses, and prior updates
   are excluded.
4. For each qualifying transition, let `z_sampled` be the sampled action logit
   after the authoritative action mask and let `z_other` be the maximum logit
   among every other authoritatively legal action. Add:

   `0.02 * mean(relu(0.1 - (z_sampled - z_other)))`

   to the existing PPO/value/entropy loss. The `0.1` target is a prospectively
   fixed small positive ordering margin; it is not calibrated from ADR-0085's
   descriptive values. A minibatch with no qualifying transition contributes
   exact differentiable zero.
5. Apply the term in every existing shuffled minibatch in each of the existing
   eight PPO epochs. It adds no pass, replay, teacher, cross-update state,
   episode, root, RNG draw, or NLL.
6. Record coefficient, target margin, qualifying episode count, qualifying
   transition count, active-minibatch count, and mean active-minibatch hinge
   loss for every optimizer update.
7. V4's initialization, architecture, one-boundary recurrence, 2,048 unique
   roots, 32-by-64 budget, reward, GAE, remaining PPO values, RNG seeds, public
   dev set, shared-expert baseline, checkpoint ranking, 30/40 plus idle
   `<0.25` construction bar, engine pins, and deterministic argmax evaluation
   remain exact.
8. Before any v6 trajectory or model update, implementation must be committed
   and prove exact v4 inheritance, exact strongest-other masking, sampled-action
   exclusion from the alternative set, win/actor filtering, empty-filter zero,
   all-eight-epoch application, telemetry, no extra RNG, v1--v5 compatibility,
   candidate-aware artifact/preflight/runner paths, deterministic twin
   synthetic updates, full tests, focused M9 checks, smoke, determinism, and
   golden replay.
9. Replica A runs the full immutable budget only after an exact-current-commit
   public gate. Replica B is authorized only if A passes construction and must
   reproduce the exact full run and selected checkpoint before comparison.
10. No M9 confirmation or held-out namespace exists. M8 held-out-v7 remains
    sealed.

## Alternatives

- Inherit v5 and add the hinge beside NLL is rejected because it combines two
  successful-action objectives and cannot isolate the margin mechanism.
- Lower or retune v5's NLL coefficient is rejected because ADR-0086 authorizes
  a different mechanism, not post-result NLL tuning.
- Use checkpoint-derived action margins as the target is rejected because
  ADR-0085 declared those measurements descriptive and non-tuning.
- Change evaluation to categorical is rejected because deterministic argmax is
  the frozen construction contract.

## Consequences

- V6 is a direct successful-action ordering experiment, not a probability NLL
  retry.
- The strongest-other computation must exclude the sampled action and every
  illegal action without introducing NaNs for masked logits.
- No v6 implementation, trajectory, optimizer update, or changed model exists
  at this precommit.
