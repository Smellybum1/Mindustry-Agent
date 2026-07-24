"""ADR-0135 candidate-native joint-bundle supervision."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import torch
from torch import nn

from mindustry_agents.policies import CandidateNativePlannerV11
from mindustry_agents.process.launcher import RlServerProcess
from mindustry_agents.training.candidate_distill import _canonical_sha256
from mindustry_agents.training.candidate_on_policy_relabel import teacher_labels
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
from mindustry_agents.training.ippo_ppo import IPPOTransition, sha256_path
from mindustry_agents.training.selector import (
    CONTROL_SCHEMA_V1,
    FEATURE_SCHEMA_V2,
    build_selector_features,
    selector_action,
)


CONFIG_SHA256 = (
    "c8138e9d26b8addcd821068ff93b02ecdec03b1053cc8ecf7be2f40b6b3ce0b4"
)
PROTOCOL_SHA256 = (
    "f3a9b9eecfaeae0858ac46db52e8eea27a6927a2b4ba688d22fcaaab5e27a98b"
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
PAIRWISE_INPUT_WIDTH = ACTION_DESCRIPTOR_WIDTH * 2
PAIRWISE_HIDDEN_WIDTH = 64
ACTOR_LABEL_BUDGET = 256
MODEL_SCHEMA = "ippo_shared_recurrent_selector_joint_bundle_v1"
MODEL_ARCHITECTURE = {
    "schema": MODEL_SCHEMA,
    "inherited_architecture": "ippo_shared_recurrent_selector_v1",
    "inherited_parameters_exact": True,
    "inherited_private_hidden_state": True,
    "joint_input": (
        "all_actor_authoritative_seat_action_descriptors_from_one_"
        "immutable_pre_step_boundary"
    ),
    "pairwise_head": [404, 64, 1],
    "pairwise_aggregation": "sum_over_unordered_variable_seat_pairs",
    "action_count_per_seat": ACTION_COUNT,
    "maximum_bundle_count": 1000,
    "hidden_state": "private_per_seat_zero_on_reset_or_death",
}


@dataclass(frozen=True)
class JointBundleBoundary:
    """One atomic supervised boundary with one to three variable seats."""

    transitions: tuple[IPPOTransition, ...]
    student_actions: tuple[int, ...]

    @property
    def actor_labels(self) -> int:
        return len(self.transitions)


@dataclass(frozen=True)
class JointBundleEpisode:
    """One deterministic student-controlled public training episode."""

    seed: int
    outcome: str
    tick: int
    core_health: float
    boundaries: tuple[JointBundleBoundary, ...]
    actor_labels: int
    forced_controls: int
    student_teacher_matches: int
    rejected_student_actions: int
    trace_sha256: str


class JointBundleSelector(SharedRecurrentSelector):
    """Inherited selector plus simultaneous cross-seat compatibility."""

    model_schema = MODEL_SCHEMA

    def __init__(self, seed: int, *, pairwise_head_seed: int):
        super().__init__(seed)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(pairwise_head_seed)
            self.pairwise_head = nn.Sequential(
                nn.Linear(PAIRWISE_INPUT_WIDTH, PAIRWISE_HIDDEN_WIDTH),
                nn.Tanh(),
                nn.Linear(PAIRWISE_HIDDEN_WIDTH, 1),
            )
            nn.init.zeros_(self.pairwise_head[2].weight)
            nn.init.zeros_(self.pairwise_head[2].bias)

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
        """Return inherited outputs plus fixed per-action descriptors."""

        batch = candidates.shape[0]
        if candidates.shape != (batch, 8, 37):
            raise ValueError("M9 joint-bundle candidates must be [batch,8,37]")
        if scalars.shape != (batch, 160):
            raise ValueError("M9 joint-bundle scalars must be [batch,160]")
        if candidate_present.shape != (batch, 8):
            raise ValueError("M9 joint-bundle presence must be [batch,8]")
        if action_mask.shape != (batch, ACTION_COUNT):
            raise ValueError("M9 joint-bundle action mask drifted")
        if agent_ids.shape != (batch,):
            raise ValueError("M9 joint-bundle agent ids drifted")
        if hidden.shape != (batch, HIDDEN_WIDTH):
            raise ValueError("M9 joint-bundle hidden state drifted")
        if bool(((agent_ids < 0) | (agent_ids >= AGENT_COUNT)).any()):
            raise ValueError("M9 joint-bundle agent id is out of range")

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
            raise AssertionError("M9 joint-bundle descriptor shape drifted")
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

    def pairwise_matrix(
        self, left: torch.Tensor, right: torch.Tensor
    ) -> torch.Tensor:
        """Score all ordered action pairs for two ascending-id seats."""

        if (
            left.ndim != 3
            or right.ndim != 3
            or left.shape != right.shape
            or left.shape[1:] != (ACTION_COUNT, ACTION_DESCRIPTOR_WIDTH)
        ):
            raise ValueError("M9 joint-bundle pair descriptors drifted")
        batch = left.shape[0]
        left_grid = left[:, :, None, :].expand(
            batch, ACTION_COUNT, ACTION_COUNT, ACTION_DESCRIPTOR_WIDTH
        )
        right_grid = right[:, None, :, :].expand(
            batch, ACTION_COUNT, ACTION_COUNT, ACTION_DESCRIPTOR_WIDTH
        )
        return self.pairwise_head(
            torch.cat((left_grid, right_grid), dim=-1)
        ).squeeze(-1)

    def joint_scores(
        self,
        masked_logits: torch.Tensor,
        descriptors: torch.Tensor,
    ) -> torch.Tensor:
        """Return flattened legal bundle logits for one to three seats."""

        if masked_logits.ndim != 3:
            raise ValueError("M9 joint-bundle logits must be [batch,seats,10]")
        batch, seats, actions = masked_logits.shape
        if seats < 1 or seats > AGENT_COUNT or actions != ACTION_COUNT:
            raise ValueError("M9 joint-bundle variable seat count drifted")
        if descriptors.shape != (
            batch,
            seats,
            ACTION_COUNT,
            ACTION_DESCRIPTOR_WIDTH,
        ):
            raise ValueError("M9 joint-bundle descriptor batch drifted")
        if seats == 1:
            return masked_logits[:, 0, :]
        pair01 = self.pairwise_matrix(
            descriptors[:, 0], descriptors[:, 1]
        )
        if seats == 2:
            scores = (
                masked_logits[:, 0, :, None]
                + masked_logits[:, 1, None, :]
                + pair01
            )
            return scores.reshape(batch, ACTION_COUNT**2)
        pair02 = self.pairwise_matrix(
            descriptors[:, 0], descriptors[:, 2]
        )
        pair12 = self.pairwise_matrix(
            descriptors[:, 1], descriptors[:, 2]
        )
        scores = (
            masked_logits[:, 0, :, None, None]
            + masked_logits[:, 1, None, :, None]
            + masked_logits[:, 2, None, None, :]
            + pair01[:, :, :, None]
            + pair02[:, :, None, :]
            + pair12[:, None, :, :]
        )
        return scores.reshape(batch, ACTION_COUNT**3)


def _bundle_index(actions: Sequence[int]) -> int:
    result = 0
    for action in actions:
        if action < 0 or action >= ACTION_COUNT:
            raise ValueError("M9 joint-bundle action is out of range")
        result = result * ACTION_COUNT + int(action)
    return result


def _bundle_actions(index: int, seats: int) -> tuple[int, ...]:
    if seats < 1 or seats > AGENT_COUNT:
        raise ValueError("M9 joint-bundle seat count is invalid")
    if index < 0 or index >= ACTION_COUNT**seats:
        raise ValueError("M9 joint-bundle index is out of range")
    actions = [0] * seats
    for position in range(seats - 1, -1, -1):
        index, actions[position] = divmod(index, ACTION_COUNT)
    return tuple(actions)


def load_joint_bundle_config(path: Path) -> dict[str, Any]:
    """Load ADR-0135's immutable recipe."""

    if sha256_path(path) != CONFIG_SHA256:
        raise ValueError("M9 joint-bundle config digest drifted")
    config = json.loads(path.read_text(encoding="utf-8"))
    joint = config.get("joint_bundle", {})
    if (
        config.get("schema")
        != "m9_candidate_native_joint_bundle_config_v1"
        or config.get("candidate_version")
        != "m9-candidate-native-joint-bundle-v1"
        or config.get("confirmation_seed_set") is not None
        or config.get("held_out_seed_set") is not None
        or int(config.get("continuation_updates", 0)) != 32
        or int(config.get("episodes_per_update", 0)) != 64
        or int(config.get("actor_label_budget_per_minibatch", 0))
        != ACTOR_LABEL_BUDGET
        or joint.get("pairwise_head") != [404, 64, 1]
        or float(joint.get("pairwise_scale", -1)) != 1.0
        or int(joint.get("maximum_legal_bundle_size", 0)) != 1000
        or config.get("model_architecture") != MODEL_ARCHITECTURE
    ):
        raise ValueError("M9 joint-bundle config contract drifted")
    return config


