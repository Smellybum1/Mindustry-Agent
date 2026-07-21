# M8 design — one learned task-selector seat

**Status:** M8.1 design accepted; M8.4 verified; M8.5 one-way final completed
without promotion 2026-07-21.
**Feature schema:** `selector_features_v1`. **Reward schema:** `selector_reward_v1`.

## Scope and success condition

M8 replaces only agent 0's idle-task utility choice. Agents 1 and 2 remain the
M7.4 adaptive scripted policy, and deterministic lifecycle/safety rules remain
scripted for every seat. Low-level skills, candidate generation, masks, board
claims, reservations, conflict resolution, and event-driven stepping are
unchanged. There is no raw movement, coordinate, block, message, or help action
in the learned surface.

Promotion requires all of the following after the policy, code, checkpoint, and
manifest are frozen:

1. held-out win-rate 95% CI is strictly above the permanent random-valid and
   greedy-utility upper bounds under ADR-0012;
2. the learned mixed team also beats a matched mixed-team ablation in which
   agent 0 uses pure greedy selection and agents 1/2 are otherwise identical;
3. every teammate-scorecard 95% CI is non-regressing versus greedy-utility in
   the metric's good direction (lower idle/duplicates/help latency/
   announcements-per-transition/abandonment/recovery time); a metric with no
   held-out coverage is reported `not observed` and is neither passed nor
   failed; the corresponding dev adversarial fixture must still pass;
4. all reward adversaries in `docs/REWARD_AUDIT.md` pass with archived traces.

Train seeds are used for optimization. Dev seeds may select checkpoints and
hyperparameters. Held-out seeds are a one-way final gate and are never used for
normalization, early stopping, reward revision, or feature revision.

## Controller boundary and single-seat semantics

The team controller assembles one atomic `agent_actions[]` bundle at each M7.4
decision boundary. Agent 0's model can emit only:

| Index | Protocol action | Mask rule |
|---:|---|---|
| 0–7 | `SELECT_CANDIDATE_TASK[k]` | candidate row exists, is not `WAIT`, and `action_masks[0].candidate_task[k]` is true |
| 8 | `CONTINUE_CURRENT_TASK` | `action_masks[0].continue_current_task` |
| 9 | `WAIT` | `action_masks[0].wait` |

The existing candidate catalog includes a `WAIT` row. That row is encoded but
its SELECT logit is masked; action 9 is the single canonical wait action. The
adapter submits the chosen typed action through the ordinary protocol. It gets
no direct board mutation, skill call, target id, resource grant, or priority
override. Same-tick claims still resolve in the server's atomic total order.

M8 is a selector, not a learned lifecycle controller. Existing deterministic
rules force `ABANDON` for bounded recoverable BLOCKED replans, wave preemption,
and readiness rebalance. Forced actions are recorded in the trajectory but have
`policy_loss_mask=0`; the reward interval still accrues. A boundary with only
one legal action is treated the same way. After a forced abandon,
the next observation is an ordinary model decision. Agent death, termination,
or a mask with no legal action resolves to protocol `WAIT` and is likewise
excluded from PPO loss.

The policy applies its 10-way mask before sampling. If a raw implementation bug
still chooses a masked action, the adapter records `invalid_action`, applies the
audited penalty, and submits `WAIT`. It never retries an alternate action,
crashes the episode, or silently clips to a valid candidate.

## Observation tensors

The framework-neutral adapter first produces Python lists/numbers. Tensor
conversion belongs only in `mindustry_agents.training` after ADR-0011. No raw
task id, engine entity id, prose announcement, absolute machine path, held-out
statistic, or final hand-tuned `utility` total enters the model.

### Candidate table: `float32[8, 37]`

Rows preserve the authoritative boundary order and zero-pad to eight. The
separate `candidate_present[8]` marks real rows. Each row is:

- 13 `UtilityFeatures`, in this pinned order:
  `team_value`, `urgency`, `capability_fit`, `role_fit`, `proximity`,
  `help_synergy`, `human_priority`, `travel_cost`, `resource_cost`,
  `duplication_risk`, `switching_cost`, `danger`, `uncertainty`;
