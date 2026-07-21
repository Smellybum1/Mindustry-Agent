# Reward audit

**Status: selector reward v1 implemented and adversarially verified.** This
document is the standing audit for every reward component. Per brief §17.5/§28,
no reward component may influence
training until it has an entry here with: definition, scale, state variables,
intended behaviour, **at least three exploit hypotheses**, automated adversarial
tests, and example graphs/events.

## Reward component template (copy per component)

| Field | Value |
|---|---|
| Name | `reward.<scope>.<name>` |
| Definition | |
| Scale / range | |
| State variables read | |
| Intended behaviour | |
| Exploit hypothesis 1 | |
| Exploit hypothesis 2 | |
| Exploit hypothesis 3 | |
| Adversarial tests | |
| Telemetry key | |
| Status | not implemented |

## Telemetry keys (must always be stored separately, never only the sum)

```text
reward.team.objective
reward.team.wave
reward.team.core_health
reward.team.production
reward.team.efficiency
reward.agent.task_progress
reward.agent.help
reward.penalty.invalid_action
reward.penalty.duplicate_work
reward.penalty.communication
reward.penalty.abandonment
reward.team.milestone_highwater
reward.team.terminal_outcome
reward.team.unresolved_tick_cost
reward.penalty.abandonment_liability
```

## Known Mindustry reward-hacking risks (brief §17.5)

Each of these must be mitigated before the corresponding signal is used.

| Proposed signal | Likely exploit | Safer treatment | Status |
|---|---|---|---|
| Items mined | Mine and discard repeatedly | Reward net useful delivery to a valid sink | not implemented |
| Items delivered | Move the same items back and forth | Track source/sink and net milestone change | not implemented |
| Blocks built | Build/deconstruct/rebuild loops | Reward first completion of required plan | not implemented |
| Repair amount | Allow or cause repeated damage | Reward objective survival or avoided loss, not raw repair | not implemented |
| Enemies damaged | Farm durable targets or ignore objective | Reward threat removal and scenario outcome | not implemented |
| Time alive | Hide forever | Time cost plus objective milestones | not implemented |
| Messages sent | Spam announcements | Never positive; apply small communication cost | not implemented |
| Help offered | Offer help without contributing | Reward only accepted, measured contribution | not implemented |
| Task count | Create trivial tasks | Fixed validated task catalog and value thresholds | not implemented |
| Production rate | Produce unusable stockpiles | Tie to scenario demand and bounded inventory | not implemented |
| Wave progress | Trigger waves recklessly | Balance survival, damage, and completion | not implemented |

Adversarial tests for each row land before reward activation (roadmap M8.4).

## M8 selector reward v1

All five components below are implemented by `SelectorReward`, stored
separately in trajectories/manifests, and approved for M8.4 training only. The
27-case `reward_adversary` gate runs before either independent PPO run. This is
not an M8.5 promotion approval and does not authorize held-out evaluation.

### `reward.team.milestone_highwater`

| Field | Value |
|---|---|
| Definition | Emit once per physical high-water mark: working line `+1`, defense readiness reaching 1.0 `+1`, and each scheduled wave changing from present to cleared `+2` (three waves, total component cap `+8`). |
| Scale / range | `[0,+8]` per episode; no negative delta when a milestone is later lost. |
| State variables read | `line_operational`, `defense_readiness`, scenario wave schedule/ordinal, enemy-count transition, per-episode high-water bitset. |
| Intended behaviour | Establish useful economy/defense early and clear real threats; share sparse team credit with the selector seat. |
| Exploit hypothesis 1 | Complete, destroy, and rebuild the same line/defense to repeat rewards. Mitigation: monotonic bitset keyed by physical milestone ordinal, not task id. |
| Exploit hypothesis 2 | Idle while the two scripted seats earn every team milestone. Mitigation: terminal/time terms plus mandatory wait-only counterfactual; this component is rejected if WAIT-only return is not lower than the matched greedy seat. |
| Exploit hypothesis 3 | Manipulate enemy count or task events to fake a wave clear. Mitigation: require a scheduled native wave to have spawned and the authoritative enemy group to transition nonzero→zero; task completion/messages never count. |
| Adversarial tests | `reward_adversary --case rebuild-loop`; `--case wait-only`; `--case fake-wave-clear`. Assert each high-water id pays once, WAIT-only return is lower, and unscheduled/enemy-free transitions pay zero. |
| Telemetry key | `reward.team.milestone_highwater` plus `reward.team.milestone_ids[]`. |
| Status | implemented-approved-m8.4; adversaries pass 2026-07-21 |

