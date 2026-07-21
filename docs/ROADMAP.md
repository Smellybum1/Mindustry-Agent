# Roadmap

Milestones M0–M10 from brief §25, as trackable checklists with exit criteria.
Checkboxes reflect **truthful** current state (date 2026-07-20). A box is ticked
only when its exit criterion is genuinely met.

Anchors used by `scripts/*.sh` and the Makefile are the GitHub-style slugs of the
milestone headings.

---

## Milestone 0: Repository and reproducible build

Deliverables:
- [x] Fork initialized with `upstream` remote (branch `coop-agent/v159.7`)
- [x] Exact engine tag/commit pinned in `ENGINE_VERSION`
- [x] JDK 17+ build verified (JDK 21, `--release 17`; `./gradlew rl-server:classes`
      and `:dist` green through the full `:core` kapt pipeline, 2026-07-20)
- [x] Server build command verified (`./gradlew server:dist` green; jar boots
      headless and shuts down cleanly, 2026-07-20)
- [x] Python project created (`python/pyproject.toml`, zero-dep core)
- [ ] Python lockfile created
- [x] `AGENTS.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `STATUS.md`, `HANDOFF.md`
- [ ] CI builds Java and runs basic Python tests
- [x] One-command bootstrap for reference runtime (`make bootstrap` / `scripts/bootstrap.sh`)

Exit criteria:
- [ ] Fresh checkout can run `make bootstrap` and `make test` (bootstrap ✔;
      `make test` runs Python tests ✔, Java tests pending)
- [x] Build does not depend on an unpinned `latest`
- [x] Current upstream modifications are zero or documented (`docs/UPSTREAM_PATCHES.md`)

## Milestone 1: External-step technical spike

Deliverables:
- [x] `rl-server` launcher (real headless launcher; `mindustry.rl`)
- [x] Fixed delta (`FixedStepGraphics` pins `1/60 s`; `state.tick` +1.0/update)
- [x] Health/handshake
- [x] Reset (in-code 48×48 scenario, repeated resets without JVM restart)
- [x] Step N ticks (exact advance)
- [x] Minimal observation (tick/wave/copper/lead/units/buildings/core-health/done)
- [x] State hash (canonical SHA-256, sorted-by-id, 1e-3 float quantization)
- [x] Tiny scenario load

Exit criteria:
- [x] `make smoke` starts one JVM, resets, steps 600 ticks, exits successfully
      (`bash scripts/smoke.sh` → exit 0)
- [x] Tick count is exact (verified 0→600 in 10×60 chunks)
- [x] Same seed/action trace produces matching hash (two fresh JVMs + two
      in-JVM resets identical; `bash scripts/determinism.sh` → exit 0). NB (M1):
      no RNG/time-driven state, so the *seed* lever was not yet exercised — **now
      resolved** by the bootstrap-defense-v0 loader: enemy waves make different
      seeds diverge post-wave while same-seed stays identical (determinism check 4).
- [x] Timing report is emitted (`{engine_ms, observation_ms, ...}` per step)

**First major go/no-go gate — PASSED (2026-07-20).**

## Milestone 2: Persistent reset and process pool

Deliverables:
- [x] Persistent process (`process/supervisor.py` — pool of long-lived JVMs)
- [x] Repeated in-memory reset (`tools/stress_reset.py` — 1000 resets, no restart)
- [x] Python process supervisor (`ProcessSupervisor`: ports, seeds, logs,
      handshake verify, crash detect + auto-replace, clean shutdown via
      atexit + context manager)
- [x] PettingZoo skeleton (`env/parallel_env.py` `MindustryParallelEnv`,
      duck-typed ParallelEnv surface; `env/client.py`, `env/vector.py`)
- [x] Multi-JVM benchmark (`tools/benchmark.py` — 1/2/4 JVMs)
- [x] Leak/stability test (`tools/stress_reset.py` — RSS sampled, no leak)

Exit criteria:
- [x] 1,000 repeated resets pass (`bash scripts/stress-reset.sh` → exit 0; all
      1000 initial hashes identical; no leak)
- [x] Four or more environments step independently (`VectorCollector` steps a
      4-JVM pool in lockstep; see `docs/BENCHMARKS.md` M2 scaling)
- [x] Dead child process is detected and replaced (crash → truncation → respawn
      + re-handshake; unit-tested against a fake server, both crash and hang)
- [x] Performance baseline documented in `docs/BENCHMARKS.md` (M2 measurements)

**M2 caveats (truthful, as of M3):** per-agent observations and skill actions are
now **real** (M3 landed — see below); `MindustryParallelEnv`'s dict plumbing carries
them, though that facade's action-bundling shape still predates the M3 command schema
(training-layer adaptation deferred). Scaling is capped at 4 JVMs (shared host);
M8.3 later completed the 10,000-reset Gate 5; 8/16-JVM scaling remains outside
the accepted host cap.

## Milestone 3: Agent entities and first skills — DONE (verified 2026-07-20)

Deliverables:
- [x] Stable agent identities (`agentcore.AgentId`; `RlAgentRegistry` binds
      index → unit/controller, rebuilt per reset)
- [x] Controlled unit ownership (`alpha` units + `SkillController`; excluded from
      vanilla auto-control — see M3_DESIGN open-question 2)
- [x] Navigate, mine, deliver, wait skills (`agentcore.skill.*`, engine-free FSMs)
- [~] Action masks (per-agent array plumbed; still empty placeholders — real masks
      deferred until the action vocabulary grows)
- [x] Skill telemetry (per-agent `skill:{type,status,reason,progress,next_retry_tick}`
      in observations; `action_results[]` per action)

Exit criteria:
- [x] Scripted single agent mines and delivers copper (smoke: target 20 → carried
      21 → core +21, exact ledger). Seed variation is still trivial (no stochastic
      content until the full scenario loader — next issue) but the agent mines and
      delivers deterministically from the fixed start under any seed.
- [x] No teleporting or free-resource shortcuts (mining accrues via `MinerComp`;
      delivery routes through `Call.transferItemTo` gated by `acceptStack`; the
      core-copper ledger balances exactly)
- [x] Skill failure reasons are testable (`BLOCKED(INVALID_TARGET)` on a non-ore
      tile in the smoke; `STUCK`/`CORE_FULL`/`NO_CORE` in the 13 JUnit FSM tests)

## Milestone 4: Build and defence skills

Design: **docs/M4_DESIGN.md** (approved; open questions 1–5 there must be
resolved against source and recorded in place, M3-style). Issue-sized items
below; implement in order — 4.1/4.2 unblock everything else.

### 4.1 Dynamic re-path determinism (prerequisite)
- **DONE (verified 2026-07-20):** thread-less `Pathfinder.syncUpdate()` consumes
  pending tile-change refreshes without the `Time.millis()` gate. The extended
  determinism trace places a copper wall at `(33,24)` after wave 1 spawns and
  matches all 73 hash boundaries across two fresh JVMs while daggers continue
  around the changed tile. Normal threaded play is untouched; ControlPathfinder
  remains out of scope.
- Objective: building/destroying blocks mid-episode must not break cross-process
  determinism. `Pathfinder`'s tile-change refresh is gated by `Time.millis()`
  in `afterGameUpdate` (see docs/UPSTREAM_PATCHES.md entry 2 caveat) — neutralize
  for the sim-thread `syncUpdate()` path (extend the existing patch minimally or
  bypass the gate when thread-less; keep normal-mode behaviour untouched).
- Files: `core/src/mindustry/ai/Pathfinder.java` (patch entry 2 amendment),
  `rl-server` caller, docs/UPSTREAM_PATCHES.md.
- Acceptance: determinism.sh extended with a trace that PLACES a wall in the
  lane after wave 1 spawns (via a temporary direct placement hook or the 4.3
  build skill once ready) → identical hashes across two JVMs while daggers
  re-route around it.
- Excludes: ControlPathfinder (still unused by our units).

### 4.2 AgentBody port + BuildBlock skill (S1)
- **DONE (verified 2026-07-20):** engine-free `BuildBlock` + `AgentBody` build
  primitives, live `BuilderComp` adapter, whitelisted `BUILD` action, typed
  `RESOURCES_SHORT`/`OCCUPIED`/`OUT_OF_RANGE`/`PLAN_REMOVED` outcomes, five new
  FSM tests (82 JUnit total), and a live smoke ledger. A Duo consumes exactly 35
  core copper; an underfunded Duo consumes only the available 34 then blocks at
  zero. The temporary M4.1 placement hook has been removed.
- Objective: `BuildBlock(block,x,y,rotation)` per M4_DESIGN S1 — enqueue
  BuildPlan, engine consumes core resources and constructs; typed BLOCKED
  reasons (RESOURCES_SHORT via progress-stall detection, OCCUPIED, OUT_OF_RANGE).
- Files: `agent-core/src/**/skill/` (FSM + AgentBody build primitives),
  `rl-server` SkillController (BuilderComp bridging), ActionDecoder (`BUILD`),
  docs/PROTOCOL.md (additive).
- Acceptance (integration): build one Duo from core stock — core copper
  decreases by exactly the Duo cost (cite Blocks.java; STRATEGY_NOTES says 35),
  building exists at full health; BLOCKED(RESOURCES_SHORT) reachable by
  draining the core first. FSM unit tests with stubbed body (M3 pattern).
- Depends: 4.1 (hash stability once blocks change pathing).

### 4.3 ExecuteSchematic (S2) + east_duo_v1 data
- **DONE (verified 2026-07-20):** `ExecuteSchematic` sequences the data-backed
  seven-block layout through legal `BuildBlock` plans, reports monotone aggregate
  progress, and propagates typed inner failures. The live smoke completes two
  Duos plus five walls for exactly 100 copper; the cross-process trace reproduces
  all 78 hash boundaries. One new FSM test brings the Java total to 83.
- Objective: ordered BuildBlock list from
  `scenarios/schematics/east_duo_v1.json` (new; single source of truth; layout
  per docs/SCENARIOS.md east defence: 2 Duos + copper walls, turrets first).
- Acceptance: schematic completes on a fresh episode; progress reported as
  completed/total; determinism with the build trace; cost ledger balances
  (sum of block costs).
- Depends: 4.2.

### 4.4 SupplyBuilding (S3)
- **DONE (verified 2026-07-20):** engine-free `SupplyBuilding` withdraws through
  `Call.takeItems`, deposits through `Call.transferItemTo`, exposes actual delivered
  and target-stock telemetry, and reports typed `CORE_SHORT`/`CARGO_MISMATCH`
  blocking. Five FSM tests bring the Java total to 88. Live smoke supplies both
  schematic Duos with 15 copper each: both reach 30 ammo units, core copper drops
  by exactly 30, and both unit cargo stacks end empty. The expanded trace matches
  all 79 hashes across fresh JVMs.
- Objective: withdraw copper from core via the legal reverse path (resolve
  M4_DESIGN open question 2 — cite the call), carry, `transferItemTo` the
  turret; `SUPPLY {x,y,item,amount}` action; BLOCKED(CORE_SHORT) reachable.
- Acceptance: supply 30 copper across the two built Duos — each empty Duo legally
  accepts 15 copper as 30 ammo units (`maxAmmo=30`, copper multiplier 2), core
  copper −30 exactly, both agents cargo 0; ledger printed in smoke. The original
  singular-Duo wording was impossible under the pinned engine's capacity rule.
- Depends: 4.2 (needs a turret to exist).

### 4.5 RebuildRegion (S4)
- **DONE (verified 2026-07-20):** `RebuildRegion` snapshots `TeamData.plans` by
  explicit queue index (stable newest-first engine order), re-enqueues the saved
  block/rotation/config through legal `BuildPlan` construction, and propagates
  `BuildBlock` failures. Three FSM tests bring the Java total to 91. Live smoke
  builds a spawn-tile wall for six copper, wave 1 destroys it at tick 2700, then
  the skill clears that exact ghost plan and charges exactly six copper again.
  Standing damaged-block healing remains explicitly unsupported for alpha units.
- Objective: re-enqueue broken-block plans within a rect from the team's
  broken-block queue (resolve open question 3: field + iteration order);
  "repair" of standing damaged blocks is explicitly OUT (alpha cannot heal —
  scenario v1 adds a Mender instead).
- Acceptance: wave destroys a wall → RebuildRegion restores it, cost paid
  again from core, ledger balances; SUCCEEDED when rect has no broken blocks.
- Depends: 4.2; waves (done).

### 4.6 DefendRegion (S5) + EmergencyRetreat (S6)
- **DONE (verified 2026-07-20):** `DefendRegion` holds a world anchor, selects
  the nearest targetable enemy by squared distance then lowest engine unit id,
  and delegates range/prediction/aim/fire gates to `AIController.updateWeapons()`.
  `EmergencyRetreat` clears the native build queue, ceases fire, preserves cargo,
  and returns to the core. Four FSM tests bring the Java total to 95. Live smoke
  proves a queued plan is cancelled and an alpha-attributed bullet event precedes
  a dagger health drop (450 -> 443). The 79-boundary replay includes combat and
  matches across fresh JVMs. Weapon spread/pitch RNG uses the globally seeded
  `Mathf.rand` stream; the source audit is recorded in `M4_DESIGN.md`.
- Objective: per M4_DESIGN — anchor + radius, deterministic target selection
  (nearest, tie-break lowest unit id), engine handles aim/fire legality;
  RETREAT cancels plans and returns to core.
- Acceptance: defending agent within the lane damages daggers (enemy HP drops
  attributable in the event log); determinism holds with combat in the trace
  (weapon RNG must derive from seeded sources — audit `Weapon`/bullet spread
  RNG, document; if wall-clock or entropy-seeded, fix via the same seeding
  discipline as reset).
- Depends: 4.1; scenario waves (done).

### 4.7 Protocol/observation/hash closure
- **DONE (verified 2026-07-20):** agent observations expose ordered queue depth,
  current first-plan identity, and live progress; team observations expose the
  broken-block count and an ID-sorted turret summary with native `totalAmmo`.
  The canonical hash now includes every unit's build plans in queue order, every
  active team's broken-block plans in queue order (including removal markers),
  and turret ammo. Python adds typed plan/turret observation records and a
  round-trip test (30 pytest total). Live checks observe plan progress 0.000 ->
  0.056 before retreat and both supplied Duos at 30 ammo; deterministic replay
  remains the cross-process proof for the expanded hash.
- Objective: per-agent build-queue depth + plan progress in observations; team
  broken-block count; turret ammo in team/building summary; hash gains ordered
  build plans, broken-block queue, turret ammo (M4_DESIGN §Hash).
- Acceptance: docs/PROTOCOL.md updated; protocol.py dataclasses + tests;
  hashes perturb deterministically under build/supply traces.

### 4.8 M4 acceptance run
- **DONE (verified 2026-07-20):** `scripts/smoke.sh` runs a dedicated live M4
  acceptance. One alpha mines/delivers 21 copper, builds all seven ordered
  `east_duo_v1` entries plus 23 legal wall reinforcements, supplies both Duos
  with 15 copper / 30 ammo each, issues `DEFEND`, and clears wave 1 at tick 3271
  with core health exactly 1100. The balanced ledger is copper 250 + 21 mined -
  100 schematic - 138 reinforcement - 30 ammo = 3. A reset with defense omitted
  still loses at tick 3450. The full build+supply+combat determinism trace matches
  all 79 boundaries; stress-reset passes 1000 resets with zero hash mismatches
  (median 0.94 ms, p95 1.87 ms) and no leak.
- Objective: scripted single agent builds east_duo_v1, supplies both Duos, and
  the team survives wave 1 with the core untouched (SCENARIOS.md arithmetic
  (a)/(b) finally demonstrated in-engine); a second run with defence omitted
  still loses (regression of the loss path).
- Acceptance: new `scripts/`-wired check (extend smoke or scenario_check);
  determinism.sh green with the full build+supply+combat trace; stress-reset
  green (registry/plan cleanup across resets).
- Exit criteria (brief): scripted agent builds and supplies a Duo ✔; defends a
  marked lane ✔; skills survive repeated reset tests ✔.

## Milestone 5: Coordination and announcements

Head start: the engine-independent contract board is **already implemented and
tested** (`agentcore.{board,task,reservation,event,announce,utility}`, 64+ JUnit
tests, docs/COORDINATION.md). M5 is adapter + policy work, not board work.
The board lives on the sim thread inside rl-server (single-threaded by
contract); Python sees it only through the protocol.

### 5.1 Candidate task generator
- **DONE (verified 2026-07-20):** `agentcore.candidates` expands a fixed-order,
  maximum-eight catalog from immutable boundary snapshots, sorts repeated turret
  targets by engine ID, preserves `WAIT` as the final fallback, and emits typed
  capability/range masks. Scenario parsing now exposes objective IDs and
  thresholds, named regions, ore-patch IDs, and the reference schematic anchor;
  the sim-thread `EngineCandidates` adapter supplies live core, footprint, ammo,
  rebuild, wave, and enemy facts. `EngineFeatureSource` feeds deterministic
  distance/deficit/danger values to `HandTunedUtility`. Five synthetic JUnit
  tests prove byte stability, ordering, bounds, and both mask types. Live smoke
  proves initial harvest/build/wait, post-build turret supply, post-supply removal,
  aligned masks, and wave-time defense candidates.
- Objective: deterministic generator producing a bounded list of valid
  `TaskSpec`s per agent per decision boundary, driven by scenario objectives +
  world state (brief §10.4): mine-when-core-below-threshold, build east_duo_v1
  when absent, supply under-ammoed turrets, rebuild broken blocks, defend lane
  during waves, wait. Feature values for `HandTunedUtility` come from a new
  engine-backed `FeatureSource` (distances, deficits, danger).
- Files: new `agentcore.candidates` (engine-free core + data-driven rules),
  engine feature source in rl-server; unit tests with synthetic world states.
- Acceptance: for a fixed world snapshot the candidate list is byte-stable and
  masked correctly (validity per agent capability/range).

### 5.2 Board↔engine adapter + protocol coordination surface
- **DONE (verified 2026-07-20):** `CoordinationAdapter` owns one sim-thread
  `TaskBoard` per episode, resets it in-process, resolves same-tick candidate
  claims before starting any skill, and keeps leases alive during arbitrarily
  chunked external steps. It maps harvest (mine/deliver/settle until threshold),
  schematic, turret supply, rebuild, defend, and wait tasks to the legal M3/M4
  skills. Protocol v1 now accepts typed task actions, returns typed rejections,
  publishes full structured `task_events[]`, and includes a stable maximum-32
  `task_board[]`; action masks include board/dependency/ownership legality. The
  canonical state hash includes non-empty board state. The live coordination
  check exercises invalid selection, contested claims, continue/request/offer/
  accept/decline help, real build+supply completion, wait+abandon, and repeats the
  complete transcript byte-identically in a second JVM through tick 280.
- Objective: host a `TaskBoard` per episode in rl-server (reset clears it —
  board.reset() exists); map task execution to M3/M4 skills (task type →
  skill sequence per docs/STRATEGY_NOTES.md mapping table); publish
  `task_events[]` (drained CoordinationEvents, already schema-shaped per brief
  §11.3) and a bounded `task_board[]` snapshot in StepResponse; accept
  task-level actions per brief §15.1: `SELECT_CANDIDATE_TASK[k]`,
  `CONTINUE_CURRENT_TASK`, `OFFER_HELP[k]`, `ACCEPT/DECLINE_HELP[k]`,
  `ABANDON[reason]`, `REQUEST_HELP`, `WAIT` — validated, masked, additive in
  protocol v1.
- Acceptance: python-side sees events and snapshots; invalid task actions get
  typed rejections; determinism holds (board ops are already deterministic;
  the adapter must keep stable iteration).

### 5.3 Scripted multi-agent policies
- **DONE (verified 2026-07-20):** dependency-free `GreedyUtilityPolicy` and
  `RoleAssignmentPolicy` baselines consume the M5.2 candidates/masks and use a
  stable lowest-index tie-break. `HelperCoordinator` implements deterministic
  nearest-idle request/offer/accept actions. The live three-agent policy check
  proves distinct miner/builder intent, a build blocked on real copper, an
  accepted 20-copper helper contract fulfilled by 21 copper mined and delivered
  through engine skills, exactly one schematic completion, and a byte-identical
  transcript in a second fresh JVM through tick 912. Full smoke includes it.
- Objective: (a) greedy-utility policy (each agent picks its highest-utility
  candidate, CONTINUEs until completion/blockage); (b) role-assignment policy
  (fixed roles: miner/builder/supplier per agent index); both in
  `python/src/mindustry_agents/policies/` driving 2–4 agents through the
  protocol. Helper flow: builder REQUEST_HELP on RESOURCES_SHORT; nearest idle
  agent OFFER_HELP; accept → helper runs a SUPPLY contribution subtask;
  fulfilment recorded on the contract (board API exists).
- Acceptance: two agents announce **distinct** work; a helper contract is
  offered, accepted, and fulfilled with measurable contribution; duplicate
  claims resolved deterministically (claim tie-break already tested — now
  demonstrated live); no duplicate construction (reservations wired: schematic
  footprint + resource budget, 5.4).
- Depends: 5.1, 5.2; M4 skills for build/supply tasks.

### 5.4 Reservations wired to real targets
- **DONE (verified 2026-07-20):** candidate claims are ordered by utility and
  stable agent/task identity before reservation acquisition and skill start.
  Schematic tasks reserve their exact multiblock bounding footprint plus
  estimated copper; supply tasks reserve their copper budget. Reservation state
  is exposed per task and included in the canonical hash. A live overlap probe
  proves the later, higher-utility bidder wins independent of bundle order, the
  loser receives a structured `reservation_overlap` event and never gets a
  build plan, abandonment clears the winner's plan/reservations, and a released
  builder then completes. Two supply tasks hold and release disjoint five-copper
  budgets. The full trace repeats byte-identically through tick 280.
- Objective: claiming a build task reserves the schematic footprint (tiles) and
  estimated copper; supply tasks reserve resource budget; abandonment/expiry
  releases (board semantics exist — wire acquire/release into the adapter).
- Acceptance: two builder agents given overlapping candidates never place
  conflicting plans (property test live in-engine); reservation conflict emits
  the documented event.

### 5.5 Lease expiry / failure recovery (chaos)
- **DONE (verified 2026-07-20):** validation-only reset options select one agent
  and deterministic failure tick. At that tick the sim-thread hook cancels its
  queued build plan, freezes its skill, and suppresses lifecycle reports without
  releasing board ownership. The live chaos run stops sending agent 0 actions,
  observes lease expiry at tick 627 with both reservations released, lets agent 1
  reclaim and complete the partial schematic at tick 893, and reaches a normal
  terminal loss at tick 3600. A second fresh JVM produces a byte-identical trace.
- Objective: simulate an agent failure mid-task (stop sending its actions +
  suppress its heartbeats via a test hook); its lease expires; the task reopens;
  another agent claims and completes it.
- Acceptance: scripted chaos run shows expiry → reclaim → completion in the
  event log; episode still terminates normally; determinism unaffected (the
  "failure" is part of the action trace).

### 5.6 Announcements end-to-end + metrics
- **DONE (verified 2026-07-20):** every task event now carries an
  `announcement` rendered solely from its structured fields when the board's
  rate limiter sets `announce=true`; routine progress/heartbeats carry an empty
  string. Step infos expose cumulative duplicate-work, completion/abandonment,
  agent/idle tick, idle-fraction, and structured/announced message counters.
  The live runner prints four coherent lines (intent, resources-short block,
  helper offer, completion), verifies structured request/accept/fulfilment and
  progress ordering, proves same-tick accept suppression and no routine text,
  bounds the trace at 112 structured/four announced messages, and repeats all
  events/metrics byte-identically in a second JVM.
- Objective: rendered announcement strings (templates exist) surfaced in
  StepResponse `task_events[]` and printed by the python runner exactly at
  meaningful transitions (rate limits enforced by the board; heartbeats never
  rendered). Team metrics counters into `infos`: duplicate-work incidents,
  idle fraction, task completion/abandonment counts (brief §22.1 subset).
- Acceptance: a headless scripted run prints a coherent transcript matching
  brief §12.4 shape (intent → helper offer/accept → progress → blocked →
  complete); rate-limit tests pass live; message count bounded.

Exit criteria (brief, unchanged):
- [x] Two or more agents announce distinct work
- [x] A helper contract is accepted and completed
- [x] Duplicate task claims are resolved
- [x] Stale claim expires after a simulated agent failure
- [x] Communication rate limit passes tests

## Milestone 6: Bootstrap Defense v0

Loader status: **done and verified 2026-07-20** — full 48×48 world, ore
patches, east spawn, 250-copper loadout, deterministic 3-wave dagger schedule
(2700/4500/6300) from `scenario.json`, moving enemies (sync pathfinder patch),
win/loss/truncate termination, and seed sensitivity. M6 is complete: the
scripted team wins, deterministic replay matches, and the human demo is verified.

### 6.1 Scripted expert team
- **DONE (verified 2026-07-20):** `BUILD_LINE` is now a live, reserved board
  task backed by the checked-in `copper_line_v1` two-drill/seven-conveyor plan.
  The three-agent expert builds the line and `east_duo_v1`, legally mines its
  remaining budget, constructs a protected four-Duo defense, supplies/rebuilds
  between waves, and wins at tick 8100 on seeds 12345, 23456, 34567, 45678,
  and 987666666 (core health 848/884/1001/920/983). `make scripted-demo`
  prints the structured announcement/outcome transcript plus a legal
  insufficient-copper variant that emits `BLOCKED(resources_short)`, replans
  through mining, and also wins.
- Objective: a fixed policy (2 agents minimum, 3 preferred to exercise helping)
  that wins bootstrap-defense-v0: mine → build drill line per SCENARIOS.md →
  build+supply east_duo_v1 → rebuild between waves → survive wave 3. Built on
  the 5.3 policies; may be a hand-tuned sequence where utility falls short.
- Acceptance: win (outcome=win at tick 8100, core alive) on the defined
  evaluation seed set (scenario v0 is seed-stable except spawn spread — expect
  uniform wins; record per-seed result); `make scripted-demo` wired: headless
  run printing the announcement transcript + outcome; the deliberately-blocked
  variant (insufficient copper hook) shows BLOCKED → replan per brief §12.4.

### 6.2 Evaluation metrics + episode summaries
- **DONE (verified 2026-07-20):** `make evaluate-scripted` runs the fixed
  five-seed set in one persistent JVM, writes pinned per-episode JSONL under
  `runs/`, and prints the aggregate table recorded in `docs/BENCHMARKS.md`.
  Summaries include all requested milestone, core/unit/resource, task, idle,
  and message fields; the run is 5/5 wins with minimum/mean core health
  848/927.2 and two agent losses across all episodes.
- Objective: per-episode JSONL summary (outcome, milestone ticks: first drill,
  line complete, turrets built, turrets supplied; core damage; units lost;
  resource totals; task stats: completed/abandoned/duplicated; idle fraction;
  message counts) written under `runs/` from `infos` — brief §22.1 subset.
  `evaluate-scripted` script: N episodes across the seed set → aggregate table.
- Acceptance: `make evaluate-scripted` produces the table; numbers land in
  docs/BENCHMARKS.md (M6 section).

### 6.3 Replay + golden traces
- **DONE (verified 2026-07-20):** the checked-in JSONL golden contains two
  complete expert episodes (seeds 12345/23456), 16,200 advanced ticks, 678
  checkpoints, every ordered action, every structured coordination event, and
  every resulting hash. `make determinism` replays it through a fresh JVM after
  the legacy 79-boundary stage. An in-memory one-line MINE-target mutation
  provably flips a checkpoint; the golden file remains unchanged.
- Objective: record seed + full action/coordination trace per episode
  (compact JSONL); `tools/replay.py` re-runs a trace through a fresh JVM and
  verifies hash checkpoints. Check in one golden trace ≥10,000 ticks
  (Gate 1 target) under `tests/golden/` with expected hashes; wire into
  `make determinism` as a second stage.
- Acceptance: golden replay byte-identical on a fresh checkout; a deliberate
  one-line skill change flips the hash (documented negative test, then
  reverted).

### 6.4 agent-plugin demo server (human-joinable)
- **DONE (verified 2026-07-20):** `agent-plugin:dist` produces an
  official-layout loadable plugin
  for `server:dist`. The isolated `make demo-server` probe loads the plugin in
  the real server, spawns three Alphas, legally builds both shared JSON plans and
  an initial four-Duo defense, verifies the per-plan build order, renders
  rate-limited board announcements, mines whenever no enemy is present, and
  expands to six/eight supplied Duos with seven new walls after each of waves
  1–2.
  `DEMO_SURVIVAL=1` verifies both expansions and clears all three waves without
  a socket. A stock v159.7 client joined, resumed, observed the complete
  mining/building/supplying/chat path, survived all three waves, then used
  `/agents stop`; all three agents halted immediately. The safe default opens
  no socket; `DEMO_JOIN=1` is the explicit private port-6567 path.
- Objective: `agent-plugin` loads into the REAL dedicated server
  (`server:dist` jar + plugin per official plugin layout; ENGINE_NOTES §boot):
  spawns the same agent units driven by the SAME `agentcore` skills/board (its
  own `AgentBody`/clock adapter — real-time pacing, threads as vanilla), an
  in-process scripted policy (6.1), announcements rendered to team chat via
  the existing templates (rate-limited), minimal commands: `/agents status`,
  `/agents pause|resume`, `/agents stop` (emergency stop). Loopback/private
  binding by default (port 6567 only when the user wants to join; the machine
  hosts other projects — never grab ports silently).
- Acceptance: `make demo-server` starts it; a human with the stock v159.7
  client joins locally, sees agents mining/building/supplying with concise
  chat announcements, `/agents stop` halts all agents instantly. Training and
  demo mode share `agentcore` skills + board (verified by code inspection +
  a parity smoke: same scripted opening produces the same build order).
- Depends: 6.1; M4/M5. This is deliberately LAST — everything it shows must
  already be true headlessly.

### 6.5 M6 closure
- **DONE (verified 2026-07-20):** the full closure matrix and brief §32
  repository-evidence audit are recorded in `docs/STATUS.md`; evaluation and
  real-server numbers are current, handoff docs are refreshed, and the closure
  commit is tagged `milestone-6`.
- Objective: docs/STATUS.md, docs/BENCHMARKS.md (evaluation numbers),
  docs/HANDOFF.md refreshed; tag `milestone-6` commit; brief §32 checklist
  audit (items 1–15) recorded in STATUS.md with honest per-item state.

Exit criteria (brief, unchanged):
- [x] Scripted agents complete the scenario across a defined seed set
- [x] Human can join a private real-time server and observe/use the agents
- [x] Training and demo mode share the same skills and task board
- [x] Deterministic replay matches training results

# Phase 2: The Teammate Roadmap (M7–M10, restructured 2026-07-27)

**North star (project owner's explicit goal): agents that cooperate at a level
top players would want on their team.** The success metric is a skilled human
*choosing* these agents as teammates — not raw completion speed. This
restructures the original M7–M10: adaptive planning and the evaluation ladder
are pulled BEFORE learning (a learned selector inherits the candidate
catalog's ceiling and must beat baselines worth beating); human cooperation is
the destination milestone, with its metrics threaded through everything
earlier. Review findings that motivate this ordering: `docs/REVIEW_M6.md`.

---

## Milestone 7: Consolidation, adaptive planning, evaluation ladder

Objective: fix the M6 review findings, make the SCRIPTED team genuinely
adaptive (the "primitive planning" complaint), and build the evaluation
machinery every later milestone is judged by. No learning yet; no new
dependencies.

### 7.1 Review-findings consolidation
- **DONE (verified 2026-07-20):** findings 1/3/4/6/8/9/10/11/12 are
  resolved. Scenario geometry/timing now flows through reset metadata to the
  expert and directly from `Scenario` to the plugin; overflow truncation ranks
  by utility while reserving DEFEND; episode handles use root seed plus a
  deterministic process reset counter; duplicated skill defaults/dead branches
  and unsafe reservation removal are removed. The Pathfinder catalogue matches
  the actual 48-line patch. Full validation is green (103 JUnit, 40 pytest,
  smoke ledgers, 79-boundary determinism, 672-checkpoint/16,200-tick golden,
  1,000 resets, 5/5 evaluation, plugin and three-wave survival probes).
- Objective: resolve `docs/REVIEW_M6.md` findings 1, 3, 4, 6, 8, 9, 10, 11, 12
  (mechanical fixes: regenerate the UPSTREAM_PATCHES diff, delete dead
  DemoCoordinator branches, derive probe-asserted counts from placement loops,
  data-drive all coordinates/constants from scenario/schematic JSON, truncate
  candidates by utility not generation order, replace nanoTime episode_id with
  rootSeed+counter, single-source duplicated constants, resolve SupplyBuilding
  stock fields).
- Files: per-finding citations in REVIEW_M6.md.
- Acceptance: full verification suite green (smoke/determinism/stress/golden
  replay/evaluate-scripted — golden trace WILL change if behaviour-adjacent
  constants unify; regenerate it deliberately in its own commit with
  before/after outcome equivalence shown); no literal coordinate remains in
  scripted_demo.py or DemoCoordinator that exists in scenario/schematic JSON.

### 7.2 One coordination brain (training/demo parity for real)
- **DONE (verified 2026-07-21):** `ExpertCoordinationDriver` now owns the
  complete scripted staging, task lifecycle, wave response, repair/resupply,
  expansion, and reserve-mining policy. Both the fixed-step
  `CoordinationAdapter` and real-time plugin use that same engine-neutral
  driver and scenario-derived `ExpertCoordinationPlan`; `DemoCoordinator` is
  reduced to pacing, engine/IO adaptation, controls, rebinding, and telemetry.
  `make coordination-parity` compares a 366-decision/89-selection recorded
  trace across two driver instances (all six exercised task types), then
  compares the actual fixed-step and no-port plugin openings: both emit 33
  selections with digest
  `f335f6b950ac1b58857ca84b40e7151f966d5d53408fd0e643fbc54a39671385`.
  The no-port survival acceptance still clears all three waves and reaches tick
  8100 with 1091/1100 core health.
- Objective: extract the shared task-lifecycle driver so `CoordinationAdapter`
  (fixed-step) and the demo plugin consume ONE implementation of staging, wave
  response, expansion policy, and task lifecycle (REVIEW_M6 finding 5).
  DemoCoordinator shrinks to pacing/IO adaptation. Widen the parity probe from
  build-order equality to policy-decision equality (same snapshot → same task
  selections) on a recorded scenario trace.
- Why first: every capability after this must reach the human demo unchanged —
  the north star is meaningless if the demo brain forks from the training brain.
- Acceptance: parity probe compares decision sequences, not just build order;
  demo survival probe still passes; no coordination logic left in agent-plugin
  beyond adaptation.

### 7.3 The utility layer becomes the expert
- **DONE (verified 2026-07-21):** `evaluate-scripted` now drives the pure
  `GreedyUtilityPolicy` through public candidate observations, masks,
  `SELECT_CANDIDATE_TASK`, the task board, reservations, and existing skills;
  the M6 `ExpertEpisode` is retained only as the frozen ladder/golden baseline.
  Scenario-derived fortification/expansion candidates, recurring task identity,
  real planned-target utility, multi-seat defense, a 30-ammo reserve, and
  structured resource-block abandon/regenerate/reselection close the fixed
  scenario gaps recorded in `docs/CANDIDATE_GAPS.md`. The five pinned seeds all
  win at tick 8100 (core health min/mean 1082/1096.4); the legal pre-spend
  variant wins with 209 core health and seven explicit replans. Pre-wave
  milestones correctly remain fixed, while seeded spawn spread produces real
  wave-clear/message/loss/core-health variation. The enriched shared plan keeps
  fixed-step/plugin decision parity green (43 selections, digest
  `157134ba5a4e3f39ccc3cf237093481dc8474b7edd1d20e16b274ec338b1a6c2`).
- Objective: retire the hand-authored `ExpertEpisode` macro as the primary
  policy (REVIEW_M6 finding 2). The greedy-utility policy over the candidate
  catalog must win bootstrap-defense-v0 5/5 (+ blocked variant) end to end.
  Enrich the candidate catalog/utility features only as needed to win — every
  gap found is recorded (it is the concrete list of what the catalog cannot
  express). ExpertEpisode is demoted to a frozen baseline for the ladder.
- Acceptance: `evaluate-scripted` runs the utility-driven policy: 5/5 wins;
  the win no longer produces identical milestone ticks across seeds only if
  behaviour genuinely varies (do not fake variation); a
  `docs/CANDIDATE_GAPS.md` list of expressiveness gaps found.

### 7.4 Adaptive planning v1 (de-primitive the catalog)
- Objective: upgrade the four rigidity layers (REVIEW_M6 inventory) within
  the scripted regime:
  (a) wave-clock awareness: candidate priorities/leads computed from the wave
  schedule and current defense readiness (ammo coverage vs incoming wave DPS
  per STRATEGY_NOTES arithmetic), replacing the fixed 600-tick lead and magic
  priorities with derived quantities;
  (b) economy predicates implemented for real: conveyor connectivity +
  core-inflow rate (finding 7) so "line complete" means the line WORKS;
  (c) spatial gating: real assignmentRange + travel-cost from actual distance;
  (d) event-driven decision boundaries: decision on task-terminal, BLOCKED,
  wave-spawn, wave-clear, core-damage events (the protocol already carries
  them) instead of fixed polling quanta;
  (e) replanning: BLOCKED tasks trigger candidate regeneration + reselection
  (not just retry), bounded by the existing switching-cost mechanics.
- Acceptance: on the FIXED scenario, milestone ticks/messages now vary by seed
  where behaviour legitimately differs; a new `adaptive-probe` scenario variant
  (e.g. pre-damaged line, delayed loadout) that the linear macro cannot win but
  the adaptive policy does; idle fraction and time-to-defense-ready improve vs
  the frozen ExpertEpisode baseline on the variant set.
- **Verified 2026-07-21:** priorities now derive from copper/economy/defense
  deficits; loaded wave HP/DPS plus native Duo damage, reload, inaccuracy,
  magazine, travel, and clear time derive ammo targets and defend lead.
  `BUILD_LINE` completes only after the exact footprint has a directed
  drill-to-core conveyor path and a 600-tick automated inflow window reaches
  0.6 copper/s.
- `stop_on_decision_event` is additive and opt-in: task terminal/BLOCKED,
  economy-ready, wave spawn/clear, and core damage can end a chunk early without
  changing default exact-step behavior. Recoverable BLOCKED replans are bounded
  to 3/180 ticks and utility switching cost uses recent assignment history.
- `make adaptive-planning-check` proves fixed adaptive/frozen wins, adaptive
  delayed-loadout-probe win, and frozen probe loss. Across fixed+probe at seed
  12345, adaptive mean idle fraction is **0.125 vs 0.878** and mean censored
  defense-ready tick is **817 vs 5251**. Fixed evaluation remains 5/5.

### 7.5 Scenario variation v1 + seed governance (ADR-0012)
- Objective: procedural jitter driven by root_seed within scenario_version 2:
  copper/lead patch positions (bounded), wave composition/timing jitter
  (bounded), starting loadout range, optional second approach lane variant.
  Train/dev/held-out seed-set governance: named frozen seed sets in
  `configs/evaluation/`, held-out sets never used during development. ADR-0012
  records variation axes + governance + scenario_version discipline.
- Acceptance: determinism per seed unchanged (same seed → same world+hashes);
  scenario_check validates variants; the 7.3 utility policy wins ≥80% on the
  dev variant set (record honestly; gaps feed 7.4 iteration).
- **Verified 2026-07-21:** `bootstrap-defense-v1` / scenario version 2 resolves
  all five bounded axes independently from `root_seed`, validates the resolved
  geometry/waves, publishes it in metadata, and hashes the resolved contract.
  Same-seed initial state and idle-through-wave action traces match across
  repeated resets and fresh JVMs. Named train/dev/held-out v1 sets are checked
  in, pairwise disjoint, and
  the dev tool refuses to execute a held-out set (ADR-0012).
- `make scenario-variation-check` exercises every axis, runs the ordinary
  undefended `scenario_check`, and records adaptive-v1 at **8/10 wins (80%)** on
  the frozen dev set. Seeds 2005/2007 expose an honest upper-lane wave-3
  fortification-coverage gap in `docs/CANDIDATE_GAPS.md`.

### 7.6 Evaluation ladder + teammate scorecard v0
- **DONE (verified 2026-07-21):** `make evaluate-ladder` runs the permanent
  random-valid, pure greedy-utility, fixed role-assignment, frozen M6 macro
  (fixed only), and adaptive-v1 cells. Each cell starts in a fresh JVM and
  preserves frozen seed order; every scored episode follows the same unscored
  same-seed idle-through-wave-1 trace used by M7.5. The certified Windows path uses one JVM at a
  time, below the four-JVM project cap, because simultaneous live JVMs changed
  policy traces under host contention. Two certified runs produced identical
  65-line JSONL. Episode records include pinned engine/scenario/seed-set/policy
  manifests and the six-field teammate scorecard; unobserved help/recovery is
  `null` with coverage counts, never imputed. Aggregates use 10,000 stable
  bootstrap resamples. Fixed/dev are descriptive and the held-out set remains
  sealed behind an explicit one-way flag; no promotion claim was made.
- Objective: the permanent judgment machinery: baselines = random-valid,
  greedy-utility, role-assignment, frozen ExpertEpisode (fixed scenario only),
  adaptive-v1. Evaluation harness runs N episodes × policy × seed set with
  bootstrap confidence intervals and a promotion rule (a policy is only
  "better" if CI-separated on held-out seeds). Teammate scorecard v0 computed
  per episode from existing metrics: idle fraction, duplicate-work incidents,
  time-to-help (request→fulfilment ticks), announcement precision (rendered
  messages per meaningful transition), task-abandonment rate, recovery time
  after agent loss. `make evaluate-ladder` produces the table;
  docs/BENCHMARKS.md gains the section.
- Acceptance: ladder runs reproducibly on Windows (4-JVM cap); scorecard
  appears in episode JSONL + aggregate table; promotion rule documented in
  ADR-0012.

Exit criteria:
- [x] All REVIEW_M6 findings resolved or explicitly waived with rationale
- [x] One coordination brain; decision-level parity probe green
- [x] Utility-driven policy wins fixed 5/5 + ≥80% dev variants; macro retired
- [x] Seed-varied behaviour demonstrably adaptive (variant probe + metrics)
- [x] Ladder + scorecard v0 reproducible; held-out governance in force

## Milestone 8: Learned task selector (single seat)

Objective: replace ONE seat's utility scoring with a learned policy that
CI-beats greedy-utility on held-out variants. Everything else stays scripted.
Not the destination — the proof that learning plugs into the seam.

### 8.1 M8_DESIGN.md before any code
- **DONE (verified 2026-07-21):** `docs/M8_DESIGN.md` pins a single learned
  selector seat, the ordinary 10-way masked task-action surface, exact
  `8×37` candidate and 56-scalar schemas, deterministic forced lifecycle
  actions, event-boundary cadence, feed-forward actor/critic, run manifests,
  matched/permanent comparators, and the one-way held-out promotion protocol.
  `docs/REWARD_AUDIT.md` drafts all five v1 components with 15 component-specific
  exploit hypotheses plus an eight-case cross-component adversarial matrix.
  Every row remains `drafted-not-implemented`: no reward, torch dependency,
  model, trainer, spatial grid, or held-out execution was added.
- Featurization: fixed-size candidate table (≤8 rows × feature vector from
  the existing UtilityFeatures + task-type one-hot + board context), scalar
  team/self features; NO spatial grids yet. Exact tensor shapes + masks.
- Single-learned-seat semantics: the learned agent submits
  SELECT_CANDIDATE_TASK[k]/CONTINUE/WAIT through the SAME task_action protocol
  and board claim resolution as scripted seats (no privileged path).
- Invalid action = masked out; if selected anyway (should be impossible),
  penalty + WAIT, never a crash. Decision cadence = 7.4's event boundaries.
- Reward v1 DRAFTED here with docs/REWARD_AUDIT.md entries (team milestone
  high-water marks + terminal outcome + small per-tick time cost + small
  invalid/abandon penalties; each component: 3 exploit hypotheses + an
  adversarial script). No reward influences training until its audit row is
  complete — the audit gate is hard.
### 8.2 ADR-0011: RL dependency boundary
- PyTorch (pinned exact version) permitted ONLY under `python[rl]` extra,
  imported ONLY in `mindustry_agents/training/`; env/protocol/process stay
  stdlib (ADR-0007 intact). Lockfile for the rl extra. WSL2 becomes the
  training runtime (bring-up + re-verification there is part of this item);
  Windows remains the dev/demo runtime.
- **DONE (verified 2026-07-21):** ADR-0011 accepts the exact
  NumPy 2.4.2/PettingZoo 1.26.1/PyTorch 2.12.1 CPU boundary. uv 0.11.16
  regenerates the hashed Linux CPython 3.12 lock byte-identically. On Ubuntu
  24.04/WSL2, 33 core tests pass under `python -S` and the temporary locked
  environment reports Python 3.12.3, PyTorch 2.12.1+cpu, and no CUDA device.
  The full Windows Python suite (54 tests), smoke, determinism golden, and
  65-episode fixed/dev ladder remain green; held-out remained sealed.
### 8.3 Throughput bring-up for training
- Larger step chunks at decision boundaries (event-driven cadence makes steps
  long), process-based or chunk-batched collector if needed; Gate 5 overnight
  run (≥10k resets); record honest scaling on WSL2. Do not train until ≥50×
  aggregate real-time at 4 JVMs with inference in the loop.
- **DONE (verified 2026-07-21):** the supervised vector path now carries
  `stop_on_decision_event` and sums each child's actual advance. A frozen
  M8-shape CPU graph runs in shadow mode at initial/real decision boundaries;
  its logits never affect scripted actions. On Ubuntu 24.04/WSL2 the certified
  1/2/4-JVM cells reached 122.4×/212.7×/293.5× aggregate real-time, with all
  episodes winning and the same final hash. The long gate completed 10,000
  in-process resets with zero hash mismatches, 0.93 ms median / 1.27 ms p95,
  338.3 MiB peak RSS below the 650 MiB ceiling, and no orphan process.

### 8.4 PPO selector + run manifests
- Feed-forward first, recent-history features; run manifest per brief §21.1;
  checkpoints reproduce evaluation bit-exactly (eval mode deterministic).
- **DONE (verified 2026-07-21):** the framework-neutral 8x37/56 feature adapter,
  audited five-component reward, one learned selector seat, masked PPO trainer,
  checkpoint chain, training JSONL, complete replay traces, and exact manifests
  are implemented. All 27 reward adversaries pass before training. Two
  independent pinned WSL2 runs selected update 3 with identical checkpoint
  `0b2bd8ac904a9e21...`, replay digest `87ba273f376c47de...`, full-run digest
  `56cc7b54bc9b01b5...`, and dev action/state aggregate
  `52aecddf4c96bab6...`. The checkpoint is 0/10 on dev and was not a promotion
  candidate; subsequent M8.5 train/dev progress is recorded below.

### 8.5 Promotion gate
- Beats random-valid AND greedy-utility with CI separation on HELD-OUT variant
  seeds; scorecard v0 not worse than greedy-utility (a selector that wins
  faster but teams worse fails); anti-exploit scripts show no reward farming;
  behavioural traces (task Gantt from event log) reviewed and archived.

**FINAL V1 RESULT — NOT PROMOTED (2026-07-21):** elapsed-time GAE, repeated
governed train cycles, canonical WAIT, mixed-seat ablations, paired scorecards,
two reproducible parent runs per recipe, deterministic 75/25 checkpoint
interpolation, lineage validation, and the exclusive one-way runner are
implemented. The frozen derived checkpoint won 9/10 dev and passed every
precondition. The one-way held-out result was learned 4/10 (95% CI
`[0.1,0.7]`), permanent random-valid 6/10 (`[0.3,0.9]`), permanent
greedy-utility 6/10 (`[0.3,0.9]`), and matched greedy 1/10 (`[0.0,0.3]`). It
did not CI-beat either permanent baseline and regressed on permanent-greedy idle
and abandonment scorecards. The completed attempt marker forbids rerunning this
held-out set; individual outcomes must not inform policy changes.

**POST-FAILURE GOVERNANCE FROZEN (2026-07-21):** ADR-0013 permanently
quarantines held-out-v1 and precommits `bootstrap-defense-v1-held-out-v2`
before any new model work. V2 contains 40 unique roots (`910001..910040`), is
globally disjoint from fixed/train/dev/v1-held-out roots, is refused by
development loaders, and permits one exclusive future final attempt under the
same promotion gates. No successor candidate has been trained. M9 remains
gated on M8 promotion.

The first successor recipe is precommitted as `m8-selector-v3-diverse`: it
holds the 512-episode/eight-update budget, model, reward, optimizer, RNGs, and
dev selection fixed while replacing 32 repeats over 16 train roots with 8
repeats over 64 new train roots. Its config names held-out-v2. Two pinned runs
reproduced exactly but selected update 1 at only 3/10 dev wins (full-run digest
`e9e1ee37fbfef6ee...`), so the hypothesis is rejected before preflight and v2
remains unopened.

The next precommitted train/dev-only hypothesis is
`m8-selector-v4-teacher-regularized`: the v3 recipe plus coefficient 0.05
successful-episode imitation of adaptive-v1's action at the same structured
boundary. The auxiliary is training-only, separately metered, zero by default,
and changes neither reward nor evaluation. Its config names held-out-v2; no v4
training evidence exists yet.

V4 reproduced exactly and improved the diverse-root result to 5/10 dev wins at
update 5 (full-run digest `fc23c1ed82a546d3...`), but remains ineligible for
preflight. V5 is precommitted as the final coefficient-only test, changing only
the successful teacher coefficient from 0.05 to 0.10. It must reach at least
9/10 dev wins or this line stops; its config names held-out-v2.

V5 reproduced exactly but fell to 3/10 dev wins at update 8 (full-run digest
`4d55b193cede563b...`), closing the teacher-strength line. V6 is precommitted as
an auxiliary-free data-budget test: the v3 recipe with only training cycles
raised from 8 to 32, giving all 64 roots the original 32 visits (2,048 episodes,
32 updates). It must reach at least 9/10 dev wins or stop before preflight.

Two pinned v6 runs reproduce exactly and select update 31 at 9/10 dev wins
(`0dfdcf9b5273ae3f...`; full-run `54476ef63e31e06d...`), meeting the
precommitted continuation bar. Direct reproducible-checkpoint lineage is now
validated alongside legacy interpolation. The full dev scorecard preflight is
next; held-out-v2 remains unopened.

The dev-v1 preflight beats every win-rate comparator but remains ineligible
because three favorable scorecard means have ten-pair intervals crossing zero.
ADR-0014 freezes a disjoint 40-root dev-v2 one-way confirmation for V6, with an
exclusive attempt marker and freshly matched permanent baselines. Failure
rejects V6; success is required before held-out-v2 can be opened.

The exclusive dev-v2 attempt started but aborted on a matched-control
catalog-WAIT indexing bug before any result artifacts were persisted. Under
ADR-0014 the attempt is consumed, V6 is rejected, and dev-v2 will not be rerun.
The control path is fixed and regression-tested for future candidates.
Held-out-v2 remains unopened; M8.5 is still unmet.

ADR-0015 precommits V7 as a deterministic 90/10 blend of reproducible V6
update 31 and teacher-regularized V4 update 5. Cross-commit parent hashes are
explicitly validated. The 40-root, globally disjoint dev-v3 confirmation set is
frozen before construction and permits one V7 attempt only after dev-v1
qualification. Its construction and result are recorded below; held-out-v2
remains sealed.

V7 constructions match exactly and its dev-v3 confirmation wins 35/40 versus
permanent greedy 30/40. Every scorecard except idle passes; idle is favorable
on average but its interval crosses zero, so V7 is rejected and dev-v3 is
consumed. ADR-0016 precommits V8 as a one-coordinate `-0.25` WAIT-logit bias
adjustment to V7, with no reward/mask/lifecycle change. Dev-v4 is frozen as a
new disjoint 40-root one-way confirmation. Its result is recorded below.

V8 constructions match exactly and dev-v4 is fully eligible at 37/40 wins with
all scorecards passing. Its exclusive held-out-v2 final completes at 36/40 and
strictly CI-beats permanent random (19/40) and greedy (23/40), but V8 is **not
promoted**: idle and abandonment regress versus permanent greedy,
announcements/recovery are uncertain, and matched-greedy idle is uncertain.
Held-out-v2 is consumed and cannot be rerun.

ADR-0017 freezes `bootstrap-defense-v1-held-out-v3` before further model work:
80 globally disjoint roots and one future exclusive final. A new candidate must
name v3 and use newly governed train/dev confirmation evidence. M8.5 remains
unmet and M9 remains gated.

ADR-0018 precommits V9 as the final WAIT-bias step: one additional `-0.25`
child adjustment from V8 (`-0.50` total from V7), with every other model and
behavior field fixed. Its config names held-out-v3. A new globally disjoint
80-root dev-v5 set is frozen for one confirmation after dev-v1 qualification.
V9 constructs exactly at checkpoint `3ae49108c913b078...` with lineage
`c329bfc096122a13...`, beats all dev-v1 win comparators, and completes dev-v5
at 65/80 wins. Under the then-implemented matched-only development scorecard it
qualified for held-out-v3.

Held-out-v3 completes exactly once: V9 70/80, permanent random 33/80,
permanent greedy 49/80, matched greedy 5/80. All strict win gates pass, but V9
is **not promoted** because announcements, idle, and abandonment regress versus
permanent greedy, permanent-greedy recovery is uncertain, and matched-greedy
idle is uncertain. Held-out-v3 is consumed and its individual outcomes remain
quarantined.

ADR-0019 corrects the development/final parity defect: preflight now requires
paired non-regression versus both seed-level permanent greedy and matched
greedy, and hashes the permanent record source for final validation. It freezes
`bootstrap-defense-v1-held-out-v4` before further candidate work: 160 globally
disjoint roots, development-loader refusal, and one future exclusive final only
after the corrected gate passes. M8.5 remains unmet and M9 remains gated.

ADR-0020 precommits V10 from train/dev evidence only. V9 agreed with
adaptive-v1 on 5.3% of unforced dev-v5 decisions; adaptive-v1 substantially
reduced idle and abandonment, while role assignment sacrificed wins and
duplicates. V10 therefore uses V6's 64-root/32-cycle recipe with one new
training-only term: coefficient `1.0` adaptive-teacher cross-entropy on every
unforced transition. Reward and inference stay unchanged, and the immutable
config names held-out-v4. A globally disjoint 160-root dev-v6 set is frozen for
one corrected dual-scorecard confirmation after reproducible construction and
dev-v1 screening.

V10 reproduces exactly across two pinned runs but selects update 6 at only 1/10
dev-v1 wins (checkpoint `a20f44d6ec093076...`, full-run digest
`787b5d4bd6548eea...`). Mean dev idle is about 0.361. The full-boundary 1.0
teacher term therefore fails its screen and is rejected before dev-v6. Dev-v6
and held-out-v4 remain unopened.

ADR-0021 precommits V11 as a fixed 90/10 blend of reproducible V6 update 31
and V10 update 6. This tests V10's stronger teacher state at the V7-established
blend weight without another training run or sweep. V11 must reproduce and
reach at least 9/10 dev-v1 wins. Dev-v6 remains retired unopened; a disjoint
160-root dev-v7 set is frozen for one corrected dual-scorecard confirmation.

V11 constructions match checkpoint `0a8fa8b4ba98581d...` and lineage
`845282326c58308c...`. It reaches 9/10 dev-v1 wins and beats every observed win
comparator. Ten-pair scorecards remain ineligible: permanent idle/abandonment
regress and matched idle/abandonment are favorable but uncertain. The frozen
bar authorizes one dev-v7 confirmation only; held-out-v4 remains sealed.

Dev-v7 completes once: V11 137/160, permanent random 69/160, permanent greedy
100/160, matched random 19/160, matched greedy 12/160. Win gates and all
matched-greedy scorecards pass. Permanent-greedy duplicates pass, but
announcements, idle, recovery, and abandonment fail. V11 is rejected, dev-v7
is consumed, held-out-v4 remains sealed, and M8.5 remains unmet.

ADR-0022 precommits V12 as V6's 64-root/32-cycle recipe under
`selector_reward_v2`. Four capped negative-only components target the exact
remaining gates: idle ticks, duplicate work, announcements, and non-forced team
abandonment. Their audit rows and adversaries must pass before training. V12
must reproduce and reach 9/10 dev-v1 wins with mean idle below 0.25. A disjoint
160-root dev-v8 set is frozen for one corrected confirmation; held-out-v4
remains sealed.

The production v2 accumulator, rollout telemetry, schema plumbing, and all 37
v1/v2 reward adversaries pass on 2026-07-21, together with the 121-test Python
suite. Two exact 2,048-episode V12 runs then reproduce bit-for-bit at update 28:
10/10 dev-v1 wins, checkpoint `a10752ccf12b513c...`, replay
`6f99df0a3243de3f...`, and full-run digest `6d8912cbc00766c6...`. Mean idle is
0.26628148, which misses the precommitted `<0.25` continuation bar. V12 is
rejected before confirmation; dev-v8 and held-out-v4 remain unopened.

ADR-0023 precommits V13 after permitted dev-v1 frontier analysis shows that
checkpoint selection, rather than reward construction, excluded a 10/10,
0.24980951-idle update. V13 must rerun the exact V12 construction twice with a
selector that first requires at least 9/10 wins and idle `<0.25`, then uses the
existing ranking. V12 artifacts are not retroactively relabeled. Dev-v8 is
retired unopened; a disjoint 160-root dev-v9 set is frozen for one exclusive
ADR-0019 confirmation. The strict gate, per-checkpoint idle evidence, and
version-compatible reproducibility evidence are implemented. Two exact V13
runs select update 24 at 10/10 dev-v1 wins and mean idle 0.24980951. Checkpoint
`ff5c21bc6644d903...`, replay `c556d3ec24f06c8a...`, full-run digest
`842ac034e91e84ae...`, and lineage `8aff4629be3090b3...` reproduce. V13 is
authorized for dev-v9 only; held-out-v4 remains sealed.

Dev-v9 completes once at V13 152/160, permanent random 62/160, permanent greedy
92/160, matched random 13/160, and matched greedy 15/160. Every win gate and
matched-greedy scorecard passes. Permanent-greedy duplicates pass, but
announcements, idle, recovery, and abandonment fail. V13 is rejected, dev-v9
is consumed, held-out-v4 remains sealed, and M8.5 remains unmet.

Exit criteria:
- [x] M8_DESIGN.md + ADR-0011/0012 accepted; reward audit rows complete
- [x] Training runs reproducible (manifest + seeds + lockfile)
- [ ] Learned seat CI-beats greedy-utility on held-out; scorecard non-regressing
- [x] No known reward exploit; adversarial scripts in CI-runnable form

## Milestone 9: Multi-agent learning + partner robustness

Objective: all seats learned (parameter-shared IPPO → MAPPO), trained and
evaluated against a PARTNER POPULATION so coordination does not overfit to
clones. This is where "teammate" starts being trained for directly.

- 9.1 Parameter-shared IPPO (per-agent role embedding + hidden state); team
  reward with small individual shaping (audited per component, as 8.1).
- 9.2 Partner population: scripted variants (greedy, role, adaptive-v1,
  delayed, noisy, occasionally-declines-help, drops-mid-episode), frozen old
  checkpoints; every training batch mixes partners; evaluation matrix includes
  unseen-partner cells.
- 9.3 Communication value ablation: board-visible vs board-hidden actors —
  announcements must provide measurable coordination benefit, else the
  observation/featurization of board state needs rework (result recorded
  either way).
- 9.4 MAPPO centralized critic (training-only global state; ADR if the critic
  needs new privileged observation channels).
- 9.5 Robustness curriculum: agent dropout mid-episode, lease-expiry recovery,
  helper-decline tolerance — scorecard's recovery metrics become training
  distribution, not just evaluation.

Exit criteria:
- [ ] Multi-agent learned team CI-beats the best scripted team on held-out variants
- [ ] Graceful degradation with one seat dropped (quantified vs scripted)
- [ ] Communication ablation shows positive value of the structured board
- [ ] Performance holds with unseen partner checkpoints + scripted partners

## Milestone 10: The human-teammate milestone (north star)

Objective: a skilled human plays bootstrap-defense (and variants) WITH the
agents and rates them teammates worth keeping. Human-cooperation capability is
built, measured, and iterated here — on the SAME brain that trains (7.2).

- 10.1 Human command surface v2: `/agents goal <task> <region>`,
  `/agents assign <agent> <task>`, `/agents release <agent>`,
  `/agents autonomy low|normal|high`, `/agents quiet on|off` — human-created
  goals become high-priority board tasks entering the SAME candidate stream
  (human_priority weight already exists); validated, confirmable, revocable.
- 10.2 Human-presence adaptation: detect human build plans/recent construction
  zones in the demo (plugin observes player plans), register them as
  human-priority reservations (board rule exists — wire the detection), agents
  yield + announce the conflict exactly once; never deconstruct human work;
  never consume the human's reserved resource budget below a floor.
- 10.3 Human session capture (local, opt-in): demo sessions record the same
  event/trajectory JSONL as training episodes + human actions; from these,
  (a) partner-style statistics (pace, role preference, plan-changes) and
  (b) scripted human-partner models (fast-expert / slow-beginner / cautious /
  plan-changer / help-requester) join the M9 partner population.
- 10.4 Teammate scorecard v1 (human terms): human intervention rate, plan
  conflicts per session, yield latency, goal-compliance rate, time-to-help on
  human requests, announcement usefulness rating, post-session preference
  ("keep this team?" + comparative rating vs scripted team). Session protocol
  documented; results logged per session in runs/.
- 10.5 Learned policy in the demo seat: latency budget (decision within one
  real-time tick), safety invariants live (stop/pause instant, autonomy
  levels honored), fallback to scripted brain on policy-process failure.
- 10.6 Iterate to the bar: fine-tune against the human-partner population;
  exit when scorecard targets hold across ≥3 distinct human sessions and the
  human prefers playing WITH agents vs without on the same scenario.

Exit criteria:
- [ ] Human goals/overrides work end to end; agents never fight human plans
- [ ] Human sessions captured; human-partner models in the training population
- [ ] Learned team scores ≥ scripted team on scorecard v1 WITH a human present
- [ ] The project owner, playing seriously, prefers the agent team present
      (recorded sessions + ratings) — the north-star acceptance

---

Cross-cutting (any milestone): protobuf migration only if profiling crosses
the ADR-0004 trigger; engine pin frozen; every new reward component blocked on
its REWARD_AUDIT row; docs/STATUS.md + HANDOFF.md updated per change, as ever.
