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
  crash-replacement, PettingZoo-shaped facade, vector collector; 156 pytest
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
- **What is stubbed**: the M10 human goal/override/study implementation remains
  future work. `docs/M10_DESIGN.md` and ADR-0057 now accept its architecture and
  require the plugin to adopt the public candidate/typed-action path before
  commands are added. The behavior-neutral `AgentRuntimeRegistry` prerequisite
  is implemented and tested, and `DemoAgentRegistry` now owns real-time spawn/
  rebind behind it. The tested Java `GreedyUtilityPolicy` fallback exists over
  public candidates/masks. The real-time default now uses the complete public
  typed-action path and has reached readiness after wave damage/rebind;
  `DEMO_PUBLIC_POLICY=0` is the explicit legacy regression oracle. Its stock-
  clock survival gate is green through tick 8100
  with core health 1100, three structured wave clears, both expansion and
  maintenance completions, and reserve mining. Exact public-path parity is green:
  390 traced candidate/mask boundaries and 1,170 Java actions match Python, and
  two fresh JVMs reproduce 225 accepted selections with digest
  `aaf2e734ea384fe4b537cbdf3bd5342fb5e954f3432a91470ebce311fa503714`.
  A persistent logistics seat reduces seven repeated abandon/reclaim cycles to
  two phase-entry rebalances and seven unassigned waits. All prerequisites and
  the default promotion pass. M10.1 now adds the engine-free
  strict `HumanControl` parser and simulation-thread state with bounded ordered
  goals, assignments, autonomy/quiet settings, deterministic ids/revisions,
  stable rejection reasons, and reset tests. Explicit task provenance and the
  engine-free overlay core now wrap only already-valid structured ordinary
  candidates, reserve bounded goal-order slots, preserve WAIT, and return the
  exact original candidate set for empty control. Autonomous bytes,
  observations, and hashes omit provenance. Engine matching, assignment masks,
  and queued plugin application are now live on the public path. Callbacks parse
  and enqueue only; simulation-thread application emits structured results.
  Explicit and NORMAL implicit assignment, LOW/NORMAL/HIGH masks, terminal
  cancellation, reversible release, and quiet rendering pass unit and no-port
  integration probes.
  The probe completes assigned `human:goal:1` BUILD_LINE, exercises assigned LOW
  defense, stable-id reassignment, and advisory HIGH defense, applies 16/16
  commands, restores empty/NORMAL state, and suppresses four nonurgent messages.
  The probe also injects an engine build plan over active work, observes one
  deterministic yield/notice, preserves the rules-scaled resource floor, keeps
  recent construction agent-free for 600 ticks, then resumes the stable goal.
  M10.1 and M10.2 are complete. Exact public parity and stock tick-8100/full-
  health survival remain green; opt-in session capture is next.
  M8.5 evaluation machinery is real, but the candidate did not promote.
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
- **Post-V21 runtime correction**: the adapter now retains/hashes a blocked
  skill's authoritative retry tick, masks only the same semantic work before it
  is due, rejects direct bypass as `retry_not_due`, and reopens it exactly on the
  due tick. The live fixture is `BUILD_SCHEMATIC` tick 607 -> 667 and proves an
  alternative non-WAIT task stays legal. A full public-policy run also found and
  fixed stale dead-seat ownership: it emits forced structured
  `ABANDON(agent_death)`, releases reservations, wakes `task_terminal`, and
  leaves only no-op WAIT legal for that seat. Fixed seeds are 5/5 with 12 loss
  releases. The regenerated two-win/16,200-tick/664-checkpoint golden reproduces
  twice at `f08c5af6b6ea4e25...`; only hashes changed, and the negative mutation
  still diverges. This was the validated boundary before V22 model work began;
  the governed confirmation set was not opened.
- **V22 precommit**: ADR-0033 freezes an exact V21 retrain under runtime contract
  `abandon_wait_retry_and_agent_death_boundaries_v3`; only candidate ID,
  runtime contract, and confirmation path differ. Dev-v17 is retired unopened;
  dev-v18 freezes disjoint roots `181001..181160` and remains unopened, while
  held-out-v4 stays sealed. The 44 exact reward adversaries, 143 Python tests,
  pinned build, five-seed candidate gate, smoke, determinism, and negative replay
  pass. Config hash is `95bc200596718170...`; adversary report hash is
  `18f337ac3ca54700...`.
- **V22 rejected at construction gate**: replica A completed all 2,048 episodes
  and 32 updates, then found no frontier row below the frozen idle threshold.
  Update 17 was 10/10 but reported idle `0.48320387`; the reconstructed frontier
  hashes to `17d8afa6e7fb2f33...`. Replica B did not start. The cause is a runtime
  metric defect exposed by real agent death: dead seats accumulated both
  available and idle ticks forever, contaminating the idle reward. The adapter
  now partitions unavailable ticks separately; diagnostic update-17 evaluation
  becomes 10/10 at `0.13474577`, but the trained checkpoint remains rejected.
  Dev-v18 is retired unopened and held-out-v4 remains sealed.
- **V23 precommit**: ADR-0034 freezes an exact V22 retrain under runtime contract
  `abandon_wait_retry_agent_death_available_idle_v4`; only candidate ID,
  runtime contract, and confirmation path differ. Dev-v19 freezes disjoint roots
  `191001..191160` and remains unopened. All 44 exact reward adversaries, 145
  Python tests, pinned build, five-seed availability ledger, smoke, determinism,
  and negative replay pass. Config hash is `17e741e63f9862bc...`; adversary
  report hash is `e2043acefb24a016...`.
- **V23 rejected on reusable dev-v1**: two admissible pinned replicas reproduce
  update 5 at 10/10 construction wins and `0.09043677` idle (checkpoint
  `2ae62cc31c86731a...`, full run `85dfb4e2596cd653...`, direct lineage
  `b532f8cb8df8e3c...`). Preflight rejects it because abandonment is
  definitively `+0.04490747` worse than both permanent and matched greedy, and
  permanent idle is definitively `+0.03999701` worse. Report hash is
  `4237a8503bb4bff4...`; dev-v19 was never opened and is retired; held-out-v4
  remains sealed.
- **Post-V23 runtime correction**: 31/32 non-forced abandons alternated between
  resource-short supply targets every two ticks. The adapter now retains an
  ordered, canonical-hashed set of retry holdoffs. `CORE_SHORT` and
  `RESOURCES_SHORT` apply across the task type; other failures remain
  target-local. The two-target fixture proves tick 432 -> 492 masking, direct
  bypass rejection, unrelated-work legality, and exact due-tick reopening. The
  pinned build, 145 Python tests, 5/5 gate, smoke, determinism, and negative
  replay pass; final golden hash is `8fee3db9b5cf01f2...` with zero non-hash
  replay changes. The V23 diagnostic is inference-only and cannot promote.
- **V24 precommit**: ADR-0035 freezes an exact V23 retrain under runtime contract
  `abandon_wait_resource_scoped_retry_agent_death_available_idle_v5`; only
  candidate ID, runtime contract, and confirmation path differ. Dev-v19 is
  retired unopened. Dev-v20 freezes roots `201001..201160` and remains unopened;
  held-out-v4 stays sealed. No V24 model work preceded the packet. All 44
  exact-config reward adversaries, 146 Python tests, pinned build, 5/5 candidate
  gate, smoke, determinism, and negative replay pass. Config/adversary hashes are
  `94a7ae8cf57cb1ce...` and `4cd7f5096bbd0ebc...`.
- **V24 rejected at construction**: replica A completed 2,048 episodes/32
  updates, but no checkpoint reached 9/10. Best-ranked update 19 is 8/10 with
  idle `0.06516475`; retained frontier hash is `90ead621f808c53f...`. Replica B
  did not start, dev-v20 remained unopened and is retired, and held-out-v4 stays
  sealed. Current-runtime adaptive-v1 is 10/10 with idle `0.07308979` and zero
  abandonment; update 19 disagrees on 73/427 unforced decisions and loses seeds
  2004/2005. V24 is rejected.
