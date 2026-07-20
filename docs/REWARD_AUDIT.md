# Reward audit

**Status: no rewards implemented yet.** This document is the standing audit for
every reward component. Per brief §17.5/§28, no reward component may influence
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

Adversarial tests for each row land with the reward implementation (roadmap M7).
