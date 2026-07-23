# Upstream patches

Every direct modification to an upstream Mindustry file is catalogued here
(ADR-0010). The policy is: **prefer new modules; keep upstream edits tiny,
purpose-specific, and listed here with reason and diff summary.** Never hand-edit
`mindustry.gen` generated classes.

## Current upstream edits

### 1. `settings.gradle` — register custom modules

- **Reason**: Gradle must know about the three custom modules (`rl-server`,
  `agent-core`, `agent-plugin`). There is no non-invasive way to add a subproject
  to a Gradle build other than `include`-ing it in the settings file.
- **Diff summary**: after the existing
  `include 'desktop', 'core', 'server', 'ios', 'annotations', 'tools', 'tests'`
  line, added a comment and one line:
  `include 'rl-server', 'agent-core', 'agent-plugin'`.
- **Risk**: minimal — additive only; does not alter upstream module config, the
  Android/Arc/localRhino conditionals, or Java version checks.
- **Introduced by**: repository scaffold (this branch).

### 2. `core/src/mindustry/ai/Pathfinder.java` — synchronous deterministic flowfield update

- **Reason**: enemy ground units (wave daggers) steer by the flow-field
  `Pathfinder`, which the engine updates on a **free-running, wall-clock-paced
  background thread** (`run()`, 8 ms budget + `Thread.sleep`). That thread is
  non-deterministic, so `rl-server` disables it before world load and drives the
  work synchronously.
  With it stopped, nothing advances a flow field when tiles change, and there is
  no public entry point to converge one on the simulation thread — the update
  methods (`updateFrontier`, `updateTargets`, `queue`) are all `private`. A tiny,
  isolated method exposes exactly that, so the stepper can converge the field once
  per tick on the sim thread with **no wall-clock budget** (docs/ENGINE_NOTES.md
  §5.5, §11.6). M8.4 extends that boundary so the worker cannot restart during
  external stepping.
- **File / lines**: `core/src/mindustry/ai/Pathfinder.java` — the existing
  `syncUpdate()` entry point remains, while M8.4 adds an external-mode worker
  disable flag/method and prevents the wall-clock refresh callback from
  consuming deterministic-mode work.
- **Diff summary**: adds the following simulation-thread-only sequence:
  ```java
  public void syncUpdate(){
      if(net.client()) return;
      if(state.isPlaying()){
          if(needsRefresh){
              needsRefresh = false;
              for(Flowfield path : mainList){
                  if(path != null && path.needsRefresh()){
                      synchronized(path.targets){
                          path.updateTargetPositions();
                      }
                  }
              }
              for(Flowfield data : threadList){
                  data.dirty = true;
              }
          }
          queue.run();
          for(Flowfield data : threadList){
              if(data.dirty && data.frontier.size == 0){
                  updateTargets(data);
                  data.dirty = false;
              }
              updateFrontier(data, -1);   //-1 => unbounded budget, full convergence
          }
      }
  }
  ```
  The queue/frontier portion mirrors `run()`'s loop, substituting the `maxUpdate`
  (8 ms) budget with `-1` (unbounded). The leading block performs the refresh work
  that normal play schedules through `afterGameUpdate`, without its wall-clock
  delay or asynchronous queue hand-off. `rl-server` calls the method once per tick
  after each `stepOnce()` (and once at reset). Wave `GroundAI` consults the
  flow-field `Pathfinder`
  (`AIController.pathfind → pathfinder.getField(...).getNextTile(...)`);
  `ControlPathfinder` serves `CommandAI`/`LogicAI` and now has the matching
  external-mode worker-disable hook catalogued in entry 3.
- **Behaviour change for normal game mode**: **none**. The engine never calls
  either external-mode disable hook or `syncUpdate()`; threaded play retains
  the upstream behavior.