- **What is broken**: learned construction remains below the 9/10 gate. The
  reusable evidence supports a governed moderate teacher-strength successor;
  no successor model work has started.
- **V25 precommit**: ADR-0036 holds the V24 runtime/reward/data/model/optimizer/
  RNG/schedule/selection exact and doubles only full-boundary teacher coefficient
  `0.05 -> 0.10`, plus candidate/label/confirmation metadata. This is motivated
  by current-runtime adaptive-v1 at 10/10 and V24 disagreement of 73/427, while
  remaining tenfold below V10's failed `1.0`. Dev-v20 is retired unopened;
  dev-v21 freezes roots `211001..211160` and remains unopened; held-out-v4 stays
  sealed. No V25 model work preceded the packet. All 44 exact-config adversaries,
  147 Python tests, pinned build, 5/5 candidate gate, smoke, determinism, and
  negative replay pass. Config/adversary hashes are `90b50d1b7add7fd0...` and
  `8faa7834e426678e...`.
- **V25 rejected at construction**: replica A completed 2,048 episodes/32
  updates but peaked at 8/10. Best update 16 has idle `0.06516475`; retained
  frontier hash is `0ad699ece62ab94b...`. Replica B did not start, dev-v21 is
  retired unopened, and held-out-v4 stays sealed. The stronger coefficient
  lifted update 1 from 1/10 to 7/10 and reduced mean disagreement logit gap
  `1.49301094 -> 1.07148486`, but the best policy keeps 73 disagreements and
  loses seeds 2004/2005. V25 is rejected.
- **V26 precommit**: ADR-0037 freezes the final fixed full-boundary teacher
  step, `0.10 -> 0.20`, based on V25's directional logit movement. It remains
  fivefold below failed `1.0`; construction failure closes the coefficient
  line. Runtime/reward/data/model/optimizer/RNG/schedule/selection stay exact
  except the mirrored coefficient and candidate/label/confirmation metadata.
  Dev-v21 is retired unopened; dev-v22 freezes roots `221001..221160` and
  remains unopened; held-out-v4 stays sealed. No V26 model work preceded the
  packet. All 44 exact-config adversaries, 148 Python tests, pinned build, 5/5
  candidate gate, smoke, determinism, and negative replay pass. Config/adversary
  hashes are `b5e3bf17a1dc1ace...` and `202e71a48bf8a05f...`.
- **V26 rejected; coefficient line closed**: replica A completed 2,048
  episodes/32 updates but peaked at 5/10. Best update 10 has idle `0.06423822`;
  retained frontier hash is `0f67cf4484c09ad7...`. Replica B did not start,
  dev-v22 is retired unopened, and held-out-v4 stays sealed. The final `0.20`
  step reversed V25's early gain, so no coefficient-only successor is
  authorized.
- **V27 precommit**: ADR-0038 returns to V24's exact `0.05`
  online-teacher construction and adds one separate success-only teacher-
  trajectory warmup before PPO. A train-v2 census found 5/64 adaptive wins and
  121 unforced labels on those winning sequences; eight CE epochs present 968
  samples without consuming ordinary action/PPO RNG state. Losing trajectories
  remain archived evidence. Dev-v22 is retired unopened; dev-v23 freezes roots
  `231001..231160` and remains unopened; held-out-v4 stays sealed. Complete
  pretraining gates pass: 44 exact-config adversaries, 152 Python tests, pinned
  build, 5/5 candidate gate, smoke, determinism, and negative replay. Config/
  adversary hashes are `189ef43857452494...` and `d1c1da02ed7d3a4e...`.
  The packet was committed before replica A.
- **V27 rejected at construction**: replica A completed the 64-episode warmup
  and 2,048 PPO episodes/32 updates. Warmup reproduces 5/64 teacher wins, 121
  eligible labels, 968 presentations, and model-state movement
  `dbae4c605e52b962... -> ce95e9b0aa8ab34a...`; its report hash is
  `b4ca44db858a84a8...`. Eighteen updates reach 8/10 but none reaches 9/10;
  best-ranked update 20 has idle `0.07044212`, and the frontier hashes to
  `d23df387d15966f17...`. Replica B did not start, dev-v23 is retired unopened,
  held-out-v4 stays sealed, and V27 stops before reusable preflight.
- **V28 precommit**: ADR-0039 keeps V27 exact and rehearses the
  same five-episode/121-transition successful teacher corpus for one CE epoch
  after each PPO update. V27's reusable disagreement margin grew
  `0.02482445 -> 2.24436055`, so this isolates prior retention without changing
  warmup strength, online coefficient, reward, runtime, roots, PPO budget, or
  inference. Rehearsal seed is `8607`; order is
  `PPO -> rehearsal -> checkpoint -> dev`, with an atomic failure-safe report.
  Dev-v23 is retired unopened; dev-v24 freezes roots `241001..241160` and remains
  unopened; held-out-v4 stays sealed. All 44 exact-config adversaries, 153 Python
  tests, pinned build, 5/5 candidate gate, smoke, determinism, and negative
  replay pass. Config/adversary hashes are `ef58055e7da5566d...` and
  `2d672a7f0e816a41...`. The packet was committed before replica A.
- **V28 rejected at construction**: replica A completed all 32 rehearsal-
  bearing updates but never reached 9/10. Rehearsal CE falls
  `1.39527905 -> 1.31666994`; report hash is `2bd187fea8635206...`. Ten updates
  reach 8/10; best-ranked update 27 has idle `0.07046312`, 134/401 teacher
  disagreements, and losses on 2004/2009. Rehearsal reduces the disagreement
  margin `2.24436055 -> 1.81065121` but does not flip actions; frontier hash is
  `ba963bea1d0d303b...`. Replica B did not start, dev-v24 is retired unopened,
  held-out-v4 stays sealed, and V28 stops before reusable preflight.
- **V29 precommit and rejection**: ADR-0040 froze a separate 256-root
  train-only teacher corpus `291001..291256` before any outcomes were observed.
  It keeps V28's exact warmup/rehearsal strengths and PPO construction but
  collects teacher episodes from the auxiliary set, archives every outcome, and
  filters only complete wins into CE. PPO still uses the original 64 roots for
  2,048 episodes. Dev-v24 is retired unopened; dev-v25 freezes roots
  `251001..251160` and remains unopened; held-out-v4 stays sealed. Complete gates
  passed: 44 exact-config adversaries, 154 Python tests, pinned build, 5/5
  candidate gate, smoke, determinism, and negative replay. Config/adversary
  hashes are `a40a8772ef5392fb...` and `cac12af7f0861dea...`. The committed
  packet preceded all V29 outcomes. Replica A then collected 37 teacher wins
  and 860 eligible transitions, but no learned checkpoint exceeded 4/10.
  Rehearsal CE fell `1.32362124 -> 0.46930411`; warmup/rehearsal/frontier
  hashes are `582f362322e4aa43...`, `b5c089bf4d85acd2...`, and
  `26c6270efca0c852...`. Best-ranked update 5 has idle `0.21429663`. Replica B
  did not start, dev-v25 is retired unopened, held-out-v4 stays sealed, and V29
  stops before reusable preflight.
