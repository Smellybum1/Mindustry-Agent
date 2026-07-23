# ADR-0070: Freeze the first M9 IPPO optimization and public comparison

**Status:** Accepted

## Context

ADR-0069 authorizes M9 on fresh public governance without relabeling M8 as
promoted. The all-seat runtime boundary now proves one parameter set, explicit
role context, private recurrent state, deterministic agent-id evaluation, one
atomic action bundle, terminal-reset independence, and direct/traversed
real-JVM parity. No M9 optimization or training episode has run.

The next irreversible decision is the first IPPO construction. Its reward,
optimizer, budget, RNG streams, checkpoint choice, and public comparison must
be fixed before implementation results can influence them. The existing
all-seat teacher-controlled parity trace loses its five diagnostic episodes;
it is therefore a boundary oracle, not justified training supervision. The
fixed-role server expert remains the public construction baseline.

## Decision

1. The immutable first recipe is `m9-ippo-v1`, stored in
   `configs/training/m9-ippo-v1.json`, SHA-256
   `5d349b4a93f1334292d09a4f4af6acd4764328836e6d6dbab309443e318c9861`.
   The public comparison is
   `configs/evaluation/m9-ippo-v1-public-protocol.json`, SHA-256
   `1f53ad0dde01a5433f609e8e0772d4576f6e5b600f0efb456242ee7333c6f554`.
2. One `ippo_shared_recurrent_selector_v1` parameter set supplies all three
   actors and local critics. The implemented architecture, ordinary ten-action
   vocabulary, role embedding, private 64-value seat state, death/reset
   clearing, deterministic `0,1,2` evaluation order, and one-boundary
   recurrent truncation remain exact.
3. Training uses 32 cycles of 64 episodes (2,048 total), Adam at `0.0001` and
   epsilon `1e-8`, per-second discount `0.99`, GAE `0.95`, PPO clip `0.2`,
   eight epochs, minibatches of 256, entropy coefficient `0.02`, value
   coefficient `0.5`, and maximum gradient norm `0.5`. Torch has one CPU
   thread. Model, action-sampling, shuffle, and minibatch RNG streams use
   seeds 9601 through 9604 respectively.
4. The existing `selector_reward_v2` team reward is shared identically among
   seats with the exact quality coefficients and caps in the recipe. The sole
   individual component is
   `reward.agent.own_available_idle_ticks`: `-0.00025` per monotonic increase
   in the owning seat's authoritative available-idle counter, capped at
   `-1.0` per seat. Its complete audit row is precommitted in
   `docs/REWARD_AUDIT.md`; it may not influence training until all six named
   adversaries pass.
5. No teacher or behavior-cloning term is authorized. The architecture parity
   oracle remains diagnostic-only.
6. Checkpoints are eligible only at 30 or more wins on the 40-root public dev
   set and mean team idle fraction strictly below `0.25`. Eligible checkpoints
   rank by wins, team return, core health, team idle, then earliest update.
7. Before replica A, the server `shared-expert-v1`
   (`agentcore.coordination.ExpertCoordinationDriver`) baseline must be
   evaluated on and frozen for the same public dev document. Candidate/baseline
   comparisons use paired 20,000-iteration bootstrap intervals with seed 9701.
8. The reward accumulator, PPO optimizer/rollout boundary, manifest lineage,
   exact replay, failure paths, and all adversaries must be implemented and
   pass the full pretraining gate in a committed boundary before any training
   episode. Replica A and B then use the exact same recipe independently and
   must reproduce checkpoint and direct replay evidence.
9. IPPO must first pass the construction threshold and produce exact replicas.
   MAPPO implementation is authorized only if the public paired interval lower
   bounds for win-rate and team return are respectively at least zero and
   strictly positive, the team-idle interval upper bound is at most zero, and
   direct checkpoint lineage is exact.
10. The only authorized data are the frozen M9 public train v1 and dev v1
    documents. Confirmation/final namespaces do not exist. Held-out access is
    prohibited. M8 held-out-v7 remains sealed and M8-only.

## Alternatives

- Training before the immutable recipe is rejected because observed outcomes
  could influence reward, optimizer, or sample budget.
- Imitating the teacher-controlled parity path is rejected because its observed
  public diagnostic performance does not justify supervision.
- Starting with MAPPO is rejected because IPPO must establish the all-seat
  actor and public improvement boundary before privileged training-only state
  is considered.
- Reusing an M8 held-out or retired set is rejected; M9 final governance must
  be newly precommitted if public construction succeeds.
- Increasing the budget or changing coefficients after replica A is rejected;
  any successor requires a new prospective ADR and candidate identity.

## Consequences

- The next work is implementation and adversarial verification, not training.
- CPU-only local processes may run schema validation, reward adversaries,
  baseline evaluation, exact replicas, hashes, and replay checks, while the
  existing one-environment-per-JVM and process caps remain binding.
- A public failure is informative but cannot be repaired in place. `m9-ippo-v1`
  remains immutable and any justified successor is separately governed.
- M8's rejection and sealed evidence state are unchanged.

## Reversal conditions

Supersede this ADR only prospectively, before the replacement candidate runs,
with a new exact recipe, data namespace, exploit audit, and comparison
protocol. Do not mutate or rerun `m9-ippo-v1` after observing its public result.

## Implementation and baseline evidence

The reward/rollout/optimizer boundary was committed at `dea79c487a` before any
training episode. From that exact commit and runnable JAR
`fdbd1d5482b556137...`, the fixed server expert was evaluated on all 40 public
dev-v1 roots and repeated the first episode exactly after terminal reset. It
wins 36/40, with mean team return `-1.641725`, mean core health `967.95`, and
mean authoritative task-board idle fraction `1.0`. The legacy expert drives
skills outside task-board assignment accounting, so its survival is strong but
its idle ledger is intentionally not repaired post hoc. The immutable evidence
SHA-256 is `ba4c9182f346a6eefc8c904d3e7825ee23933aede535b7c516ec63800f6a2d70`.
No M9 training episode preceded this baseline freeze.
