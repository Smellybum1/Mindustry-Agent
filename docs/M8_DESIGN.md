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

### Optional successful teacher-trajectory warmup

The trainer also supports a zero-default `teacher_trajectory_warmup_v1`
construction primitive for governed successor experiments. When enabled, it
runs a separately shuffled number of complete train-split cycles with
adaptive-v1 controlling the learned seat at the same structured decision
boundaries. The model still evaluates every boundary, but its sampled action
cannot enter the environment during warmup. Forced lifecycle actions retain
their existing mask semantics.

Only unforced labeled transitions are eligible for cross-entropy. A governed
config may require `teacher_warmup_success_only`, in which case every losing
teacher episode is archived but contributes no gradient. Epochs, minibatch
size, seed-set order, and minibatch order are explicit config coordinates with
RNGs separate from ordinary action sampling and PPO minibatching. The warmup
uses the same Adam instance as the following PPO updates, so optimizer state
continuity is deterministic and intentional.

Warmup changes training initialization only: reward, features, masks, action
cadence, inference, dev evaluation, and held-out access are unchanged. Enabled
runs atomically write `selector-v1-teacher-warmup.json` before ordinary PPO,
including the exact config and train set, seed schedule, episode summaries,
optimizer metrics, and pre/post model-state hashes. That report is part of the
full-run reproducibility digest. With `teacher_warmup_cycles` absent or zero,
the trainer does not require warmup fields and preserves the historical
rollout/manifest shape.

An independently seeded, zero-default rehearsal mode may reuse that governed
eligible corpus after each ordinary PPO update. Rehearsal performs a configured
number of CE-only epochs before the checkpoint is saved and evaluated; it does
not recollect episodes, expand the train split, or consume ordinary PPO RNGs.
It continues through the same Adam instance, making the optimizer ordering
`PPO -> rehearsal -> checkpoint` explicit. Enabled runs atomically refresh
`selector-v1-teacher-rehearsal.json` after every update with the exact warmup-
report hash, compact corpus, per-update loss/sample metrics, and current model
digest. The rehearsal report joins full-run reproducibility evidence and
survives a later construction-gate failure. Absent or zero rehearsal epochs
preserve the warmup-only and historical trainer paths exactly.

The warmup corpus may also name an explicit `teacher_warmup_seed_set`. That
artifact must be a governed `train` split; dev and held-out files are rejected
through the same loader used by ordinary PPO. It changes only teacher-controlled
episode collection: PPO continues to use `train_seed_set`, and evaluation
continues to use `dev_seed_set`. The auxiliary set identity, exact roots, and
schedule are added to the manifest and warmup report. With the field absent,
the ordinary PPO train set remains the warmup source and historical runs retain
their exact manifest shape.

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

V7's two constructions match checkpoint `40478db69dd700b7...`, model state
`872234642d7238f3...`, and lineage `955960199cb90b18...`. Dev-v1 beats every
observed win comparator but retains small-sample scorecard uncertainty. The
exclusive dev-v3 confirmation completes at 35/40 wins versus permanent greedy
30/40, matched greedy 5/40, and matched random 3/40. Recovery, abandonment,
announcements, and duplicates pass. Idle difference is favorable on average
(`-0.0185`) but uncertain (`[-0.0566,0.0184]`), so V7 is rejected and dev-v3
is consumed without opening held-out-v2.

## V8 governed successor

ADR-0016 precommits a single auditable change before construction: subtract
0.25 from the V7 model's WAIT output bias (`special_head.2.bias[1]`). No reward,
feature, mask, lifecycle rule, or other parameter changes. Masks remain
authoritative, so forced/only-legal WAIT is unaffected. The hypothesis directly
targets V7's sole failed aggregate gate and is not a bias sweep.

Two constructions must match exactly. V8 must pass dev-v1 observed win gates
before the already frozen, globally disjoint 40-root dev-v4 set is opened for
one confirmation. A started attempt consumes dev-v4. Only full eligibility can
authorize held-out-v2; dev-v2 and dev-v3 remain consumed.

V8 constructions match checkpoint `1f3c4525fb5fd10d...`, model state
`b0ff1497ce1ae702...`, and lineage `8bc6ee1a9719e78d...`. Its one-way dev-v4
confirmation is fully eligible at 37/40 wins, with every paired scorecard
passing. The exclusive held-out-v2 final then completes once at 36/40 wins
(95% CI `[0.8,0.975]`), CI-separated from permanent random 19/40
(`[0.325,0.625]`) and permanent greedy 23/40 (`[0.425,0.725]`), and above
matched greedy 5/40.

V8 is nevertheless **not promoted**. Versus permanent greedy, announcements
are uncertain and idle (`+0.2710`) plus abandonment (`+0.1893`) regress with
separated intervals; recovery is uncertain. Versus matched greedy, idle remains
uncertain. Win superiority cannot override teammate-quality gates. The v2
attempt and artifacts are immutable, and individual outcomes cannot tune a
successor.

ADR-0017 freezes held-out-v3 before any new model work: 80 globally disjoint
roots, development-loader refusal, and one future exclusive final only after a
new candidate passes newly governed confirmation. Held-out-v2 is consumed.

## V9 governed successor

ADR-0018 precommits one final WAIT-bias step from train/dev evidence before V9
construction. V9 subtracts another 0.25 from `special_head.2.bias[1]`, making
the total V7→V9 WAIT adjustment `-0.50`. Every other tensor, reward, feature,
mask, and lifecycle rule remains fixed. This is not a coefficient sweep: the
single continuation follows V8's fully passing dev-v4 scorecards.

