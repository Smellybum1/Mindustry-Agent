# ADR-0042: V31 initial schematic prior

**Status:** Accepted

## Context

V30 restored the intended CE budget and recovered from V29's 4/10 collapse, but
21/32 checkpoints plateaued at 8/10. Reusable dev-v1 diagnosis of best-ranked
update 11 reproduces V24's losses on seeds 2004/2005. It disagrees with the
10/10 adaptive teacher on 135/452 unforced decisions with mean selected-minus-
teacher margin `1.37575208`.

The failure evidence is much narrower than that aggregate. Seed 2004 has only
six unforced decisions and two disagreements. At tick 0, every reusable seed
chooses `BUILD_LINE` while the teacher chooses `BUILD_SCHEMATIC`; the learned
margin ranges from `0.83764815` to `0.85484707`. This common first decision is
the only coordinate that can be changed without another corpus/strength sweep.

## Decision

1. V31 is the exact V30 construction plus one structured policy-logit prior:
   add `+1.0` to every valid `BUILD_SCHEMATIC` candidate at tick 0. The value is
   frozen before construction, exceeds the largest observed reusable margin by
   about `0.145`, and is not selected from a sweep.
2. The prior applies only at the exact externally stepped structured boundary.
   It does not force an action: sampling/argmax still operates over adjusted
   masked logits. A missing or masked matching candidate fails closed. All
   other ticks and task types receive exact zero adjustment.
3. The same bias tensor participates in rollout log probabilities, PPO log-
   probability recomputation, teacher warmup/rehearsal CE, reusable evaluation,
   confirmation, and final evaluation. This prevents an old/new-policy or
   training/evaluation mismatch. Bias-free historical configs retain their
   exact numerical path.
4. The applied tensor is archived in decision traces and their digest. Config
   validation rejects unsupported schemas, negative ticks, empty task types,
   non-finite values, and zero biases before environment work.
5. Runtime, reward, roots, model, optimizer values, RNG values, PPO budget,
   teacher corpus/filter/caps, online teacher coefficient, checkpoint selection,
   and every later policy boundary stay exact. Candidate ID, quality label,
   initial prior, and confirmation path are the only config differences.
6. Replica B starts only if replica A reaches at least 9/10 reusable
   construction wins with mean idle below 0.25. Passing replicas must reproduce
   all corpus/sample-schedule/checkpoint/frontier/model/replay/full-run evidence
   and direct lineage.
7. Retire V30's unopened dev-v26. Freeze dev-v27 at globally disjoint roots
   `271001..271160`; it remains unopened until exact replicas and both reusable
   permanent-greedy and matched-greedy scorecards pass. Held-out-v4 stays
   sealed.
8. Training may begin only after exact-config reward adversaries, the Python
   suite, pinned build, five-seed candidate gate, smoke, and determinism
   including negative replay pass from a committed packet.

## Alternatives

- More teacher coefficient, corpus size, or presentation changes were rejected:
  V24–V30 already isolate those lines without clearing the same failure pair.
- A forced scripted first action was rejected because it would bypass learned
  masked selection. The bounded prior preserves the policy decision surface.
- Biasing `BUILD_SCHEMATIC` globally was rejected because reusable evidence is
  specific to the first decision and later schematic-over-WAIT disagreements
  are common in winning episodes.
- Using the exact observed maximum plus epsilon was rejected as brittle. A
  single decimal `+1.0` is precommitted without a sweep and leaves a clear
  margin.

## Consequences

- V31 changes one decision boundary while retaining the complete from-scratch
  governed construction. Training trajectories may diverge after that first
  action, which is the intended causal test.
- The prior is deterministic, framework-local training policy state; it does
  not alter engine state, reward, masks, lifecycle, communication, or stepping.
- Construction failure retires dev-v27 unopened. Construction success still
  authorizes only exact reproduction and reusable preflight.

No V31 teacher collection or model work occurred before this precommit.

Pretraining validation passes all 44 exact-config reward adversaries, the full
156-test Python suite, the pinned build, five-seed candidate-policy gate, smoke,
and golden determinism including the negative replay. Config SHA-256 is
`861f34bd07db43a54aafb2b88ef725a0185c1aca685b533b32e99995ada1594b`;
adversary report SHA-256 is
`e7eb2f8826db46171fd5f4c8a08666b8138f4c04b66511f260a95546321412d9`.