def validate_protocol(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    """Validate the immutable public-only authority packet."""

    path = root / str(config["public_evaluation_protocol"])
    if sha256_path(path) != PROTOCOL_SHA256:
        raise ValueError("M9 joint-bundle protocol digest drifted")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    authority = protocol.get("downstream_authority", {})
    if (
        protocol.get("schema")
        != "m9_candidate_native_joint_bundle_public_protocol_v1"
        or protocol.get("config_sha256") != CONFIG_SHA256
        or any(
            authority.get(key) is not False
            for key in (
                "may_select_source_checkpoint",
                "may_repair_source_checkpoint",
                "may_add_target_identifiers",
                "may_change_planner_candidates_features_or_masks",
                "may_sweep_pairwise_width_scale_loss_or_minibatch_budget",
                "may_use_reward_critic_ppo_or_mappo",
                "may_access_confirmation",
                "may_access_held_out",
                "may_authorize_human_session",
            )
        )
    ):
        raise ValueError("M9 joint-bundle public authority drifted")
    return protocol


def source_model_and_optimizer(
    root: Path,
    config: dict[str, Any],
) -> tuple[JointBundleSelector, torch.optim.Adam, dict[str, Any]]:
    """Load exact inherited state and append the empty pairwise group."""

    source = config["source_checkpoint"]
    bound_paths = {
        "config_sha256": source["config_path"],
        "file_sha256": source["path"],
        "source_result_sha256": source["source_result"],
        "source_manifest_sha256": source["source_manifest"],
    }
    for digest_key, relative in bound_paths.items():
        if sha256_path(root / str(relative)) != source[digest_key]:
            raise ValueError("M9 joint-bundle source identity drifted")
    for evidence in config["public_evidence"].values():
        if sha256_path(root / str(evidence["path"])) != evidence["sha256"]:
            raise ValueError("M9 joint-bundle public evidence drifted")

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
        raise ValueError("M9 joint-bundle source checkpoint drifted")
    model = JointBundleSelector(
        9601, pairwise_head_seed=int(config["pairwise_head_init_seed"])
    )
    incompatible = model.load_state_dict(base.state_dict(), strict=False)
    expected_missing = {
        "pairwise_head.0.weight",
        "pairwise_head.0.bias",
        "pairwise_head.2.weight",
        "pairwise_head.2.bias",
    }
    if (
        set(incompatible.missing_keys) != expected_missing
        or incompatible.unexpected_keys
    ):
        raise ValueError("M9 joint-bundle inherited model drifted")
    inherited = [
        parameter
        for name, parameter in model.named_parameters()
        if not name.startswith("pairwise_head.")
    ]
    new_parameters = [
        parameter
        for name, parameter in model.named_parameters()
        if name.startswith("pairwise_head.")
    ]
    optimizer = torch.optim.Adam(
        inherited,
        lr=float(config["learning_rate"]),
        eps=float(config["adam_epsilon"]),
    )
    optimizer.load_state_dict(payload["optimizer_state"])
    optimizer.add_param_group(
        {
            "params": new_parameters,
            "lr": float(config["learning_rate"]),
            "eps": float(config["adam_epsilon"]),
        }
    )
    if optimizer.state_dict()["state"].keys() != payload[
        "optimizer_state"
    ]["state"].keys():
        raise ValueError("M9 joint-bundle inherited Adam state drifted")
    return model, optimizer, payload


def joint_decide_all_seats(
    model: JointBundleSelector,
    state: SharedSeatState,
    observations: list[dict[str, Any]],
    action_masks: list[dict[str, Any]],
    metadata: dict[str, Any],
    *,
    task_board: list[dict[str, Any]] | None = None,
    boundary_reasons: list[str] | tuple[str, ...] = (),
) -> AllSeatDecision:
    """Choose one simultaneous deterministic legal bundle."""

    if len(observations) != AGENT_COUNT or len(action_masks) != AGENT_COUNT:
        raise ValueError("M9 joint-bundle requires exactly three seats")
    state.observe_lifecycle(observations)
    agent_actions: list[dict[str, Any] | None] = [None] * AGENT_COUNT
    features_by_agent: dict[int, Any] = {}
    action_indices: dict[int, int] = {}
    hidden_inputs: dict[int, torch.Tensor] = {}
    old_log_probabilities: dict[int, float] = {}
    old_values: dict[int, float] = {}
    policy_loss_masks: dict[int, bool] = {}
    recurrent_resets: dict[int, bool] = {}
    evaluation_order: list[int] = []
    masked_by_agent: dict[int, torch.Tensor] = {}
    descriptors_by_agent: dict[int, torch.Tensor] = {}

    for agent_id in range(AGENT_COUNT):
        if state.dead[agent_id]:
            agent_actions[agent_id] = {
                "agent_id": agent_id,
                "task_action": {"type": "WAIT"},
            }
            action_indices[agent_id] = 9
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
        hidden_input = state.hidden[agent_id : agent_id + 1].detach().clone()
        recurrent_resets[agent_id] = state.sequence_start[agent_id]
        with torch.no_grad():
            _, masked, value, next_hidden, descriptors = (
                model.forward_with_descriptors(
                    *_feature_tensors(features),
                    torch.tensor([agent_id], dtype=torch.long),
                    hidden_input,
                )
            )
        state.hidden[agent_id] = next_hidden[0].detach()
        state.sequence_start[agent_id] = False
        evaluation_order.append(agent_id)
        features_by_agent[agent_id] = features
        hidden_inputs[agent_id] = hidden_input[0]
        old_values[agent_id] = float(value[0].item())
        masked_by_agent[agent_id] = masked[0]
        descriptors_by_agent[agent_id] = descriptors[0]
        variable = features.forced_task_action is None
        policy_loss_masks[agent_id] = bool(features.policy_loss_mask)
        if not variable:
            forced_action = features.forced_task_action
            if forced_action is None:
                raise RuntimeError("M9 joint-bundle nonvariable seat drifted")
            agent_actions[agent_id] = {
                "agent_id": agent_id,
                "task_action": forced_action,
            }
            action_indices[agent_id] = _action_index(
                agent_actions[agent_id]  # type: ignore[arg-type]
            )

    variable_agents = [
        agent_id
        for agent_id in evaluation_order
        if features_by_agent[agent_id].forced_task_action is None
    ]
    if variable_agents:
        masked = torch.stack(
            [masked_by_agent[agent_id] for agent_id in variable_agents]
        )[None, :]
        descriptors = torch.stack(
            [descriptors_by_agent[agent_id] for agent_id in variable_agents]
        )[None, :]
        with torch.no_grad():
            scores = model.joint_scores(masked, descriptors)
        chosen = _bundle_actions(
            int(torch.argmax(scores[0]).item()), len(variable_agents)
        )
        for agent_id, index in zip(
            variable_agents, chosen, strict=True
        ):
            features = features_by_agent[agent_id]
            if not bool(features.action_mask[index]):
                raise RuntimeError(
                    "M9 joint-bundle selected outside authoritative mask"
                )
            agent_actions[agent_id] = {
                "agent_id": agent_id,
                "task_action": selector_action(
                    index, observations[agent_id].get("task_candidates", [])
                ),
            }
            action_indices[agent_id] = index

    for agent_id in evaluation_order:
        index = action_indices[agent_id]
        old_log_probabilities[agent_id] = float(
            torch.log_softmax(masked_by_agent[agent_id], dim=-1)[index].item()
        )
    if any(action is None for action in agent_actions):
        raise AssertionError("M9 joint-bundle action assembly drifted")
    actions = [action for action in agent_actions if action is not None]
    return AllSeatDecision(
        schema="m9_joint_bundle_atomic_all_seat_boundary_v1",
        agent_actions=actions,
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


def collect_joint_bundle_episode(
    env: RlServerProcess,
    model: JointBundleSelector,
    config: dict[str, Any],
    *,
    seed: int,
) -> JointBundleEpisode:
    """Collect one public student-state joint-label episode."""

    reset = env.reset(
        seed,
        scenario_id=str(config["scenario_id"]),
        scenario_version=int(config["scenario_version"]),
        agent_count=AGENT_COUNT,
    )
    planner = CandidateNativePlannerV11()
    state = SharedSeatState.fresh()
    observations = reset.initial_observations
    masks = reset.action_masks
    metadata = reset.metadata
    board: list[dict[str, Any]] = []
    reasons: list[str] = []
    tick = reset.tick
    outcome = reset.outcome
    boundaries: list[JointBundleBoundary] = []
    labels_seen = 0
    forced = 0
    matches = 0
    rejected = 0
    trace: list[dict[str, Any]] = []

    while outcome == "running" and tick < int(metadata["tick_cap"]):
        teacher = planner.actions(observations, masks, board)
        decision = joint_decide_all_seats(
            model,
            state,
            observations,
            masks,
            metadata,
            task_board=board,
            boundary_reasons=reasons,
        )
        labels = teacher_labels(decision, teacher, observations)
        supervised_agents = sorted(labels)
        forced += len(decision.evaluation_order) - len(supervised_agents)
        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, int(metadata["tick_cap"]) - tick),
            agent_actions=decision.agent_actions,
            stop_on_decision_event=True,
        )
        rejected += sum(
            not result.get("accepted", False)
            for result in response.action_results
        )
        commit_all_seat_boundary(
            state,
            decision,
            response.action_results,
            observations,
            tick=tick,
        )
        advanced = int(
            response.decision_boundary.get(
                "advanced_ticks", response.tick - tick
            )
        )
        done = response.outcome != "running"
        transitions = []
        student_actions = []
        for agent_id in supervised_agents:
            features = decision.features[agent_id]
            label = labels[agent_id]
            student_action = decision.action_indices[agent_id]
            matches += int(student_action == label)
            labels_seen += 1
            student_actions.append(student_action)
            transitions.append(
                IPPOTransition(
                    agent_id=agent_id,
                    candidates=torch.tensor(
                        features.candidates, dtype=torch.float32
                    ),
                    scalars=torch.tensor(
                        features.scalars, dtype=torch.float32
                    ),
                    candidate_present=torch.tensor(
                        features.candidate_present, dtype=torch.bool
                    ),
                    action_mask=torch.tensor(
                        features.action_mask, dtype=torch.bool
                    ),
                    hidden_input=decision.hidden_inputs[agent_id],
                    action=label,
                    old_log_prob=0.0,
                    old_value=decision.old_values[agent_id],
                    team_reward=0.0,
                    individual_reward=0.0,
                    advanced_ticks=advanced,
                    done=done,
                    policy_loss_mask=True,
                    recurrent_reset=decision.recurrent_resets[agent_id],
                )
            )
        if transitions:
            boundaries.append(
                JointBundleBoundary(
                    transitions=tuple(transitions),
                    student_actions=tuple(student_actions),
                )
            )
        trace.append(
            {
                "tick": tick,
                "next_tick": response.tick,
                "student_actions": decision.agent_actions,
                "teacher_labels": [labels[key] for key in sorted(labels)],
                "supervised_agents": supervised_agents,
                "action_results": response.action_results,
                "state_hash": response.state_hash,
                "outcome": response.outcome,
            }
        )
        observations = response.observations
        masks = response.action_masks
        board = response.task_board
        reasons = list(response.decision_boundary.get("reasons", []))
        tick = response.tick
        outcome = response.outcome

    if outcome == "running" or not boundaries:
        raise RuntimeError("M9 joint-bundle episode was incomplete")
    return JointBundleEpisode(
        seed=seed,
        outcome=outcome,
        tick=tick,
        core_health=float(observations[0]["team"]["core_health"]),
        boundaries=tuple(boundaries),
        actor_labels=labels_seen,
        forced_controls=forced,
        student_teacher_matches=matches,
        rejected_student_actions=rejected,
        trace_sha256=_canonical_sha256(trace),
    )