Two V8-parent constructions match checkpoint
`3ae49108c913b0783300744d906eda0ca2b7846115f3919378fc7ab9e8d2c998`,
model state `a62210ed1716cba6f2f869afe571373815ee4b25fddc18cacff25e93ca729af3`,
and lineage `c329bfc096122a13b2b5b18c4f1ff90bbaafa30fde621e70a7c25302ccc7f88c`.
After beating every dev-v1 win comparator, V9 completed the exclusive 80-root
dev-v5 confirmation at 65/80 wins. It passed the then-implemented matched-control
scorecard and all observed win gates, so held-out-v3 was opened once.

The held-out-v3 final completed at 70/80 wins (`0.875`, 95% CI
`[0.8,0.9375]`) versus permanent random 33/80 (`0.4125`,
`[0.3,0.525]`), permanent greedy 49/80 (`0.6125`, `[0.5,0.7125]`),
and matched greedy 5/80 (`0.0625`). Every win gate passed, but V9 is **not
promoted**. Versus permanent greedy, announcements, idle, and abandonment
regressed; recovery was uncertain. Versus matched greedy, idle was uncertain.
The final records, aggregate, and report SHA-256 values are respectively
`20d77ea9dc98057080b0ddba2d519c6ee12421b1b4c93aba5b40b857106b508d`,
`4f3ad4372798656ef8e6d2ee7b7f2ecf26a9ed6191aa88437b4f626545f58760`,
and `eff86e5d718addc968ff02fcf9a458a1f5f098b25b6192782780e050559ced30`.
Held-out-v3 is consumed; individual outcomes and traces remain quarantined.

The result exposed a governance mismatch: development preflight checked
teammate scorecards only against matched greedy, while the final also required
non-regression against permanent greedy. ADR-0019 makes the gates identical.
Preflight now loads and hashes exact seed-level permanent records and requires
both permanent-greedy and matched-greedy scorecards to pass. It also freezes
the 160-root, globally disjoint `bootstrap-defense-v1-held-out-v4` contract
before any future candidate work. Development tools refuse v4, which permits
one exclusive future final only after a newly governed candidate passes the
corrected dual-scorecard preflight.

## V10 governed successor

ADR-0020 precommits a full-boundary adaptive-teacher distillation experiment
from reusable dev evidence. V9 matched adaptive-v1 on only 5.3% of 8,180
unforced dev-v5 decisions. Adaptive-v1 reduced mean idle from about 0.310 to
0.076 and abandonment from about 0.202 to 0.118 on those roots, while a
role-assignment alternative won only 43/80 and raised duplicates.

V10 returns to V6's 64-root, 32-cycle PPO recipe and adds coefficient `1.0`
cross-entropy toward adaptive-v1 on every unforced transition. The earlier
V4/V5 term used only successful episodes at 0.05/0.10, so it did not address
losing-episode coverage. V10 changes no reward, feature, model, mask, lifecycle,
RNG, or inference behavior and names held-out-v4 in its immutable config.

Dev-v1 is only an early screen. ADR-0020 freezes a new one-way, 160-root
dev-v6 confirmation. Exact permanent records must be refreshed on dev-v6, and
both permanent-greedy and matched-greedy paired scorecards must pass before
held-out-v4 can be authorized.

Two pinned V10 runs reproduce exactly but reject the hypothesis on the dev-v1
screen. Both select update 6 at 1/10 wins with checkpoint
`a20f44d6ec0930768202da33c3833bebfbe46c6025547abc2ea31296cce4c6a8`,
model state `5d5cd3bd8395855f31abc8304583ca9ece70d1c2f78037c2a21596adb8b5e4c6`,
replay digest `045854f0a9e587128702e5538c36965e2d226be3f4ee7563e909c2b05479ddb2`,
and full-run digest
`787b5d4bd6548eea73c972c081fb72e031f9c516562f08eeb72538d8266769b1`.
Mean dev idle rises to about 0.361. Full-boundary coefficient 1.0 collapses win
capacity despite reducing teacher loss, so V10 stops before dev-v6; dev-v6 and
held-out-v4 remain unopened.

## V11 governed successor

ADR-0021 precommits a 90/10 interpolation of reproducible V6 update 31 and V10
update 6. This reuses the V7 weight that preserved 9/10 dev capacity while
testing V10's stronger all-boundary teacher state at bounded strength. No
reward, feature, mask, lifecycle, architecture, or inference behavior changes.
V11 names held-out-v4 and must reach at least 9/10 dev-v1 wins. Dev-v6 stays
reserved to rejected V10; a new disjoint 160-root dev-v7 set is frozen for one
ADR-0019 dual-scorecard confirmation only after V11 qualifies.

Two V11 constructions match checkpoint
`0a8fa8b4ba98581d776ee4a69e8f992b4b30f2776b82408eeeca791abd30749f`,
model state `eefe623958d9456d48e537cbcca20efb478335880f056a15c19e5ef7aed8deaf`,
and lineage `845282326c58308cbc4af03925559f332750de9e92cebfa365b7736d3bfa6fd7`.
Dev-v1 is 9/10 and beats all four observed win comparators, meeting the frozen
continuation bar. Permanent-greedy idle and abandonment regress; matched-greedy
idle and abandonment are favorable but uncertain on ten pairs. This authorizes
only the exclusive dev-v7 confirmation, not held-out-v4.

The exclusive dev-v7 confirmation completes once at V11 137/160, permanent
random 69/160, permanent greedy 100/160, matched random 19/160, and matched
greedy 12/160. Every observed win gate and every matched-greedy scorecard pass.
Versus permanent greedy, duplicates pass but announcements, idle, recovery, and
abandonment fail. V11 is rejected; dev-v7 is consumed and held-out-v4 remains
sealed. Records, aggregate, and report hashes are
`ebc2362db79af180804b6de057ec2e5bc3879b137a1856a281f12fa8f930d8bc`,
`a605ec43468f9f89158e95e6d4f2e47355415fd4d9f3b353ac282f6582569410`,
and `bdf411b0fb386e7cf1385292570f79384252701f31d9484f832c70c945b78cff`.