- **V30 precommit and rejection**: ADR-0041 identifies V29's confound:
  expanding 121 eligible labels to 860 while keeping epoch counts fixed raised
  warmup presentations `968 -> 6,880` and rehearsal `121 -> 860` per update.
  V30 holds V29 exact but caps each CE epoch at 121 deterministic samples, so
  update counts return to V28 strength while schedules rotate through the
  diverse corpus. Exact indices/coverage/schedule hashes are reproducibility
  evidence; absent caps preserve historical behavior. Dev-v25 is retired
  unopened; dev-v26 freezes `261001..261160` and remains unopened; held-out-v4
  stays sealed. All 44 exact-config adversaries, 155 Python tests, pinned build,
  5/5 candidate gate, smoke, determinism, and negative replay pass. Config/
  adversary hashes are `c57556695157dcd4...` and `a3bcf116478e1be0...`. The
  committed packet preceded all model work. Replica A then restored exactly 968
  warmup and 3,872 rehearsal presentations, covering 603/860 warmup and 855/860
  aggregate rehearsal transitions. CE fell `1.41403544 -> 1.05248463` across
  rehearsal, but the best result remained 8/10. Twenty-one updates reached
  8/10; best-ranked update 11 has idle `0.06573742`. Warmup/rehearsal/frontier
  hashes are `7f92ee1bdaa59d8f...`, `a2559f5651cc0d54...`, and
  `e841b620424e0299...`. Replica B did not start, dev-v26 is retired unopened,
  held-out-v4 stays sealed, and V30 stops before reusable preflight.
- **V31 precommitted; replica A next**: reusable V30 update-11 diagnosis loses
  the same 2004/2005 pair as V24. Seed 2004 has six policy decisions and only
  two teacher disagreements; all ten seeds begin `BUILD_LINE` instead of the
  10/10 teacher's `BUILD_SCHEMATIC`, with learned gaps
  `0.83764815..0.85484707`. ADR-0042 keeps V30 exact and adds `+1.0` only to a
  valid tick-0 `BUILD_SCHEMATIC` logit. Masked selection still decides the
  action; rollout, PPO, teacher CE, preflight, and final all use the same tensor,
  while historical configs remain exact. Dev-v26 is retired unopened; dev-v27
  freezes `271001..271160` and remains unopened; held-out-v4 stays sealed. All
  44 exact-config adversaries, 156 Python tests, pinned build, 5/5 candidate
  gate, smoke, determinism, and negative replay pass. Config/adversary hashes
  are `861f34bd07db43a5...` and `e7eb2f8826db4617...`. The committed packet must
  precede all V31 model work.
- **Post-V37 reusable diagnostics rejected**: after V37's reusable scorecard
  rejection and ADR-0049's retirement of the membership-exposed sets, two
  off-contract V38 coordinates were tested only on reusable evidence. Collision
  redirect (`097d8f5c95b0bbd6a40d3f8fbca0ca6e86d527d4bbf1c8a1f3a01ebc52ff2490`)
  falls from 9/10 to 6/10 and shifts idle from learned seat 0 to seat 2: total
  idle rises `7,840 -> 11,609` (`+48.07%`), with learned seat `-3,053` and seat
  2 `+6,988`; 37 rewrites include 34 for seat 2 and 13 `WAIT`s, and seeds
  2002/2003/2006 flip to losses. Partner-intent masking
  (`83a4242b6b7df288ec20976029356637de61a3e2adf9736b1a3cff41e5006319`) is
  bound to V37's exact config/checkpoint/direct lineage/public reusable set but
  reaches 7/10 and mean core health `500.0`. Idle falls `7,840 -> 7,182`, by
  seat `[4,658,342,2,840] -> [4,619,338,2,225]`, yet only 39 learned-seat ticks
  are saved and seed 2002 seat 2 contributes 617/658 of the reduction. Its mean
  authoritative idle is `0.05223`; all 48 masks have clean traces, while seeds
  2005/2010 flip to losses. It cannot measure announcement/recovery parity.
  Both coordinates are rejected; the subsequent V38 precommit follows.
- **Actionability evidence and V38 precommit**: artifact
  `0500a74377b740556e3012635491318acbde3939c7f179bd24e79aa46ebf2099` matches
  V37's complete 1,128-boundary action/tick/state-hash sequence exactly and
  reproduces 9/10 wins, core health `805.5`, and idle `[4,658,342,2,840]`. Every
  one of the 4,658 learned-seat idle ticks overlaps fortification; 4,611 occur
  while seat 1 owns its running `BUILD_SCHEMATIC`. No-valid-non-WAIT/no-staging
  intervals account for 1,607 ticks, six harvest claim losses account for
  3,011, and no idle interval exposes valid staging. ADR-0050 therefore holds
  V37 exact and exposes only the existing nonexclusive proactive
  `DEFEND_REGION` candidate to learned seat 0 while another seat owns a live
  `BUILD_SCHEMATIC` in the quiet pre-defend-lead window. It does not force,
  mask, redirect, or alter scripted seats; retraining and fresh baselines are
  required. Config SHA-256 is
  `d92bf9aa2050a5a4d62fc29566fb2514feec84eb421f62b6cac2e24b0969f2bf` and the
  umbrella reservation SHA-256 is
  `a2e2389925797a5f5a8c93224561f68f36fd443afbebdc07f888aaf6bef6f27a`.
  The governance/config/umbrella/test packet is committed at `de597c8462`
  before membership access. Primary-only freezer commit `a7504a4781` precedes
  freeze commit `9c8f7f3d32`; the value-free record says
  `values_emitted=false` after checking 41 pre-existing membership documents and
  5,321 unique roots. Dev-v34 and held-out-v5 are frozen at 160 unique, globally
  disjoint roots each. Their hashes are
  `bef6bb17c7759530dc216961733839808dbff228bb96a09232dced89a7ca5ac7` and
  `1118ef59b0953aacd86176737777013bb2c6498e128f28bcbb7850e6ad586910`;
  freeze-record SHA-256 is
  `7282a3cd405f2d6b00dd3942fb8da2b2f62eb3a8f567dc067edc07756787018e`.
  Both sets remain unconsumed. V38's runtime implementation is committed at
  `8b3f9cc749`, and all pretraining gates are green. The public-seed-12345 live
  probe has seat 1 running `BUILD_SCHEMATIC`, one valid learned-seat
  `DEFEND_REGION` stage beside ordinary `BUILD_LINE`, no scripted-seat stage,
  and no synthetic claim/helper/event. Focused `CandidateGenerator` tests and
  Gradle `agent-core:test rl-server:test agent-plugin:classes` pass; Python is
  166/166. Candidate policy is 5/5 with 10 proactive staging starts; smoke is
  9/9. Determinism ends at `20a97f36407167597981e77c` cross-process,
  `a2cf4a73ee901c844f30f486` after reset, and
  `495ba05fa71697bdc8ff2951` for the alternate seed. Golden replay covers 664
  checkpoints, 16,200 ticks, and two episodes; negative replay detects a
  one-line `MINE` change. All 44 exact-config reward adversaries pass for config
  `d92bf9aa2050a5a4d62fc29566fb2514feec84eb421f62b6cac2e24b0969f2bf`; the
  temporary, uncommitted report SHA-256 is
  `e44865297a31ab1625bf4a43116cf1ff712b96657043c200c0af629ddd4f59bf`. At that
  implementation checkpoint, no baseline episode or model work had begun.
- **V38 replica A passes its exact authorization gate**: from committed
  repository `3effefed781b88c2e71354d784db58eb787ed7e6`, config
  `d92bf9aa2050a5a4d62fc29566fb2514feec84eb421f62b6cac2e24b0969f2bf`, and
  lock `8d865c8c710a61d7e37b8896b38166a1dcf121e40d17fbb1a47e948b4861bf6c`,
  replica A completed 256 warmup episodes, 2,048 training episodes, and 32
  updates. Selected update 20 is 9/10 with return `4.859680000000006`, core
  health `565.2`, and idle `0.021071738935729764`. Checkpoint/model-state hashes
  are `3bc4a3a1cc9c2ef4450e20c689c3909a8bf9ae8ba35b194e8710df1acf737b5e` and
  `b9f592ffe58d1b866f200cd3544a2ecfd48f6d662f517aece3dffa745fa66540`.
  Both replay passes are bit-exact at
  `272dfb7a5793c1b79be95ce9b7e2407c3752cb6ee183cf9440dbe388ee4553af`;
  action-state is
  `5ba7991a0dd10f0d857c5fcbf75ccbbb573eb7a7c59b975967c3432463f3c68c`,
  canonical full-run is
  `356a2065c8c2001ba6e9b2b480949e0c4ff3fdfd39b88ac8747c49e2838f57a2`,
  frontier is
  `9955422e926e955700370f6dcf792c1c1054e6501e8b5b46afb151911ea78c7b`,
  and manifest is
  `e61516546eabb0cf35d53f699c1e24fa20f214f9a534678cf69ff5361ecd63ad`.
  The precommitted `>=9/10` and idle `<0.25` gate passes exactly. Exact replica
  B is authorized from the same commit/config/toolchain in an independent
  output. Dev-v34 and held-out-v5 remain unconsumed; no scorecard,
  confirmation, or final episode has run. M8.5 remains unmet.
