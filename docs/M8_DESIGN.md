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
