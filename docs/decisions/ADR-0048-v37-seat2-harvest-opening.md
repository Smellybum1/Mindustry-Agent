# ADR-0048: V37 fixed seat-2 harvest opening

**Status:** Accepted

## Context

V36's collision-free learned `BUILD_LINE` opening removed learned-seat idle but
failed construction: replica A completed all 32 updates and topped out at 7/10.
Accepted-task timelines show why the static opening substitution is not a safe
repair. Starting the line 250 ticks earlier advances the complete learned-seat
task sequence; on seeds 2001 and 2003 its harvest target finishes before wave 1,
the seat selects proactive defense with no enemies present, and dies during the
first wave. The governed V35 checkpoint instead remains on harvest through the
spawn boundary and wins both seeds.

V35's original tick-0 schematic path has a second, separable collision. Fixed
scripted seat 2 selects the same exclusive schematic as learned seat 0 and
scripted seat 1, loses to seat 1, and remains idle for about 250 ticks. V35's
mean idle ticks by fixed seat are `[390.1,8.1,380.0]`, versus permanent greedy
`[274.8,51.5,298.8]`. V34's accepted public trace records no seat-2 claim loss
on any of its five seeds, so a scripted-partner-only opening need not change the
public candidate-policy path.

Reusable-only interventions isolate the next coordinate. Giving seat 2 a
tick-0 `BUILD_LINE` selection wins only 6/10 and leaves learned seat 0 with mean
idle `1861.9`, because the line is unavailable when it replans. Giving seat 2
the valid tick-0 `HARVEST_RESOURCE` selection preserves BUILD_LINE for learned
seat 0 at tick 250 and produces 9/10 wins, mean core health `720.0`, and mean
idle ticks `[267.0,0.7,308.2]` with the unchanged V35 checkpoint. This is
diagnostic evidence only; the partner sequence changed and requires fresh
training.

## Decision

1. V37 is the exact V35 construction, not V36, plus one scripted-partner
   opening. Learned seat 0 retains the tick-0 `+1.0` `BUILD_SCHEMATIC` prior,
   fixed seat-1 `claim_lost` wake, runtime, reward, teachers, budgets, model,
   optimizer, RNGs, roots, and gates from V35.
2. Add config schema `fixed_seat_initial_task_type_v1` with exact tick `0`,
   fixed scripted `agent_id` 2, and task type `HARVEST_RESOURCE`. No other seat,
   tick, or task type is affected.
3. At that one boundary, resolve exactly one valid, mask-selectable candidate of
   the configured task type and replace only scripted seat 2's ordinary greedy
   selection with the corresponding explicit `SELECT_CANDIDATE_TASK` action.
   Missing, duplicate, invalid, or masked matches fail the run before the step;
   there is no fallback action.
4. Apply the same partner opening in teacher-controlled collection, PPO
   collection, reusable evaluation, checkpoint replay, matched-greedy and
   matched-random controls, confirmation, and final evaluation. Permanent
   public random/greedy baselines remain their frozen policies and receive no
   V37 override.
5. The server receives an ordinary structured candidate selection. V37 adds no
   protocol field, server special case, action-mask change, board mutation,
   synthetic event, reward component, or engine behavior.
6. V35/V36 checkpoints remain diagnostic history only. V37 retrains from
   scratch; replica A must reach at least 9/10 reusable construction wins with
   mean idle below 0.25 before replica B.
7. Passing twins must reproduce checkpoint, frontier, model, replay, teacher
   schedules/reports, canonical full-run digest, and direct lineage before any
   scorecard or confirmation gate can advance.
8. Retire V36's unopened dev-v32. Freeze dev-v33 at globally disjoint roots
   `286001..286160`; it remains unopened until exact replicas and both reusable
   permanent-greedy and matched-greedy scorecards pass. Held-out-v4 stays sealed.
9. Training may begin only after config/seed governance, exact-config reward
   adversaries, Python tests, focused partner-opening tests, the inherited
   V35 focused/public/Java gates, smoke, determinism, and negative replay pass
   from the committed V37 implementation packet.

