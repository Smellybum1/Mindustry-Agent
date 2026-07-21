# Handoff

Codex-ready handoff per brief §27. Kept truthful; `TODO` marks pending info.

## Project state

- **What currently works** (M0–M6, M7.1–M7.6, and M8.1–M8.4 complete, verified
  2026-07-21): the
  fixed-step headless `rl-server` (reset/step/hash over loopback JSON, smoke +
  determinism + 1000-reset stress all green), the `agent-core` coordination
  board, deterministic candidate catalog, **and the M3/M4 `agentcore.skill` FSM
  layer** (108 JUnit tests), agent
  entities + skills in the exact engine (`RlAgentRegistry`, `SkillController`,
  `ActionDecoder`; agents mine copper and deliver it to the core with an exact
  balance ledger), the Python env/process layer (supervisor pool with
  crash-replacement, PettingZoo-shaped facade, vector collector; 92 pytest
  green), benchmarks recorded in `docs/BENCHMARKS.md`, and — new — the **full
  `bootstrap-defense-v0` world loaded from `scenario.json`** (48×48, ore patches,
  east spawn, 250-copper loadout, deterministic 3-wave dagger schedule at
  2700/4500/6300 with moving enemies, win/loss/truncate termination). Enemy pathing
  is deterministic via the one sanctioned upstream patch, `Pathfinder.syncUpdate()`
  (`docs/UPSTREAM_PATCHES.md`). The **seed lever is now real**: different seeds
  diverge once enemies spawn, same seed stays identical. M4.1 also neutralizes
  the tile-change `Time.millis()` refresh gate in thread-less mode; a wall placed
  after wave 1 produces identical re-pathing hashes across fresh JVMs. M4.2 adds
  legal `BUILD`: real `BuildPlan` execution, exact core resource consumption,
  and typed failure telemetry. M4.3 adds data-backed `SCHEMATIC`: the ordered
  `east_duo_v1` build completes through those legal plans for exactly 100 copper.
  M4.4 legally supplies both Duos for a balanced 30-copper core delta and 30 ammo
  units each; the full trace matches 79 boundaries. M4.5 rebuilds an engine-recorded
  wave-destroyed wall for an exact second six-copper charge. M4.6 adds deterministic
  alpha defense, agent-attributed damage events, and plan-cancelling core retreat
  (95 JUnit tests total); combat is present in the 79-boundary replay. M4.7 closes
  plan/progress/turret observations and hashes ordered build plans, broken queues,
  and turret ammo. M4.8 proves the one-agent defended wave-1 path with an untouched
  core and retains the matched omitted-defense loss regression.
  M5.1 parses the scored scenario objectives into a bounded, byte-stable per-agent
  candidate catalog; engine-backed utility features and aligned capability/range
  masks are live in reset/step observations. Smoke covers build/supply/defend
  candidate transitions.
  M5.2 hosts a reset-safe board on the sim thread, accepts typed task actions,
  maps claimed scenario tasks to legal skills, publishes bounded snapshots and
  drained structured events, and hashes non-empty board state. Its three-agent
  live check repeats byte-identically across two fresh JVMs through tick 280.
  M5.3 adds dependency-free greedy and fixed-role task policies plus deterministic
  helper coordination. Its live check records distinct miner/builder work, a
  real resources-short block, an accepted 20-copper helper contract fulfilled by
  21 legally mined/delivered copper, and one schematic completion; the full trace
  repeats byte-identically across fresh JVMs through tick 912.
  M5.4 acquires exact schematic-footprint and copper reservations before skill
  start, hashes and publishes them, cancels interrupted build queues, and releases
  on every lifecycle exit. Its live overlap trace gives the higher-utility second
  bidder the only build plan, emits `reservation_overlap` for the loser, proves
  abandon/reclaim/completion and supply budgets, and repeats byte-identically
  through tick 280.
  M5.5 adds a deterministic, validation-only failed-agent hook. The live chaos
  run freezes agent 0 mid-build, expires its lease and reservations at tick 627,
  lets agent 1 reclaim/complete at tick 893, reaches a normal terminal outcome,
  and repeats byte-identically through tick 3600.
  M5.6 renders human-readable announcements exclusively from structured events,
  exposes cumulative duplicate/completion/abandonment/idle/message metrics, and
  keeps routine traffic silent. Its live helper episode emits 112 structured
  events but only four announcements, suppresses the same-tick accept line, and
  repeats the entire event/metric transcript byte-identically across fresh JVMs.
  M6.1 adds the real two-drill copper line and a three-agent expert that wins
  all three waves on the five-seed set. Final core health is
  848/884/1001/920/983; the legal insufficient-copper variant emits a structured
  block, replans through mining, and also wins.
  M6.2 writes pinned JSONL episode summaries and aggregates the same five seeds:
  5/5 wins, minimum/mean core health 848/927.2, with full figures in BENCHMARKS.
  M6.3 checks in a complete two-episode/16,200-tick action+coordination golden;
  after the deliberate M7.1 regeneration, fresh-JVM replay matches 672
  checkpoints and the negative mutation test flips one.
  M6.4 builds a loadable stock-server plugin. Its isolated real-server probe
  legally completes the shared copper-line/east-Duo opening, expands it to 20
  fortifications/four supplied Duos, matches both build orders, enters reserve
  mining, and verifies pause/resume/emergency-stop without opening a port. The
  separate no-port survival probe adds two Duos/seven walls after waves 1–2,
  supplies all six/eight turrets, clears three waves, and reaches tick 8100 with
  1091 core health. A stock v159.7 client observed the full run and confirmed
  `/agents stop` halted all three active tasks. M7.1 resolves the independent
  review's mechanical findings: scenario-owned coordinates/timing feed both
  demos, candidate overflow is utility-ranked with a DEFEND reservation,
  transport episode IDs are deterministic, duplicated skill constants and dead
  demo branches are removed, supply stock telemetry has explicit consumers, and
  the upstream patch catalogue is exact. The current no-port survival probe
  reaches tick 8100 with 1100 core health after dynamic 9-block/2-turret
  expansions following waves 1 and 2. M7.2 replaces the two scripted policy
  implementations with one engine-neutral `ExpertCoordinationDriver` and
  scenario-derived plan. The fixed-step adapter and plugin now share staging,
  lifecycle, wave response, maintenance, expansion, and reserve-mining
  decisions; the plugin retains only real-time/engine/IO adaptation and
  controls. The recorded parity probe covers 366 decisions/89 selections and
  all six task types, while the two live openings both emit 33 selections with
  digest `f335f6b950ac1b58857ca84b40e7151f966d5d53408fd0e643fbc54a39671385`.
  The post-extraction survival run clears waves at ticks 3102/4865/6655 and
  reaches tick 8100 with 1091/1100 core health. M7.3 promotes the public
  candidate/utility seam to the primary expert: `GreedyUtilityPolicy` submits
  normal task actions over live candidates/masks, the former `ExpertEpisode`
  macro is frozen for the ladder, and structured resource blocks now trigger
  abandon/regenerate/reselection. Scenario-derived fortification/expansion
  candidates and the shared enriched plan produce 5/5 wins at tick 8100
  (minimum/mean core health 1082/1096.4); the legal pre-spend variant wins with
  209 health and seven replans. Genuine wave-clear/message/loss/health
  variation follows seeded enemy spread. `docs/CANDIDATE_GAPS.md` records the
  remaining rigidity. Updated shared fixed-step/plugin openings still match:
  43 selections and digest
  `157134ba5a4e3f39ccc3cf237093481dc8474b7edd1d20e16b274ec338b1a6c2`.
  The final stock-paced no-port probe reaches the six-turret opening at tick
  1814, completes eight-/ten-turret expansions, clears waves at ticks
  3015/4799/6606, and ends tick 8100 with 1100/1100 core health. Recurring task
  identity intentionally changes coordination hashes; the separately
  regenerated golden retains two wins, 16,200 ticks, and 672 checkpoints, with
  exact replay and a passing negative mutation check.
  M7.4 replaces the remaining fixed planning constants with authoritative
  economy/defense/spatial facts. The real line predicate requires directed
  drill-to-core connectivity and a full 600-tick window at 0.6 copper/s; wave
  HP/DPS and native Duo values derive readiness, ammo target, and defend lead.
  Opt-in event-driven steps wake on task/economy/wave/core-damage transitions,
  while default stepping remains exact. Typed BLOCKED replans are bounded and
  recent assignments feed switching cost. The delayed-loadout adaptive probe
  is won at tick 8100 (line 1794, defense-ready 1382), while the frozen macro
  cannot complete its opening and loses. Across fixed+probe, adaptive mean idle
  fraction is 0.125 vs 0.878 and censored defense-ready tick is 817 vs 5251.
  `make adaptive-planning-check`, fixed 5/5 evaluation, and the legal
  resource-pressure replan win are green. The M7.4 golden retains two wins and
  16,200 ticks across 670 checkpoints, with exact replay and a passing negative
  mutation. All REVIEW_M6 findings are resolved.
  M7.5 adds `bootstrap-defense-v1` / scenario version 2: bounded independently
  seeded ore positions, loadout, wave timing/composition, and an optional upper
  lane. Resolved contracts are validated, published, and hashed. ADR-0012
  freezes disjoint train/dev/held-out sets and development tools refuse held-out
  execution. Repeated/fresh-JVM reset and idle-through-wave traces match per
  seed; v2 waves receive deterministic disjoint entity-ID ranges so prior
  episode allocation history cannot leak through native spawning. Adaptive-v1 wins
  8/10 on the frozen dev set; seeds 2005/2007 expose the retained fixed-anchor
  upper-lane fortification gap. No held-out episode has been run.
  M7.6 adds the permanent five-policy evaluation ladder, a versioned fixed seed
  contract, deterministic 10,000-resample bootstrap intervals, and a per-episode
  teammate scorecard derived from structured events and existing metrics. The
  certified one-JVM Windows path writes byte-repeatable 65-episode JSONL plus
  aggregates in 39.6 seconds after the same per-seed idle trace used by M7.5.
  Adaptive-v1 is 5/5 fixed and 8/10 dev; pure
  greedy is 5/5 fixed and 9/10 dev. These are descriptive only: ADR-0012 now
  requires strict held-out win-rate CI separation, and held-out remains sealed.
  M8.1 is design-only and complete: `docs/M8_DESIGN.md` pins the one-seat
  selector tensors/masks/model/cadence/manifests/promotion protocol, while
  `docs/REWARD_AUDIT.md` drafts five hard-gated components with 15 exploit
  hypotheses and eight cross-component adversaries. M8.2 accepts ADR-0011 and
  pins the RL-only Linux CPU runtime to NumPy 2.4.2, PettingZoo 1.26.1, and
  PyTorch 2.12.1+cpu. Its 15-package hashed lock regenerates byte-identically;
  the WSL2 acceptance gate passed 33 `python -S` core tests and a temporary
  locked import/device probe on CPython 3.12.3. No reward or learned policy is
  implemented. M8.3 carries decision-event stepping through the supervised
  vector collector and adds a training-only shadow-inference gate. Its
  certified WSL2 result is 122.4×/212.7×/293.5× aggregate real-time at 1/2/4
  JVMs, with identical winning hashes. The same command passed 10,000 resets
  with zero drift, 338.3 MiB peak RSS, and no orphan.