### `reward.team.terminal_outcome`

| Field | Value |
|---|---|
| Definition | `+10` for scenario win; `-10` for loss or truncation. Exactly one terminal value. |
| Scale / range | `{-10,+10}`. |
| State variables read | Authoritative scenario outcome, `terminations[]`, `truncations[]`. |
| Intended behaviour | Make team survival/completion dominate shaping and reject crashes/timeouts as success. |
| Exploit hypothesis 1 | Hide/defend forever and ignore economy/tasks. Mitigation: fixed scenario terminal rules plus milestone/time terms and held-out scorecard non-regression. |
| Exploit hypothesis 2 | Crash, disconnect, or force truncation to escape a likely loss. Mitigation: truncation equals loss and retains remaining time charge. |
| Exploit hypothesis 3 | Achieve a minimal win while sacrificing teammate quality/core margin. Mitigation: scorecard CI non-regression is a separate hard promotion gate; terminal reward cannot override it. |
| Adversarial tests | `reward_adversary --case survival-only`; `--case forced-truncation`; `--case reckless-minimal-win`. Assert no nonterminal survival pays, truncation equals loss, and the reckless trace fails promotion despite reward. |
| Telemetry key | `reward.team.terminal_outcome`. |
| Status | implemented-approved-m8.4; adversaries pass 2026-07-21 |

### `reward.team.unresolved_tick_cost`

| Field | Value |
|---|---|
| Definition | `-0.0002 × advanced_ticks` while any milestone-high-water bit is unset. On loss/truncation, also charge the unadvanced ticks through the scenario cap. Stop only after every milestone is genuinely reached. |
| Scale / range | `[-1.8,0]` for the current 9,000-tick cap. |
| State variables read | `advanced_ticks`, scenario tick cap, milestone bitset, terminal outcome. |
| Intended behaviour | Prefer earlier useful readiness/clears without depending on call count or wall time. |
| Exploit hypothesis 1 | Lose early to avoid future time cost. Mitigation: counterfactual remaining-cap charge on loss/truncation. |
| Exploit hypothesis 2 | Change action repeat/decision frequency to alter cost. Mitigation: exact engine ticks only; identical action trace has identical total. |
| Exploit hypothesis 3 | Superficially trip readiness then abandon the objective to stop cost. Mitigation: high-water trigger uses physical predicates and terminal/scorecard gates punish subsequent collapse. |
| Adversarial tests | `reward_adversary --case early-suicide`; `--case chunk-size`; `--case readiness-then-abandon`. Assert early/late losses have equal tick-cost horizon, chunkings match exactly, and superficial task events do not stop cost. |
| Telemetry key | `reward.team.unresolved_tick_cost`, `reward.team.charged_ticks`. |
| Status | implemented-approved-m8.4; adversaries pass 2026-07-21 |

### `reward.penalty.invalid_action`

| Field | Value |
|---|---|
| Definition | `-0.25` when the raw policy choice is false in the 10-way mask; cap at `-1.0` per episode and submit protocol WAIT. Server-side claim loss/rejection of a mask-valid atomic bid is not invalid. |
| Scale / range | `[-1,0]`. |
| State variables read | Raw action index, exact boundary action mask, typed action result. |
| Intended behaviour | Make mask/plumbing failures visible and harmless without overwhelming outcome reward. |
| Exploit hypothesis 1 | Spam masked actions after the cap. Mitigation: WAIT fallback still loses milestone/time opportunity; spam case must score below valid WAIT and greedy. |
| Exploit hypothesis 2 | Penalize the policy for a stale/broken environment mask. Mitigation: archive observation/mask/raw action; schema or stale-boundary mismatch fails the run rather than assigning reward. |
| Exploit hypothesis 3 | Use invalid probes to gain state or an alternate valid action. Mitigation: no retry or new observation; exactly WAIT and one structured diagnostic. |
| Adversarial tests | `reward_adversary --case invalid-spam`; `--case mask-corruption`; `--case invalid-probe`. Assert cap/fallback, environment fault classification, and no extra action/state transition. |
| Telemetry key | `reward.penalty.invalid_action`, `reward.invalid_action_count`. |
| Status | implemented-approved-m8.4; adversaries pass 2026-07-21 |

