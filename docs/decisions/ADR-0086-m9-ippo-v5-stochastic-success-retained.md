# ADR-0086: Accept retained stochastic success in rejected M9 IPPO v5

**Status:** Accepted

## Context

ADR-0085 prospectively froze an immutable-checkpoint, public-only diagnostic
after v5 failed construction. Implementation commit
`e0efa3ac70f8f66d12c4e7dd72d21229a509683d` passed all 434 Python tests before
execution. Two fresh JVMs then produced byte-identical 400-episode reports for
rejected v5 updates 7 and 32.

Update 7 replayed its immutable 1/40 deterministic result and won 51/160
categorical episodes. Update 32 replayed 0/40 deterministic but won 62/160
categorical episodes, 121.57% of update 7. Update 32's categorical wins had
mean chosen-action probability `0.42454807985024373` and mean top-two legal
logit margin `1.5374214747694672`; the model distribution remained capable of
successful trajectories even though its deterministic action sequence failed.

The exact twin run digest is
`1cfd3679cbebaaae8e11d99c1b202c3f47614805f2ad4a48d62cb4b3d40f137c`.
The full report SHA-256 is
`bf85941900cf609a7876b9b322ee02f252968c8c02c3a6f50a6c64ecfc4f1150`.
The compact result is
`configs/evaluation/m9-ippo-v5-mode-margin-diagnostic-result.json`, SHA-256
`0c0cbe21a53bf7d63f2f3099c81d98cf566095313c783bf5acd12cffc6874ce3`.

## Decision

1. Accept ADR-0085's frozen classification:
   `stochastic_success_retained_without_deterministic_consolidation`.
2. Keep v5 rejected. The diagnostic does not select update 7 or update 32,
   authorize Replica B, or change the authoritative deterministic construction
   policy.
3. Reject `success_distribution_eroded` at this boundary: update 32 categorical
   wins increased from 51 to 62 instead of falling to at most 50%.
4. Authorize only a separate precommit for one deterministic-margin alignment
   mechanism. It must target the sampled action from current-update winning
   actor transitions relative to the strongest other legal action, without
   changing rollout data, roots, rewards, entropy schedule, recurrence,
   architecture, RNGs, public evaluation, or restricted-data authority.
5. The action-mode measurements are descriptive. Their numeric values cannot
   select a checkpoint, tune a coefficient after implementation, or become a
   promotion threshold.
6. No v6 implementation or training may begin before its full immutable recipe
   and public protocol are committed.

## Alternatives

- An optimizer-collapse stabilizer is rejected as the next direction because
  update 32 retained and improved categorical wins under the frozen test.
- Another probability NLL coefficient is rejected because v5 directly tested
  that family and failed deterministic construction.
- Switching official evaluation to categorical is rejected because the frozen
  construction contract requires deterministic argmax behavior.
- Selecting v5 update 32 for stochastic deployment is rejected because v5
  failed construction and this diagnostic has no selection authority.

## Consequences

- The next candidate, if precommitted, should use a direct strongest-alternative
  margin objective rather than another chosen-action probability objective.
- V5 checkpoints remain immutable diagnostic sources only.
- No confirmation or held-out data was accessed; M8 held-out-v7 remains sealed.