- **M8.4 evidence**: the exact one-seat selector seam is implemented with
  framework-neutral 8x37/56 features, five separately audited reward
  components, masked feed-forward PPO, chained checkpoints,
  training/replay JSONL, and complete run manifests. All 27 reward adversaries
  pass. Two independent pinned runs match checkpoint `0b2bd8ac904a9e21...`,
  complete replay `87ba273f376c47de...`, full-run digest
  `56cc7b54bc9b01b5...`, and dev action/state aggregate
  `52aecddf4c96bab6...`. The selected checkpoint is 0/10 on dev and is not
  promotable; held-out remains sealed. Current final capacity is 375.1x at four
  JVMs and 10,000 resets with zero drift/no leak/no orphan. The golden is 664
  checkpoints over 16,200 ticks and two wins.
- **M8.5 final**: base and auxiliary parent pairs reproduce exactly; two 75/25
  constructions match checkpoint `4fdad5cbd8476a8f...` and lineage
  `995cb7d71fa21e4e...`. Frozen dev preflight passed at 9/10. The exclusive
  held-out final then completed once and returned `not_promoted`: learned 4/10
  `[0.1,0.7]`, random-valid 6/10 `[0.3,0.9]`, greedy-utility 6/10 `[0.3,0.9]`,
  matched greedy 1/10 `[0.0,0.3]`. Permanent CI separation failed, and idle /
  abandonment regressed versus permanent greedy. The attempt marker forbids a
  rerun; held-out outcomes must not be used for policy revision.