### `reward.penalty.abandonment_liability`

| Field | Value |
|---|---|
| Definition | `-0.05` when a task selected by the learned seat is later abandoned for policy/replanable BLOCKED reasons; cap `-0.5`. Exclude forced wave/readiness switches, death, lease-failure fixtures, human override, and terminal cleanup. |
| Scale / range | `[-0.5,0]`. |
| State variables read | Accepted learned selection id/semantic key, structured ABANDON event/reason, forced-action classification. |
| Intended behaviour | Discourage knowingly bad/churning selections while preserving necessary safety switches and recovery. |
| Exploit hypothesis 1 | Never abandon a permanently blocked task to avoid the penalty. Mitigation: unresolved tick cost, missed terminal/milestones, and deterministic bounded lifecycle abandon still apply. |
| Exploit hypothesis 2 | Select only trivial/WAIT work to avoid abandonment. Mitigation: WAIT has no milestone credit and the wait-only adversary must underperform matched greedy. |
| Exploit hypothesis 3 | Cause a forced safety/death/human abandon to be charged or farmed. Mitigation: reason allowlist and accepted-selection attribution; excluded reasons always pay zero. |
| Adversarial tests | `reward_adversary --case claim-abandon-churn`; `--case blocked-never-release`; `--case forced-abandon-exclusions`. Assert capped liability, safety recovery, and exact zero for exclusions. |
| Telemetry key | `reward.penalty.abandonment_liability`, `reward.abandonment_reason_counts`. |
| Status | implemented-approved-m8.4; adversaries pass 2026-07-21 |

## V12 selector reward v2 implementation

`selector_reward_v2` retains every v1 component and adds the four negative-only
rows below. They were precommitted under ADR-0022 before implementation and
may influence V12 after the production tests and expanded adversary gate pass.

### `reward.penalty.team_idle_ticks`

| Field | Value |
|---|---|
| Definition | `-0.0001` for each monotonic increase in cumulative `idle_agent_ticks`. |
| Scale / range | `[-2.7,0]` for three agents and the 9,000-tick cap. |
| State variables read | Structured cumulative `idle_agent_ticks`, `agent_ticks`, scenario tick/agent cap, prior counters. |
| Intended behaviour | Prefer action traces that keep the whole mixed team doing useful work. |
| Exploit hypothesis 1 | Lose early to avoid idle cost. Mitigation: terminal loss plus full-horizon unresolved cost dominates. |
| Exploit hypothesis 2 | Manipulate step chunking. Mitigation: charge exact cumulative delta and fail counter rollback. |
| Exploit hypothesis 3 | Perform churn/busywork instead of idling. Mitigation: duplicate/abandon penalties plus milestone, win, and scorecard gates. |
| Adversarial tests | `idle-early-loss`; `quality-chunk-size`; `idle-busywork`. |
| Telemetry key | `reward.penalty.team_idle_ticks`, `reward_quality_counters.idle_agent_ticks`, `reward_quality_penalty_totals`. |
| Status | implemented-approved-v12; adversaries pass 2026-07-21 |

### `reward.penalty.duplicate_work`

