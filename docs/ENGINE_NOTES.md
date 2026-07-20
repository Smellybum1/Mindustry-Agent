# Engine Notes — Pinned Mindustry Engine Source Inspection

**Purpose:** Foundation for building a custom `rl-server` module with an externally-controlled, deterministic, fixed-step simulation loop.

**Pinned engine:** Anuken/Mindustry tag `v159.7`, commit `c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c` (this checkout: `C:\Codex\Mindustry Agent`).
**Pinned Arc dependency:** `archash=208a754044` (`gradle.properties:29`; consumed by `build.gradle:5,12`). Arc source cited below was fetched from `https://raw.githubusercontent.com/Anuken/Arc/208a754044/...`. Arc is only present in this checkout as compiled jars under `~/.gradle/caches/modules-2/.../com.github.Anuken.Arc/*/208a754044/`; there are no `-sources` jars.

Every claim below is cited as `path:line`. Arc citations use the fetched file's line numbers, which match the tag `208a754044`.

> **TL;DR for the three headline questions**
> - **(a) Fixed step without patching upstream:** YES for the core loop and clock. We can drive Mindustry's real `Logic` at an explicit `1/60f` delta with zero wall-clock dependency by writing our own `Application` implementation (in `rl-server`) plus a `Graphics` subclass whose `getDeltaTime()` returns a constant. No edits to Arc or Mindustry core are required for the loop, clock, boot, reset, or entity update. The **only** area that may need a tiny upstream touch (or reflection) is forcing the two background **pathfinder threads** to run synchronously.
> - **(b) Main nondeterminism risks:** (1) the two free-running pathfinding threads (`Pathfinder`, `ControlPathfinder`) paced by wall clock; (2) the global `Mathf.rand` seeded from entropy at class-load (`Mathf.java:52`, `Rand.java:32-33`); (3) unordered entity-group iteration (swap-remove) making iteration order history-dependent; (4) a couple of unseeded per-instance `Rand`s (`PhysicsProcess`, `Pathfinder` non-wave mode using `hashCode()`).
> - **(c) Contradictions with the brief:** The brief's §7.2 says to set a `FixedStepGraphics` delta and "explicitly configure Arc `Time`". Verified: fixing the **graphics** delta is necessary and sufficient — `Time.delta` and `Time.time` derive from `Core.graphics.getDeltaTime()`, and `state.tick` reads graphics delta *directly* (not `Time.delta`), so a `Time.setDeltaProvider` override alone would NOT be enough; the graphics delta is the true single source. The brief's §7.4 reset list is broadly correct but `Logic.reset()` does NOT reset the static entity-id counter `EntityGroup.lastId`, nor reseed any RNG — both must be handled by us. AsyncCore (physics/avoidance) is already synchronized at step boundaries via a fork-join join (`AsyncCore.end()`), contrary to any assumption that all async systems free-run.

---

## 1. Server boot path

### 1.1 `ServerLauncher` (`server/src/mindustry/server/ServerLauncher.java`)

`main()` (`:25-39`):
- `Vars.platform = new Platform(){}` (`:28`) — anonymous default `Platform`.
- `Vars.net = new Net(platform.getNet())` (`:29`) — a `Net` object is constructed but **no socket is opened** (see §9).
- Installs a `Log.logger` (`:31-34`).
- `new HeadlessApplication(new ServerLauncher(), throwable -> CrashHandler.handle(...))` (`:35`) — this is the two-arg Arc constructor, which uses the **default render interval of `1/60f`** (`HeadlessApplication.java:26-28`) and **starts Arc's background main-loop thread immediately** (see §2).

`ServerLauncher` itself is the first `ApplicationListener`; its `init()` (`:42-83`) runs once on the Arc main-loop thread and performs the heavy boot:
- `Core.settings.setDataDirectory(...)`; `loadLocales=false`; `headless=true` (`:43-45`).
- `Vars.loadSettings()` then `Vars.init()` (`:47-48`). `Vars.init()` constructs the core singletons: `content = new ContentLoader()` (`Vars.java:352`), `world = new World()` (`:355`), `asyncCore = new AsyncCore()` (`:358`), `spawner`, `indexer`, `pathfinder`, `controlPath`, `fogControl` (`Vars.java:362-366`), and `state = new GameState()` (`:376`).
- Content pipeline: `content.createBaseContent()`, `mods.loadScripts()`, `content.createModContent()`, `content.init()` (`:53-56`), with a mod-content-error gate that `System.exit(1)`s on failure (`:58-70`).
- **Listener registration order** (`:74-78`), which is the exact per-tick `update()` order:
  1. `new ApplicationListener(){ public void update(){ asyncCore.begin(); }}` (`:74`) — submits async physics/avoidance jobs.
  2. `logic = new Logic()` (`:75`) — the entire simulation update (§3).
  3. `netServer = new NetServer()` (`:76`) — snapshot sync; a no-op per tick unless hosting (§9).
  4. `new ServerControl(args)` (`:77`) — console/command layer (§9, must NOT be reused).
  5. `new ApplicationListener(){ public void update(){ asyncCore.end(); }}` (`:78`) — joins async jobs.
- `mods.eachClass(Mod::init)` (`:80`); `Events.fire(new ServerLoadEvent())` (`:82`).

**Consequence for us:** the `asyncCore.begin()` / `asyncCore.end()` bracket wraps `Logic.update()`. Any listener whose `update()` runs between begin and end (Logic, NetServer, ServerControl) executes concurrently with the physics/avoidance worker threads, which are then joined at `end()`. We must preserve this begin/…/end bracket order in `rl-server` (see §5, §11).

### 1.2 What content/mods load
Base content and mod content are created and initialized once during `init()` (`ServerLauncher.java:53-56`). This is a one-time cost; episode resets do **not** reload content. `Fonts.loadContentIconsHeadless()` (`:51`) and `UI.loadColors()` (`:50`) are headless-safe stubs.

### 1.3 How the update loop is driven (stock)
It is driven by Arc's `HeadlessApplication.mainLoop()` background thread calling every listener's `update()` once per render interval (§2). This is exactly what `rl-server` replaces.

---

## 2. Arc headless loop and timing