- 16-way `TaskType` one-hot in Java enum order from `HARVEST_RESOURCE` through
  `REQUEST_HELP`;
- 8 task/board values: clipped priority, estimated ticks / scenario tick cap,
  estimated copper / declared scenario copper budget, helpers requested / 3,
  dependency count / 4, exclusive bit, semantic task already active bit, and
  semantic task owned by another seat bit.

Every numeric term is finite and clipped to `[0,1]`. M8.4 exposes the raw
13-term feature breakdown and the two semantic-board bits at the same immutable
observation boundary that produced the candidate; Python must not reconstruct
them from prose or unstable ids. WAIT has a normal task-type row and zero-valued
work context.

### Scalar context: `float32[56]`

The first 10 self features are health fraction, dead bit, normalized x/y,
cargo fraction, build-queue depth / 8, build-plan progress, skill progress,
active-task bit, and BLOCKED bit.

The next 16 team/scenario features are core copper / declared scenario budget,
core-health fraction, measured inflow / target inflow, time-to-next-wave /
maximum wave spacing, wave ordinal / wave count, enemy count / 10, enemy total
health / 5000, nearest-enemy distance / map diagonal, line-operational bit,
and the four defense coverage/readiness fractions, broken blocks / 32, alive
agent fraction, and remaining-tick fraction.

The next 6 board aggregates are OPEN, RUNNING, and BLOCKED task counts / 32,
self-owned-task bit, resource-reservation count / 32, and tile-reservation
count / 32. The next 16 values are the previous selected task type one-hot
(all zero at reset), followed by ticks since that selection / scenario tick
cap. The final 7 values are a multi-hot boundary reason vector in this order:
`task_terminal`, `task_blocked`, `economy_operational`, `task_expired`,
`wave_spawn`, `wave_clear`, `core_damage`.

All normalizers come from scenario metadata or fixed protocol bounds and are
versioned with the feature schema. No running mean/variance is fit on dev or
held-out data.

### Masks and trajectory fields

- `candidate_present`: `bool[8]`;
- `action_mask`: `bool[10]`, using the table above;
- `policy_loss_mask`: scalar bool (false for forced lifecycle/safety actions);
- `advanced_ticks`: exact ticks represented by the transition;
- `terminated`, `truncated`, chosen action, raw/masked logits, log-probability,
  value prediction, per-component reward, boundary reasons, and state hash.

Schema construction must fail loudly on unknown task types, non-finite values,
wrong row counts, or an all-false live/controllable action mask.

## Model v1

The first model is feed-forward. A shared candidate encoder maps 37→64→64.
A scalar encoder maps 56→64→64. Each SELECT logit comes from a 128→64→1 head
over one candidate embedding plus the scalar embedding. A separate scalar head
produces CONTINUE and WAIT logits. The critic consumes the scalar embedding plus
the masked mean candidate embedding through 128→64→1. Hidden activations are
Tanh; initialization and all RNG streams are manifest-pinned.

There is no GRU in M8. The previous-task one-hot, time-since-selection, current
skill/task state, and boundary reasons provide bounded recent context. Recurrent
state is reconsidered only if the feed-forward ablation cannot beat the matched
greedy seat without reward or feature leakage.

Training samples from the masked categorical distribution. Evaluation uses
argmax with the lowest action index as an exact tie-break. Checkpoint evaluation
must repeat the same action/state-hash trace in two fresh runs before promotion.

## Decision cadence and trajectory attribution

The collector calls `step(..., stop_on_decision_event=true)` with a requested
chunk ending at the scenario terminal cap. Task terminal/BLOCKED, economy ready,
wave spawn/clear, and core damage end the chunk early. There is no fixed polling
decision layered on top. Reward time terms use `advanced_ticks`, not the number
of calls or wall time.

An action owns the interval from its accepted boundary through the next model
or forced boundary. Same-tick claim losses remain ordinary typed action results.
The trajectory retains structured task/game events so reward and scorecard
derivations are replayable independently of the summed reward.

## Reward v1 implementation and hard gate

`selector_reward_v1` contains only:

