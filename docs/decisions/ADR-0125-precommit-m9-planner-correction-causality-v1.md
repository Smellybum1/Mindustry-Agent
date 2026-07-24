# ADR-0125: Precommit M9 planner-correction causality v1

**Status:** Accepted

## Context

The rejected student-state relabel update-64 checkpoint and rejected
hard-example relabel update-96 checkpoint each win 13/40 public-dev episodes.
The update-64 student disagrees with planner v11 on only 89/3,200 eligible
same-state labels, and ADR-0122 showed that all 39 same-family disagreement
pairs have distinct governed candidate features. ADR-0124 then showed that
raising normalized teacher-NLL pressure on observed student/planner
disagreements did not construct a passing student: its best checkpoint reached
17/40 and final update 96 returned to 13/40.

That null result rejects the fixed `4.0` scalar learning-pressure intervention.
It does not establish whether the planner/student disagreements themselves are
causally important in closed loop. Raw disagreement counts by terminal outcome
cannot answer that question because episode duration and the visited-state
distribution differ. A public-only, paired intervention is cheaper and more
informative than another training recipe.

## Decision

Freeze `m9-planner-correction-causality-v1` before implementation. It is a
diagnostic only. It loads the exact rejected update-64 and update-96 models
without loading, changing, or stepping their optimizers. It runs the same 40
public-dev roots in three fixed modes:

1. `baseline`: deterministic student argmax controls every boundary.
2. `correct_first`: at the first atomic boundary containing any eligible
   student/planner disagreement, execute planner v11's complete canonical
   actor-authoritative bundle once, then return control to the student.
3. `correct_all`: at every such boundary, execute that complete planner bundle.

A correction is atomic across actor-authoritative, non-forced seats. It is not
a per-seat hybrid and does not replace server-forced controls. In every mode,
the student's GRU hidden state advances from its own inference, while accepted
selection history records the bundle that actually executed. This rule also
applies when the planner bundle executes. The intervention therefore measures
the closed-loop effect of this online planner-correction rule; it does not
claim to replay the baseline disagreement sequence after trajectories diverge.

The protocol records paired root outcomes and exposure-normalized disagreement,
switching, retargeting, and commitment measures. Semantic commitments begin or
change only on accepted actor-authoritative `SELECT`/`WAIT` actions;
`CONTINUE` preserves the prior identity. Durations end at the next identity
change or terminal. It also records the fixed last 600 ticks before terminal,
legal-logit margins, and every substituted atomic bundle with pre/post state
hashes. `correct_first` is descriptive only.

The diagnostic is valid only if each checkpoint baseline reproduces its frozen
13/40 win count and mean core health exactly, twin fresh-JVM reports match
root by root, terminal reset matches, and every bound source/config/checkpoint/
seed hash passes. The historical construction summaries did not retain
per-root outcomes, so no unavailable per-root source record is invented. Given
a valid result:

- `strong_correction_signal` requires both `correct_all` cells to reach at
  least 28/40 wins;
- `low_correction_signal` requires both `correct_all` cells to reach at most
  21/40 wins;
- every other result is `mixed_correction_signal`.

These thresholds are prospective and exact. No takeover grid, first-K sweep,
post-result checkpoint choice, or approximate significance rule is authorized.
The paired McNemar exact-binomial statistic is reported descriptively and does
not replace the frozen classification.

The full protocol is
`configs/evaluation/m9-planner-correction-causality-v1-protocol.json`; its
SHA-256 is
`aee96892e4ceb131da7743afabc2d41fbb08be41e53b9b79c22158af3530cad6`.

## Constraints

- Public-dev only. No confirmation, held-out, learned human-session, or other
  restricted data access is authorized. M8 held-out-v7 remains sealed.
- The two rejected checkpoints remain unselected, unrepaired, and
  unpromotable. Update 94 is excluded from the primary question because it was
  selected descriptively after the failed hard-example run.
- Planner v11, candidates, governed features, masks, deterministic inference,
  roots, scenario, and action validity are unchanged.
- No training, model or optimizer mutation, reward, PPO, MAPPO, target ID,
  planner change, correction-weight sweep, or checkpoint repair is authorized.
- Implementation, focused tests, exact-current-commit public preflight, and
  twin-JVM/reset evidence must precede classification.
- A valid result may authorize only drafting a separately named prospective
  successor ADR. It does not itself authorize model work or promotion.

## Consequences

Implementation may add one fail-closed public diagnostic runner, command,
tests, and result schema. A failed baseline/hash/determinism gate makes the
diagnostic invalid and stops interpretation. A valid result will distinguish
large, small, or checkpoint-dependent benefit from online planner correction
without spending another construction budget or opening sealed data.