- **Determinism audit of the synchronous path**:
  - *Iteration order*: `threadList` is appended in registration order (one field —
    the wave-team ground core field — in v0); `updateFrontier` is a plain BFS over
    an `IntQueue`; `updateTargets` iterates `IntSeq` targets in order. No unordered
    iteration, no floating-point reduction. Deterministic.
  - *RNG*: the only `Rand` in the flow-field code is
    `Pathfinder.EnemyCoreField.getPositions()` (`:602-604`), guarded by
    `state.rules.randomWaveAI`. The scenario sets `randomWaveAI = false`, so the
    branch — and its `hashCode()`/`state.tick`-seeded `Rand` (the ENGINE_NOTES §6
    caveat) — is **never entered**. Belt-and-braces: `state.rules.waves = true`, so
    even if it were entered the seed would be `state.wave` (deterministic), never
    `hashCode()`. Neutralized by rules, not by patch.
  - *Wall clock*: `syncUpdate()` reads no clock. The one remaining `Time.millis()`
    gate is the normal-mode `afterGameUpdate` refresh handler (`:187-194`). In the
    thread-less deterministic path, `syncUpdate()` now consumes `needsRefresh`
    immediately on the simulation thread, refreshes targets, marks every registered
    flow field dirty, and fully converges it in the same call. It does not read or
    update the wall-clock timestamp. A guard keeps the ordinary callback out of
    this external mode.
- **Risk**: narrow — external mode changes worker startup/refresh hand-off only
  after the new hook is called; normal mode is unaffected. Verified by
  `bash scripts/determinism.sh` (two fresh JVMs, identical
  hashes across the moving-enemy window) and `scripts/smoke.sh` (daggers path to the
  core deterministically).
- **Introduced by**: bootstrap-defense-v0 scenario loader (this branch, M4 prep).
- **M4.1 amendment (2026-07-20)**: extended only `syncUpdate()` with the
  thread-less tile-change refresh described above. Verified by the determinism
  harness placing a copper wall in the east lane after wave 1 spawns, then comparing
  hashes across two fresh JVMs while daggers continue around the changed tile.
- **M8.4 amendment (2026-07-21)**: added `backgroundThreadEnabled`,
  `disableBackgroundThread()`, and a deterministic-mode guard around the
  wall-clock refresh hand-off. `rl-server` disables the worker before world
  load and drives `syncUpdate()` on the simulation thread. Normal game mode
  retains the original threaded path.

### 3. `core/src/mindustry/ai/ControlPathfinder.java` — external worker disable

- **Reason / diff**: deterministic external stepping cannot leave the command
  pathfinder on a wall-clock worker. A private enable flag makes `start()`
  opt-out, and `disableBackgroundThread()` stops an existing worker. Ordinary
  game mode never calls it.

### 4. `core/src/mindustry/entities/EntityGroup.java` — external stable ordering

- **Reason / diff**: swap removal and unordered sleeping-building re-addition
  made identical training runs diverge. External mode may install a stable
  integer key; `rl-server` uses reverse tile position only for `Groups.build`.
  External removals shift in order and repair affected generated indices.
  Ordinary mode retains upstream swap removal.
- **Verification**: dedicated tests cover insertion, removal/index repair, and
  insertion ahead of the update cursor; independent PPO action/state traces
  match bit-exactly.

### 5. `core/src/mindustry/entities/comp/BuildingComp.java` — proximity order

- **Reason / diff**: `ObjectSet` proximity callbacks could choose different
  conveyor neighbors and sleeping-building wake order. External mode sorts
  stored proximity plus add/remove notification targets by tile position;
  ordinary mode retains the upstream path.

### 6. `core/src/mindustry/world/blocks/ConstructBlock.java` — headless RNG guard

- **Reason / diff**: headless placement sound pitch consumed global RNG despite
  having no observable effect. Placement effect/sound emission now requires
  `!headless`; graphical play is unchanged.

### 7. `.github/workflows/{pr,push,gradle-wrapper-validation}.yml` — upstream-only guards

