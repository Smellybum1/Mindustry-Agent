"""ADR-0137 counterfactual continuation-regret supervision."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import torch
from torch import nn

from mindustry_agents.policies import CandidateNativePlannerV11
from mindustry_agents.process.launcher import RlServerProcess
from mindustry_agents.training.candidate_distill import _canonical_sha256
from mindustry_agents.training.ippo import (
    ACTION_COUNT,
    AGENT_COUNT,
    HIDDEN_WIDTH,
    AllSeatDecision,
    SharedRecurrentSelector,
    SharedSeatState,
    _action_index,
    _feature_tensors,
    commit_all_seat_boundary,
    model_state_digest,
)
from mindustry_agents.training.ippo_artifacts import load_ippo_checkpoint
from mindustry_agents.training.ippo_ppo import sha256_path
from mindustry_agents.training.selector import (
    CONTROL_SCHEMA_V1,
    FEATURE_SCHEMA_V2,
    build_selector_features,
    selector_action,
)


CONFIG_SHA256 = (
    "947b09c84528005d752c976ce220bff51070f9764b243a27b2a387c0f6b9add1"
)
PROTOCOL_SHA256 = (
    "7cb2881bd2ca388e8babef5127ece4ea872464bae61838c023476e13f5110ac7"
)
SOURCE_CONTENT_SHA256 = (
    "55005ab5a0591b2688e32a4819678088f0f8701de920dbf788202539c046b865"
)
SOURCE_MODEL_SHA256 = (
    "7838b9392b32d7dc5867dd53ffed78a77f9094f3492cf0b2ac4406ec551ae0d1"
)
SOURCE_OPTIMIZER_SHA256 = (
    "f3bdf93bf2dfae69842b87ca69f124c1bdda074b05422c02198530a5fdb687bc"
)
ACTION_DESCRIPTOR_WIDTH = 202
GLOBAL_INPUT_WIDTH = 669
GLOBAL_HIDDEN_WIDTH = 128
BUNDLE_INPUT_WIDTH = 1549
HORIZONS = (1, 4, 8, 16)
MODEL_SCHEMA = "frozen_source_descriptor_global_gru_bundle_cost_v1"
MODEL_ARCHITECTURE = {
    "schema": MODEL_SCHEMA,
    "source_action_descriptor_width": ACTION_DESCRIPTOR_WIDTH,
    "action_count_per_seat": ACTION_COUNT,
    "global_input_width": GLOBAL_INPUT_WIDTH,
    "global_gru": [GLOBAL_INPUT_WIDTH, GLOBAL_HIDDEN_WIDTH],
    "bundle_input_width": BUNDLE_INPUT_WIDTH,
    "bundle_cost_head": [BUNDLE_INPUT_WIDTH, 256, 128, 4],
    "final_linear_initialization": "zeros",
}


@dataclass(frozen=True)
class PlannerBundleRanking:
    """Canonical planner-v11 ordering at one immutable boundary."""

    ordered_action_indices: tuple[tuple[int, int, int], ...]
    fractional_rank: dict[tuple[int, int, int], float]
    canonical_actions: list[dict[str, Any]]


@dataclass(frozen=True)
class PreparedBoundary:
    """One provisional all-seat decision and its cost-model tensors."""

    decision: AllSeatDecision
    raw_logits: torch.Tensor
    masked_logits: torch.Tensor
    descriptors: torch.Tensor
    next_private_hidden: dict[int, torch.Tensor]
    global_input: torch.Tensor
    provisional_global_hidden: torch.Tensor
    legal_bundles: tuple[tuple[int, int, int], ...]
    bundle_static_inputs: torch.Tensor
    source_bundle_costs: torch.Tensor
    variable_agents: tuple[int, ...]


@dataclass(frozen=True)
class ContinuationRootExample:
    """The frozen prefix and sampled branch targets for one public root."""

    seed: int
    prefix_global_inputs: torch.Tensor
    prefix_commit_mask: torch.Tensor
    bundle_static_inputs: torch.Tensor
    targets: torch.Tensor
    achieved_horizons: torch.Tensor
    sampled_bundles: tuple[tuple[int, int, int], ...]
    planner_inadmissible: tuple[bool, ...]
    selected_state_sha256: str
    branch_trace_sha256: tuple[str, ...]

    @property
    def branch_rows(self) -> int:
        return int(self.targets.shape[0])


@dataclass
class ContinuationRuntimeState:
    """Reset-local private and global recurrent state."""

    seats: SharedSeatState
    global_hidden: torch.Tensor

    @classmethod
    def fresh(cls) -> "ContinuationRuntimeState":
        return cls(
            seats=SharedSeatState.fresh(),
            global_hidden=torch.zeros(GLOBAL_HIDDEN_WIDTH),
        )


class ContinuationRegretSelector(SharedRecurrentSelector):
    """Frozen source descriptors plus a new recurrent bundle-cost scorer."""

    model_schema = MODEL_SCHEMA

    def __init__(self, source_seed: int, *, new_parameter_seed: int):
        super().__init__(source_seed)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(new_parameter_seed)
            self.global_recurrent_cell = nn.GRUCell(
                GLOBAL_INPUT_WIDTH, GLOBAL_HIDDEN_WIDTH
            )
            self.bundle_cost_head = nn.Sequential(
                nn.Linear(BUNDLE_INPUT_WIDTH, 256),
                nn.Tanh(),
                nn.Linear(256, 128),
                nn.Tanh(),
                nn.Linear(128, len(HORIZONS)),
            )
            nn.init.zeros_(self.bundle_cost_head[-1].weight)
            nn.init.zeros_(self.bundle_cost_head[-1].bias)

    def freeze_source(self) -> None:
        """Exclude all inherited actor parameters from optimization."""

        for name, parameter in self.named_parameters():
            if not name.startswith(
                ("global_recurrent_cell.", "bundle_cost_head.")
            ):
                parameter.requires_grad_(False)

    def new_parameters(self) -> list[nn.Parameter]:
        """Return new trainable parameters in stable module order."""

        return [
            parameter
            for name, parameter in self.named_parameters()
            if name.startswith(
                ("global_recurrent_cell.", "bundle_cost_head.")
            )
        ]

    def forward_with_descriptors(
        self,
        candidates: torch.Tensor,
        scalars: torch.Tensor,
        candidate_present: torch.Tensor,
        action_mask: torch.Tensor,
        agent_ids: torch.Tensor,
        hidden: torch.Tensor,
    ) -> tuple[
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
    ]:
        """Return source outputs and fixed 202-value action descriptors."""

        batch = candidates.shape[0]
        if candidates.shape != (batch, 8, 37):
            raise ValueError("M9 continuation candidates must be [batch,8,37]")
        if scalars.shape != (batch, 160):
            raise ValueError("M9 continuation scalars must be [batch,160]")
        if candidate_present.shape != (batch, 8):
            raise ValueError("M9 continuation presence must be [batch,8]")
        if action_mask.shape != (batch, ACTION_COUNT):
            raise ValueError("M9 continuation action mask drifted")
        if agent_ids.shape != (batch,):
            raise ValueError("M9 continuation agent ids drifted")
        if hidden.shape != (batch, HIDDEN_WIDTH):
            raise ValueError("M9 continuation private hidden drifted")

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
        select_context = torch.cat(
            (
                encoded_candidates,
                other_pooled,
                repeated_hidden,
                repeated_roles,
            ),
            dim=-1,
        )
        select_logits = self.select_head(select_context).squeeze(-1)
        special_context = torch.cat((pooled, next_hidden, roles), dim=-1)
        special_logits = self.special_head(special_context)
        raw_logits = torch.cat((select_logits, special_logits), dim=-1)
        masked_logits = raw_logits.masked_fill(
            ~action_mask, torch.finfo(raw_logits.dtype).min
        )
        value = self.critic(
            torch.cat((encoded_current, pooled, next_hidden, roles), dim=-1)
        ).squeeze(-1)

        zero_code = torch.zeros(
            (batch, 8, 2),
            dtype=select_context.dtype,
            device=select_context.device,
        )
        select_descriptors = torch.cat((select_context, zero_code), dim=-1)
        zero_candidate = torch.zeros_like(pooled)
        special_base = torch.cat(
            (zero_candidate, pooled, next_hidden, roles), dim=-1
        )
        continue_code = torch.tensor(
            [1.0, 0.0],
            dtype=special_base.dtype,
            device=special_base.device,
        ).expand(batch, -1)
        wait_code = torch.tensor(
            [0.0, 1.0],
            dtype=special_base.dtype,
            device=special_base.device,
        ).expand(batch, -1)
        special_descriptors = torch.stack(
            (
                torch.cat((special_base, continue_code), dim=-1),
                torch.cat((special_base, wait_code), dim=-1),
            ),
            dim=1,
        )
        descriptors = torch.cat(
            (select_descriptors, special_descriptors), dim=1
        )
        if descriptors.shape != (batch, ACTION_COUNT, ACTION_DESCRIPTOR_WIDTH):
            raise AssertionError("M9 continuation descriptor shape drifted")
        return raw_logits, masked_logits, value, next_hidden, descriptors

    def forward(
        self,
        candidates: torch.Tensor,
        scalars: torch.Tensor,
        candidate_present: torch.Tensor,
        action_mask: torch.Tensor,
        agent_ids: torch.Tensor,
        hidden: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        raw, masked, value, next_hidden, _ = self.forward_with_descriptors(
            candidates,
            scalars,
            candidate_present,
            action_mask,
            agent_ids,
            hidden,
        )
        return raw, masked, value, next_hidden

    def continuation_hidden(
        self,
        prefix_inputs: torch.Tensor,
        commit_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Apply the global GRU to one or more fixed boundary prefixes."""

        if prefix_inputs.ndim == 2:
            prefix_inputs = prefix_inputs.unsqueeze(0)
        if prefix_inputs.ndim != 3 or prefix_inputs.shape[-1] != GLOBAL_INPUT_WIDTH:
            raise ValueError("M9 continuation prefix input drifted")
        batch, length, _ = prefix_inputs.shape
        hidden = torch.zeros(
            (batch, GLOBAL_HIDDEN_WIDTH),
            dtype=prefix_inputs.dtype,
            device=prefix_inputs.device,
        )
        if commit_mask is not None:
            if commit_mask.ndim == 1:
                commit_mask = commit_mask.unsqueeze(0)
            if commit_mask.shape != (batch, max(0, length - 1)):
                raise ValueError("M9 continuation prefix commit mask drifted")
        for index in range(length):
            provisional = self.global_recurrent_cell(
                prefix_inputs[:, index], hidden
            )
            if index == length - 1:
                hidden = provisional
            elif commit_mask is None:
                hidden = provisional
            else:
                hidden = torch.where(
                    commit_mask[:, index : index + 1], provisional, hidden
                )
        return hidden

    def cost_outputs(
        self,
        bundle_static_inputs: torch.Tensor,
        global_hidden: torch.Tensor,
    ) -> torch.Tensor:
        """Return four source-residual continuation costs."""

        if bundle_static_inputs.ndim == 2:
            bundle_static_inputs = bundle_static_inputs.unsqueeze(0)
        if bundle_static_inputs.ndim != 3:
            raise ValueError("M9 continuation bundle input drifted")
        batch, bundles, static_width = bundle_static_inputs.shape
        if static_width != BUNDLE_INPUT_WIDTH - GLOBAL_HIDDEN_WIDTH:
            raise ValueError("M9 continuation static bundle width drifted")
        if global_hidden.shape != (batch, GLOBAL_HIDDEN_WIDTH):
            raise ValueError("M9 continuation global hidden shape drifted")
        before_hidden = bundle_static_inputs[..., :1414]
        after_hidden = bundle_static_inputs[..., 1414:]
        expanded_hidden = global_hidden[:, None, :].expand(
            batch, bundles, GLOBAL_HIDDEN_WIDTH
        )
        full = torch.cat(
            (before_hidden, expanded_hidden, after_hidden), dim=-1
        )
        residual = self.bundle_cost_head(full)
        source_cost = after_hidden[..., :1]
        return source_cost + residual