| Field | Value |
|---|---|
| Definition | `-0.05` per monotonic increase in cumulative `duplicate_work_incidents`, capped at `-1.0`. |
| Scale / range | `[-1,0]`. |
| State variables read | Structured cumulative duplicate counter and prior charged count. |
| Intended behaviour | Reduce redundant claims/work without blaming mask-valid atomic claim races as invalid actions. |
| Exploit hypothesis 1 | Stop proposing useful work. Mitigation: terminal/milestone/time terms and WAIT-only adversary. |
| Exploit hypothesis 2 | Farm after the cap. Mitigation: no positive signal exists; scorecard still counts every incident. |
| Exploit hypothesis 3 | Counter reset hides incidents. Mitigation: any in-episode rollback fails the run. |
| Adversarial tests | `duplicate-quality-cap`; `duplicate-after-cap`; `quality-counter-rollback`. |
| Telemetry key | `reward.penalty.duplicate_work`, `reward_quality_counters.duplicate_work_incidents`, `reward_quality_penalty_totals`. |
| Status | implemented-approved-v12; adversaries pass 2026-07-21 |

### `reward.penalty.communication`

| Field | Value |
|---|---|
| Definition | `-0.005` per monotonic increase in cumulative announced messages, capped at `-1.0`; routine structured messages cost zero. |
| Scale / range | `[-1,0]`. |
| State variables read | Structured cumulative `announced_messages` and prior charged count. |
| Intended behaviour | Discourage announcement spam while retaining structured communication authority. |
| Exploit hypothesis 1 | Suppress necessary warnings. Mitigation: small capped scale plus win/recovery/scorecard gates. |
| Exploit hypothesis 2 | Relabel announcements as routine. Mitigation: server-authoritative message priority; policy cannot set telemetry classification. |
| Exploit hypothesis 3 | Change boundary frequency to repeat charges. Mitigation: cumulative delta accounting. |
| Adversarial tests | `announcement-quality-cap`; `routine-message-zero`; `quality-chunk-size`. |
| Telemetry key | `reward.penalty.communication`, `reward_quality_counters.announced_messages`, `reward_quality_penalty_totals`. |
| Status | implemented-approved-v12; adversaries pass 2026-07-21 |

### `reward.penalty.team_abandonment`

| Field | Value |
|---|---|
| Definition | `-0.1` per structured non-forced ABANDON by any agent, capped at `-2.0`; forced wave/readiness/death/lease/human/terminal cleanup reasons are excluded. |
| Scale / range | `[-2,0]`. |
| State variables read | Structured task events, agent id, task id, reason code, charged count. |
| Intended behaviour | Reduce team-wide task churn that the learned selector induces through shared coordination. |
| Exploit hypothesis 1 | Hold permanently blocked tasks. Mitigation: unresolved time cost, lifecycle bounds, and win gate. |
| Exploit hypothesis 2 | Trigger excluded reasons intentionally. Mitigation: exclusions are authoritative safety/lifecycle events and remain visible in scorecards. |
| Exploit hypothesis 3 | Duplicate/replay one event. Mitigation: server event stream is authoritative and each delivered event is charged once; cap bounds damage. |
| Adversarial tests | `team-abandon-quality-cap`; `team-forced-abandon-zero`; `blocked-never-release`. |
| Telemetry key | `reward.penalty.team_abandonment`, `reward_quality_penalty_totals`, structured `task_events.reason_code`. |
| Status | implemented-approved-v12; adversaries pass 2026-07-21 |

## V15 coefficient override

ADR-0026 retains the exact reward-v2 components, authoritative inputs, caps,
and exploit mitigations above. Only two coefficients change for V15:

| Component | V12/V14 | V15 | V15 range |
|---|---:|---:|---:|
| `reward.penalty.team_idle_ticks` | `-0.0001` / idle agent tick | `-0.0003` / idle agent tick | `[-8.1,0]` |
| `reward.penalty.team_abandonment` | `-0.1` / non-forced event | `-0.25` / non-forced event | `[-2,0]` |

The exact V15 config is SHA-256 `c39c50d34c03e795...`. Its hashed adversary
report is `f278eb912699b817...`; all 37 cases pass, including early loss versus
full-horizon idle, cumulative chunk invariance, idle busywork, rollback, caps,
and forced-abandon exclusions. Status: implemented-approved-v15 pre-training,
2026-07-21.

## V16 explicit idle cap