def _packed_minibatches(
    boundaries: Sequence[JointBundleBoundary],
    order: torch.Tensor,
    label_budget: int,
) -> list[list[JointBundleBoundary]]:
    """Pack whole boundaries without crossing the frozen label budget."""

    if label_budget < AGENT_COUNT:
        raise ValueError("M9 joint-bundle label budget is too small")
    result: list[list[JointBundleBoundary]] = []
    current: list[JointBundleBoundary] = []
    labels = 0
    for raw_index in order.tolist():
        boundary = boundaries[int(raw_index)]
        if boundary.actor_labels < 1 or boundary.actor_labels > AGENT_COUNT:
            raise ValueError("M9 joint-bundle boundary label count drifted")
        if current and labels + boundary.actor_labels > label_budget:
            result.append(current)
            current = []
            labels = 0
        current.append(boundary)
        labels += boundary.actor_labels
    if current:
        result.append(current)
    return result


def _group_joint_nll(
    model: JointBundleSelector,
    boundaries: Sequence[JointBundleBoundary],
) -> tuple[torch.Tensor, int, int, int]:
    """Return summed joint NLL and deterministic accuracy counts."""

    if not boundaries:
        raise ValueError("M9 joint-bundle group is empty")
    seats = boundaries[0].actor_labels
    if any(item.actor_labels != seats for item in boundaries):
        raise ValueError("M9 joint-bundle group seat count drifted")
    transitions = [
        transition
        for boundary in boundaries
        for transition in boundary.transitions
    ]
    candidates = torch.stack([item.candidates for item in transitions])
    scalars = torch.stack([item.scalars for item in transitions])
    present = torch.stack([item.candidate_present for item in transitions])
    masks = torch.stack([item.action_mask for item in transitions])
    agent_ids = torch.tensor(
        [item.agent_id for item in transitions], dtype=torch.long
    )
    hidden = torch.stack(
        [item.hidden_input for item in transitions]
    ).detach()
    _, masked, _, _, descriptors = model.forward_with_descriptors(
        candidates, scalars, present, masks, agent_ids, hidden
    )
    batch = len(boundaries)
    masked = masked.reshape(batch, seats, ACTION_COUNT)
    descriptors = descriptors.reshape(
        batch, seats, ACTION_COUNT, ACTION_DESCRIPTOR_WIDTH
    )
    scores = model.joint_scores(masked, descriptors)
    targets = torch.tensor(
        [
            _bundle_index(
                [transition.action for transition in boundary.transitions]
            )
            for boundary in boundaries
        ],
        dtype=torch.long,
    )
    if not bool(
        torch.stack(
            [
                transition.action_mask[transition.action]
                for transition in transitions
            ]
        ).all()
    ):
        raise ValueError("M9 joint-bundle teacher target is masked")
    nll = -torch.log_softmax(scores, dim=-1)[
        torch.arange(batch), targets
    ]
    predictions = torch.argmax(scores, dim=-1)
    bundle_correct = int((predictions == targets).sum().item())
    seat_correct = 0
    for prediction, boundary in zip(
        predictions.tolist(), boundaries, strict=True
    ):
        predicted = _bundle_actions(int(prediction), seats)
        expected = tuple(
            transition.action for transition in boundary.transitions
        )
        seat_correct += sum(
            left == right
            for left, right in zip(predicted, expected, strict=True)
        )
    return nll.sum(), batch * seats, bundle_correct, seat_correct