## V12 governed successor

ADR-0022 precommits `selector_reward_v2` after V11 proved that win capacity and
matched-team quality are no longer the limiting gates. V2 retains reward v1 and
adds bounded negative-only costs for cumulative idle agent ticks, duplicate
work, announcements, and non-forced team abandonment. The maximum new episode
penalty is 6.7, below the 20-point terminal win/loss gap. V1 remains the default
and cross-schema checkpoint use must fail.

V12 otherwise uses V6's 64-root/32-cycle recipe and names held-out-v4. Two
pinned runs must reproduce; dev-v1 continuation requires 9/10 wins and mean
idle below 0.25. Dev-v8 is frozen as a new globally disjoint 160-root one-way
confirmation under ADR-0019. No V12 training may begin until all four reward
audit rows and their adversarial tests pass.

V12 later reproduces at update 28 with 10/10 dev-v1 wins but mean idle
0.26628148, so it is rejected before dev-v8. ADR-0023 precommits V13 as the
same training construction with a quality-gated checkpoint selector: require
at least 9/10 wins and mean idle strictly below 0.25, then apply the existing
wins/return/core-health/earlier-update ranking. V13 must rerun twice rather than
retroactively relabeling a V12 artifact. Dev-v8 is retired unopened and dev-v9
is frozen as 160 disjoint roots `91001..91160` for one exclusive confirmation.

Two exact V13 runs reproduce the full idle-aware frontier and select update 24
at 10/10 dev-v1 wins with mean idle 0.24980951. Checkpoint
`ff5c21bc6644d903...`, full-run digest `842ac034e91e84ae...`, and lineage
`8aff4629be3090b3...` pass, authorizing dev-v9 only.

Dev-v9 completes once at V13 152/160, permanent random 62/160, permanent greedy
92/160, matched random 13/160, and matched greedy 15/160. All win and matched
scorecard gates pass. Permanent-greedy duplicates pass; announcements, idle,
recovery, and abandonment fail. V13 is rejected and held-out-v4 stays sealed.

ADR-0024 freezes scorecard v2 before any successor confirmation. Future
abandonment rates count structured non-forced ABANDON events only, using the
same safety/lifecycle exclusions as reward v2, while reporting forced and
non-forced counts separately. Simulation telemetry also exposes per-agent idle
ticks. Prior records and decisions remain v1 and are never recomputed.

## V39 governed successor

ADR-0052 precommits one selector-input coordinate from reusable V38 evidence.
The fixed scripted actions are already computed before the learned seat at the
same structured boundary. When seat 1 or 2 selects the exact same `task_id` as
a learned-seat candidate, V39 raises that candidate's existing normalized
`duplication_risk` input to `1.0`. This is structured evidence only: it does not
mask, redirect, reorder, force, suppress, or apply an action, and it does not
add a model dimension or reward component.

The complete V38 runtime, action vocabulary, feature shape, model, reward,
optimizer, roots, teacher, budget, RNGs, and checkpoint ranking remain exact.
Configurations without the explicit
`fixed_partner_selected_task_duplication_risk_v1` block remain historically
exact. Focused fail-closed tests, a disabled-feature parity replay, the public
survival/staging gate, full suites, smoke, determinism, golden/negative replay,
and exact-config reward adversaries must pass before replica A. Any public
regression rejects V39 before training.

The immutable config is
`configs/training/m8-selector-v39-partner-intent-duplication-risk.json`, SHA-256
`54d76bb209ec31f24bc2711b208cb2995e6d538534ba0b99a150091596ccf924`
after ADR-0053's final-identity-only repair.
The value-free confirmation umbrella reserves dev-v35. Dev-v35 membership
may be constructed only by the primary agent after this precommit is committed,
and may not be consumed until exact replicas and strict reusable scorecards
pass. Dev-v35 is frozen unconsumed with zero prior membership reads. A legacy
test read retired held-out-v5 without outcomes; ADR-0053 freezes held-out-v6
value-free in a separate no-read namespace. Neither dev-v35 nor held-out-v6
may be consumed before its frozen one-way gate.

V39 replica A later completed the exact construction but peaked at 8/10, below
the frozen 9/10 floor, despite rank-best idle `0.01845563475648595`. V39 is
rejected before replica B or scorecards. Dev-v35 is retired unopened and
unconsumed; held-out-v6 remains sealed and unconsumed.

## V40 governed successor

ADR-0054 identifies contradictory teacher supervision as the only narrow V40
coordinate. On V39's fixed warmup schedule, 752 of 3,956 teacher-eligible
transitions label an action that the same structured boundary marks as exact
partner-intent duplicate risk. The successful teacher corpus retains 189 such
transitions; deterministic V39 sampling presents them 177 times in warmup and
734 times in rehearsal, reaching 188 unique conflicts, while PPO's 0.05 teacher
term is also unfiltered.

V40 excludes only those exact action-index conflicts from teacher warmup,
teacher rehearsal, and PPO teacher imitation. The transition remains available
to PPO policy, value, entropy, reward, and trace construction. Historical
configs omit the filter and remain exact. Runtime selection, partner intent,
feature shape, action authority, reward, model, optimizer coefficients, roots,
budgets, RNGs, and checkpoint ranking remain V39-exact.

The immutable preimplementation config SHA-256 is
`230759e7e02dcca9a6b7608f7784b20f85845c40da0f7a28dd1ec13641d0013a`.
The value-free dev-v36 umbrella reserves 160 roots in `[4B,5B)` without a
membership read. Dev-v36 construction/access is primary-only after the
precommit and required gates; held-out-v6 remains sealed.