- **What is stubbed**: the M10 human goal/override/study surface remains future
  work. M8.5 evaluation machinery is real, but the candidate did not promote.
- **What remains for M6**: nothing. The closure matrix and 15-item audit are
  recorded, and the closure commit is tagged `milestone-6`.
- **Post-failure governance**: ADR-0013 freezes the 40-root, globally disjoint
  `bootstrap-defense-v1-held-out-v2` contract before any successor model work.
  Development loaders refuse it and only one exclusive future final is
  permitted. `m8-selector-v3-diverse` tested 64 train roots at the unchanged
  512-episode budget and reproduced exactly, but selected update 1 at only 3/10
  dev wins (`e9e1ee37fbfef6ee...`). It stops before preflight and v2 remains
  unopened. M9.1 remains blocked by its explicit promotion prerequisite.
- **Teacher-regularized successor**: v4 reproduced exactly and improved the
  diverse-root dev result to 5/10, but remains ineligible. V5 changes only the
  teacher coefficient from 0.05 to 0.10 and is precommitted as the final test;
  it reproduced exactly but fell to 3/10, closing that line. V2 is unopened.
- **Long diverse successor**: v6 is precommitted as auxiliary-free v3 with only
  cycles raised from 8 to 32 (2,048 episodes/32 updates), restoring 32 visits
  per root. Two pinned runs reproduce exactly and select update 31 at 9/10 dev
  wins (`0dfdcf9b5273ae3f...`, full-run `54476ef63e31e06d...`). Direct-checkpoint
  lineage is implemented; full dev scorecard preflight is next. V2 is unopened.
- **V6 dev preflight**: all four win-rate comparisons pass, but idle, recovery,
  and abandonment intervals are uncertain on ten dev-v1 pairs. ADR-0014 freezes
  a one-way 40-root dev-v2 confirmation with an exclusive attempt and refreshed
  permanent baselines. It must pass before held-out-v2 can be opened.
- **V6 confirmation result**: the exclusive marker was created, then the run
  aborted before result files on a matched-control catalog-WAIT indexing bug.
  ADR-0014 consumes any started attempt, so V6 is rejected and dev-v2 must not
  be rerun. The bug is fixed/regression-tested. Held-out-v2 remains unopened.
- **V7 precommit**: ADR-0015 freezes a 90/10 V6 update-31 / V4 update-5 blend,
  with explicit cross-commit parent validation. Dev-v3 is a new disjoint
  40-root, one-way confirmation set available only after V7 passes dev-v1. Its
  result follows; dev-v2 remains consumed and held-out-v2 sealed.
- **V7 result**: exact constructions; dev-v3 finishes 35/40 versus permanent
  greedy 30/40. Recovery, abandonment, announcements, and duplicates pass;
  idle remains favorable but uncertain. V7 is rejected and dev-v3 consumed.
- **V8 precommit**: ADR-0016 freezes a single `-0.25` WAIT-logit bias adjustment
  to V7, with masks/reward/lifecycle unchanged. Dev-v4 is a new disjoint
  40-root, one-way confirmation set. Its result follows.
- **V8 final**: exact checkpoint `1f3c4525fb5fd10d...`; dev-v4 fully eligible
  at 37/40. Held-out-v2 completes once at V8 36/40, random 19/40, greedy 23/40,
  matched greedy 5/40. Win gates pass, but permanent-greedy idle/abandonment
  regress and other scorecards remain uncertain. V8 is not promoted; v2 is
  consumed and individual outcomes must not guide future policy changes.
- **Post-V8 governance**: ADR-0017 freezes 80 disjoint held-out-v3 roots before
  further model work. A successor must name v3 and use a new confirmation path.
- **V9 precommit**: ADR-0018 freezes one additional `-0.25` WAIT-bias child of
  V8 (`-0.50` total from V7), with all other behavior fixed. It names
  held-out-v3. Dev-v5 is a new disjoint 80-root, one-way confirmation set. V9
  constructs exactly at checkpoint `3ae49108c913b078...`, model state
  `a62210ed1716cba6...`, and lineage `c329bfc096122a13...`.
- **V9 result**: after beating every dev-v1 win comparator, V9 completed
  dev-v5 at 65/80 and qualified under the then-implemented matched-only
  scorecard. Held-out-v3 then completed once: V9 70/80, random 33/80, greedy
  49/80, matched greedy 5/80. Every win gate passes, but permanent-greedy
  announcements/idle/abandonment regress, permanent recovery is uncertain,
  and matched idle is uncertain. V9 is not promoted; v3 is consumed.
- **Post-V9 governance**: ADR-0019 fixes the preflight/final mismatch by
  requiring paired scorecards against both seed-level permanent greedy and
  matched greedy, hashing the permanent record source, and revalidating it at
  final time. It freezes 160 globally disjoint held-out-v4 roots before future
  candidate work; development tools refuse v4 and only one final is allowed.
- **V10 precommit**: ADR-0020 selects one all-boundary teacher-distillation
  hypothesis from dev evidence. V10 uses V6's 64-root/32-cycle recipe and adds
  coefficient `1.0` adaptive-v1 cross-entropy on every unforced transition;
  reward/inference are unchanged. Its config names held-out-v4. A new disjoint
  160-root dev-v6 set is frozen for one corrected dual-scorecard confirmation.
  Two pinned runs reproduce exactly but select update 6 at only 1/10 dev wins
  (`a20f44d6ec093076...`; full run `787b5d4bd6548eea...`). V10 is rejected
  before dev-v6; dev-v6 and held-out-v4 remain unopened.