- **V38 replica B and direct lineage are exact**: replica B ran independently
  from the same commit, config, and lock and selected update 20 with identical
  9/10 wins, return `4.859680000000006`, core health `565.2`, and idle
  `0.021071738935729764`. All 32 checkpoints are byte-identical. Selected
  checkpoint/model, replay, action-state, and canonical full-run reproduce at
  `3bc4a3a1cc9c2ef...`, `b9f592ffe58d1b86...`, `272dfb7a5793c1b79...`,
  `5ba7991a0dd10f0d...`, and `356a2065c8c2001b...`; warmup raw hash is exact at
  `d1dab1c2d438ba95...`. Path-bearing rehearsal/frontier/manifest raw hashes
  differ as expected, while governed canonical comparison passes. Direct
  lineage passes schema `selector_checkpoint_direct_lineage_v1` for selected
  update 20 and exact commit/checkpoint/model/config, with digest
  `ada0bcca1d60b25b...` and artifact SHA-256 `9a608dc354ff06ba3...`. Fresh V38
  permanent random/greedy and matched baselines, then reusable scorecard
  preflight, are next. Both protected sets remain unconsumed; confirmation and
  final remain prohibited. M8.5 remains unmet.
- **V38 reusable preflight rejects before confirmation**: ADR-0051 accepts the
  selected-only contract at guard commit
  `9bc96f91c7219ad9e9656f99b29f15331b78b399`: explicit seed-set file, declared
  split and pre-read held-out gate, prebuilt fail-closed JAR, config/repository/JAR
  provenance, no implicit Gradle, and fail-closed stale-provenance checks.
  Legacy registry mode remains diagnostic compatibility only. Python is
  176/176 and reward adversaries are 44/44 (`e44865297a31ab...`). Fresh
  permanent random/greedy are 4/10 and 8/10, with idle `0.0153280914` and
  `0.0157205468`; matched random/greedy are 5/10 and 6/10, with idle
  `0.1635828272` and `0.0888449994`. Candidate update 20 remains 9/10, return
  `4.85968`, core `565.2`, idle `0.0210717389`, and passes all observed win
  comparisons. Permanent scorecards leave announcements, duplicates, and idle
  uncertain; matched scorecards leave duplicates and recovery uncertain.
  Preflight is false (`99575abd...` records, `aa3fa1fe...` aggregate,
  `e6c9cf27...` report), so ADR-0050 rejects V38. Dev-v34 is retired unopened
  and unconsumed without a membership read; held-out-v5 remains sealed and
  unconsumed. M8.5 remains unmet.
- **Four V39 reusable-only diagnostics rejected**: all four artifacts have
  byte-exact twins and candidate/matched/permanent parity. The WAIT
  communication probe (`014085de7007e4d6227e6c5ae89ee1cd636b60f036c6b1db23a8acdd41908ad6`)
  records structured/suppressed counts candidate `17641/74`, matched
  `16161/69`, and permanent `17252/74`. Candidate-minus-permanent announcements
  remain uncertain before filtering (`-0.00307796`, CI
  `[-0.01502905,0.00748813]`) and after filtering (`+0.00176772`, CI
  `[-0.00574127,0.00877167]`); matched stays pass. The claim-loss probe
  (`e3c726380516e9762566ab5b98dc3312758f52d2c943b979e49263cefbb9f794`)
  has 10/10 canonical parity and finds 19 learned-seat-0 losses (18 supply, one
  harvest), zero staged/live partner schematics, 19/19 ordinary non-WAIT
  alternatives, and zero extra boundary reconvergences. Seed 2005's harvest at
  tick 2053/gap 695 could expose `BUILD_LINE` at 694 only by changing the
  trajectory and recreating V34 staging-disappearance risk. Reject both.
- **Recovery/collision coordinates also rejected**: recovery artifact
  `727e62145895a5a9435a6c62372156a7887c5dd12d2d5d204d8d7b89bc5d298e`
  finds 30 deaths and zero same-type valid choices at the exact death boundary.
  Seeds 2004/2006 first permit `HARVEST` next tick, but require bias-to-tie
  above `3.822402`/`3.973103` against defense. Supply-collision artifact
  `9b9905b208dceb95b9ddbf240a4050d63a85779b321eec7b6fc35bdfb1e26870`
  records 18 collisions in seven bursts, alternate supply for 11/18, and 18
  mask changes (11 supply, six schematic, one harvest), with a `+1`
  alternate-supply prior for only 6/18. This is the same 18/37 rejected
  redirect-rewrite and 18/48 rejected-mask coordinate; it affects duplicates,
  not recovery or idle.
- **V39 authorization boundary**: no V39 ADR, config, model, or confirmation-set
  freeze was authorized by the four rejected diagnostics. ADR-0052 now
  precommits the successor: exact fixed-partner `task_id` intent raises the
  matching learned candidate's existing `duplication_risk` input to `1.0`
  without masking, redirecting, forcing, reordering, suppressing, or applying
  an action. ADR-0053 supersedes only final-set metadata; the behavior-identical live
  config SHA-256 is
  `54d76bb209ec31f24bc2711b208cb2995e6d538534ba0b99a150091596ccf924`.
  The value-free umbrella reserved dev-v35 for primary-only construction after
  the precommit. Dev-v34 remains retired;
  held-out-v5 is retired without outcomes after a legacy test manifest read;
  held-out-v6 is frozen value-free and unconsumed. Its receipt/membership hashes
  are `4f31a7078e5cd456...` / `2bf4aa04ef54d873...`. Dev-v35 is frozen value-free and
  unconsumed. M8.5 remains unmet. Implementation passes 198 Python tests,
  pinned Java, public/runtime/replay gates, and the revised 44/44 reward gate;
  the ignored report hashes to
  `f3365c5abdd30fb8f1f7731c245c4b00b15870f5f22839f65aab4a9ebdc5173e`.
- **V39 rejected at construction**: replica A completed all 32 updates but no
  checkpoint reached 9/10. Rank-best update 25 is 8/10, return
  `3.3231000000000073`, core `448.0`, idle `0.01845563475648595`; checkpoint /
  frontier hashes are `1af02875472f54a6...` / `181ed3e7069b429b...`.
  Replica B and scorecards are prohibited. Dev-v35 is retired unopened and
  unconsumed; held-out-v6 remains sealed and unconsumed.
- **V40 precommitted and implemented, not model-gated**: reusable/train-only diagnosis finds
  752 exact partner-intent teacher-label conflicts among 3,956 eligible warmup
  transitions, with 177 warmup and 734 rehearsal presentations. ADR-0054
  filters only those exact conflicts from teacher imitation; PPO policy/value,
  runtime, reward, model, roots, budget, and RNGs stay V39-exact. Config SHA is
  `230759e7e02dcca9...`. A value-free umbrella reserves primary-only dev-v36 in
  `[4B,5B)`. Implementation commit `c9459c58f4`, 208 Python tests, and the
  corrected bound diagnostic pass; report SHA is `4fe2960225d659cb...`. No
  membership, baseline, or model work exists.
