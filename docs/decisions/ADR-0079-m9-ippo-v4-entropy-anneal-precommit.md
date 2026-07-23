# ADR-0079: Precommit M9 IPPO v4 entropy annealing

**Status:** Accepted

## Context

ADR-0078 accepts ADR-0077's predeclared policy-mode signal. Immutable rejected
v3 update 29 reproduced 0/40 with deterministic argmax but won 56/160 with
four fixed categorical streams, with every stream contributing 11--17 wins.
The model did not change and two fresh JVM runs reproduced exactly. This shows
that the policy distribution contains transferable successful behavior while
its deterministic mode fails to consolidate it.

V3 already rejected repeated-root exposure as the sole explanation by using
2,048 unique public roots. V2 rejected longer recurrent backpropagation. The
next candidate must therefore isolate one mechanism aimed at reducing the
stochastic/deterministic policy-mode gap without changing data, model,
recurrent credit, reward, budget, or official evaluation.

## Decision

1. Freeze the successor as `m9-ippo-v4-entropy-anneal`, derived from immutable
   v3. Its config is
   `configs/training/m9-ippo-v4-entropy-anneal.json`, SHA-256
   `9b9495e03b11e0fdae744fefd64f65de513b85093cf96e2a088ac4235766d215`.
   Its public protocol is
   `configs/evaluation/m9-ippo-v4-entropy-anneal-public-protocol.json`,
   SHA-256
   `db9b5647f249d30889b911a075905a78f4ba9ccef5613bc25d09126e1d1e7ace`.
2. V4 changes exactly one learning mechanism from v3: the entropy coefficient.
   Replace the constant 0.02 incentive with an inclusive linear schedule from
   0.02 at optimizer update 1 to 0.0 at update 32:

   `coefficient(update) = 0.02 * (32 - update) / 31`

   for integer updates 1 through 32. Action collection remains categorical
   under the fixed sampling RNG. Official dev evaluation remains deterministic
   argmax.
3. V3's exact 2,048 unique public roots, one-use schedule, seed 9603 shuffle,
   32-by-64 budget, model initialization and architecture, one-boundary
   recurrent optimizer, other PPO values, rewards, four RNG seeds, public dev
   roots, shared-expert baseline, checkpoint ranking, and 30/40 plus idle
   `<0.25` construction bar remain exact.
4. No teacher, replay selection, successful-trajectory distillation, learning
   rate change, temperature change, root change, or budget increase is
   permitted. No reward component changes, so `docs/REWARD_AUDIT.md` remains
   unchanged.
5. Before any v4 trajectory or model update, implementation must be committed
   and prove:
   - exact config/protocol hashes and semantic equality with v3 outside the
     named identity and entropy-schedule fields;
   - exact coefficients at updates 1 and 32, strict monotonic non-increase, and
     the frozen formula at all 32 updates;
   - the scheduled coefficient is the value used by every PPO minibatch and is
     recorded in optimizer-update telemetry;
   - exact v3 root membership, one-use schedule, model/reward/RNG/dev/baseline
     inheritance;
   - candidate-aware checkpoint, manifest, preflight, runner, and failure
     paths;
   - deterministic twin synthetic updates plus the full Python and pinned Java
     suites, M9 focused checks, smoke, determinism, and golden replay.
6. Replica A runs the full immutable budget after an exact-current-commit gate.
   If A has no eligible checkpoint, v4 is rejected and replica B does not run.
   If A passes construction, replica B must reproduce the full run and selected
   checkpoint before paired public comparison.
7. MAPPO remains prohibited unless exact v4 replicas satisfy every frozen
   public paired gate. No M9 confirmation or held-out namespace exists. M8
   held-out-v7 remains sealed and unavailable.

## Alternatives

- Changing official evaluation to categorical sampling is rejected because it
  changes deployable behavior and the 56/160 diagnostic remains below the
  official construction floor.
- Setting entropy to zero from update 1 is rejected because it changes initial
  exploration and may collapse before broad one-use roots are observed.
- Distilling successful v3 trajectories is deferred because it introduces
  replay selection and a supervised objective.
- Expert behavior cloning is deferred because it introduces teacher data and
  a supervised objective.
- Retuning learning rate, clipping, recurrent length, root count, or budget is
  rejected because it does not isolate the observed policy-mode mechanism.

## Consequences

- V4 is a bounded deterministic-policy consolidation test, not a general PPO
  retune.
- Optimizer APIs and manifests must become update-aware without changing
  v1/v2/v3 behavior or hashes.
- No v4 trajectory, optimizer update, checkpoint, or changed model state exists
  at this precommit.