- **V11 precommit**: ADR-0021 freezes a 90/10 V6 update-31 / V10 update-6
  blend using V7's established weight. It names held-out-v4 and must reach
  9/10 dev-v1. Dev-v6 is retired unopened; dev-v7 is a new disjoint 160-root
  one-way confirmation set. Exact constructions produce checkpoint
  `0a8fa8b4ba98581d...` and lineage `845282326c58308c...`; dev-v1 is 9/10 and
  beats all win comparators. Scorecards are still uncertain/regressing, so V11
  is authorized for dev-v7 only. Dev-v7 then completes once at V11 137/160,
  random 69/160, greedy 100/160, matched random 19/160, matched greedy 12/160.
  Win and matched scorecard gates pass; permanent announcements, idle,
  recovery, and abandonment fail. V11 is rejected and dev-v7 consumed.
- **V12 precommit**: ADR-0022 freezes reward v2 as v1 plus capped negative-only
  idle, duplicate, announcement, and non-forced team-abandonment components.
  Production accounting and trace telemetry are implemented; all 37 reward
  adversaries and the 121-test Python suite pass, authorizing training. V12
  uses V6's long recipe and names held-out-v4. Two exact 2,048-episode runs
  reproduce at update 28 with 10/10 dev-v1 wins, checkpoint
  `a10752ccf12b513c...`, model state `64846932b7e2d948...`, replay
  `6f99df0a3243de3f...`, and full-run digest `6d8912cbc00766c6...`.
  Mean idle is 0.26628148, missing the precommitted `<0.25` bar, so V12 is
  rejected. Dev-v8 is unopened and held-out-v4 remains sealed.
- **V13 precommit**: ADR-0023 keeps V12's exact training/reward construction
  but gates checkpoint selection at 9/10 dev-v1 wins and mean idle `<0.25`
  before applying the existing ranking. Two fresh exact runs are required;
  V12 update 24 is not retroactively promoted. Dev-v8 is retired unopened and
  dev-v9 is frozen at disjoint roots `91001..91160` for one exclusive
  dual-scorecard confirmation. The selector and version-compatible manifest
  evidence are implemented. Two exact 2,048-episode runs select eligible update
  24 at 10/10 wins and idle 0.24980951. Checkpoint `ff5c21bc6644d903...`,
  model state `6695f8ffb690f635...`, replay `c556d3ec24f06c8a...`, full-run
  digest `842ac034e91e84ae...`, and lineage `8aff4629be3090b3...` reproduce.
  Dev-v9 then completes once at V13 152/160, permanent random 62/160,
  permanent greedy 92/160, matched random 13/160, and matched greedy 15/160.
  All win and matched scorecard gates pass; permanent announcements, idle,
  recovery, and abandonment fail. V13 is rejected, dev-v9 is consumed, and
  held-out-v4 remains sealed. Records/aggregate/report hashes are
  `b4caeaba900f047a...`, `46f940a8361b4dad...`, and `a4dd2ecad7c485de...`.
- **Permitted successor evidence**: reusable dev-v1 traces attribute all 23
  non-forced V13 abandons to learned seat 0 resource-short replans; 21 are
  saturated-resource turret-supply selections. Selected-candidate diagnostics
  now expose bounded resource/urgency/switching evidence without changing the
  replay action/state digest. Do not inspect dev-v9 episode records for tuning.
- **Scorecard v2 precommit**: ADR-0024 aligns future abandonment judgment with
  reward v2 by excluding forced wave/readiness/death/lease/human/terminal/
  cleanup reasons from the rate while retaining separate counters. It also
  adds per-agent idle telemetry. Schema v2 and the server counters are
  implemented; 128 Python tests, build, smoke, determinism, and live metric
  reconciliation pass. No consumed result is rerun or changed.
- **Immediate-abandon boundary fix**: reusable dev-v1 traces showed that 30
  learned-seat abandon actions consumed 23,371 ticks because `RlServer` sampled
  the coordination decision revision after applying actions. A successful
  `ABANDON` now marks `task_terminal`; pre-action revision sampling makes
  stop-on-event advance exactly one fixed tick and return for immediate
  replanning. The reservation check covers the live path. The regenerated
  golden remains two wins/16,200 ticks/664 checkpoints and two recordings match
  at SHA-256 `f386e056e3b21cbf...`; only decision-revision-dependent state hashes
  changed. Python tests, build, smoke, determinism, and negative replay pass.
- **Corrected-runtime V13 probe**: rejected update 24 remains 10/10 on reusable
  dev-v1 and mean idle improves from 0.24980951 to 0.20217810. Every learned
  abandonment now advances one tick, but immediate replanning exposes 105
  non-forced resource-short abandons, so dual scorecards remain ineligible.
  Records/aggregate/preflight hashes are `373d47db23646daa...`,
  `c03ce068da2a1203...`, and `5b161a1baee74d5e...`. V13 stays rejected.
- **V14 precommit**: ADR-0025 requires a from-scratch retrain of V13's exact
  learning recipe under runtime contract
  `successful_abandon_task_terminal_one_tick_v1`. Two 2,048-episode replicas
  must reproduce. Reusable dev-v1 must reach 9/10 with idle `<0.25` and pass
  the corrected permanent-plus-matched dual scorecards before dev-v10 can be
  consumed. Dev-v10 is frozen at disjoint roots `101001..101160`; held-out-v4
  remains sealed. The full 129-test Python suite passes.
- **V14 result**: two pinned 2,048-episode runs reproduce exactly at update 32,
  10/10 reusable dev-v1 wins, idle 0.15861366, checkpoint `d403044cc5adec74...`,
  model state `d2d60661ad2a5b90...`, replay `c6647a44b09ce7eb...`, full-run
  digest `ecd8776cda1430d5...`, and lineage `52f6138246423c54...`. Fresh
  scorecard-v2 permanent baselines are used. The corrected dev-v1 preflight
  rejects V14 before confirmation: permanent-greedy idle is definitively worse
  by 0.11430187 and non-forced abandonment by 0.04469033; recovery is
  uncertain. Dev-v10 is unopened, held-out-v4 is sealed, and M8.5 remains
  unmet.
- **V15 precommit**: reusable dev-v1 shows 59 learned WAIT decisions consume
  34,993/81,000 ticks, and V14 update 32 is already the lowest-idle 10/10
  frontier point. ADR-0026 keeps the V14 construction exact except idle cost
  `0.0001 -> 0.0003` and non-forced team-abandon cost `0.1 -> 0.25`, with the
  abandonment cap unchanged. The adversary runner loads/hashes the candidate
  config; all 37 exact-config cases and 131 Python tests pass. Dev-v10 is
  retired unopened; dev-v11 is frozen at disjoint roots `111001..111160`.
  Held-out-v4 remains sealed.