- **V40 pretraining gates green**: pinned Java, public 5/5 survival with 10
  staging starts, focused wake/staging, smoke, accepted determinism digests,
  664-checkpoint/16,200-tick golden plus negative replay, and 44/44 exact-config
  reward adversaries pass. Reward report SHA is `9677e5caed4d891...`.
- **Dev-v36 frozen value-free**: the primary-only `[4B,5B)` freezer was
  committed at `54db674e2e` before construction. It reads no membership and
  emits no values. Membership/receipt hashes are `d4bfbcf88d99f4f...` /
  `fce63a49f80d165...`; dev-v36 and held-out-v6 remain unconsumed. The
  receipt-aware Python suite passes 212 tests without membership access.
- **V40 replica A passes construction**: from committed repository
  `c288483436`, the exact 256-warmup/2,048-PPO/32-update run selects update 28
  at 10/10 reusable wins, return `7.77414`, core `656.3`, and idle
  `0.008388499062201467`. Checkpoint SHA is `9ff618797d8ae593...`; fresh replay
  is bit-exact at `5af990a3ec8ff7fb...`, with action-state/full-run digests
  `4f0726c7dc8f127...` / `b6dd3c958762c082...`. Replica B is authorized;
  dev-v36 and held-out-v6 remain unopened/unconsumed.
- **V40 replicas and direct lineage are exact**: Replica B independently
  reproduces update 28, 10/10 wins, every mean, all 32 checkpoint files,
  warmup, checkpoint/model, replay, action-state, and full-run evidence. The
  canonical comparator passes. Direct lineage digest/artifact SHA are
  `cfb0ec1b21fd49fb...` / `5fdc3bdabf24ee5e...`. Fresh selected-only permanent
  baselines and reusable dual scorecards are next; dev-v36 and held-out-v6
  remain unopened/unconsumed.
- **V40 rejected at reusable scorecards**: fresh permanent random/greedy are
  4/10 and 8/10; candidate 10/10 and matched random/greedy 5/10 and 6/10 pass
  every observed win comparison. Permanent-greedy announcements and idle and
  matched-greedy recovery remain uncertain, so both frozen scorecards fail.
  Report SHA is `8453b0c4b75cd681...`. Dev-v36 is retired unopened/unconsumed;
  held-out-v6 stays sealed/unconsumed. No confirmation/final episode ran.
- **V41 midpoint rejected at reusable scorecards**: canonical
  reusable diagnosis shows V40 updates 25/26/28 all 10/10 and all fail the same
  three scorecard rows; updates 25 and 26 have complementary idle outliers.
  ADR-0055 fixes one
  50/50 aligned-state midpoint with exact A/B parent constructions. Config /
  umbrella hashes are `c4705974f18512a...` / `7ce8f5cf640978ef...`. The reward
  adversary passes 44/44 (`995d9db2f866d5f2...`). Dev-v37 is frozen value-free
  and unopened in `[5B,6B)` with membership/receipt hashes
  `7874f5abaf230665...` / `277264b80c6456f7...`; held-out-v6 remains sealed.
  A/B construction under pinned WSL Torch 2.12.1 is byte-exact at checkpoint
  `b6b5e98ddee56740...`, model state `93594bd64193740a...`, and canonical
  lineage `37c4b1e571fca96c...`. Fresh permanent random/greedy are 4/10 and 8/10;
  the midpoint is 10/10 and matched random/greedy are 5/10 and 6/10, so every
  observed win comparison passes. Permanent-greedy idle and matched-greedy
  recovery remain uncertain; report SHA is `ca7b39c84a9f51d1...`. V41 is
  rejected before confirmation. Dev-v37 is retired unopened/unconsumed;
  held-out-v6 remains sealed/unconsumed.
- **V42 relabel implemented; pretraining boundary green**: public trace
  diagnosis closes learned WAIT-logit and danger-label interventions. The exact
  optimizer-free teacher diagnostic reproduces V40's 752 conflicts and finds
  deterministic nonconflicting alternates for 682, including all 256 tick-zero
  conflicts and 174/189 successful-corpus conflicts; 70 retain V40 fallback
  filtering. ADR-0056 freezes adaptive-preference-preserving relabeling across
  warmup, rehearsal, and generic PPO teacher imitation without changing runtime
  actions, masks, reward, model, roots, budget, or RNGs. Config/umbrella hashes
  are `3fcb0c8800c638a3...` / `c1644d2dd6dde231...`. Dev-v38 is frozen
  primary-only and unopened in `[6B,7B)`. The production/test
  packet keeps original/effective labels separate and implements all three
  generic teacher paths plus deterministic telemetry. Its live diagnostic
  reproduces 752 conflicts, 682 relabels, and 70 fallbacks; report/payload/
  action-state hashes are `83f8dd6904e5356d...` / `e92436ffb3773b80...` /
  `0e609742ba171c60...`. The 2026-07-23 boundary passes 243 Python tests, Java,
  public policy (5/5, 10 proactive starts), both focused coordination checks,
  smoke, determinism, the 664-checkpoint/16,200-tick golden and negative replay,
  and all 44 exact-config reward adversaries (`272ac291ef143fa6...`). Freezer /
  freeze commits are `3e328ce91e` / `949b73f987`; membership/receipt hashes are
  `3f4b0d012cf87303...` / `fea431ae993d1072...`. The receipt records zero reads
  and no emitted values, and the full suite now passes 279 tests. Independent
  replicas from training commit `12980ee2b9` both select update 2 at 9/10 wins,
  return `4.73976`, core `568.8`, and idle `0.03455784384563236`; all 32
  checkpoint files match. Checkpoint/model/replay/action-state/full-run hashes
  are `65f8e3dc3a41bf89...` / `4363617f8535bc8b...` /
  `d01d0dfe425d1b0d...` / `52751513f785c196...` /
  `cb719361da11ab6c...`. Direct lineage digest/artifact hashes are
  `b1dbf1abc6a7dacd...` / `100945a4820b2039...`. Fresh permanent random/greedy
  are 4/10 and 8/10; candidate is 9/10 and matched random/greedy are 5/10 and
  6/10, so every win comparison passes. Both frozen scorecards still fail:
  permanent-greedy announcements and idle and matched-greedy recovery remain
  uncertain. Records/aggregate/report hashes are `e0a78468268bc021...` /
  `dae12fbf3868c6cc...` / `01bf941060bc7e6f...`. V42 is rejected before
  confirmation. A no-authority public build-line-prior diagnostic makes all ten
  openings nonconflicting and fixes idle, but remains 9/10 and still fails
  permanent announcements and matched recovery. Records/report hashes are
  `6ccd6ac543d43891...` / `41e3b71b133f4c63...`. No V43 is authorized; dev-v38
  is retired unopened/unconsumed and held-out-v6 remains sealed/unconsumed.
- **V43 architecture successor precommitted**: ADR-0060 identifies the v1
  actor's missing candidate-set context: SELECT logits cannot compare against
  other candidates and CONTINUE/WAIT cannot see the catalog. V43 changes only
  model architecture, adding masked other-candidate context to SELECT and
  masked all-candidate context to CONTINUE/WAIT. Runtime authority, features,
  reward, teacher path/relabeling, roots, budgets, optimizer, RNG values,
  scripted seats, and engine pins remain V42-exact. Config/umbrella hashes are
  `29b4430839451f13...` / `99851aa2cdbfb469...`. Dev-v39 is reserved
  primary-only in `[7B,8B)` and remains unconstructed; dev-v38 remains retired
  without a read and held-out-v6 remains sealed. Implementation and the full
  pretraining boundary are next; no model or restricted membership work is yet
  authorized.
- **V43 implementation boundary green**: the config-selected v2 actor, masked
  set pooling, dynamic checkpoint schema, and training/replay/lineage/preflight/
  final plumbing are implemented with v1 compatibility. The boundary passes
  293 Python tests, pinned Java, public 5/5 survival with 10 staging starts,
  secondary-claim and owned-schematic checks, smoke, deterministic golden and
  negative replay, and all 44 exact-config reward adversaries (report SHA
  `3e3210447ff4f428...`). Dev-v39 remains unconstructed; no V43 training episode
  or restricted membership read has occurred.