def joint_bundle_update(
    model: JointBundleSelector,
    optimizer: torch.optim.Optimizer,
    episodes: Sequence[JointBundleEpisode],
    config: dict[str, Any],
    generator: torch.Generator,
) -> dict[str, float]:
    """Apply the frozen normalized legal joint-bundle NLL."""

    boundaries = [
        boundary for episode in episodes for boundary in episode.boundaries
    ]
    if not boundaries:
        raise ValueError("M9 joint-bundle update has no boundaries")
    epochs = int(config["epochs_per_update"])
    label_budget = int(config["actor_label_budget_per_minibatch"])
    loss_total = 0.0
    batches = 0
    presentations = 0
    bundle_presentations = 0
    bundle_correct = 0
    seat_correct = 0
    for _ in range(epochs):
        order = torch.randperm(len(boundaries), generator=generator)
        for minibatch in _packed_minibatches(
            boundaries, order, label_budget
        ):
            loss_sum: torch.Tensor | None = None
            labels = 0
            for seats in range(1, AGENT_COUNT + 1):
                group = [
                    boundary
                    for boundary in minibatch
                    if boundary.actor_labels == seats
                ]
                if not group:
                    continue
                group_loss, group_labels, correct, seat_hits = (
                    _group_joint_nll(model, group)
                )
                loss_sum = (
                    group_loss
                    if loss_sum is None
                    else loss_sum + group_loss
                )
                labels += group_labels
                bundle_presentations += len(group)
                bundle_correct += correct
                seat_correct += seat_hits
            if loss_sum is None or labels < 1 or labels > label_budget:
                raise ValueError("M9 joint-bundle minibatch packing drifted")
            loss = loss_sum / labels
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(), float(config["max_grad_norm"])
            )
            optimizer.step()
            loss_total += float(loss.item())
            batches += 1
            presentations += labels
    labels = sum(boundary.actor_labels for boundary in boundaries)
    return {
        "joint_bundle_nll": loss_total / max(1, batches),
        "batches": float(batches),
        "atomic_boundaries": float(len(boundaries)),
        "one_seat_boundaries": float(
            sum(item.actor_labels == 1 for item in boundaries)
        ),
        "two_seat_boundaries": float(
            sum(item.actor_labels == 2 for item in boundaries)
        ),
        "three_seat_boundaries": float(
            sum(item.actor_labels == 3 for item in boundaries)
        ),
        "labels": float(labels),
        "presentations": float(presentations),
        "bundle_presentations": float(bundle_presentations),
        "bundle_top1_accuracy": bundle_correct
        / max(1, bundle_presentations),
        "seat_top1_accuracy": seat_correct / max(1, presentations),
    }


