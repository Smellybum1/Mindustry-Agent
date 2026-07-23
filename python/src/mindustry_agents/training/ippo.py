"""M9.1 parameter-shared recurrent selector boundary.

This module owns the all-seat learned action seam only. Optimization is
deliberately absent until ADR-0069's implementation gate is committed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import torch
from torch import nn

from mindustry_agents.training.selector import (
    ACTION_COUNT,
    CONTROL_SCHEMA_V1,
    FEATURE_SCHEMA_V2,
    SelectorFeatures,
    SelectorHistory,
    build_selector_features,
    selector_action,
)

IPPO_MODEL_SCHEMA = "ippo_shared_recurrent_selector_v1"
IPPO_STATE_SCHEMA = "ippo_private_seat_state_v1"
IPPO_BOUNDARY_SCHEMA = "ippo_atomic_all_seat_boundary_v1"
AGENT_COUNT = 3
ROLE_EMBEDDING_WIDTH = 8
HIDDEN_WIDTH = 64

IPPO_MODEL_ARCHITECTURE = {
    "schema": IPPO_MODEL_SCHEMA,
    "agent_count": AGENT_COUNT,
    "candidate_encoder": [37, 64, 64],
    "current_scalar_encoder": [56, 64, 64],
    "lagged_context_encoder": [104, 64, 64],
    "role_embedding": [AGENT_COUNT, ROLE_EMBEDDING_WIDTH],
    "recurrent_cell": [200, HIDDEN_WIDTH],
    "select_head": [200, 64, 1],
    "special_head": [136, 64, 2],
    "critic": [200, 64, 1],
    "activation": "Tanh",
    "action_count": ACTION_COUNT,
    "hidden_state": "private_per_seat_zero_on_reset_or_death",
}


class SharedRecurrentSelector(nn.Module):
    """One shared actor/critic with role context and private recurrent inputs."""

    model_schema = IPPO_MODEL_SCHEMA

    def __init__(self, seed: int):
        super().__init__()
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            self.candidate_encoder = nn.Sequential(
                nn.Linear(37, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh()
            )
            self.current_scalar_encoder = nn.Sequential(
                nn.Linear(56, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh()
            )
            self.lagged_context_encoder = nn.Sequential(
                nn.Linear(104, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh()
            )
            self.role_embedding = nn.Embedding(
                AGENT_COUNT, ROLE_EMBEDDING_WIDTH
            )
            self.recurrent_cell = nn.GRUCell(200, HIDDEN_WIDTH)
            self.select_head = nn.Sequential(
                nn.Linear(200, 64), nn.Tanh(), nn.Linear(64, 1)
            )
            self.special_head = nn.Sequential(
                nn.Linear(136, 64), nn.Tanh(), nn.Linear(64, 2)
            )
            self.critic = nn.Sequential(
                nn.Linear(200, 64), nn.Tanh(), nn.Linear(64, 1)
            )

    def initial_hidden(
        self, batch_size: int, *, device: torch.device | str = "cpu"
    ) -> torch.Tensor:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        return torch.zeros(
            (batch_size, HIDDEN_WIDTH), dtype=torch.float32, device=device
        )

    def forward(
        self,
        candidates: torch.Tensor,
        scalars: torch.Tensor,
        candidate_present: torch.Tensor,
        action_mask: torch.Tensor,
        agent_ids: torch.Tensor,
        hidden: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        batch = candidates.shape[0]
        if candidates.shape != (batch, 8, 37):
            raise ValueError("IPPO candidates must have shape [batch,8,37]")
        if scalars.shape != (batch, 160):
            raise ValueError("IPPO scalars must have shape [batch,160]")
        if candidate_present.shape != (batch, 8):
            raise ValueError("IPPO candidate mask must have shape [batch,8]")
        if action_mask.shape != (batch, ACTION_COUNT):
            raise ValueError("IPPO action mask must have shape [batch,10]")
        if agent_ids.shape != (batch,):
            raise ValueError("IPPO agent ids must have shape [batch]")
        if hidden.shape != (batch, HIDDEN_WIDTH):
            raise ValueError("IPPO hidden state must have shape [batch,64]")
        if bool(((agent_ids < 0) | (agent_ids >= AGENT_COUNT)).any()):
            raise ValueError("IPPO agent id is out of range")

        encoded_candidates = self.candidate_encoder(candidates)
        encoded_current = self.current_scalar_encoder(scalars[:, :56])
        encoded_lag = self.lagged_context_encoder(scalars[:, 56:])
        roles = self.role_embedding(agent_ids)
        weights = candidate_present.to(encoded_candidates.dtype).unsqueeze(-1)
        candidate_sum = (encoded_candidates * weights).sum(dim=1)
        candidate_count = weights.sum(dim=1)
        pooled = candidate_sum / candidate_count.clamp_min(1.0)

        recurrent_input = torch.cat(
            (encoded_current, pooled, encoded_lag, roles), dim=-1
        )
        next_hidden = self.recurrent_cell(recurrent_input, hidden)

        other_sum = candidate_sum[:, None, :] - encoded_candidates * weights
        other_count = candidate_count[:, None, :] - weights
        other_pooled = other_sum / other_count.clamp_min(1.0)
        other_pooled = other_pooled * (other_count > 0).to(other_pooled.dtype)
        repeated_hidden = next_hidden[:, None, :].expand(-1, 8, -1)
        repeated_roles = roles[:, None, :].expand(-1, 8, -1)
        select_logits = self.select_head(
            torch.cat(
                (
                    encoded_candidates,
                    other_pooled,
                    repeated_hidden,
                    repeated_roles,
                ),
                dim=-1,
            )
        ).squeeze(-1)
        special_logits = self.special_head(
            torch.cat((pooled, next_hidden, roles), dim=-1)
        )
        raw_logits = torch.cat((select_logits, special_logits), dim=-1)
        masked_logits = raw_logits.masked_fill(
            ~action_mask, torch.finfo(raw_logits.dtype).min
        )
        value = self.critic(
            torch.cat((encoded_current, pooled, next_hidden, roles), dim=-1)
        ).squeeze(-1)
        return raw_logits, masked_logits, value, next_hidden


def model_state_digest(model: nn.Module) -> str:
    """Stable digest over one shared model's named tensor values."""

    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        value = tensor.detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(b"\0")
        digest.update(bytes(value.numpy().tobytes()))
    return digest.hexdigest()


