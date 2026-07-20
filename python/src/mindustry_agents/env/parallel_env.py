"""PettingZoo-style ParallelEnv facade over one rl-server world.

:class:`MindustryParallelEnv` presents the PettingZoo ``ParallelEnv`` *method
surface* (``possible_agents``, ``agents``, ``reset``, ``step``, ``close``,
``observation_space``/``action_space``) **without importing pettingzoo**. It is
duck-typed on purpose: the core package must import with zero third-party deps
(ADR-0007). Wrapping this in a real ``pettingzoo.ParallelEnv`` once the ``[rl]``
extra is installed is trivial — subclass ``ParallelEnv`` and delegate each method
to an instance of this class (see the module docstring example below).

HONESTY REQUIREMENT (M1 engine state)
-------------------------------------
The M1 engine emits a single **world-level** observation and has **no per-agent
entities** yet (that is milestone M3). So:

* ``possible_agents == ["agent_0", "agent_1"]`` and every agent currently
  receives the *same* world observation (a shared reference-equal dict copy).
* Actions are accepted as a per-agent dict but are **no-op bundles** — the engine
  ignores their contents in M1. Nothing here fakes per-agent state.

The *plumbing* is nonetheless per-agent end to end: ``reset``/``step`` take and
return dicts keyed by agent name, and the per-agent action dict is bundled into
the single :class:`StepRequest` the protocol already carries. When M3 lands, only
the *payload contents* (real per-agent observations/rewards) change — not the
shape of this API.

Example pettingzoo adapter (needs the ``[rl]`` extra)::

    from pettingzoo import ParallelEnv
    from mindustry_agents.env.parallel_env import MindustryParallelEnv

    class MindustryPZEnv(ParallelEnv):
        metadata = {"name": "mindustry_coop_v0"}
        def __init__(self, client):
            self._env = MindustryParallelEnv(client)
            self.possible_agents = list(self._env.possible_agents)
        def reset(self, seed=None, options=None):
            return self._env.reset(seed=seed, options=options)
        def step(self, actions):
            return self._env.step(actions)
        # observation_space/action_space/close delegate likewise.

Standard-library only.
"""

from __future__ import annotations

from typing import Any, Optional

from mindustry_agents.env.client import EnvClient

DEFAULT_AGENTS = ["agent_0", "agent_1"]


