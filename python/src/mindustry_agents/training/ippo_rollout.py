"""Real-JVM rollout adapter for ADR-0070's all-seat IPPO boundary."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import torch

from mindustry_agents.process.launcher import RlServerProcess
from mindustry_agents.training.ippo import (
    SharedRecurrentSelector,
    SharedSeatState,
    commit_all_seat_boundary,
    decide_all_seats,
    model_state_digest,
)
from mindustry_agents.training.ippo_ppo import (
    IPPOEpisodeRollout,
    IPPOTransition,
)
from mindustry_agents.training.ippo_reward import IPPOReward


@dataclass(frozen=True)
class IPPOEpisodeEvidence:
    """Training rollout plus authoritative audit evidence."""

    rollout: IPPOEpisodeRollout
    tick: int
    core_health: float
    shared_reward_components: dict[str, float]
    individual_reward_totals: tuple[float, float, float]
    coordination_metrics: dict[str, Any]
    trace: tuple[dict[str, Any], ...]
    trace_sha256: str
    model_state_sha256: str


def _json_digest(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def rollout_ippo_episode(
    env: RlServerProcess,
    model: SharedRecurrentSelector,
    config: dict[str, Any],
    *,
    seed: int,
    evaluation: bool,
    action_generator: torch.Generator,
) -> IPPOEpisodeEvidence:
    """Run one externally stepped episode with one atomic all-seat action."""

    reset = env.reset(
        seed,
        scenario_id=str(config["scenario_id"]),
        scenario_version=int(config["scenario_version"]),
        agent_count=int(config["agent_count"]),
    )
    observations = reset.initial_observations
    masks = reset.action_masks
    metadata = reset.metadata
    tick = reset.tick
    outcome = reset.outcome
    board: list[dict[str, Any]] = []
    boundary_reasons: list[str] = []
    previous_team = dict(observations[0]["team"])
    state = SharedSeatState.fresh()
    reward = IPPOReward(
        config["team_quality_reward"], config["individual_shaping"]
    )
    transitions: list[IPPOTransition] = []
    trace: list[dict[str, Any]] = []
    shared_totals: dict[str, float] = {}
    final_metrics: dict[str, Any] = {}

    while outcome == "running" and tick < int(metadata["tick_cap"]):
        decision = decide_all_seats(
            model,
            state,
            observations,
            masks,
            metadata,
            task_board=board,
            boundary_reasons=boundary_reasons,
            evaluation=evaluation,
            action_generator=action_generator,
        )
        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, int(metadata["tick_cap"]) - tick),
            agent_actions=decision.agent_actions,
            stop_on_decision_event=True,
        )
        commit_all_seat_boundary(
            state,
            decision,
            response.action_results,
            observations,
            tick=tick,
        )
        current_team = dict(response.observations[0]["team"])
        reasons = list(response.decision_boundary.get("reasons", []))
        advanced_ticks = int(
            response.decision_boundary.get(
                "advanced_ticks", response.tick - tick
            )
        )
        breakdown = reward.observe(
            previous_team,
            current_team,
            advanced_ticks=advanced_ticks,
            tick_cap=int(metadata["tick_cap"]),
            outcome=response.outcome,
            task_events=response.task_events,
            game_events=response.game_events,
            boundary_reasons=reasons,
            coordination_metrics=response.coordination_metrics,
        )
        for key, amount in breakdown.team.components.items():
            shared_totals[key] = shared_totals.get(key, 0.0) + amount
        done = response.outcome != "running"
        boundary_transition_indices: list[int] = []
        for agent_id in decision.evaluation_order:
            features = decision.features[agent_id]
            transitions.append(
                IPPOTransition(
                    agent_id=agent_id,
                    candidates=torch.tensor(
                        features.candidates, dtype=torch.float32
                    ),
                    scalars=torch.tensor(features.scalars, dtype=torch.float32),
                    candidate_present=torch.tensor(
                        features.candidate_present, dtype=torch.bool
                    ),
                    action_mask=torch.tensor(
                        features.action_mask, dtype=torch.bool
                    ),
                    hidden_input=decision.hidden_inputs[agent_id],
                    action=decision.action_indices[agent_id],
                    old_log_prob=decision.old_log_probabilities[agent_id],
                    old_value=decision.old_values[agent_id],
                    team_reward=breakdown.team.total,
                    individual_reward=breakdown.individual_components[agent_id],
                    advanced_ticks=advanced_ticks,
                    done=done,
                    policy_loss_mask=decision.policy_loss_masks[agent_id],
                    recurrent_reset=decision.recurrent_resets[agent_id],
                )
            )
            boundary_transition_indices.append(len(transitions) - 1)
        trace_row = {
            "tick": tick,
            "next_tick": response.tick,
            "advanced_ticks": advanced_ticks,
            "agent_actions": decision.agent_actions,
            "action_results": response.action_results,
            "action_indices": decision.action_indices,
            "evaluation_order": list(decision.evaluation_order),
            "transition_indices": boundary_transition_indices,
            "shared_reward_components": breakdown.team.components,
            "individual_reward_components": list(
                breakdown.individual_components
            ),
            "individual_reward_totals": list(
                breakdown.own_idle_penalty_totals
            ),
            "state_hash": response.state_hash,
            "outcome": response.outcome,
        }
        if config.get("candidate_version") == "m9-ippo-v2-sequence16":
            trace_row["recurrent_resets"] = decision.recurrent_resets
        trace.append(trace_row)
        observations = response.observations
        masks = response.action_masks
        board = response.task_board
        boundary_reasons = reasons
        previous_team = current_team
        tick = response.tick
        outcome = response.outcome
        final_metrics = response.coordination_metrics

    if outcome == "running":
        raise RuntimeError("M9 IPPO episode ended without a terminal outcome")
    rollout = IPPOEpisodeRollout(seed, outcome, tuple(transitions))
    return IPPOEpisodeEvidence(
        rollout=rollout,
        tick=tick,
        core_health=float(observations[0]["team"]["core_health"]),
        shared_reward_components=dict(sorted(shared_totals.items())),
        individual_reward_totals=tuple(reward.own_idle_penalty_totals),
        coordination_metrics=final_metrics,
        trace=tuple(trace),
        trace_sha256=_json_digest(trace),
        model_state_sha256=model_state_digest(model),
    )