## Alternatives

- Keeping V36's learned build-line opening was rejected by its 7/10 replica-A
  frontier.
- A learned harvest opening and a one-tick learned replan each won only 6/10.
- Fixed seat-2 build-line opening won only 6/10 and greatly increased learned
  idle.
- Waking learned seat 0 or all claim losers was rejected by V34's public
  staging failure; a tick-0 response also changed V35 to 6/10 off-contract.
- Converting a failed claim into implicit help was rejected because the current
  helper contract is explicitly request/offer/accept and does not provide an
  `ASSIST_BUILD` skill. Adding implicit assignment would combine protocol,
  lifecycle, skill, and metric changes without isolated evidence.

## Consequences

- V37 changes the deployed scripted teammate sequence, so both exact training
  replicas and matched controls must use the opening and permanent baselines
  must be refreshed before preflight.
- Public candidate policies and the V35 server runtime remain byte-exact.
- The fixed partner action is structured, deterministic, visible in archived
  action traces, and covered by the same state hashing and external stepping.

The reusable V35/V36 accepted-task timelines hash to
`a88cbfcf02c1b0f978157ad86e71170a4dc276be2a25b09a50f29712b7fc4983` and
`9801c4068c927a0cbea3e9800b033a3693ea05ad09b8d6ad7cb86eecaca9469b`.
The fixed seat-2 harvest diagnostic is
`runs/m8-selector-v37-v35-seat2-harvest.json`, SHA-256
`6aab097127bf7104e5cd8d3a68bb8650a079bcbcfa0b5b01fd1f1fb0a171ef14`.
The immutable V37 config SHA-256 is
`78bb87f459afc926f68068aa7f6f5881b3e1fa9f4d7026dca2fb2bb216acbb32`.
The dev-v33 seed document SHA-256 is
`804571d3cda373e8e11ccbd3b13c24ca6f1135adf8f98b3789b77a4153303ddf`.
All 44 exact-config reward adversaries pass; the report at
`runs/m8-selector-v37-precommit/reward-adversaries.json` hashes to
`6df5481af4652c58de05442b3ccc72e0a603a573ed228f8a6006d7a217791028`.
The precommit brings the complete Python suite to 162 passing tests.
No V37 implementation, teacher collection, model work, dev-v33 evidence, or
held-out evidence preceded this precommit.

The subsequent implementation applies the opening through every governed
rollout path, archives the full structured action, and fails before stepping on
candidate drift. Focused positive, legacy-identity, and fail-closed coverage
bring the complete Python suite to 165 passing tests. The inherited live/Java/
determinism gates and all V37 model work remained pending at that implementation
commit.

From implementation commit `0c4a09659f`, the pinned Java build/tests, focused
seat-1 wake check, complete 5/5 public gate with all five proactive-staging
starts, smoke, cross-process/reset/seed determinism, 664-checkpoint/16,200-tick
golden replay, negative replay, and all 44 exact-config reward adversaries pass.
The adversary report reproduces SHA-256
`6df5481af4652c58de05442b3ccc72e0a603a573ed228f8a6006d7a217791028`.
Replica A is authorized; dev-v33 and held-out-v4 remain unopened.

Replica A selects update 16 at 9/10 reusable wins, mean return `4.18676`, mean
core health `805.5`, and mean idle `0.05108287`. Its checkpoint/model/replay/
full-run digests are `a9a55110fe2266b8ba0c34053e79eb99ef14a06c9b12727d4810cc7513df8297`,
`21b665232664f79e7009a0f2274655cb00b7d607765efbba27013c96e642207b`,
`9b67d5d468f86a55bf07e015756a0c06259a40c85bd411f64e2d45b489696526`,
and `614c071b7f3003b016e332c4540787969d3b468f0804acfbc8db1fa443cd7163`.
The frontier hashes to
`93e736d9969fd51809f91091b2a45100ea5ccf56331439533892d8a7a6e098f9`;
fresh checkpoint replays are bit-exact. Replica B is authorized. Dev-v33 and
held-out-v4 remain unopened.