- **V15 result**: two pinned 2,048-episode runs reproduce exactly at update 25,
  10/10 reusable dev-v1 wins, idle 0.21873675, checkpoint
  `a328550d36448897...`, model state `823336f58798a487...`, replay
  `32735e17026b8903...`, full-run digest `22792939f896fbd0...`, and lineage
  `0db57e0879cca7df...`. Abandonment improves to 0.01673964, but the corrected
  preflight rejects V15 because permanent-greedy idle is definitively worse;
  recovery and matched idle are uncertain. Dev-v11 is unopened, held-out-v4 is
  sealed, and M8.5 remains unmet.
- **V18 precommit**: V17 idle/recovery gaps have only about -0.08 paired-root
  correlation, so ADR-0029 targets all remaining scorecards. V18 uses idle cost
  `0.004` capped at `5.0`, announcement cost `0.01` capped at `1.0`, and a new
  backward-compatible recovery-delay penalty `0.001` per tick capped at `3.0`.
  Duplicate cap `4.0` preserves busywork ordering. Exact structured/game events
  mirror the governed recovery definition; pending roles continue charging, so
  non-recovery cannot evade cost. All 43 adversaries and 138 Python tests pass.
  Dev-v13 is retired unopened; dev-v14 is frozen at disjoint roots
  `141001..141160`. Held-out-v4 remains sealed.
- **V16 rejected on reusable dev-v1**: two pinned replicas reproduce update 23
  at 9/10 construction wins and mean idle 0.10050130. Checkpoint
  `6db48a03427edfa2...`, model state `91c3364b793d7091...`, replay
  `4862b1a8a319d8bf...`, full run `65bebd16464f95a1...`, and lineage
  `a172fad58f842f6e...` reproduce. Non-forced abandonment is zero and matched
  idle improves by 0.12929577, but permanent-greedy idle still regresses by
  0.05618951 (95% CI +0.03029619..+0.08042806); recovery is uncertain against
  both scorecards. Dev-v12 is unopened, held-out-v4 is sealed, and M8.5 remains
  unmet.
- **V17 rejected on reusable dev-v1**: two pinned replicas reproduce update 17
  at 9/10 construction wins and mean idle 0.08594077. Checkpoint
  `6dbde34e0b745b55...`, model state `701bff0e24bfae60...`, replay
  `ab01623eda4d40ea...`, full run `8b210937805c23f3...`, and lineage
  `233282b7fc536cb3...` reproduce. Permanent-greedy idle remains 0.04162898
  worse (95% CI +0.01733907..+0.06734018); permanent announcements and both
  recovery comparisons are uncertain. Non-forced abandonment is zero and
  matched idle improves by 0.14385630. Dev-v13 is unopened, held-out-v4 is
  sealed, and M8.5 remains unmet.
- **V18 rejected on reusable dev-v1**: two pinned replicas reproduce update 22
  at 9/10 construction wins and mean idle 0.10978972. Checkpoint
  `0984700a681bfdc5...`, model state `2fd25b37851c1d97...`, replay
  `d098fba29b3de64f...`, full run `127410b515f6917e...`, and lineage
  `b226742761e58852...` reproduce. Permanent-greedy idle is 0.06547793 worse
  (95% CI +0.03188818..+0.09708444); recovery remains uncertain against
  permanent greedy (-6.85 ticks, 95% CI -93.62..+114.80) and matched greedy
  (-42.52 ticks, 95% CI -214.79..+118.93). Announcements, duplicate work, and
  abandonment non-regress, while matched idle improves by 0.12000735. Dev-v14
  is unopened, held-out-v4 is sealed, and M8.5 remains unmet.
- **V19 precommit**: reusable per-agent diagnostics show V18 reaches its idle
  cap in 8/10 dev episodes and that downstream seat 1 dominates excess idle
  (`0.174262` versus permanent greedy `0.031523`). ADR-0030 restores idle cost
  `0.002`, raises its cap to `8.0` (4,000 differentiating idle-agent ticks),
  and raises duplicate cap to `7.0` so capped duplicate plus abandonment churn
  remains worse than capped honest idle. All other V18 fields remain exact.
  All 44 exact adversaries, 140 Python tests, smoke, and determinism pass.
  Config hash is `4d9911a8f6dda1bb...`; adversary report is
  `23262f5332cc9f52...`. Dev-v14 is retired unopened; dev-v15 is frozen at
  disjoint roots `151001..151160`; held-out-v4 remains sealed.
- **V19 rejected on reusable dev-v1**: two pinned replicas reproduce update 24
  at 9/10 construction wins and mean idle 0.09911830. Checkpoint
  `1a9376a331b3aadc...`, model state `510e07d964c84de0...`, replay
  `75bf5fb9cc34d5a6...`, full run `4d15c3a728f33d4c...`, and lineage
  `121a7400b241ce77...` reproduce. Idle-cap hits fall from V18's 8/10 selected
  dev episodes to 2/10 and the permanent-idle gap improves to 0.05480651, but
  remains definitively worse (95% CI +0.02786525..+0.08510262). Recovery stays
  uncertain against both scorecards and non-forced abandonment regresses by
  0.00131579. Dev-v15 is unopened, held-out-v4 is sealed, and M8.5 remains
  unmet. Preflight report SHA-256 is `cc7bfa34d06b4007...`.
- **V20 precommit**: ADR-0031 closes the cap line. Reusable all-adaptive wins
  9/10 with permanent-idle gap 0.01737902 and zero abandonment difference;
  V19 disagrees on 529/607 unforced decisions. V20 keeps V19 exact except a
  low full-boundary teacher coefficient `0.05`, far below V10's failed `1.0`.
  Teacher candidate diagnostics are behavior-neutral and excluded from
  action/state digests. All 44 exact adversaries, 141 Python tests, smoke, and
  determinism pass. Config hash is `22604e484c82601a...`; adversary report is
  `b72ab95c45ec418f...`. Dev-v15 is retired unopened; dev-v16 is frozen at
  disjoint roots `161001..161160`; held-out-v4 remains sealed.