def load_continuation_config(path: Path) -> dict[str, Any]:
    """Load ADR-0137's immutable recipe."""

    if sha256_path(path) != CONFIG_SHA256:
        raise ValueError("M9 continuation config digest drifted")
    config = json.loads(path.read_text(encoding="utf-8"))
    collection = config.get("counterfactual_collection", {})
    optimizer = config.get("optimizer", {})
    architecture = config.get("model_architecture", {})
    if (
        config.get("schema")
        != "m9_candidate_native_continuation_regret_config_v1"
        or config.get("candidate_version")
        != "m9-candidate-native-continuation-regret-v1"
        or config.get("confirmation_seed_set") is not None
        or config.get("held_out_seed_set") is not None
        or collection.get("continuation_horizons") != list(HORIZONS)
        or int(collection.get("selected_boundary_zero_based", -1)) != 8
        or int(collection.get("bundles_per_root", 0)) != 8
        or architecture.get("bundle_cost_head") != [1549, 256, 128, 4]
        or int(architecture.get("global_recurrence", {}).get("hidden_width", 0))
        != GLOBAL_HIDDEN_WIDTH
        or optimizer.get("class") != "AdamW"
        or int(optimizer.get("groups", 0)) != 32
        or int(optimizer.get("optimizer_steps_per_group", 0)) != 256
    ):
        raise ValueError("M9 continuation config contract drifted")
    return config


