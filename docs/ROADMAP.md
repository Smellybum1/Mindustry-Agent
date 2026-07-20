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
- [ ] Server build command verified
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
      in-JVM resets identical; `bash scripts/determinism.sh` → exit 0). NB: the
      M1 scenario has no RNG/time-driven state, so the *seed* lever is not yet
      exercised (see `docs/STATUS.md`); the stepping/clock/reset determinism is.
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

**M2 caveats (truthful):** per-agent observations are still world-level (M3);
`MindustryParallelEnv` wires the per-agent dict plumbing but every agent receives
the same world observation and actions are accepted-but-no-op. Scaling is capped
at 4 JVMs (shared host); ≥10,000-reset Gate 5 and 8/16-JVM scaling are deferred.

## Milestone 3: Agent entities and first skills

Deliverables:
- [ ] Stable agent identities (`agentcore.AgentId` exists; ownership pending)
- [ ] Controlled unit ownership
- [ ] Navigate, mine, deliver, wait skills
- [ ] Action masks
- [ ] Skill telemetry

Exit criteria:
- [ ] Scripted single agent mines and delivers copper from multiple seeded starts
- [ ] No teleporting or free-resource shortcuts
- [ ] Skill failure reasons are testable

## Milestone 4: Build and defence skills

Deliverables:
- [ ] Fixed schematic execution
- [ ] Supply building/turret
- [ ] Repair
- [ ] Defend region
- [ ] Emergency retreat

Exit criteria:
- [ ] One scripted agent can build and supply a Duo in the exact engine
- [ ] One scripted agent can defend a marked lane
- [ ] Skills survive repeated reset tests

## Milestone 5: Coordination and announcements

Deliverables:
- [ ] Task catalog (`agentcore.TaskType` vocabulary fixed; semantics pending)
- [ ] Candidate generator
- [ ] Shared task board
- [ ] Claims/leases
- [ ] Help offers
- [ ] Reservations
- [ ] Human-readable templates
- [ ] Scripted multi-agent policy

Exit criteria:
- [ ] Two or more agents announce distinct work
- [ ] A helper contract is accepted and completed
- [ ] Duplicate task claims are resolved
- [ ] Stale claim expires after a simulated agent failure
- [ ] Communication rate limit passes tests

## Milestone 6: Bootstrap Defense v0

Deliverables:
- [ ] Complete scenario (`scenarios/bootstrap-defense-v0/`, spec only today)
- [ ] Scripted expert
- [ ] Evaluation metrics
- [ ] Replay
- [ ] Demo plugin

Exit criteria:
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