- **V20 rejected on reusable dev-v1**: two pinned replicas reproduce update 32
  at 9/10 construction wins and mean idle 0.09850656. Checkpoint
  `6209f46876db0778...`, model state `1ba534267c67ff54...`, replay
  `a1bc0eec0c7f0002...`, full run `a407aa303e839844...`, and lineage
  `564f7fdca22f0ba9...` reproduce. Teacher disagreement falls from 529/607 to
  170/362 and abandonment returns to zero, but permanent idle remains
  0.05419477 worse (95% CI +0.02812093..+0.08298135). Permanent announcements,
  duplicates, and recovery are uncertain; matched recovery is also uncertain.
  Dev-v16 is unopened, held-out-v4 is sealed, and M8.5 remains unmet. Preflight
  report SHA-256 is `a4ae30d0be2a6ec2...`.
- **Automatic-WAIT boundary correction**: exact structured-event reconstruction
  of all ten reusable V20 episodes matches the runtime idle counters and locates
  the largest gaps after `RELEASE:WAIT`; individual seats remained unassigned
  for up to 2,086 ticks. `WAIT` success released and cleared the assignment but
  did not advance the coordination revision, so stop-on-event waited for an
  unrelated boundary. A successful automatic wait release now marks assignment
  `task_terminal` while preserving the authoritative board `RELEASE` and `OPEN`
  state. The live check returns on the release tick after the deterministic
  61-tick lifecycle and reproduces byte-identically across JVMs. Pinned build,
  141 Python tests, smoke, determinism, and the unchanged 664-checkpoint golden
  pass. Existing candidates retain their recorded results; the corrected
  decision sequence requires a governed from-scratch successor.
- **V21 precommit**: ADR-0032 freezes an exact V20 retrain under runtime contract
  `successful_abandon_one_tick_wait_release_same_tick_v2`; only candidate ID,
  runtime contract, and confirmation path differ. Keeping teacher coefficient
  `0.05` fixed isolates the WAIT-boundary correction instead of confounding it
  with another loss change. Dev-v16 is retired unopened; dev-v17 freezes
  globally disjoint roots `171001..171160`, and held-out-v4 remains sealed. All
  44 exact adversaries, 142 Python tests, pinned build, smoke, and determinism
  pass. Config hash is `5567e1c1d79cae0f...`; adversary report hash is
  `732536ffcd358d25...`.
- **V21 rejected on reusable dev-v1**: two pinned replicas reproduce update 29
  at 9/10 wins and mean idle 0.04383598. Checkpoint `68c3dfba722e0b75...`,
  model `5c09bf859571ac2c...`, replay `81ca21dfe5d634b4...`, full run
  `5d5831a59032c57e...`, and lineage `df5af947a70f6a8c...` match. Permanent
  idle is now essentially parity at -0.00047581 (CI crosses zero), and matched
  idle/recovery improve decisively. V21 still fails because task abandonment is
  definitively +0.04347388 worse against both scorecards. Six episodes each
  retry one resource-short supply target three times at two-tick cadence before
  the fourth succeeds, totaling 18 non-forced replans; matched greedy has none.
  Announcements, duplicates, and permanent recovery remain uncertain. Dev-v17
  is unopened and held-out-v4 remains sealed. Preflight hash is
  `f1a8e47d4cd771793...`.
- **What is broken**: nothing known.
- **Current branch**: `coop-agent/v159.7`
- **Current commit**: see `git rev-parse HEAD` (this scaffold is committed in
  several small commits; the pre-existing HEAD was `c9686eb5`).
- **Engine tag/commit**: `v159.7` / `c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c`;
  Arc `208a754044`.
- **Uncommitted changes intentionally preserved**: the user's modified
  `AGENTS.md`, generated `annotations/src/main/resources/classids.properties`,
  and stat-only upstream files `core/src/mindustry/ai/BlockIndexer.java` plus
  `core/src/mindustry/entities/Units.java`. None belongs to project commits;
  never stage them.

## Exact commands