@dataclass
class SharedSeatState:
    """Private reset-local history and recurrent state for exactly three seats."""

    histories: list[SelectorHistory]
    hidden: torch.Tensor
    dead: list[bool]
    sequence_start: list[bool]

    @classmethod
    def fresh(cls) -> "SharedSeatState":
        return cls(
            histories=[SelectorHistory() for _ in range(AGENT_COUNT)],
            hidden=torch.zeros((AGENT_COUNT, HIDDEN_WIDTH), dtype=torch.float32),
            dead=[False] * AGENT_COUNT,
            sequence_start=[True] * AGENT_COUNT,
        )

    def reset_seat(self, agent_id: int) -> None:
        if agent_id < 0 or agent_id >= AGENT_COUNT:
            raise ValueError("agent id is out of range")
        self.histories[agent_id] = SelectorHistory()
        self.hidden[agent_id].zero_()
        self.sequence_start[agent_id] = True

    def observe_lifecycle(self, observations: list[dict[str, Any]]) -> None:
        if len(observations) != AGENT_COUNT:
            raise ValueError("IPPO requires exactly three observations")
        for agent_id, observation in enumerate(observations):
            dead = bool(observation.get("unit", {}).get("dead", False))
            if dead:
                self.reset_seat(agent_id)
            self.dead[agent_id] = dead


@dataclass(frozen=True)
class AllSeatDecision:
    """One immutable pre-step decision assembled into a single action bundle."""

    schema: str
    agent_actions: list[dict[str, Any]]
    features: dict[int, SelectorFeatures]
    action_indices: dict[int, int]
    hidden_inputs: dict[int, torch.Tensor]
    old_log_probabilities: dict[int, float]
    old_values: dict[int, float]
    policy_loss_masks: dict[int, bool]
    recurrent_resets: dict[int, bool]
    evaluation_order: tuple[int, ...]
    model_state_sha256: str


