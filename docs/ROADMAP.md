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
≥10,000-reset Gate 5 and 8/16-JVM scaling are deferred.

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
- Objective: ordered BuildBlock list from
  `scenarios/schematics/east_duo_v1.json` (new; single source of truth; layout
  per docs/SCENARIOS.md east defence: 2 Duos + copper walls, turrets first).
- Acceptance: schematic completes on a fresh episode; progress reported as
  completed/total; determinism with the build trace; cost ledger balances
  (sum of block costs).
- Depends: 4.2.

### 4.4 SupplyBuilding (S3)
- Objective: withdraw copper from core via the legal reverse path (resolve
  M4_DESIGN open question 2 — cite the call), carry, `transferItemTo` the
  turret; `SUPPLY {x,y,item,amount}` action; BLOCKED(CORE_SHORT) reachable.
- Acceptance: supply 30 copper to a built Duo — turret ammo +30-equivalent
  (resolve ammo accounting, open question 4), core copper −30 exactly, agent
  cargo 0; ledger printed in smoke.
- Depends: 4.2 (needs a turret to exist).

### 4.5 RebuildRegion (S4)
- Objective: re-enqueue broken-block plans within a rect from the team's
  broken-block queue (resolve open question 3: field + iteration order);
  "repair" of standing damaged blocks is explicitly OUT (alpha cannot heal —
  scenario v1 adds a Mender instead).
- Acceptance: wave destroys a wall → RebuildRegion restores it, cost paid
  again from core, ledger balances; SUCCEEDED when rect has no broken blocks.
- Depends: 4.2; waves (done).

### 4.6 DefendRegion (S5) + EmergencyRetreat (S6)
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
- Objective: per-agent build-queue depth + plan progress in observations; team
  broken-block count; turret ammo in team/building summary; hash gains ordered
  build plans, broken-block queue, turret ammo (M4_DESIGN §Hash).
- Acceptance: docs/PROTOCOL.md updated; protocol.py dataclasses + tests;
  hashes perturb deterministically under build/supply traces.

### 4.8 M4 acceptance run
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
- Objective: claiming a build task reserves the schematic footprint (tiles) and
  estimated copper; supply tasks reserve resource budget; abandonment/expiry
  releases (board semantics exist — wire acquire/release into the adapter).
- Acceptance: two builder agents given overlapping candidates never place
  conflicting plans (property test live in-engine); reservation conflict emits
  the documented event.

### 5.5 Lease expiry / failure recovery (chaos)
- Objective: simulate an agent failure mid-task (stop sending its actions +
  suppress its heartbeats via a test hook); its lease expires; the task reopens;
  another agent claims and completes it.
- Acceptance: scripted chaos run shows expiry → reclaim → completion in the
  event log; episode still terminates normally; determinism unaffected (the
  "failure" is part of the action trace).

### 5.6 Announcements end-to-end + metrics
- Objective: rendered announcement strings (templates exist) surfaced in
  StepResponse `task_events[]` and printed by the python runner exactly at
  meaningful transitions (rate limits enforced by the board; heartbeats never
  rendered). Team metrics counters into `infos`: duplicate-work incidents,
  idle fraction, task completion/abandonment counts (brief §22.1 subset).
- Acceptance: a headless scripted run prints a coherent transcript matching
  brief §12.4 shape (intent → helper offer/accept → progress → blocked →
  complete); rate-limit tests pass live; message count bounded.

Exit criteria (brief, unchanged):
- [ ] Two or more agents announce distinct work
- [ ] A helper contract is accepted and completed
- [ ] Duplicate task claims are resolved
- [ ] Stale claim expires after a simulated agent failure
- [ ] Communication rate limit passes tests

## Milestone 6: Bootstrap Defense v0

Loader status: **done and verified 2026-07-20** — full 48×48 world, ore
patches, east spawn, 250-copper loadout, deterministic 3-wave dagger schedule
(2700/4500/6300) from `scenario.json`, moving enemies (sync pathfinder patch),
win/loss/truncate termination, seed sensitivity. Remaining M6 = the team
actually winning it, and humans watching it happen.

### 6.1 Scripted expert team
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
- Objective: per-episode JSONL summary (outcome, milestone ticks: first drill,
  line complete, turrets built, turrets supplied; core damage; units lost;
  resource totals; task stats: completed/abandoned/duplicated; idle fraction;
  message counts) written under `runs/` from `infos` — brief §22.1 subset.
  `evaluate-scripted` script: N episodes across the seed set → aggregate table.
- Acceptance: `make evaluate-scripted` produces the table; numbers land in
  docs/BENCHMARKS.md (M6 section).

### 6.3 Replay + golden traces
- Objective: record seed + full action/coordination trace per episode
  (compact JSONL); `tools/replay.py` re-runs a trace through a fresh JVM and
  verifies hash checkpoints. Check in one golden trace ≥10,000 ticks
  (Gate 1 target) under `tests/golden/` with expected hashes; wire into
  `make determinism` as a second stage.
- Acceptance: golden replay byte-identical on a fresh checkout; a deliberate
  one-line skill change flips the hash (documented negative test, then
  reverted).

### 6.4 agent-plugin demo server (human-joinable)
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
- Objective: docs/STATUS.md, docs/BENCHMARKS.md (evaluation numbers),
  docs/HANDOFF.md refreshed; tag `milestone-6` commit; brief §32 checklist
  audit (items 1–15) recorded in STATUS.md with honest per-item state.

Exit criteria (brief, unchanged):
- [ ] Scripted agents complete the scenario across a defined seed set
- [ ] Human can join a private real-time server and observe/use the agents
- [ ] Training and demo mode share the same skills and task board
- [ ] Deterministic replay matches training results

## Milestone 7: Learned single-agent selector

Deliverables:
- [ ] Random and heuristic baselines
- [ ] PPO task selector
- [ ] Training configuration
- [ ] Checkpoint/evaluation pipeline
- [ ] Reward audit (`docs/REWARD_AUDIT.md` template exists)

Exit criteria:
- [ ] Learned policy beats random valid
- [ ] Behavioural videos/logs show real task progress
- [ ] No known trivial reward exploit remains

## Milestone 8: IPPO multi-agent baseline

Deliverables:
- [ ] Parameter-shared actor
- [ ] Per-agent hidden state or history
- [ ] Structured communication observation
- [ ] Communication/no-communication comparison

Exit criteria:
- [ ] Multi-agent policy beats fixed-role baseline on ≥1 randomized scenario family
- [ ] Task duplication and idle time are measured
- [ ] Checkpoints reproduce evaluation results

## Milestone 9: MAPPO and partner diversity

Deliverables:
- [ ] Centralized critic
- [ ] Population of partner policies/scripts
- [ ] Held-out partner evaluation
- [ ] Failure/dropout curriculum

Exit criteria:
- [ ] Policy works with unseen partner checkpoints
- [ ] Performance degrades gracefully if one teammate fails
- [ ] Coordination communication provides measurable benefit

## Milestone 10: Human-agent study and polished demo

Deliverables:
- [ ] Human goal/override commands
- [ ] Announcement UI
- [ ] Session logging
- [ ] Human evaluation protocol
- [ ] Video/replay tooling

Exit criteria:
- [ ] Human can play a complete scenario with agents
- [ ] Emergency stop and override work
- [ ] Agents do not repeatedly fight human plans
- [ ] Human feedback and intervention metrics are captured
