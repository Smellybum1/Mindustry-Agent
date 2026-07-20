# M8 design — one learned task-selector seat

**Status:** M8.1 design accepted; implementation remains gated by M8.2/M8.3.
**Feature schema:** `selector_features_v1`. **Reward schema:** `selector_reward_v1-draft`.

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

Every numeric term is finite and clipped to `[0,1]`. M8.4 must expose the raw
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

## Reward v1 draft and hard gate

`selector_reward_v1-draft` contains only:

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
and adversarial cases live in `docs/REWARD_AUDIT.md`. Reward emission and PPO
training are forbidden until every listed implementation test is green and the
row status changes from `drafted-not-implemented`.

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