def validate_protocol(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    """Validate the public-only authority packet."""

    path = root / str(config["public_evaluation_protocol"])
    if sha256_path(path) != PROTOCOL_SHA256:
        raise ValueError("M9 continuation protocol digest drifted")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    authority = protocol.get("downstream_authority", {})
    forbidden = (
        "may_select_or_repair_source_checkpoint",
        "may_select_intermediate_checkpoint",
        "may_change_planner_candidates_features_masks_or_scores",
        "may_use_planner_at_inference",
        "may_add_target_identifiers_or_hard_coded_target_pairs",
        "may_target_disagreement_or_outcome",
        "may_sweep_horizon_width_budget_loss_or_optimizer",
        "may_use_reward_return_critic_ppo_or_mappo",
        "may_change_online_planner_or_apply_direct_online_correction",
        "may_access_confirmation_restricted_held_out_or_embargoed_data",
        "may_authorize_human_session",
    )
    if (
        protocol.get("schema")
        != "m9_candidate_native_continuation_regret_public_protocol_v1"
        or protocol.get("config_sha256") != CONFIG_SHA256
        or any(authority.get(key) is not False for key in forbidden)
    ):
        raise ValueError("M9 continuation public authority drifted")
    return protocol


def source_model_and_optimizer(
    root: Path,
    config: dict[str, Any],
) -> tuple[ContinuationRegretSelector, torch.optim.AdamW, dict[str, Any]]:
    """Load and freeze the exact source model; create fresh AdamW."""

    source = config["source_checkpoint"]
    for digest_key, relative in {
        "config_sha256": source["config_path"],
        "file_sha256": source["path"],
        "source_result_sha256": source["source_result"],
        "source_manifest_sha256": source["source_manifest"],
    }.items():
        if sha256_path(root / str(relative)) != source[digest_key]:
            raise ValueError("M9 continuation source identity drifted")
    for evidence in config["public_evidence"].values():
        if "path" in evidence and sha256_path(root / str(evidence["path"])) != evidence[
            "sha256"
        ]:
            raise ValueError("M9 continuation public evidence drifted")

    base = SharedRecurrentSelector(9601)
    payload = load_ippo_checkpoint(
        root / str(source["path"]),
        base,
        expected_config_sha256=str(source["config_sha256"]),
    )
    if (
        payload["checkpoint_content_sha256"] != SOURCE_CONTENT_SHA256
        or payload["model_state_sha256"] != SOURCE_MODEL_SHA256
        or payload["optimizer_state_sha256"] != SOURCE_OPTIMIZER_SHA256
        or model_state_digest(base) != SOURCE_MODEL_SHA256
    ):
        raise ValueError("M9 continuation source checkpoint drifted")
    model = ContinuationRegretSelector(
        9601,
        new_parameter_seed=int(config["rng"]["new_parameter_initialization_seed"]),
    )
    incompatible = model.load_state_dict(base.state_dict(), strict=False)
    expected_prefixes = ("global_recurrent_cell.", "bundle_cost_head.")
    if (
        incompatible.unexpected_keys
        or not incompatible.missing_keys
        or any(
            not key.startswith(expected_prefixes)
            for key in incompatible.missing_keys
        )
    ):
        raise ValueError("M9 continuation inherited model drifted")
    model.freeze_source()
    values = config["optimizer"]
    optimizer = torch.optim.AdamW(
        model.new_parameters(),
        lr=float(values["learning_rate"]),
        betas=tuple(float(item) for item in values["betas"]),
        eps=float(values["epsilon"]),
        weight_decay=float(values["weight_decay"]),
    )
    if optimizer.state:
        raise ValueError("M9 continuation AdamW did not start empty")
    return model, optimizer, payload


def _canonical_indices(
    actions: list[dict[str, Any]], observations: list[dict[str, Any]]
) -> tuple[int, int, int]:
    return tuple(
        _action_index(action, observations[agent_id].get("task_candidates", []))
        for agent_id, action in enumerate(actions)
    )  # type: ignore[return-value]


def planner_bundle_ranking(
    planner: CandidateNativePlannerV11,
    observations: list[dict[str, Any]],
    action_masks: list[dict[str, Any]],
    task_board: list[dict[str, Any]] | None = None,
) -> PlannerBundleRanking:
    """Observe planner-v11's complete admissible ordering without changing it."""

    observer = copy.deepcopy(planner)
    if len(observations) != len(action_masks) or len(observations) != AGENT_COUNT:
        raise ValueError("M9 planner observer requires exactly three seats")
    team = observations[0].get("team", {})
    tick = int(team.get("tick", 0))
    if tick < observer._last_tick:
        observer.reset()
    observer._last_tick = tick
    wave = int(team.get("wave", 0))
    wave_advanced = observer._last_wave is not None and wave > observer._last_wave
    observer._last_wave = wave
    enemy_count = int(team.get("enemy_count", 0))
    time_to_wave = int(team.get("time_to_next_wave", 0))
    defend_lead = int(team.get("defend_lead_ticks", 0))
    active_build = observer._defer_schematics_during_active_build and any(
        task.get("task_type") in {"BUILD_LINE", "BUILD_SCHEMATIC"}
        and task.get("status") in {"CLAIMED", "RUNNING", "BLOCKED"}
        for task in (task_board or [])
    )
    fortification_blocks_line = (
        (
            observer._suppress_line_after_completed_fortification
            or observer._suppress_line_during_active_fortification
        )
        and any(
            task.get("task_type") == "BUILD_SCHEMATIC"
            and task.get("target") == "region expert_fortification_v1"
            and (
                task.get("status") == "COMPLETED"
                or (
                    observer._suppress_line_during_active_fortification
                    and task.get("status") in {"CLAIMED", "RUNNING", "BLOCKED"}
                )
            )
            for task in (task_board or [])
        )
    )
    active_defend_tasks = sum(
        task.get("task_type") == "DEFEND_REGION"
        and task.get("status") in {"CLAIMED", "RUNNING", "BLOCKED"}
        for task in (task_board or [])
    )
    available_defend_slots = (
        None
        if observer._maximum_active_defend_tasks is None
        else max(
            0,
            observer._maximum_active_defend_tasks - active_defend_tasks,
        )
    )

    fixed_actions: list[dict[str, Any] | None] = [None] * AGENT_COUNT
    allocatable: list[int] = []
    options: list[list[dict[str, Any] | None]] = []
    for agent_id, (observation, action_mask) in enumerate(
        zip(observations, action_masks, strict=True)
    ):
        fixed = observer._fixed_action(
            agent_id,
            observation,
            action_mask,
            tick,
            enemy_count,
            time_to_wave,
            defend_lead,
            wave_advanced,
        )
        if fixed is not None:
            fixed_actions[agent_id] = fixed
            continue
        allocatable.append(agent_id)
        candidates = observer._candidates(observation, action_mask)
        if active_build:
            candidates = [
                candidate
                for candidate in candidates
                if candidate.get("task_type") != "BUILD_SCHEMATIC"
            ]
        if fortification_blocks_line:
            candidates = [
                candidate
                for candidate in candidates
                if candidate.get("task_type") != "BUILD_LINE"
            ]
        options.append(candidates + [None])

    ranked: list[tuple[tuple[Any, ...], int, tuple[int, int, int]]] = []
    for order, allocation in enumerate(itertools.product(*options)):
        if observer._conflicts(allocation, available_defend_slots):
            continue
        selected = [item for item in allocation if item is not None]
        phase_total = sum(
            observer._phase_score(agent_id, candidate, team, active_build)
            for agent_id, candidate in zip(
                allocatable, allocation, strict=True
            )
            if candidate is not None
        )
        utility_total = sum(
            float(candidate.get("utility", 0.0)) for candidate in selected
        )
        stable_indices = tuple(
            -int(candidate["index"]) if candidate is not None else -10_000
            for candidate in allocation
        )
        actions = list(fixed_actions)
        for agent_id, candidate in zip(allocatable, allocation, strict=True):
            actions[agent_id] = (
                observer._simple(
                    agent_id,
                    "SELECT_CANDIDATE_TASK",
                    candidate_index=int(candidate["index"]),
                )
                if candidate is not None
                else observer._simple(agent_id, "WAIT")
            )
        complete = [action for action in actions if action is not None]
        if len(complete) != AGENT_COUNT:
            raise AssertionError("M9 planner observer action assembly drifted")
        ranked.append(
            (
                (len(selected), phase_total, utility_total, stable_indices),
                order,
                _canonical_indices(complete, observations),
            )
        )
    ranked.sort(key=lambda item: item[0], reverse=True)
    ordered = tuple(item[2] for item in ranked)
    canonical = planner.actions(observations, action_masks, task_board)
    if not ordered or ordered[0] != _canonical_indices(canonical, observations):
        raise RuntimeError("M9 planner observer changed canonical v11 action")
    denominator = max(1, len(ordered) - 1)
    return PlannerBundleRanking(
        ordered_action_indices=ordered,
        fractional_rank={
            bundle: index / denominator for index, bundle in enumerate(ordered)
        },
        canonical_actions=canonical,
    )


def _legal_bundles(
    masks: torch.Tensor,
    fixed_indices: dict[int, int],
    variable_agents: Sequence[int],
) -> tuple[tuple[int, int, int], ...]:
    choices = [
        [int(index) for index in torch.where(masks[agent_id])[0].tolist()]
        for agent_id in variable_agents
    ]
    if not choices:
        return (
            tuple(fixed_indices.get(agent_id, 9) for agent_id in range(AGENT_COUNT)),
        )  # type: ignore[return-value]
    result = []
    for allocation in itertools.product(*choices):
        complete = [
            fixed_indices.get(agent_id, 9) for agent_id in range(AGENT_COUNT)
        ]
        for agent_id, action in zip(variable_agents, allocation, strict=True):
            complete[agent_id] = action
        result.append(tuple(complete))
    return tuple(result)  # type: ignore[return-value]


def _source_costs(
    legal_bundles: Sequence[tuple[int, int, int]],
    masked_logits: torch.Tensor,
    variable_agents: Sequence[int],
) -> tuple[torch.Tensor, torch.Tensor]:
    scores = torch.tensor(
        [
            sum(
                float(masked_logits[agent_id, bundle[agent_id]].item())
                for agent_id in variable_agents
            )
            for bundle in legal_bundles
        ],
        dtype=torch.float32,
    )
    minimum = torch.min(scores)
    maximum = torch.max(scores)
    costs = (
        torch.zeros_like(scores)
        if bool(maximum == minimum)
        else 1.0 - (scores - minimum) / (maximum - minimum)
    )
    ranks = torch.zeros((len(legal_bundles), AGENT_COUNT), dtype=torch.float32)
    for agent_id in variable_agents:
        legal = sorted({bundle[agent_id] for bundle in legal_bundles})
        ordered = sorted(
            (int(index) for index in legal),
            key=lambda index: (-float(masked_logits[agent_id, index]), index),
        )
        denominator = max(1, len(ordered) - 1)
        values = {action: rank / denominator for rank, action in enumerate(ordered)}
        for row, bundle in enumerate(legal_bundles):
            ranks[row, agent_id] = values[bundle[agent_id]]
    return costs, ranks


def _global_input(
    raw_logits: torch.Tensor,
    masks: torch.Tensor,
    descriptors: torch.Tensor,
    authority: torch.Tensor,
) -> torch.Tensor:
    means = []
    normalized = []
    for agent_id in range(AGENT_COUNT):
        legal = masks[agent_id]
        means.append(descriptors[agent_id, legal].mean(dim=0))
        row = raw_logits[agent_id]
        maximum = row[legal].max()
        normalized.append(
            torch.where(
                legal,
                (row - maximum).clamp(-20.0, 0.0),
                torch.full_like(row, -20.0),
            )
        )
    result = torch.cat(
        (
            torch.cat(means),
            torch.cat(normalized),
            masks.to(torch.float32).reshape(-1),
            authority.to(torch.float32),
        )
    )
    if result.shape != (GLOBAL_INPUT_WIDTH,):
        raise AssertionError("M9 continuation global input width drifted")
    return result


def _static_bundle_inputs(
    legal_bundles: Sequence[tuple[int, int, int]],
    descriptors: torch.Tensor,
    source_costs: torch.Tensor,
    action_ranks: torch.Tensor,
    authority: torch.Tensor,
) -> torch.Tensor:
    rows = []
    for index, bundle in enumerate(legal_bundles):
        chosen = torch.stack(
            [
                descriptors[agent_id, bundle[agent_id]]
                for agent_id in range(AGENT_COUNT)
            ]
        )
        rows.append(
            torch.cat(
                (
                    chosen.reshape(-1),
                    chosen[0] * chosen[1],
                    chosen[0] * chosen[2],
                    chosen[1] * chosen[2],
                    chosen[0] * chosen[1] * chosen[2],
                    source_costs[index : index + 1],
                    action_ranks[index],
                    authority.to(torch.float32),
                )
            )
        )
    result = torch.stack(rows)
    if result.shape[1] != BUNDLE_INPUT_WIDTH - GLOBAL_HIDDEN_WIDTH:
        raise AssertionError("M9 continuation static bundle width drifted")
    return result


def prepare_boundary(
    model: ContinuationRegretSelector,
    state: ContinuationRuntimeState,
    observations: list[dict[str, Any]],
    action_masks: list[dict[str, Any]],
    metadata: dict[str, Any],
    *,
    task_board: list[dict[str, Any]] | None = None,
    boundary_reasons: list[str] | tuple[str, ...] = (),
    selection: str = "source",
    override_bundle: tuple[int, int, int] | None = None,
) -> PreparedBoundary:
    """Prepare one source, cost-model, or explicitly overridden bundle."""

    if selection not in {"source", "cost", "override"}:
        raise ValueError("M9 continuation selection mode drifted")
    state.seats.observe_lifecycle(observations)
    actions: list[dict[str, Any] | None] = [None] * AGENT_COUNT
    features_by_agent: dict[int, Any] = {}
    indices: dict[int, int] = {}
    hidden_inputs: dict[int, torch.Tensor] = {}
    values: dict[int, float] = {}
    policy_masks: dict[int, bool] = {}
    resets: dict[int, bool] = {}
    evaluation_order: list[int] = []
    next_hidden: dict[int, torch.Tensor] = {}
    raw_rows = torch.zeros((AGENT_COUNT, ACTION_COUNT))
    masked_rows = torch.full(
        (AGENT_COUNT, ACTION_COUNT), torch.finfo(torch.float32).min
    )
    descriptor_rows = torch.zeros(
        (AGENT_COUNT, ACTION_COUNT, ACTION_DESCRIPTOR_WIDTH)
    )
    mask_rows = torch.zeros((AGENT_COUNT, ACTION_COUNT), dtype=torch.bool)

    for agent_id in range(AGENT_COUNT):
        if state.seats.dead[agent_id]:
            actions[agent_id] = {
                "agent_id": agent_id,
                "task_action": {"type": "WAIT"},
            }
            indices[agent_id] = 9
            mask_rows[agent_id, 9] = True
            continue
        features = build_selector_features(
            observations,
            action_masks,
            metadata,
            task_board=task_board,
            boundary_reasons=boundary_reasons,
            history=state.seats.histories[agent_id],
            agent_id=agent_id,
            feature_schema=FEATURE_SCHEMA_V2,
            control_schema=CONTROL_SCHEMA_V1,
        )
        hidden_input = state.seats.hidden[agent_id : agent_id + 1].detach().clone()
        resets[agent_id] = state.seats.sequence_start[agent_id]
        with torch.no_grad():
            raw, masked, value, provisional, descriptors = (
                model.forward_with_descriptors(
                    *_feature_tensors(features),
                    torch.tensor([agent_id], dtype=torch.long),
                    hidden_input,
                )
            )
        evaluation_order.append(agent_id)
        features_by_agent[agent_id] = features
        hidden_inputs[agent_id] = hidden_input[0]
        values[agent_id] = float(value[0].item())
        policy_masks[agent_id] = bool(features.policy_loss_mask)
        next_hidden[agent_id] = provisional[0].detach()
        raw_rows[agent_id] = raw[0]
        masked_rows[agent_id] = masked[0]
        descriptor_rows[agent_id] = descriptors[0]
        mask_rows[agent_id] = torch.tensor(features.action_mask)
        if features.forced_task_action is not None:
            action = {
                "agent_id": agent_id,
                "task_action": features.forced_task_action,
            }
            actions[agent_id] = action
            indices[agent_id] = _action_index(action)

    variable_agents = tuple(
        agent_id
        for agent_id in evaluation_order
        if features_by_agent[agent_id].forced_task_action is None
    )
    authority = torch.tensor(
        [agent_id in variable_agents for agent_id in range(AGENT_COUNT)]
    )
    legal = _legal_bundles(mask_rows, indices, variable_agents)
    costs, ranks = _source_costs(legal, masked_rows, variable_agents)
    global_input = _global_input(
        raw_rows, mask_rows, descriptor_rows, authority
    )
    with torch.no_grad():
        provisional_global = model.global_recurrent_cell(
            global_input.unsqueeze(0),
            state.global_hidden.unsqueeze(0),
        )[0]
    static_inputs = _static_bundle_inputs(
        legal, descriptor_rows, costs, ranks, authority
    )
    if selection == "override":
        if override_bundle not in legal:
            raise ValueError("M9 continuation override is not mask legal")
        chosen = override_bundle
    elif selection == "cost":
        with torch.no_grad():
            outputs = model.cost_outputs(
                static_inputs.unsqueeze(0),
                provisional_global.unsqueeze(0),
            )[0]
        chosen = legal[int(torch.argmin(outputs.mean(dim=-1)).item())]
    else:
        source_actions = dict(indices)
        for agent_id in variable_agents:
            source_actions[agent_id] = int(
                torch.argmax(masked_rows[agent_id]).item()
            )
        chosen = tuple(
            source_actions.get(agent_id, 9)
            for agent_id in range(AGENT_COUNT)
        )
        if chosen not in legal:
            raise AssertionError("M9 continuation source bundle drifted")
    for agent_id in variable_agents:
        index = chosen[agent_id]
        actions[agent_id] = {
            "agent_id": agent_id,
            "task_action": selector_action(
                index, observations[agent_id].get("task_candidates", [])
            ),
        }
        indices[agent_id] = index
    if any(action is None for action in actions):
        raise AssertionError("M9 continuation action assembly drifted")
    complete = [action for action in actions if action is not None]
    decision = AllSeatDecision(
        schema="m9_continuation_regret_atomic_all_seat_boundary_v1",
        agent_actions=complete,
        features=features_by_agent,
        action_indices=indices,
        hidden_inputs=hidden_inputs,
        old_log_probabilities={},
        old_values=values,
        policy_loss_masks=policy_masks,
        recurrent_resets=resets,
        evaluation_order=tuple(evaluation_order),
        model_state_sha256=model_state_digest(model),
    )
    return PreparedBoundary(
        decision=decision,
        raw_logits=raw_rows,
        masked_logits=masked_rows,
        descriptors=descriptor_rows,
        next_private_hidden=next_hidden,
        global_input=global_input,
        provisional_global_hidden=provisional_global,
        legal_bundles=legal,
        bundle_static_inputs=static_inputs,
        source_bundle_costs=costs,
        variable_agents=variable_agents,
    )


def commit_boundary(
    state: ContinuationRuntimeState,
    prepared: PreparedBoundary,
    action_results: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    *,
    tick: int,
) -> bool:
    """Commit provisional recurrent state only after accepted atomic actions."""

    accepted = {
        int(item["agent_id"])
        for item in action_results
        if item.get("accepted", False) and type(item.get("agent_id")) is int
    }
    commit_all_seat_boundary(
        state.seats,
        prepared.decision,
        action_results,
        observations,
        tick=tick,
    )
    for agent_id in prepared.decision.evaluation_order:
        if agent_id in accepted:
            state.seats.hidden[agent_id] = prepared.next_private_hidden[agent_id]
            state.seats.sequence_start[agent_id] = False
    all_accepted = all(
        agent_id in accepted for agent_id in prepared.decision.evaluation_order
    )
    if all_accepted:
        state.global_hidden = prepared.provisional_global_hidden
    return all_accepted


def sample_bundles(
    legal_bundles: Sequence[tuple[int, int, int]],
    source_bundle: tuple[int, int, int],
    *,
    seed: int,
    boundary: int = 8,
    count: int = 8,
) -> tuple[tuple[int, int, int], ...]:
    """Apply the frozen source-anchor plus SHA-256 ordering."""

    if source_bundle not in legal_bundles:
        raise ValueError("M9 continuation source bundle is not legal")
    others = [bundle for bundle in legal_bundles if bundle != source_bundle]
    others.sort(
        key=lambda bundle: (
            hashlib.sha256(
                (
                    f"m9-ccr-v1|{seed}|{boundary}|"
                    + ",".join(str(item) for item in bundle)
                ).encode("ascii")
            ).digest(),
            bundle,
        )
    )
    return tuple([source_bundle, *others[: max(0, count - 1)]])


def _selected_state_digest(
    *,
    tick: int,
    observations: list[dict[str, Any]],
    action_masks: list[dict[str, Any]],
    task_board: list[dict[str, Any]],
) -> str:
    return _canonical_sha256(
        {
            "tick": tick,
            "observations": observations,
            "action_masks": action_masks,
            "task_board": task_board,
        }
    )


def _replay_to_selected_boundary(
    env: RlServerProcess,
    model: ContinuationRegretSelector,
    config: dict[str, Any],
    *,
    seed: int,
) -> dict[str, Any]:
    selected = int(
        config["counterfactual_collection"]["selected_boundary_zero_based"]
    )
    reset = env.reset(
        seed,
        scenario_id=str(config["scenario_id"]),
        scenario_version=int(config["scenario_version"]),
        agent_count=AGENT_COUNT,
    )
    runtime = ContinuationRuntimeState.fresh()
    planner = CandidateNativePlannerV11()
    observations = reset.initial_observations
    masks = reset.action_masks
    metadata = reset.metadata
    board: list[dict[str, Any]] = []
    reasons: list[str] = []
    tick = reset.tick
    outcome = reset.outcome
    prefix: list[torch.Tensor] = []
    commits: list[bool] = []
    trace: list[dict[str, Any]] = []
    for boundary in range(selected):
        if outcome != "running":
            raise RuntimeError(
                "M9 continuation root terminated before fixed boundary"
            )
        ranking = planner_bundle_ranking(planner, observations, masks, board)
        prepared = prepare_boundary(
            model,
            runtime,
            observations,
            masks,
            metadata,
            task_board=board,
            boundary_reasons=reasons,
            selection="source",
        )
        source_bundle = tuple(
            prepared.decision.action_indices[agent_id]
            for agent_id in range(AGENT_COUNT)
        )
        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, int(metadata["tick_cap"]) - tick),
            agent_actions=prepared.decision.agent_actions,
            stop_on_decision_event=True,
        )
        accepted = commit_boundary(
            runtime,
            prepared,
            response.action_results,
            observations,
            tick=tick,
        )
        prefix.append(prepared.global_input)
        commits.append(accepted)
        trace.append(
            {
                "boundary": boundary,
                "tick": tick,
                "bundle": source_bundle,
                "planner_admissible": (
                    source_bundle in ranking.fractional_rank
                ),
                "accepted": accepted,
                "state_hash": response.state_hash,
            }
        )
        observations = response.observations
        masks = response.action_masks
        board = response.task_board
        reasons = list(response.decision_boundary.get("reasons", []))
        tick = response.tick
        outcome = response.outcome
    if outcome != "running":
        raise RuntimeError("M9 continuation fixed boundary is terminal")
    prepared = prepare_boundary(
        model,
        runtime,
        observations,
        masks,
        metadata,
        task_board=board,
        boundary_reasons=reasons,
        selection="source",
    )
    prefix.append(prepared.global_input)
    return {
        "reset": reset,
        "runtime": runtime,
        "planner": planner,
        "observations": observations,
        "masks": masks,
        "metadata": metadata,
        "board": board,
        "reasons": reasons,
        "tick": tick,
        "outcome": outcome,
        "prepared": prepared,
        "prefix": torch.stack(prefix),
        "commits": torch.tensor(commits, dtype=torch.bool),
        "selected_state_sha256": _selected_state_digest(
            tick=tick,
            observations=observations,
            action_masks=masks,
            task_board=board,
        ),
        "prefix_trace": trace,
    }


