"""Deterministic one-boundary IPPO optimization primitives for M9."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import torch
import torch.nn.functional as functional

from mindustry_agents.training.ippo import (
    AGENT_COUNT,
    HIDDEN_WIDTH,
    IPPO_MODEL_ARCHITECTURE,
    SharedRecurrentSelector,
)

IPPO_CONFIG_SCHEMA = "ippo_training_config_v1"
IPPO_V1_CONFIG_SHA256 = (
    "5d349b4a93f1334292d09a4f4af6acd4764328836e6d6dbab309443e318c9861"
)
IPPO_V1_PROTOCOL_SHA256 = (
    "1f53ad0dde01a5433f609e8e0772d4576f6e5b600f0efb456242ee7333c6f554"
)


@dataclass(frozen=True)
class IPPOTransition:
    """One seat's private transition at one atomic team boundary."""

    agent_id: int
    candidates: torch.Tensor
    scalars: torch.Tensor
    candidate_present: torch.Tensor
    action_mask: torch.Tensor
    hidden_input: torch.Tensor
    action: int
    old_log_prob: float
    old_value: float
    team_reward: float
    individual_reward: float
    advanced_ticks: int
    done: bool
    policy_loss_mask: bool = True

    @property
    def reward(self) -> float:
        return self.team_reward + self.individual_reward


@dataclass(frozen=True)
class IPPOEpisodeRollout:
    """One episode's transitions in deterministic boundary/agent order."""

    seed: int
    outcome: str
    transitions: tuple[IPPOTransition, ...]


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_ippo_v1_config(path: Path) -> dict[str, Any]:
    """Load and fail closed on any drift from ADR-0070's immutable recipe."""

    if sha256_path(path) != IPPO_V1_CONFIG_SHA256:
        raise ValueError("M9 IPPO v1 config hash does not match ADR-0070")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema") != IPPO_CONFIG_SCHEMA:
        raise ValueError("M9 IPPO config schema is invalid")
    if config.get("candidate_version") != "m9-ippo-v1":
        raise ValueError("M9 IPPO candidate identity is invalid")
    if config.get("model_architecture") != IPPO_MODEL_ARCHITECTURE:
        raise ValueError("M9 IPPO model architecture drifted")
    if config.get("teacher") is not None:
        raise ValueError("M9 IPPO v1 does not authorize a teacher")
    if config.get("confirmation_seed_set") is not None:
        raise ValueError("M9 IPPO confirmation access is not authorized")
    if config.get("held_out_seed_set") is not None:
        raise ValueError("M9 IPPO held-out access is not authorized")
    if int(config.get("torch_threads", 0)) != 1:
        raise ValueError("M9 IPPO requires one torch CPU thread")
    if int(config["training_cycles"]) * int(config["episodes_per_update"]) != 2048:
        raise ValueError("M9 IPPO episode budget drifted")
    return config


def _validate_transition(item: IPPOTransition) -> None:
    if item.agent_id < 0 or item.agent_id >= AGENT_COUNT:
        raise ValueError("IPPO transition agent id is invalid")
    if item.candidates.shape != (8, 37):
        raise ValueError("IPPO transition candidates must have shape [8,37]")
    if item.scalars.shape != (160,):
        raise ValueError("IPPO transition scalars must have shape [160]")
    if item.candidate_present.shape != (8,):
        raise ValueError("IPPO transition candidate mask must have shape [8]")
    if item.action_mask.shape != (10,):
        raise ValueError("IPPO transition action mask must have shape [10]")
    if item.hidden_input.shape != (HIDDEN_WIDTH,):
        raise ValueError("IPPO transition hidden input must have shape [64]")
    if item.action < 0 or item.action >= 10 or not bool(item.action_mask[item.action]):
        raise ValueError("IPPO transition action is outside its mask")
    if item.advanced_ticks < 0:
        raise ValueError("IPPO transition advanced ticks cannot be negative")