The filter implementation is committed at `c9459c58f4`. The bound train-only
diagnostic reproduces the complete schedule and corrected 189 successful-
corpus conflicts; its report/payload hashes are `4fe2960225d659cb...` /
`8484c36bf959fd9e...`. The 208-test Python suite passes. Runtime and reward
gates also pass: pinned Java, public 5/5 survival with 10 staging starts,
focused wake/staging, smoke, accepted determinism digests, golden/negative
replay, and 44/44 exact-config reward adversaries. Reward evidence hashes to
`9677e5caed4d891...`. Dev-v36 construction remains primary-only and must be
committed before model work. The dedicated freezer generates only within
`[4B,5B)`, hashes its in-memory manifest bytes, and never reads prior, sealed,
or generated membership; its pure tests pass in the 211-test suite.
The freezer was committed at `54db674e2e` and then created dev-v36 value-free.
Membership/receipt hashes are `d4bfbcf88d99f4f...` / `fce63a49f80d165...`;
the receipt records zero membership reads and no emitted values. Dev-v36 and
held-out-v6 remain unconsumed; 212 receipt-aware Python tests pass without
opening membership.

Replica A subsequently completed from committed repository `c288483436` and
passed construction. The frozen rank selects update 28 at 10/10 reusable wins,
return `7.77414`, core health `656.3`, and idle `0.008388499062201467`.
Checkpoint SHA is `9ff618797d8ae593...`; fresh replay is bit-exact at
`5af990a3ec8ff7fb...`, with action-state/full-run digests
`4f0726c7dc8f127...` / `b6dd3c958762c082...`. Replica B is authorized from
the identical committed identity. Dev-v36 consumption and held-out-v6 access
remain prohibited pending exact-twin and reusable-scorecard gates.

Replica B reproduces Replica A exactly, including all 32 checkpoint bytes,
warmup, selected update 28 metrics, checkpoint/model, replay, action-state, and
canonical full-run evidence. The official manifest comparator passes. Direct
lineage validates at digest `cfb0ec1b21fd49fb...`, artifact SHA
`5fdc3bdabf24ee5e...`. Fresh selected-only permanent baselines and both
reusable scorecards are therefore authorized; confirmation/final access is not.

Fresh reusable evidence then rejects V40 before confirmation. Candidate wins
10/10 versus permanent random/greedy 4/10 and 8/10 and matched random/greedy
5/10 and 6/10. All observed win comparisons pass, but permanent-greedy
announcements and idle CIs cross zero, and matched-greedy recovery crosses
zero. Both frozen scorecards therefore fail. Dev-v36 is retired unopened and
unconsumed; held-out-v6 remains sealed and unconsumed.

## V41 governed successor

ADR-0055 precommits one unswept 50/50 model-state midpoint between V40 updates
26 and 25. A canonical reusable-only diagnostic shows updates 25, 26, and 28
are each 10/10 and each fails permanent announcements/idle and matched recovery.
Updates 25 and 26 expose complementary idle outliers, while update 25 has the
best recovery mean and update 26 the best idle/announcement/core means.

Construction A uses Replica A's aligned parents and construction B uses Replica
B's; exact checkpoint/model/lineage identity is required before evaluation.
Runtime, reward, features, action authority, partner intent, scripted opening,
roots, and RNG semantics remain V40-exact. Dev-v37 is reserved value-free in
`[5B,6B)` and must be frozen primary-only before construction. Held-out-v6
remains sealed. Config/umbrella hashes are `c4705974f18512a...` /
`7ce8f5cf640978ef...`; no V41 model or evaluation work preceded the precommit.

The exact-config reward gate passes 44/44. Dev-v37 was then frozen value-free
and remains unopened; membership/receipt hashes are `7874f5abaf230665...` /
`277264b80c6456f7...`. Interpolation required one compatibility correction so
the governed constructor propagates `selector_reward_v2` from config while
preserving legacy reward-v1 defaults and failing closed on mismatch. The
224-test suite passes. Using the parent-pinned WSL Torch 2.12.1 environment,
independent A/B midpoints are byte-exact at checkpoint `b6b5e98ddee56740...`,
model state `93594bd64193740a...`, and lineage `37c4b1e571fca96c...`.

Fresh reusable evidence rejects the midpoint before confirmation. Permanent
random/greedy are 4/10 and 8/10; V41 is 10/10 and matched random/greedy are
5/10 and 6/10. All win comparisons pass. The permanent-greedy scorecard fails
only uncertain idle (mean `-0.00739956`, CI
`[-0.02001559,+0.01067689]`); the matched-greedy scorecard fails only uncertain
recovery (mean `-19.85`, CI `[-81.80125,+29.65]`). Report SHA is
`ca7b39c84a9f51d1...`. Dev-v37 is retired unopened/unconsumed and held-out-v6
remains sealed/unconsumed.

## V42 governed successor

ADR-0056 precommits the one remaining narrow training-only coordinate. Public
trace diagnosis shows V41's seed-2006 idle outlier follows learned-seat death
and forced WAIT while the surviving partners have only structured
`runtime:wait` candidates; teacher danger is zero and agrees with the learned
selection before every public learned-seat death. This closes WAIT-logit,
danger-label, exact-death recovery, and broader runtime-action interventions.

The exact V40 teacher train schedule contains 752 structured partner-intent
conflicts. A behavior-neutral, optimizer-free diagnostic finds a deterministic
valid non-WAIT alternate for 682, including all 256 tick-zero conflicts and
174/189 successful-corpus conflicts. V42 preserves the adaptive teacher's
current task-type preference/return-to-defense state, excludes exact risk
indices, then selects highest utility with lower-index tie breaking. The 70
no-alternate conflicts retain V40's filter. The original scripted action still
drives the teacher trajectory and policy state; only the separate imitation
label changes across warmup, rehearsal, and PPO teacher imitation.

