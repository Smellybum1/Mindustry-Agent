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

## M1 decision: pathfinder threads — reflection, not an upstream patch

The brief sanctioned a minimal upstream edit to force the two free-running
pathfinder threads (`Pathfinder`, `ControlPathfinder`) synchronous *if* they
could not be cleanly avoided. **No upstream edit was needed for M1.** The M1
scenario has no waves, no enemies, and no commanded units, so no flowfields are
ever created and nothing consumes pathfinding. `rl-server` stops both threads
immediately after world load by invoking their private `stop()` via reflection
(`RlServer.stopPathfinders()`), so they never run during an episode. This keeps
the checkout free of upstream modifications. When units/enemies arrive (M3+) and
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