def ippo_advantages(
    episodes: Sequence[IPPOEpisodeRollout],
    *,
    gamma_per_second: float,
    gae_lambda: float,
) -> tuple[list[IPPOTransition], torch.Tensor, torch.Tensor]:
    """Compute GAE independently down each seat's decision sequence."""

    if not 0.0 <= gamma_per_second <= 1.0:
        raise ValueError("gamma_per_second must be in [0,1]")
    if not 0.0 <= gae_lambda <= 1.0:
        raise ValueError("gae_lambda must be in [0,1]")
    flat: list[IPPOTransition] = []
    advantages: list[float] = []
    returns: list[float] = []
    for episode in episodes:
        if not episode.transitions:
            raise ValueError("IPPO episode has no transitions")
        values = [0.0] * len(episode.transitions)
        for item in episode.transitions:
            _validate_transition(item)
        for agent_id in range(AGENT_COUNT):
            indices = [
                index
                for index, item in enumerate(episode.transitions)
                if item.agent_id == agent_id
            ]
            next_value = 0.0
            next_advantage = 0.0
            for index in reversed(indices):
                item = episode.transitions[index]
                elapsed_seconds = item.advanced_ticks / 60.0
                gamma = gamma_per_second**elapsed_seconds
                lambda_decay = gae_lambda**elapsed_seconds
                continuation = 0.0 if item.done else 1.0
                delta = (
                    item.reward
                    + gamma * next_value * continuation
                    - item.old_value
                )
                advantage = (
                    delta
                    + gamma * lambda_decay * next_advantage * continuation
                )
                values[index] = advantage
                next_value = item.old_value
                next_advantage = advantage
        flat.extend(episode.transitions)
        advantages.extend(values)
        returns.extend(
            advantage + item.old_value
            for advantage, item in zip(values, episode.transitions)
        )
    tensor = torch.tensor(advantages, dtype=torch.float32)
    actor = torch.tensor(
        [item.policy_loss_mask for item in flat], dtype=torch.bool
    )
    if actor.any():
        selected = tensor[actor]
        tensor[actor] = (selected - selected.mean()) / selected.std(
            unbiased=False
        ).clamp_min(1e-8)
    return flat, tensor, torch.tensor(returns, dtype=torch.float32)


def ippo_update(
    model: SharedRecurrentSelector,
    optimizer: torch.optim.Optimizer,
    episodes: Sequence[IPPOEpisodeRollout],
    config: dict[str, Any],
    shuffle_generator: torch.Generator,
) -> dict[str, float]:
    """Apply ADR-0070's teacher-free clipped PPO update."""

    transitions, advantages, returns = ippo_advantages(
        episodes,
        gamma_per_second=float(config["gamma_per_second"]),
        gae_lambda=float(config["gae_lambda"]),
    )
    candidates = torch.stack([item.candidates for item in transitions])
    scalars = torch.stack([item.scalars for item in transitions])
    present = torch.stack([item.candidate_present for item in transitions])
    masks = torch.stack([item.action_mask for item in transitions])
    hidden = torch.stack([item.hidden_input for item in transitions]).detach()
    agent_ids = torch.tensor(
        [item.agent_id for item in transitions], dtype=torch.long
    )
    actions = torch.tensor(
        [item.action for item in transitions], dtype=torch.long
    )
    old_log_probs = torch.tensor(
        [item.old_log_prob for item in transitions], dtype=torch.float32
    )
    actor_mask = torch.tensor(
        [item.policy_loss_mask for item in transitions], dtype=torch.bool
    )
    batch_size = int(config["minibatch_size"])
    if batch_size < 1:
        raise ValueError("IPPO minibatch size must be positive")
    totals = {
        "policy_loss": 0.0,
        "value_loss": 0.0,
        "entropy": 0.0,
        "batches": 0.0,
    }
    for _ in range(int(config["ppo_epochs"])):
        order = torch.randperm(len(transitions), generator=shuffle_generator)
        for start in range(0, len(transitions), batch_size):
            index = order[start : start + batch_size]
            _, masked_logits, values, _ = model(
                candidates[index],
                scalars[index],
                present[index],
                masks[index],
                agent_ids[index],
                hidden[index],
            )
            log_probabilities = torch.log_softmax(masked_logits, dim=-1)
            log_probs = log_probabilities.gather(
                1, actions[index, None]
            ).squeeze(1)
            probabilities = torch.softmax(masked_logits, dim=-1)
            entropy = -(probabilities * log_probabilities).sum(dim=-1)
            active = actor_mask[index]
            if active.any():
                ratio = torch.exp(
                    log_probs[active] - old_log_probs[index][active]
                )
                unclipped = ratio * advantages[index][active]
                clipped = torch.clamp(
                    ratio,
                    1.0 - float(config["clip_ratio"]),
                    1.0 + float(config["clip_ratio"]),
                ) * advantages[index][active]
                policy_loss = -torch.minimum(unclipped, clipped).mean()
                entropy_loss = entropy[active].mean()
            else:
                policy_loss = values.sum() * 0.0
                entropy_loss = values.sum() * 0.0
            value_loss = functional.mse_loss(values, returns[index])
            loss = (
                policy_loss
                + float(config["value_coefficient"]) * value_loss
                - float(config["entropy_coefficient"]) * entropy_loss
            )
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(), float(config["max_grad_norm"])
            )
            optimizer.step()
            totals["policy_loss"] += float(policy_loss.item())
            totals["value_loss"] += float(value_loss.item())
            totals["entropy"] += float(entropy_loss.item())
            totals["batches"] += 1.0
    divisor = max(1.0, totals["batches"])
    return {
        key: value if key == "batches" else value / divisor
        for key, value in totals.items()
    }