- **Reason**: the inherited Mindustry workflows are designed for
  `Anuken/Mindustry`; two fetch Arc from the moving `master` branch and all
  exercise upstream build surfaces rather than this fork's pinned custom
  modules and Python package. Allowing them to run in the fork would violate the
  source-pin rule and duplicate the project-owned CI workflow.
- **Diff summary**: each inherited job has one job-level
  `if: github.repository == 'Anuken/Mindustry'` guard. Their upstream behavior
  is otherwise byte-for-byte unchanged. The additive
  `.github/workflows/coop-agent-ci.yml` owns fork CI with pinned action SHAs,
  hash-locked Python dependencies, Java/Python tests, and custom distributions.
- **Risk**: minimal — upstream runs are unaffected; fork runs skip only jobs
  that were unsafe and irrelevant here.
- **Introduced by**: Milestone 0 CI closure packet (2026-07-23).

## M1 decision: pathfinder threads — reflection, not an upstream patch

The brief sanctioned a minimal upstream edit to force the two free-running
pathfinder threads (`Pathfinder`, `ControlPathfinder`) synchronous *if* they
could not be cleanly avoided. **No upstream edit was needed for M1.** The M1
scenario has no waves, no enemies, and no commanded units, so no flowfields are
ever created and nothing consumes pathfinding. `rl-server` stops both threads
immediately after world load by invoking their private `stop()` via reflection
(`RlServer.stopPathfinders()`), so they never run during an episode. This keeps
the checkout free of upstream modifications.

**Update (bootstrap-defense-v0 loader):** revisited and resolved. Enemy wave
daggers do consume the flow-field `Pathfinder`, so the sanctioned `syncUpdate()`
patch (entry 2 above) was added — the cleaner choice than reflecting into four
private members (`threadList`, `queue`, `updateFrontier`, `updateTargets`), and the
exact approach ENGINE_NOTES §11.6 recommends. Both threads stay stopped;
`syncUpdate()` drives the field synchronously on the sim thread. M8.4 later
added explicit external-mode disable hooks for both workers (entries 2–3), even
though current wave AI does not consume `ControlPathfinder`.

When units/enemies arrive (M3+) and
pathfinding is actually consumed, a synchronous `syncUpdate()` — reflection or a
catalogued upstream patch — will be revisited then (see `docs/ENGINE_NOTES.md`
§5.5, §11.6).

Other engine gaps handled without upstream edits, via reflection into public
engine classes on the classpath (no `--add-opens` needed):

- `EntityGroup.lastId` (private static) reset to 0 per episode.
- `Pools.typePools` (private static) enumerated on reset so only free pooled
  objects are discarded after the outgoing world is cleared. This prevents
  prior-combat pool occupancy from changing later entity allocation.
- `Time.globalTimeRaw` / `Time.globalTime` zeroed per episode (`setInternalTime`
  covers `timeRaw`/`time`; `globalTimeRaw` has no public setter).

## Not counted as upstream patches

- New files under `rl-server/`, `agent-core/`, `agent-plugin/`, `python/`,
  `docs/`, `scripts/`, `scenarios/`, `configs/`, and new top-level files
  (`AGENTS.md`, `CLAUDE.md`, `NOTICE.md`, `ENGINE_VERSION`, `Makefile`) are
  **additions**, not modifications of upstream files, and do not require an entry
  here.
- `.github/workflows/coop-agent-ci.yml` is a project-owned additive workflow;
  only the three inherited workflow guards are counted as upstream patches.
- `tests/golden/bootstrap-defense-v0-scripted-v1.jsonl` is an additive M6
  project-owned replay fixture in the roadmap-mandated golden directory. It
  modifies no upstream test source or build configuration.
- The `.gitignore` additions are appended to an upstream file but are purely
  additive ignore rules. Noted here for completeness; not a behavioural patch.

## Generated files

- `annotations/src/main/resources/classids.properties` may show as modified
  during a Gradle build — it is **generated**, not a hand edit. Do not commit
  incidental regenerations of it as part of scaffold commits.
