# Roadmap

Milestones M0–M10 from brief §25, as trackable checklists with exit criteria.
Checkboxes reflect **truthful** current state (date 2026-07-23). A box is ticked
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
- [x] Python lockfiles created (`requirements-rl-linux-py312.lock` for the
      pinned CPU training runtime and `requirements-dev-linux-py312.lock` for
      the CI test tools; both hash-locked and reproducible with uv 0.11.16)
- [x] `AGENTS.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `STATUS.md`, `HANDOFF.md`
- [x] CI builds Java and runs Python tests (`coop-agent-ci.yml` uses SHA-pinned
      actions and hash-locked Python dependencies; hosted Ubuntu 24.04 run
      `29972868046` passed bootstrap, all tests, and distribution builds on
      2026-07-23)
- [x] One-command bootstrap for reference runtime (`make bootstrap` / `scripts/bootstrap.sh`)

Exit criteria:
- [x] Fresh checkout can run `make bootstrap` and `make test` (verified
      2026-07-23 from detached clean commit `43d3b17db6` on Ubuntu 24.04 with
      an isolated JDK 21.0.11, GNU Make 4.3, empty Gradle cache, and no Python
      dependencies: 33 core tests plus Java suites/custom-module compile green)
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

ADR-0024 precommits scorecard v2 for future evidence only. V1's abandonment
rate incorrectly includes forced safety/lifecycle preemption that reward v2
explicitly excludes. V2 derives the rate from structured non-forced ABANDON
events, retains forced/non-forced counts, and adds per-agent idle telemetry.
The implementation passes 128 Python tests plus build, smoke, determinism, and
live counter reconciliation. All consumed results remain immutable and V13
stays rejected.

Reusable dev-v1 transition-duration analysis also found that successful policy
abandonment was not visible to stop-on-event stepping: the server sampled the
decision revision after applying actions, so 30 V13 abandons consumed 23,371
ticks while waiting for unrelated boundaries. Successful `ABANDON` now marks
`task_terminal`, the step samples revision before the action bundle, and the
live reservation check requires exactly one fixed tick before replanning. The
semantically unchanged two-win/16,200-tick golden was regenerated for the
corrected state hashes; 128 Python tests, build, smoke, determinism, and the
negative replay check pass. V13 remains rejected and dev-v9 remains consumed.

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

ADR-0025 precommits V14 after the corrected boundary replays rejected V13 on
reusable dev-v1 at 10/10 wins and mean idle 0.20217810, but reveals 105
non-forced resource-short replans and still fails the dual scorecard. V14 must
retrain from scratch under the one-tick successful-abandon runtime while
holding V13's reward, optimizer, architecture, RNG seeds, train/dev roots,
schedule, and checkpoint-selection rule fixed. Two exact 2,048-episode runs
must reproduce. Reusable dev-v1 must meet 9/10 wins, idle `<0.25`, and both
permanent/matched scorecards before a one-way confirmation can begin. Dev-v10
is frozen at 160 disjoint roots `101001..101160`; the 129-test Python suite
passes and held-out-v4 remains sealed.

Two exact V14 2,048-episode replicas select update 32 at 10/10 reusable dev-v1
wins and mean idle 0.15861366. Checkpoint `d403044cc5adec74...`, replay
`c6647a44b09ce7eb...`, full-run digest `ecd8776cda1430d5...`, and lineage
`52f6138246423c54...` reproduce. Fresh scorecard-v2 permanent baselines and the
corrected dual preflight then reject V14: permanent-greedy idle and non-forced
abandonment are definitively worse, while recovery is uncertain. Dev-v10 is
unopened, held-out-v4 remains sealed, and M8.5 remains unmet.

ADR-0026 precommits V15 from reusable V14 dev-v1 evidence: 59 learned WAIT
choices consume 34,993/81,000 ticks and the selected checkpoint is already the
lowest-idle 10/10 frontier point. V15 holds the complete V14 construction fixed
except idle cost `0.0001 -> 0.0003` and non-forced team-abandon cost
`0.1 -> 0.25`; the abandonment cap remains `2.0`. The adversary runner now
hashes the exact candidate config, and all 37 cases plus 131 Python tests pass.
Dev-v10 is retired unopened. Dev-v11 freezes 160 disjoint roots
`111001..111160` for one confirmation only after reusable dual scorecards pass;
held-out-v4 remains sealed.

Two exact V15 2,048-episode replicas select update 25 at 10/10 reusable dev-v1
wins and mean idle 0.21873675. Checkpoint `a328550d36448897...`, replay
`32735e17026b8903...`, full-run digest `22792939f896fbd0...`, and lineage
`0db57e0879cca7df...` reproduce. Non-forced abandonment improves to 0.01673964,
but the corrected dual preflight rejects V15 because permanent-greedy idle is
definitively worse; recovery and matched idle remain uncertain. Dev-v11 is
unopened, held-out-v4 remains sealed, and M8.5 remains unmet.

V16's two pinned 2,048-episode replicas reproduce exactly and select update 23
at 9/10 construction wins with mean idle 0.10050130. Checkpoint
`6db48a03427edfa2...`, model state `91c3364b793d7091...`, replay
`4862b1a8a319d8bf...`, full run `65bebd16464f95a1...`, and direct lineage
`a172fad58f842f6e...` reproduce. Reusable dev-v1 shows zero non-forced
abandonment and matched-greedy idle improvement of 0.12929577, but rejects the
candidate because permanent-greedy idle remains 0.05618951 worse (95% CI
+0.03029619..+0.08042806) and recovery is uncertain against both scorecards.
Dev-v12 remains unopened, held-out-v4 remains sealed, and M8.5 remains unmet.

V17's two pinned 2,048-episode replicas reproduce exactly and select update 17
at 9/10 construction wins with mean idle 0.08594077. Checkpoint
`6dbde34e0b745b55...`, model state `701bff0e24bfae60...`, replay
`ab01623eda4d40ea...`, full run `8b210937805c23f3...`, and direct lineage
`233282b7fc536cb3...` reproduce. Reusable dev-v1 still rejects the candidate:
permanent-greedy idle is 0.04162898 worse (95% CI
+0.01733907..+0.06734018), permanent announcements and both recovery
comparisons are uncertain. Non-forced abandonment remains zero and matched
idle improves by 0.14385630. Dev-v13 remains unopened, held-out-v4 remains
sealed, and M8.5 remains unmet.

V17's paired idle and recovery gaps have approximately -0.08 correlation, and
idle-only pressure did not resolve recovery. ADR-0029 therefore precommits V18
as a scorecard-aligned reward extension. Idle cost becomes `0.004` with the
`5.0` cap fixed; announcement cost becomes `0.01` with its `1.0` cap fixed; and
an optional recovery-delay component charges `0.001` per deterministic tick,
capped at `3.0`, until a different agent resumes a lost agent's prior structured
task type. Unrecovered roles continue charging, so the signal cannot be evaded
by refusing takeover. Duplicate cap becomes `4.0` solely to retain the exact
busywork ordering. Historical configs omit the recovery fields and remain
exact. All 43 exact-config adversaries and 138 Python tests pass. Dev-v13 is
retired unopened; dev-v14 freezes 160 disjoint roots `141001..141160` for one
confirmation only after reusable dual scorecards pass. Held-out-v4 remains
sealed.

V18's two pinned 2,048-episode replicas reproduce exactly and select update 22
at 9/10 construction wins with mean idle 0.10978972. Checkpoint
`0984700a681bfdc5...`, model state `2fd25b37851c1d97...`, replay
`d098fba29b3de64f...`, full run `127410b515f6917e...`, and direct lineage
`b226742761e58852...` reproduce. Reusable dev-v1 rejects the candidate because
permanent-greedy idle is 0.06547793 worse (95% CI
+0.03188818..+0.09708444). Recovery is also uncertain against permanent
greedy (-6.85 ticks, 95% CI -93.62..+114.80) and matched greedy (-42.52 ticks,
95% CI -214.79..+118.93). Announcements, duplicate work, and abandonment
non-regress, and matched idle improves by 0.12000735. Dev-v14 remains unopened,
held-out-v4 remains sealed, and M8.5 remains unmet.

ADR-0030 precommits V19 from reusable diagnostics only. V18 reaches its idle
cap in 8/10 selected dev episodes, after just 1,250 idle-agent ticks, and
per-agent counters show downstream seat 1 dominates the permanent-idle gap
(`0.174262` versus `0.031523`). V19 restores idle cost `0.002` and raises its
cap to `8.0`, preserving differentiation through 4,000 idle-agent ticks. The
duplicate cap rises to `7.0`, so capped duplicate plus abandonment churn
(`-9.0`) remains strictly worse than capped honest idle (`-8.0`). All other V18
fields remain exact. A new full-horizon busywork adversary closes the prior
cap-ordering gap; all 44 exact cases, 140 Python tests, smoke, and determinism
pass. Dev-v14 is retired unopened; dev-v15 freezes 160 disjoint roots
`151001..151160` for one confirmation only after reusable dual scorecards pass.
Held-out-v4 remains sealed.

V19's two pinned 2,048-episode replicas reproduce exactly and select update 24
at 9/10 construction wins with mean idle 0.09911830. Checkpoint
`1a9376a331b3aadc...`, model state `510e07d964c84de0...`, replay
`75bf5fb9cc34d5a6...`, full run `4d15c3a728f33d4c...`, and direct lineage
`121a7400b241ce77...` reproduce. The longer cap reduces selected-dev saturation
from 8/10 to 2/10 episodes and improves permanent idle from a 0.06547793 gap to
0.05480651, but it remains definitively worse (95% CI
+0.02786525..+0.08510262). Recovery remains uncertain against both scorecards,
and non-forced abandonment regresses slightly by 0.00131579. Dev-v15 remains
unopened, held-out-v4 remains sealed, and M8.5 remains unmet.

ADR-0031 closes the idle-cap line and precommits V20 from reusable train/dev
evidence. The all-adaptive teacher wins 9/10 with a much smaller permanent-idle
gap of 0.01737902 and zero abandonment difference, while V19 disagrees with its
action on 529/607 unforced decisions. V20 holds V19 exact except
`teacher_imitation_coefficient 0.0 -> 0.05` at every unforced boundary. This is
well below V10's failed `1.0` coefficient and changes training loss only, not
reward or inference. Teacher candidate diagnostics are added to traces without
entering action/state digests. All 44 exact adversaries, 141 Python tests,
smoke, and determinism pass. Dev-v15 is retired unopened; dev-v16 freezes 160
disjoint roots `161001..161160` for one confirmation only after reusable dual
scorecards pass. Held-out-v4 remains sealed.

V20's two pinned 2,048-episode replicas reproduce exactly and select update 32
at 9/10 construction wins with mean idle 0.09850656. Checkpoint
`6209f46876db0778...`, model state `1ba534267c67ff54...`, replay
`a1bc0eec0c7f0002...`, full run `a407aa303e839844...`, and direct lineage
`564f7fdca22f0ba9...` reproduce. Teacher disagreement drops from 529/607 to
170/362 unforced decisions and abandonment returns to zero, proving the loss
changed behavior. It does not improve permanent idle, which remains 0.05419477
worse (95% CI +0.02812093..+0.08298135); permanent announcements/duplicates
and both recovery comparisons are uncertain. Dev-v16 remains unopened,
held-out-v4 remains sealed, and M8.5 remains unmet.

Exact reconstruction of assignment occupancy from all ten reusable V20 traces
matches the runtime idle counters and identifies a scheduling defect: automatic
`WAIT` success emitted structured `RELEASE` and cleared the assignment without
advancing the coordination decision revision. Stop-on-event could then leave a
seat idle until an unrelated event; observed gaps reached 2,086 ticks. A
successful wait release now marks the ended assignment `task_terminal` while
the reusable board task correctly returns to `OPEN`. The live reservation gate
requires the response to stop on the release tick after the deterministic
61-tick lifecycle and reproduces byte-identically across fresh JVMs. The pinned
build, 141 Python tests, smoke, determinism, and unchanged 664-checkpoint golden
pass. Previously trained checkpoints keep their recorded results; V21 must be a
governed from-scratch retrain under the corrected decision sequence, with a new
runtime contract and unopened dev-v17 precommitted before model work.

ADR-0032 precommits V21 as an exact V20 retrain under runtime contract
`successful_abandon_one_tick_wait_release_same_tick_v2`. Candidate ID, runtime
contract, and confirmation path are the only config differences; retaining the
frozen `0.05` teacher coefficient isolates this runtime correction rather than
confounding it with another loss change. Dev-v16 is retired unopened. Dev-v17
freezes 160 globally disjoint roots `171001..171160` for one exclusive
confirmation only after exact replicas, reusable construction, and both
permanent/matched scorecards pass; held-out-v4 remains sealed. The 44 exact
reward adversaries, 142 Python tests, pinned build, smoke, and determinism pass.
Config SHA-256 is `5567e1c1d79cae0f...`; adversary report SHA-256 is
`732536ffcd358d25...`.

V21's two pinned 2,048-episode replicas reproduce exactly and select update 29
at 9/10 construction wins with mean idle 0.04383598. Checkpoint
`68c3dfba722e0b75...`, model state `5c09bf859571ac2c...`, replay
`81ca21dfe5d634b4...`, full run `5d5831a59032c57e...`, and direct lineage
`df5af947a70f6a8c...` match. The runtime correction removes the definitive
permanent-idle regression: candidate-minus-greedy is -0.00047581 (95% CI
-0.00999458..+0.01044892), while matched idle and recovery improve decisively.
Reusable preflight nevertheless rejects V21 because task abandonment is
definitively worse by 0.04347388 against both permanent greedy (95% CI
+0.02043040..+0.06680916) and matched greedy (95% CI
+0.01956487..+0.06757326). In six episodes the learned seat selects one
resource-short supply target, abandons it, and repeats the same target three
times at two-tick cadence before the fourth selection succeeds: 18 non-forced
replans absent from matched greedy. Announcements, duplicates, and permanent
recovery remain uncertain. Dev-v17 remains unopened, held-out-v4 remains
sealed, and M8.5 remains unmet.

The repeated-retry cause is now corrected in the runtime before any V22 model
work. The adapter retains and hashes the blocked skill's authoritative
`nextRetryTick`, masks only equivalent type/target work while `tick` is earlier,
rejects a direct selection bypass as `retry_not_due`, keeps alternative non-WAIT
work legal, and reopens the same candidate exactly when due. The live fixture
proves `BUILD_SCHEMATIC` block tick 607 -> retry tick 667. The broader public gate
also exposed stale ownership after real unit loss; dead fixed seats now emit
forced structured `ABANDON(agent_death)`, release reservations, wake
`task_terminal`, and permit only no-op WAIT. All five fixed seeds win with 12
loss releases. Two regenerated golden recordings match at SHA-256
`f08c5af6b6ea4e25908da8b59e10ba7f4d10afdef7306529859ef726023dccd2`;
all 664 hash fields change because retry eligibility joins canonical state, but
all non-hash records remain identical and the negative mutation still diverges.
V22 still requires a precommitted runtime contract, fresh unopened dev-v18, and
a from-scratch exact-replica training run; M8.5 remains unmet.

ADR-0033 now supplies that precommit. V22 is an exact V21 retrain under runtime
contract `abandon_wait_retry_and_agent_death_boundaries_v3`; candidate ID,
runtime contract, and confirmation path are the only config differences. Reward,
teacher coefficient `0.05`, train/dev roots, model, optimizer, RNGs, schedule,
and checkpoint selection remain frozen. Dev-v17 is retired unopened; dev-v18
freezes globally disjoint roots `181001..181160` and remains unopened; held-out-v4
remains sealed. The 44 exact-config reward adversaries, 143 Python tests, pinned
build, five-seed candidate gate, smoke, determinism, and negative replay pass.
Config/adversary SHA-256 are `95bc200596718170...` and
`18f337ac3ca54700...`. No V22 model work began before this packet; exact twin
replicas and reusable preflight are next, and M8.5 remains unmet.

V22 replica A completed all 2,048 episodes/32 updates but correctly failed its
precommitted construction gate before a selected checkpoint or run manifest was
produced. All frontier idle means were `0.43868123..0.54747927`; update 17 was
10/10 wins but `0.48320387` idle. Replica B did not start, dev-v18 remained
unopened, and held-out-v4 remains sealed. The reconstructed frontier hashes to
`17d8afa6e7fb2f3360d327ef76d0ee082dc8fe3aa6d77926c532c7051ae380d4`.
The real-agent-loss correction had exposed a metric defect: dead seats still
accumulated both `agent_ticks` and idle forever. Occupancy now partitions each
seat-tick into available or unavailable, and idle applies only to available,
unassigned seats. A diagnostic update-17 replay under the corrected metric is
10/10 with mean idle `0.13474577`, but V22's training reward was contaminated,
so its checkpoint cannot be promoted or relabeled. V22 is rejected, dev-v18 is
retired unopened, and a fresh governed retrain is required before any new
confirmation set can be opened. M8.5 remains unmet.

ADR-0034 precommits V23 as the exact V22 construction under corrected runtime
contract `abandon_wait_retry_agent_death_available_idle_v4`. Candidate ID,
runtime contract, and confirmation path are the only config differences; all
reward fields, teacher coefficient `0.05`, train/reusable-dev roots, model,
optimizer, RNGs, schedule, and checkpoint selection remain frozen. Dev-v18 is
retired unopened. Dev-v19 freezes 160 globally disjoint roots `191001..191160`
and remains unopened; held-out-v4 stays sealed. All 44 exact-config reward
adversaries, 145 Python tests, pinned build, five-seed availability ledger,
smoke, determinism, and negative replay pass. Config/adversary SHA-256 are
`17e741e63f9862bc...` and `e2043acefb24a016...`. No V23 model work preceded
this packet; exact twin replicas and reusable preflight are next. M8.5 remains
unmet.

V23's two admissible pinned replicas reproduce update 5 exactly at 10/10
construction wins and mean idle `0.09043677` (checkpoint
`2ae62cc31c86731a...`, full run `85dfb4e2596cd653...`, direct lineage
`b532f8cb8df8e3c...`). Reusable preflight rejects the candidate before dev-v19:
abandonment is definitively `+0.04490747` worse than both permanent and matched
greedy, and permanent idle is definitively `+0.03999701` worse. Preflight hash
is `4237a8503bb4bff4...`; dev-v19 remains unopened and is retired, held-out-v4
remains sealed, and M8.5 remains unmet.

Trace review found 31/32 non-forced abandons alternating resource-short supply
targets every two ticks. The adapter's single target-local slot allowed each
new target to overwrite the previous holdoff. Retry state is now an ordered,
canonical-hashed set. `CORE_SHORT`/`RESOURCES_SHORT` holdoffs apply to the task
type, other failures remain target-local, direct bypass returns
`retry_not_due`, unrelated task types remain legal, and entries reopen exactly
when due. The live two-turret fixture proves tick 432 -> 492 behavior; the
pinned build, 145 Python tests, 5/5 candidate gate, smoke, determinism, and
negative replay pass. Two final golden recordings match at
`8fee3db9b5cf01f2...`; all 664 state hashes change with zero non-hash changes.
The old V23 checkpoint's diagnostic is not promotion evidence. V24 must be
precommitted and retrained from scratch under this corrected decision sequence.

ADR-0035 precommits V24 as an exact V23 retrain under runtime contract
`abandon_wait_resource_scoped_retry_agent_death_available_idle_v5`. Candidate
ID, runtime contract, and confirmation path are the only config differences;
reward, teacher coefficient `0.05`, train/reusable-dev roots, model, optimizer,
RNGs, schedule, and checkpoint selection remain frozen. Dev-v19 is retired
unopened. Dev-v20 freezes 160 globally disjoint roots `201001..201160` and
remains unopened; held-out-v4 stays sealed. No V24 model work preceded this
packet. All 44 exact-config reward adversaries, 146 Python tests, the pinned
build, five-seed candidate gate, smoke, determinism, and negative replay pass.
Config/adversary SHA-256 are `94a7ae8cf57cb1ce...` and
`4cd7f5096bbd0ebc...`. Exact twin replicas and reusable preflight are next;
M8.5 remains unmet.

V24 replica A completed all 2,048 episodes/32 updates but no checkpoint reached
the frozen 9/10 construction threshold. The best ranking row is update 19 at
8/10, mean return `1.20730`, mean core health `692.8`, and mean idle
`0.06516475`; the retained frontier hashes to `90ead621f808c53f...`. Replica B
did not start, dev-v20 remained unopened and is retired, and held-out-v4 stays
sealed. Current-runtime reusable diagnosis shows adaptive-v1 at 10/10, idle
`0.07308979`, and zero abandonment; V24 update 19 disagrees on 73/427 unforced
decisions and loses seeds 2004/2005. V24 is rejected and M8.5 remains unmet.

ADR-0036 precommits V25 from reusable evidence only. Current-runtime
adaptive-v1 wins 10/10 with idle `0.07308979` and zero abandonment, while V24
update 19 disagrees on 73/427 unforced decisions. V25 holds the V24 runtime,
reward, roots, model, optimizer, RNGs, schedule, and selection exact and changes
only full-boundary teacher coefficient `0.05 -> 0.10` (plus candidate/label/
confirmation metadata). This remains tenfold below V10's failed `1.0`. Dev-v20
is retired unopened; dev-v21 freezes disjoint roots `211001..211160` and remains
unopened; held-out-v4 stays sealed. No V25 model work preceded this packet.
All 44 exact-config reward adversaries, 147 Python tests, pinned build, 5/5
candidate gate, smoke, determinism, and negative replay pass. Config/adversary
SHA-256 are `90b50d1b7add7fd0...` and `8faa7834e426678e...`. Exact replicas
are next; M8.5 remains unmet.

V25 replica A completed 2,048 episodes/32 updates but again peaked at 8/10, so
replica B did not start and dev-v21 remains unopened and is retired. Best update
16 has mean return `1.20830`, core health `693.7`, and idle `0.06516475`; the
retained frontier hashes to `0ad699ece62ab94b...`. The coefficient did move
optimization: update 1 rose from V24's 1/10 to 7/10, and the mean disagreement
logit gap fell from `1.49301094` to `1.07148486`. It did not flip the 73
disagreements or losses on seeds 2004/2005. V25 is rejected; M8.5 remains unmet.

ADR-0037 precommits V26 as the final fixed full-boundary teacher step. V25's
directional logit movement authorizes `0.10 -> 0.20`, still fivefold below the
failed `1.0`; failure to reach 9/10 closes this coefficient line. Runtime,
reward, roots, model, optimizer, RNGs, schedule, and selection remain exact;
only coefficient plus candidate/label/confirmation metadata change. Dev-v21 is
retired unopened. Dev-v22 freezes disjoint roots `221001..221160` and remains
unopened; held-out-v4 stays sealed. No V26 model work preceded this packet.
All 44 exact-config adversaries, 148 Python tests, pinned build, 5/5 candidate
gate, smoke, determinism, and negative replay pass. Config/adversary hashes are
`b5e3bf17a1dc1ace...` and `202e71a48bf8a05f...`. Replica A is next;
M8.5 remains unmet.

V26 replica A completed 2,048 episodes/32 updates but regressed to a maximum of
5/10. Best update 10 has mean return `-5.01232`, core health `533.8`, and idle
`0.06423822`; the retained frontier hashes to `0f67cf4484c09ad7...`. Replica B
did not start, dev-v22 remained unopened and is retired, and held-out-v4 stays
sealed. The final `0.20` step reverses V25's early gain, so the fixed full-
boundary teacher-strength line is closed. No coefficient-only successor is
authorized; M8.5 remains unmet.

ADR-0038 precommits V27 as a trajectory-quality intervention rather than a
coefficient step. It returns to V24's exact low `0.05` online-teacher recipe and
adds one separately seeded adaptive-v1 cycle over all 64 train-v2 roots before
PPO. The current runtime teacher wins 5/64; only the 121 unforced transitions
from those successful complete sequences enter eight deterministic CE epochs
(968 sample presentations), while all episode summaries remain reproducibility
evidence. Reward, runtime, model, PPO budget, ordinary RNGs, roots, checkpoint
selection, and evaluation remain exact. Dev-v22 is retired unopened. Dev-v23
freezes disjoint roots `231001..231160` and remains unopened; held-out-v4 stays
sealed. No V27 model work preceded the precommit. Complete pretraining gates
pass: 44 exact-config adversaries, 152 Python tests, pinned build, 5/5 candidate
gate, smoke, determinism, and negative replay. Config/adversary hashes are
`189ef43857452494...` and `d1c1da02ed7d3a4e...`. A committed packet is required
before replica A; M8.5 remains unmet.

V27 replica A completed its 64 teacher-controlled episodes and all 2,048 PPO
episodes/32 updates but failed construction. The warmup exactly exposes 5/64
wins, 121 eligible labels, and 968 sample presentations; model state changes
`dbae4c605e52b962... -> ce95e9b0aa8ab34a...`, with report hash
`b4ca44db858a84a8...`. Eighteen updates reach 8/10, but none reaches 9/10. Best-
ranked update 20 has mean return `1.10996`, core health `601.9`, and idle
`0.07044212`; the complete frontier hashes to `d23df387d15966f17...`. Replica B
did not start, dev-v23 remained unopened and is retired, held-out-v4 stays
sealed, and V27 is rejected before reusable preflight. M8.5 remains unmet.

ADR-0039 precommits V28 from reusable evidence only. V27's initial successful-
teacher prior is present at update 1 (mean disagreement margin `0.02482445`) but
is erased by best-ranked update 20 (134/401 disagreements, margin `2.24436055`,
worse than V24). V28 therefore holds V27 exact and applies one separately seeded
CE rehearsal epoch over the same five winning teacher episodes after every PPO
update, before checkpoint/dev evaluation. Seed `8607`, optimizer ordering, and
an atomic per-update report are explicit. Warmup strength, online teacher
coefficient, reward, runtime, roots, model, PPO budget, ordinary RNGs, selection,
and inference remain unchanged. Dev-v23 is retired unopened. Dev-v24 freezes
disjoint roots `241001..241160` and remains unopened; held-out-v4 stays sealed.
No V28 model work preceded the packet. All 44 exact-config adversaries, 153
Python tests, pinned build, 5/5 candidate gate, smoke, determinism, and negative
replay pass. Config/adversary hashes are `ef58055e7da5566d...` and
`2d672a7f0e816a41...`. A committed packet is required before replica A; M8.5
remains unmet.

V28 replica A completed all 64 warmup episodes, 2,048 PPO episodes, and 32
rehearsal-bearing updates but failed construction. Rehearsal CE falls
`1.39527905 -> 1.31666994`, with 32-update report hash `2bd187fea8635206...`.
Ten updates reach 8/10 but none reaches 9/10. Best-ranked update 27 has mean
return `1.11366`, core health `516.4`, idle `0.07046312`, and the same 134/401
teacher disagreements and losses on 2004/2009 as V27's best. Mean disagreement
margin improves `2.24436055 -> 1.81065121` but no action flips; complete frontier
hash is `ba963bea1d0d303b...`. Replica B did not start, dev-v24 remained unopened
and is retired, held-out-v4 stays sealed, and V28 is rejected before reusable
preflight. M8.5 remains unmet.

ADR-0040 precommits V29 as a successful-corpus diversity intervention. V28
reduced disagreement margin without changing its 134/401 actions, so increasing
strength on the same 121 labels is rejected. Before any outcomes are observed,
V29 freezes a separate 256-root train-only teacher set `291001..291256`. All
teacher episodes and outcomes are archived; only complete wins enter the same
eight-epoch warmup and one-epoch-per-update rehearsal. PPO remains exactly V28:
the original 64 roots, 2,048 episodes, 32 updates, reward, runtime, model,
optimizer values, RNG values, online coefficient, selection, and inference.
Dev-v24 is retired unopened. Dev-v25 freezes disjoint roots `251001..251160` and
remains unopened; held-out-v4 stays sealed. No teacher outcomes/model work had
been observed at precommit. All 44 exact-config adversaries, 154 Python tests,
pinned build,
5/5 candidate gate, smoke, determinism, and negative replay pass. Config/
adversary hashes are `a40a8772ef5392fb...` and `cac12af7f0861dea...`. A committed
packet is required before V29 collection/model work; M8.5 remains unmet.

V29 replica A completed all 256 teacher episodes, 2,048 PPO episodes, and 32
rehearsal-bearing updates but failed construction. The frozen teacher set yields
37 wins and 860 eligible transitions; eight warmup epochs have mean CE
`1.38471070` and report hash `582f362322e4aa43...`. Rehearsal CE falls
`1.32362124 -> 0.46930411`, with report hash `b5c089bf4d85acd2...`, but no
checkpoint exceeds 4/10. Best-ranked update 5 has mean return `-10.68702`, core
health `182.6`, and idle `0.21429663`; complete frontier hash is
`26c6270efca0c852...`. Replica B did not start, dev-v25 remained unopened and is
retired, held-out-v4 stays sealed, and V29 is rejected before reusable preflight.
M8.5 remains unmet.

ADR-0041 precommits V30 after V29 exposed a presentation-budget confound. The
successful corpus grew from 121 to 860 transitions, so fixed epoch counts also
grew warmup presentations `968 -> 6,880` and per-update rehearsal
`121 -> 860`; the best construction result fell from V28's 8/10 to V29's 4/10.
V30 holds V29 exact but deterministically caps each warmup and rehearsal epoch
at 121 sampled transitions. This restores V28's eight warmup batches and one
rehearsal batch per PPO update while rotating through all 860 eligible labels;
exact sampled indices and schedule hashes join reproducibility evidence.
Dev-v25 is retired unopened. Dev-v26 freezes disjoint roots `261001..261160`
and remains unopened; held-out-v4 stays sealed. No V30 teacher collection or
model work preceded the committed packet. All 44 exact-config adversaries, 155
Python tests, pinned build, 5/5 candidate gate, smoke, determinism, and negative
replay pass. Config/adversary hashes are `c57556695157dcd4...` and
`a3bcf116478e1be0...`. Replica A is next; M8.5 remains unmet.

V30 replica A reproduced the 37-episode/860-transition eligible corpus and
completed all 2,048 PPO episodes/32 updates, but failed construction at a
maximum 8/10. Warmup consumes exactly 968 presentations/eight batches and
samples 603 unique transitions; report hash is `7f92ee1bdaa59d8f...`.
Rehearsal consumes exactly 3,872 presentations, collectively covers 855/860
transitions, and lowers CE `1.41403544 -> 1.05248463`; report hash is
`a2559f5651cc0d54...`. Twenty-one updates reach 8/10. Best-ranked update 11 has
mean return `1.18132`, core health `686.5`, and idle `0.06573742`; complete
frontier hash is `e841b620424e0299...`. Replica B did not start, dev-v26 remained
unopened and is retired, held-out-v4 stays sealed, and V30 is rejected before
reusable preflight. M8.5 remains unmet.

ADR-0042 precommits V31 from reusable evidence only. V30 update 11 recreates
V24's losses on seeds 2004/2005; seed 2004 has just six unforced decisions and
two teacher disagreements. At tick 0 every reusable seed chooses `BUILD_LINE`
over the teacher's `BUILD_SCHEMATIC` by margin `0.83764815..0.85484707`. V31
holds V30 exact and adds a precommitted `+1.0` logit prior only to a valid
`BUILD_SCHEMATIC` candidate at tick 0. It remains a masked model selection, not
a forced action; the same tensor enters rollout, PPO, warmup/rehearsal CE, and
all evaluation paths, while bias-free configs retain their exact path. Dev-v26
is retired unopened. Dev-v27 freezes disjoint roots `271001..271160` and remains
unopened; held-out-v4 stays sealed. No V31 model work preceded the committed
packet. All 44 exact-config adversaries, 156 Python tests, pinned build, 5/5
candidate gate, smoke, determinism, and negative replay pass. Config/adversary
hashes are `861f34bd07db43a5...` and `e7eb2f8826db4617...`. Replica A is next;
M8.5 remains unmet.

V31 replicas reproduce selected update 16 exactly at 9/10 reusable wins, mean
return `3.11808`, core health `891.0`, and idle `0.07742222`. Checkpoint,
model-state, replay, canonical full-run, and direct-lineage hashes are
`6961656faaee8d93...`, `d87d193cb36e6604...`, `b9f7e84c938a0bd3...`,
`b2dacf42484258fb...`, and `78e923796393ca58...`. Reusable dev-v1 then beats
all four observed win-rate comparators but fails corrected scorecard parity:
permanent-greedy idle regresses `+0.02698246` and abandonment `+0.03137446`
with paired intervals wholly above zero; matched-greedy abandonment also
regresses, and recovery plus permanent announcements are uncertain. V31 is
rejected, dev-v27 remains unopened and is retired, held-out-v4 stays sealed,
and M8.5 remains unmet.

ADR-0043 precommits V32 from reusable structured traces. Every one of V31's 13
non-forced abandons is a one-copper `SUPPLY_TURRET` start that blocks at zero
live copper, and every available idle run exposes only WAIT during a quiet
pre-wave gap. V32 holds V31 exact but masks supply unless the core or selecting
unit currently has copper, then adds a priority-1.0 nonexclusive defense-
staging task for learned seat 0 only when no ordinary work exists; its duration
ends at the existing defend-lead boundary. The initial all-seat implementation
failed public seed 23456 (4/5), and the pretraining correction restored 5/5 by
preserving the scripted partners exactly. Engine-free/live checks, the pinned
112-test Java build, candidate gate, smoke, determinism, negative replay, 157 Python
tests, and all 44 exact-config reward adversaries pass. Dev-v27 is retired
unopened. Dev-v28 freezes globally disjoint roots `281001..281160` and remains
unopened; held-out-v4 stays sealed. This packet was committed before V32 model
work. M8.5 remains unmet.

V32's two pinned replicas reproduce selected update 28 exactly at 10/10,
return `5.58316`, core health `639.2`, and idle `0.06066571`. Checkpoint,
model-state, replay, canonical full-run, and direct-lineage hashes are
`72e10ec9dcf9b30c...`, `dae302b62259866f...`, `837102913ff2596d...`,
`f4495f671fd72430...`, and `3744c81c88dd435f...`. Fresh V32-runtime permanent
baselines and matched controls give learned 10/10, permanent random 5/10,
permanent greedy 8/10, matched random 4/10, and matched greedy 0/10. The targeted
abandonment defect is eliminated, but corrected reusable preflight rejects V32:
permanent-greedy idle is definitively `+0.02116306` worse (95% CI
`[+0.00659211,+0.03839977]`); permanent announcements/recovery and matched
recovery are uncertain. Dev-v28 remains unopened and is retired, held-out-v4
stays sealed, and M8.5 remains unmet.

ADR-0044 precommits V33 from reusable V32 evidence only. Mean idle ticks by
seat are `[4.2, 408.8, 487.4]` for V32 versus `[274.8, 51.5, 298.8]` for permanent
greedy. Scripted seat 1 is the dominant `+357.3`-tick gap while learned seat 0
is already `-270.6` better. V33 therefore extends the exact V32 proactive-
staging rule to fixed seat 1 and preserves seat 2. All model, reward, teacher,
training, and reusable-selection fields remain exact. Dev-v28 is retired
unopened. Dev-v29 freezes globally disjoint roots `282001..282160` and remains
unopened; held-out-v4 stays sealed. Config/seed governance, 158 Python tests,
and all 44 exact-config reward adversaries pass. No V33 implementation, live
outcome, or model work preceded the precommit. M8.5 remains unmet.

V33 is rejected at its hard public pretraining boundary. Extending defense
staging to seat 1 changed seed 23456 from a V32 win to a loss at tick 7593,
producing only 4/5 even with seat 2 preserved. The uncommitted runtime
experiment was removed and the accepted V32 runtime restored; replica A never
began. Dev-v29 remains unopened and is retired, held-out-v4 stays sealed, and
M8.5 remains unmet.

ADR-0045 precommits V34 from a fresh reusable-only V32 trace. In every one of
the ten wins, scripted seat 1 loses a mask-valid simultaneous supply claim and
then a harvest claim; the latter returns structured `claim_lost` at tick 254
but does not wake stop-on-event, leaving the unassigned seat idle until the
unrelated tick-660 economy boundary. V34 preserves V32's complete task catalog,
partner policy, learned policy, reward, teacher/training construction, and
scorecards. It only exposes final atomic loss as structured decision boundary
`claim_lost`, without assigning or penalizing the loser or synthesizing a board
event. Dev-v29 is retired unopened. Dev-v30 freezes globally disjoint roots
`283001..283160` and remains unopened; held-out-v4 stays sealed. Config/seed
governance, 159 Python tests, and all 44 exact-config reward adversaries pass.
No V34 runtime implementation, live outcome, or model work preceded the
precommit. M8.5 remains unmet.

V34 is rejected at its complete public pretraining boundary. The all-seat
claim-loss wake preserved 5/5 survival but reduced required proactive-staging
starts from five to zero, so the candidate command failed and later gates/model
work did not run. Public claim losses by fixed seat were
`[[9,0,0],[14,0,0],[10,0,0],[10,0,0],[9,0,0]]`: every affected public action
belonged to learned seat 0, while the reusable defect belongs to scripted seat
1. The experiment was removed and V32 rebuilt; its gate again passes 5/5 with
five staging starts. Dev-v30 remains unopened and is retired, held-out-v4 stays
sealed, and M8.5 remains unmet.

ADR-0046 precommits V35 from the disjoint V34 public and V32 reusable traces.
Only final atomic loss from fixed scripted seat 1 wakes `claim_lost`; identical
losses from learned seat 0 and scripted seat 2 preserve V32 scheduling. The
loser still receives no assignment, synthetic board event, or invalid penalty.
V35 otherwise holds the complete V32 construction exact. Dev-v30 is retired
unopened. Dev-v31 freezes globally disjoint roots `284001..284160` and remains
unopened; held-out-v4 stays sealed. Config/seed governance, 160 Python tests,
and all 44 exact-config reward adversaries pass. No V35 runtime implementation,
live outcome, or model work preceded the precommit. M8.5 remains unmet.

V35's implementation checkpoint now passes its focused fixed-seat live probe,
pinned Java build, and complete public candidate gate. Scripted seat 1 wakes
after one tick on a real harvest `claim_lost`; learned seat 0 loses the same
task without a decision wake. Winner ownership remains authoritative and no
synthetic board event is emitted. The public gate is 5/5 with all five proactive
staging starts restored. From implementation commit `673042bfd0`, smoke,
cross-process/reset/seed determinism, the 16,200-tick golden replay, and negative
replay all pass. Replica A is authorized; dev-v31 and held-out-v4 remain
unopened. M8.5 remains unmet.

V35's exact replicas select update 8 at 9/10, return `3.85778`, core health
`721.8`, and idle `0.05600096`; all checkpoint/replay/full-run/direct-lineage
comparisons are exact. Fresh V35 baselines are random 4/10 and greedy 8/10.
Learned wins 9/10 and improves matched-greedy idle/recovery, but reusable
preflight rejects permanent-greedy idle by `+0.01815752` with 95% CI
`[+0.00077632,+0.04116776]`; several announcement/recovery/duplicate intervals
remain uncertain. A fixed-seat trace finds mean idle ticks `[390.1,8.1,380.0]`:
seat 1 is corrected, but learned seat 0 loses its biased schematic claim at
tick 0 and idles 250 ticks in every episode. Removing the prior flips the first
choice to `BUILD_LINE` but the already-trained off-contract checkpoint falls to
6/10, so it cannot be reused. V35 is rejected, dev-v31 is retired unopened,
held-out-v4 stays sealed, and M8.5 remains unmet.

ADR-0047 precommits V36 from the exact V35 collision trace. V36 changes only the
existing tick-0 `+1.0` prior from `BUILD_SCHEMATIC` to `BUILD_LINE`; the latter
is the rejected checkpoint's unadjusted first choice on all ten seeds and avoids
the universal collision while retaining a deliberate non-WAIT opening. Runtime,
reward, teachers, training budget, model, RNGs, reusable roots, and gates remain
V35-exact. Dev-v31 is retired unopened. Dev-v32 freezes globally disjoint roots
`285001..285160` and remains unopened; held-out-v4 stays sealed. Config/seed
governance, 161 Python tests, and all 44 exact-config reward adversaries pass.
No V36 model work preceded the precommit. M8.5 remains unmet.

From committed packet `f8b191c582`, V36's focused seat-1 positive/seat-0
negative wake check, pinned Java build, and complete public candidate-policy
gate pass; public survival is 5/5 with five proactive-staging starts. Smoke,
cross-process/reset/seed determinism, the 16,200-tick golden replay, and the
negative replay control also pass. Replica A is authorized. Dev-v32 and
held-out-v4 remain unopened; M8.5 remains unmet.

V36 replica A completes all 32 updates, but no checkpoint reaches the 9/10
construction floor. Rank-best update 5 is 7/10 with return `-0.17522`, core
health `488.3`, and idle `0.05917146`; replica B is prohibited. The build-line
opening removes learned-seat idle but loses seeds 2001/2003/2004 near wave 3.
Reusable-only harvest and one-tick-replan diagnostics each win 6/10, while
forced WAIT reproduces V35's exact 9/10 outcomes and rejected idle profile. A
public trace finds the same tick-0 schematic claim loss on all five accepted
public seeds, so a server-side initial wake is not isolated from V34's staging
failure. V36 is rejected, dev-v32 is retired unopened, held-out-v4 stays
sealed, and M8.5 remains unmet.

ADR-0048 precommits V37 from reusable accepted-task timelines. V37 restores the
complete V35 learned/runtime construction and changes only fixed scripted seat
2's tick-0 opening from its colliding schematic choice to valid
`HARVEST_RESOURCE`. The unchanged V35 checkpoint then wins 9/10 off-contract
with mean core health `720.0` and idle ticks `[267.0,0.7,308.2]`; a seat-2 line
opening and the learned alternatives win only 6/10. Dev-v32 is retired unopened;
dev-v33 freezes disjoint roots `286001..286160` and remains unopened;
held-out-v4 stays sealed. Config/seed governance and all 44 exact-config reward
adversaries pass, and the Python suite is 162/162. No V37 implementation or
model work preceded the precommit. M8.5 remains unmet.

V37's fixed-seat opening is now implemented fail-closed across teacher/PPO
collection, reusable evaluation, checkpoint replay, matched controls,
confirmation, and final evaluation. Full structured action evidence is archived
without changing legacy-config behavior or permanent public baselines. Missing,
duplicate, invalid, and masked matches fail before the step; 165 Python tests
pass. From implementation commit `0c4a09659f`, the pinned Java build/tests,
focused fixed-seat check, 5/5 public gate with five proactive-staging starts,
smoke, cross-process/reset/seed determinism, 664-checkpoint/16,200-tick golden
replay, negative replay, and all 44 exact-config reward adversaries pass.
Replica A is authorized; dev-v33 and held-out-v4 remain sealed, and no V37 model
work has begun.

V37 replica A selects update 16 at 9/10 reusable wins, mean return `4.18676`,
core health `805.5`, and idle `0.05108287`. Checkpoint/model/replay/full-run
digests are `a9a55110fe2266b8...`, `21b665232664f79e...`,
`9b67d5d468f86a55...`, and `614c071b7f3003b0...`; fresh checkpoint replays are
bit-exact. The precommitted construction and idle floors pass, so exact replica
B is authorized. Dev-v33 and held-out-v4 remain sealed.

V37 replica B reproduces A exactly at update 16: checkpoint bytes, model state,
replay traces, teacher evidence, canonical frontier evidence, and full-run
digest `614c071b7f3003b0...` match. Direct lineage passes from training commit
`8d323a3c72` with digest `fd69503ae40e977b...` and artifact SHA-256
`3c17cfdf02a43fcb...`. Reusable permanent-greedy and matched-greedy scorecards
must pass before dev-v33 can be opened; held-out-v4 remains sealed.

V37's reusable preflight is ineligible. Candidate wins are 9/10 versus permanent
random 4/10, permanent greedy 8/10, matched random 5/10, and matched greedy
3/10. The complete matched-greedy scorecard passes, including idle
`-0.13391229` and recovery `-88.95` ticks. Permanent-greedy parity fails because
announcement, idle, and recovery intervals remain uncertain; idle is
`+0.01323943` with 95% CI `[-0.00258843,+0.03051348]`. V37 is rejected under
the frozen rule, dev-v33 is retired without execution, and
M8.5 remains unmet. The report hashes to `faac2dc071489f25...`.

ADR-0049 records that a delegated read-only review subsequently exposed the
membership of dev-v33 and held-out-v4 despite an explicit prohibition. No
episode or outcome was observed, but both sets are retired unexecuted and may
never be used. Any successor must precommit globally disjoint dev-v34 and
held-out-v5 sets and a committed umbrella marker that precedes membership reads
and baseline episodes.

Two reusable-only, off-contract V38 diagnostics are rejected. Collision
redirect (`097d8f5c95b0bbd6a40d3f8fbca0ca6e86d527d4bbf1c8a1f3a01ebc52ff2490`)
falls from V37's 9/10 to 6/10 and raises total idle `7,840 -> 11,609`
(`+48.07%`): learned-seat idle falls by 3,053 ticks but seat 2 gains 6,988.
Its 37 rewrites include 34 for seat 2 and 13 to `WAIT`; seeds 2002, 2003, and
2006 flip from win to loss. Broader collision rerouting therefore moves the
problem between seats and is not a viable coordinate.

Partner-intent masking
(`83a4242b6b7df288ec20976029356637de61a3e2adf9736b1a3cff41e5006319`) is
bound to the exact V37 config, checkpoint, direct lineage, and public reusable
set, but falls to 7/10 with mean core health `500.0`. Total idle falls
`7,840 -> 7,182`, with per-seat ticks
`[4,658,342,2,840] -> [4,619,338,2,225]`; only 39 learned-seat ticks are saved,
and 617 of the 658 total savings come from seed 2002 seat 2. Mean authoritative
idle is `0.05223`. All 48 masks have clean traces with no invalid or unaccepted
learned action, while seeds 2005 and 2010 flip from win to loss. The diagnostic
does not carry the event evidence required for announcement or recovery parity.
This coordinate is also rejected; the subsequent V38 precommit is recorded
below. M8.5 remains unmet.

The behavior-preserving actionability trace
(`0500a74377b740556e3012635491318acbde3939c7f179bd24e79aa46ebf2099`)
matches all 1,128 V37 action/tick/state-hash boundaries exactly and reproduces
9/10 wins, mean core health `805.5`, and idle ticks `[4,658,342,2,840]`. All
4,658 learned-seat idle ticks overlap the structured fortification task; 4,611
occur while its `BUILD_SCHEMATIC` is `RUNNING` under seat 1. Of learned-seat
idle, 1,607 ticks have no valid non-WAIT action and no exposed proactive staging
candidate. Six simultaneous harvest claim losses account for 3,011 ticks, and
no learned-idle interval exposes a valid staging action.

ADR-0050 precommits V38 from that reusable evidence. V38 holds V37 exact except
that learned seat 0 may receive the existing nonexclusive proactive
`DEFEND_REGION` candidate while another seat owns a live `BUILD_SCHEMATIC` in
the quiet pre-defend-lead window. It does not force, mask, redirect, or change
any scripted-seat action; the candidate remains subject to ordinary learned
selection. V38 requires retraining and fresh baselines. Config SHA-256 is
`d92bf9aa2050a5a4d62fc29566fb2514feec84eb421f62b6cac2e24b0969f2bf`.
The umbrella reservation SHA-256 is
`a2e2389925797a5f5a8c93224561f68f36fd443afbebdc07f888aaf6bef6f27a`.
The governance/config/umbrella/test packet is committed at `de597c8462` before
any replacement membership generation or read, and the Python suite is
166/166. The primary-only freezer was committed at `a7504a4781`, then the
value-free membership freeze was committed at `9c8f7f3d32` with
`values_emitted=false`. It verified 41 pre-existing membership documents with
5,321 unique roots, then froze dev-v34 and held-out-v5 at 160 unique, globally
disjoint roots each. Their hashes are
`bef6bb17c7759530dc216961733839808dbff228bb96a09232dced89a7ca5ac7` and
`1118ef59b0953aacd86176737777013bb2c6498e128f28bcbb7850e6ad586910`;
the value-free freeze record hashes to
`7282a3cd405f2d6b00dd3942fb8da2b2f62eb3a8f567dc067edc07756787018e`.
Both sets remain unconsumed. The Python suite remains 166/166; no baseline,
episode, or model work has begun.

V38's runtime implementation is committed at `8b3f9cc749`, and the complete
pretraining boundary is green. The focused live owned-schematic probe on public
seed 12345 observes seat 1 running `BUILD_SCHEMATIC`, one valid learned-seat
`DEFEND_REGION` stage beside ordinary `BUILD_LINE`, no scripted-seat stage, and
no synthetic claim/helper/event. Focused `CandidateGenerator` tests and Gradle
`agent-core:test rl-server:test agent-plugin:classes` pass; Python is 166/166.
The public candidate-policy gate is 5/5 with 10 proactive staging starts, and
smoke is 9/9. Determinism ends at cross-process
`20a97f36407167597981e77c`, reset `a2cf4a73ee901c844f30f486`, and alternate
seed `495ba05fa71697bdc8ff2951`. Golden replay covers 664 checkpoints, 16,200
ticks, and two episodes; negative replay detects a one-line `MINE` change. All
44 exact-config reward adversaries pass for config
`d92bf9aa2050a5a4d62fc29566fb2514feec84eb421f62b6cac2e24b0969f2bf`; the
temporary, uncommitted report SHA-256 is
`e44865297a31ab1625bf4a43116cf1ff712b96657043c200c0af629ddd4f59bf`.
At that implementation checkpoint, dev-v34 and held-out-v5 remained
unconsumed, and no baseline episode or model work had begun. Replica B remained
prohibited unless replica A reached at least 9/10 wins with mean idle below
`0.25`.

V38 replica A completed from committed repository
`3effefed781b88c2e71354d784db58eb787ed7e6`, exact config
`d92bf9aa2050a5a4d62fc29566fb2514feec84eb421f62b6cac2e24b0969f2bf`, and
lock `8d865c8c710a61d7e37b8896b38166a1dcf121e40d17fbb1a47e948b4861bf6c`:
256 warmup episodes, 2,048 training episodes, and 32 updates. Selected update
20 reaches 9/10 wins, mean return `4.859680000000006`, core health `565.2`, and
idle `0.021071738935729764`. Checkpoint/model-state hashes are
`3bc4a3a1cc9c2ef4450e20c689c3909a8bf9ae8ba35b194e8710df1acf737b5e` and
`b9f592ffe58d1b866f200cd3544a2ecfd48f6d662f517aece3dffa745fa66540`.
Both replay digests are bit-exact at
`272dfb7a5793c1b79be95ce9b7e2407c3752cb6ee183cf9440dbe388ee4553af`;
action-state is `5ba7991a0dd10f0d857c5fcbf75ccbbb573eb7a7c59b975967c3432463f3c68c`,
canonical full-run is
`356a2065c8c2001ba6e9b2b480949e0c4ff3fdfd39b88ac8747c49e2838f57a2`,
frontier is `9955422e926e955700370f6dcf792c1c1054e6501e8b5b46afb151911ea78c7b`,
and manifest is
`e61516546eabb0cf35d53f699c1e24fa20f214f9a534678cf69ff5361ecd63ad`.
The precommitted gate passes exactly (`>=9/10` and idle `<0.25`), authorizing
exact replica B from the same commit/config/toolchain in an independent output.
Dev-v34 and held-out-v5 remain unconsumed; no scorecard, confirmation, or final
episode has run. M8.5 remains unmet.

V38 replica B completed independently from that exact commit, config, and lock
and reproduced update 20 exactly at 9/10 wins, return `4.859680000000006`, core
health `565.2`, and idle `0.021071738935729764`. All 32 checkpoint files are
byte-identical; selected checkpoint/model, replay, action-state, and canonical
full-run remain respectively `3bc4a3a1cc9c2ef...`, `b9f592ffe58d1b86...`,
`272dfb7a5793c1b79...`, `5ba7991a0dd10f0d...`, and `356a2065c8c2001b...`.
Warmup raw hash matches exactly at `d1dab1c2d438ba95...`. Expected output-path
differences change rehearsal/frontier/manifest raw hashes, while governed
canonical validation passes. Direct lineage passes schema
`selector_checkpoint_direct_lineage_v1`, selected update 20, and exact
training/repository commit, checkpoint, model, and config, with digest
`ada0bcca1d60b25b...` and artifact SHA-256 `9a608dc354ff06ba3...`.
Exact replicas are therefore complete. Next refresh permanent random/greedy and
matched baselines under the V38 runtime, then run reusable scorecard preflight.
Dev-v34 and held-out-v5 remain unconsumed; confirmation/final remain prohibited
and M8.5 remains unmet.

ADR-0051 accepts the selected-only evaluation contract implemented at guard
commit `9bc96f91c7219ad9e9656f99b29f15331b78b399`: explicit-only
`--seed-set-file`, required declared split and pre-read held-out gate, no
implicit Gradle, runtime config/repository/JAR provenance, and stale-provenance
promotion rejection. Legacy registry loading remains an explicit diagnostic
compatibility path, not a promotion fallback. Python passes 176/176 and the
exact-config reward report remains 44/44 at `e44865297a31ab...`.

Fresh permanent baselines bind config `d92bf9aa2050a5a4...`, repository
`9bc96f91c7219ad9e9656f99b29f15331b78b399`, and JAR `5d4fc89f...`;
records/aggregate hashes are `aaf28dd1...`/`4bbc3aa3...`. Permanent random is
4/10, idle `0.0153280914`, core `217.7`; permanent greedy is 8/10, idle
`0.0157205468`, core `707.2`. V38 update 20 reproduces on reusable dev-v1 at
9/10, return `4.85968`, core `565.2`, idle `0.0210717389`; matched random is
5/10 with idle `0.1635828272`, and matched greedy is 6/10 with idle
`0.0888449994`. All four observed win comparisons pass.

V38 nevertheless fails its frozen dual scorecards. Versus permanent greedy,
announcements (`-0.00307796475`, CI `[-0.0150290537,0.0074881288]`),
duplicates (`-0.6`, CI `[-1.9,0.6]`), and idle (`+0.00535119211`, CI
`[-0.0112619599,0.0266615919]`) are uncertain; recovery and abandonment pass.
Versus matched greedy, announcements and idle pass, while duplicates (`-1.0`,
CI `[-3.4,0.8]`) and recovery (`-20.85`, CI
`[-100.3025,61.4025]`) are uncertain; abandonment passes. Preflight is false
with records/aggregate/report hashes `99575abd...`/`aa3fa1fe...`/`e6c9cf27...`.
Under ADR-0050, uncertainty is failure: V38 is rejected before confirmation.
Dev-v34 is retired unopened and unconsumed without a membership read;
held-out-v5 remains sealed and unconsumed. Diagnose one successor coordinate
from reusable evidence only, precommit it, and freeze a new dev confirmation
identity before model work. M8.5 remains unmet.

Four byte-exact-twin, parity-controlled V39 diagnostics have now exhausted the
immediate reusable-only candidates without authorizing a successor. The WAIT
communication probe (`014085de7007e4d6227e6c5ae89ee1cd636b60f036c6b1db23a8acdd41908ad6`)
counts structured/suppressed WAIT communication at candidate `17641/74`,
matched `16161/69`, and permanent `17252/74`; candidate-minus-permanent remains
uncertain both before filtering (`-0.00307796`, CI
`[-0.01502905,0.00748813]`) and after filtering (`+0.00176772`, CI
`[-0.00574127,0.00877167]`), while matched remains a pass. The claim-loss probe
(`e3c726380516e9762566ab5b98dc3312758f52d2c943b979e49263cefbb9f794`)
has 10/10 canonical parity and finds 19 learned-seat-0 losses (18 supply, one
harvest), zero with a staged/live partner schematic, 19/19 with an ordinary
non-WAIT option, and zero extra boundary reconvergences. Moving seed 2005's
tick-2053 harvest gap from 695 to expose `BUILD_LINE` at 694 changes the
trajectory and risks V34's staging-disappearance defect. The recovery catalog
(`727e62145895a5a9435a6c62372156a7887c5dd12d2d5d204d8d7b89bc5d298e`)
finds zero same-type valid choices at 30 exact death boundaries; next-tick
`HARVEST` on seeds 2004/2006 requires bias-to-tie above `3.822402`/`3.973103`
against defense. The supply-collision probe
(`9b9905b208dceb95b9ddbf240a4050d63a85779b321eec7b6fc35bdfb1e26870`)
finds 18 collisions in seven bursts, 11/18 alternate supply choices, and 18
mask-induced changes (11 supply, six schematic, one harvest), with only 6/18
alternate-supply priors within `+1`; these are the same 18/37 rejected redirect
rewrites and 18/48 rejected masks, affecting duplicates but not recovery/idle.
All four coordinates are rejected.

ADR-0052 now precommits one materially new V39 coordinate. Fixed scripted-seat
actions are computed before learned selection; an exact fixed-partner
`task_id` match raises only the matching learned candidate's existing
`duplication_risk` input to `1.0`. The action remains unmasked and learned-seat
selection remains authoritative, unlike the rejected 48-choice mask and
37-choice redirect. Runtime, action vocabulary, feature dimensions, model,
reward, optimizer, roots, teacher, budget, RNGs, and checkpoint ranking remain
V38-exact. ADR-0053 supersedes only the final-set metadata after a legacy
full-suite test read retired held-out-v5. The behavior-identical live config
hashes to
`54d76bb209ec31f24bc2711b208cb2995e6d538534ba0b99a150091596ccf924`.

Implementation and pretraining gates are authorized; replica A is not. The
committed value-free umbrella reserved dev-v35; it is now frozen unconsumed
with zero membership reads. Held-out-v5 is retired without outcomes and a new
committed umbrella reserves held-out-v6 in a disjoint no-read namespace.
Focused feature/parity checks, public 5/5 survival/staging, suites, smoke,
determinism, replay controls, and the initial exact-config reward gate pass.
The revised-hash 44/44 reward gate passes. Held-out-v6 is frozen value-free with
zero membership reads and remains unconsumed; its receipt/membership hashes are
`4f31a7078e5cd456...` / `2bf4aa04ef54d873...`. Replica A was authorized only
after those gates passed; M8.5 remained unmet.

V39 replica A completed 256 warmup episodes, 2,048 PPO episodes, and all 32
updates from committed repository `e31e4daf71`. No checkpoint met the frozen
9/10 construction floor. Rank-best update 25 reached 8/10 with return
`3.3231000000000073`, core `448.0`, and idle `0.01845563475648595`;
checkpoint/frontier hashes are `1af02875472f54a6...` / `181ed3e7069b429b...`.
Replica B is prohibited and V39 is rejected before reusable scorecards.
Dev-v35 is retired unopened/unconsumed; held-out-v6 remains sealed/unconsumed.
M8.5 remains unmet.

ADR-0054 precommits V40 after reusable/train-only diagnosis rejects a risk
magnitude change: all ten openings cross within `0.100813646..0.110020827`.
The exact V39 teacher corpus instead contains 752 partner-intent conflicts
among 3,956 eligible transitions, including 177 warmup and 734 rehearsal
presentations. V40 filters only those exact action-index conflicts from warmup,
rehearsal, and PPO teacher imitation; runtime, PPO policy/value learning,
reward, model, roots, budgets, and RNGs remain V39-exact. The immutable config
hash is `230759e7e02dcca9...`. A value-free umbrella reserves dev-v36 in the
disjoint `[4B,5B)` namespace before membership creation. Implementation and all
pretraining gates were authorized. The exact filter is now implemented at
`c9459c58f4`; 208 Python tests and the bound 256-episode train-only diagnostic
pass. Its report hashes to `4fe2960225d659cb...` and records the corrected 189
successful-corpus conflicts. Pinned Java, public 5/5 survival with 10 staging
starts, focused wake/staging, smoke, determinism, golden/negative replay, and
44/44 exact-config reward gates now pass; the reward report hashes to
`9677e5caed4d891...`. The complete boundary authorizes primary-only dev-v36
construction after this evidence is committed. Replica A remains prohibited
until that value-free freeze is committed; held-out-v6 access stays prohibited.
The primary-only freezer and its no-membership tests are now implemented, with
211 Python tests green. It was committed at `54db674e2e` before construction.
Dev-v36 is now frozen value-free and unconsumed; membership/receipt hashes are
`d4bfbcf88d99f4f...` / `fce63a49f80d165...`. Replica A is authorized; replica
B, dev-v36 consumption, and held-out-v6 access remain prohibited. The
receipt-aware suite passes 212 tests without opening membership.

V40 replica A then completed the exact committed construction and passed the
frozen floor. Update 28 is selected at 10/10 reusable wins, mean return
`7.77414`, mean core health `656.3`, and mean idle `0.008388499062201467`;
checkpoint SHA is `9ff618797d8ae593...`. Two fresh checkpoint replays are
bit-exact at `5af990a3ec8ff7fb...`, with action-state/full-run digests
`4f0726c7dc8f127...` / `b6dd3c958762c082...`. Replica B is authorized from
the same committed repository/config/toolchain. Dev-v36 and held-out-v6 remain
unopened and unconsumed; scorecards, confirmation, and final remain prohibited.

V40 replica B completed independently and exactly reproduces Replica A:
selected update 28, 10/10 wins, every scorecard mean, all 32 checkpoint files,
warmup, checkpoint/model, replay, action-state, and full-run evidence match.
The canonical manifest comparator passes. Direct lineage validates at digest
`cfb0ec1b21fd49fb...`, artifact SHA `5fdc3bdabf24ee5e...`. Exact replicas are
complete, authorizing fresh selected-only permanent baselines and both reusable
scorecards. Dev-v36 and held-out-v6 remain unopened/unconsumed; confirmation
and final access remain prohibited.

Fresh selected-only V40 permanent baselines are random 4/10 and greedy 8/10.
The reusable preflight records candidate 10/10, matched random 5/10, and matched
greedy 6/10, passing every observed win comparison. It nevertheless fails both
frozen scorecards: permanent-greedy announcements and idle are uncertain, and
matched-greedy recovery is uncertain. Records/aggregate/report hashes are
`3fe4454202460b4...` / `eafe2ce3faf8baba...` / `8453b0c4b75cd681...`.
V40 is rejected before confirmation. Dev-v36 is retired unopened/unconsumed;
held-out-v6 remains sealed/unconsumed and M8.5 remains unmet.

ADR-0055 precommits V41 after a canonical reusable-only frontier diagnostic
rejects direct selection of V40 updates 25, 26, or 28: all are 10/10, and all
fail the same permanent announcement/idle and matched recovery rows. Updates 25
and 26 have complementary idle outliers. V41 tests one unswept 50/50 aligned
model-state midpoint, using exact A/B parent pairs and changing no runtime,
reward, feature, root, or action-authority field. Config/umbrella hashes are
`c4705974f18512a...` / `7ce8f5cf640978ef...`. The exact-config reward gate is
44/44. Dev-v37 is frozen value-free and unopened in `[5B,6B)` with membership /
receipt hashes `7874f5abaf230665...` / `277264b80c6456f7...`. Independent
construction under pinned WSL Torch 2.12.1 is exact at checkpoint/model/lineage
hashes `b6b5e98ddee56740...` / `93594bd64193740a...` /
`37c4b1e571fca96c...`. Fresh permanent random/greedy are 4/10 and 8/10; V41 is
10/10 versus matched random/greedy 5/10 and 6/10, passing every observed win
comparison. It nevertheless fails both frozen scorecards: permanent-greedy
idle is uncertain at 95% CI `[-0.02001559,+0.01067689]`, and matched-greedy
recovery is uncertain at `[-81.80125,+29.65]`. Report SHA is
`ca7b39c84a9f51d1...`. V41 is rejected before confirmation; dev-v37 is retired
unopened/unconsumed, held-out-v6 remains sealed/unconsumed, and M8.5 remains
unmet.

ADR-0056 precommits V42 after public-only diagnosis closes WAIT-logit,
danger-label, exact-death recovery, broader staging, reward-pressure,
teacher-strength, and interpolation-sweep successors. The exact 256-episode
ordinary teacher schedule reproduces V40's 752 partner-intent conflicts. A
behavior-neutral, optimizer-free diagnostic finds a deterministic valid
non-WAIT alternate for 682 conflicts, including all 256 tick-zero conflicts and
174/189 successful-corpus conflicts; 70 retain V40 filtering. V42 changes only
the effective generic teacher-imitation label, preserving the adaptive
teacher's current preference/return state and selecting the highest-utility
nonrisk candidate with stable index tie breaking. Original scripted trajectory
actions, runtime masks and authority, reward, features, model, roots, budgets,
RNGs, and engine pins remain V40-exact. Config/umbrella hashes are
`3fcb0c8800c638a3...` / `c1644d2dd6dde231...`. Dev-v38 is primary-only in
`[6B,7B)` and remained unconstructed until the committed implementation and
complete public/pretraining gates passed. Held-out-v6 remains sealed/unconsumed.
No V42 model work or restricted membership access preceded the precommit. The
production/test packet now implements separate original and
effective teacher labels, pure adaptive-preference relabeling, V40 fallback,
all-three-path CE handling, and deterministic telemetry. The complete public/
runtime/Java/replay/reward boundary passed on 2026-07-23. The production
diagnostic reproduces 752 conflicts, 682 relabels, and 70 fallbacks over 34,898
transitions; report/payload/action-state hashes are `83f8dd6904e5356d...` /
`e92436ffb3773b80...` / `0e609742ba171c60...`. The boundary passes 243 Python
tests and Java; public policy is 5/5 with 10 proactive staging starts; both
focused coordination checks and smoke pass; deterministic replay yields 664
checkpoints / 16,200 ticks / two wins and the negative mutation is detected;
all 44 exact-config reward adversaries pass with report SHA
`272ac291ef143fa6...`. The freezer was committed at `3e328ce91e`; dev-v38 and
its value-free receipt were then committed at `949b73f987`. Membership/receipt
hashes are `3f4b0d012cf87303...` / `fea431ae993d1072...`; the receipt records
zero membership reads and no values emitted. The full suite passes 248 tests.
Independent pinned-toolchain replicas from training commit `12980ee2b9` both
select update 2 at 9/10 reusable wins, mean return `4.73976`, core health
`568.8`, and idle `0.03455784384563236`. All 32 checkpoint files match and the
canonical comparator passes. Checkpoint/model/replay/action-state/full-run
hashes are `65f8e3dc3a41bf89...` / `4363617f8535bc8b...` /
`d01d0dfe425d1b0d...` / `52751513f785c196...` /
`cb719361da11ab6c...`; direct lineage digest/artifact hashes are
`b1dbf1abc6a7dacd...` / `100945a4820b2039...`. Fresh permanent random/greedy
are 4/10 and 8/10; candidate is 9/10 and matched random/greedy are 5/10 and
6/10, so every observed win comparison passes. Both frozen scorecards fail:
permanent-greedy announcements (mean `-0.00417813`, 95% CI
`[-0.02124498,+0.00920379]`) and idle (mean `+0.01883730`, 95% CI
`[-0.00111686,+0.04325210]`) are uncertain, and matched-greedy recovery is
uncertain (mean `-38.3`, 95% CI `[-117.30125,+32.30125]`). Records/aggregate/
report hashes are `e0a78468268bc021...` / `dae12fbf3868c6cc...` /
`01bf941060bc7e6f...`. V42 is rejected before confirmation. A no-authority
public diagnostic retargets the existing tick-zero prior from conflicting
schematic to nonconflicting build line. It keeps 9/10, reduces mean idle to
`0.00083124`, and passes idle, but permanent announcements remain uncertain
(mean `-0.00230904`, 95% CI `[-0.00738835,+0.00265009]`) and matched recovery
remains uncertain (mean `-4.8`, CI `[-76.20125,+64.2]`). Records/report hashes
are `6ccd6ac543d43891...` / `41e3b71b133f4c63...`. The diagnostic has no
promotion authority and closes the runtime-prior reopening. No V43 is
authorized. Dev-v38 is retired unopened/unconsumed, held-out-v6 remains
sealed/unconsumed, and M8.5 remains unmet.

ADR-0062 now precommits V45 from V44's full-frontier collapse. V45 preserves
V43's current-state set actor and adds V44's lag through separate encoders and
zero-initialized residual actor heads; it does not repeat the 160->64
bottleneck. Everything else remains exact. Config/umbrella hashes are
`a7d0c8029acebe79...` / `e4fe0b56a95fa64c...`. Dev-v41 is reserved in
`[9B,10B)` but unconstructed; dev-v40 remains retired without a read and
held-out-v6 remains sealed. Implementation and the complete pretraining boundary
must be committed before value-free dev-v41 construction. M8.5 remains unmet.

The V45 implementation/pretraining boundary is green: exact V43 base-path
equality, zero residual initialization, learnable lag sensitivity, masks,
schema failure, and compatibility are covered. The embargo-safe 273-test suite,
pinned Java, public 5/5 gate with ten staging starts, both focused checks,
smoke, golden/negative determinism, and 44 reward adversaries (SHA
`84cd359cf9cbd401...`) pass. The 43 scenario-variation tests remain last green
before dev-v40 freeze and are not rerun because they glob-read retired
membership. Dev-v41 remains unconstructed; commit this boundary before the
primary-only freezer.

The primary-only dev-v41 freezer is now implemented on the commit-bound V44
atomic/no-read primitives with exact V45 reservation, namespace, and sealed-set
validation. Its receipt binds both the wrapper and helper commits and contains
no seed values. The embargo-safe suite passes 277 tests. The freezer has not
executed; dev-v41 remains unconstructed until the tool is committed.

The committed freezer then constructed dev-v41 without emitting or reading
membership. Membership/receipt hashes are `591513526bdd0bce...` /
`d2d14a281d37a046...`; the receipt records zero membership-document reads.
Dev-v41 is frozen and unconsumed pending both reusable scorecards.

Two exact V45 replicas select update 32 at 10/10 reusable wins, return
`7.67784`, core `730.1`, and idle `0.00873637`; checkpoint/full-run/lineage
prefixes are `cdc526403cd1fe27...` / `f253cd6dbb1c0f5c...` /
`5c1ca3fc7ab9c49f...`. Fresh permanent random/greedy are 4/10 and 8/10;
matched random/greedy are 5/10 and 6/10. All win comparisons pass. Both frozen
scorecards fail on uncertainty: permanent announcements and idle, and matched
recovery. Report SHA is `ea7466a45d91d415...`.

The remaining reusable idle outlier on root 2004 contains 65 forced WAITs after
the only legal defense action, which agrees with the scripted teacher. The
selector cannot act at those boundaries, so this evidence does not authorize a
new memory coordinate or an outcome-driven relaxation. V45 is rejected before
confirmation; dev-v41 is retired unopened/unconsumed, held-out-v6 remains
sealed/unconsumed, and M8.5 remains unmet.

The scenario-variation governance module no longer glob-reads embargoed seed
memberships. It limits membership reads to explicit legacy/public contracts and
uses value-free receipts/existence for later governed sets. Its 44 tests and
the complete 322-test Python suite pass without reading dev-v34..v41 or held-
out-v5/v6 membership.

ADR-0063 now precommits V46 under the project owner's explicit learned-control
scope expansion. A new policy index may defer one otherwise-unforced boundary
to the already-computed canonical adaptive-v1 seat-0 action; it is unavailable
for expert WAIT and cannot override any deterministic safety/lifecycle force.
The existing ten V45 logits and critic remain the exact base. A same-boundary
expert-action one-hot and zero-initialized DEFER head are appended, teacher
losses remain ordinary-action only, and PPO learns the control choice. Mean
DEFER above 25% makes a checkpoint ineligible.

Config/umbrella hashes are `b588ee43e66bd9d...` /
`a78631d7ba9f1cd2...`. Dev-v42 is reserved primary-only in `[10B,11B)` but
unconstructed. The committed implementation and complete public/pretraining
boundary are required before value-free membership construction or model work.
Dev-v41 remains retired unopened and held-out-v6 remains sealed.

The V46 policy-side control adapter, feature v3, model v5, ordinary-only teacher
losses, effective-action history, validated telemetry, and 25% gates are now
implemented. Focused tests prove V45 bit-exact ordinary logits/masks/value at
initialization, zero-output DEFER construction, learned expert sensitivity,
forced/WAIT/single-action exclusion, deterministic translation/fallback,
reset-local history, exact schema validation, and cap enforcement. The full
335-test embargo-safe Python suite, pinned Java/custom modules, public 5/5 gate
with ten staging starts, both focused checks, smoke, accepted deterministic
golden/negative replay, and 44/44 exact-config reward adversaries pass. The
adversary report SHA is `ec3acb4c1056207...`. Dev-v42 remains unconstructed and
no V46 training or restricted membership read has occurred.

The primary-only dev-v42 freezer is implemented on committed atomic/no-read
primitives and binds the exact V46 implementation, config, umbrella, namespace,
and sealed-final contract. Its receipt contains no seed values. The embargo-safe
suite passes 339 tests. It has not run; commit this tool before construction.

The committed freezer then constructed dev-v42 value-free. The receipt binds
membership `8f518384f19c193f...`, generator `e9a828a7d01ed7e9...`,
implementation `173cd5c2a11f3237...`, and zero membership reads. Dev-v42 is
frozen and unconsumed pending exact replicas plus reusable scorecard/control
gates; the receipt-aware suite passes 340 tests.

Two exact V46 replicas select update 32 at 10/10 public-dev wins, return
`7.22016`, core `639.2`, idle `0.01033305`, and DEFER `0.18420177`; checkpoint
and full-run prefixes are `93694e4d70ec56e4...` and
`8d61abfa4ce4fe10...`. Direct lineage now validates V46's explicit control
schema after correctly failing closed on its omission. The 341-test suite
passes. Reusable gates are next; dev-v42 remains unconsumed.

Canonical lineage `b6322349e4d14b31...` and fresh reusable evaluation reject
V46 before confirmation. Candidate/permanent random/permanent greedy/matched
random/matched greedy wins are 10/4/8/5/6, and mean DEFER `0.18420177` passes
its cap. Permanent announcements and idle plus matched recovery remain
favorable but uncertain; report SHA is `2af00337138b9939...`. Dev-v42 is retired
unopened/unconsumed, held-out-v6 remains sealed, and M8.5 remains unmet.

ADR-0060 now precommits V43 from public/train/reusable architecture evidence.
The v1 actor scores each SELECT candidate independently and its CONTINUE/WAIT
head cannot see the candidate catalog. V43 changes only the model architecture:
masked other-candidate context feeds each SELECT logit and masked all-candidate
context feeds CONTINUE/WAIT. Features, runtime authority, reward, teacher
trajectory/relabeling, roots, budgets, optimizer, RNG values, scripted seats,
and engine pins remain V42-exact. Config/umbrella hashes are
`29b4430839451f13...` / `99851aa2cdbfb469...`. Dev-v39 is reserved primary-only
in `[7B,8B)` and remains unconstructed; dev-v38 remains retired without a
membership read and held-out-v6 remains sealed/unconsumed. The committed
implementation and full public/pretraining boundary are required before
value-free dev-v39 construction or model work. M8.5 remains unmet.

The V43 implementation and complete pretraining boundary are now green. Model
selection is config-driven; v1 compatibility and v1/v2 checkpoint separation
are enforced through training, replay, lineage, preflight, and final evaluation.
The boundary passes 293 Python tests, pinned Java, public policy 5/5 with 10
staging starts, both focused coordination checks, smoke, deterministic golden
and negative replay, and all 44 exact-config reward adversaries (report SHA
`3e3210447ff4f428...`). Dev-v39 remains unconstructed and no V43 training
episode has run. Commit this boundary before implementing and committing the
primary-only value-free freezer.

The primary-only dev-v39 freezer and its no-read namespace tests are now
implemented; all 298 Python tests pass. The tool validates the exact committed
config/umbrella and creates membership plus a value-free receipt atomically.
It has not executed. Commit the freezer before construction; dev-v39 remains
unconstructed and replica A remains prohibited.

The committed freezer at `6b7a6c5dca` has now created dev-v40 value-free in
`[8B,9B)`. Membership SHA is `05ca1f48227581fc...`; receipt SHA is
`acffc919ab1c40e2...` and attests no emitted values, zero membership-document
reads, and no generated, retired-confirmation, or sealed-final read. Dev-v40
remains unconsumed. Commit the membership and receipt packet before replica A.

The membership/receipt packet was committed at `b510cc48a1` before replica A.
V44's two pinned replicas reproduce exactly and select update 1 at 9/10 reusable
wins, mean idle `0.07252724`, checkpoint `4e51d31bd4f33a67...`, and full-run
digest `029e77830406127a...`; direct lineage is `aa799280368304ae...`. Fresh
permanent random/greedy remain 4/10 and 8/10; matched random/greedy are 5/10 and
6/10, so every observed win comparison passes. The scorecards nevertheless
reject V44: permanent idle decisively regresses, permanent announcements/
duplicates are uncertain, and matched duplicates/idle/recovery are uncertain.
Records/aggregate/report hashes are `3ec9dfa9504f93e2...` /
`b364484245ec0213...` / `260625f302f3e268...`. Update 1 is the only 9-win
frontier checkpoint; later updates collapse to 4-8 wins. V44 is rejected before
confirmation; dev-v40 is retired unopened/unconsumed, held-out-v6 remains
sealed/unconsumed, and M8.5 remains unmet.

The committed freezer at `5007a7b9f3` has now created dev-v39 value-free.
Membership SHA is `0b88fda1b37647aa...`; the receipt attests no emitted values,
zero membership-document reads, and no generated, retired-confirmation, or
sealed-final read. Dev-v39 remains unconsumed. Commit the membership and receipt
packet before replica A. That packet was committed at `df7723c6cb` before the
replicas recorded below.

V43's two pinned replicas reproduce exactly and select update 27 at 10/10
reusable wins, mean idle `0.00874233`, checkpoint `b4cc691ad0c08d67...`, and
full-run digest `66385a8f85ec7db7...`; direct lineage is
`1f07166a5d27aa30...`. Fresh permanent random/greedy are 4/10 and 8/10; matched
random/greedy are 5/10 and 6/10, so every win comparison passes. Permanent
recovery now passes decisively, and matched announcement/duplicate/idle metrics
pass. V43 nevertheless fails the frozen dual scorecards because permanent
announcements and idle remain favorable but uncertain and matched recovery is
uncertain. Records/aggregate/report hashes are `a3bf222c25ec52ea...` /
`12c0272429e14f42...` / `10f829a54a110507...`. V43 is rejected before
confirmation; dev-v39 is retired unopened/unconsumed, held-out-v6 remains
sealed/unconsumed, and M8.5 remains unmet.

ADR-0061 now precommits V44 from the reusable temporal failure pattern. V43 is
memoryless even though the three remaining failed rows measure decision churn,
continued idling, and recovery after agent loss. V44 changes only the bounded
feature/model architecture: it appends the prior authoritative boundary's base
scalars, masked candidate mean/count, and submitted action one-hot, then feeds
the resulting 160 scalars through the V43 set-context actor. Runtime authority,
reward, teacher trajectory/relabeling, roots, budgets, optimizer, RNG values,
scripted seats, and engine pins stay exact. Config/umbrella hashes are
`9a23c90567754eb8...` / `4a526274d9568726...`. Dev-v40 is reserved primary-only
in `[8B,9B)` and remains unconstructed; dev-v39 remains retired without a
membership read and held-out-v6 remains sealed/unconsumed. The committed
implementation and full public/pretraining boundary are required before
value-free dev-v40 construction or model work. M8.5 remains unmet.

The V44 implementation and full pretraining boundary are green. Feature/model
selection is config-driven; prior-boundary snapshots are immutable and reset-
local; checkpoint, manifest, lineage, preflight, and final gates bind both
schemas while v1/v2 remain compatible. The boundary passes 305 Python tests,
pinned Java, public policy 5/5 with ten staging starts, both focused checks,
smoke, deterministic golden and negative replay, and all 44 exact-config reward
adversaries (report SHA `740aba578809911...`). Dev-v40 remains unconstructed and
no V44 training episode has run. Commit this boundary before implementing and
committing the primary-only value-free freezer.

The primary-only dev-v40 freezer and its no-read namespace tests are now
implemented; all 310 Python tests pass. The tool validates the exact committed
config/umbrella and atomically creates membership plus a value-free receipt. It
has not executed. Commit the freezer before construction; dev-v40 remains
unconstructed and replica A remains prohibited.

ADR-0064 records the owner-authorized reusable-scorecard power correction after
V46. A no-DEFER ablation remained 10/10 and failed essentially the same three
confidence rows, so another small control coordinate is not justified. The
paired-bootstrap zero-crossing rule remains exact; its canonical reusable
sample increases from ten roots to 160 precommitted public roots in `[11B,12B)`.
The frozen V46 checkpoint receives one screen with fresh permanent and matched
baselines and cannot be retrained or reselected. Dev-v43 is reserved
value-free in `[12B,13B)` but cannot be constructed unless every reusable-v2
gate passes. Dev-v42 remains retired unopened/unconsumed, held-out-v6 remains
sealed, and M8.5 remains unmet.

The precommit was committed at `26d25acd64`; its pinned generator then froze
160 public reusable-v2 roots (membership `c529951782ec0426...`) with zero
restricted membership reads and zero episodes. Commit this data/evidence packet
before refreshing baselines or evaluating V46. M8.5 remains unmet.

Reusable-v2 gives a decisive V46 rejection without restricted access. V46 wins
96/160 versus permanent greedy's 84/160, passes the `0.25` DEFER cap and every
matched scorecard, but permanent announcements remain uncertain and permanent
idle is unfavorable by `+0.00391218` (CI
`[-0.00166438,+0.00971554]`). Preflight SHA is `d272edd51197166b...`.
Dev-v43 remains unconstructed, held-out-v6 remains sealed, and M8.5 remains
unmet.

ADR-0065 precommits V47 from the public early-death mechanism. On 63 roots with
seat-0 death before tick 3000, permanent idle/announcement gaps average
`+0.02701331` / `+0.00769989`; on 94 later-death roots both are favorable, and
all 30 greedy-only wins contain a seat-0 death. V47 retains exactly one learned
brain but transfers it, only after active-unit death, to the lowest-ID living
seat and resets its history. Feature/model/reward/control schemas and all
training values remain V46-exact. Config/umbrella hashes are
`ff112f910c13603c...` / `8e6fccc9d07de4ef...`. Dev-v43 is cancelled
unconstructed; dev-v44 is reserved in `[13B,14B)` but unconstructed. The
committed implementation and complete public/pretraining boundary are required
before membership construction or training. M8.5 remains unmet.

The V47 implementation and complete public/pretraining boundary are green.
The one learned brain is sticky while alive, transfers only after observed
death, resets history, and uses the active seat's existing structured action
path; matched controls and every lineage/promotion gate bind the same schema.
A repeatable public JVM check transfers `0->1->2` at ticks 2738/4462, records
one maximum simultaneous learned seat, and wins at tick 9000. The complete 348
Python tests, pinned Java/custom modules, public 5/5 gate with ten staging
starts, both focused coordination checks, smoke, deterministic golden/negative
replay, and 44/44 exact-config reward adversaries pass (report
`5e6aec4530d27823...`). Dev-v44 remains unconstructed and no V47 training
episode has run. Commit this boundary before implementing its value-free
freezer. M8.5 remains unmet.

The primary-only dev-v44 freezer is implemented on the committed atomic/no-read
primitives and the complete embargo-safe suite passes 352 tests. It binds the
exact V47 implementation/config/umbrella, reusable-v2 hash, cancelled dev-v43
namespace, retired dev-v42 state, and sealed held-out-v6 contract, and can emit
only a value-free receipt. It has not executed; commit the tool before
membership construction. M8.5 remains unmet.

The committed freezer `56dab3eb9e` constructed dev-v44 value-free. The receipt
binds membership `82ea1b7d59f23a0d...` and implementation
`64463e76e5606fb...`, emits no values, and records zero generated, cancelled,
retired, or sealed membership reads. Dev-v44 is frozen and unconsumed. Commit
the membership/receipt packet before replica A. M8.5 remains unmet.

Two exact V47 replicas select update 25 at 10/10 public-dev wins, idle
`0.01586387`, DEFER `0.13594699`, checkpoint `ea821b97dd1e6f4c...`, and
full-run `6f107b1e2f6e432c...`. Reusable-v2 wins are candidate 125/160,
permanent random 62/160, permanent greedy 84/160, matched random 48/160, and
matched greedy 22/160. All win/control gates pass, but permanent idle remains
uncertain (`-0.00006783`, CI `[-0.00408121,+0.00412951]`) and one automatic
`plan_removed` event makes abandonment uncertain against both greedy
comparators. Preflight is `8eb91b92dc36a22...`. V47 is rejected; dev-v44 is
retired unopened/unconsumed and held-out-v6 remains sealed.

Public diagnostics reject highest-living failover and frontier update 27.
Update 32 improves to 128/160 wins, zero abandonment, and favorable mean idle,
but its CI still crosses zero. The residual variance concentrates after
failover, especially when authority ends on seat 1; V47 resets and discards the
surviving scripted seat's prior temporal context. A successor requires a new
precommit before implementation or training. M8.5 remains unmet.

ADR-0066 now precommits V48 from that public mechanism. V47's exactly one
learned brain and sticky lowest-living death failover remain, but all seats
maintain reset-local structured history from their own authoritative prior
boundary and submitted action. On transfer the brain adopts the target living
seat's cache instead of all zeros. Feature/model/reward/control schemas,
training roots, 2,048-episode budget, optimizer, RNGs, and every gate remain
exact. Config/umbrella hashes are `714bd13db0ffee6f...` /
`656602be6dd5c3cf...`. Dev-v45 is reserved in `[14B,15B)` but unconstructed;
dev-v44 remains retired unopened and held-out-v6 remains sealed.

V48 is now implemented through the candidate and matched-control paths.
Each living seat records its already-drained structured boundary and submitted
canonical/effective action; dead caches retain their last boundary, and death
transfer adopts the target cache. Manifests, lineage, traces, reusable/final
gates, and telemetry bind the cache schema and one-model/one-action authority.
The live public `0->1->2` gate wins twice in one JVM at tick 9000 with exact
transfers at 2738/4462. All 361 Python tests, custom Java modules, public 5/5
survival, focused checks, smoke, deterministic golden/negative replay, and
44/44 exact-config reward adversaries pass (`8cfe56b3a000d4c...`). Dev-v45 is
still unconstructed and no V48 training has run. M8.5 remains unmet.

A separate primary-only V48 freezer now binds implementation
`07c6951a7ffe8da...`, the exact config/umbrella/public evidence,
`[14B,15B)`, retired dev-v44, and sealed held-out-v6 without membership reads.
Its four pure tests pass. The committed freezer has now atomically constructed
dev-v45 without reading or rendering membership. Receipt SHA is
`ee51d681fa5127be...`; it records membership SHA `79dd2a1d0958bcf...`,
`values_emitted=false`, and zero membership reads. The committed-receipt test
brings the suite to 362. Dev-v45 remains unconsumed; this does not authorize
confirmation or held-out access.

V48's two replicas reproduce exactly and select update 23 with 10/10
public-dev wins. Reusable-v2 rejects it before confirmation despite 127/160
wins versus permanent random/greedy 62/84 and matched random/greedy 48/22.
Abandonment, matched-greedy scorecard, and one-brain/history authority pass,
but mean DEFER is `0.273531 > 0.25` and permanent-greedy idle regresses
`+0.011532`, CI `[+0.005381,+0.017928]`. The no-transfer subset is worse
(`0.367418` DEFER; `+0.019146` idle), so this is a global learned-policy shift,
not merely transfer-time cache inference. Public result SHA is
`ae0818783ef7ed41...`. Dev-v45 remains unread/unconsumed and held-out-v6
remains sealed. M8.5 remains unmet.

ADR-0067 retires held-out-v6 as membership-exposed/unexecuted. A broad
namespace-metadata search opened its manifest before authorization and
displayed only the set id, with no seed value or outcome, but project policy
treats any manifest read as access. The replacement held-out-v7 freezer was
committed at `71d7fcf168` and created 160 roots value-free in `[17B,18B)`.
Receipt/membership hashes are `8b78b27153d597fb...` /
`f6d84b50d10ec6fc...`; held-out-v7 remains sealed and unconsumed.

ADR-0068 precommits the owner-authorized V49 governance direction on fresh
data. The selected V47 checkpoint is fixed unchanged; operational
non-inferiority requires each paired mean and CI upper bound to stay within
scenario-unit margins while strict held-out win CI separation remains exact.
Protocol SHA is `6711d6e43fab8f65...`. The implementation preserves zero-margin
historical behavior, passes the full Python suite, and binds protocol identity
through reusable, confirmation, and final gates.

Fresh reusable-v3 rejects V49 before confirmation. Candidate/permanent
random/permanent greedy/matched random/matched greedy wins are
123/61/82/58/24 of 160. Every win/control gate, matched-greedy scorecard,
DEFER (`0.163862 <= 0.25`), one-brain authority, reward, lineage, and
reproducibility check passes. Permanent-greedy idle is `+0.00567867`, but its
95% CI `[-0.00022269,+0.01242934]` exceeds the frozen `1/150` margin. Public
result/preflight hashes are `9e2f31ee8053b296...` /
`4834b8c2832a0b6a...`. Dev-v45 is retired unopened/unconsumed, dev-v46 was
never constructed, and held-out-v7 remains sealed. Public attribution locates
the residual on no-transfer/seat-1 contexts while final seat 2 is favorable;
another transfer-local M8 wrapper is not supported. M8.5 remains unmet.

**OWNER-AUTHORIZED M9 DIRECTION (2026-07-23):** ADR-0069 explicitly
supersedes the M9 entry dependency in ADR-0013/0017/0019 after the governed
one-brain line reached its architectural ceiling. This does not promote V49 or
complete M8.5. Held-out-v7 remains sealed and M8-only. M9.1 begins on fresh
public train/dev namespaces with an all-seat parameter-shared recurrent IPPO
boundary; the implementation and complete public parity gate must be committed
before any M9 training episode.

Exit criteria:
- [x] M8_DESIGN.md + ADR-0011/0012 accepted; reward audit rows complete
- [x] Training runs reproducible (manifest + seeds + lockfile)
- [ ] Learned seat CI-beats greedy-utility on held-out; scorecard non-regressing
- [x] No known reward exploit; adversarial scripts in CI-runnable form

## Milestone 9: Multi-agent learning + partner robustness

Objective: all seats learned (parameter-shared IPPO → MAPPO), trained and
evaluated against a PARTNER POPULATION so coordination does not overfit to
clones. This is where "teammate" starts being trained for directly.

**ENTRY AUTHORIZED (2026-07-23):** ADR-0069 supersedes the former M8-promotion
prerequisite without relabeling M8 as successful. `docs/M9_DESIGN.md` defines
the staged implementation. Fresh public M9 train/dev sets are frozen. The
all-seat shared-parameter/recurrent-state boundary now passes unit, full-suite,
five-seed direct/traversed JVM parity, terminal-reset replay, smoke,
determinism/golden, and reward-adversary gates. The live report/model hashes are
`4773bf9b36b9972c...` / `e82745a19729aa31...`. At that entry boundary no M9
training, confirmation, held-out access, or MAPPO work was authorized. ADR-0070
then froze the first immutable IPPO recipe: one shared recurrent actor/local
critic, 2,048 episodes, exact optimizer/RNG streams, no teacher, the existing
shared team reward, one audited capped per-seat available-idle cost, and a
40-root public comparison with the fixed-role server expert. The recipe/protocol hashes are
`5d349b4a93f13342...` / `1f53ad0dde01a543...`. Reward/trainer implementation,
six new adversaries, frozen baseline evidence, and the complete pretraining
gate must be committed before replica A or any training episode. The
reward/rollout/optimizer implementation is now green: per-seat cumulative
charging, private-seat GAE, stored-hidden one-boundary PPO, all six adversaries,
and stochastic terminal-reset replay pass. The reward/rollout report hashes are
`f6b87fb96ccf206c...` / `70284030cb0cc2b4...`. A prior-combat Arc free-pool
reset leak was fixed; the regenerated 664-checkpoint golden changes only 128
state hashes, with zero action/event/tick/outcome changes. Exact replicas have
not started. The fixed server expert is now frozen from implementation commit
`dea79c487a` on all 40 public dev roots: 36 wins, mean core `967.95`, mean team
return `-1.641725`, idle `1.0`, and exact terminal-reset replay. Evidence SHA is
`ba4c9182f346a6ee...`. Run/checkpoint manifests and exact replay are now
implemented. Cross-process checkpoint content, fresh-JVM trace, and manifest
digests are `0d391dea0287ea28...`, `f85b6d34835594b0...`, and
`64ca9645816d99f8...`; public-only artifact report SHA is
`2a5b536ce71d07ee...`. The complete `m9-pretraining-check` passed from exact
implementation commit `2b62f7e5d7`: Python/Java, focused M9 checks, smoke,
cross-process/reset determinism, and the 664-checkpoint golden replay are green.
The versioned public-only preflight result has SHA `e0281b195eb87be...` and
records no confirmation or held-out access. The governed full-run runner is
implemented with exact-commit authority, 32 deterministic all-root cycles,
per-update 40-root dev selection, progress telemetry, fresh-JVM replay, paired
comparison, per-file serializer integrity, and canonical direct replica
identity. The first authorized A0 attempt collected 64 public train episodes
and then aborted before GAE, an optimizer update, checkpoint, or manifest: a
forced actor-excluded ABANDON uses placeholder index 9 while WAIT is masked.
ADR-0071 retires A0 and corrects validation without changing actions, rewards,
roots, budget, optimizer, RNG, architecture, or selection. The new focused
regression, 12-test IPPO module, and full 389-test suite pass. Commit the
correction and incident record, then rerun the complete gate from that exact
commit before restarting replica A in a clean output directory. Incident
evidence SHA is `c533018ee7f61885...`. That correction was committed as
`eabd0ce978`; the complete exact-commit gate passed. Clean A1/B1 replicas then
completed 2,048 episodes and 32 updates each with byte-identical manifests and
canonical full-run digest `186b7745c079f85a...`. No checkpoint reached the
frozen 30/40 public construction bar. Update 11 was best at 16/40 wins, mean
return `-7.878245`, mean core `390.05`, and idle `0.14656396`; the fixed expert
is 36/40. ADR-0072 therefore rejects `m9-ippo-v1` as an exact, public
generalization failure. No checkpoint is selected, MAPPO remains unauthorized,
and no confirmation or held-out data was accessed. A separately named
prospective IPPO successor is required. ADR-0073 now precommits
`m9-ippo-v2-sequence16` from that public evidence. The only learning change is
16-boundary truncated recurrent backpropagation within deterministic
episode/seat/reset windows; v1's model, runtime actions, reward, roots, budget,
optimizer, RNGs, selection, and public comparator remain fixed. Config/protocol
hashes are `266e50429902de0d...` / `ec9a69612b709290...`. No v2 trajectory,
optimizer update, checkpoint, or changed model state existed at precommit
time. Implementation, focused sequence/reset/gradient/padding evidence, and the
complete exact-commit gate are next. The sequence optimizer and
candidate-aware checkpoint/runner
boundary are now implemented locally. Focused tests prove length-one v1
equivalence, deterministic episode/seat/reset partitioning, padding invariance,
cross-boundary gradient flow, successor config/checkpoint binding, and exact
twin CPU updates; all 397 Python tests pass. Commit-bound worker evidence and
the complete gate are still required before replica A. The public-free
synthetic workers were rerun from exact implementation commit `9428d90055` and
match model state `b5495c745f29c311...`, optimizer state
`95fdc80083899212...`, and canonical checkpoint `bb134fd817965992...`.
Versioned report SHA is `580493699e7c342b...`. V2 fail-closed preflight and
training commands are committed. The complete public-only gate passed at
`bd28be1b8f`: 397 Python tests, pinned Java checks, all focused M9 checks, live
smoke, cross-process/reset determinism, and the M6 golden replay are green. The
versioned pretraining result SHA is `70cbefcc779bea60...` and records no
confirmation or held-out access. Because committing that result changes HEAD,
one final exact-commit gate rerun is required before replica A.
That rerun passed at exact commit `e6a29fb351`. Replica A completed the full
2,048-episode/32-update budget but failed construction: update 2 was best at
11/40 public dev wins, return `-14.70004`, core `260.425`, and idle
`0.29205803`; update 32 was 0/40. Training won 513/2,048, below v1's 598.
ADR-0074 rejects v2, prohibits replica B, leaves MAPPO blocked, and records
compact result SHA `42b4a2c4ee6eb542...`. No confirmation or held-out data was
accessed. A separately precommitted public IPPO successor is required.
ADR-0075 now precommits `m9-ippo-v3-diverse2048` from that public evidence.
V3 derives from v1 and changes only training-root diversity: 2,048 unique
public roots replace 32 repeats of 64 roots within the unchanged
2,048-episode/32-update budget. Seed 9603 shuffles the complete membership once
before 32 consecutive 64-root updates. V1's one-boundary optimizer, model,
reward, PPO values, dev roots, construction threshold, and expert comparator
remain exact. Config/protocol/train-root hashes are `5d437c390fc54423...`,
`29085f124d958f56...`, and `2e4d5b853ba9c8a6...`. Candidate-aware
config/checkpoint/manifest/preflight/
runner support is committed at `f32cba6f72`. The common schedule validator proves
all 2,048 roots appear once across exact 32-by-64 slices, zero v1-train/dev
overlap, and deterministic digest `a58244f31f21c24b...`. Focused governance
tests and the complete 404-test Python suite pass. Its implementation-bound
report reproduced byte-identically twice and is committed with SHA
`e8334ee662e718b7...`. The complete gate passed at exact commit `89de310520`.
Replica A completed all 2,048 unique-root episodes and 32 updates, but every
deterministic public-dev checkpoint was 0/40. Update 29 was best by return at
`-14.022125`, core `0.0`, and idle `0.12201736`; final update 32 was 0/40.
Stochastic training won 585/2,048, close to v1's 598. ADR-0076 rejects v3,
prohibits replica B and MAPPO, and records compact result SHA
`2e3ed1c113bcd1c0...`. No confirmation or held-out data was accessed. Before
another recipe, a bounded public-only stochastic-policy versus deterministic
argmax diagnostic must be precommitted and cannot repair or promote v3.
ADR-0077 now freezes that diagnostic before implementation: immutable v3
update 29, the same 40 public dev roots, one argmax stream, four categorical
streams at seeds 9602/19602/29602/39602, and two fresh-JVM exact repetitions.
At least 32/160 categorical wins denotes a diagnostic sampling signal only.
Protocol SHA is `89fecf69b76cd0fb...`. The fail-closed implementation and
focused tests pass at commit `8f574ef2b6`. Two fresh JVMs reproduce exactly at
digest `8b0b5fdd9083953d...`: argmax remains 0/40, while the four fixed
categorical streams win 56/160 in total (13/40, 11/40, 17/40, 15/40).
ADR-0078 accepts the predeclared sampling signal but keeps v3 rejected and
records compact result SHA `50c823d2d3d6123d...`. No restricted data was
accessed. The recommended v4 isolates entropy annealing toward zero over the
otherwise exact v3 recipe and requires a separate precommit before model work.
ADR-0079 now freezes `m9-ippo-v4-entropy-anneal`: every v3 mechanism remains
exact except the entropy coefficient, which follows the inclusive schedule
`0.02 * (32 - update) / 31` from update 1 through 32. Config/protocol hashes
are `9b9495e03b11e0fd...` and `db9b5647f249d308...`. Collection stays
categorical; dev evaluation stays deterministic argmax. No v4 trajectory or
optimizer update exists. Candidate-aware config/checkpoint/manifest/preflight/
runner support, exact inheritance checks, and per-update entropy telemetry are
implemented locally. Focused tests and the complete 417-test Python suite pass.
Implementation commit `d232d64dc5` and evidence commit `fbca0c6bbc` are
pushed. The complete gate passed at `fbca0c6bbc`, then Replica A completed all
2,048 public episodes and 32 updates. The deterministic frontier reached 16/40
at update 30 and 18/40 at update 31 with idle `0.09766800`, then update 32
collapsed to 0/40. ADR-0080 rejects v4 and prohibits Replica B. Compact result
SHA is `e85eb1d267412db4...`; no restricted data was accessed. A precommitted
public-only immutable-v4 late-checkpoint diagnostic is next, before any v5
recipe. ADR-0081 now freezes that diagnostic before implementation or
execution: updates 31 and 32, the same 40 public roots, one argmax and four
fixed categorical streams, two fresh JVMs, and exact 80%-retention versus
50%-collapse classification. Protocol SHA is `d68fee034d3b90e7...`. It cannot
select, repair, train, promote, or access restricted data. The fail-closed
runner, exact twin-JVM comparison, command surface, and focused tests are
implemented locally; all 420 Python tests pass. The two fresh JVMs reproduce
exactly at digest `a69c48c6120b87f1...`: update 31 is 18/40 argmax and 64/160
categorical, while update 32 is 0/40 argmax but retains 60/160 categorical
wins. ADR-0082 accepts deterministic mode instability, keeps v4 rejected, and
requires a separate precommit before one success-conditioned self-imitation
mechanism. Compact result SHA is `7273098097889601...`; no restricted data was
accessed. ADR-0083 now freezes `m9-ippo-v5-success-imitation`: v4 plus one
constant `0.02` sampled-action NLL over actor-valid transitions from winning
episodes in the current update only. It adds no replay, teacher, pass, RNG,
episode, root, reward, or restricted data. Config/protocol SHA prefixes are
`056a6ee24363b55a...` and `205508d8cfaba910...`. Implementation commit
`d6969679ad` preserves v1--v4 and adds exact filter/loss/telemetry,
candidate-aware artifact and authority paths, and a fail-closed CPU runner.
Ten focused tests pass. Two fresh synthetic runs reproduce byte-identically;
committed report SHA is `c8676245cee741f0...` and optimizer digest is
`27bd5804b512ccf1...`. The complete exact-current-commit public gate passed at
`84af0016f6` with all 430 Python tests, pinned Java checks, focused M9 checks,
smoke, determinism, and golden replay. Replica A completed 2,048 episodes and
32 updates, with 559 training wins feeding 27,614 qualifying transitions, but
deterministic public dev peaked at only 1/40 wins at update 7 and ended 0/40.
ADR-0084 rejects v5 and prohibits Replica B. Manifest/full-run digests are
`cdf0c86e3b5f5fa...` / `ef37b266b9f061ea...`; compact result SHA is
`f969cb595526763c...`. No restricted access occurred. Precommit one
immutable-v5 public-only diagnostic before any v6 recipe.
ADR-0085 now freezes that diagnostic before checkpoint execution: v5 updates
7 and 32, the same 40 public roots, one argmax and four fixed categorical
streams, two exact fresh JVMs, descriptive chosen-action probability/top-two
legal-logit margins, and integer-only retained-versus-eroded classification.
Protocol SHA is `9a9b44e36a22d68d...`. It cannot select, repair, train,
promote, or access restricted data. The fail-closed two-JVM runner,
action-mode measurement, exact classification, command surface, and four
focused tests are implemented at `e0efa3ac70`; all 434 Python tests pass. Two
fresh JVMs reproduce exactly at digest `1cfd3679cbebaaae...`: update 7 is 1/40
argmax and 51/160 categorical, while update 32 is 0/40 argmax but 62/160
categorical. ADR-0086 accepts retained stochastic success without deterministic
consolidation, keeps v5 rejected, and authorizes only a separately precommitted
strongest-alternative margin mechanism. Compact result SHA is
`0c0cbe21a53bf7d6...`; no restricted access occurred.
ADR-0087 now freezes `m9-ippo-v6-success-margin` before implementation or
training. V6 inherits v4 and adds only coefficient `0.02`, target `0.1`
`relu(target - (sampled_logit - strongest_other_legal_logit))` over
current-update winning actor transitions in every existing PPO minibatch.
V5's NLL is absent. Config/protocol SHA prefixes are `bd8e84acd0e340b6...` /
`f0adddd4c8b2127a...`. Implementation commit `05e6b48772` preserves v1--v5
and adds exact strongest-other loss/filter/telemetry, candidate-aware
artifact/authority paths, and a fail-closed CPU runner. Nine focused tests
pass; twin synthetic reports are byte-identical at SHA `4dc0463838756789...`
and optimizer digest `c11f5ecf0de81d2f...`. The complete public gate passed at
exact commit `f805e52842`. Replica A completed 2,048 episodes and 32 updates;
600 winning training episodes activated the margin on 30,412 transitions, but
deterministic public dev peaked at 2/40 wins at update 29 and finished 0/40.
ADR-0088 rejects v6 and prohibits Replica B. Manifest/full-run digests are
`d6ecb9f820ec975...` / `bc74e4b2f88a0e6...`; compact result SHA is
`37f3ecd470f7580a...`. No restricted data was accessed. Before any v7 model or
trajectory, a public-only v1--v6 design synthesis must freeze a change in the
source of action supervision rather than retune the rejected self-imitation
scalars. That synthesis is complete in `docs/M9_V1_V6_SYNTHESIS.md`.
ADR-0089 now freezes a public-only diagnostic of the 36/40 internal shared
expert as a candidate-native supervision source. Protocol SHA is
`3aea109ad7d876fb...`; it requires unique semantic projection onto the
same-boundary ordinary candidate/mask surface, exact fresh-JVM replay, and at
least 30/40 replay wins. It cannot train, modify a model, authorize v7, or
access restricted data. Implementation commit `6d9bd3708b` passed the full
gate and rebuilt-runtime replay checks. Two fresh JVM source runs reproduced
36/40 wins, but exact projection covered only 65/3,833 selections overall and
51/3,585 winning-episode selections. The frozen thresholds failed before
replay. ADR-0090 closes direct shared-expert distillation; compact result SHA
is `1d8eb99978ebf148...`. The next supervision source must be a prospectively
defined candidate-native planner that proves its own randomized-family
survival before any v7 model or trajectory. ADR-0091 now precommits
`candidate-native-planner-v1` before implementation or evaluation. It
coordinates one atomic bundle over ordinary authoritative candidates/masks,
reserves exclusive task/semantic targets across seats, and uses only structured
observations, the task board, accepted action results, and bounded reset-local
state. Protocol SHA is `4c1981c4ced305a2...`. Two fresh JVMs plus terminal-
reset replay must reproduce exactly, accept every action without a nonordinary
fallback or cross-seat conflict, reach at least 30/40 public wins, retain at
least 80% of the frozen 36-win source expert, and label at least 95% of
unforced boundaries with non-WAIT selections. This gate cannot train,
authorize v7, or access confirmation/held-out data. The planner, fail-closed
runner, command surface, and focused conflict/authority/threshold tests are now
implemented locally. The full 456-test Python suite, pinned Java/custom-module
suite, smoke, deterministic replay, and 664-checkpoint golden are green. Commit
this implementation boundary before the first governed 40-root run.
That run now rejects v1. Two fresh JVMs and terminal reset reproduce exactly,
and non-WAIT coverage is 4,959/4,963 (`99.9194%`), but survival is only 13/40.
Every episode also rejects one tick-250 fortification schematic with
`reservation_overlap`; distinct candidate ids/semantic targets do not expose
overlapping physical footprints. Full/compact result SHA prefixes are
`57f1c4d2c49075b1...` / `5a9df7fce1c39f14...`. ADR-0092 preserves the
rejection. ADR-0093 prospectively freezes v2's only change: at most one new
`BUILD_SCHEMATIC` selection per atomic bundle, with every other planner rule
and gate inherited exactly. Protocol SHA is `411c40c69ac7419f...`; implementation
now adds only that constructor-bound constraint, exact protocol/inheritance
validation, focused v1/v2 behavior tests, and a separate command surface. All
458 Python tests pass. The exact v2 run is bit-identical to v1: 13/40 wins and
the same 40 tick-250 rejections. V2 emits only one new schematic, but it
overlaps the already RUNNING build-line task from tick 0. Full/compact SHA
prefixes are `7d1e734bdacae51cb...` / `59d9993c9779abf0...`; ADR-0094 rejects
v2. ADR-0095 precommits v3's only change: consult the authoritative task board
and defer new BUILD_SCHEMATIC candidates while a BUILD_LINE or
BUILD_SCHEMATIC task is CLAIMED, RUNNING, or BLOCKED. Protocol SHA is
`fc8be8ce0bf63015...`. Implementation is next; no v7 or restricted access is
authorized. The task-board filter, exact protocol/inheritance validation,
focused v1/v2/v3 behavior tests, and separate command surface are now local;
all 460 Python tests pass. Commit this boundary before evaluation.
The exact v3 gate accepts every action and reproduces across fresh JVM/reset,
but survival falls to 3/40 with 99.4711% non-WAIT coverage. At the public
tick-250 boundary its idle seat chooses harvest while two underfilled-turret
supply targets are valid. ADR-0096 rejects v3; full/compact SHA prefixes are
`b94f02d2183aa4db...` / `9af4d952fc690c53...`. ADR-0097 precommits v4's sole
change: in the active-build defer state with positive turret coverage and ammo
below one, rank SUPPLY_TURRET above HARVEST_RESOURCE. Protocol SHA is
`ffb5bff61b76161e...`; implementation is next.
The exact active-build supply score, protocol/inheritance validation, focused
v1--v4 tests, and separate command are now local; all 462 Python tests pass.
V4 is canonical-trace identical to v3 at 3/40: its positive turret-coverage
precondition never activates even though actor-masked supply candidates exist.
ADR-0098 rejects the no-op; compact SHA is `57aa6bdbdbacd84e...`. ADR-0099
precommits v5's sole change as removing that redundant coverage clause and
using valid supply-candidate existence plus ammo below one. Protocol SHA is
`f408fcc9c200a74e...`; implementation is next.
The exact precondition removal, protocol/inheritance checks, focused v1--v5
tests, and command are local; all 464 Python tests pass. Commit before the gate.
V5 improves to 12/40 with 99.9560% coverage but still has eight BUILD_LINE
`reservation_overlap` rejections at ticks 1921--2031 after the completed
fortification occupies that footprint. ADR-0100 rejects v5 at compact SHA
`3ac6102e640ee8f7...`. ADR-0101 precommits v6's sole change: suppress
BUILD_LINE after the authoritative board records `expert_fortification_v1`
COMPLETED. Protocol SHA is `748032f71739c878...`; implementation is next.
The exact board filter, protocol/inheritance checks, focused v1--v6 tests, and
command are local; all 466 Python tests pass. Commit before evaluation.
V6 reaches 27/40 with 99.6804% coverage but retains eight BUILD_LINE
rejections because the expert fortification is RUNNING, not yet COMPLETED.
ADR-0102 rejects v6 at compact SHA `930b617186248ea3...`. ADR-0103 precommits
v7's sole change as widening that board predicate to
CLAIMED/RUNNING/BLOCKED/COMPLETED. Protocol SHA is `df0427db128c8543...`;
implementation is next.
The lifecycle predicate, exact protocol/inheritance checks, focused v1--v7
tests, and command are committed; all 468 Python tests pass. V7 eliminates all
action rejections and is exact across twin JVM/reset, but remains 27/40 at
99.7620% coverage. Public boundary inspection shows losing roots retaining
exposed DEFEND work through the safe inter-wave interval. ADR-0104 rejects v7
at compact SHA `d46d86025d0e45ec...`. ADR-0105 precommits v8's sole change:
abandon DEFEND when there are no enemies and the next wave is outside the
authoritative defend-lead window. Protocol SHA is `168317b2e5a34e64...`;
the exact rule, inheritance validation, focused v7/v8 tests, and separate
command are implemented locally; all 471 Python tests pass. Commit before the
gate.

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

**M10 PREIMPLEMENTATION ARCHITECTURE ACCEPTED (2026-07-23):**
`docs/M10_DESIGN.md` and ADR-0057 pin the command/control schema, simulation-
thread queue, autonomy/quiet semantics, telemetry, and acceptance gates. They
also make the existing `docs/CANDIDATE_GAPS.md` seam a hard prerequisite: the
real-time plugin must move from `ExpertCoordinationDriver`'s stage-local
candidates to the public `EngineCandidates` / typed-action path before human
goals are applied. M10 implementation has begun only on that prerequisite; it
does not start M9, authorize V43, or access any governed seed membership. The first
behavior-neutral prerequisite now exists: `AgentRuntimeRegistry` removes the
public candidate/coordination adapters' concrete training-registry dependency;
`DemoAgentRegistry` implements that boundary for deterministic spawn/rebind. A
tested engine-neutral Java `GreedyUtilityPolicy` now mirrors selection, replan
throttling, wave preemption, and combat logistics preference over public
candidates/masks. The default
real-time plugin now runs the full candidate -> mask -> typed action -> board ->
reservation -> skill path and reached readiness after ordinary wave-damage
recovery and rebind. Its stock-clock public-path survival gate
passes through tick 8100 at full core health, with structured evidence for all
three wave clears, both expansion/maintenance completions, and reserve mining.
Exact public-path parity also passes: Python matches 390 real plugin candidate/
mask boundaries and all 1,170 Java actions, while two fresh JVMs reproduce 225
accepted selections with digest `aaf2e734ea384fe4b537cbdf3bd5342fb5e954f3432a91470ebce311fa503714`.
A persistent logistics seat reduces seven abandon/reclaim cycles to two phase-
entry rebalances and seven unassigned waits. All prerequisites and default
promotion are green; `DEMO_PUBLIC_POLICY=0` preserves the legacy regression
oracle, and command implementation is next.

The first command packet is now implemented in `agent-core`: an engine-free
strict parser and simulation-thread-owned control state provide bounded ordered
goals, assignments, autonomy/quiet settings, deterministic ids/revisions,
stable result reasons, and reset behavior. The engine-free overlay core is also
present: explicit
human task provenance wraps only already-valid structured ordinary candidates,
reserves bounded slots in goal order, and preserves WAIT. Empty control omits
the metadata, leaving autonomous canonical bytes, observations, and hashes
unchanged. Engine matching, assignment masks, and command queuing are now live:
callbacks enqueue only, the simulation thread applies structured commands, and
the public path honors explicit assignment plus LOW/NORMAL/HIGH and quiet
semantics. A deterministic no-port probe completes an assigned human build-line
goal, exercises LOW and HIGH defense goals, and releases/cancels all state; the
exact public digest and full-health stock survival remain green. Human build-
plan detection now reserves exact footprints and rules-scaled costs, yields
overlapping or resource-conflicting agent work, protects recent construction
for 600 ticks, and emits exactly one rendered conflict notice. M10.1 and M10.2
are complete; opt-in session capture is next.

- **DONE (verified 2026-07-23) — 10.1 Human command surface v2:** `/agents goal <task> <region>`,
  `/agents cancel <goal-id>`, `/agents assign <agent> <goal-id>`,
  `/agents release <agent>`,
  `/agents autonomy low|normal|high`, `/agents quiet on|off` — human-created
  goals become high-priority board tasks entering the SAME candidate stream
  (human_priority weight already exists); validated, confirmable, revocable.
- **DONE (verified 2026-07-23) — 10.2 Human-presence adaptation:** detect human build plans/recent construction
  zones in the demo (plugin observes player plans), register them as
  human-priority reservations (board rule exists — wire the detection), agents
  yield + announce the conflict exactly once; never deconstruct human work;
  never consume the human's reserved resource budget below a floor.
- **IN PROGRESS (capture/statistics/models implemented 2026-07-23; M9 activation gated) — 10.3 Human session capture (local, opt-in):** demo sessions record the same
  event/trajectory JSONL as training episodes + human actions; from these,
  (a) partner-style statistics (pace, role preference, plan-changes) and
  (b) scripted human-partner models (fast-expert / slow-beginner / cautious /
  plan-changer / help-requester) join the M9 partner population. Capture,
  deterministic control replay/statistics, and all five executable profiles are
  complete; actual population activation remains blocked on M8 promotion and
  M9 authorization, so the M10 exit checkbox remains open.
- **IN PROGRESS (objective derivation/rating protocol implemented 2026-07-23; real sessions pending) — 10.4 Teammate scorecard v1 (human terms):** human intervention rate, plan
  conflicts per session, yield latency, goal-compliance rate, time-to-help on
  human requests, announcement usefulness rating, post-session preference
  ("keep this team?" + comparative rating vs scripted team). Session protocol
  documented; results logged per session in runs/. The create-new local tool
  derives every objective field from capture and accepts only an explicit,
  digest-bound rating file. Opted-in private join mode now preflights capture
  and scorecard paths, validates the completed session, and automatically writes
  an unrated objective scorecard after normal exit. The deterministic probe
  leaves ratings null. A create-new rating tool binds four explicit human
  answers to the validated capture digest and rejects extra/free-text fields;
  a create-new evidence report rejects duplicates and separates incompatible
  runtime/scenario/policy groups. Capture v3 now adds the project commit and
  canonical plugin/server runtime-content hashes. Legacy v1/v2 remains readable
  but cannot count toward the provenance-complete floor; v2 whole-JAR hashes
  were superseded after deterministic builds exposed volatile upstream archive
  metadata. Two fresh committed v3 JVMs reproduce content/provenance exactly.
  Per ADR-0058, three serious compatible v3 sessions meet only the
  collection floor: learned/scripted targets and a
  paired agents-present/absent protocol must be precommitted before acceptance
  collection. ADR-0059 now freezes that protocol and its targets: three
  counterbalanced absent/scripted/learned blocks, capture-time assignment,
  strict per-metric learned-versus-scripted non-regression, and direct owner
  preference. Capture v4 and the no-port zero-agent gate are implemented.
  Learned assignments remain unavailable until M8 promotion and M10.5; real
  serious sessions and human-entered ratings are still required.
- 10.5 Learned policy in the demo seat: latency budget (decision within one
  real-time tick), safety invariants live (stop/pause instant, autonomy
  levels honored), fallback to scripted brain on policy-process failure.
- 10.6 Iterate to the bar: fine-tune against the human-partner population;
  exit when scorecard targets hold across ≥3 distinct human sessions and the
  human prefers playing WITH agents vs without on the same scenario.

Exit criteria:
- [x] Human goals/overrides work end to end; agents never fight human plans
- [ ] Human sessions captured; human-partner models in the training population
- [ ] Learned team scores ≥ scripted team on scorecard v1 WITH a human present
- [ ] The project owner, playing seriously, prefers the agent team present
      (recorded sessions + ratings) — the north-star acceptance

---

Cross-cutting (any milestone): protobuf migration only if profiling crosses
the ADR-0004 trigger; engine pin frozen; every new reward component blocked on
its REWARD_AUDIT row; docs/STATUS.md + HANDOFF.md updated per change, as ever.