def _feature_tensors(
    features: SelectorFeatures,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    return (
        torch.tensor([features.candidates], dtype=torch.float32),
        torch.tensor([features.scalars], dtype=torch.float32),
        torch.tensor([features.candidate_present], dtype=torch.bool),
        torch.tensor([features.action_mask], dtype=torch.bool),
    )


def _action_index(
    action: dict[str, Any],
    candidates: list[dict[str, Any]] | None = None,
) -> int:
    task_action = action.get("task_action", {})
    action_type = task_action.get("type")
    if action_type == "SELECT_CANDIDATE_TASK":
        index = int(task_action.get("candidate_index", -1))
        if index < 0 or index >= 8:
            raise ValueError("teacher candidate index is out of range")
        if (
            candidates is not None
            and index < len(candidates)
            and candidates[index].get("task_type") == "WAIT"
        ):
            return 9
        return index
    if action_type == "CONTINUE_CURRENT_TASK":
        return 8
    return 9


def canonical_teacher_bundle(
    actions: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Map scripted catalog-WAIT selections into the ordinary WAIT action."""

    _validate_teacher_bundle(actions)
    if len(observations) != AGENT_COUNT:
        raise ValueError("teacher canonicalization requires three observations")
    result = []
    for agent_id, action in enumerate(actions):
        candidates = observations[agent_id].get("task_candidates", [])
        if (
            action.get("task_action", {}).get("type") == "SELECT_CANDIDATE_TASK"
            and _action_index(action, candidates) == 9
        ):
            result.append(
                {"agent_id": agent_id, "task_action": {"type": "WAIT"}}
            )
        else:
            result.append(action)
    return result


def _validate_teacher_bundle(
    teacher_actions: list[dict[str, Any]] | None,
) -> None:
    if teacher_actions is None:
        return
    if len(teacher_actions) != AGENT_COUNT:
        raise ValueError("teacher bundle must contain exactly three actions")
    for agent_id, action in enumerate(teacher_actions):
        if int(action.get("agent_id", -1)) != agent_id:
            raise ValueError("teacher bundle is not in deterministic agent-id order")
        if not isinstance(action.get("task_action"), dict):
            raise ValueError("teacher action is missing task_action")


def decide_all_seats(
    model: SharedRecurrentSelector,
    state: SharedSeatState,
    observations: list[dict[str, Any]],
    action_masks: list[dict[str, Any]],
    metadata: dict[str, Any],
    *,
    task_board: list[dict[str, Any]] | None = None,
    boundary_reasons: list[str] | tuple[str, ...] = (),
    evaluation: bool,
    action_generator: torch.Generator | None = None,
    teacher_actions: list[dict[str, Any]] | None = None,
) -> AllSeatDecision:
    """Evaluate alive seats against one pre-step boundary and bundle atomically."""

    if len(observations) != AGENT_COUNT or len(action_masks) != AGENT_COUNT:
        raise ValueError("IPPO requires exactly three observations and masks")
    if not evaluation and action_generator is None:
        raise ValueError("stochastic IPPO decisions require an action generator")
    _validate_teacher_bundle(teacher_actions)
    if teacher_actions is not None:
        teacher_actions = canonical_teacher_bundle(teacher_actions, observations)
    state.observe_lifecycle(observations)
    agent_actions: list[dict[str, Any]] = []
    features_by_agent: dict[int, SelectorFeatures] = {}
    action_indices: dict[int, int] = {}
    hidden_inputs: dict[int, torch.Tensor] = {}
    old_log_probabilities: dict[int, float] = {}
    old_values: dict[int, float] = {}
    policy_loss_masks: dict[int, bool] = {}
    recurrent_resets: dict[int, bool] = {}
    evaluation_order: list[int] = []

    for agent_id in range(AGENT_COUNT):
        if state.dead[agent_id]:
            action = (
                teacher_actions[agent_id]
                if teacher_actions is not None
                else {"agent_id": agent_id, "task_action": {"type": "WAIT"}}
            )
            agent_actions.append(action)
            action_indices[agent_id] = _action_index(
                action, observations[agent_id].get("task_candidates", [])
            )
            continue

        features = build_selector_features(
            observations,
            action_masks,
            metadata,
            task_board=task_board,
            boundary_reasons=boundary_reasons,
            history=state.histories[agent_id],
            agent_id=agent_id,
            feature_schema=FEATURE_SCHEMA_V2,
            control_schema=CONTROL_SCHEMA_V1,
        )
        tensors = _feature_tensors(features)
        hidden_input = state.hidden[agent_id : agent_id + 1].detach().clone()
        recurrent_resets[agent_id] = state.sequence_start[agent_id]
        with torch.no_grad():
            _, masked_logits, value, next_hidden = model(
                *tensors,
                torch.tensor([agent_id], dtype=torch.long),
                hidden_input,
            )
        state.hidden[agent_id] = next_hidden[0].detach()
        state.sequence_start[agent_id] = False
        evaluation_order.append(agent_id)
        features_by_agent[agent_id] = features

        if teacher_actions is not None:
            action = teacher_actions[agent_id]
            index = _action_index(
                action, observations[agent_id].get("task_candidates", [])
            )
        elif features.forced_task_action is not None:
            action = {
                "agent_id": agent_id,
                "task_action": features.forced_task_action,
            }
            index = _action_index(action)
        else:
            if evaluation:
                index = int(torch.argmax(masked_logits[0]).item())
            else:
                probabilities = torch.softmax(masked_logits[0], dim=-1)
                index = int(
                    torch.multinomial(
                        probabilities,
                        1,
                        generator=action_generator,
                    ).item()
                )
            action = {
                "agent_id": agent_id,
                "task_action": selector_action(
                    index, observations[agent_id].get("task_candidates", [])
                ),
            }
        if features.forced_task_action is None and not bool(
            features.action_mask[index]
        ):
            raise RuntimeError("IPPO selected an action outside the authoritative mask")
        hidden_inputs[agent_id] = hidden_input[0]
        old_log_probabilities[agent_id] = float(
            torch.log_softmax(masked_logits[0], dim=-1)[index].item()
        )
        old_values[agent_id] = float(value[0].item())
        policy_loss_masks[agent_id] = bool(
            teacher_actions is None
            and features.forced_task_action is None
            and features.policy_loss_mask
        )
        agent_actions.append(action)
        action_indices[agent_id] = index

    if [int(item["agent_id"]) for item in agent_actions] != list(range(AGENT_COUNT)):
        raise AssertionError("IPPO action bundle order drifted")
    return AllSeatDecision(
        schema=IPPO_BOUNDARY_SCHEMA,
        agent_actions=agent_actions,
        features=features_by_agent,
        action_indices=action_indices,
        hidden_inputs=hidden_inputs,
        old_log_probabilities=old_log_probabilities,
        old_values=old_values,
        policy_loss_masks=policy_loss_masks,
        recurrent_resets=recurrent_resets,
        evaluation_order=tuple(evaluation_order),
        model_state_sha256=model_state_digest(model),
    )


def commit_all_seat_boundary(
    state: SharedSeatState,
    decision: AllSeatDecision,
    action_results: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    *,
    tick: int,
) -> None:
    """Commit only accepted submitted actions after the atomic server step."""

    accepted = {
        int(result["agent_id"])
        for result in action_results
        if result.get("accepted", False)
        and type(result.get("agent_id")) is int
    }
    for agent_id in decision.evaluation_order:
        features = decision.features[agent_id]
        index = decision.action_indices[agent_id]
        action = decision.agent_actions[agent_id].get("task_action", {})
        if (
            agent_id in accepted
            and action.get("type") == "SELECT_CANDIDATE_TASK"
            and index < len(observations[agent_id].get("task_candidates", []))
        ):
            task_type = observations[agent_id]["task_candidates"][index]["task_type"]
            state.histories[agent_id].record_selection(str(task_type), tick)
        state.histories[agent_id].record_boundary(features, index)
