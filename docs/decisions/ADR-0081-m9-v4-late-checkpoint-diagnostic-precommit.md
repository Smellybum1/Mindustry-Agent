# ADR-0081: Precommit the M9 v4 late-checkpoint diagnostic

**Status:** Accepted

## Context

ADR-0080 rejects `m9-ippo-v4-entropy-anneal` after public construction.
Immutable update 31 won 18/40 public-dev episodes with low idle, while the
zero-entropy update 32 immediately fell to 0/40. That transition could mean
either:

- the final optimizer update damaged survival behavior throughout the policy
  distribution; or
- sampled survival behavior remained present, but the deterministic mode moved
  to a failing action sequence.

Those cases support different bounded successors. The first points toward
optimizer-step stabilization. The second points toward a mechanism that makes
successful sampled behavior authoritative at the deterministic mode. Another
training recipe before separating them would mix hypotheses.

## Decision

1. Freeze the public-only protocol at
   `configs/evaluation/m9-ippo-v4-late-checkpoint-diagnostic-protocol.json`,
   SHA-256
   `d68fee034d3b90e720988639bb47b3e6df2961c7fabc46a0b9b161bab32b2dc1`.
2. The only source models are immutable rejected v4 updates 31 and 32. Their
   result, manifest, checkpoint-file, checkpoint-content, model-state, training
   commit, config, protocol, and rejected status must validate exactly before
   any episode starts.
3. Reuse only the 40 public M9 dev-v1 roots. For each checkpoint, run one
   deterministic argmax stream and four categorical streams with fixed action
   RNG seeds `9602`, `19602`, `29602`, and `39602`. Each stream covers all 40
   roots at temperature 1.0 under the authoritative action mask.
4. Run the complete 400-episode checkpoint/mode matrix twice in fresh JVMs.
   The two full reports, per-root traces, aggregates, checkpoint order, and
   model digests must match exactly. Models and optimizer state must not
   mutate.
5. The deterministic streams must exactly reproduce the immutable manifest:
   update 31 at 18/40 and update 32 at 0/40. Any mismatch fails the diagnostic.
6. Classify one of three outcomes using only prospectively frozen arithmetic:
   - **mode instability** when the argmax drop is at least 10 wins, update 32
     retains at least 32/160 categorical wins, and its categorical wins are at
     least 80% of update 31's;
   - **optimizer distribution collapse** when the argmax drop is at least 10,
     update 31 has at least 32/160 categorical wins, and update 32 retains at
     most 50% of them;
   - **inconclusive** otherwise.
7. The diagnostic cannot select, repair, train, or promote either checkpoint.
   It cannot authorize v4 Replica B, MAPPO, confirmation, or held-out access.
   A result may recommend one separately named, separately precommitted v5
   learning mechanism only.
8. No confirmation or M9 held-out namespace may be allocated. M8 held-out-v7
   remains sealed and unavailable.

## Alternatives

- Selecting update 31 is rejected because it missed the frozen construction
  floor and v4 is immutable.
- Comparing only the two argmax results is rejected because those outcomes are
  already known and cannot distinguish distribution damage from mode movement.
- Inspecting confirmation or held-out roots is rejected because the public
  failure supplies the diagnostic question and restricted evidence has no
  role in candidate design.
- Training both an optimizer-stabilized and a mode-consolidating successor is
  rejected because it spends two candidate budgets without first using the
  immutable public evidence to separate the hypotheses.

## Consequences

- No new model, optimizer update, checkpoint, or training trajectory is
  authorized by this ADR.
- The diagnostic requires fail-closed multi-checkpoint source validation,
  fixed-mode execution, exact fresh-JVM comparison, and compact public result
  evidence.
- V5 remains undefined until the diagnostic result is accepted in a separate
  ADR.
