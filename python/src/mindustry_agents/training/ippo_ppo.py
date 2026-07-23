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
IPPO_V2_CONFIG_SHA256 = (
    "266e50429902de0d97049eaeb80558b22bb20fffedda926e92091102489a76da"
)
IPPO_V2_PROTOCOL_SHA256 = (
    "ec9a69612b709290a339b1e44f202b65d6dabc5d47b513021ab474dee54934b0"
)
IPPO_V3_CONFIG_SHA256 = (
    "5d437c390fc54423ac1be1f27b47395e68bd42e5f85a74e8abd13275c5f9b458"
)
IPPO_V3_PROTOCOL_SHA256 = (
    "29085f124d958f563965a682adb029bdff24bf3a03df2148dd19c41c36e2a82f"
)
IPPO_V4_CONFIG_SHA256 = (
    "9b9495e03b11e0fdae744fefd64f65de513b85093cf96e2a088ac4235766d215"
)
IPPO_V4_PROTOCOL_SHA256 = (
    "db9b5647f249d30889b911a075905a78f4ba9ccef5613bc25d09126e1d1e7ace"
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
    recurrent_reset: bool = False

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


def load_ippo_v2_config(path: Path) -> dict[str, Any]:
    """Load and fail closed on ADR-0073's immutable sequence recipe."""

    if sha256_path(path) != IPPO_V2_CONFIG_SHA256:
        raise ValueError("M9 IPPO v2 config hash does not match ADR-0073")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema") != "ippo_training_config_v2":
        raise ValueError("M9 IPPO v2 config schema is invalid")
    if config.get("candidate_version") != "m9-ippo-v2-sequence16":
        raise ValueError("M9 IPPO v2 candidate identity is invalid")
    if config.get("model_architecture") != IPPO_MODEL_ARCHITECTURE:
        raise ValueError("M9 IPPO v2 model architecture drifted")
    if config.get("teacher") is not None:
        raise ValueError("M9 IPPO v2 does not authorize a teacher")
    if config.get("confirmation_seed_set") is not None:
        raise ValueError("M9 IPPO v2 confirmation access is not authorized")
    if config.get("held_out_seed_set") is not None:
        raise ValueError("M9 IPPO v2 held-out access is not authorized")
    if int(config.get("torch_threads", 0)) != 1:
        raise ValueError("M9 IPPO v2 requires one torch CPU thread")
    if int(config["training_cycles"]) * int(config["episodes_per_update"]) != 2048:
        raise ValueError("M9 IPPO v2 episode budget drifted")
    recurrent = config.get("recurrent_backpropagation")
    if recurrent != {
        "schema": "truncated_seat_sequence_v1",
        "sequence_length": 16,
        "sequences_per_minibatch": 16,
        "initial_hidden": "stored_rollout_state_at_window_start_detached",
        "hidden_output": "recomputed_private_next_boundary_state_within_window",
        "window_order": "episode_order_then_agent_id_then_boundary_order",
        "window_split": "episode_or_authoritative_seat_reset_or_16_transitions",
        "padding": "right_padded_and_loss_masked",
        "cross_agent_state": False,
    }:
        raise ValueError("M9 IPPO v2 recurrent sequence contract drifted")
    if config.get("optimizer_ppo", {}).get(
        "recurrent_backpropagation"
    ) != {
        "schema": "truncated_seat_sequence_v1",
        "sequence_length": 16,
        "sequences_per_minibatch": 16,
    }:
        raise ValueError("M9 IPPO v2 optimizer sequence contract drifted")
    if (
        int(config["minibatch_size"])
        != int(recurrent["sequence_length"])
        * int(recurrent["sequences_per_minibatch"])
    ):
        raise ValueError("M9 IPPO v2 sequence minibatch budget drifted")
    return config


def load_ippo_v3_config(path: Path) -> dict[str, Any]:
    """Load and fail closed on ADR-0075's diverse-root recipe."""

    if sha256_path(path) != IPPO_V3_CONFIG_SHA256:
        raise ValueError("M9 IPPO v3 config hash does not match ADR-0075")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema") != "ippo_training_config_v3":
        raise ValueError("M9 IPPO v3 config schema is invalid")
    if config.get("candidate_version") != "m9-ippo-v3-diverse2048":
        raise ValueError("M9 IPPO v3 candidate identity is invalid")
    if config.get("model_architecture") != IPPO_MODEL_ARCHITECTURE:
        raise ValueError("M9 IPPO v3 model architecture drifted")
    if config.get("teacher") is not None:
        raise ValueError("M9 IPPO v3 does not authorize a teacher")
    if config.get("confirmation_seed_set") is not None:
        raise ValueError("M9 IPPO confirmation access is not authorized")
    if config.get("held_out_seed_set") is not None:
        raise ValueError("M9 IPPO held-out access is not authorized")
    if int(config.get("torch_threads", 0)) != 1:
        raise ValueError("M9 IPPO v3 requires one torch CPU thread")
    if int(config["training_cycles"]) * int(config["episodes_per_update"]) != 2048:
        raise ValueError("M9 IPPO v3 episode budget drifted")
    if config.get("training_root_schedule") != {
        "schema": "unique_root_per_episode_v1",
        "root_count": 2048,
        "reuse_count": 1,
        "shuffle": "single_deterministic_full_schedule",
        "shuffle_seed": 9603,
        "updates": 32,
        "episodes_per_update": 64,
    }:
        raise ValueError("M9 IPPO v3 diverse-root schedule contract drifted")
    if config.get("recurrent_backpropagation") != {
        "schema": "one_boundary_truncation_v1",
        "hidden_input": "stored_rollout_state",
        "hidden_output": "private_next_boundary_state",
        "cross_agent_state": False,
    }:
        raise ValueError("M9 IPPO v3 one-boundary optimizer contract drifted")
    return config


def load_ippo_v4_config(path: Path) -> dict[str, Any]:
    """Load and fail closed on ADR-0079's entropy-annealing recipe."""

    if sha256_path(path) != IPPO_V4_CONFIG_SHA256:
        raise ValueError("M9 IPPO v4 config hash does not match ADR-0079")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema") != "ippo_training_config_v4":
        raise ValueError("M9 IPPO v4 config schema is invalid")
    if config.get("candidate_version") != "m9-ippo-v4-entropy-anneal":
        raise ValueError("M9 IPPO v4 candidate identity is invalid")
    if (
        config.get("parent_candidate_version") != "m9-ippo-v3-diverse2048"
        or config.get("sole_learning_change")
        != "linear_entropy_coefficient_anneal_0.02_to_0.0"
    ):
        raise ValueError("M9 IPPO v4 successor identity drifted")
    if config.get("model_architecture") != IPPO_MODEL_ARCHITECTURE:
        raise ValueError("M9 IPPO v4 model architecture drifted")
    if config.get("teacher") is not None:
        raise ValueError("M9 IPPO v4 does not authorize a teacher")
    if config.get("confirmation_seed_set") is not None:
        raise ValueError("M9 IPPO confirmation access is not authorized")
    if config.get("held_out_seed_set") is not None:
        raise ValueError("M9 IPPO held-out access is not authorized")
    if int(config.get("torch_threads", 0)) != 1:
        raise ValueError("M9 IPPO v4 requires one torch CPU thread")
    if int(config["training_cycles"]) * int(config["episodes_per_update"]) != 2048:
        raise ValueError("M9 IPPO v4 episode budget drifted")
    if config.get("training_root_schedule") != {
        "schema": "unique_root_per_episode_v1",
        "root_count": 2048,
        "reuse_count": 1,
        "shuffle": "single_deterministic_full_schedule",
        "shuffle_seed": 9603,
        "updates": 32,
        "episodes_per_update": 64,
    }:
        raise ValueError("M9 IPPO v4 diverse-root schedule contract drifted")
    if config.get("recurrent_backpropagation") != {
        "schema": "one_boundary_truncation_v1",
        "hidden_input": "stored_rollout_state",
        "hidden_output": "private_next_boundary_state",
        "cross_agent_state": False,
    }:
        raise ValueError("M9 IPPO v4 one-boundary optimizer contract drifted")
    schedule = {
        "schema": "linear_update_v1",
        "start": 0.02,
        "end": 0.0,
        "first_update": 1,
        "last_update": 32,
        "interpolation": "inclusive",
    }
    if (
        config.get("entropy_coefficient") != 0.02
        or config.get("entropy_coefficient_schedule") != schedule
        or config.get("optimizer_ppo", {}).get(
            "entropy_coefficient_schedule"
        )
        != schedule
    ):
        raise ValueError("M9 IPPO v4 entropy schedule contract drifted")
    return config


def load_ippo_config(path: Path) -> dict[str, Any]:
    """Load one accepted immutable M9 IPPO recipe by its exact hash."""

    digest = sha256_path(path)
    if digest == IPPO_V1_CONFIG_SHA256:
        return load_ippo_v1_config(path)
    if digest == IPPO_V2_CONFIG_SHA256:
        return load_ippo_v2_config(path)
    if digest == IPPO_V3_CONFIG_SHA256:
        return load_ippo_v3_config(path)
    if digest == IPPO_V4_CONFIG_SHA256:
        return load_ippo_v4_config(path)
    raise ValueError("M9 IPPO config hash is not an accepted recipe")


def config_sha256(config: dict[str, Any]) -> str:
    candidate = config.get("candidate_version")
    if candidate == "m9-ippo-v1":
        return IPPO_V1_CONFIG_SHA256
    if candidate == "m9-ippo-v2-sequence16":
        return IPPO_V2_CONFIG_SHA256
    if candidate == "m9-ippo-v3-diverse2048":
        return IPPO_V3_CONFIG_SHA256
    if candidate == "m9-ippo-v4-entropy-anneal":
        return IPPO_V4_CONFIG_SHA256
    raise ValueError("M9 IPPO candidate identity is unsupported")


def protocol_sha256(config: dict[str, Any]) -> str:
    candidate = config.get("candidate_version")
    if candidate == "m9-ippo-v1":
        return IPPO_V1_PROTOCOL_SHA256
    if candidate == "m9-ippo-v2-sequence16":
        return IPPO_V2_PROTOCOL_SHA256
    if candidate == "m9-ippo-v3-diverse2048":
        return IPPO_V3_PROTOCOL_SHA256
    if candidate == "m9-ippo-v4-entropy-anneal":
        return IPPO_V4_PROTOCOL_SHA256
    raise ValueError("M9 IPPO candidate identity is unsupported")


def entropy_coefficient_for_update(
    config: dict[str, Any],
    update: int | None,
) -> float:
    """Return one candidate's immutable per-update entropy coefficient."""

    if config.get("candidate_version") != "m9-ippo-v4-entropy-anneal":
        return float(config["entropy_coefficient"])
    if update is None:
        raise ValueError("M9 IPPO v4 optimizer update number is required")
    schedule = config["entropy_coefficient_schedule"]
    first = int(schedule["first_update"])
    last = int(schedule["last_update"])
    if update < first or update > last:
        raise ValueError("M9 IPPO v4 optimizer update number is out of range")
    start = float(schedule["start"])
    end = float(schedule["end"])
    fraction = (update - first) / (last - first)
    return start + (end - start) * fraction


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
    if item.action < 0 or item.action >= 10:
        raise ValueError("IPPO transition action index is invalid")
    if not bool(item.action_mask.any()):
        raise ValueError("IPPO transition action mask has no legal action")
    if item.policy_loss_mask and not bool(item.action_mask[item.action]):
        raise ValueError("IPPO actor transition action is outside its mask")
    if item.advanced_ticks < 0:
        raise ValueError("IPPO transition advanced ticks cannot be negative")
    if not isinstance(item.recurrent_reset, bool):
        raise ValueError("IPPO transition recurrent reset flag is invalid")


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


def _ippo_one_boundary_update(
    model: SharedRecurrentSelector,
    optimizer: torch.optim.Optimizer,
    episodes: Sequence[IPPOEpisodeRollout],
    config: dict[str, Any],
    shuffle_generator: torch.Generator,
) -> dict[str, float]:
    """Apply ADR-0070's detached one-boundary clipped PPO update."""

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


def ippo_sequence_windows(
    episodes: Sequence[IPPOEpisodeRollout],
    *,
    sequence_length: int,
) -> tuple[tuple[int, ...], ...]:
    """Return deterministic flat-index windows without crossing seat resets."""

    if sequence_length < 1:
        raise ValueError("IPPO sequence length must be positive")
    windows: list[tuple[int, ...]] = []
    offset = 0
    for episode in episodes:
        if not episode.transitions:
            raise ValueError("IPPO episode has no transitions")
        for item in episode.transitions:
            _validate_transition(item)
        for agent_id in range(AGENT_COUNT):
            indices = [
                offset + index
                for index, item in enumerate(episode.transitions)
                if item.agent_id == agent_id
            ]
            if not indices:
                continue
            first = episode.transitions[indices[0] - offset]
            if not first.recurrent_reset:
                raise ValueError(
                    "IPPO sequence does not start at an authoritative seat reset"
                )
            current: list[int] = []
            for index in indices:
                item = episode.transitions[index - offset]
                if current and (
                    item.recurrent_reset or len(current) == sequence_length
                ):
                    windows.append(tuple(current))
                    current = []
                current.append(index)
            if current:
                windows.append(tuple(current))
        offset += len(episode.transitions)
    covered = [index for window in windows for index in window]
    expected = list(range(offset))
    if sorted(covered) != expected or len(covered) != len(set(covered)):
        raise AssertionError("IPPO sequence windows do not partition transitions")
    return tuple(windows)


def _sequence_minibatch_loss(
    model: SharedRecurrentSelector,
    transitions: Sequence[IPPOTransition],
    advantages: torch.Tensor,
    returns: torch.Tensor,
    windows: Sequence[tuple[int, ...]],
    *,
    sequence_length: int,
    clip_ratio: float,
    value_coefficient: float,
    entropy_coefficient: float,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, int]:
    """Recompute private hidden state through one padded sequence minibatch."""

    if not windows:
        raise ValueError("IPPO sequence minibatch is empty")
    batch = len(windows)
    candidates = torch.zeros((batch, sequence_length, 8, 37))
    scalars = torch.zeros((batch, sequence_length, 160))
    present = torch.zeros(
        (batch, sequence_length, 8), dtype=torch.bool
    )
    masks = torch.zeros(
        (batch, sequence_length, 10), dtype=torch.bool
    )
    masks[:, :, 9] = True
    agent_ids = torch.zeros((batch, sequence_length), dtype=torch.long)
    actions = torch.full((batch, sequence_length), 9, dtype=torch.long)
    old_log_probs = torch.zeros((batch, sequence_length))
    actor = torch.zeros((batch, sequence_length), dtype=torch.bool)
    valid = torch.zeros((batch, sequence_length), dtype=torch.bool)
    advantage_batch = torch.zeros((batch, sequence_length))
    return_batch = torch.zeros((batch, sequence_length))
    initial_hidden = []

    for row, window in enumerate(windows):
        if not window or len(window) > sequence_length:
            raise ValueError("IPPO sequence window length is invalid")
        first = transitions[window[0]]
        initial_hidden.append(first.hidden_input)
        expected_agent = first.agent_id
        for step, index in enumerate(window):
            item = transitions[index]
            if item.agent_id != expected_agent:
                raise AssertionError("IPPO sequence window crossed agent ids")
            if step and item.recurrent_reset:
                raise AssertionError("IPPO sequence window crossed a seat reset")
            candidates[row, step] = item.candidates
            scalars[row, step] = item.scalars
            present[row, step] = item.candidate_present
            masks[row, step] = item.action_mask
            agent_ids[row, step] = item.agent_id
            actions[row, step] = item.action
            old_log_probs[row, step] = item.old_log_prob
            actor[row, step] = item.policy_loss_mask
            valid[row, step] = True
            advantage_batch[row, step] = advantages[index]
            return_batch[row, step] = returns[index]

    hidden = torch.stack(initial_hidden).detach()
    log_probabilities = []
    values = []
    entropies = []
    for step in range(sequence_length):
        _, masked_logits, value, hidden = model(
            candidates[:, step],
            scalars[:, step],
            present[:, step],
            masks[:, step],
            agent_ids[:, step],
            hidden,
        )
        all_log_probabilities = torch.log_softmax(masked_logits, dim=-1)
        log_probabilities.append(
            all_log_probabilities.gather(
                1, actions[:, step, None]
            ).squeeze(1)
        )
        probabilities = torch.softmax(masked_logits, dim=-1)
        entropies.append(
            -(probabilities * all_log_probabilities).sum(dim=-1)
        )
        values.append(value)

    log_probs = torch.stack(log_probabilities, dim=1)
    value_tensor = torch.stack(values, dim=1)
    entropy_tensor = torch.stack(entropies, dim=1)
    active = valid & actor
    if active.any():
        ratio = torch.exp(log_probs[active] - old_log_probs[active])
        unclipped = ratio * advantage_batch[active]
        clipped = torch.clamp(
            ratio,
            1.0 - clip_ratio,
            1.0 + clip_ratio,
        ) * advantage_batch[active]
        policy_loss = -torch.minimum(unclipped, clipped).mean()
        entropy = entropy_tensor[active].mean()
    else:
        policy_loss = value_tensor.sum() * 0.0
        entropy = value_tensor.sum() * 0.0
    value_loss = functional.mse_loss(
        value_tensor[valid], return_batch[valid]
    )
    loss = (
        policy_loss
        + value_coefficient * value_loss
        - entropy_coefficient * entropy
    )
    return (
        loss,
        policy_loss,
        value_loss,
        entropy,
        int(valid.sum().item()),
    )


def ippo_sequence_update(
    model: SharedRecurrentSelector,
    optimizer: torch.optim.Optimizer,
    episodes: Sequence[IPPOEpisodeRollout],
    config: dict[str, Any],
    shuffle_generator: torch.Generator,
) -> dict[str, float]:
    """Apply ADR-0073's deterministic truncated-sequence PPO update."""

    transitions, advantages, returns = ippo_advantages(
        episodes,
        gamma_per_second=float(config["gamma_per_second"]),
        gae_lambda=float(config["gae_lambda"]),
    )
    recurrent = config["recurrent_backpropagation"]
    sequence_length = int(recurrent["sequence_length"])
    sequences_per_minibatch = int(recurrent["sequences_per_minibatch"])
    if sequence_length * sequences_per_minibatch != int(
        config["minibatch_size"]
    ):
        raise ValueError("IPPO sequence minibatch budget is invalid")
    windows = ippo_sequence_windows(
        episodes, sequence_length=sequence_length
    )
    totals = {
        "policy_loss": 0.0,
        "value_loss": 0.0,
        "entropy": 0.0,
        "batches": 0.0,
    }
    padded_slots = 0
    real_presentations = 0
    for _ in range(int(config["ppo_epochs"])):
        order = torch.randperm(len(windows), generator=shuffle_generator)
        for start in range(0, len(windows), sequences_per_minibatch):
            selected = [
                windows[int(index)]
                for index in order[start : start + sequences_per_minibatch]
            ]
            loss, policy_loss, value_loss, entropy, real = (
                _sequence_minibatch_loss(
                    model,
                    transitions,
                    advantages,
                    returns,
                    selected,
                    sequence_length=sequence_length,
                    clip_ratio=float(config["clip_ratio"]),
                    value_coefficient=float(config["value_coefficient"]),
                    entropy_coefficient=float(config["entropy_coefficient"]),
                )
            )
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(), float(config["max_grad_norm"])
            )
            optimizer.step()
            totals["policy_loss"] += float(policy_loss.item())
            totals["value_loss"] += float(value_loss.item())
            totals["entropy"] += float(entropy.item())
            totals["batches"] += 1.0
            real_presentations += real
            padded_slots += len(selected) * sequence_length - real
    divisor = max(1.0, totals["batches"])
    return {
        **{
            key: value if key == "batches" else value / divisor
            for key, value in totals.items()
        },
        "sequence_windows": float(len(windows)),
        "real_transition_presentations": float(real_presentations),
        "padded_transition_slots": float(padded_slots),
    }


