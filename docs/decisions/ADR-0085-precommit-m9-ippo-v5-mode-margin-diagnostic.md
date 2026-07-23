# ADR-0085: Precommit M9 IPPO v5 mode-margin diagnostic

**Status:** Accepted

## Context

ADR-0084 rejects v5 after its exact Replica A peaked at 1/40 deterministic
public-dev wins and ended at 0/40 despite 559 stochastic training wins and
27,614 success-imitation transitions. Blindly changing the imitation
coefficient or exposure count would be post-result retuning. The next decision
needs to distinguish stochastic success retained without deterministic
consolidation from erosion of the successful action distribution.

## Decision

1. Freeze the diagnostic protocol at
   `configs/evaluation/m9-ippo-v5-mode-margin-diagnostic-protocol.json`,
   SHA-256
   `9a9b44e36a22d68dcc37216db377ff29fcecf9ad6525e2d89bd6092a694dad0b`.
2. Bind only rejected v5 Replica A update 7 (the immutable 1/40 public
   frontier) and update 32 (the immutable 0/40 final checkpoint), including
   exact file, checkpoint-content, model-state, manifest, result, config, and
   protocol identities.
3. Use the same 40 public dev roots. For each checkpoint run one deterministic
   argmax stream and four categorical streams with action seeds `9602`,
   `19602`, `29602`, and `39602`.
4. Run the complete 400-episode matrix twice in fresh JVMs and require exact
   report identity. Model parameters, optimizer state, environment contract,
   roots, and action seeds cannot change.
5. For every actor-valid transition, recompute the authoritatively masked
   logits from the stored transition inputs and private hidden input. Report
   chosen-action probability and top-two legal-logit margin, grouped by mode,
   checkpoint, and authoritative terminal outcome. These measurements are
   descriptive and cannot select a checkpoint or affect classification.
6. Classify with integer win counts only:
   - `stochastic_success_retained_without_deterministic_consolidation` when
     both argmax results are at most 1/40, update 32 has at least 16/160
     categorical wins, and retains at least 80% of update 7's categorical
     wins;
   - `success_distribution_eroded` when update 7 has at least 16/160
     categorical wins and update 32 has at most 50% of update 7's categorical
     wins;
   - otherwise `inconclusive`.
7. A retained-without-consolidation result may recommend precommitting one
   deterministic-margin alignment mechanism. An erosion result may recommend
   precommitting one optimizer or auxiliary-loss stabilization mechanism. An
   inconclusive result authorizes no new training recipe.
8. The diagnostic cannot train, repair, select, promote, access confirmation
   data, or access held-out data. V5 remains rejected under every result.

## Alternatives

- Immediately lower the `0.02` coefficient or apply imitation fewer times is
  rejected because v5 supplied no evidence that either coordinate is causal.
- Reuse v4 update 31 as a training start is rejected because v4 is rejected
  and that would add checkpoint selection and lineage changes.
- Use action-mode margin as the classification threshold is rejected because
  no prospective scale calibration exists; it is recorded only as descriptive
  evidence.
- Open any new seed set is rejected because the public dev roots are sufficient
  for this non-promotional diagnostic.

## Consequences

- Implementation must fail closed on every source identity and authority bit.
- No v5 checkpoint may be loaded for diagnostic execution until this ADR and
  protocol are committed.
- M8 held-out-v7 remains sealed and no M9 confirmation/held-out namespace is
  authorized.
