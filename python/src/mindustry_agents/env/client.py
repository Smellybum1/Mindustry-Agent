"""Synchronous, framework-neutral env client wrapping one JVM connection.

:class:`EnvClient` is a thin, stateful convenience layer over a single
length-prefixed JSON control connection (``docs/PROTOCOL.md``). It owns the
per-connection episode/tick bookkeeping that the protocol requires — the active
``episode_id`` and the ``expected_tick`` that every :class:`StepRequest` must
carry — and returns Gym/PettingZoo-flavoured tuples instead of raw dataclasses.

It deliberately does **not** own a process: it is constructed from a
:class:`mindustry_agents.process.launcher.Connection`, so it is trivial to point
at either a real JVM or the fake test server. Standard-library only (ADR-0007);
no RL framework import.

Honesty note (M1 engine): the engine emits *world-level* observations, one copy
per agent slot, and there are no per-agent entities yet (that is M3). This client
therefore returns the raw per-slot observation list untouched; the per-agent
fan-out and the "actions are accepted-but-no-op" contract live one layer up in
:mod:`mindustry_agents.env.parallel_env`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from mindustry_agents import protocol as P
from mindustry_agents.process.launcher import Connection

DEFAULT_SCENARIO_ID = "bootstrap-defense-v0"


class EnvClientError(RuntimeError):
    """Raised when the server rejects a request or the episode state is invalid."""


@dataclass
class ResetResult:
    observations: list[dict[str, Any]]
    info: dict[str, Any]


class EnvClient:
    """Stateful, single-connection view of one rl-server world.

    Not thread-safe: a connection carries one in-flight request at a time. Step
    many worlds concurrently by giving each its own client (see
    :class:`mindustry_agents.env.vector.VectorCollector`).
    """

    def __init__(
        self,
        connection: Connection,
        *,
        scenario_id: str = DEFAULT_SCENARIO_ID,
        agent_count: int = 2,
        client_name: str = "mindustry-agents",
    ):
        self._conn = connection
        self.scenario_id = scenario_id
        self.agent_count = agent_count
        self.client_name = client_name
        self.episode_id: Optional[str] = None
        self.tick: int = 0
        self.handshake_response: Optional[P.HandshakeResponse] = None

    # -- helpers -----------------------------------------------------------

    def _call(self, message: Any) -> Any:
        resp = self._conn.call(message)
        if isinstance(resp, P.ErrorResponse):
            raise EnvClientError(
                f"server error [{resp.code}]: {resp.message} ({resp.detail})"
            )
        return resp

    def set_timeout(self, timeout_s: Optional[float]) -> None:
        """Set the socket timeout for subsequent calls (``None`` = block)."""
        self._conn.set_timeout(timeout_s)

    # -- protocol surface --------------------------------------------------

    def handshake(self) -> P.HandshakeResponse:
        resp = self._call(
            P.HandshakeRequest(
                protocol_version=P.PROTOCOL_VERSION, client_name=self.client_name
            )
        )
        if not isinstance(resp, P.HandshakeResponse):
            raise EnvClientError(f"expected handshake_response, got {type(resp).__name__}")
        if resp.protocol_version != P.PROTOCOL_VERSION:
            raise EnvClientError(
                f"protocol version mismatch: server={resp.protocol_version} "
                f"client={P.PROTOCOL_VERSION}"
            )
        self.handshake_response = resp
        return resp

    def reset(
        self,
        seed: int,
        options: Optional[dict[str, Any]] = None,
    ) -> ResetResult:
        """Reset the world with ``seed``. Returns per-slot observations + info.

        ``info`` carries ``state_hash``, ``episode_id``, ``tick``, ``action_masks``
        and scenario ``metadata`` (mirrors the reset response fields, minus the
        observation list which is returned separately).
        """
        options = options or {}
        deterministic = bool(options.get("deterministic", True))
        agent_count = int(options.get("agent_count", self.agent_count))
        scenario_id = str(options.get("scenario_id", self.scenario_id))
        resp = self._call(
            P.ResetRequest(
                request_id=self._conn.next_request_id(),
                scenario_id=scenario_id,
                root_seed=int(seed),
                agent_count=agent_count,
                deterministic=deterministic,
                options={
                    k: v
                    for k, v in options.items()
                    if k not in ("deterministic", "agent_count", "scenario_id")
                },
            )
        )
        if not isinstance(resp, P.ResetResponse):
            raise EnvClientError(f"expected reset_response, got {type(resp).__name__}")
        self.episode_id = resp.episode_id
        self.tick = resp.tick
        info = {
            "episode_id": resp.episode_id,
            "tick": resp.tick,
            "state_hash": resp.state_hash,
            "action_masks": resp.action_masks,
            "metadata": resp.metadata,
        }
        return ResetResult(observations=list(resp.initial_observations), info=info)

    def step(
        self,
        actions_bundle: list[dict[str, Any]],
        ticks: int = 1,
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[bool],
        list[bool],
        dict[str, Any],
    ]:
        """Advance exactly ``ticks`` engine updates applying ``actions_bundle``.

        Returns ``(observations, reward_breakdowns, terminations, truncations,
        info)`` where each list is per-agent-slot in agent-index order, and
        ``info`` carries ``state_hash``, ``tick``, ``previous_tick``,
        ``team_state``, ``timing``, ``action_masks``, ``game_events``,
        ``task_events``.
        """
        if self.episode_id is None:
            raise EnvClientError("step() called before reset()")
        resp = self._call(
            P.StepRequest(
                request_id=self._conn.next_request_id(),
                episode_id=self.episode_id,
                expected_tick=self.tick,
                ticks_to_advance=int(ticks),
                agent_actions=list(actions_bundle),
            )
        )
        if not isinstance(resp, P.StepResponse):
            raise EnvClientError(f"expected step_response, got {type(resp).__name__}")
        self.tick = resp.tick
        info = {
            "tick": resp.tick,
            "previous_tick": resp.previous_tick,
            "state_hash": resp.state_hash,
            "team_state": resp.team_state,
            "timing": resp.timing,
            "action_masks": resp.action_masks,
            "game_events": resp.game_events,
            "task_events": resp.task_events,
        }
        return (
            list(resp.observations),
            list(resp.reward_breakdowns),
            list(resp.terminations),
            list(resp.truncations),
            info,
        )

    def health(self) -> P.HealthResponse:
        resp = self._call(P.HealthRequest(request_id=self._conn.next_request_id()))
        if not isinstance(resp, P.HealthResponse):
            raise EnvClientError(f"expected health_response, got {type(resp).__name__}")
        return resp

    def close(self) -> None:
        """Best-effort graceful close of the underlying connection."""
        try:
            self._conn.set_timeout(2.0)
            self._conn.send(
                P.CloseRequest(request_id=self._conn.next_request_id(), reason="close")
            )
            try:
                self._conn.recv()
            except Exception:
                pass
        except Exception:
            pass
        finally:
            self._conn.close()