ADR-0027 adds an optional `idle_agent_tick_cap` to reward v2. Its absence
preserves the V12-V15 coefficient-derived maximum exactly. V16 alone sets idle
cost to `-0.001` per idle agent tick and caps that component at `-5.0`; all
other V15 components and caps remain unchanged. Negative idle cost/cap values
fail the run.

The exact V16 config is SHA-256 `13bea4f89ac396f7...`. Its adversary report is
`ac35e476ae77fbd6...`; all 39 cases pass. New `idle-quality-cap` and
`idle-after-cap` cases prove exact saturation and zero post-cap charge, while
`idle-early-loss`, chunk invariance, busywork, rollback, and forced exclusions
remain green. Two exact training replicas reproduce, but reusable dev-v1
rejects the resulting candidate: permanent-greedy idle is 0.05618951 worse
(95% CI +0.03029619..+0.08042806) and recovery is uncertain against both
scorecards. The reward implementation remains adversary-approved; the V16
training intervention is rejected before dev-v12. Status:
implemented-approved reward / rejected candidate, 2026-07-21.

## V17 doubled capped idle slope

ADR-0028 changes V16's idle cost from `-0.001` to `-0.002` per team idle agent
tick while retaining the explicit `-5.0` maximum. At that slope, the 600-tick
idle adversary costs `-3.6`, so duplicate-work cap rises from `-1.0` to `-2.0`
to keep capped duplicate/abandon busywork at `-4.0`, strictly worse than honest
idle. V16's ordinary two duplicate incidents cost only `-0.1`, so the safety
cap is inactive in the observed regime. Communication, abandonment, terminal,
milestone, and unresolved-time terms are unchanged. V17 must pass the exact-
config adversary matrix before training. The exact V17 config is SHA-256
`71ffd120617ac860...`; adversary report `f716fc529c8aae8c...` passes all 39
cases, and the full 135-test Python suite passes. Status: implemented-approved-
v17 pre-training, 2026-07-21.

## Cross-component adversarial matrix

These CI-runnable cases are mandatory before changing any status to approved:

| Case | Script | Required assertion |
|---|---|---|
| Idle farming | Learned seat submits WAIT whenever legal; scripted seats unchanged. | Return and milestone count are lower than matched greedy; no positive idle/message/task-count signal exists. |
| Claim/abandon churn | Alternate attractive build claims with forced policy abandon. | Milestones pay once; abandonment cap is exact; churn cannot exceed honest completion return. |
| Duplicate bids | Learned seat deliberately selects the scripted seat's same candidate. | Claim loss gives no milestone/invalid reward; duplicate scorecard worsens and blocks promotion. |
| Message spam | Replay identical structured work with routine/announcement spam injected at telemetry boundary. | Every reward component is identical; communication has no positive reward input. |
| Unsafe help | Offer/accept without measurable fulfilment, then with a real delivery. | Both traces receive identical reward v1 (help is not rewarded); unsafe help cannot improve return and remains visible in scorecard/events. |
| Survival-only | Defend/WAIT while skipping economy/readiness work. | No line/readiness high-water reward; terminal rules and scorecard prevent promotion. |
| Build/rebuild loop | Repeatedly damage/rebuild an already credited plan. | High-water id pays exactly once and repair/build quantities pay zero. |
| Chunk manipulation | Replay one action trace using different requested step chunk sizes. | Per-component rewards and charged tick totals match exactly. |

The implementation emits `reward-adversaries.json` in the selected run
directory with 37 passing component and cross-component cases: the original
27 v1 cases plus all ten precommitted v2 cases. It includes the eight mandatory
matrix rows, cap and post-cap checks, counter rollback, chunk invariance, early
loss, busywork, mask corruption, readiness loss, unsafe telemetry, and farming
exclusions. Each case records its reward schema, action/state hashes,
structured events, coordination counters, every applicable component, total
return, and pass/fail reason. Reward totals alone are insufficient evidence.

V12 runs A and B use the approved v2 reward and reproduce bit-for-bit at
update 28. The selected policy wins 10/10 dev-v1 episodes but records mean idle
0.26628148, above the precommitted `<0.25` continuation threshold. This rejects
the candidate before dev-v8; it does not invalidate the accumulator audit.