class MindustryParallelEnv:
    """Duck-typed PettingZoo ParallelEnv over a single :class:`EnvClient`."""

    metadata: dict[str, Any] = {"name": "mindustry_coop_v0", "is_parallelizable": True}

    def __init__(
        self,
        client: EnvClient,
        possible_agents: Optional[list[str]] = None,
    ):
        self._client = client
        self.possible_agents: list[str] = list(possible_agents or DEFAULT_AGENTS)
        self.agents: list[str] = []
        self._steps: int = 0

    # -- spaces (stubs; concrete once observations are agent-scoped, M3) ----

    def observation_space(self, agent: str) -> dict[str, Any]:
        """Descriptor stub. Framework-neutral; a real gymnasium.Space arrives
        with the ``[rl]`` extra and the M3 per-agent observation schema."""
        return {
            "type": "world_observation",
            "note": "M1: shared world-level dict; per-agent schema is M3",
            "keys": [
                "tick",
                "wave",
                "copper",
                "lead",
                "unit_count",
                "building_count",
                "core_health",
                "done",
            ],
        }

    def action_space(self, agent: str) -> dict[str, Any]:
        """Descriptor stub. M1 actions are accepted-but-no-op bundles."""
        return {
            "type": "noop_bundle",
            "note": "M1: actions accepted but ignored by the engine; real "
            "high-level action vocabulary is M3+",
        }

    # -- PettingZoo ParallelEnv surface ------------------------------------

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[dict[str, Any]] = None,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        """Reset the world. Returns ``(observations, infos)`` keyed by agent.

        A ``seed`` of ``None`` defaults to ``0`` (the protocol requires an int
        root seed). All live agents receive the same world observation in M1.
        """
        if seed is None:
            seed = 0
        result = self._client.reset(seed, options)
        self.agents = list(self.possible_agents)
        self._steps = 0
        observations = self._fanout_observations(result.observations)
        infos = {agent: dict(result.info) for agent in self.agents}
        return observations, infos

    def step(
        self,
        actions: dict[str, Any],
    ) -> tuple[
        dict[str, dict[str, Any]],
        dict[str, float],
        dict[str, bool],
        dict[str, bool],
        dict[str, dict[str, Any]],
    ]:
        """Advance one env step. ``actions`` is a per-agent dict.

        Per PettingZoo, each agent maps to one action; the bundle is applied
        atomically (one :class:`StepRequest`, one advance). Returns the standard
        five dicts ``(observations, rewards, terminations, truncations, infos)``
        keyed by agent name. When all agents terminate/truncate, ``self.agents``
        is emptied (PettingZoo end-of-episode convention).

        ``options``-style ``ticks`` control: pass an integer under the reserved
        ``"__ticks__"`` key in ``actions`` to advance more than one engine tick
        per env step (defaults to 1). It is stripped from the bundle.
        """
        ticks = int(actions.get("__ticks__", 1)) if isinstance(actions, dict) else 1
        bundle = self._bundle_actions(actions)
        obs, rewards, terms, truncs, info = self._client.step(bundle, ticks=ticks)
        self._steps += 1

        observations = self._fanout_observations(obs)
        reward_map = self._fanout_rewards(rewards)
        termination_map = self._fanout_flags(terms)
        truncation_map = self._fanout_flags(truncs)
        info_map = {agent: dict(info) for agent in self.agents}

        # PettingZoo: drop agents that are done; empty when the episode ends.
        done_agents = [
            a
            for a in self.agents
            if termination_map.get(a, False) or truncation_map.get(a, False)
        ]
        if len(done_agents) == len(self.agents):
            self.agents = []

        return observations, reward_map, termination_map, truncation_map, info_map

    def close(self) -> None:
        self._client.close()

    # -- fan-out helpers ---------------------------------------------------

    def _bundle_actions(self, actions: dict[str, Any]) -> list[dict[str, Any]]:
        """Bundle a per-agent action dict into agent-index-ordered list.

        Missing agents get an empty (no-op) action. The reserved ``__ticks__``
        control key is not part of the bundle.
        """
        bundle: list[dict[str, Any]] = []
        for agent in self.possible_agents:
            action = actions.get(agent, {}) if isinstance(actions, dict) else {}
            if not isinstance(action, dict):
                action = {"value": action}
            bundle.append({"agent": agent, **action})
        return bundle

    def _fanout_observations(
        self, observations: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Map the per-slot observation list to a per-agent dict.

        M1: the engine returns one observation per agent slot (all identical
        world snapshots). If the engine ever returns a single shared obs, it is
        broadcast to every agent.
        """
        result: dict[str, dict[str, Any]] = {}
        for i, agent in enumerate(self.agents):
            if not observations:
                result[agent] = {}
            elif i < len(observations):
                result[agent] = dict(observations[i])
            else:
                result[agent] = dict(observations[0])
        return result

    def _fanout_rewards(self, rewards: list[dict[str, Any]]) -> dict[str, float]:
        """Sum each agent's reward-component breakdown into a scalar.

        The full per-component breakdown is preserved in ``info`` (protocol
        ``reward_breakdowns``); this scalar is the PettingZoo-facing sum. M1
        rewards are empty, so all sums are ``0.0``.
        """
        result: dict[str, float] = {}
        for i, agent in enumerate(self.agents):
            breakdown = rewards[i] if i < len(rewards) else {}
            total = 0.0
            if isinstance(breakdown, dict):
                total = float(sum(v for v in breakdown.values() if isinstance(v, (int, float))))
            result[agent] = total
        return result

    def _fanout_flags(self, flags: list[bool]) -> dict[str, bool]:
        result: dict[str, bool] = {}
        for i, agent in enumerate(self.agents):
            result[agent] = bool(flags[i]) if i < len(flags) else False
        return result