def collect_continuation_root(
    env: RlServerProcess,
    model: ContinuationRegretSelector,
    config: dict[str, Any],
    *,
    seed: int,
) -> ContinuationRootExample:
    """Collect one fixed-state public counterfactual root."""

    baseline = _replay_to_selected_boundary(
        env, model, config, seed=seed
    )
    prepared: PreparedBoundary = baseline["prepared"]
    source_bundle = tuple(
        prepared.decision.action_indices[agent_id]
        for agent_id in range(AGENT_COUNT)
    )
    sampled = sample_bundles(
        prepared.legal_bundles,
        source_bundle,  # type: ignore[arg-type]
        seed=seed,
        count=int(config["counterfactual_collection"]["bundles_per_root"]),
    )
    selected_indices = [
        prepared.legal_bundles.index(bundle) for bundle in sampled
    ]
    ranking = planner_bundle_ranking(
        baseline["planner"],
        baseline["observations"],
        baseline["masks"],
        baseline["board"],
    )
    targets: list[list[float]] = []
    achieved: list[list[int]] = []
    inadmissible: list[bool] = []
    branch_digests: list[str] = []
    for bundle in sampled:
        if bundle not in ranking.fractional_rank:
            targets.append([1.0] * len(HORIZONS))
            achieved.append([1] * len(HORIZONS))
            inadmissible.append(True)
            branch_digests.append(
                _canonical_sha256(
                    {
                        "seed": seed,
                        "bundle": bundle,
                        "planner_inadmissible": True,
                    }
                )
            )
            continue
        replay = _replay_to_selected_boundary(
            env, model, config, seed=seed
        )
        if (
            replay["selected_state_sha256"]
            != baseline["selected_state_sha256"]
            or not torch.equal(replay["prefix"], baseline["prefix"])
            or not torch.equal(replay["commits"], baseline["commits"])
        ):
            raise RuntimeError("M9 continuation selected-state replay drifted")
        branch_ranking = planner_bundle_ranking(
            replay["planner"],
            replay["observations"],
            replay["masks"],
            replay["board"],
        )
        if branch_ranking.fractional_rank != ranking.fractional_rank:
            raise RuntimeError("M9 continuation planner ranking replay drifted")
        branch = prepare_boundary(
            model,
            replay["runtime"],
            replay["observations"],
            replay["masks"],
            replay["metadata"],
            task_board=replay["board"],
            boundary_reasons=replay["reasons"],
            selection="override",
            override_bundle=bundle,
        )
        costs = [float(branch_ranking.fractional_rank[bundle])]
        branch_trace = [
            {
                "boundary": 8,
                "tick": replay["tick"],
                "bundle": bundle,
                "rank_cost": costs[0],
            }
        ]
        response = env.step(
            replay["reset"].episode_id,
            expected_tick=replay["tick"],
            ticks_to_advance=max(
                1,
                int(replay["metadata"]["tick_cap"]) - replay["tick"],
            ),
            agent_actions=branch.decision.agent_actions,
            stop_on_decision_event=True,
        )
        if not commit_boundary(
            replay["runtime"],
            branch,
            response.action_results,
            replay["observations"],
            tick=replay["tick"],
        ):
            raise RuntimeError(
                "M9 continuation observer-admissible branch was rejected"
            )
        observations = response.observations
        masks = response.action_masks
        board = response.task_board
        reasons = list(response.decision_boundary.get("reasons", []))
        tick = response.tick
        outcome = response.outcome
        while outcome == "running" and len(costs) < max(HORIZONS):
            next_ranking = planner_bundle_ranking(
                replay["planner"], observations, masks, board
            )
            next_prepared = prepare_boundary(
                model,
                replay["runtime"],
                observations,
                masks,
                replay["metadata"],
                task_board=board,
                boundary_reasons=reasons,
                selection="source",
            )
            next_bundle = tuple(
                next_prepared.decision.action_indices[agent_id]
                for agent_id in range(AGENT_COUNT)
            )
            if next_bundle not in next_ranking.fractional_rank:
                costs.append(1.0)
                branch_trace.append(
                    {
                        "boundary": 8 + len(costs) - 1,
                        "tick": tick,
                        "bundle": next_bundle,
                        "rank_cost": 1.0,
                        "planner_inadmissible": True,
                    }
                )
                break
            costs.append(float(next_ranking.fractional_rank[next_bundle]))
            next_response = env.step(
                replay["reset"].episode_id,
                expected_tick=tick,
                ticks_to_advance=max(
                    1, int(replay["metadata"]["tick_cap"]) - tick
                ),
                agent_actions=next_prepared.decision.agent_actions,
                stop_on_decision_event=True,
            )
            if not commit_boundary(
                replay["runtime"],
                next_prepared,
                next_response.action_results,
                observations,
                tick=tick,
            ):
                raise RuntimeError(
                    "M9 continuation observer-admissible continuation "
                    "was rejected"
                )
            branch_trace.append(
                {
                    "boundary": 8 + len(costs) - 1,
                    "tick": tick,
                    "bundle": next_bundle,
                    "rank_cost": costs[-1],
                    "state_hash": next_response.state_hash,
                }
            )
            observations = next_response.observations
            masks = next_response.action_masks
            board = next_response.task_board
            reasons = list(
                next_response.decision_boundary.get("reasons", [])
            )
            tick = next_response.tick
            outcome = next_response.outcome
        row_targets = []
        row_achieved = []
        for horizon in HORIZONS:
            count = min(horizon, len(costs))
            row_targets.append(sum(costs[:count]) / count)
            row_achieved.append(count)
        targets.append(row_targets)
        achieved.append(row_achieved)
        inadmissible.append(False)
        branch_digests.append(_canonical_sha256(branch_trace))
    return ContinuationRootExample(
        seed=seed,
        prefix_global_inputs=baseline["prefix"],
        prefix_commit_mask=baseline["commits"],
        bundle_static_inputs=prepared.bundle_static_inputs[selected_indices],
        targets=torch.tensor(targets, dtype=torch.float32),
        achieved_horizons=torch.tensor(achieved, dtype=torch.int64),
        sampled_bundles=sampled,
        planner_inadmissible=tuple(inadmissible),
        selected_state_sha256=baseline["selected_state_sha256"],
        branch_trace_sha256=tuple(branch_digests),
    )


