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
  non-deterministic, so `rl-server` keeps it **stopped** (reflection, unchanged).
  With it stopped, nothing advances a flow field when tiles change, and there is
  no public entry point to converge one on the simulation thread — the update
  methods (`updateFrontier`, `updateTargets`, `queue`) are all `private`. A tiny,
  isolated method exposes exactly that, so the stepper can converge the field once
  per tick on the sim thread with **no wall-clock budget** (docs/ENGINE_NOTES.md
  §5.5, §11.6). This was the single sanctioned upstream edit the brief reserved for
  Risk 1/Risk 3.
- **File / lines**: `core/src/mindustry/ai/Pathfinder.java:356-378` — one new
  `public void syncUpdate()` (25 lines incl. javadoc), inserted immediately before
  `getField(...)`. No existing line changed.
- **Diff summary**: adds
  ```java
  public void syncUpdate(){
      if(net.client()) return;
      if(state.isPlaying()){
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
  It mirrors the body of `run()`'s loop **exactly**, substituting the `maxUpdate`
  (8 ms) budget with `-1` (unbounded). `rl-server` calls it once per tick after
  each `stepOnce()` (and once at reset). `ControlPathfinder` is **not** patched:
  wave `GroundAI` consults only the flow-field `Pathfinder`
  (`AIController.pathfind → pathfinder.getField(...).getNextTile(...)`);
  `ControlPathfinder` serves only `CommandAI`/`LogicAI`, which our units do not use.
- **Behaviour change for normal game mode**: **none**. The engine never calls
  `syncUpdate()`; the threaded `run()` path is byte-for-byte unchanged. The method
  is only reachable from `rl-server` with the thread stopped.
- **Determinism audit of the synchronous path**:
  - *Iteration order*: `threadList` is appended in registration order (one field —
    the wave-team ground core field — in v0); `updateFrontier` is a plain BFS over
    an `IntQueue`; `updateTargets` iterates `IntSeq` targets in order. No unordered
    iteration, no floating-point reduction. Deterministic.
  - *RNG*: the only `Rand` in the flow-field code is
    `Pathfinder.EnemyCoreField.getPositions()` (`:555-556`), guarded by
    `state.rules.randomWaveAI`. The scenario sets `randomWaveAI = false`, so the
    branch — and its `hashCode()`/`state.tick`-seeded `Rand` (the ENGINE_NOTES §6
    caveat) — is **never entered**. Belt-and-braces: `state.rules.waves = true`, so
    even if it were entered the seed would be `state.wave` (deterministic), never
    `hashCode()`. Neutralized by rules, not by patch.
  - *Wall clock*: `syncUpdate()` reads no clock. The one remaining `Time.millis()`
    gate is the normal-mode `afterGameUpdate` refresh handler (`:190-193`). In the
    thread-less deterministic path, `syncUpdate()` now consumes `needsRefresh`
    immediately on the simulation thread, refreshes targets, marks every registered
    flow field dirty, and fully converges it in the same call. It does not read or
    update the wall-clock timestamp. The ordinary threaded handler is untouched.
- **Risk**: minimal — additive public method, no existing code touched, no normal-mode
  path affected. Verified by `bash scripts/determinism.sh` (two fresh JVMs, identical
  hashes across the moving-enemy window) and `scripts/smoke.sh` (daggers path to the
  core deterministically).
- **Introduced by**: bootstrap-defense-v0 scenario loader (this branch, M4 prep).
- **M4.1 amendment (2026-07-20)**: extended only `syncUpdate()` with the
  thread-less tile-change refresh described above. Verified by the determinism
  harness placing a copper wall in the east lane after wave 1 spawns, then comparing
  hashes across two fresh JVMs while daggers continue around the changed tile.

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
`syncUpdate()` drives the field synchronously on the sim thread. `ControlPathfinder`
still needs no patch (unused by wave AI and by our straight-steering agents).

When units/enemies arrive (M3+) and
pathfinding is actually consumed, a synchronous `syncUpdate()` — reflection or a
catalogued upstream patch — will be revisited then (see `docs/ENGINE_NOTES.md`
§5.5, §11.6).

Other engine gaps handled without upstream edits, via reflection into public
engine classes on the classpath (no `--add-opens` needed):

- `EntityGroup.lastId` (private static) reset to 0 per episode.
- `Time.globalTimeRaw` / `Time.globalTime` zeroed per episode (`setInternalTime`
  covers `timeRaw`/`time`; `globalTimeRaw` has no public setter).

## Not counted as upstream patches

- New files under `rl-server/`, `agent-core/`, `agent-plugin/`, `python/`,
  `docs/`, `scripts/`, `scenarios/`, `configs/`, and new top-level files
  (`AGENTS.md`, `CLAUDE.md`, `NOTICE.md`, `ENGINE_VERSION`, `Makefile`) are
  **additions**, not modifications of upstream files, and do not require an entry
  here.
- The `.gitignore` additions are appended to an upstream file but are purely
  additive ignore rules. Noted here for completeness; not a behavioural patch.

## Generated files

- `annotations/src/main/resources/classids.properties` may show as modified
  during a Gradle build — it is **generated**, not a hand edit. Do not commit
  incidental regenerations of it as part of scaffold commits.
