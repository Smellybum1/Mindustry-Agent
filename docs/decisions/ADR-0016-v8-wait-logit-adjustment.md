# ADR-0016: V8 WAIT-logit adjustment and one-way confirmation

**Status:** Accepted

## Context

V7 completed dev-v3 at 35/40 wins versus permanent greedy's 30/40 and passed
recovery, abandonment, announcements, and duplicate-work scorecards. Only idle
fraction remained uncertain: candidate-minus-matched-greedy mean `-0.0185`,
95% interval `[-0.0566, 0.0184]`. ADR-0015 therefore rejects V7 and consumes
dev-v3. Held-out-v2 remains unopened.

## Decision

1. V8 is a deterministic child of the frozen V7 checkpoint. It subtracts 0.25
   from coordinate 1 of `special_head.2.bias`, the WAIT logit. No other tensor,
   feature, reward, mask, lifecycle rule, or action changes.
2. The adjustment is chosen once from aggregate dev evidence before V8
   construction. Individual dev-v3 outcomes are not inspected or used.
3. Legal-action masks remain authoritative. If WAIT is the only legal action,
   masking still selects it; the adjustment only changes choices with multiple
   legal actions.
4. Two independent constructions from the identical V7 A/B artifacts must
   match checkpoint bytes, model-state digest, and lineage digest.
5. Freeze `bootstrap-defense-v1-dev-v4` now with 40 unique roots
   `41001..41040`, globally disjoint from every prior split.
6. V8 must beat every observed dev-v1 win comparator before one exclusive
   dev-v4 confirmation. A started attempt consumes dev-v4. Failure or abort
   rejects V8 and individual outcomes cannot tune a successor.
7. Only a fully eligible dev-v4 result may authorize held-out-v2 under
   ADR-0013. Dev-v2 and dev-v3 remain consumed.

## Consequences

- The policy change directly targets the only failed V7 aggregate gate without
  adding a reward component or changing deterministic environment behavior.
- The exact one-coordinate delta is auditable in checkpoint lineage.
- This is a single governed hypothesis, not a tunable logit-bias sweep.

