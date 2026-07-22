# ADR-0047: V36 collision-free build-line opening prior

**Status:** Accepted; V36 rejected at replica A

## Context

V35 is exactly reproducible and passes construction at 9/10, but reusable
preflight rejects permanent-greedy idle. Its fixed-seat trace isolates the
learned-seat source: mean idle ticks are `[390.1,8.1,380.0]`, and learned seat 0
selects the `+1.0`-biased `BUILD_SCHEMATIC` candidate at tick 0 in every episode.
Scripted seat 1 wins the same atomic claim, so seat 0 remains unassigned for
exactly 250 ticks in all ten reusable episodes.

The prior, not the candidate catalog or claim ordering, causes the collision.
When the prior is disabled on the rejected checkpoint, the unchanged model
chooses candidate index 1 (`BUILD_LINE`) at tick 0 on every seed and avoids the
universal initial idle interval. That retrospective off-contract policy wins
only 6/10, so it is diagnostic rather than promotion evidence and cannot be
used without retraining.

V34 already proved that waking learned seat 0 after all claim losses removes
accepted public staging. The next intervention must therefore change the
training-only opening choice while leaving runtime scheduling exact.

## Decision

1. V36 changes the existing tick-0 `initial_task_type_logit_bias_v1` task type
   from `BUILD_SCHEMATIC` to `BUILD_LINE`. Tick `0` and bias `+1.0` remain exact.
2. V36 holds V35's runtime, candidate generation, scripted partner policies,
   reward, teacher corpus/filter/caps, warmup and rehearsal schedules, PPO
   budget, architecture, optimizer values, RNG values, train/reusable roots,
   checkpoint selection, and held-out identity exact.
3. The deliberate `BUILD_LINE` prior preserves a non-WAIT structured opening
   while avoiding the scripted builder's demonstrated schematic claim. It does
   not mask either task or alter board ownership, communication, telemetry, or
   rewards.
4. V35 checkpoints remain diagnostic history only. V36 retrains from scratch;
   replica A must reach at least 9/10 reusable construction wins with mean idle
   below 0.25 before replica B.
5. Passing twins must reproduce checkpoint, frontier, model, replay, teacher
   schedules/reports, canonical full-run digest, and direct lineage before any
   scorecard or confirmation gate can advance.
6. Retire V35's unopened dev-v31. Freeze dev-v32 at globally disjoint roots
   `285001..285160`; it remains unopened until exact replicas and both reusable
   permanent-greedy and matched-greedy scorecards pass. Held-out-v4 stays sealed.
7. Training may begin only after config/seed governance, exact-config reward
   adversaries, Python tests, inherited V35 focused/public/Java gates, smoke,
   determinism, and negative replay pass from the committed V36 packet.

## Alternatives

- Keeping the schematic prior was rejected by the universal tick-0 collision.
- Removing all prior was rejected as the committed intervention because the
  rejected checkpoint falls to 6/10 off-contract and earlier construction work
  introduced a deliberate opening prior to avoid an initial WAIT failure.
- Waking learned seat 0 was rejected by V34's loss of required public staging.
- Masking schematic or changing claim ownership was rejected because both
  actions are valid and the atomic winner is correct.
- Changing rewards, teachers, budgets, or multiple logits was rejected because
  the trace identifies one exact structured decision.

## Consequences

- V36 is a training-policy intervention only. Server protocol, runtime hashes,
  scripted/public policies, and fixed-seat claim-loss semantics remain V35.
- The opening trajectory changes, so V35 model evidence cannot be promoted.
- Permanent baselines still require refresh before V36 preflight even though
  runtime is unchanged, preserving the standing self-contained evidence rule.

The V35 fixed-seat diagnostic is `runs/m8-selector-v35-seat0-idle.json`, SHA-256
`4ea36d7d149c5071070cda856b085da20f195b1bf246032e556ba607dbf428d0`.
The no-prior diagnostic is `runs/m8-selector-v35-seat0-no-prior.json`, SHA-256
`9ebfcc2a40bbb97b62fa710c29e769528a7cd490bd0c05f8d3ae51d40dba14c7`.
The immutable V36 config SHA-256 is
`36e3ca203db9a56e70c1b2948f768cc8e11f073eec04bf12430f1eebe7af9970`.
The dev-v32 seed document SHA-256 is
`8a9f1f3a7b55a52fab747a6ce289e92feb9471358f03475ca2d7ef0024c2e961`.
The precommit brings the Python suite to 161 passing tests. All 44 exact-config
reward adversaries pass; `runs/m8-selector-v36-precommit/reward-adversaries.json`
hashes to
`ccb5ede0e0efda855d125063371aa0121d2488bff629d218210f01f6a0e20400`.
No V36 model work, dev-v32 evidence, or held-out evidence preceded this
precommit.

From committed packet `f8b191c582`, the inherited fixed-seat wake check,
pinned Java build, and complete public candidate-policy gate pass. The public
gate survives 5/5 seeds with proactive staging beginning in all five. Smoke,
cross-process/reset/seed determinism, the 16,200-tick golden scripted replay,
and its deliberate-mismatch negative control also pass. V36 replica A is
therefore authorized under decision 4; dev-v32 and held-out-v4 remain unopened.

## Outcome

Replica A completed all 32 governed updates but no checkpoint passed the
precommitted 9/10 construction floor. Rank-best update 5 reached 7/10 reusable
wins, mean return `-0.17522`, mean core health `488.3`, and mean idle fraction
`0.05917146`; update 11 also reached 7/10 but ranked lower by return. The full
ineligible frontier is
`runs/m8-selector-v36-a/selector-v1-dev-frontier.json`, SHA-256
`c8659c770e5ec251e443f0aecc2b744716694152b738d09c6f57f53a0f0f7e16`.
Replica B was therefore prohibited and no permanent baseline, reusable
scorecard, dev-v32, or held-out-v4 evaluation ran.

The rank-best checkpoint's per-seat mean idle ticks are `[3.7,1.7,804.0]` and
its opening is collision-free, so construction rather than the idle threshold
is the failure. It loses seeds 2001, 2003, and 2004 near wave 3. The exact trace
is `runs/m8-selector-v36-seat0-idle.json`, SHA-256
`2a094fbd4999c04094dbca6528f0d2b811e46dcfee0492b78074684543d9e24c`.

Reusable-only diagnostics reject the remaining simple openings and cadence
escape. Applying a harvest prior to V36 update 5 wins 6/10 (SHA-256
`0b4c091c90d6c9b8e3c1bba73fd066ac5e6800d94365cc9992dff2830ec04793`).
Giving V35 update 8 a one-tick initial response also wins 6/10 (SHA-256
`6af6f19190d42cf7231a28dd4b10161d392c298f0e051d085abd5296c00b1f17`).
Forcing canonical WAIT preserves V35's 9/10 outcomes but reproduces its exact
`[390.1,8.1,380.0]` idle profile (SHA-256
`7903bd8eba902bb22f540ad56f98d9b3e5e2f67a1abf43b5f4bf58a74bc41d68`).
The accepted public policy also loses the same schematic claim at tick 0 on all
five seeds while retaining its required staging, so a server-side tick-0 wake
is not isolated from V34's public failure (public trace SHA-256
`8414b9be763add3228addd1ad42cb5f3680dcf8dbe91c87edcac3051fe4286b0`).

V36 is rejected, dev-v32 is retired unopened, held-out-v4 remains sealed, and
M8.5 remains unmet. A successor requires accepted-task timeline diagnosis; it
must not combine another opening guess with unrelated training changes.
