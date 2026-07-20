"""A tiny fake rl-server that speaks the length-prefixed JSON protocol.

Used by the M2 unit tests so the supervisor / env client can be exercised without
booting a real ~12 s JVM. It mirrors the wire contract of ``mindustry.rl`` closely
enough for the pool machinery (port + READY parsing, handshake verification,
reset/step/health/close, crash detection) but runs no engine.

Run as a subprocess::

    python fake_server.py --port 47810 [--commit <hash>] [--agents 2]
                          [--crash-after-steps N] [--hang-after-steps N]
                          [--no-ready] [--bad-commit]

Behaviour knobs (for failure-path tests):

* ``--no-ready``     : never print the READY line (startup-failure detection).
* ``--bad-commit``   : report a wrong engine_commit (handshake verification).
* ``--crash-after-steps N`` : ``os._exit`` after N steps (crash → replacement).
* ``--hang-after-steps N``  : stop responding after N steps (timeout → replace).

Determinism: reset hash is a stable function of the seed; step hash is a stable
function of ``(seed, tick)`` so repeated same-seed resets match (stress test).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import socket
import sys
import time
from pathlib import Path

# Make the src-layout package importable when run as a bare script subprocess.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from mindustry_agents import ENGINE_COMMIT  # noqa: E402
from mindustry_agents import protocol as P  # noqa: E402

ENGINE_TAG = "v159.7"
ARC_VERSION = "208a754044"


def _hash(*parts: object) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(repr(part).encode("utf-8"))
    return h.hexdigest()


def _world_obs(tick: int, seed: int) -> dict:
    return {
        "tick": tick,
        "wave": 1,
        "copper": 100,
        "lead": 0,
        "unit_count": 0,
        "building_count": 1,
        "core_health": 1100,
        "done": False,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--commit", default=ENGINE_COMMIT)
    ap.add_argument("--agents", type=int, default=2)
    ap.add_argument("--crash-after-steps", type=int, default=-1)
    ap.add_argument("--hang-after-steps", type=int, default=-1)
    ap.add_argument("--no-ready", action="store_true")
    ap.add_argument("--bad-commit", action="store_true")
    args = ap.parse_args(argv)

    commit = "deadbeef" * 5 if args.bad_commit else args.commit

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", args.port))
    srv.listen(1)

    # stderr line so log capture has something to show in diagnostics.
    print(f"[fake] listening on 127.0.0.1:{args.port}", file=sys.stderr, flush=True)
    if not args.no_ready:
        print(f"READY {args.port}", flush=True)
    else:
        # Simulate a hung startup: accept nothing, just idle a while.
        time.sleep(30)
        return 0

    conn, _ = srv.accept()
    recv = conn.recv
    seed = 0
    tick = 0
    steps = 0
    episode = "fake-ep-0"

    try:
        while True:
            try:
                msg = P.read_message(recv)
            except P.ProtocolError:
                break  # peer closed

            if isinstance(msg, P.HandshakeRequest):
                conn.sendall(
                    P.encode(
                        P.HandshakeResponse(
                            protocol_version=P.PROTOCOL_VERSION,
                            engine_version=ENGINE_TAG,
                            engine_commit=commit,
                            arc_version=ARC_VERSION,
                            process_id=os.getpid(),
                        )
                    )
                )
            elif isinstance(msg, P.ResetRequest):
                seed = msg.root_seed
                tick = 0
                steps = 0
                episode = f"fake-ep-{seed}"
                n = args.agents
                conn.sendall(
                    P.encode(
                        P.ResetResponse(
                            request_id=msg.request_id,
                            episode_id=episode,
                            tick=0,
                            initial_observations=[_world_obs(0, seed) for _ in range(n)],
                            action_masks=[{} for _ in range(n)],
                            state_hash=_hash("reset", seed),
                            metadata={"scenario": msg.scenario_id, "fake": True},
                        )
                    )
                )
            elif isinstance(msg, P.StepRequest):
                prev = tick
                tick += msg.ticks_to_advance
                steps += 1
                n = args.agents
                conn.sendall(
                    P.encode(
                        P.StepResponse(
                            request_id=msg.request_id,
                            episode_id=episode,
                            previous_tick=prev,
                            tick=tick,
                            observations=[_world_obs(tick, seed) for _ in range(n)],
                            action_masks=[{} for _ in range(n)],
                            team_state={"team": "sharded", "cores": 1},
                            reward_breakdowns=[{} for _ in range(n)],
                            terminations=[False] * n,
                            truncations=[False] * n,
                            state_hash=_hash("step", seed, tick),
                            timing={
                                "engine_ms": 0.5,
                                "observation_ms": 0.05,
                                "serialization_ms": 0.01,
                                "io_ms": 0.0,
                            },
                        )
                    )
                )
                if args.crash_after_steps >= 0 and steps >= args.crash_after_steps:
                    os._exit(42)  # hard crash, no graceful close
                if args.hang_after_steps >= 0 and steps >= args.hang_after_steps:
                    time.sleep(3600)  # unresponsive; client must time out
            elif isinstance(msg, P.HealthRequest):
                conn.sendall(
                    P.encode(
                        P.HealthResponse(
                            request_id=msg.request_id,
                            ok=True,
                            uptime_ticks=tick,
                            episode_id=episode,
                        )
                    )
                )
            elif isinstance(msg, P.CloseRequest):
                conn.sendall(
                    P.encode(P.HealthResponse(request_id=msg.request_id, ok=True))
                )
                break
            else:
                conn.sendall(
                    P.encode(
                        P.ErrorResponse(
                            request_id=getattr(msg, "request_id", 0),
                            code="unknown_type",
                            message=f"unhandled {type(msg).__name__}",
                        )
                    )
                )
    finally:
        try:
            conn.close()
        except OSError:
            pass
        srv.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
