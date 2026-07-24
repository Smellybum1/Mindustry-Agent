"""ADR-0133 trajectory-plan model, collector, and optimizer."""

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
from mindustry_agents.training.candidate_sequence_relabel import (
    supervised_sequence_windows,
)
from mindustry_agents.training.ippo import (
    SharedRecurrentSelector,
    SharedSeatState,
    canonical_teacher_bundle,
    commit_all_seat_boundary,
    decide_all_seats,
    model_state_digest,
)
from mindustry_agents.training.ippo_artifacts import load_ippo_checkpoint
from mindustry_agents.training.ippo_ppo import IPPOTransition, sha256_path
from mindustry_agents.training.selector import TASK_TYPES


CONFIG_SHA256 = (
    "ae0d29aa7fd8882e51582df111e5f27830382228c992765c6def7d6998b7f95f"
)
PROTOCOL_SHA256 = (
    "1812f19c8c64cc980399def88d9dec43e0cda0cb589b5a4bcae1afd88f68962b"
)
SOURCE_MODEL_SHA256 = (
    "7838b9392b32d7dc5867dd53ffed78a77f9094f3492cf0b2ac4406ec551ae0d1"
)
SOURCE_OPTIMIZER_SHA256 = (
    "f3bdf93bf2dfae69842b87ca69f124c1bdda074b05422c02198530a5fdb687bc"
)
SOURCE_CONTENT_SHA256 = (
    "55005ab5a0591b2688e32a4819678088f0f8701de920dbf788202539c046b865"
)
PLAN_SLOTS = 4
FAMILY_COUNT = 16
FAMILY_START = 13
FAMILY_END = 29
PLAN_BIAS_SCALE = 1.0
PLAN_LOSS_COEFFICIENT = 0.25
SEQUENCE_LENGTH = 16
SEQUENCES_PER_MINIBATCH = 16
MODEL_SCHEMA = "ippo_shared_recurrent_selector_trajectory_plan_v1"
MODEL_ARCHITECTURE = {
    "schema": MODEL_SCHEMA,
    "inherited_architecture": "ippo_shared_recurrent_selector_v1",
    "inherited_parameters_exact": True,
    "plan_context": (
        "encoded_current_plus_pooled_candidates_plus_next_private_hidden_"
        "plus_role_embedding"
    ),
    "plan_head": [200, 64, 64],
    "plan_shape": [PLAN_SLOTS, FAMILY_COUNT],
    "candidate_bias": (
        "slot_zero_family_logit_selected_by_candidate_task_family_one_hot"
    ),
    "action_count": 10,
    "hidden_state": "private_per_seat_zero_on_reset_or_death",
}
TASK_TYPE_TO_INDEX = {name: index for index, name in enumerate(TASK_TYPES)}


@dataclass(frozen=True)
class TrajectoryPlanEpisode:
    """One student-controlled episode with aligned macro-family programs."""

    seed: int
    outcome: str
    tick: int
    core_health: float
    transitions: tuple[IPPOTransition, ...]
    plan_targets: tuple[tuple[int, int, int, int] | None, ...]
    eligible_labels: int
    context_transitions: int
    forced_controls: int
    student_teacher_matches: int
    rejected_student_actions: int
    trace_sha256: str