| Command | Expected output |
|---|---|
| `make bootstrap` | Prints ENGINE_VERSION, Java/Python/Git versions, Gradle wrapper presence, pytest presence; ends `bootstrap: OK`, exit 0. |
| `make build` | Builds `rl-server:dist` + the loadable `agent-plugin:dist`, then validates the Python package import; ends `build: OK`, exit 0. |
| `make test` | Runs the Python suite (92 pass). Use `make test-java` for the JUnit suite. Exit 0. |
| `make test-python` | `pytest python/tests -q` → all pass. |
| `make verify-rl-boundary` | On Linux/WSL2 with uv 0.11.16 and Python 3.12, runs 33 core tests under `python -S`, reconstructs the 15-package hashed CPU environment in a temporary directory, and ends `RL-BOUNDARY OK`. Verified 2026-07-21. |
| `make training-gate` | On WSL2 with pinned `UV`/`JAVA`, reconstructs the RL environment, runs the 1/2/4-JVM shadow-inference collector gate, then 10,000 resets. Current 4-JVM result 375.1x real-time; zero reset drift/leak/orphans; ends `TRAINING-GATE OK`. Verified 2026-07-21. |
| `bash scripts/train-selector.sh` | Runs 27 reward adversaries, two independent train/dev PPO runs, two complete fresh-checkpoint replays, and exact manifest comparison. Current checkpoint `0b2bd8ac...`, full digest `56cc7b54...`, dev 0/10; ends `TRAIN-SELECTOR OK`. Held-out is not read. |
| `make test-java` | Runs the `agent-core` (108 tests) and `rl-server` JUnit suites plus the `agent-plugin` compile check; ends `test-java: OK`, exit 0. Verified 2026-07-21. |
| `make smoke` | Runs exact stepping + M3/M4 ledgers/combat/acceptance and M5.2–5.6 coordination/policy/reservation/chaos/announcement checks twice across fresh JVMs, plus omitted-defense loss checks. Ends `SCENARIO OK`, exit 0. Verified 2026-07-21. |
| `make determinism` | Runs the legacy 79-boundary cross-process replay, reset purity with deterministic unique episode IDs, seed sensitivity, then the checked-in golden (664 checkpoints / 16,200 ticks / two wins). Exit 0. Verified 2026-07-21; `REPLAY_NEGATIVE=1` also passes. |
| `make candidate-policy-check` | Runs the pure public greedy selector over all five pinned seeds; requires 5/5 wins through the ordinary candidate/mask/task-action seam. Verified 2026-07-21. |
| `make coordination-parity` | Compares two complete recorded decision sequences, runs the fixed-step shared expert, then boots the no-port plugin and requires identical live-opening digest/count. Current result: 356 recorded decisions; live digest `1571…a6c2`, 43 selections. Verified 2026-07-21. |
| `make adaptive-planning-check` | Runs adaptive-v1 and frozen M6 on fixed+delayed-loadout scenarios. Requires adaptive 2/2 wins, fixed frozen win, probe frozen loss, all four decision-event reasons, lower mean idle fraction (0.125 < 0.878), and lower defense-ready tick (817 < 5251). Verified 2026-07-21. |
| `make scenario-variation-check` | Validates all scenario-v2 axes, disjoint seed governance, same-seed repeated/fresh-JVM reset and idle-through-wave hashes, frozen-dev adaptive survival, and an undefended v2 pathing/loss run. Current result: 8/10 wins (80%); held-out sets are refused. Verified 2026-07-21. |
| `make evaluate-ladder` | Runs 65 fixed/dev episodes across five versioned baselines, writes episode JSONL plus deterministic bootstrap aggregates, and leaves held-out sealed. Current adaptive-v1 result is 2/5 fixed and 9/10 dev. Verified 2026-07-21. |
| `make stress-reset` | Boots one persistent JVM, resets 1000× (same seed) with no restart; latest M7.1 run: zero hash mismatches, median 1.31 ms, p95 2.60 ms, peak 298.3 MiB, no leak; ends `STRESS-RESET OK`, exit 0. Verified 2026-07-20. |
| `make benchmark` | Measures single-env engine ticks/sec + reset latency, protocol overhead, and 1/2/4-JVM aggregate scaling; prints a markdown report; ends `BENCHMARK OK`, exit 0. ~5 s of stepping + JVM boots, well under 10 min. Verified 2026-07-20. |
| `make scripted-demo` | Runs adaptive-v1 and the legal post-reservation resource-pressure fixture; both end at tick 8100, and the fixture records a real `resources_short_replan`. Verified 2026-07-21. |
| `make evaluate-scripted` | Runs five pinned fixed seeds and writes `runs/scripted-evaluation.jsonl`; current M7.4 result is 5/5 wins, min/mean core health 200/572.6. Verified 2026-07-21. |
| `make demo-server` | Builds/boots the real server+plugin in an isolated no-port probe; verifies layout, full expert preparation, reserve mining, announcements, and controls; exits 0. `DEMO_SURVIVAL=1` clears three waves and reaches tick 8100 with 1100/1100 core health without opening a port. Use `DEMO_JOIN=1` only for an explicit private port-6567 human session. |

(If `make` is unavailable on Windows, run `bash scripts/<name>.sh` directly.)

## Architecture map

- **Key modules**: `rl-server` (headless fixed-step launcher, `mindustry.rl`),
  `agent-core` (`agentcore`), `agent-plugin` (loadable real-time server adapter,
  `mindustry.agentplugin`); Python
  `mindustry_agents` package. See `docs/ARCHITECTURE.md`.
- **Python env/process layer (M2)** — the request path top to bottom:
  `env.parallel_env.MindustryParallelEnv` (per-agent dict PettingZoo surface,
  duck-typed, no pettingzoo import) → `env.client.EnvClient` (one connection,
  episode/tick bookkeeping, tuple returns) → `process.launcher.Connection`
  (length-prefixed JSON socket) → one JVM. `process.supervisor.ProcessSupervisor`
  owns a pool of these (ports, seeds, per-child `runs/` stderr logs, handshake
  verification, crash/hang detection + auto-replacement, atexit/context-manager
  shutdown); `env.vector.VectorCollector` steps the whole pool in lockstep. All
  stdlib-only (ADR-0007). The JVM is mocked in unit tests by
  `python/tests/fake_server.py` (a subprocess speaking the real protocol).
- **Important classes/functions**: `mindustry.rl.RlServer` (fixed-step launcher +
  control loop; see `FixedStepApplication`, `FixedStepGraphics`, `StateHasher`,
  and `Scenario` — the JSON-driven world/waves/termination loader — in
  `rl-server/src/main/java/mindustry/rl/`);
  `agentcore.board.TaskBoard` + `agentcore.{task,reservation,event,announce,utility}`
  (see `docs/COORDINATION.md`);
  `mindustry_agents.protocol.{encode,decode,decode_stream,read_message}`;
  `mindustry_agents.process.launcher` (JVM supervisor, tracks spawned PID only).
- **Protocol entry points**: `docs/PROTOCOL.md` (spec v1);
  `python/src/mindustry_agents/protocol.py` (reference impl); Java side in
  `mindustry.rl` (length-prefixed JSON, byte-compatible — verified by smoke).
- **Simulation thread rules**: only the sim thread reads/mutates game state; I/O
  threads parse+queue (`docs/ARCHITECTURE.md` threading rule).
- **Reset path**: `RlServer` reset handler — `Logic.reset()` plus the gaps it
  leaves (reseed `Mathf.rand`, reset `EntityGroup.lastId`, zero `Time` incl.
  `globalTimeRaw`, pathfinder threads stopped); in-process, no JVM restart,
  ~4 ms median. See `docs/ENGINE_NOTES.md`.
- **Step path**: queued request → sim thread applies action bundle → exactly N
  fixed-delta engine updates → observation + SHA-256 canonical hash.
- **Observation path**: built on the sim thread at the step boundary (M1 minimal:
  tick/wave/core items/counts/health; per-agent observations are M3).
- **Task/skill path**: `agentcore` owns the board and engine-free skills;
  `agentcore.coordination.ExpertCoordinationDriver` owns the shared scripted
  policy and lifecycle. `mindustry.rl.CoordinationAdapter` owns the per-episode
  board, validates external task actions, optionally adapts that driver for
  parity evaluation, maps task types to M3/M4 skills, and reports lifecycle/
  events/snapshots. `SkillController` and `RlAgentRegistry` remain the engine
  ports; `ActionDecoder` retains the legacy direct-command path.

## Current performance

- **Machine information**: AMD Ryzen 7 9800X3D (8C/16T), 61.6 GB RAM, Windows 11,
  Temurin 21.0.11, Python 3.12.5.
- **Single-environment ticks/sec**: ~76,000 engine-only (~1,270× real-time);
  ~54,000 end-to-end through the Python client.