def ippo_update(
    model: SharedRecurrentSelector,
    optimizer: torch.optim.Optimizer,
    episodes: Sequence[IPPOEpisodeRollout],
    config: dict[str, Any],
    shuffle_generator: torch.Generator,
    *,
    update_number: int | None = None,
) -> dict[str, float]:
    """Dispatch one accepted M9 IPPO recurrent optimization contract."""

    schema = config.get("recurrent_backpropagation", {}).get("schema")
    if schema == "truncated_seat_sequence_v1":
        return ippo_sequence_update(
            model,
            optimizer,
            episodes,
            config,
            shuffle_generator,
        )
    if schema in (None, "one_boundary_truncation_v1"):
        if config.get("candidate_version") != "m9-ippo-v4-entropy-anneal":
            return _ippo_one_boundary_update(
                model,
                optimizer,
                episodes,
                config,
                shuffle_generator,
            )
        coefficient = entropy_coefficient_for_update(config, update_number)
        scheduled_config = {**config, "entropy_coefficient": coefficient}
        metrics = _ippo_one_boundary_update(
            model,
            optimizer,
            episodes,
            scheduled_config,
            shuffle_generator,
        )
        return {**metrics, "entropy_coefficient": coefficient}
    raise ValueError("unsupported M9 IPPO recurrent optimization contract")