def evaluate_joint_episode(
    env: RlServerProcess,
    model: JointBundleSelector,
    config: dict[str, Any],
    *,
    seed: int,
) -> dict[str, Any]:
    """Evaluate one deterministic joint-bundle episode."""

    reset = env.reset(
        seed,
        scenario_id=str(config["scenario_id"]),
        scenario_version=int(config["scenario_version"]),
        agent_count=AGENT_COUNT,
    )
    state = SharedSeatState.fresh()
    observations = reset.initial_observations
    masks = reset.action_masks
    metadata = reset.metadata
    board: list[dict[str, Any]] = []
    reasons: list[str] = []
    tick = reset.tick
    outcome = reset.outcome
    trace: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}
    while outcome == "running" and tick < int(metadata["tick_cap"]):
        decision = joint_decide_all_seats(
            model,
            state,
            observations,
            masks,
            metadata,
            task_board=board,
            boundary_reasons=reasons,
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
        trace.append(
            {
                "tick": tick,
                "next_tick": response.tick,
                "actions": decision.agent_actions,
                "action_results": response.action_results,
                "state_hash": response.state_hash,
                "outcome": response.outcome,
            }
        )
        observations = response.observations
        masks = response.action_masks
        board = response.task_board
        reasons = list(response.decision_boundary.get("reasons", []))
        tick = response.tick
        outcome = response.outcome
        metrics = response.coordination_metrics
    if outcome == "running":
        raise RuntimeError("M9 joint-bundle evaluation was incomplete")
    return {
        "seed": seed,
        "outcome": outcome,
        "tick": tick,
        "core_health": float(observations[0]["team"]["core_health"]),
        "team_idle_fraction": float(metrics["idle_fraction"]),
        "trace_sha256": _canonical_sha256(trace),
    }