Runtime actions and masks, fixed partners, features, reward, model, optimizer
coefficients, roots, budget, RNGs, checkpoint ranking, and engine pins remain
V40-exact. Config/umbrella hashes are `3fcb0c8800c638a3...` /
`c1644d2dd6dde231...`. Dev-v38 is reserved primary-only in `[6B,7B)` and was
not constructed until the committed implementation and complete public/
pretraining boundary passed. Held-out-v6 remains sealed and unconsumed. No model
work or restricted membership access preceded this precommit.

The implementation now keeps original and effective teacher labels separate,
uses one shared effective-label rule in warmup, rehearsal, and PPO teacher CE,
and emits V42-only relabel/fallback/schedule evidence. Pure selection tests cover
state nonmutation, adaptive preference, stable ties, invalid/masked/WAIT
exclusion, and no-alternate fallback; historical V40 sampling fixtures remain
exact. The live production diagnostic reproduces 752 conflicts, 682 relabels,
and 70 fallbacks over 34,898 transitions. Its report/payload/action-state hashes
are `83f8dd6904e5356d...` / `e92436ffb3773b80...` /
`0e609742ba171c60...`.

The complete 2026-07-23 pretraining boundary passes 243 Python tests and the
Java gate, public 5/5 survival with 10 proactive staging starts, secondary-claim
and owned-schematic checks, smoke, deterministic cross-process/reset/seed
checks, the 664-checkpoint/16,200-tick golden plus negative replay, and all 44
exact-config reward adversaries. The reward report SHA is
`272ac291ef143fa6...`. The primary-only freezer was committed at `3e328ce91e`
and then created dev-v38 value-free. The freeze commit is `949b73f987`;
membership/receipt hashes are `3f4b0d012cf87303...` /
`fea431ae993d1072...`. The receipt records zero membership-document reads and
no values emitted. The full suite passes 248 tests.

Independent construction under the pinned WSL Torch 2.12.1 toolchain and
training commit `12980ee2b9` is exact. Replicas A/B both select update 2 at 9/10
reusable wins, mean return `4.73976`, core health `568.8`, and idle
`0.03455784384563236`; all 32 checkpoint files match. Checkpoint/model/replay/
action-state/full-run hashes are `65f8e3dc3a41bf89...` /
`4363617f8535bc8b...` / `d01d0dfe425d1b0d...` /
`52751513f785c196...` / `cb719361da11ab6c...`. Direct lineage digest/artifact
hashes are `b1dbf1abc6a7dacd...` / `100945a4820b2039...`.

Fresh permanent random/greedy are 4/10 and 8/10; candidate is 9/10 and matched
random/greedy are 5/10 and 6/10, so all observed win comparisons pass. Both
frozen scorecards fail. Permanent-greedy announcements and idle cross zero;
matched-greedy recovery also crosses zero. Records/aggregate/report hashes are
`e0a78468268bc021...` / `dae12fbf3868c6cc...` /
`01bf941060bc7e6f...`. V42 is rejected before confirmation.

An explicitly off-contract public diagnostic retargets only the existing
tick-zero prior from `BUILD_SCHEMATIC` to `BUILD_LINE`. All ten openings become
nonconflicting and permanent/matched idle passes, but the variant remains 9/10
and still fails permanent announcements and matched recovery. Records/report
hashes are `6ccd6ac543d43891...` / `41e3b71b133f4c63...`. The diagnostic has no
promotion authority and closes the runtime-prior reopening. No V43 is
authorized; dev-v38 is retired unopened/unconsumed and held-out-v6 remains
sealed/unconsumed.

## V43 governed architecture successor

ADR-0060 precommits the first model-architecture successor after the independent
v1 scorer failed the frozen promotion scorecards. The v1 SELECT head sees one
candidate plus scalar context but cannot see competing candidates, while its
CONTINUE/WAIT head cannot see the candidate catalog at all. Reusable/train-only
evidence repeatedly exposes catalog-dependent alternative choice, including 682
teacher-conflict alternates and a catalog-dependent idle correction.

V43 keeps the exact V42 observation, runtime, action authority, reward, teacher
trajectory/relabeling, roots, budgets, optimizer, RNG values, scripted seats,
and engine pins. Its masked set-context actor gives each SELECT logit the mean
embedding of the other present candidates and gives CONTINUE/WAIT the mean of
all present candidates. Padding is excluded; masks remain authoritative. The
critic retains its existing scalar-plus-pooled-candidate input.

The immutable config/umbrella hashes are `29b4430839451f13...` /
`99851aa2cdbfb469...`. Dev-v39 is reserved primary-only in `[7B,8B)` but may not
be constructed until the committed implementation and complete pretraining
boundary pass. Dev-v38 remains retired without a membership read. Held-out-v6
remains sealed and unconsumed. No V43 implementation, model construction, or
restricted membership access preceded this precommit.

The implementation now selects v1/v2 models from the immutable config, uses
masked candidate presence for set pooling, propagates the dynamic schema through
checkpoints, replicas, lineage, preflight, and final evaluation, and rejects
cross-schema substitution. The complete boundary passes 293 Python tests,
pinned Java, public 5/5 survival with 10 staging starts, both focused checks,
smoke, deterministic golden/negative replay, and all 44 exact-config reward
adversaries (`3e3210447ff4f428...`). Dev-v39 remains unconstructed and no V43
training episode has run.

