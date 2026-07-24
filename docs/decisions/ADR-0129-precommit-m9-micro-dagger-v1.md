# ADR-0129: Precommit M9 micro-DAgger v1

**Status:** Accepted

## Context

Candidate-native teacher-forced distillation, student-state relabeling,
disagreement weighting, planner correction, and truncated sequence relabeling
have all failed the frozen 30/40 public construction floor. ADR-0128 stops
automatic model work after sequence relabel v1. The owner has now explicitly
authorized a new prospective public plan and its execution.

One pure-imitation mechanism remains isolated and untested: label freshness
inside an optimizer update. The prior student-state relabel run collected 64
student-controlled episodes once, then optimized those fixed states for eight
epochs. After the first epoch, later epochs trained on states collected by an
older model. This is distinct from teacher-vs-student disagreement pressure
and from recurrent backpropagation.

## Decision

Freeze `m9-candidate-native-micro-dagger-v1` before implementation or model
work. It starts from the exact rejected teacher-forced update-32 model and Adam
state without selecting, repairing, or promoting that checkpoint. This is the
same initialization used by the on-policy relabel v1 comparison.

The unique public-root schedule remains exactly 2,048 roots partitioned into
32 macro updates of 64 roots. Each macro update contains eight deterministic
micro updates. Before every micro update, the current post-previous-micro model
re-runs all 64 macro roots under deterministic student control and planner v11
labels the same pre-action student-visited actor-valid boundaries. The freshly
collected dataset receives exactly one shuffled epoch of the unchanged
detached one-boundary teacher-action NLL, then is discarded. The next micro
update recollects those roots using the newly updated model.

Thus every unique root is recollected eight times within its macro update,
for 16,384 public collection episodes. Every collected example is presented
once, preserving eight optimizer epochs per macro update while making every
epoch maximally fresh. The existing seed-9613 generator is continuous across
all micro updates. No cross-micro replay is permitted.

Dev evaluation and checkpointing remain macro-level only: the same 40 public
dev roots run after each group of eight micro updates, producing lineage
updates 33 through 64. The 30/40 construction floor, idle threshold, ranking,
and replica policy are unchanged.

Everything except collection/optimizer interleaving is inherited exactly:
planner, candidates, features, masks, deterministic student actions, teacher
label filter, model, source model/optimizer state, Adam values, learning rate,
minibatch size, gradient clipping, unique roots, dev roots, and selection
gate. No example weighting, margin, sequence backpropagation, EMA, replay,
reward, critic, entropy, PPO, or MAPPO is introduced.

Configuration/public-protocol SHA-256 values are
`127c7290b6c3c9435933542968f309ec5b62db3463fd4c2e3500d608cc863374` /
`50a754dde6f3effdb95485aaba5c59dddacbb53aec48895835c7def3c9eec15e`.

Replica A may start only after implementation and focused tests are committed,
a single micro update is checkpoint-exact with the existing flat NLL,
configured eight-micro optimizer replicas match, live post-update collection
uses the current model and repeats after terminal reset, and the complete
public-only exact-current-commit preflight passes. Replica B is authorized only
if Replica A reaches at least 30/40 wins and the idle threshold; failure
prohibits Replica B.

## Constraints

- The source checkpoint/result/manifest/config hashes, public seed hashes,
  unique-root schedule, model, optimizer values/state, planner, labels, dev
  protocol, gate, and replica rules are frozen and fail closed.
- Only collect/optimize cadence changes. The increased collection count is
  explicit and cannot be interpreted as permission to add roots or replay.
- The source and every failed M9 checkpoint remain rejected, unselected,
  unrepaired, and unpromotable.
- No confirmation, held-out, learned human-session, or other restricted data
  access is authorized. M8 held-out-v7 remains sealed.
- A valid failure exhausts maximal within-update freshness for this pure-CE
  candidate lineage; it does not authorize a schedule sweep.

## Consequences

Implementation may add one fail-closed micro-DAgger collector/optimizer runner,
preflight, commands, tests, and public result. No candidate trajectory,
optimizer update, changed model state, or restricted access preceded this
precommit. Replica A failure must be recorded honestly and stops Replica B.