### 2.1 `HeadlessApplication` main loop (`arc/backend/headless/HeadlessApplication.java`)
- Constructor assigns the Arc `Core.*` singletons: `Core.settings`, `Core.app=this`, `Core.files=new MockFiles()`, `Core.audio=new MockAudio()`, `Core.graphics = this.graphics = new MockGraphics()`, `Core.input=new MockInput()` (`:35-41`).
- `renderInterval` is nanoseconds: `renderIntervalSec>0 ? (long)(sec*1e9) : (sec<0 ? -1 : 0)` (`:42`). Default path uses `1/60f` (`:23,27`).
- `initialize()` (`:47-59`) spawns `mainLoopThread` (named `"HeadlessApplication"`) and starts it.
- `mainLoop()` (`:61-104`):
  - Calls `listener.init()` for all listeners once (`:62-66`).
  - Loop (`:70-94`): computes a wall-clock sleep from `Time.nanos()` to hit the target interval (`:71-79`, `Threads.sleep`), then per iteration:
    1. `runnables.run()` (`:81`) — drains `Core.app.post(...)` queue.
    2. `graphics.incrementFrameId()` (`:82`).
    3. `defaultUpdate()` (`:83`) — see 2.3.
    4. `for listener : listeners → listener.update()` (`:85-89`).
    5. `graphics.updateTime()` (`:90`) — recomputes delta from wall clock.
- `post(Runnable)` enqueues into `runnables` (`:132-134`); `exit()` posts `running=false` (`:137-139`).

**This is the exact structure we replicate synchronously**, minus the sleep and minus `updateTime()`.

### 2.2 `MockGraphics` delta (`arc/mock/MockGraphics.java`)
- `deltaTime` is a package-private field (`:14`); `getDeltaTime()` returns it (`:72-74`).
- `updateTime()` (`:151-162`) sets `deltaTime = (System.nanoTime() - lastTime)/1e9f` — **wall-clock derived**. This is the single wall-clock coupling for the whole simulation.
- Because `deltaTime` is package-private, an out-of-package subclass cannot write the field, but it **can override `getDeltaTime()` and `updateTime()`**, which is all we need.

### 2.3 `arc.util.Time` (`arc/util/Time.java`) and `Application.defaultUpdate`
- `Time.delta` (`:15`) default `1f`; `Time.time`, `Time.globalTime` (`:17`).
- Default delta provider: `deltaimpl = () -> Math.min(Core.graphics.getDeltaTime()*60f, 3f)` (`:26`) — reads graphics delta, **clamped to a max of 3 ticks/frame**.
- `Time.updateGlobal()` (`:62-72`): `globalTimeRaw += Core.graphics.getDeltaTime()*60f; delta = deltaimpl.get(); ...; globalTime=(float)globalTimeRaw`. Called by `Application.defaultUpdate()` (`arc/Application.java:30-33`) → runs **before** listener updates each frame.
- `Time.update()` (`:74-96`): `timeRaw += delta; time=(float)timeRaw; ...` and processes `Time.run(...)` delayed tasks (tick-based, deterministic). **Called by `Logic.update()`** (`Logic.java:536`), not by the app loop.
- `Time.setDeltaProvider(Floatp)` (`:111-114`) exists but is insufficient alone (see 2.5).
- `Time.nanos()`/`Time.millis()` (`:117-124`) wrap `System.nanoTime`/`currentTimeMillis` — used only by wall-clock consumers listed in §7.

### 2.4 What a fixed 1/60 delta produces
With `getDeltaTime()` pinned to `1f/60f`:
- `Logic.update()`: `delta=1/60` (`Logic.java:519`), `state.tick += delta*60f` → `state.tick += 1.0` exactly (`:520`). `state.tick` is a `double` (`GameState.java:21`), so `+1.0` per tick is exact with no drift.
- `Time.updateGlobal()`: `globalTimeRaw += (1/60)*60 = 1.0`; `delta = min((1/60)*60, 3) = 1.0` (`Time.java:63-64`).
- `Time.update()`: `timeRaw += 1.0` (`Time.java:75`).
All three clocks advance exactly one tick per engine update, deterministically, with **no wall-clock read**.

### 2.5 Why `Time.setDeltaProvider` alone is NOT enough (contradicts a naive reading of brief §7.2)
`Logic.update()` reads `Core.graphics.getDeltaTime()` **directly** for `state.tick` (`Logic.java:519-520`), and `Time.updateGlobal()` reads `Core.graphics.getDeltaTime()` **directly** for `globalTimeRaw` (`Time.java:63`). Overriding only the `Time` delta provider would leave `state.tick` and `globalTime` still wall-clock driven. **The graphics delta is the true single source of truth and must be overridden.** (Overriding graphics delta additionally makes the default `deltaimpl` produce the correct clamped `Time.delta`, so no `Time` override is needed at all.)