- team milestone high-water rewards: working line `+1`, full defense readiness
  `+1`, and first clear of each of three scheduled waves `+2` (maximum `+8`);
- terminal outcome: win `+10`, loss or truncation `-10`;
- unresolved-objective time cost: `-0.0002` per engine tick until every
  milestone is reached, with loss/truncation charged through the scenario cap
  so early suicide cannot avoid it;
- invalid raw action `-0.25`, capped at `-1.0` per episode, then WAIT;
- learned-selection abandonment liability `-0.05`, capped at `-0.5`, excluding
  forced wave/readiness switches, death, lease-failure probes, human override,
  and termination cleanup.

Components are stored separately. Raw mining, delivery, building, repair,
damage, survival time, messages, offers, task count, and utility score have zero
reward. Discounting may value earlier real milestones, but high-water rewards
cannot repeat after damage/rebuild or task-id regeneration. The detailed audit
and adversarial cases live in `docs/REWARD_AUDIT.md`. The 27-case gate now runs
before either PPO run and all five rows are approved for M8.4. Promotion remains
separately gated by M8.5 and ADR-0012.

## Run and checkpoint manifest

Every training/evaluation artifact records:

- engine tag/commit, Arc hash, protocol/scenario/feature/reward versions;
- repository commit and dirty flag; Python version, exact RL lockfile hash, OS,
  WSL distribution, CPU/GPU, and deterministic-library settings;
- train/dev/held-out seed-set ids and versions, with the active split explicit;
- environment, model-init, action-sampling, shuffle, and minibatch RNG seeds;
- learned seat id, scripted teammate policy/version, lifecycle policy version,
  action cadence, normalizers, model architecture, optimizer/PPO parameters,
  rollout/update counts, and four-JVM cap;
- checkpoint SHA-256, parent checkpoint, source config SHA-256, reward-component
  totals, scorecard, episode outcomes, action/state-hash trace digest, and all
  produced artifact paths relative to the run directory.

A checkpoint is loadable only with an exact feature/reward/model schema match.
Evaluation mode disables sampling and optimizer state. The final held-out run
stores its exact JSONL/aggregate manifests and cannot be rerun to select another
checkpoint.

M8.4 writes a per-transition training JSONL, two complete fresh-checkpoint
replay traces, every update checkpoint, per-update dev selection evidence, and
a path-independent full-run digest. Two independent pinned WSL2 runs selected
update 3 with checkpoint SHA-256 `0b2bd8ac904a9e21...`, complete replay digest
`87ba273f376c47de...`, full-run reproducibility digest
`56cc7b54bc9b01b5...`, and dev action/state aggregate
`52aecddf4c96bab6...`.
The checkpoint won 0/10 dev episodes, so it is an implementation artifact, not
a promotion candidate. Held-out remained sealed.

## M8.5 final evidence

The first improvement pass fixes boundary-frequency-dependent GAE credit by
raising both `gamma_per_second` and `gae_lambda` to elapsed engine seconds. It
also makes repeated train-only cycles explicit in the run manifest and maps the
catalog WAIT candidate to the one canonical WAIT action. These changes alter no
reward component, environment state, inference action vocabulary, or scripted
lifecycle rule.

The frozen candidate uses two aligned model-seed-8601 parents. Base update 2
uses ordinary PPO and wins 8/10 dev; auxiliary update 2 adds coefficient 0.1
cross-entropy only over unforced decisions from successful on-policy train
episodes and wins 6/10. The term is training-only and does not alter reward or
evaluation. Two independent pinned runs reproduce each parent exactly.

The dev-only promotion preflight evaluates permanent random-valid and
greedy-utility aggregates plus matched seat-0 random and pure-greedy controls.
The matched controls preserve adaptive-v1 teammates, adaptive lifecycle, event
cadence, canonical WAIT, scenario, and seed set. Dev is a qualification screen:
the learned observed win rate must be strictly greater than every comparator,
all reward adversaries must pass, and paired scorecard intervals must be
non-regressing. The 95% CI-separation claim is made only by the one-way held-out
final described above.

