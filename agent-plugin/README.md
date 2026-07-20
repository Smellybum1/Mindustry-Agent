# agent-plugin

**Status: stub (roadmap M6/M10). Not yet a loadable Mindustry plugin.**

This module is the **real-time demonstration adapter**. In *training mode* the
engine is driven headless and externally stepped by `rl-server`. In *human
demonstration mode* the same agent behaviours must run inside an ordinary
Mindustry dedicated server at real-time pacing so a human can join and cooperate.

`agent-plugin` is that bridge. Its eventual responsibilities (brief §6.2):

- Load into an ordinary dedicated server as a Mindustry server plugin.
- Spawn or register server-controlled agent units.
- Connect to a policy process, or use an in-process scripted fallback.
- **Reuse `agent-core`** for tasks, skills, coordination, and announcements — the
  demo path must not fork behaviour from the training path (ADR-0006, brief
  §7.3). Training and demo share the same task board, skills, observations,
  action schema, and announcement templates.
- Surface announcements through team chat, labels, pings, or commands.
- Expose human controls: pause, stop, goal assignment, status.
- Enforce communication rate limits and honour human build-zone/resource
  overrides (human priority, brief §20.2).

Mindustry's official plugin model is server-side; ordinary clients should not
need a client mod for the first demonstration.

## Why a stub now

The vertical slice is proven in headless training mode first (M1–M6). The demo
server is only wired once the scripted team and scenario exist, so that the demo
genuinely shares `agent-core` rather than reimplementing it. The current
placeholder class exists solely to keep the module compiling and its dependency
edges (`:core`, `:agent-core`) honest.