### 2.6 Can we get fixed step WITHOUT patching Arc/Mindustry? — YES
`arc.Application` (`arc/Application.java:8`) is an interface where almost everything is a `default` method; the only members we must implement are `getListeners()`, `getType()`, `getClipboardText()`, `setClipboardText()`, `post()`, `exit()` (`:11,36,91,93,117,124`). The `Core.*` fields are `public static` and freely assignable (`arc/Core.java:19-24`). Therefore `rl-server` can:
1. Implement its own `FixedStepApplication implements arc.Application`, replicating `HeadlessApplication`'s `Core.*` assignment block (`HeadlessApplication.java:35-41`) but substituting our graphics.
2. Provide `FixedStepGraphics extends arc.mock.MockGraphics` overriding `getDeltaTime(){ return 1f/60f; }` and `updateTime(){}` (no-op).
3. **Not** start a background thread. Instead expose `initOnce()` (calls each listener's `init()` once) and `stepOnce()` that mirrors the loop body: `runnables.run(); graphics.incrementFrameId(); defaultUpdate(); for(l:listeners) l.update();` — all on the caller's thread.
4. Set `mainLoopThread`/`getMainThread()` to the control thread so `Core.app.isOnMainThread()` (`Application.java:86-89`) returns true for the stepping thread (some engine code asserts this).

No source changes to Arc or Mindustry are required for any of the above.

---

## 3. Logic / update path (`core/src/mindustry/core/Logic.java`)

### 3.1 `Logic.update()` (`:494-613`) order of operations (when `state.isPlaying()` and not paused)
1. `PerfCounter.frame.*` (`:496-497`) — telemetry only (§7).
2. `Events.fire(Trigger.update)` (`:501`); `universe.updateGlobal()` (`:502`).
3. Settings autosave gate when not playing (`:504-507`).
4. `state.enemies = Groups.unit.count(...)` (`:513`).
5. `Events.fire(Trigger.beforeGameUpdate)` (`:517`).
6. `float delta = Core.graphics.getDeltaTime(); state.tick += delta*60f; state.updateId++` (`:519-521`).
7. `state.teams.updateTeamStats()` (`:522`); `MapPreviewLoader.checkPreviews()` (`:523`).
8. Fog update if `state.rules.fog` (`:525-527`); campaign sector/universe updates (`:529-535`).
9. `Time.update()` (`:536`).
10. `logicVars.update()` (`:538`) — world-processor logic variables.
11. Server-side (`!net.client() && !state.isEditor()`): `updateWeather()` (`:542`); per-team: `fillItems`, `BaseBuilderAI` if `buildAi` (`:555-558`), `RtsAI` if `rtsAi` (`:560-563`), prebuild-AI core unit spawns (`:566-577`).
12. `state.rules.objectives.update()` (`:581-583`).
13. Wave timer decrement (`:585-589`) and `runWave()` when `state.wavetime<=0` (`:591-593`).
14. Environment attributes recompute (`:596-598`).
15. `updateEntities()` (`:600`) — see 3.2.
16. `Events.fire(Trigger.afterGameUpdate)` (`:602`).
17. `if(runStateCheck) checkGameState()` (`:605-607`).

### 3.2 `updateEntities()` (`:463-492`)
Order: `Groups.updatePooling()`; `Groups.bullet.updatePhysics()`; `Groups.unit.updatePhysics()`; `Groups.all.update()` (`:467-470`); then `Groups.unit.update()` (`:474`); `Groups.powerGraph.update()` (`:478`); `Groups.build.update()` (`:482`); `Groups.bullet.update()` + `Groups.bullet.collide()` (`:486-488`). All iteration is over `EntityGroup` arrays in insertion/swap order (§10). `PerfCounter.*` calls are telemetry.

### 3.3 `state.tick` advance
`state.tick` is a `double` field (`GameState.java:21`) advanced only at `Logic.java:520`. With fixed delta it is an exact integer sequence.

### 3.4 `Logic.reset()` (`:299-313`) — what it clears / does NOT clear
Clears: `Groups.clear()` (`:300`); `Time.clear()` (`:301`, cancels pending `Time.run` tasks); fires `ResetEvent` (`:302`) — which triggers `AsyncCore` process reset (`AsyncCore.java:32-37`), `Pathfinder.stop()` (`Pathfinder.java:148`), `ControlPathfinder.stop()` (`ControlPathfinder.java:224`); replaces `world.tiles = new Tiles(0,0)` (`:303`); `state.data.unload()` (`:305`); recreates `state = new GameState()` → back to `State.menu` (`:308`); fires `StateChangeEvent` (`:310`); `Core.settings.manualSave()` (`:312`).

**Does NOT reset (must be handled by `rl-server`):**
- `EntityGroup.lastId` (`EntityGroup.java:19`) — the **static** monotonic entity-id counter is never reset here; it keeps climbing across episodes. Cross-episode hash equality requires resetting it (reflection or a controlled load).
- `Mathf.rand` seed (`Mathf.java:52`) — never reseeded (§6). Must reseed at reset.
- Per-instance `Rand`s inside `PhysicsProcess`/`Pathfinder` (§6).
- The static `Groups` singletons are cleared but `Time.globalTime`/`Time.time` are `Time.time` state — `Time.clear()` only clears the delayed-task list, not `timeRaw`/`globalTimeRaw`. `PlayEvent` sets `state.tick=0` (`:99`) but `Time.time` is not explicitly zeroed on reset; a fresh play does not reset `Time.time` internal accumulators. If hashing includes `Time.time`, zero it explicitly (`Time.setInternalTime(0)`).

### 3.5 `play()` (`:269-297`) and `runWave()` (`:319-325`)
`play()` sets `state.set(State.playing)` (`:270`), computes `wavetime` (`:272`), resets `state.stats` (`:273`), fires `PlayEvent` (`:274`, which zeroes `state.tick` at `:99` and shuffles weather using `Mathf.random` at `:92-96`), adds loadout items to each team core (`:277-289`), heals cores (`:292-296`). `runWave()` calls `spawner.spawnEnemies()` (`:320`), increments `state.wave`, resets `wavetime`, fires `WaveEvent`.

---

## 4. World / map loading and episode reset

### 4.1 Load entry points
- `World.loadMap(Map)` / `loadMap(Map, Rules)` (`World.java:340-392`) → `SaveIO.load(map.file, new FilterContext(map))` (`:352`). Headless validity check requires at least one core or throws `MapException` (`:383-388`).
- `SaveIO.load(...)` (`io/SaveIO.java:139-163`) reads the save/map and fires `SaveLoadEvent(context.isMap())` (`:173`).
- `World.loadGenerator(w,h,gen)` (`World.java:252`) for procedurally generated worlds; `loadSector(...)` (`:261-265`) for campaign.
- The world-load lifecycle fires `WorldLoadBeginEvent` (`World.java:210`) and `WorldLoadEvent` (`World.java:237`). `WorldLoadEvent` is what starts the pathfinder thread and (re)initializes async processes (`Pathfinder.java:145 start()` inside the `WorldLoadEvent` handler at `:118-146`; `AsyncCore.java:25-30`).

### 4.2 Minimal headless episode load + restart (no JVM restart)
The stock flow to start a match (mirrors what the server "host" command does): construct `Rules`, `world.loadMap(map, rules)` (fires world-load → pathfinder/async init), then `logic.play()` (sets `State.playing`, adds loadout, fires `PlayEvent`). To restart an episode without JVM restart: `logic.reset()` (§3.4) → back to `State.menu`, then load + play again. `reset()` already tears down pathfinder/async via `ResetEvent`, and the next `WorldLoadEvent` rebuilds them. `control.saves.*` and disk saving are client/campaign-only and guarded by `!headless` (e.g. `Logic.java:420-422`), so headless reset avoids disk work except `Core.settings.manualSave()` (`:312`) — which can be neutralized by disabling autosave/using a mock settings sink.

### 4.3 Rules, cores, units, `state.set`
- `Rules` is a plain data object on `state.rules` (`GameState.java:35`). Apply by assignment before load, or `Call.setRules(state.rules)` for networked propagation (not needed headlessly).
- Cores/loadout: cores come from the map's saved tiles; starting items are injected in `play()` (`:277-289`).
- `state.set(State state)` (`GameState.java:60-66`) fires `StateChangeEvent` and flips the private `state` enum (`paused|playing|menu`, `:119-121`). `isPlaying()`==`State.playing` (`:98-100`) is the gate that enables the whole `Logic.update()` body and `AsyncCore.begin/end`.

---

## 5. Asynchronous systems

### 5.1 `AsyncCore` — physics + avoidance (fork-join, ALREADY step-synchronized)
`core/src/mindustry/async/AsyncCore.java`. Holds `processes = [PhysicsProcess, AvoidanceProcess]` (`:14-17`). `begin()` (`:40-66`): when `state.isPlaying()`, calls each process's `begin()` on the main thread (builds snapshots), then submits each process's `process()` to a fixed thread pool sized `processes.size` (=2) of daemon `"AsyncLogic-Thread"`s (`:51-63`). `end()` (`:68-77`): `complete()` (`:79-91`) blocks on every `future.get()` (join), then calls each process's `end()` on the main thread (writes results back).
- **Determinism:** one future per process, no intra-process parallelism; joined every tick. Given identical inputs (unit set + iteration order), collision/avoidance output is deterministic. `PhysicsProcess.process()` (`PhysicsProcess.java:70-83`) rebuilds per-layer quadtrees (`:127-136`) and resolves collisions iterating `bodies`/`refs` in insertion order derived from `Groups.unit` iteration (`:41-62`). The one nondeterministic draw is `rand.random(360f)` for *exactly coincident* bodies (`PhysicsProcess.java:132,186-187`) — rare, but the `rand` is `new Rand()` (entropy-seeded) and never reseeded.
- **For `rl-server`:** keep the `asyncCore.begin()` … `asyncCore.end()` bracket around `Logic.update()` (register a begin-listener first and an end-listener last, exactly as `ServerLauncher.java:74,78`). Because it joins each tick, it is already deterministic at step boundaries. Optionally force it single-threaded by running `process()` inline (a small custom wrapper) to eliminate the thread pool entirely.

### 5.2 `Pathfinder` — enemy flowfield (FREE-RUNNING background thread; main nondeterminism source #1)
`core/src/mindustry/ai/Pathfinder.java`. A dedicated `"Pathfinder"` thread at `MIN_PRIORITY`, daemon, started on `WorldLoadEvent` (`:145,283-291`). `run()` (`:322-354`) loops forever: `queue.run()`, then for each flowfield `updateFrontier(data, maxUpdate)` with `maxUpdate = 8ms` wall-clock budget (`:26,340`), then `Thread.sleep(updateInterval)` where `updateInterval = 1000/updateFPS` (`:29,345`). It also refreshes on a `Time.millis()` interval (`:190-193`, `refreshIntervalMs=100` at `:111`).
- **Consumers:** ground wave/AI units via `AIController` — `pathfinder.getField(...).getNextTile(...)` (`AIController.java:154`); `BaseBuilderAI.java:97`; `UnitComp` solidity check `pathfinder.get(tileX,tileY)` (`UnitComp.java:165`, synchronous array read, deterministic).
- **Nondeterminism:** the flowfield weights a unit reads on tick T depend on how many 8ms-budgeted background iterations have completed by then — wall-clock dependent. `Flowfield` keeps `completeWeights`/`hasComplete`/`dirty` snapshots (`Pathfinder.java:617-625`), so reads are of whatever snapshot the thread last published.

### 5.3 `ControlPathfinder` — RTS/commanded-unit hierarchical pathfinding (FREE-RUNNING thread; risk #1 for OUR agents)
`core/src/mindustry/ai/ControlPathfinder.java`. Dedicated `"Control Pathfinder"` thread, `MIN_PRIORITY`, started on world load (`:230,392-395`); `run()` (`:1536-1620`) loops with `maxUpdate = 12ms` budget (`:82,1612`) and `Thread.sleep(updateInterval)` (`:85,1618`).
- **Consumers:** `CommandAI` (`ai/types/CommandAI.java:332`) and `LogicAI` (`ai/types/LogicAI.java:77`) call `controlPath.getPathPosition(...)`. **Our agent-controlled units use `CommandAI`, so this is directly on our path.**
- **Important mitigating detail:** `getPathPosition(...)` (`:1121-1181+`) first performs a **synchronous main-thread straight-line raycast** (`:1154-1165`); if the destination is reachable in a straight line it returns immediately and deterministically (`:1168-1172`) without touching the async field. The async hierarchical field is only consulted when obstacles block the ray. **On open maps / short moves, commanded movement is deterministic even with the thread running.** Nondeterminism only enters for obstacle navigation.

### 5.4 Other threads
- `Core.executor` — shared `Threads.executor("Main Executor", OS.cores)` pool (`arc/Core.java:32`); used for misc async (e.g. content/asset loading), not the per-tick sim path in headless training.
- `arc.util.Timer` — a global timer thread, only spun up if `Timer.schedule`/`Time.runTask` is actually called. In the sim path with net disabled these calls belong to net/client/campaign code (`NetServer.java:1012,1406`, `Net.java:194`, `Control.java`, `Saves.java`) and are **not** triggered during a headless, non-hosted training tick. `Time.run(...)` (used e.g. `Logic.gameOver` `:437`) is tick-based and deterministic, NOT Timer-based.
- `SoundControl` has its own audio thread (`audio/SoundControl.java:490-575`) but `SoundControl` is a `Control` submodule and is **not** registered by the server launcher, so it never runs headlessly.

### 5.5 Determinism verdict on async
- AsyncCore: deterministic at step boundaries (already joined). ✅ (modulo coincident-body `rand`).
- Pathfinder / ControlPathfinder: **nondeterministic as shipped** due to wall-clock pacing. To make deterministic we must run their update methods synchronously at tick boundaries with an unbounded budget so fields fully converge before consumption. Their update methods (`updateFrontier`, `updateFields`, `queue.run()`) are `private`; forcing synchronous execution therefore needs either (a) a tiny upstream patch exposing a `syncUpdate()` that the thread loop and our stepper both call, or (b) reflection, or (c) not starting the thread and driving the private methods reflectively. This is the one place where the "tiny isolated upstream patch" of Risk 1 in the brief is the cleanest option.

---

## 6. Randomness sources

| Source | Seeding | Deterministic as-is? | Affects sim state? |
|---|---|---|---|
| Global `Mathf.rand` (`arc/math/Mathf.java:52`) | `new Rand()` → `setSeed(new Random().nextLong())` (`arc/math/Rand.java:32-33`) — **entropy at class-load** | **No** | **Yes** — weather (`Logic.java:92-96,385-388`), wave spawn spread (`WaveSpawner.java:91,100`), misc |
| `WaveSpawner` spread | uses global `Mathf.range`/`Tmp.v1.rnd` (`WaveSpawner.java:91,100`) | Inherits `Mathf.rand` (no) | Yes — enemy spawn positions |
| `Pathfinder` internal `rand` (`Pathfinder.java:551`) | `setSeed(state.rules.waves ? state.wave : (int)(state.tick/5400)+hashCode())` (`:556`) | Wave mode: **yes**; non-wave: **no** (`Object.hashCode()`) | Yes (enemy path target selection) |
| `FlyingAI.rand` (`ai/types/FlyingAI.java:12,51`) | `setSeed(unit.type.id + (waves ? wave : unit.id))` | **Yes** | Yes (flyer targeting) |
| `PhysicsProcess.rand` (`async/PhysicsProcess.java:132,187`) | `new Rand()`, never reseeded | **No** (but only fires on coincident bodies) | Yes, rarely |
| `Fx.rand` (`content/Fx.java:25`) | reseeded per-effect id (`:168` etc.) | Yes | **No** — visual effects only |

**Root-seed derivation must:** (1) at each reset, `Mathf.rand.setSeed(deriveMapWeatherSeed(rootSeed))` — this is the dominant lever, covering weather + wave spread; (2) ensure `state.rules.waves=true` so `Pathfinder`/`FlyingAI` seed from `state.wave` (deterministic) rather than `hashCode()`/entropy; (3) optionally reseed `PhysicsProcess.rand` (reflection) if coincident-body determinism is required; (4) prefer scenarios/rules that avoid the non-wave `hashCode()` branch in `Pathfinder`. `Rand` itself is a deterministic xorshift128+ (`Rand.java:15`), so identical seeds → identical streams.

---

## 7. Wall-clock dependencies (grep of `core/`, `server/`)

`Time.time` / `Time.globalTime` are **tick-based** (advanced by our fixed delta) and are therefore deterministic, NOT wall-clock — the many `Time.time`/`Time.globalTime` uses in bullets/abilities/buildings (e.g. `BuildingComp.java:489-506`, `entities/bullet/*`) are safe. The true wall-clock calls are `System.nanoTime`/`System.currentTimeMillis` via `Time.nanos()`/`Time.millis()`:

| Location | Call | Affects sim? |
|---|---|---|
| `ai/Pathfinder.java:26,190,392,477,499` | `Time.millis/nanos` for update budget + refresh timing | **Yes** (nondeterminism vector, §5.2) |
| `ai/ControlPathfinder.java:82,903,1537,1562` | same, RTS pathfinding | **Yes** (§5.3) |
| `core/PerfCounter.java:56,78,97,108` | perf timing | No — telemetry only |
| `core/NetServer.java` (multiple), `NetClient.java`, `net/*` | connection/snapshot timestamps | No if net disabled (§9) |
| `audio/SoundControl.java` | audio scheduling | No — not loaded headlessly |
| `core/Renderer.java:612`, `ClientLauncher.java` | screenshots / client frame pacing | No — client only |
| `entities/comp/PlayerComp.java:92`, `PuddleComp.java:42` | `Time.millis`/`Time.time` init timestamps | `PuddleComp` uses `Time.time` (deterministic); `PlayerComp:92` is a preview timestamp (client) |

**Net wall-clock exposure in the deterministic training path = the two pathfinder threads only.** Everything else is telemetry, client, or net (disabled).

---

## 8. Unit control APIs (server-side, no network player)

> Note: `mindustry.gen.*` classes (`Unit`, `Call`, `Groups`, concrete unit classes like `UnitWaterMove`) are **code-generated** by the annotation processor into `core/build/generated/source/kapt/main/mindustry/gen/`, NOT in `core/src`. Component logic lives in `core/src/mindustry/entities/comp/*Comp.java`; generated citations below reference the `core/build/...` tree produced by a build.

### 8.1 Spawning a team unit server-side (no net)
- `UnitType.spawn` overloads all funnel into `spawn(Team, float x, float y, float rotation, Cons<Unit> cons)` (`core/src/mindustry/type/UnitType.java:573`), which does `create(team)` → set pos/rotation → `unit.add()` → optional consumer (`:581-585`). Convenience forms: `spawn(Team,x,y,rotation)` `:607`, `spawn(Team,x,y)` `:611`, `spawn(x,y)` `:615` (uses `state.rules.defaultTeam`), `spawn(Team,Position)` `:619`, `spawn(Position)` `:623`, `spawn(Position,Team)` `:627`.
- `UnitType.create(Team)` (`:554`) builds the unit via `constructor.get()`, `setType(this)`, assigns the default controller, heals.
- `unit.add()` — the source `UnitComp.add()` (`entities/comp/UnitComp.java:592`) only does team bookkeeping / unit-cap; the actual **group registration is generated** (annotation processor `annotations/src/main/java/mindustry/annotations/entity/EntityProcess.java:493-508` emits `index__<group> = Groups.<group>.addIndex(this)`). Result (e.g. `core/build/.../gen/UnitWaterMove.java:1129-1149`): registers into `Groups.unit`, `Groups.sync`, `Groups.draw`; idempotent via an `added` flag. `Groups.unit` is mapping-enabled, so `Groups.unit.getByID(id)` works.
- `unit.id` = `EntityGroup.nextId()` assigned at **construction** (`gen/Unit.java:140`; `EntityGroup.java:36-39`), monotonic per session (see §10 for cross-episode caveat).
- **Canonical server-side spawn idiom** (from the engine itself, `Logic.java:570-574`): `Unit u = type.spawn(core, team); u.flag=...; u.add(); Units.notifyUnitSpawn(u); Fx.spawn.at(u);` — fully net-free.

### 8.2 Commanding units — `CommandAI` (`core/src/mindustry/ai/types/CommandAI.java`)
All fields/methods are directly settable server-side; no networking involved:
- Set command type: `command(UnitCommand)` (`:56-63`, validated against `unit.type.commands`).
- Move to position: `commandPosition(Vec2)` (`:557-565`) → `commandPosition(pos, stopWhenInRange)` (`:567-580`); sets `targetPos`/`lastTargetPos`, clears `attackTarget`.
- Attack/move to entity: `commandTarget(Teamc)` (`:582-588`) → `commandTarget(Teamc, stopAtTarget)` (`:590-593`); sets `attackTarget`.
- Queue waypoints: `commandQueue(Position)` (`:493-503`), cap `maxCommandQueueSize=50` (`:19`), field `Seq<Position> commandQueue` (`:24`).
- Clear: `clearCommands()` (`:177-181`). Public state: `targetPos` (`:25`), `attackTarget` (`:26`), `command` (`:43`); `hasCommand()` (`:549`).
- `updateUnit()` (`:116`) drives movement each tick via `defaultBehavior()` (`:198`) → `controlPath.getPathPosition(...)` (`:332`, see §5.3 determinism note).
- **Getting a unit onto `CommandAI`:** it is the default controller for RTS-commandable units — `UnitType.controller = u -> !playerControllable || (team.isAI() && !team.rules().rtsAi) ? aiController.get() : new CommandAI()` (`UnitType.java:281`). To force it: `unit.controller(new CommandAI())` (generated setter, `gen/UnitWaterMove.java:1369-1373`, also back-links `controller.unit(this)`), then cast `unit.controller()` to `CommandAI`.

`UnitCommand` (`core/src/mindustry/ai/UnitCommand.java`) is a `MappableContent` (`:64-67`) whose static instances are built in `loadAll()` (`:74-117`): `moveCommand`, `repairCommand`, `rebuildCommand`, `assistCommand`, `mineCommand`, `enterPayloadCommand`, `loadUnitsCommand`, `loadBlocksCommand`, `unloadPayloadCommand`, `loopPayloadCommand`. Commands with a sub-controller (`Func<Unit,AIController>` at `:22`, e.g. `mineCommand`→`MinerAI`, `rebuildCommand`→`BuilderAI`) cause `CommandAI` to delegate `updateUnit()` to `commandController` (`:146-156`).

### 8.3 `Call.*` server-safety (`core/build/.../gen/Call.java`)
**Dispatch rule:** every `@Remote` body runs the local handler under `if(net.server() || !net.active())` and sends a packet only under `if(net.server())`. With nothing hosted, `net.active()==false` ⇒ local handler runs directly, **no packet is sent**. So `Call.*` is safe headlessly — but many methods still need a `Player`:

| Call method | Cite | Needs Player? | Notes |
|---|---|---|---|
| `beginPlace(Unit, Block, Team, x, y, rot, config)` | `Call.java:113-129` | No (takes Unit) | `Build.beginPlace`; used by `BuilderComp:173` |
| `beginBreak(Unit, Team, x, y)` | `Call.java:99-111` | No | used by `BuilderComp:191` |
| `transferItemTo(Unit, Item, amount, x, y, Building)` | `Call.java:2324` | No | used by mining `MinerComp:81,106` |
| payload calls (`pickedUnitPayload`, `pickedBuildPayload`, `payloadDropped`, `unitEnteredPayload`) | `CommandAI.java:186,206,221,224,237,431` | No | Unit-based |
| `commandUnits(Player, int[] unitIds, Building, Unit, Vec2, queue, finalBatch)` | `Call.java:400-418` | **Yes** | `InputHandler.commandUnits` early-returns on null player, filters `unit.team==player.team()` (`InputHandler.java:309-331`); admin `allowAction` check is `net.server()`-guarded |
| `commandBuilding(Player, int[], Vec2)` | `Call.java:372-385` | **Yes** | `InputHandler.java:469-493` |
| `unitControl(Player, Unit)` | `Call.java:2412-2422` | **Yes** | player possession (`InputHandler.java:771`) |
| `unitClear(Player)` | `Call.java:2389-2400` | **Yes** | respawn/dock (`InputHandler.java:820`) |

There is **no** `Call.requestBuild`/`Call.buildBlock` in this version. **Recommendation:** for a no-network-player layer, bypass the Player-scoped Call methods (they no-op on null player) and instead manipulate `CommandAI` (§8.2), the `plans` queue (§8.4), and `mineTile` (§8.5) directly; use the Unit-scoped `Call.*` (`beginPlace`, `beginBreak`, `transferItemTo`, payload) freely.

### 8.4 Build plans — `BuilderComp` (`core/src/mindustry/entities/comp/BuilderComp.java`)
- Queue: `Queue<BuildPlan> plans` (`:32`, generated `plans()` accessor). Add via `addBuild(BuildPlan)` (`:272-273`, tail) or `addBuild(BuildPlan, boolean tail)` (`:277-299`, de-dupes by x/y, seeds from existing `ConstructBuild`); gated by `canBuild()` (`:40-42`, requires `type.buildSpeed>0`). Helpers: `clearBuilding()` `:267`, `removeBuild(x,y,breaking)` `:253`, `buildPlan()` head `:313`.
- Execution: `update()` (`:44-47`) → `updateBuildLogic()` (`:76-223`) validates plans, picks nearest reachable, calls `Call.beginPlace`/`Call.beginBreak` (`:173,191`) then `construct`/`deconstruct` (`:211-218`). Only non-headless bits are sound loops guarded by `if(!headless)` (`:79,157`). **The `plans` queue is processed autonomously each tick regardless of controller.**
- `BuildPlan` (`core/src/mindustry/entities/units/BuildPlan.java`): fields `int x,y,rotation`, `@Nullable Block block` (null ⇒ breaking), `boolean breaking`, `Object config` (`:16-33`). Constructors: place `(x,y,rotation,block)` `:36`, place-with-config `:45`, break `(x,y)` `:55`. **Coordinates are tile coords.** Server-side: `unit.addBuild(new BuildPlan(tx,ty,rot,block))`.

### 8.5 Mining — `MinerComp` (`core/src/mindustry/entities/comp/MinerComp.java`)
- Single control field: `@Nullable Tile mineTile` (`:24`), directly settable via generated `unit.mineTile(tile)`. `mining()` = `mineTile != null && !activelyBuilding()` (`:35-37`).
- `update()` (`:71-125`) validates with `validMine(mineTile)` (`:53-61`, range `type.mineRange`, drop mineable per `type.mineTier`), accumulates `mineTimer`, transfers to core via `Call.transferItemTo`/`InputHandler.transferItemToUnit` (`:81,106,111`); auto-clears invalid target (`:88-90`). Only non-headless bit is a sound loop `if(!headless)` (`:121-123`). Bypass `MinerAI` by setting `unit.mineTile(tile)` directly.

---

## 9. Networking (headless)

- `Net.server()` = `server && active`, `client()` = `!server && active`, `active()` = `active` (`net/Net.java:389,396-397,403`) — all start false. `Vars.net = new Net(...)` is constructed at boot (`ServerLauncher.java:29`) but **opens nothing**. The **only** call that opens a listening socket is `Net.host(int)` (`net/Net.java:189-195`, sets `active=true, server=true`); client sockets come only from `connect(...)` (`:168`). `host` is invoked exclusively from `NetServer.openServer()` (`NetServer.java:1046-1057`, `:1048 net.host(Config.port.num())`), reached via the `ServerControl` "host" command. **If `rl-server` never calls `net.host(...)`/`openServer()`, no port opens and `net.active()` stays false** → all `Call.*` run locally with no packets (§8.3).
- `NetServer` constructor (`NetServer.java:138`) only **registers packet listeners** (`:140-158`) — opens nothing; harmless to construct. `NetServer.update()` (`:1008-1037`) guards all real work on `net.server()` (`:1009,1019`), so it is a per-tick no-op when not hosting. Keep `netServer` present because `Logic.update()` references `netServer.admins` (`:505`) and `netServer.isWaitingForPlayers()` (`:608`).
- **What `ServerControl` (`server/src/mindustry/server/ServerControl.java`, 1469 lines) does that we must NOT reuse:**
  - **stdin console-reader thread** `serverInput` (`:83-104`), started as daemon `"Server Controls"` on `ServerLoadEvent` (`:376-384`, `new Thread(serverInput,...).start()` at `:378-380`).
  - **Command TCP socket** `toggleSocket(boolean)` (`:1428-1468`): `new ServerSocket()` + `bind` (`:1432-1433`), accept loop (`:1434-1443`), enabled at setup via `toggleSocket(Config.socketInput.bool())` (`:374`).
  - **Hosting**: the `host` command → `netServer.openServer()` → `net.host(...)`; `gameOverListener` → `net.closeServer()` (`:131`).
  - **Arc `Timer` tasks**: autosave `Timer.schedule(...)` ~60s (`:356-359`), round-reload timer `Timer.schedule` (`:1400`, task at `:1401-1406`).
  A training launcher must **not** construct/`setup()` `ServerControl` at all; register only our own control listener. (Constructing `Net`/`NetServer` is fine; just never host, never open the command socket, never start the stdin thread.)
- **Threading rule (brief §23.6) is enforceable here:** with net disabled there is no inbound net thread; the control transport (Python I/O) must only *enqueue* requests, and only the single stepping thread reads/writes game state.

---

## 10. State hashing inputs

- **Entity collections:** `Groups.unit`, `Groups.build`, `Groups.bullet`, `Groups.all`, `Groups.powerGraph`, `Groups.weather` are `EntityGroup`s backed by an **unordered** `Seq` (`new Seq<>(false, 32, type)`, `EntityGroup.java:51`). `iterator()`/`each()` iterate `array` in slot order (`:149-153,341-343`).
- **Iteration order is NOT content-stable:** `remove()` on an unordered `Seq` is **swap-with-last** (`EntityGroup.java:262-284`; `removeIndex` explicitly swaps head into the vacated slot `:298-305`; confirmed by Arc `Seq.remove(int)` taking the `else`/non-ordered swap branch, `arc/struct/Seq.java:689-708`). So slot order depends on the history of removals (deaths). Given the **same seed + same action trace**, the history is identical and iteration order is reproducible → **fine for replay/regression hashing**. For a **canonical content hash independent of history**, sort entities by `id()` (or by `(type,x,y,id)`) before hashing.
- **Entity ids:** `EntityGroup.lastId` is `static` and monotonic (`:19,36-39`), bumped on load via `checkNextId` (`io/SaveVersion.java:500`). It is **not reset** by `Logic.reset()`, so identical scenarios across episodes assign different absolute ids unless we reset it. Hash schemes should therefore either reset `lastId` per episode (reflection) or hash id-relative/sorted structure rather than absolute ids.
- **Buildings:** live on tiles (`Tile.build`) and in `Groups.build`; iterate tiles in row-major order via `world.tiles` for a stable spatial hash. `Teams`/`TeamData` hold `cores`, `plans` (`BlockPlan` queue) — deterministic order.
- **Recommended canonical hash inputs** (matches brief §7.6): `state.tick`, `state.wave`, ruleset id; per core: items + health; per building (sorted by tile index): type, team, health, config, inventory; per unit (sorted by id): type, team, quantized pos/vel, health, inventory, command, controller/agent; objectives; task-board/leases (our layer); reward high-water marks (our layer). Quantize floats explicitly (document precision, e.g. positions to 1e-3 tiles) and never hash `Fx`/render/`Time.millis` state.

---

## 11. Recommended `rl-server` design

### 11.1 `FixedStepGraphics extends arc.mock.MockGraphics`
```java
public final class FixedStepGraphics extends MockGraphics{
    private float delta = 1f/60f;
    public void setDeltaSeconds(float s){ this.delta = s; }
    @Override public float getDeltaTime(){ return delta; }
    @Override public void updateTime(){ /* no-op: no wall clock */ }
    // getFrameId() still works via incrementFrameId()
}
```
Rationale: overriding `getDeltaTime()` is the single lever that makes `state.tick`, `Time.delta`, `Time.time`, and `Time.globalTime` all advance exactly one tick per update (§2.4-2.5). No Arc patch needed.

### 11.2 `FixedStepApplication implements arc.Application`
Reuse the `Core.*` assignment block from `HeadlessApplication` (`HeadlessApplication.java:35-41`) but with our graphics; do NOT start a background thread.
```java
final Seq<ApplicationListener> listeners = new Seq<>();
final TaskQueue runnables = new TaskQueue();
FixedStepGraphics graphics;
Thread stepThread; // the control/stepping thread; set for isOnMainThread()

// constructor: Core.settings/app/files/audio/graphics/input = ... (mirror :35-41)

void initOnce(){ synchronized(listeners){ for(var l:listeners) l.init(); } }

void stepOnce(){
    runnables.run();                 // drain Core.app.post(...)  (HeadlessApplication.java:81)
    graphics.incrementFrameId();     // (:82)
    defaultUpdate();                 // Core.settings.autosave + Time.updateGlobal (Application.java:30-33)
    synchronized(listeners){ for(var l:listeners) l.update(); }  // (:85-89)
    // NOTE: intentionally NO graphics.updateTime()  (removes the only wall-clock read)
}
@Override public void post(Runnable r){ runnables.post(r); }
@Override public Seq<ApplicationListener> getListeners(){ return listeners; }
@Override public ApplicationType getType(){ return ApplicationType.headless; }
@Override public Thread getMainThread(){ return stepThread; }
// getClipboardText/setClipboardText/exit trivial
```

### 11.3 Boot (once per process)
Mirror `ServerLauncher.init()` (`ServerLauncher.java:42-82`) minus `ServerControl`:
`Core.settings.setDataDirectory(...)`; `headless=true`; `Vars.loadSettings()`; `Vars.init()`; content pipeline (`createBaseContent → loadScripts → createModContent → init`); then register listeners **in this exact order** (mirrors `:74-78`):
1. `begin` listener → `asyncCore.begin()`
2. `logic = new Logic()`
3. `netServer = new NetServer()` (kept for `Logic`'s references; never `net.host`)
4. **our `RlControlListener`** (replaces `ServerControl`) — reads queued actions, but performs no stdin/Timer/host work
5. `end` listener → `asyncCore.end()`

Then `Events.fire(new ServerLoadEvent())`. `initOnce()`.

### 11.4 Reset (episode restart, no JVM restart)
```
logic.reset();                          // Groups/Time/world/state teardown (Logic.java:299-313)
resetEntityIdCounter();                 // reflection: EntityGroup.lastId = base  (NOT done by reset())
Mathf.rand.setSeed(deriveSeed(root));   // (Mathf.java:52) — dominant RNG lever
Time.setInternalTime(0);                // zero Time.time if hashed
state.rules = buildRules(scenario);     // waves=true so Pathfinder/FlyingAI seed deterministically
world.loadMap(scenarioMap, state.rules);// fires WorldLoad* → pathfinder/async re-init
logic.play();                           // State.playing, loadout, PlayEvent (tick=0)
// reset OUR layer: task board, leases, agent FSMs, policy state, reward high-water marks, pending actions
spawnAgentUnits(); applyInitialResources();
for(i in 0..warmupTicks) stepOnce();    // advance required init ticks
captureFirstObservationAndHash();
```
Target < 250 ms (brief Gate 2); cache immutable scenario/map bytes in memory to avoid disk re-read.

### 11.5 Step exactly N ticks
```
validateEpisodeAndExpectedTick(req);
actionApplier.apply(req.actions);       // enqueue via Core.app.post OR apply directly on step thread
for(int i=0;i<req.ticks;i++){
    fixedGraphics.setDeltaSeconds(1f/60f);
    stepOnce();                         // asyncCore.begin→Logic→...→asyncCore.end all inside
    syncPathfindersIfDeterministicMode();// force flowfield/control-path convergence (see 11.6)
}
StepResult r = observationService.capture();  // read state ONLY on this thread
controlChannel.reply(r);
```
Because `asyncCore.begin/end` are listeners 1 and 5, each `stepOnce()` already forks and joins physics/avoidance within the tick — no extra sync needed for AsyncCore.

### 11.6 Determinism mode — pathfinders
Preferred: a minimal isolated upstream patch adding `Pathfinder.syncUpdate()` / `ControlPathfinder.syncUpdate()` that runs `queue.run()` + full frontier/field convergence with **no wall-clock budget** and **not** starting the background thread when a `deterministic` flag is set; call these from `syncPathfindersIfDeterministicMode()`. Fallback: reflection into the private update methods. Document this as the single sanctioned upstream edit (brief Risk 1 / Risk 3).

### 11.7 Threading rules (brief §23.6, enforce as invariant)
- Exactly one thread (`stepThread`) ever reads or mutates game state, for both action application and observation capture.
- The Python/control transport thread may only parse and enqueue `ControlRequest`s; it must hand off via a queue consumed at the top of `stepOnce()` (`runnables.run()`) or a request channel drained by the step thread.
- Never call `net.host(...)`; never construct `ServerControl`; never start `SoundControl`/`Renderer`/client modules.
- The AsyncCore worker pool and (patched) synchronous pathfinders are the only permitted additional compute, both fully joined before observation capture.

---

## 12. Risks / unknowns (not fully verified in this pass)

1. **Forcing pathfinders synchronous** — the exact private methods (`Pathfinder.updateFrontier`, `updateTargets`, `queue`; `ControlPathfinder.updateFields`, `queue`, `unitRequests`) and whether a clean `syncUpdate()` can fully converge fields within one tick without the background thread has NOT been implemented/tested here. Needs a spike (brief Milestone 1 / Risk 3). This is the single biggest open determinism item.
2. **`EntityGroup.lastId` reset** — reset requires reflection (private static). Whether the generated `mindustry.gen.Groups.clear()` (generated at build; source not in `core/src`) also touches id state was not confirmed (the generated `Groups` class is not present in this source checkout; it is produced by annotation processing into `core/build/`).
3. **`Time.time` at reset** — `Logic.reset()` does not zero `Time`'s internal `timeRaw`/`globalTimeRaw`; `PlayEvent` zeroes `state.tick` but not `Time.time`. If the hash or any gameplay logic depends on absolute `Time.time` across episodes, add an explicit `Time.setInternalTime(0)` (verified the setter exists, `Time.java:102-105`) — but note `globalTimeRaw` has no public setter, so `Time.globalTime` continuity across resets is unverified and may need reflection if it must be zeroed.
4. **Coincident-body / non-wave `hashCode()` RNG** — `PhysicsProcess.rand` and the non-wave `Pathfinder` seed (`Pathfinder.java:556`) are entropy/identity seeded; full determinism requires avoiding those branches (use waves) or reflection to reseed. Impact assumed low but unquantified.
5. **Floating-point reduction order** — with the async pool sized 2 and one future per process there is no intra-process FP-order variance, but this was reasoned from structure, not measured across JITs/CPUs. The 10,000-tick golden replay (brief Gate 1) is the real test.
6. **Mods** — content/mod init happens once at boot; mod code could register `Timer`/thread work or its own RNG. Assumes a no-mod or vetted-mod training config (brief Risk 5/11).
7. **`Groups.updatePooling()` / entity pooling** — pooled entity reuse order after deaths was not deeply audited for hash stability; the sort-by-id canonical hash (§10) is the mitigation but pooling-driven field residue is unverified.
8. **`universe.update()` / campaign** — verified these are gated by `state.isCampaign()` (`Logic.java:529-535`); a non-campaign custom-map training scenario avoids them. Not exercised here.

---

*End of engine notes. All non-Arc citations are against this checkout (v159.7). Arc citations are against `Anuken/Arc@208a754044`. No engine source files were modified.*