The governed constructor averages the aligned states 75% base / 25% auxiliary.
Two independent constructions match checkpoint SHA-256
`4fdad5cbd8476a8f...`, model-state digest `266c4acc5504dcda...`, and
path-independent lineage digest `995cb7d71fa21e4e...`. Frozen dev preflight is
9/10 learned versus 3/10 permanent random, 8/10 permanent greedy, 2/10 matched
random, and 1/10 matched greedy, with reward and scorecard gates passing.

The final runner validates checkpoint/config/lineage/dev-preflight/source
hashes and frozen repository status, then creates an exclusive attempt file
before loading held-out membership. It ran exactly once. Held-out aggregates:

- learned selector: 4/10, 95% CI `[0.1,0.7]`;
- permanent random-valid: 6/10, `[0.3,0.9]`;
- permanent greedy-utility: 6/10, `[0.3,0.9]`;
- matched greedy seat: 1/10, `[0.0,0.3]`.

The learned interval does not clear either permanent upper bound. It beats the
matched greedy observed rate, but idle fraction and abandonment regress versus
permanent greedy and recovery is uncertain. The final decision is
`not_promoted`. Exact local artifact hashes are recorded in `docs/STATUS.md` and
the completed attempt marker forbids any rerun or outcome-driven policy tuning.

## Post-failure successor precommit

ADR-0013 freezes held-out-v2 before successor model work. The first successor
hypothesis changes only training-root diversity: `m8-selector-v3-diverse` uses
64 new train-only roots (`11001..11064`) for 8 cycles instead of 16 roots for
32 cycles. Both recipes therefore contain exactly 512 training episodes and
eight 64-episode optimizer updates. Model architecture, reward, PPO parameters,
RNG seeds, dev-v1 checkpoint selection, learned seat, scripted teammates, and
event cadence remain unchanged; successful-trajectory imitation is disabled.

The hypothesis is that broader train-root coverage reduces repeated-root
specialization without increasing the training or model capacity budget. It
was selected from train/dev methodology only, before running the recipe, and
its immutable config names `bootstrap-defense-v1-held-out-v2`. A successor that
does not pass the frozen dev preflight stops there and never opens v2.

Two independent pinned runs reproduced the recipe exactly but rejected the
hypothesis on dev. Both selected update 1 at 3/10 dev wins with checkpoint
`174c71d6b44819d4...`, checkpoint replay `9d156396fc6ee71a...`, and full-run
digest `e9e1ee37fbfef6ee...`. Later updates scored 1–3/10. The recipe therefore
stops before promotion preflight or any held-out-v2 access.

The second successor hypothesis, `m8-selector-v4-teacher-regularized`, keeps
the rejected v3 recipe and adds one training-only coefficient: 0.05
cross-entropy toward adaptive-v1's action at the same immutable boundary, only
for unforced transitions in successful on-policy episodes. The teacher action
is already produced for scripted lifecycle/teammate control, so this adds no
engine read or behavior to evaluation. PPO actions and audited rewards remain
authoritative; the earlier self-imitation coefficient stays zero. Teacher
actions, indices, loss, and sample counts are recorded for replay and optimizer
telemetry. The zero-default path preserves all older recipes.

This hypothesis addresses sparse successful diverse-root training evidence
(49/512 v3 train episodes) with a structured coordination prior, without
changing model capacity, roots, episode/update budget, RNGs, reward, dev set,
or evaluation. Its frozen config names held-out-v2 and must stop on dev failure.

Two pinned v4 runs reproduced exactly and selected update 5 at 5/10 dev wins:
checkpoint `da777520e27ee20c...`, replay `a455e5c0caf702ec...`, and full-run
digest `fc23c1ed82a546d3...`. This improves v3 but cannot strictly beat the 8/10
permanent-greedy dev aggregate, so v4 stops before preflight.

V5 is the final coefficient-only follow-up. It changes only the successful
teacher coefficient from 0.05 to 0.10 and precommits a strict continuation bar:
at least 9/10 dev wins, sufficient to exceed the existing 8/10 permanent-greedy
aggregate before the full scorecard preflight. A lower result ends this
teacher-regularization line. Its frozen config names held-out-v2.