Both V43 replicas then reproduce exactly at selected update 27: 10/10 wins,
mean idle `0.00874233`, checkpoint `b4cc691ad0c08d67...`, replay
`12ed6b616310deb7...`, and full-run digest `66385a8f85ec7db7...`. Direct lineage
passes at `1f07166a5d27aa30...`. Fresh permanent random/greedy are 4/10 and 8/10;
matched random/greedy are 5/10 and 6/10. Every win comparison passes and
permanent recovery becomes decisively favorable, but the frozen scorecards
still reject V43: permanent announcements and idle remain favorable but
uncertain, and matched recovery remains uncertain. Report SHA is
`10f829a54a110507...`. Dev-v39 is retired unopened/unconsumed and held-out-v6
remains sealed.

## V44 governed lagged-boundary successor

ADR-0061 precommits the first bounded temporal coordinate. V43 routes the full
current candidate set but remains memoryless, while every remaining failed
metric is sequence-defined. On reusable root 2004 its 65 WAIT actions and only
five SELECT actions coincide with the sole high-idle candidate trajectory.
Current features cannot distinguish a newly changed team/catalog boundary from
an otherwise similar repeated boundary.

V44 retains the exact current 8x37 candidate rows and 56 scalars, then appends
the immediately previous authoritative boundary's 56 base scalars, masked mean
of its 37-value present candidate rows, candidate-count fraction, and submitted
ten-way action one-hot. The initial lag is all zero and reset clears it. The
model retains V43's set pooling and heads; only its scalar encoder grows from
56 to 160 inputs. This is explicit one-boundary memory, not a recurrent hidden
state, runtime prior, reward change, or teacher change.

The immutable config/umbrella hashes are `9a23c90567754eb8...` /
`4a526274d9568726...`. Dev-v40 is reserved primary-only in `[8B,9B)` but must
not be constructed until the committed implementation and complete pretraining
boundary pass. Dev-v39 remains retired without a membership read. Held-out-v6
remains sealed and unconsumed. No V44 implementation, model construction, or
restricted membership access preceded this precommit.

The implementation now carries the lag through the framework-neutral selector
history and config-selects v1/v2/v3 feature/model pairs. Immutable snapshots,
reset isolation, padding exclusion, action encoding, set equivariance, masks,
and cross-schema rejection are covered. The complete boundary passes 305 Python
tests, pinned Java, public 5/5 survival with ten staging starts, both focused
checks, smoke, deterministic golden/negative replay, and all 44 exact-config
reward adversaries (`740aba578809911...`). Dev-v40 remains unconstructed and no
V44 training episode has run.

The primary-only dev-v40 freezer is now implemented with exact hash/path/
namespace/sealed-binding validation and a value-free zero-read receipt. All 310
Python tests pass. It has not executed; commit the freezer before construction.

Committed freezer `6b7a6c5dca` created dev-v40 value-free in `[8B,9B)`.
Membership/receipt hashes are `05ca1f48227581fc...` /
`acffc919ab1c40e2...`; the receipt attests no values emitted, zero membership
reads, and no retired or sealed-set access. Dev-v40 remains unconsumed. Commit
the membership/receipt packet before replica A.

Both V44 replicas reproduce exactly and select update 1 at 9/10 wins, mean idle
`0.07252724`, checkpoint `4e51d31bd4f33a67...`, replay
`a5ac208b8ea91f19...`, and full-run digest `029e77830406127a...`. Every observed
win comparison passes. Matched announcements and permanent recovery pass, but
the scorecards reject V44: permanent idle decisively regresses and permanent
announcements/duplicates plus matched duplicates/idle/recovery remain
uncertain. Report SHA is `260625f302f3e268...`. Update 1 is the frontier's only
9-win checkpoint and later updates collapse to 4-8 wins, implicating the
160->64 replacement of V43's current-state scalar path. Dev-v40 is retired
unopened/unconsumed and held-out-v6 remains sealed.

## V45 governed residual-temporal successor

ADR-0062 preserves V43's complete current-state set actor and encodes V44's
104-value lag separately. Zero-initialized temporal SELECT and CONTINUE/WAIT
output layers add residual logits to the unchanged base actor; the critic stays
current-state-only. Thus construction begins lag-independent without V44's
160->64 bottleneck, while training can learn bounded temporal corrections.

The immutable config/umbrella hashes are `a7d0c8029acebe79...` /
`e4fe0b56a95fa64c...`. Dev-v41 is reserved primary-only in `[9B,10B)` and
remains unconstructed. Dev-v40 remains retired without a membership read and
held-out-v6 remains sealed. No V45 implementation or model work preceded this
precommit.

The residual actor is now implemented and construction-time identical to V43
until its exact-zero temporal heads learn. The 273-test embargo-safe suite,
pinned Java, public 5/5 gate, focused checks, smoke, golden/negative determinism,
and all 44 exact-config reward adversaries (`84cd359cf9cbd401...`) pass. The 43
legacy scenario-variation tests remain last green before dev-v40 freeze and are
not rerun because they glob-read retired membership. Dev-v41 is unconstructed
and no V45 training episode has run.

The primary-only dev-v41 freezer is implemented with commit-bound reusable
atomic primitives, exact V45 validation, and a value-free receipt; the embargo-
safe suite now passes 277 tests. It has not executed. Commit it before
membership construction.

The committed freezer constructed dev-v41 without emitting or reading seed
values. Membership/receipt hashes are `591513526bdd0bce...` /
`d2d14a281d37a046...`; the receipt records zero membership-document reads.
Dev-v41 is frozen and unconsumed.

Two exact V45 replicas select update 32 at 10/10 reusable wins, return
`7.67784`, core `730.1`, and idle `0.00873637`; checkpoint/full-run/lineage
prefixes are `cdc526403cd1fe27...` / `f253cd6dbb1c0f5c...` /
`5c1ca3fc7ab9c49f...`. Fresh permanent random/greedy are 4/10 and 8/10 and
matched random/greedy are 5/10 and 6/10. Every win gate passes, but permanent
announcements and idle and matched recovery remain favorable yet uncertain, so
both reusable scorecards fail. Report SHA is `ea7466a45d91d415...`.