- **V43 freezer implemented, not executed**: the primary-only dev-v39 freezer
  validates exact config/umbrella hashes, paths, identity, count, `[7B,8B)`
  namespace, and the sealed-final binding, then atomically writes membership and
  a value-free zero-read receipt. All 298 Python tests pass. The tool must be
  committed before it can execute; dev-v39 remains unconstructed.
- **Dev-v39 frozen value-free and committed before training**: committed freezer
  `5007a7b9f3` created the 160-root set solely in `[7B,8B)`. Membership SHA is
  `0b88fda1b37647aa...`; the value-free receipt records zero document reads and
  no emitted values. Commit `df7723c6cb` froze the membership/receipt packet
  before replica A; dev-v39 remained unconsumed.
- **V43 exact replicas complete; reusable gate rejects**: both pinned runs
  select update 27 at 10/10 wins and mean idle `0.00874233`; all 32 checkpoints
  and canonical evidence match. Checkpoint/replay/full-run hashes are
  `b4cc691ad0c08d67...` / `12ed6b616310deb7...` /
  `66385a8f85ec7db7...`; lineage is `1f07166a5d27aa30...`. Permanent
  random/greedy are 4/10 and 8/10; matched random/greedy are 5/10 and 6/10.
  Permanent recovery now passes decisively, but permanent announcements/idle
  and matched recovery remain uncertain. Report SHA is `10f829a54a110507...`.
  V43 is rejected; dev-v39 is retired unopened/unconsumed and held-out-v6 stays
  sealed.
- **V44 temporal successor precommitted**: ADR-0061 freezes one-boundary
  structured memory: 56 prior scalars, a masked 37-value prior candidate mean,
  prior candidate-count fraction, and a ten-way submitted-action one-hot. The
  V43 set actor remains intact with a 160-input scalar encoder. Config/umbrella
  hashes are `9a23c90567754eb8...` / `4a526274d9568726...`. Dev-v40 is reserved
  in `[8B,9B)` but unconstructed; implementation and the complete public/
  pretraining boundary are next. Dev-v39 remains retired without a read and
  held-out-v6 remains sealed.
- **V44 implementation boundary green**: config-selected v1/v2/v3 features and
  models, immutable/reset-local lag snapshots, and feature+model identity across
  checkpoints, manifests, lineage, preflight, and final evaluation are wired.
  The boundary passes 305 Python tests, pinned Java, public 5/5 survival with ten
  staging starts, both focused checks, smoke, deterministic golden/negative
  replay, and 44/44 exact-config reward adversaries (SHA
  `740aba578809911...`). Dev-v40 remains unconstructed; no V44 training episode
  or restricted membership read has occurred.
- **V44 freezer implemented, not executed**: the primary-only dev-v40 freezer
  validates exact config/umbrella hashes, paths, identity, count, `[8B,9B)`
  namespace, and sealed-final binding, then atomically writes membership and a
  value-free zero-read receipt. All 310 Python tests pass. The tool must be
  committed before it can execute; dev-v40 remains unconstructed.
- **Dev-v40 frozen value-free; packet not yet committed**: committed freezer
  `6b7a6c5dca` created the 160-root set solely in `[8B,9B)`. Membership/receipt
  hashes are `05ca1f48227581fc...` / `acffc919ab1c40e2...`; the value-free
  receipt records zero document reads and no emitted values. Dev-v40 remains
  unconsumed. Commit this packet before replica A.
- **V44 exact replicas complete; reusable gate rejects**: both pinned runs
  select update 1 at 9/10 wins and mean idle `0.07252724`; all 32 checkpoints
  and canonical evidence match. Checkpoint/replay/full-run hashes are
  `4e51d31bd4f33a67...` / `a5ac208b8ea91f19...` /
  `029e77830406127a...`; lineage is `aa799280368304ae...`. All observed win
  comparisons, matched announcements, and permanent recovery pass, but
  permanent idle decisively regresses and permanent announcements/duplicates
  plus matched duplicates/idle/recovery remain uncertain. Report SHA is
  `260625f302f3e268...`. V44 is rejected; dev-v40 is retired unopened/unconsumed
  and held-out-v6 stays sealed.
- **V45 residual-temporal successor precommitted**: ADR-0062 preserves V43's
  current-state set actor and adds V44's lag only through separately encoded,
  zero-initialized residual logits. Config/umbrella hashes are
  `a7d0c8029acebe79...` / `e4fe0b56a95fa64c...`. Dev-v41 is reserved in
  `[9B,10B)` but unconstructed; implementation and the public/pretraining gate
  are next. Dev-v40 remains retired without a read and held-out-v6 stays sealed.
- **V45 implementation boundary green**: the v4 actor is V43-exact at
  construction, adds separately encoded zero-output residual heads, and retains
  the current-state critic. The embargo-safe 273-test suite, pinned Java,
  public 5/5 gate, focused checks, smoke, golden/negative determinism, and 44/44
  reward adversaries pass (`84cd359cf9cbd401...`). The 43 scenario-variation
  tests remain last green before dev-v40 freeze and are not rerun because they
  glob-read retired membership. Dev-v41 remains unconstructed; no V45 training
  or restricted read has occurred.
- **V45 freezer implemented, not executed**: the primary-only wrapper binds the
  reviewed atomic helper commit, validates exact V45 hashes/paths/identity/
  `[9B,10B)` namespace/sealed binding, and writes membership plus a value-free
  receipt. The embargo-safe suite passes 277 tests. Commit the freezer before
  execution; dev-v41 remains unconstructed.
- **V45 confirmation packet frozen, unconsumed**: the committed freezer wrote
  dev-v41 without emitting or reading membership. Membership/receipt hashes are
  `591513526bdd0bce...` / `d2d14a281d37a046...`; the receipt records zero
  membership-document reads. Do not consume it before both reusable scorecards
  pass.
- **V45 rejected before confirmation**: exact replicas select update 32 at
  10/10 wins, core `730.1`, idle `0.00873637`, checkpoint
  `cdc526403cd1fe27...`, and full-run `f253cd6dbb1c0f5c...`. All four win gates
  pass, but permanent announcements/idle and matched recovery remain favorable
  yet uncertain; report SHA is `ea7466a45d91d415...`. Root 2004's 65 WAITs are
  all forced after the only legal teacher-agreed defense action, so another
  selector-memory coordinate is not supported. Dev-v41 is retired unopened/
  unconsumed and held-out-v6 remains sealed.
- **Full Python suite restored without embargo access**: scenario-variation
  disjointness now reads only explicit legacy/public memberships (fixed/train,
  dev-v1..v33, held-out-v1..v4). Governed replacements remain receipt/existence
  checks only. The focused module passes 44 tests and the full suite passes 322;
  no dev-v34..v41 or held-out-v5/v6 membership was read.
- **V46 control expansion precommitted**: with explicit owner authorization,
  ADR-0063 adds one learned `DEFER_TO_SCRIPTED_EXPERT` policy index translated
  to the already-computed canonical adaptive-v1 action. It cannot override
  forced safety/lifecycle actions or duplicate expert WAIT. The V45 ordinary
  actor/critic stays exact, teacher losses stay on actions 0..9, and mean DEFER
  above 25% is ineligible. Config/umbrella hashes are
  `b588ee43e66bd9d...` / `a78631d7ba9f1cd2...`; dev-v42 is reserved in
  `[10B,11B)` but unconstructed.
