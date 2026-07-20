# agent-plugin

`agent-plugin` is the real-time, human-joinable adapter for Bootstrap Defense
v0. It is a normal Mindustry server plugin: the distribution jar contains
`plugin.json`, this module, the shared `agentcore` classes, and only the two
project-owned `mindustry.rl` adapters it needs. It deliberately does not bundle
upstream engine classes.

The demo uses the exact checked-in scenario and schematic JSON as training mode.
It spawns three Alpha units and runs the shared `TaskBoard`, low-level skill FSMs,
and `AnnouncementRenderer` on the vanilla simulation thread. The only pacing
difference is that the stock server advances in real time and keeps its normal
pathfinder threads. Its fallback policy builds a six-Duo expert defense, keeps
every available agent mining and delivering copper between waves, switches to
defense when enemies appear, then repairs, adds two Duos plus seven walls after
each of the first two waves, supplies all eight/ten active turrets, and resumes
mining.
A lost agent slot is rebound to a replacement Alpha at the core and reported in
the server log; tasks and controllers remain attached to the same stable slot.

## Commands

Both the server console and an ordinary client can use the agent controls:

- `/agents status`
- `/agents pause`
- `/agents resume`
- `/agents stop` — immediate emergency stop; clears mining, build plans,
  movement, firing, and active skills.

The server console also supports `agents start` when the plugin was loaded in
manual mode.

## Run safely

```bash
# Automated real-server acceptance probe. Does not open a network port.
bash scripts/demo-server.sh

# Full real-time three-wave survival probe. Also opens no network port.
DEMO_SURVIVAL=1 bash scripts/demo-server.sh

# Explicit human-join mode. This is the only path that opens the game socket.
DEMO_JOIN=1 bash scripts/demo-server.sh
```

Join `localhost:6567` with a stock v159.7 client. The policy waits until the
player types `/agents resume`; the scenario clock is paused too, so map loading
cannot hide the opening or let waves advance unattended. `DEMO_PORT=<port>` may
be used when 6567 is occupied.

Every run uses an isolated temporary server data directory under `runs/`; it
does not install into the user's real Mindustry mod folder. The stock ArcNet
provider binds the selected game port on available interfaces, so join mode is
for a trusted private LAN/loopback environment and must never be exposed through
port forwarding.