class TrajectoryPlanSelector(SharedRecurrentSelector):
    """The frozen base selector plus an explicit four-slot family plan."""

    model_schema = MODEL_SCHEMA
    model_architecture = MODEL_ARCHITECTURE

    def __init__(self, seed: int, *, plan_head_seed: int):
        super().__init__(seed)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(plan_head_seed)
            self.plan_head = nn.Sequential(
                nn.Linear(200, 64),
                nn.Tanh(),
                nn.Linear(64, PLAN_SLOTS * FAMILY_COUNT),
            )
        final = self.plan_head[-1]
        if not isinstance(final, nn.Linear):
            raise AssertionError("trajectory plan final layer drifted")
        nn.init.zeros_(final.weight)
        nn.init.zeros_(final.bias)

    def forward_with_plan(
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
        raw, _, value, next_hidden = super().forward(
            candidates,
            scalars,
            candidate_present,
            action_mask,
            agent_ids,
            hidden,
        )
        encoded_candidates = self.candidate_encoder(candidates)
        encoded_current = self.current_scalar_encoder(scalars[:, :56])
        encoded_lag = self.lagged_context_encoder(scalars[:, 56:])
        del encoded_lag
        roles = self.role_embedding(agent_ids)
        weights = candidate_present.to(encoded_candidates.dtype).unsqueeze(-1)
        candidate_sum = (encoded_candidates * weights).sum(dim=1)
        candidate_count = weights.sum(dim=1)
        pooled = candidate_sum / candidate_count.clamp_min(1.0)
        plan_context = torch.cat(
            (encoded_current, pooled, next_hidden, roles), dim=-1
        )
        plan_logits = self.plan_head(plan_context).reshape(
            -1, PLAN_SLOTS, FAMILY_COUNT
        )
        family_features = candidates[:, :, FAMILY_START:FAMILY_END]
        candidate_bias = torch.einsum(
            "bf,bcf->bc", plan_logits[:, 0, :], family_features
        )
        biased_raw = torch.cat(
            (
                raw[:, :8] + PLAN_BIAS_SCALE * candidate_bias,
                raw[:, 8:],
            ),
            dim=-1,
        )
        biased_masked = biased_raw.masked_fill(
            ~action_mask, torch.finfo(biased_raw.dtype).min
        )
        return biased_raw, biased_masked, value, next_hidden, plan_logits

    def forward(
        self,
        candidates: torch.Tensor,
        scalars: torch.Tensor,
        candidate_present: torch.Tensor,
        action_mask: torch.Tensor,
        agent_ids: torch.Tensor,
        hidden: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        raw, masked, value, next_hidden, _ = self.forward_with_plan(
            candidates,
            scalars,
            candidate_present,
            action_mask,
            agent_ids,
            hidden,
        )
        return raw, masked, value, next_hidden


def load_trajectory_plan_config(path: Path) -> dict[str, Any]:
    if sha256_path(path) != CONFIG_SHA256:
        raise ValueError("M9 trajectory-plan config digest drifted")
    config = json.loads(path.read_text(encoding="utf-8"))
    plan = config.get("trajectory_plan", {})
    if (
        config.get("schema")
        != "m9_candidate_native_trajectory_plan_config_v1"
        or config.get("candidate_version")
        != "m9-candidate-native-trajectory-plan-v1"
        or config.get("confirmation_seed_set") is not None
        or config.get("held_out_seed_set") is not None
        or int(config.get("continuation_updates", 0)) != 32
        or int(config.get("episodes_per_update", 0)) != 64
        or int(config.get("sequence_length", 0)) != SEQUENCE_LENGTH
        or int(config.get("sequences_per_minibatch", 0))
        != SEQUENCES_PER_MINIBATCH
        or plan.get("task_family_order") != list(TASK_TYPES)
        or int(plan.get("program_slots", 0)) != PLAN_SLOTS
        or float(plan.get("slot_zero_candidate_logit_bias_scale", -1))
        != PLAN_BIAS_SCALE
        or float(
            plan.get("four_slot_plan_cross_entropy_coefficient", -1)
        )
        != PLAN_LOSS_COEFFICIENT
        or config.get("model_architecture") != MODEL_ARCHITECTURE
    ):
        raise ValueError("M9 trajectory-plan config contract drifted")
    return config


def validate_protocol(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    path = root / str(config["public_evaluation_protocol"])
    if sha256_path(path) != PROTOCOL_SHA256:
        raise ValueError("M9 trajectory-plan protocol digest drifted")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    authority = protocol.get("downstream_authority", {})
    if (
        protocol.get("schema")
        != "m9_candidate_native_trajectory_plan_public_protocol_v1"
        or protocol.get("config_sha256") != CONFIG_SHA256
        or protocol.get("source_diagnostic", {}).get("sha256")
        != config["source_diagnostic"]["sha256"]
        or any(
            authority.get(key) is not False
            for key in (
                "may_select_source_checkpoint",
                "may_repair_source_checkpoint",
                "may_change_planner_candidates_features_or_masks",
                "may_sweep_plan_slots_bias_scale_or_loss_coefficient",
                "may_use_reward_critic_ppo_or_mappo",
                "may_access_confirmation",
                "may_access_held_out",
                "may_authorize_human_session",
            )
        )
    ):
        raise ValueError("M9 trajectory-plan public authority drifted")
    return protocol


def source_model_and_optimizer(
    root: Path,
    config: dict[str, Any],
) -> tuple[TrajectoryPlanSelector, torch.optim.Adam, dict[str, Any]]:
    source = config["source_checkpoint"]
    bound_paths = {
        "config_sha256": source["config_path"],
        "file_sha256": source["path"],
        "source_result_sha256": source["source_result"],
        "source_manifest_sha256": source["source_manifest"],
    }
    for digest_key, relative in bound_paths.items():
        if sha256_path(root / str(relative)) != source[digest_key]:
            raise ValueError("M9 trajectory-plan source identity drifted")
    if (
        sha256_path(root / str(config["source_diagnostic"]["path"]))
        != config["source_diagnostic"]["sha256"]
    ):
        raise ValueError("M9 trajectory-plan diagnostic identity drifted")

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
    ):
        raise ValueError("M9 trajectory-plan source checkpoint drifted")
    model = TrajectoryPlanSelector(
        9601, plan_head_seed=int(config["plan_head_init_seed"])
    )
    incompatible = model.load_state_dict(base.state_dict(), strict=False)
    expected_missing = {
        "plan_head.0.weight",
        "plan_head.0.bias",
        "plan_head.2.weight",
        "plan_head.2.bias",
    }
    if (
        set(incompatible.missing_keys) != expected_missing
        or incompatible.unexpected_keys
    ):
        raise ValueError("M9 trajectory-plan inherited model drifted")
    inherited = [
        parameter
        for name, parameter in model.named_parameters()
        if not name.startswith("plan_head.")
    ]
    plan_parameters = [
        parameter
        for name, parameter in model.named_parameters()
        if name.startswith("plan_head.")
    ]
    optimizer = torch.optim.Adam(
        inherited,
        lr=float(config["learning_rate"]),
        eps=float(config["adam_epsilon"]),
    )
    optimizer.load_state_dict(payload["optimizer_state"])
    optimizer.add_param_group(
        {
            "params": plan_parameters,
            "lr": float(config["learning_rate"]),
            "eps": float(config["adam_epsilon"]),
        }
    )
    if optimizer.state_dict()["state"].keys() != payload[
        "optimizer_state"
    ]["state"].keys():
        raise ValueError("M9 trajectory-plan inherited Adam state drifted")
    return model, optimizer, payload


def _family_from_label(
    label: int,
    transition: IPPOTransition,
    active_family: int,
) -> int:
    if label == 8:
        return active_family
    if label == 9:
        return TASK_TYPE_TO_INDEX["WAIT"]
    if label < 0 or label >= 8:
        raise ValueError("M9 trajectory-plan label is invalid")
    row = transition.candidates[label, FAMILY_START:FAMILY_END]
    if row.shape != (FAMILY_COUNT,) or float(row.sum().item()) != 1.0:
        raise ValueError("M9 trajectory-plan candidate family drifted")
    return int(torch.argmax(row).item())


def build_plan_targets(
    transitions: Sequence[IPPOTransition],
    immediate_families: Sequence[int | None],
) -> tuple[tuple[int, int, int, int] | None, ...]:
    if len(transitions) != len(immediate_families):
        raise ValueError("M9 trajectory-plan target alignment drifted")
    result: list[tuple[int, int, int, int] | None] = [
        None for _ in transitions
    ]
    for agent_id in range(3):
        segment: list[int] = []

        def flush() -> None:
            supervised = [
                index
                for index in segment
                if immediate_families[index] is not None
            ]
            for position, index in enumerate(supervised):
                first = immediate_families[index]
                if first is None:
                    raise AssertionError("supervised family vanished")
                program = [int(first)]
                for future in supervised[position + 1 :]:
                    family = immediate_families[future]
                    if family is not None and int(family) != program[-1]:
                        program.append(int(family))
                    if len(program) == PLAN_SLOTS:
                        break
                program.extend([program[-1]] * (PLAN_SLOTS - len(program)))
                result[index] = tuple(program)  # type: ignore[assignment]

        for index, transition in enumerate(transitions):
            if transition.agent_id != agent_id:
                continue
            if transition.recurrent_reset and segment:
                flush()
                segment = []
            segment.append(index)
            if transition.done:
                flush()
                segment = []
        if segment:
            flush()
    if any(
        transition.policy_loss_mask != (result[index] is not None)
        for index, transition in enumerate(transitions)
    ):
        raise ValueError("M9 trajectory-plan supervision mask drifted")
    return tuple(result)


def collect_trajectory_plan_episode(
    env: RlServerProcess,
    model: TrajectoryPlanSelector,
    config: dict[str, Any],
    *,
    seed: int,
) -> TrajectoryPlanEpisode:
    reset = env.reset(
        seed,
        scenario_id=str(config["scenario_id"]),
        scenario_version=int(config["scenario_version"]),
        agent_count=3,
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
    transitions: list[IPPOTransition] = []
    immediate_families: list[int | None] = []
    active_families = [TASK_TYPE_TO_INDEX["WAIT"]] * 3
    labels_seen = 0
    matches = 0
    forced = 0
    rejected = 0
    trace: list[dict[str, Any]] = []

    while outcome == "running" and tick < int(metadata["tick_cap"]):
        teacher = planner.actions(observations, masks, board)
        decision = decide_all_seats(
            model,
            state,
            observations,
            masks,
            metadata,
            task_board=board,
            boundary_reasons=reasons,
            evaluation=True,
        )
        labels = teacher_labels(decision, teacher, observations)
        forced += len(decision.evaluation_order) - len(labels)
        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, int(metadata["tick_cap"]) - tick),
            agent_actions=decision.agent_actions,
            stop_on_decision_event=True,
        )
        accepted = {
            int(item["agent_id"])
            for item in response.action_results
            if item.get("accepted", False)
        }
        rejected += sum(
            not item.get("accepted", False)
            for item in response.action_results
        )
        advanced = int(
            response.decision_boundary.get(
                "advanced_ticks", response.tick - tick
            )
        )
        done = response.outcome != "running"
        boundary_rows: list[tuple[int, int, IPPOTransition]] = []
        for agent_id in decision.evaluation_order:
            features = decision.features[agent_id]
            supervised = agent_id in labels
            action = (
                int(labels[agent_id])
                if supervised
                else int(decision.action_indices[agent_id])
            )
            transition = IPPOTransition(
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
                action=action,
                old_log_prob=0.0,
                old_value=decision.old_values[agent_id],
                team_reward=0.0,
                individual_reward=0.0,
                advanced_ticks=advanced,
                done=done,
                policy_loss_mask=supervised,
                recurrent_reset=decision.recurrent_resets[agent_id],
            )
            family = (
                _family_from_label(
                    action, transition, active_families[agent_id]
                )
                if supervised
                else None
            )
            transitions.append(transition)
            immediate_families.append(family)
            boundary_rows.append((agent_id, action, transition))
            if supervised:
                labels_seen += 1
                matches += (
                    int(decision.action_indices[agent_id]) == action
                )
        for agent_id, _, transition in boundary_rows:
            if agent_id not in accepted:
                continue
            features = decision.features[agent_id]
            if features.forced_task_action is not None:
                continue
            student_action = int(decision.action_indices[agent_id])
            if student_action == 9:
                active_families[agent_id] = TASK_TYPE_TO_INDEX["WAIT"]
            elif 0 <= student_action < 8:
                active_families[agent_id] = _family_from_label(
                    student_action,
                    transition,
                    active_families[agent_id],
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
                "student_actions": decision.agent_actions,
                "teacher_actions": canonical_teacher_bundle(
                    teacher, observations
                ),
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

    if outcome == "running" or not transitions or labels_seen <= 0:
        raise RuntimeError("M9 trajectory-plan episode was incomplete")
    targets = build_plan_targets(transitions, immediate_families)
    return TrajectoryPlanEpisode(
        seed=seed,
        outcome=outcome,
        tick=tick,
        core_health=float(observations[0]["team"]["core_health"]),
        transitions=tuple(transitions),
        plan_targets=targets,
        eligible_labels=labels_seen,
        context_transitions=len(transitions) - labels_seen,
        forced_controls=forced,
        student_teacher_matches=matches,
        rejected_student_actions=rejected,
        trace_sha256=_canonical_sha256(trace),
    )


def trajectory_plan_update(
    model: TrajectoryPlanSelector,
    optimizer: torch.optim.Optimizer,
    episodes: Sequence[TrajectoryPlanEpisode],
    config: dict[str, Any],
    generator: torch.Generator,
) -> dict[str, float]:
    transitions, windows, window_metrics = supervised_sequence_windows(
        episodes, sequence_length=SEQUENCE_LENGTH
    )
    targets = [
        target for episode in episodes for target in episode.plan_targets
    ]
    if len(targets) != len(transitions):
        raise ValueError("M9 trajectory-plan flattened targets drifted")
    action_loss_total = 0.0
    plan_loss_total = 0.0
    batches = 0
    presentations = 0
    action_correct = 0
    plan_correct = 0
    real_presentations = 0
    padded_slots = 0
    for _ in range(int(config["epochs_per_update"])):
        order = torch.randperm(len(windows), generator=generator)
        for start in range(0, len(windows), SEQUENCES_PER_MINIBATCH):
            selected = [
                windows[int(index)]
                for index in order[
                    start : start + SEQUENCES_PER_MINIBATCH
                ]
            ]
            hidden_rows = [
                transitions[window[0]].hidden_input.reshape(1, -1).detach()
                for window in selected
            ]
            action_losses: list[torch.Tensor] = []
            plan_losses: list[torch.Tensor] = []
            maximum = max(len(window) for window in selected)
            for step in range(maximum):
                rows = [
                    row
                    for row, window in enumerate(selected)
                    if step < len(window)
                ]
                indices = [selected[row][step] for row in rows]
                items = [transitions[index] for index in indices]
                hidden = torch.cat([hidden_rows[row] for row in rows], dim=0)
                _, logits, _, next_hidden, plan_logits = (
                    model.forward_with_plan(
                        torch.stack([item.candidates for item in items]),
                        torch.stack([item.scalars for item in items]),
                        torch.stack(
                            [item.candidate_present for item in items]
                        ),
                        torch.stack([item.action_mask for item in items]),
                        torch.tensor(
                            [item.agent_id for item in items],
                            dtype=torch.long,
                        ),
                        hidden,
                    )
                )
                for position, row in enumerate(rows):
                    hidden_rows[row] = next_hidden[position : position + 1]
                real_presentations += len(items)
                for position, (index, item) in enumerate(
                    zip(indices, items, strict=True)
                ):
                    if not item.policy_loss_mask:
                        continue
                    target = targets[index]
                    if target is None:
                        raise ValueError(
                            "M9 trajectory-plan supervised target is absent"
                        )
                    if not bool(item.action_mask[item.action]):
                        raise ValueError(
                            "M9 trajectory-plan action is outside its mask"
                        )
                    action_losses.append(
                        -torch.log_softmax(logits[position], dim=-1)[
                            item.action
                        ]
                    )
                    target_tensor = torch.tensor(target, dtype=torch.long)
                    plan_losses.append(
                        torch.nn.functional.cross_entropy(
                            plan_logits[position], target_tensor
                        )
                    )
                    presentations += 1
                    action_correct += int(
                        int(torch.argmax(logits[position]).item())
                        == item.action
                    )
                    plan_correct += sum(
                        int(prediction) == expected
                        for prediction, expected in zip(
                            torch.argmax(
                                plan_logits[position], dim=-1
                            ).tolist(),
                            target,
                            strict=True,
                        )
                    )
            if not action_losses or len(action_losses) != len(plan_losses):
                raise ValueError(
                    "M9 trajectory-plan minibatch has no aligned labels"
                )
            action_loss = torch.stack(action_losses).mean()
            plan_loss = torch.stack(plan_losses).mean()
            loss = action_loss + PLAN_LOSS_COEFFICIENT * plan_loss
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(), float(config["max_grad_norm"])
            )
            optimizer.step()
            action_loss_total += float(action_loss.item())
            plan_loss_total += float(plan_loss.item())
            batches += 1
            padded_slots += len(selected) * SEQUENCE_LENGTH - sum(
                len(window) for window in selected
            )
    labels = sum(item.policy_loss_mask for item in transitions)
    return {
        "teacher_action_nll": action_loss_total / max(1, batches),
        "plan_cross_entropy": plan_loss_total / max(1, batches),
        "combined_loss": (
            action_loss_total
            + PLAN_LOSS_COEFFICIENT * plan_loss_total
        )
        / max(1, batches),
        "batches": float(batches),
        "labels": float(labels),
        "presentations": float(presentations),
        "action_top1_accuracy": action_correct / max(1, presentations),
        "plan_slot_accuracy": plan_correct
        / max(1, presentations * PLAN_SLOTS),
        "sequence_windows": float(window_metrics["retained_windows"]),
        "all_sequence_windows": float(window_metrics["all_windows"]),
        "retained_context_transitions": float(
            window_metrics["retained_transitions"] - labels
        ),
        "dropped_context_transitions": float(
            window_metrics["dropped_context_transitions"]
        ),
        "real_transition_presentations": float(real_presentations),
        "padded_transition_slots": float(padded_slots),
    }