- **V46 implementation/pretraining boundary green**: feature v3 and control v2
  expose DEFER only for legal unforced non-WAIT expert proposals; effective
  ordinary actions drive history and server submission. Model v5 preserves
  V45's ordinary logits/masks/value bit-exactly at initialization and adds a
  zero-output expert-conditioned DEFER head. Teacher losses remain actions
  0..9, while validated checkpoint/reusable/confirmation/final telemetry caps
  mean DEFER at 25%. Thirteen focused tests and the full 335-test embargo-safe
  suite pass, along with pinned Java/custom modules, public 5/5 and ten staging
  starts, both focused checks, smoke, deterministic golden/negative replay, and
  44/44 exact-config reward adversaries (report
  `ec3acb4c1056207...`). Dev-v42 remains unconstructed and no V46 training or
  restricted membership read has occurred.
- **V46 freezer implemented, not executed**: the primary-only generator reuses
  committed atomic/no-read primitives and binds the exact implementation,
  config, umbrella, `[10B,11B)` namespace, and held-out-v6 contract. Its receipt
  is value-free; 339 embargo-safe Python tests pass. Commit the freezer before
  constructing dev-v42.
- **V46 confirmation packet frozen, unconsumed**: the committed freezer created
  dev-v42 without emitting or reading membership. The value-free receipt binds
  membership `8f518384f19c193f...`, generator `e9a828a7d01ed7e9...`, and
  implementation `173cd5c2a11f3237...`, with zero membership reads. Do not
  consume dev-v42 until exact replicas and all reusable scorecard/control gates
  pass. The receipt-aware embargo-safe suite passes 340 tests.
- **V46 exact replicas complete**: both pinned runs select update 32 at 10/10
  public-dev wins, return `7.22016`, core `639.2`, idle `0.01033305`, and DEFER
  `0.18420177`. Checkpoint/model/replay/full-run prefixes are
  `93694e4d70ec56e4...` / `70c762f358ae8cce...` /
  `493ab925a384ccec...` / `8d61abfa4ce4fe10...`, and complete manifests compare
  exactly. Direct lineage correctly failed closed on a missing expected control
  coordinate; the validator now binds control v2 and all 341 tests pass.
  Reusable gates are next; dev-v42 remains unconsumed.
- **V46 rejected before confirmation**: canonical lineage is
  `b6322349e4d14b31...`. Fresh permanent random/greedy are 4/10 and 8/10;
  matched random/greedy are 5/10 and 6/10; V46 is 10/10 and its mean DEFER
  `0.18420177` passes. Both scorecards still fail uncertainty: permanent
  announcements and idle, plus matched recovery. Report SHA is
  `2af00337138b9939...`. Dev-v42 is retired unopened/unconsumed and held-out-v6
  remains sealed.
- **Reusable-scorecard power correction precommitted**: the ignored no-DEFER
  ablation remains 10/10 and fails nearly identical confidence rows (report
  `109d0bd5ef8ca177...`). With explicit owner authorization, ADR-0064 keeps the
  strict zero-crossing rule but replaces the underpowered ten-root reusable
  scorecard with one precommitted 160-root public screen in `[11B,12B)`. The
  exact V46 checkpoint is frozen and gets no retraining/reselection. Dev-v43 is
  reserved in `[12B,13B)` but unconstructed; dev-v42 remains retired unopened,
  and held-out-v6 remains sealed. Commit the ADR/umbrella/generator before
  constructing public reusable-v2 membership.
- **Reusable-v2 membership frozen, unevaluated**: precommit `26d25acd64`
  preceded deterministic construction of 160 public roots. Membership SHA is
  `c529951782ec0426...`; the receipt records zero restricted membership reads
  and zero episodes. Commit membership/receipt/tests/docs before baseline or
  candidate evaluation.
- **V46 rejected on reusable-v2**: fresh permanent random/greedy win 62/160 and
  84/160; V46 wins 96/160 and matched random/greedy win 69/160 and 67/160.
  DEFER passes at `0.22788814` and all matched scorecards pass. Permanent
  announcements remain uncertain (`-0.00016845`, CI
  `[-0.00413065,+0.00377476]`) and idle is unfavorable (`+0.00391218`, CI
  `[-0.00166438,+0.00971554]`). Preflight SHA is `d272edd51197166b...`.
  Dev-v43 remains unconstructed; held-out-v6 remains sealed. Diagnose any V47
  coordinate only from the public 160-root records.
- **V47 single-brain death failover implemented**: public traces show early
  seat-0 death on 63 roots with idle/announcement gaps `+0.02701331` /
  `+0.00769989`, versus favorable gaps after late death. All 30 greedy-only wins
  contain a seat-0 death; the fixed learned seat is then forced to WAIT.
  ADR-0065 keeps exactly one sticky learned controller and transfers it only
  when dead to the lowest-ID living seat, with history reset and dynamic
  nonactive partner intent. Config/umbrella hashes are
  `ff112f910c13603c...` / `8e6fccc9d07de4ef...`. Dev-v43 is cancelled without
  construction; dev-v44 is reserved in `[13B,14B)` but unconstructed. The
  adapter, matched controls, lineage, and promotion gates are implemented. A
  repeatable public JVM gate transfers `0->1->2` at ticks 2738/4462, keeps one
  learned seat, and wins at tick 9000. The full 348-test Python suite, pinned
  Java, public/focused/smoke/determinism gates, and 44/44 reward adversaries
  pass (report `5e6aec4530d27823...`). Commit this implementation boundary
  before implementing the dev-v44 freezer; no V47 training has run.
- **Current branch**: `coop-agent/v159.7`
- **Agent workflow**: project work is primary-agent-only. Do not spawn, fork,
  create, or use subagents for any task; see the protected user-owned
  `AGENTS.md` source of truth.
- **M10.3 capture substrate**: local capture is explicit opt-in via
  `DEMO_CAPTURE_PATH`; `bash scripts/human-session-check.sh` runs the no-port
  capture/digest/control-replay/style/profile gate. The verified probe produced
  504 records with 84 trajectory boundaries and 16/16 applied controls. The
  historical v1 content/control digests are `3e864f35ffc3cf3c...` /
  `d30d529355b07ce1...`. Capture v3 added the project commit and canonical plugin/
  server runtime-content hashes; current v4 retains them and binds agent and
  experiment conditions. Legacy v1/v2/v3 remains loader-readable, but v1/v2 is
  evidence-ineligible. V2 whole-JAR hashes exposed volatile upstream
  `version.properties`; v3 normalizes only its comment/`buildDate` and hashes
  all stable fields/content. Two fresh JVMs from committed implementation
  `c19e652324` reproduce session/control digests `7a2c68e638e9fff3...` /
  `d30d529355b07ce1...` plus plugin/server content hashes
  `faca436f81b865bd...` / `e02c4208749ee2ed...`. The
  five deterministic partner profiles are staged in
  `configs/partners/human-scripted-v1.json`, but must not be activated in
  training until M8 promotion authorizes M9. See `docs/HUMAN_SESSIONS.md`.
- **M10.4 scorecard substrate**: the same no-port gate now writes and validates
  an objective create-new scorecard with interventions, conflicts, yield
  latency, goal compliance, time-to-help, and announcement outcomes. Captured
  private join mode checks both output targets before opening the server and,
  after a normal exit, uses that same validator to write a sibling
  `.scorecard.unrated.json`. A separate `human_session_rating_v1` file must be
  human-entered and digest-bound before usefulness/preference/comparison fields
  are populated. `mindustry_agents.tools.human_rating` creates that file from
  four explicit answers, derives the digest from a validated capture, rejects
  extra fields, and refuses overwrite. The probe never fabricates ratings; its
  objective result is 5/83 intervention ticks, one
  zero-latency conflict, 1/1 eligible goal compliance, and 10/4 rendered/
  suppressed announcements. Real serious sessions remain pending.
