# ADR-0075: Precommit M9 IPPO v3 diverse-2048 training roots

**Status:** Accepted

## Context

ADR-0072 rejects v1 after exact replicas learned repeated public train roots
but peaked below construction and collapsed to zero public dev wins. ADR-0073
tested the only unexercised recurrent-credit mechanism. ADR-0074 rejects that
v2 test: sequence-16 backpropagation peaked at 11/40, trained less successfully
than v1, and did not resolve generalization.

Both candidates used the same 64 public train roots in every one of 32 cycles.
V1 won 598/2,048 repeated-root episodes while v2 won 513/2,048; neither
generalized. The strongest remaining public-only hypothesis is therefore the
training distribution itself, not recurrent credit. This decision must be
frozen before adapting the runner or collecting another trajectory.

## Decision

1. Freeze the successor as `m9-ippo-v3-diverse2048`, derived from immutable v1.
   Its config is `configs/training/m9-ippo-v3-diverse2048.json`, SHA-256
   `5d437c390fc54423ac1be1f27b47395e68bd42e5f85a74e8abd13275c5f9b458`.
   Its public protocol is
   `configs/evaluation/m9-ippo-v3-diverse2048-public-protocol.json`, SHA-256
   `29085f124d958f563965a682adb029bdff24bf3a03df2148dd19c41c36e2a82f`.
2. V3 changes exactly one training mechanism from v1: root diversity. The
   2,048-episode budget uses 2,048 unique public train roots, each exactly once,
   instead of repeating 64 roots in 32 cycles.
3. The frozen train document is
   `configs/evaluation/bootstrap-defense-v1-m9-train-diverse2048-v1.json`,
   SHA-256
   `2e4d5b853ba9c8a6b568b107537756e257d3c19205af71c0445ea5ea730088c4`.
   It contains the contiguous public train-only range
   `[18,000,100,001, 18,000,102,049)`, disjoint from v1 train roots and the
   public dev namespace. Its deterministic generator is committed with the
   packet.
4. The four existing RNG seeds remain exact. Seed 9603 performs one
   deterministic shuffle of the complete 2,048-root membership; the resulting
   permutation is sliced into 32 consecutive 64-episode updates. Every root
   must appear once and only once.
5. V1's model initialization, architecture, private runtime state, ordinary
   ten-action vocabulary, one-boundary recurrent optimizer, atomic all-seat
   action boundary, rewards, optimizer/PPO values, 32-update budget, public dev
   roots, server-expert baseline, checkpoint ranking, and 30/40 plus idle
   `<0.25` construction bar remain exact. V2 sequence optimization is not used.
6. Before any v3 trajectory or model update, implementation must be committed
   and prove:
   - exact train-document hash, count, range, uniqueness, and public namespace
     disjointness;
   - exact deterministic 2,048-root schedule identity, complete one-use
     coverage, and 32-by-64 slicing;
   - v1 one-boundary optimizer dispatch and unchanged reward/model/protocol
     contracts;
   - candidate-aware checkpoint, manifest, preflight, and training authority;
   - full Python and pinned Java suites, M9 reward/shared-policy/rollout/
     artifact checks, smoke, determinism, and golden replay.
7. Replica A runs the full immutable budget after the exact-commit gate. If A
   has no eligible checkpoint, v3 is rejected and replica B does not run. If A
   passes construction, replica B must reproduce the full run and selected
   checkpoint before paired public comparison.
8. MAPPO remains prohibited unless exact v3 replicas satisfy every frozen
   public paired gate. No M9 confirmation or held-out namespace exists. M8
   held-out-v7 remains sealed and unavailable.

## Alternatives

- Retuning v2 sequence length or optimizer values is rejected as post-result
  repair and does not address the repeated-root evidence.
- Combining diverse roots with sequence backpropagation is rejected because it
  would mix two learning changes and retain a mechanism already rejected by
  v2.
- Expanding the episode budget is rejected; v3 redistributes the exact existing
  2,048 episodes.
- Reusing public dev roots for training or opening restricted data is rejected.
- Starting MAPPO remains rejected by the accepted performance prerequisite.

## Consequences

- V3 is a bounded test of root diversity, not a budget increase or optimizer
  retune.
- The runner must support candidate-specific train membership cardinality
  without weakening v1/v2 hash validation or immutable evidence.
- Each training update sees new roots, so per-root learning curves are not
  comparable to v1 repetition; the fixed public dev frontier remains the
  construction decision.
- No v3 trajectory, optimizer update, checkpoint, or changed model state exists
  at this precommit.