- **Reset latency**: median ~0.8 ms over 1000 resets (p95 ~1.5 ms) for the M1/M2
  minimal world; **~1.07 ms median (p95 2.11 ms, max 44.94 ms warmup) for the full
  bootstrap-defense-v0 world** (bigger map + wave/flowfield preload) — Gate 2
  (<250 ms) still passes with a huge margin; no JVM restart, no stale state.
- **Memory per JVM**: peak working set ~285 MiB over 1000 resets with `-Xmx350m`
  (well under the 650 MiB leak ceiling); no per-reset leak. Within-cap RSS growth
  is lazy heap sizing, not a leak — run-to-run growth varies (+0.2% to +24%),
  which is why the leak check uses an absolute ceiling, not a growth trend.
- **Scaling table**: 1 JVM ~42k, 2 JVMs ~66k (~79%), 4 JVMs ~89k (~53%) aggregate
  ticks/sec. Near-linear to 2; capped at 4 on this shared host. Full table +
  caveats in `docs/BENCHMARKS.md` (M2 measurements).
- **Known bottleneck**: at 4 JVMs the per-step engine time (<1 ms for a 60-tick
  chunk) is smaller than the `VectorCollector`'s GIL-bound JSON encode/decode, so
  the Python side — not the engine — limits aggregate throughput. Larger step
  chunks or a process-based collector would scale further (future work).

## Tests

- **Passing**: 92 Python tests (`test_import.py`, `test_protocol.py` incl. M3–M7.6
  action/board/event roundtrips, `test_supervisor.py`, `test_env.py`; fake-server
  subprocess, no JVM, fast) and 108 Java JUnit tests (`agent-core`, incl.
  31 M3/M4 `agentcore.skill` FSM tests, via `make test-java`). Real-JVM coverage is
  the shell scripts (smoke/determinism/stress-reset/benchmark) — smoke includes
  the M5.2–M5.6 live coordination checks and determinism the scripted skill
  trace; all verified green 2026-07-21. M7.2 additionally has the recorded and
  live-runtime `coordination-parity` gate. M7.3 adds five-seed public
  `candidate-policy-check`; M7.4 adds real predicate, event-boundary,
  generalized blocked-replan, and adaptive-vs-frozen probe coverage. M7.5 adds
  cross-JVM variant-reset, sealed-set refusal, and frozen-dev survival coverage.
  M7.6 adds deterministic policy/scorecard/bootstrap unit coverage and the live
  65-episode ladder. M8 adds deterministic PPO/replay coverage plus the dev-only
  promotion comparator and paired-scorecard gates.
- **Skipped**: none.
- **Flaky**: the stress-reset *leak* check was flaky under the original
  growth-trend methodology (passed for the author, failed on re-verification);
  fixed by switching to a capped-heap absolute-ceiling check. Hash stability was
  never flaky.
- **Failing**: none.
- **Golden hashes**: the live harness and checked-in two-episode golden both
  pass; 670 checkpoints cover 16,200 ticks and two wins. M7.4 regenerated the
  trace because the hash now includes adaptive rolling facts and switching
  history; frozen macro outcomes and length did not change, and the negative
  mutation still diverges.

## Known risks and bugs

- **The seed lever is now exercised (resolved)**: with enemy waves live, different
  `root_seed`s diverge once wave 1 spawns (the native `WaveSpawner` spread is seeded
  from `root_seed`), while the same seed stays bit-identical across processes and
  resets. Proven by `tools/determinism.py` check 4. Pre-wave state is still
  seed-independent (nothing consumes `root_seed` before tick 2700) — expected.
- **Dynamic re-path determinism is resolved (M4.1)**: the thread-less
  `Pathfinder.syncUpdate()` path consumes pending tile changes immediately without
  the normal-mode wall-clock gate. `tools/determinism.py` places a copper wall at
  tick 2760 and matches all 79 hashes across fresh JVMs while daggers continue
  around it. M4.2 removed the temporary hook; the trace now uses legal `BUILD`
  and verifies the six-copper wall ledger.
- **4-JVM scaling is Python-bound** (~53% efficiency): GIL-bound JSON in the
  collector, not the engine. Fine for now; revisit before large-scale training
  (larger tick chunks or process-based collection).
- **Protocol overhead** is ~22% of a 60-tick step wall-time (engine is just
  <1 ms/chunk); Gate 6 (<10%) passes only at larger action-repeat. Honest
  status in `docs/BENCHMARKS.md`; revisit alongside ADR-0004's Protobuf trigger.
- See `docs/decisions/` and brief §29 for the standing risk register.

## Next five issues

**Authoritative work queue: `docs/ROADMAP.md` M8 item 8.5.
Handoff prompt for the next agent:
`docs/CODEX_HANDOFF_PROMPT.md`.** The summary below mirrors the head of that
queue.

1. **Choose V22 from reusable V21 evidence only.** Target the exact repeated
   resource-short same-target supply retry sequence without reopening the idle,
   reward-cap, or teacher-coefficient lines. Precommit the causal intervention
   and fresh disjoint dev-v18 before model work; dev-v17 is retired unopened.
2. **Use corrected preflight parity.** Require exact replicas, reusable dev-v1,
   and both permanent-greedy and matched-greedy scorecards before any one-way
   confirmation. Never inspect dev-v14/dev-v15/dev-v16/dev-v17 or
   held-out-v1/v2/v3 outcomes for tuning; held-out-v4 remains sealed.
3. **M9.1 remains gated.** The roadmap says to begin only after the single
   learned seat promotes; do not silently bypass that prerequisite.
4. **M9.2 partner population** remains behind M9.1.
5. **M9.3 communication ablation** remains behind M9.2.

## Decisions

See `docs/decisions/ADR-0001..0020` (do not relitigate).

## Deviations from the brief in this scaffold

- `protocol/` is **not** a Gradle module. Per ADR-0004 the bootstrap transport is
  JSON; the schema lives in `docs/PROTOCOL.md` and `protocol.py`. Protobuf +
  generated bindings are deferred to Stage D. This avoids dead scaffolding.
- The brief's separate `tests/{determinism,integration}/` directory split is not
  used; real-JVM checks live behind `scripts/*.sh`. `tests/golden/` now contains
  the checked-in complete M6 replay trace.
