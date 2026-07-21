# ADR-0018: V9 final WAIT-bias step and enlarged confirmation

**Status:** Accepted

## Context

Train/dev evidence shows a monotone governance result: V7's idle interval was
uncertain, while V8's first `-0.25` WAIT-logit adjustment made all dev-v4
scorecards pass at 37/40 wins. V8 was not promoted by held-out-v2, which is now
consumed. ADR-0017 has frozen held-out-v3 before new model work.

## Decision

1. V9 is a deterministic child of V8 and applies one additional `-0.25` delta
   to `special_head.2.bias[1]`. Relative to V7, the total WAIT-bias adjustment
   is therefore `-0.50`. No other tensor or behavior changes.
2. This is the final WAIT-bias step, not a sweep. Its direction and magnitude
   are selected once from V7/V8 train/dev aggregate evidence before V9
   construction. No held-out-v2 individual outcome or trace is used.
3. Legal-action masks remain authoritative; only multi-action choices change.
4. Two independent V8-parent constructions must match checkpoint bytes,
   model-state digest, and lineage digest.
5. V9's immutable config names `bootstrap-defense-v1-held-out-v3` version 3.
6. Freeze `bootstrap-defense-v1-dev-v5` now with 80 unique roots
   `51001..51080`, globally disjoint from every prior split. The larger set is a
   one-way V9 confirmation after dev-v1 observed win qualification.
7. A started dev-v5 attempt consumes the set. Failure or abort rejects V9 and
   its individual outcomes cannot tune a successor.
8. Only a fully eligible dev-v5 result authorizes the one-way held-out-v3 final
   under ADR-0017.

## Consequences

- V9 directly continues the only train/dev intervention that made every
  confirmation scorecard pass.
- Eighty confirmation roots reduce the chance that a favorable 40-root result
  is treated as robust without enough paired evidence.
- Dev-v2 through dev-v4 and held-out-v1/v2 remain permanently consumed.