Reusable root 2004 explains the remaining idle interval: all 65 WAIT actions
are forced and excluded from policy loss after the only legal defense action,
which agrees with the scripted teacher. The selector cannot choose at those
boundaries. V45 is rejected before confirmation; dev-v41 is retired unopened/
unconsumed, held-out-v6 remains sealed, and no evidence-backed V46 coordinate
is authorized.

The legacy scenario-variation disjointness tests are now embargo-safe: their
membership reads are limited to explicit fixed/train, dev-v1..v33, and held-
out-v1..v4 contracts, while later governed replacements use receipts and
existence checks only. All 44 focused tests and the complete 322-test Python
suite pass without opening dev-v34..v41 or held-out-v5/v6 membership.

ADR-0063 uses the project owner's explicit scope-change authorization to
precommit V46's one bounded control action. `DEFER_TO_SCRIPTED_EXPERT` is a
policy-side index translated to the already-computed canonical adaptive-v1
seat-0 action at the same immutable boundary. It cannot override forced safety
or lifecycle actions and is unavailable for expert WAIT. The V45 ordinary
actor/critic remains the exact base; a same-boundary expert-action one-hot and
zero-initialized DEFER head are appended. Teacher losses remain ordinary-action
only, while PPO learns the control decision. Promotion caps mean DEFER at 25%
of unforced policy decisions.

Config/umbrella hashes are `b588ee43e66bd9d...` /
`a78631d7ba9f1cd2...`. Dev-v42 is reserved value-free in `[10B,11B)` but
unconstructed. Implementation and the complete public/pretraining boundary
must be committed before membership construction or model work. Dev-v41 remains
retired unopened and held-out-v6 remains sealed.

The V46 implementation and complete pretraining boundary are now green. Feature
v3 appends only the canonical expert-action one-hot; control v2 exposes DEFER
only for legal unforced non-WAIT expert proposals and records the effective
ordinary action in history. Model v5 preserves V45's ten ordinary logits,
masked logits, and critic bit-exactly at initialization, while its separate
expert encoder feeds a zero-output DEFER head. Teacher losses remain sliced to
actions 0..9, and checkpoint/reusable/confirmation/final gates enforce the
inclusive 25% mean-DEFER cap with validated telemetry.

Thirteen focused V46 tests and the complete 335-test embargo-safe Python suite
pass, as do pinned Java/custom modules, public survival 5/5 with ten staging
starts, both focused coordination checks, smoke, the accepted 79-boundary and
664-checkpoint/16,200-tick golden replay plus negative mutation check, and all
44 exact-config reward adversaries. The adversary report SHA-256 is
`ec3acb4c1056207a1f83729cb62e5c38042164c5688e67c18c6d842d96a54b9e`.
Dev-v42 remains unconstructed, no V46 training/checkpoint exists, dev-v41
remains retired unopened/unconsumed, and held-out-v6 remains sealed.

The primary-only dev-v42 freezer is implemented but has not executed. It reuses
the committed atomic/no-read primitives, pins the V46 implementation/config/
umbrella commits, validates the `[10B,11B)` namespace and held-out-v6 binding,
and can emit only a value-free receipt. The embargo-safe suite now passes 339
tests. Commit the freezer before membership construction.

The committed freezer constructed dev-v42 without emitting or reading
membership. Its value-free receipt binds membership
`8f518384f19c193fa793034a141c0a89c6973dbe788de87520a6b86b16bed865`,
generator `e9a828a7d01ed7e9...`, and implementation `173cd5c2a11f3237...`,
and records zero membership-document reads. Dev-v42 is frozen and unconsumed;
do not access it until exact replicas and every reusable scorecard/control gate
pass. The receipt-aware embargo-safe suite now passes 340 tests.

Two pinned V46 replicas select update 32 at 10/10 public-dev wins, return
`7.22016`, core `639.2`, idle `0.01033305`, and mean DEFER `0.18420177`.
Checkpoint/model/replay/full-run prefixes are `93694e4d70ec56e4...` /
`70c762f358ae8cce...` / `493ab925a384ccec...` /
`8d61abfa4ce4fe10...`, and the complete manifests compare exactly. Direct
lineage initially failed closed because its expected schema omitted V46's
control coordinate; that validator now binds control v2 explicitly and the
341-test suite passes. No reusable or restricted episode has run.

Direct lineage is now canonical at `b6322349e4d14b31...`. Fresh permanent
random/greedy baselines are 4/10 and 8/10; matched random/greedy are 5/10 and
6/10. V46 wins 10/10 and passes the mean-DEFER gate at `0.18420177`, but both
frozen scorecards reject it. Against permanent greedy, announcements have mean
difference `-0.00135566`, CI `[-0.00779035,+0.00535807]`, and idle has
`-0.00538749`, CI `[-0.01753561,+0.01213167]`. Against matched greedy, recovery
has `-18.0`, CI `[-82.11,+39.75125]`. Report SHA-256 is
`2af00337138b99394b4b95994c072bffa2ae01a1d9bf9354f635044cfbf22b23`.
V46 is rejected before confirmation; dev-v42 is retired unopened/unconsumed and
held-out-v6 remains sealed.

ADR-0064 corrects the reusable scorecard's statistical power with explicit
owner authorization. The zero-crossing paired-bootstrap rule is unchanged, but
the canonical reusable screen is precommitted at 160 public roots instead of
ten. The frozen V46 checkpoint receives one rescreen with fresh permanent and
matched baselines; it is not retrained or reselected. The public membership is
reserved in `[11B,12B)`, while replacement confirmation dev-v43 is reserved
value-free in `[12B,13B)` and remains unconstructed unless every reusable-v2
gate passes. Dev-v42 remains retired unopened/unconsumed and held-out-v6
remains sealed.