Two pinned v5 runs reproduced exactly but selected update 8 at 3/10 dev wins:
checkpoint `6e488b4d2f21f0f6...`, replay `cdae4f433c493192...`, and full-run
digest `4d55b193cede563b...`. The teacher-strength line is therefore closed before
preflight and held-out-v2 remains unopened.

V6 is a precommitted data-budget hypothesis. It returns to the auxiliary-free
v3 recipe and changes only `training_cycles` from 8 to 32. Each of the 64
train-v2 roots is therefore visited 32 times, matching the per-root repetition
of the original train-v1 recipe while expanding the total budget to 2,048
episodes and 32 updates. The config names held-out-v2 and must reach at least
9/10 dev wins or stop before preflight.

Two pinned v6 runs reproduce exactly and select update 31 at 9/10 dev wins:
checkpoint `0dfdcf9b5273ae3f...`, replay `c3f6e5bb720ad95d...`, and full-run
digest `54476ef63e31e06d...`. This meets the precommitted continuation bar and
authorizes the full dev scorecard preflight, not held-out access.

Direct checkpoints now use `selector_checkpoint_direct_lineage_v1`. The
constructor requires two path-independent full-run manifests with identical
evidence, identical selected checkpoint bytes/model state/update/config, the
same training commit, and no unexpected dirt. Promotion accepts this schema or
the legacy interpolation schema through one validator. The lineage must be
constructed on the frozen evaluator commit before dev preflight.

The first full V6 dev-v1 preflight beats all four win-rate comparators, with
learned 9/10 versus permanent greedy 8/10 and matched greedy 1/10. Reward,
checkpoint, lineage, and repository gates pass. The scorecard means favor V6,
but idle, recovery, and abandonment intervals cross zero with only ten pairs,
so the result is not eligible for held-out.

ADR-0014 freezes a one-way 40-root dev-v2 confirmation set before execution.
It is disjoint from every governed split and is used only to resolve V6's
scorecard uncertainty, never to select or tune a checkpoint. The confirmation
runner creates an exclusive attempt marker and uses freshly matched permanent
baselines. Failure rejects V6; success is still only permission to invoke the
separate held-out-v2 final.

The exclusive dev-v2 attempt was created on commit `888095a664` but aborted
before artifacts were written: a forced matched-control lifecycle action chose
the catalog WAIT row, was represented as canonical index 9, and was indexed as
if it were a candidate row. ADR-0014 makes a started attempt consuming, so V6
is rejected and dev-v2 will not be rerun. Held-out-v2 remains unopened.

Matched controls now canonicalize every lifecycle/selector action before index
use and fail explicitly on a genuinely out-of-range SELECT. The regression is
covered without weakening the exclusive-attempt rule.

## V7 governed successor

ADR-0015 precommits V7 before construction as a 90/10 interpolation of aligned
V6 update 31 and V4 update 5 parents. V6 contributes its 9/10 dev capacity;
V4 contributes the successful-episode adaptive-teacher prior. Both parent runs
are independently reproducible and use only train/dev evidence. Cross-commit
construction records and validates each full training commit rather than
pretending historical runs came from the active construction commit.

Two A/B constructions must match exactly. V7 then faces dev-v1 before any new
confirmation. If it beats all observed comparators, the already frozen,
globally disjoint 40-root dev-v3 set is its single confirmation attempt. A
started attempt consumes dev-v3. Only an eligible confirmation can authorize
held-out-v2; dev-v2 remains consumed and V7 cannot use its outcomes.

## M8.1 acceptance review

- The learned surface is the existing typed board protocol and exactly one
  seat; deterministic skills and scripted teammates remain intact.
- Shapes, order, normalization, padding, masks, forced actions, cadence, model,
  reward draft, manifests, comparators, and promotion rule are explicit.
- No torch/trainer/lockfile implementation, held-out execution, reward emission,
  engine pin change, or spatial grid is part of M8.1.
- Known lane-anchor, idle/help coverage, abandonment, stable turret identity,
  and reset-precondition findings from M7 remain visible rather than encoded as
  privileged fixes.