- **M10 human-evidence governance**: ADR-0058 forbids pooling scorecards without
  their captures. `mindustry_agents.tools.human_evidence` reloads capture/rating
  pairs, rejects duplicate digests, groups exact runtime/scenario/policy pins,
  and counts only serious ratings toward the three-session floor. It never
  claims acceptance because rating v1 does not prove agents-present versus
  agents-absent preference. Legacy
  capture v1/v2 is excluded from the final-evidence floor; v3 requires exact
  project-commit and canonical runtime-content provenance. ADR-0059 and capture
  v4 now freeze the final comparison before collection: three counterbalanced
  absent/scripted/learned blocks, capture-time condition/order/seed assignment,
  six strict learned-versus-scripted objective non-regression targets, and
  direct learned-versus-absent owner preference. The dependency-free protocol,
  block-rating, and report validators are implemented. The real no-port absent
  gate passes with zero spawned agents and a valid five-boundary capture.
  Learned assignments fail closed until M8 promotion and M10.5; no final block
  has begun and the M10 checkboxes remain open.
- **Current V42 training identity**:
  `12980ee2b9e427d65be1883d014da6fc67a29c5a` (V40 training parents remain
  bound to `c288483436c1003d25dc64ce7aba968600d45f3a`).
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
| `make bootstrap` | Prints ENGINE_VERSION, Java/Python/Git versions, Gradle wrapper presence, pytest presence; resolves `python` on Windows or `python3` on stock Ubuntu; ends `bootstrap: OK`, exit 0. Clean Ubuntu verification passed at `43d3b17db6`. |
| `make build` | Builds `rl-server:dist` + the loadable `agent-plugin:dist`, then validates the Python package import; ends `build: OK`, exit 0. |
| `make test` | Runs the complete Python suite (287 with the locked runtime, or the 33-test stdlib core boundary without it), then the `agent-core` / `rl-server` JUnit suites and `agent-plugin` compile check. Literal clean-checkout Ubuntu execution passed at `43d3b17db6`; hosted Ubuntu run `29972868046` passed the locked install, full tests, and distribution build at `6b4afc4d3f`. |
| `make test-python` | With the locked dev/RL runtime, `pytest python/tests -q` runs all 287 tests. Without pytest, the script runs the governed 33-test stdlib-only core boundary under `python -S`; both paths pass. |
| `make human-session-check` | Runs the real server/plugin no-port capture-v4, control replay, style/profile, and objective-scorecard gate with three controlled agents. |
| `make human-absent-check` | Runs the real server/plugin no-port human-only condition, requires zero controlled units, validates a five-boundary capture-v4 and objective scorecard, and opens no network port. |
| `make verify-rl-boundary` | On Linux/WSL2 with uv 0.11.16 and Python 3.12, runs 33 core tests under `python -S`, reconstructs the 15-package hashed CPU environment in a temporary directory, and ends `RL-BOUNDARY OK`. Verified 2026-07-21. |
| `make training-gate` | On WSL2 with pinned `UV`/`JAVA`, reconstructs the RL environment, runs the 1/2/4-JVM shadow-inference collector gate, then 10,000 resets. Current 4-JVM result 375.1x real-time; zero reset drift/leak/orphans; ends `TRAINING-GATE OK`. Verified 2026-07-21. |
| `bash scripts/train-selector.sh` | Runs 27 reward adversaries, two independent train/dev PPO runs, two complete fresh-checkpoint replays, and exact manifest comparison. Current checkpoint `0b2bd8ac...`, full digest `56cc7b54...`, dev 0/10; ends `TRAIN-SELECTOR OK`. Held-out is not read. |
| `make test-java` | Runs the `agent-core` (108 tests) and `rl-server` JUnit suites plus the `agent-plugin` compile check; ends `test-java: OK`, exit 0. Verified 2026-07-23. |
| `make smoke` | Runs exact stepping + M3/M4 ledgers/combat/acceptance and M5.2–5.6 coordination/policy/reservation/chaos/announcement checks twice across fresh JVMs, plus omitted-defense loss checks. Ends `SCENARIO OK`, exit 0. Verified 2026-07-21. |
| `make determinism` | Runs the legacy 79-boundary cross-process replay, reset purity with deterministic unique episode IDs, seed sensitivity, then the checked-in golden (664 checkpoints / 16,200 ticks / two wins). Exit 0. Verified 2026-07-21; `REPLAY_NEGATIVE=1` also passes. |
| `make candidate-policy-check` | Runs the pure public greedy selector over all five pinned seeds; requires 5/5 wins through the ordinary candidate/mask/task-action seam. Verified 2026-07-23. |
| `make secondary-claim-wake-check` | Proves V35 wakes fixed scripted seat 1 after atomic claim loss while preserving learned-seat scheduling. Verified 2026-07-22. |
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

- **Passing**: 176 Python tests (`test_import.py`, `test_protocol.py` incl. M3–M7.6
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

1. **Commit V47's green implementation boundary.** Exclude the four protected
   user files. Dev-v44 must remain unconstructed until after this commit.
2. **Implement and commit the value-free dev-v44 freezer.** Bind the exact V47
   config/umbrella/implementation and `[13B,14B)` namespace; do not execute it
   until its no-read tests pass and the tool itself is committed.
3. **Construct dev-v44 value-free, then train exact V47 replicas.** Never read
   or render membership; commit the receipt packet before replica A.
4. **Run reusable-v2 before restricted confirmation.** Require replica
   reproducibility, direct lineage, >=9/10 construction wins, idle <0.25,
   DEFER <=0.25, and both unchanged 160-root scorecards.
5. **Keep held-out-v6 sealed and M9.1 gated.** Confirmation and final access
   remain conditional; M9 begins only after M8 promotion.

## Decisions

See `docs/decisions/ADR-0001..0061` (do not relitigate). ADR-0042 records V31's
reproducible rejection; ADR-0043 precommits and records the verified V32
actionability/staging runtime and its reusable rejection; ADR-0044 precommits
and records V33's targeted secondary-seat staging rejection before model work;
ADR-0045 precommits and records V34's all-seat claim-loss boundary rejection at
the complete public candidate gate; ADR-0046 precommits and records V35's exact
fixed-secondary-seat construction and reusable scorecard rejection; ADR-0047
records V36's collision-free build-line opening prior, green pretraining gates,
and rejection when replica A tops out at 7/10; ADR-0048 records V37's fixed
scripted-seat-2 harvest opening and reusable rejection; ADR-0049 retires the
membership-exposed but unexecuted dev-v33 and held-out-v4 sets; ADR-0050 records
V38's learned-seat-only proactive staging exposure, exact twins, and reusable
rejection; ADR-0051 accepts selected-only loading and runtime provenance while
retaining legacy registry mode only for diagnostic compatibility.
ADR-0050 also records the post-rejection closure of four parity-controlled,
reusable-only V39 diagnostics and the resulting prohibition on V39
ADR/config/model/freeze work pending primary-level design synthesis. ADR-0051
is unchanged. ADR-0052 records the completed synthesis and precommits V39's
structured fixed-partner intent as evidence in the existing duplication-risk
feature, without changing action authority. ADR-0054 records V40's narrow
teacher-conflict filter, green pretraining boundary, value-free dev-v36 freeze,
exact replicas, direct lineage, and reusable-scorecard rejection. ADR-0055's
V41 successor was frozen and constructed exactly, then rejected by both
reusable scorecards before confirmation. ADR-0056 precommits V42's exact
training-only teacher-conflict relabel with V40 filter fallback. ADR-0060
records V43's candidate-set-context actor, exact replicas, and reusable
rejection before confirmation. ADR-0061 precommits V44's bounded lagged-
boundary feature/model coordinate; implementation and the public/pretraining
boundary are next.

## Deviations from the brief in this scaffold

- `protocol/` is **not** a Gradle module. Per ADR-0004 the bootstrap transport is
  JSON; the schema lives in `docs/PROTOCOL.md` and `protocol.py`. Protobuf +
  generated bindings are deferred to Stage D. This avoids dead scaffolding.
- The brief's separate `tests/{determinism,integration}/` directory split is not
  used; real-JVM checks live behind `scripts/*.sh`. `tests/golden/` now contains
  the checked-in complete M6 replay trace.