The ADR-0064 precommit landed at `26d25acd64`. Its deterministic generator then
froze the 160 public reusable-v2 roots at membership SHA
`c529951782ec0426f...` without running an episode or reading dev-v42/held-out-v6
membership. Reusable-v2 is frozen and unevaluated pending its separate
membership/evidence commit.

The canonical 160-root screen rejects V46. It wins 96/160 versus permanent
greedy's 84/160 and passes every matched-greedy scorecard plus the DEFER cap,
but permanent announcements remain uncertain and permanent idle has an
unfavorable `+0.00391218` mean difference. Preflight SHA is
`d272edd51197166b...`. Dev-v43 remains unconstructed and held-out-v6 remains
sealed.

Public reusable-v2 traces then isolate the fixed-seat authority defect. When
seat 0 dies before tick 3000 (63 roots), the idle and announcement gaps are
`+0.02701331` and `+0.00769989`; after later death (94 roots), both gaps are
favorable. ADR-0065 precommits V47: exactly one learned brain remains sticky to
its active unit, then transfers only on death to the lowest-ID living unit.
History resets, partner intent becomes all living nonactive agents, and the
feature/model/reward/control schemas stay exact. Dev-v43 is cancelled
unconstructed; dev-v44 is reserved in `[13B,14B)` but unconstructed.

The V47 implementation and complete public/pretraining boundary are green.
Training and matched controls share the same active-seat sequence; history
resets on transfer; dynamic intent excludes the active and dead seats; lineage,
reusable, confirmation, and final reports bind the one-brain schema. The live
public failover gate transfers `0->1->2` at ticks 2738/4462 and wins at tick
9000 with a maximum of one learned seat. The 348-test Python suite, pinned Java
boundary, public 5/5 survival gate, focused checks, smoke, deterministic
golden/negative replay, and 44/44 exact-config reward adversaries pass
(`5e6aec4530d27823...`). Dev-v44 remains unconstructed and no V47 model work
has begun.

The primary-only dev-v44 freezer is implemented and unexecuted. It binds the
committed V47 boundary and creates membership plus a value-free receipt
atomically without reading cancelled, retired, generated, or sealed membership.
The full embargo-safe suite now passes 352 tests. Commit the freezer before
construction.

The committed freezer constructed dev-v44 value-free. Membership SHA is
`82ea1b7d59f23a0d...`; the receipt binds generator `56dab3eb9e...` and
implementation `64463e76e5...` and attests zero membership reads. Dev-v44 is
frozen and unconsumed. Commit this membership/receipt packet before replica A.

V47's replicas reproduce exactly at update 25 with 10/10 public-dev wins,
idle `0.01586387`, DEFER `0.13594699`, and checkpoint
`ea821b97dd1e6f4c...`. Reusable-v2 wins are 125/160 versus permanent greedy
84/160 and matched greedy 22/160. All control gates and nearly every quality row
pass, but permanent idle remains uncertain around equality and one automatic
`plan_removed` event makes non-forced abandonment uncertain against both
greedy comparators. Preflight is `8eb91b92dc36a22...`; V47 is rejected,
dev-v44 is retired unopened/unconsumed, and held-out-v6 remains sealed.

Public diagnostics close simple rescue paths. Highest-living failover worsens
idle and wins. Frontier update 27 removes abandonment but worsens idle. Update
32 reaches 128/160 wins, zero abandonment, and favorable mean idle, but its
paired interval still crosses zero. The remaining variance concentrates after
failover, especially when authority ends on seat 1. V47's mandatory history
reset discards that surviving seat's immediately prior scripted boundary.

ADR-0066 precommits V48's single causal coordinate. The one learned brain and
lowest-living failover remain exact, but every seat maintains a reset-local
structured `SelectorHistory` cache from its own submitted scripted or learned
action. On death transfer, the brain adopts the target living seat's real prior
boundary instead of all zeros. There is still one model evaluation and one
learned action per boundary; feature/model/reward/control schemas, roots,
budget, optimizer, and RNGs remain V47-exact. Config/umbrella hashes are
`714bd13db0ffee6f...` / `656602be6dd5c3cf...`. Dev-v45 is reserved in
`[14B,15B)` but unconstructed. No V48 implementation or model work preceded
this precommit.

The V48 implementation and complete public/pretraining boundary are now
green. Candidate and matched-control rollouts maintain three reset-local
caches, update only living seats from the already-drained structured boundary,
retain dead-seat caches, and adopt the target cache on transfer. Manifests,
lineage, traces, reusable/final gates, and live telemetry bind
`per_seat_scripted_prior_boundary_cache_v1`; the candidate performs exactly
one model evaluation and submits at most one learned action per boundary.
The focused live gate repeats the public `0->1->2` death sequence twice in one
JVM and wins at tick 9000 with transfers at ticks 2738 and 4462. All 361 Python
tests, custom Java modules, public 5/5 survival, focused coordination checks,
smoke, deterministic golden/negative replay, and 44/44 exact-config reward
adversaries pass (report SHA `8cfe56b3a000d4c...`). Dev-v45 remains
unconstructed and no V48 training episode has run.

The V48 value-free freezer is implemented separately from the runtime. It pins
implementation `07c6951a7ffe8da...`, the immutable config/umbrella, V47's
public reusable evidence, the `[14B,15B)` namespace, retired dev-v44, and
sealed held-out-v6 without reading any restricted membership. Its pure tests
prove range, exact reservation, and value-free receipt behavior. The freezer
must be committed before it may atomically construct dev-v45.

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