def continuation_update(
    model: ContinuationRegretSelector,
    optimizer: torch.optim.Optimizer,
    examples: Sequence[ContinuationRootExample],
    config: dict[str, Any],
    generator: torch.Generator,
) -> dict[str, float]:
    """Apply the frozen replayed Smooth-L1 objective."""

    if not examples:
        raise ValueError("M9 continuation update has no examples")
    rows = [
        (example, index)
        for example in examples
        for index in range(example.branch_rows)
    ]
    values = config["optimizer"]
    steps = int(values["optimizer_steps_per_group"])
    batch_size = int(values["branch_rows_per_minibatch"])
    loss_total = 0.0
    maximum_gradient = 0.0
    for _ in range(steps):
        selected = torch.randint(
            len(rows), (batch_size,), generator=generator
        ).tolist()
        batch_examples = [rows[int(index)] for index in selected]
        prefix = torch.stack(
            [example.prefix_global_inputs for example, _ in batch_examples]
        )
        commits = torch.stack(
            [example.prefix_commit_mask for example, _ in batch_examples]
        )
        static = torch.stack(
            [
                example.bundle_static_inputs[row]
                for example, row in batch_examples
            ]
        ).unsqueeze(1)
        targets = torch.stack(
            [example.targets[row] for example, row in batch_examples]
        )
        hidden = model.continuation_hidden(prefix, commits)
        predictions = model.cost_outputs(static, hidden)[:, 0]
        loss = torch.nn.functional.smooth_l1_loss(
            predictions,
            targets,
            beta=float(values["smooth_l1_beta"]),
        )
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        gradient = torch.nn.utils.clip_grad_norm_(
            model.new_parameters(),
            float(values["maximum_gradient_norm"]),
        )
        optimizer.step()
        loss_total += float(loss.item())
        maximum_gradient = max(maximum_gradient, float(gradient))
    return {
        "mean_loss": loss_total / steps,
        "maximum_gradient_norm": maximum_gradient,
        "optimizer_steps": float(steps),
        "replay_roots": float(len(examples)),
        "replay_branch_rows": float(len(rows)),
    }
