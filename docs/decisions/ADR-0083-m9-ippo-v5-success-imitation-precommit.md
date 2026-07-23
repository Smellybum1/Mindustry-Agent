# ADR-0083: Precommit M9 IPPO v5 success-conditioned self-imitation

**Status:** Accepted

## Context

ADR-0082 accepts ADR-0081's predeclared deterministic-mode-instability signal.
Rejected v4 update 32 retained 60/160 categorical public-dev wins, 93.75% of
update 31's 64/160, while deterministic argmax collapsed from 18/40 to 0/40.
The policy distribution therefore retained substantial successful behavior;
the missing mechanism is making that sampled behavior more probable at the
deterministic mode.

V4 already isolates entropy annealing, uses 2,048 unique public roots once,
and produces 603 stochastic training wins. The successor must use those
within-candidate successes without adding teacher data, replay selection,
episodes, roots, reward changes, or restricted evidence.

## Decision

1. Freeze the successor as `m9-ippo-v5-success-imitation`, derived from
   immutable rejected v4. Its config is
   `configs/training/m9-ippo-v5-success-imitation.json`, SHA-256
   `056a6ee24363b55aac62762c3854ff0aa5bb190df8c05fad7ab5fcf5be332002`.
   Its public protocol is
   `configs/evaluation/m9-ippo-v5-success-imitation-public-protocol.json`,
   SHA-256
   `205508d8cfaba9109825d1b31fb13dc295e0d988296aef89379980f5b559b460`.
2. V5 changes exactly one learning mechanism from v4: add
   success-conditioned self-imitation to each existing PPO minibatch. V4's
   inclusive entropy schedule from `0.02` to `0.0` remains exact.
3. A transition qualifies for self-imitation only when:
   - its enclosing current-update rollout has authoritative terminal outcome
     `win`; and
   - its existing `policy_loss_mask` is true.
   Forced controls, critic-only transitions, losses, and all prior updates are
   excluded.
4. For qualifying transitions present in one shuffled PPO minibatch, compute
   the mean negative log probability of the action actually sampled after the
   authoritative mask. Add it to the existing loss with constant coefficient
   `0.02`:

   `total = ppo_policy + 0.5 * value - scheduled_entropy * entropy
            + 0.02 * successful_action_nll`

   A minibatch with no qualifying transition contributes exact differentiable
   zero for this term. Gradient clipping and the Adam step remain unchanged.
5. The term runs in the existing minibatch order on each of the existing eight
   PPO epochs. It adds no pass, replay buffer, cross-update state, root,
   episode, teacher, or RNG draw. The coefficient `0.02` equals v4's frozen
   maximum entropy-incentive magnitude and remains constant while entropy
   anneals.
6. Record per optimizer update: coefficient, qualifying winning-episode count,
   qualifying transition count, active-minibatch count, and mean loss over
   active minibatches. These fields are authoritative manifest telemetry.
7. V4's exact model initialization and architecture, one-boundary recurrence,
   2,048 unique one-use public roots, 32-by-64 budget, rewards, GAE, other PPO
   values, four RNG seeds, public dev roots, shared-expert baseline,
   checkpoint ranking, 30/40 plus idle `<0.25` construction bar, engine pins,
   and official deterministic argmax evaluation remain exact.
8. Before any v5 trajectory or model update, implementation must be committed
   and prove:
   - exact v4 inheritance outside the named identity, protocol, and
     self-imitation fields;
   - exact win/actor filter, forced-control exclusion, empty-filter zero, and
     sampled-action masked NLL;
   - exact coefficient application on every PPO minibatch and all required
     telemetry;
   - no cross-update replay, extra pass, teacher, RNG, episode, or restricted
     data;
   - deterministic twin synthetic updates, candidate-aware
     checkpoint/manifest/preflight/runner/failure paths, v1--v4 compatibility,
     the full Python and pinned Java suites, M9 focused checks, smoke,
     determinism, and golden replay.
9. Replica A runs the full immutable budget after an exact-current-commit gate.
   If A has no eligible checkpoint, v5 is rejected and Replica B does not run.
   If A passes, B must reproduce the full run and selected checkpoint before
   paired public comparison.
10. MAPPO remains prohibited unless exact v5 replicas satisfy every frozen
    public paired gate. No M9 confirmation or held-out namespace exists. M8
    held-out-v7 remains sealed.

## Alternatives

- An optimizer-step stabilizer is rejected for v5 because update 32 retained
  93.75% of update 31's categorical wins and failed ADR-0081's distribution
  collapse criterion.
- External expert behavior cloning is deferred because the accepted signal
  supports using the candidate's own sampled successes without a teacher.
- Cross-update replay of successful episodes is rejected because it adds
  storage, stale-policy selection, and a second exposure schedule.
- Imitating losses or forced controls is rejected because neither identifies
  successful learned decisions.
- Changing reward, entropy schedule, learning rate, recurrence, roots, budget,
  or official evaluation is rejected because it would mix mechanisms.

## Consequences

- V5 is a bounded successful-mode consolidation test, not a general PPO
  retune.
- Rollout outcome membership must flow deterministically into the existing
  flat minibatch tensors without altering v1--v4 behavior.
- No v5 trajectory, optimizer update, checkpoint, or changed model state
  exists at this precommit.
