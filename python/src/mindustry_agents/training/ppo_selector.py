"""M8.4 masked PPO for one selector seat with exact run/checkpoint manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as functional

from mindustry_agents import ENGINE_COMMIT, ENGINE_TAG, PROTOCOL_VERSION
from mindustry_agents.policies import GreedyUtilityPolicy
from mindustry_agents.process.launcher import (
    DEFAULT_JVM_ARGS,
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.training.model import (
    MODEL_SCHEMA,
    SelectorActorCritic,
    feature_tensors,
)
from mindustry_agents.training.reward import (
    REWARD_SCHEMA,
    REWARD_SCHEMA_V2,
    SelectorReward,
)
from mindustry_agents.training.selector import (
    FEATURE_SCHEMA,
    SelectorFeatures,
    SelectorHistory,
    build_selector_features,
    selector_action,
)

QUALITY_GATE_SELECTION_SCHEMA = "quality_gate_v1"
QUALITY_GATE_RANKING = (
    "wins_desc",
    "mean_return_desc",
    "mean_core_health_desc",
    "update_asc",
)

ARC_HASH = "208a754044"
LEARNED_SEAT = 0
SCRIPTED_POLICY = "adaptive-v1"
LIFECYCLE_POLICY = "adaptive-lifecycle-v1"


@dataclass
class Transition:
    candidates: torch.Tensor
    scalars: torch.Tensor
    candidate_present: torch.Tensor
    action_mask: torch.Tensor
    action: int
    old_log_prob: float
    old_value: float
    reward: float
    advanced_ticks: int
    done: bool
    policy_loss_mask: bool
    successful_episode: bool = False
    teacher_action: int | None = None


@dataclass
class EpisodeRollout:
    seed: int
    outcome: str
    tick: int
    core_health: float
    transitions: list[Transition]
    reward_components: dict[str, float]
    trace: list[dict[str, Any]]
    coordination_metrics: dict[str, Any]
    task_events: list[dict[str, Any]] = field(default_factory=list)
    game_events: list[dict[str, Any]] = field(default_factory=list)
    agent_loss_ticks: dict[int, int] = field(default_factory=dict)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _model_state_digest(state: dict[str, torch.Tensor]) -> str:
    """Hash tensor names, schemas, and bytes without torch serialization metadata."""

    digest = hashlib.sha256()
    for name in sorted(state):
        tensor = state[name].detach().cpu().contiguous()
        digest.update(name.encode())
        digest.update(str(tensor.dtype).encode())
        digest.update(json.dumps(list(tensor.shape), separators=(",", ":")).encode())
        digest.update(tensor.numpy().tobytes())
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _seed_set(root: Path, relative: str, required_split: str) -> dict[str, Any]:
    document = _load_json(root / relative)
    split = str(document.get("split", ""))
    if split == "held-out" or required_split == "held-out":
        raise ValueError("held-out execution is forbidden in M8.4")
    if split != required_split:
        raise ValueError(f"seed set {relative} is {split}, expected {required_split}")
    return document


def _teacher_warmup_train_set(
    root: Path,
    train_set: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Load an optional train-only teacher corpus without changing PPO roots."""

    relative = config.get("teacher_warmup_seed_set")
    if relative is None:
        return train_set
    return _seed_set(root, str(relative), "train")


def _training_seed_schedule(
    train_set: dict[str, Any], config: dict[str, Any]
) -> list[int]:
    """Repeat only the governed train split with a deterministic per-cycle order."""

    seeds = [int(seed) for seed in train_set["seeds"]]
    cycles = int(config.get("training_cycles", 1))
    if cycles < 1:
        raise ValueError("training_cycles must be positive")
    schedule: list[int] = []
    shuffle_seed = int(config["shuffle_seed"])
    for cycle in range(cycles):
        cycle_seeds = list(seeds)
        random.Random(shuffle_seed + cycle).shuffle(cycle_seeds)
        schedule.extend(cycle_seeds)
    return schedule


def _teacher_warmup_seed_schedule(
    train_set: dict[str, Any], config: dict[str, Any]
) -> list[int]:
    """Return the separately seeded teacher-trajectory warmup schedule."""

    cycles = int(config.get("teacher_warmup_cycles", 0))
    if cycles < 0:
        raise ValueError("teacher_warmup_cycles cannot be negative")
    if cycles == 0:
        return []
    shuffle_seed = int(config["teacher_warmup_shuffle_seed"])
    seeds = [int(seed) for seed in train_set["seeds"]]
    schedule: list[int] = []
    for cycle in range(cycles):
        cycle_seeds = list(seeds)
        random.Random(shuffle_seed + cycle).shuffle(cycle_seeds)
        schedule.extend(cycle_seeds)
    return schedule


def _teacher_warmup_policy(config: dict[str, Any]) -> dict[str, Any] | None:
    """Validate an optional teacher warmup before any environment work begins."""

    cycles = int(config.get("teacher_warmup_cycles", 0))
    if cycles < 0:
        raise ValueError("teacher_warmup_cycles cannot be negative")
    if cycles == 0:
        if config.get("teacher_warmup_seed_set") is not None:
            raise ValueError("teacher_warmup_seed_set requires teacher warmup")
        return None
    epochs = int(config["teacher_warmup_epochs"])
    batch_size = int(config["teacher_warmup_minibatch_size"])
    success_only = config["teacher_warmup_success_only"]
    if epochs < 1 or batch_size < 1:
        raise ValueError("teacher warmup epochs and minibatch size must be positive")
    if not isinstance(success_only, bool):
        raise ValueError("teacher_warmup_success_only must be boolean")
    policy = {
        "cycles": cycles,
        "epochs": epochs,
        "minibatch_size": batch_size,
        "success_only": success_only,
        "shuffle_seed": int(config["teacher_warmup_shuffle_seed"]),
        "minibatch_seed": int(config["teacher_warmup_minibatch_seed"]),
    }
    samples_per_epoch = config.get("teacher_warmup_samples_per_epoch")
    if samples_per_epoch is not None:
        samples_per_epoch = int(samples_per_epoch)
        if samples_per_epoch < 1:
            raise ValueError("teacher_warmup_samples_per_epoch must be positive")
        policy["samples_per_epoch"] = samples_per_epoch
    return policy


def _teacher_rehearsal_policy(config: dict[str, Any]) -> dict[str, int] | None:
    """Validate optional per-PPO-update rehearsal of the warmup corpus."""

    epochs = int(config.get("teacher_rehearsal_epochs_per_update", 0))
    if epochs < 0:
        raise ValueError("teacher_rehearsal_epochs_per_update cannot be negative")
    if epochs == 0:
        return None
    if _teacher_warmup_policy(config) is None:
        raise ValueError("teacher trajectory rehearsal requires teacher warmup")
    policy = {
        "epochs_per_update": epochs,
        "minibatch_seed": int(config["teacher_rehearsal_minibatch_seed"]),
    }
    samples_per_epoch = config.get("teacher_rehearsal_samples_per_epoch")
    if samples_per_epoch is not None:
        samples_per_epoch = int(samples_per_epoch)
        if samples_per_epoch < 1:
            raise ValueError("teacher_rehearsal_samples_per_epoch must be positive")
        policy["samples_per_epoch"] = samples_per_epoch
    return policy


def _dev_checkpoint_selection_policy(
    config: dict[str, Any],
) -> dict[str, Any] | None:
    policy = config.get("dev_checkpoint_selection")
    if policy is None:
        return None
    if (
        not isinstance(policy, dict)
        or policy.get("schema") != QUALITY_GATE_SELECTION_SCHEMA
    ):
        raise ValueError("unsupported dev checkpoint selection schema")
    if tuple(policy.get("ranking", ())) != QUALITY_GATE_RANKING:
        raise ValueError("unsupported dev checkpoint selection ranking")
    minimum_wins = int(policy.get("minimum_wins", -1))
    maximum_idle = float(
        policy.get("maximum_mean_idle_fraction_exclusive", -1.0)
    )
    if minimum_wins < 1 or not 0.0 < maximum_idle <= 1.0:
        raise ValueError("invalid dev checkpoint selection gate")
    return {
        "schema": QUALITY_GATE_SELECTION_SCHEMA,
        "minimum_wins": minimum_wins,
        "maximum_mean_idle_fraction_exclusive": maximum_idle,
        "ranking": list(QUALITY_GATE_RANKING),
    }


def _select_dev_checkpoint_index(
    dev_selection: list[dict[str, Any]],
    policy: dict[str, Any] | None,
) -> int:
    if not dev_selection:
        raise ValueError("dev checkpoint selection is empty")
    eligible = list(range(len(dev_selection)))
    if policy is not None:
        eligible = [
            index
            for index, row in enumerate(dev_selection)
            if int(row["wins"]) >= int(policy["minimum_wins"])
            and float(row["mean_idle_fraction"])
            < float(policy["maximum_mean_idle_fraction_exclusive"])
        ]
        if not eligible:
            raise RuntimeError("no checkpoint passed the precommitted dev quality gate")
    return max(
        eligible,
        key=lambda index: (
            dev_selection[index]["wins"],
            dev_selection[index]["mean_return"],
            dev_selection[index]["mean_core_health"],
            -dev_selection[index]["update"],
        ),
    )


def _write_dev_checkpoint_frontier(
    root: Path,
    output_dir: Path,
    config_path: Path,
    config: dict[str, Any],
    dev_set: dict[str, Any],
    dev_selection: list[dict[str, Any]],
) -> tuple[Path, int]:
    """Persist the complete governed frontier before accepting or rejecting it."""

    selection_policy = _dev_checkpoint_selection_policy(config)
    selected_index: int | None = None
    selection_error: ValueError | RuntimeError | None = None
    try:
        selected_index = _select_dev_checkpoint_index(
            dev_selection, selection_policy
        )
    except (ValueError, RuntimeError) as exc:
        selection_error = exc

    report = {
        "schema": "selector_dev_checkpoint_frontier_v1",
        "source_config": {
            "path": str(config_path.relative_to(root)),
            "sha256": _sha256(config_path),
        },
        "candidate": {
            "version": str(config.get("candidate_version", "")),
            "runtime_contract": str(config.get("runtime_contract", "")),
        },
        "dev_seed_set": {
            key: dev_set[key]
            for key in ("seed_set_id", "seed_set_version", "split", "seeds")
        },
        "selection_policy": selection_policy,
        "frontier": dev_selection,
        "result": {
            "eligible": selection_error is None,
            "selected_index": selected_index,
            "selected_update": (
                int(dev_selection[selected_index]["update"])
                if selected_index is not None
                else None
            ),
            "reason": "passed" if selection_error is None else str(selection_error),
        },
    }
    path = output_dir / "selector-v1-dev-frontier.json"
    temporary_path = output_dir / "selector-v1-dev-frontier.json.tmp"
    temporary_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary_path.replace(path)
    if selection_error is not None:
        raise selection_error
    assert selected_index is not None
    return path, selected_index


def _configure_torch(config: dict[str, Any]) -> None:
    torch.use_deterministic_algorithms(True)
    try:
        torch.set_num_threads(int(config.get("torch_threads", 1)))
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass


def _model_outputs(
    model: SelectorActorCritic, features: SelectorFeatures
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, tuple[torch.Tensor, ...]]:
    tensors = feature_tensors(features)
    raw, masked, value = model(*tensors)
    return raw[0], masked[0], value[0], tuple(item[0].cpu() for item in tensors)


def _select_index(
    masked_logits: torch.Tensor,
    features: SelectorFeatures,
    *,
    evaluation: bool,
    generator: torch.Generator,
) -> tuple[int, float]:
    legal = [index for index, allowed in enumerate(features.action_mask) if allowed]
    if len(legal) == 1:
        index = legal[0]
    elif evaluation:
        index = int(torch.argmax(masked_logits).item())
    else:
        probabilities = torch.softmax(masked_logits, dim=-1)
        index = int(torch.multinomial(probabilities, 1, generator=generator).item())
    log_prob = float(torch.log_softmax(masked_logits, dim=-1)[index].item())
    return index, log_prob


def _scripted_index(
    action: dict[str, Any], candidates: list[dict[str, Any]] | None = None
) -> int:
    task_action = action.get("task_action", {})
    action_type = task_action.get("type")
    if action_type == "SELECT_CANDIDATE_TASK":
        index = int(task_action["candidate_index"])
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


def _canonical_scripted_action(
    action: dict[str, Any], candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    """Map a scripted catalog-WAIT selection to the canonical WAIT action."""

    task_action = action.get("task_action", {})
    if (
        task_action.get("type") == "SELECT_CANDIDATE_TASK"
        and _scripted_index(action, candidates) == 9
    ):
        return {
            "agent_id": int(action.get("agent_id", LEARNED_SEAT)),
            "task_action": {"type": "WAIT"},
        }
    return action


def _selected_candidate_diagnostics(
    candidates: list[dict[str, Any]], selected_index: int
) -> dict[str, Any] | None:
    """Return behavior-neutral evidence for the selected catalog candidate."""

    if (
        selected_index < 0
        or selected_index >= len(candidates)
        or selected_index >= 8
    ):
        return None
    candidate = candidates[selected_index]
    utility = candidate.get("utility_features", {})
    estimated_cost = candidate.get("estimated_cost", {})
    return {
        "candidate_index": selected_index,
        "task_type": str(candidate.get("task_type", "")),
        "target": str(candidate.get("target", "")),
        "resource_cost": float(utility.get("resource_cost", 0.0)),
        "urgency": float(utility.get("urgency", 0.0)),
        "switching_cost": float(utility.get("switching_cost", 0.0)),
        "estimated_copper": int(estimated_cost.get("copper", 0)),
        "semantic_task_active": bool(candidate.get("semantic_task_active", False)),
    }


def rollout_episode(
    env: RlServerProcess,
    model: SelectorActorCritic,
    *,
    seed: int,
    scenario_id: str,
    scenario_version: int,
    evaluation: bool,
    action_generator: torch.Generator,
    reward_schema: str = REWARD_SCHEMA,
    quality_reward: dict[str, float] | None = None,
    teacher_controlled: bool = False,
) -> EpisodeRollout:
    reset = env.reset(
        seed,
        scenario_id=scenario_id,
        scenario_version=scenario_version,
        agent_count=3,
    )
    observations = reset.initial_observations
    masks = reset.action_masks
    metadata = reset.metadata
    episode_id = reset.episode_id
    tick = reset.tick
    board: list[dict[str, Any]] = []
    boundary_reasons: list[str] = []
    history = SelectorHistory()
    if reward_schema not in {REWARD_SCHEMA, REWARD_SCHEMA_V2}:
        raise ValueError(f"unsupported reward schema: {reward_schema}")
    if reward_schema == REWARD_SCHEMA and quality_reward is not None:
        raise ValueError("reward v1 cannot use quality shaping")
    if reward_schema == REWARD_SCHEMA_V2 and quality_reward is None:
        raise ValueError("reward v2 requires quality shaping config")
    reward = SelectorReward(quality_reward=quality_reward)
    scripted = GreedyUtilityPolicy()
    transitions: list[Transition] = []
    trace: list[dict[str, Any]] = []
    reward_totals: dict[str, float] = {}
    previous_team = dict(observations[0]["team"])
    outcome = "running"
    final_metrics: dict[str, Any] = {}
    task_events: list[dict[str, Any]] = []
    game_events: list[dict[str, Any]] = []
    agent_loss_ticks: dict[int, int] = {}
    previous_dead = [bool(item["unit"]["dead"]) for item in observations]

    while outcome == "running" and tick < int(metadata["tick_cap"]):
        scripted_bundle = scripted.actions(observations, masks)
        features = build_selector_features(
            observations,
            masks,
            metadata,
            task_board=board,
            boundary_reasons=boundary_reasons,
            history=history,
            agent_id=LEARNED_SEAT,
        )
        with torch.no_grad():
            raw_logits, masked_logits, value, tensors = _model_outputs(model, features)

        scripted_action = _canonical_scripted_action(
            scripted_bundle[LEARNED_SEAT],
            observations[LEARNED_SEAT]["task_candidates"],
        )
        teacher_index = _scripted_index(
            scripted_action, observations[LEARNED_SEAT]["task_candidates"]
        )
        scripted_type = scripted_action.get("task_action", {}).get("type")
        forced = (
            features.forced_task_action is not None
            or not features.policy_loss_mask
            or scripted_type == "ABANDON"
        )
        if forced or teacher_controlled:
            learned_action = scripted_action
            selected_index = _scripted_index(
                learned_action, observations[LEARNED_SEAT]["task_candidates"]
            )
            log_prob = float(
                torch.log_softmax(masked_logits, dim=-1)[selected_index].item()
            )
        else:
            selected_index, log_prob = _select_index(
                masked_logits,
                features,
                evaluation=evaluation,
                generator=action_generator,
            )
            learned_action = {
                "agent_id": LEARNED_SEAT,
                "task_action": selector_action(
                    selected_index, observations[LEARNED_SEAT]["task_candidates"]
                ),
            }
        raw_action_valid = forced or bool(features.action_mask[selected_index])
        if not raw_action_valid:
            learned_action = {
                "agent_id": LEARNED_SEAT,
                "task_action": {"type": "WAIT"},
            }
        bundle = list(scripted_bundle)
        bundle[LEARNED_SEAT] = learned_action

        response = env.step(
            episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, int(metadata["tick_cap"]) - tick),
            agent_actions=bundle,
            stop_on_decision_event=True,
        )
        scripted.observe_action_results(response.action_results)
        task_events.extend(response.task_events)
        game_events.extend(response.game_events)
        for event in response.game_events:
            if event.get("type") == "unit_destroy" and int(
                event.get("agent_id", -1)
            ) >= 0:
                agent_loss_ticks[int(event["agent_id"])] = int(event["tick"])
        for agent_id, observation in enumerate(response.observations):
            dead = bool(observation["unit"]["dead"])
            if (
                dead
                and not previous_dead[agent_id]
                and agent_id not in agent_loss_ticks
            ):
                agent_loss_ticks[agent_id] = response.tick
            previous_dead[agent_id] = dead
        selected_task_type = None
        if selected_index < 8 and selected_index < len(
            observations[LEARNED_SEAT]["task_candidates"]
        ):
            selected_task_type = observations[LEARNED_SEAT]["task_candidates"][
                selected_index
            ]["task_type"]
        for result in response.action_results:
            if int(result.get("agent_id", -1)) != LEARNED_SEAT or not result.get(
                "accepted", False
            ):
                continue
            if learned_action["task_action"]["type"] == "SELECT_CANDIDATE_TASK":
                reward.record_learned_selection(str(result.get("task_id", "")))
                if selected_task_type is not None:
                    history.record_selection(selected_task_type, tick)

        current_team = dict(response.observations[0]["team"])
        reasons = list(response.decision_boundary.get("reasons", []))
        breakdown = reward.observe(
            previous_team,
            current_team,
            advanced_ticks=int(
                response.decision_boundary.get(
                    "advanced_ticks", response.tick - tick
                )
            ),
            tick_cap=int(metadata["tick_cap"]),
            outcome=response.outcome,
            task_events=response.task_events,
            game_events=response.game_events,
            boundary_reasons=reasons,
            raw_action_valid=raw_action_valid,
            coordination_metrics=response.coordination_metrics,
        )
        for key, amount in breakdown.components.items():
            reward_totals[key] = reward_totals.get(key, 0.0) + amount
        done = response.outcome != "running"
        transitions.append(
            Transition(
                candidates=tensors[0],
                scalars=tensors[1],
                candidate_present=tensors[2],
                action_mask=tensors[3],
                action=selected_index,
                old_log_prob=log_prob,
                old_value=float(value.item()),
                reward=breakdown.total,
                advanced_ticks=int(
                    response.decision_boundary.get(
                        "advanced_ticks", response.tick - tick
                    )
                ),
                done=done,
                policy_loss_mask=features.policy_loss_mask and not forced,
                teacher_action=teacher_index,
            )
        )
        trace.append(
            {
                "tick": tick,
                "advanced_ticks": transitions[-1].advanced_ticks,
                "action": learned_action["task_action"],
                "agent_actions": bundle,
                "action_index": selected_index,
                "teacher_action": scripted_action["task_action"],
                "teacher_action_index": teacher_index,
                "teacher_candidate_diagnostics": _selected_candidate_diagnostics(
                    observations[LEARNED_SEAT]["task_candidates"], teacher_index
                ),
                "selected_candidate_diagnostics": _selected_candidate_diagnostics(
                    observations[LEARNED_SEAT]["task_candidates"], selected_index
                ),
                "policy_loss_mask": transitions[-1].policy_loss_mask,
                "raw_logits": [float(value) for value in raw_logits.tolist()],
                "masked_logits": [float(value) for value in masked_logits.tolist()],
                "log_probability": log_prob,
                "value_prediction": float(value.item()),
                "reward_components": breakdown.components,
                **(
                    {
                        "reward_quality_counters": breakdown.quality_counters,
                        "reward_quality_penalty_totals": (
                            breakdown.quality_penalty_totals
                        ),
                    }
                    if reward_schema == REWARD_SCHEMA_V2
                    else {}
                ),
                "boundary_reasons": reasons,
                "state_hash": response.state_hash,
                "task_events": response.task_events,
                "outcome": response.outcome,
                **({"teacher_controlled": True} if teacher_controlled else {}),
            }
        )
        observations = response.observations
        masks = response.action_masks
        board = response.task_board
        boundary_reasons = reasons
        previous_team = current_team
        tick = response.tick
        outcome = response.outcome
        final_metrics = response.coordination_metrics

    successful_episode = outcome == "win"
    for transition in transitions:
        transition.successful_episode = successful_episode

    return EpisodeRollout(
        seed=seed,
        outcome=outcome,
        tick=tick,
        core_health=float(observations[0]["team"]["core_health"]),
        transitions=transitions,
        reward_components=reward_totals,
        trace=trace,
        coordination_metrics=final_metrics,
        task_events=task_events,
        game_events=game_events,
        agent_loss_ticks=agent_loss_ticks,
    )


def _advantages(
    episodes: list[EpisodeRollout], config: dict[str, Any]
) -> tuple[list[Transition], torch.Tensor, torch.Tensor]:
    gamma_per_second = float(config["gamma_per_second"])
    gae_lambda = float(config["gae_lambda"])
    flat: list[Transition] = []
    advantages: list[float] = []
    returns: list[float] = []
    for episode in episodes:
        episode_advantages = [0.0] * len(episode.transitions)
        next_value = 0.0
        next_advantage = 0.0
        for index in range(len(episode.transitions) - 1, -1, -1):
            item = episode.transitions[index]
            elapsed_seconds = item.advanced_ticks / 60.0
            gamma = gamma_per_second**elapsed_seconds
            lambda_decay = gae_lambda**elapsed_seconds
            continuation = 0.0 if item.done else 1.0
            delta = item.reward + gamma * next_value * continuation - item.old_value
            advantage = (
                delta + gamma * lambda_decay * next_advantage * continuation
            )
            episode_advantages[index] = advantage
            next_value = item.old_value
            next_advantage = advantage
        flat.extend(episode.transitions)
        advantages.extend(episode_advantages)
        returns.extend(
            advantage + item.old_value
            for advantage, item in zip(episode_advantages, episode.transitions)
        )
    advantage_tensor = torch.tensor(advantages, dtype=torch.float32)
    actor = torch.tensor([item.policy_loss_mask for item in flat], dtype=torch.bool)
    if actor.any():
        selected = advantage_tensor[actor]
        advantage_tensor[actor] = (selected - selected.mean()) / selected.std(
            unbiased=False
        ).clamp_min(1e-8)
    return flat, advantage_tensor, torch.tensor(returns, dtype=torch.float32)


def ppo_update(
    model: SelectorActorCritic,
    optimizer: torch.optim.Optimizer,
    episodes: list[EpisodeRollout],
    config: dict[str, Any],
    shuffle_generator: torch.Generator,
) -> dict[str, float]:
    transitions, advantages, returns = _advantages(episodes, config)
    candidates = torch.stack([item.candidates for item in transitions])
    scalars = torch.stack([item.scalars for item in transitions])
    present = torch.stack([item.candidate_present for item in transitions])
    masks = torch.stack([item.action_mask for item in transitions])
    actions = torch.tensor([item.action for item in transitions], dtype=torch.long)
    old_log_probs = torch.tensor(
        [item.old_log_prob for item in transitions], dtype=torch.float32
    )
    actor_mask = torch.tensor(
        [item.policy_loss_mask for item in transitions], dtype=torch.bool
    )
    successful_actor_mask = torch.tensor(
        [item.policy_loss_mask and item.successful_episode for item in transitions],
        dtype=torch.bool,
    )
    teacher_actions = torch.tensor(
        [item.teacher_action if item.teacher_action is not None else 0 for item in transitions],
        dtype=torch.long,
    )
    teacher_mask = torch.tensor(
        [
            item.policy_loss_mask and item.teacher_action is not None
            for item in transitions
        ],
        dtype=torch.bool,
    )
    successful_teacher_mask = torch.tensor(
        [
            item.policy_loss_mask
            and item.successful_episode
            and item.teacher_action is not None
            for item in transitions
        ],
        dtype=torch.bool,
    )
    batch_size = int(config["minibatch_size"])
    metrics = {
        "policy_loss": 0.0,
        "value_loss": 0.0,
        "entropy": 0.0,
        "success_imitation_loss": 0.0,
        "success_imitation_samples": 0.0,
        "successful_teacher_imitation_loss": 0.0,
        "successful_teacher_imitation_samples": 0.0,
        "teacher_imitation_loss": 0.0,
        "teacher_imitation_samples": 0.0,
        "batches": 0.0,
    }
    teacher_coefficient = float(config.get("teacher_imitation_coefficient", 0.0))
    for _ in range(int(config["ppo_epochs"])):
        order = torch.randperm(len(transitions), generator=shuffle_generator)
        for start in range(0, len(transitions), batch_size):
            index = order[start : start + batch_size]
            _, masked_logits, values = model(
                candidates[index], scalars[index], present[index], masks[index]
            )
            all_log_probs = torch.log_softmax(masked_logits, dim=-1)
            log_probs = all_log_probs.gather(
                1, actions[index, None]
            ).squeeze(1)
            probabilities = torch.softmax(masked_logits, dim=-1)
            entropy = -(probabilities * torch.log_softmax(masked_logits, dim=-1)).sum(
                dim=-1
            )
            active = actor_mask[index]
            if active.any():
                ratio = torch.exp(log_probs[active] - old_log_probs[index][active])
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
            successful = successful_actor_mask[index]
            if successful.any():
                success_imitation_loss = -log_probs[successful].mean()
                success_imitation_samples = float(successful.sum().item())
            else:
                success_imitation_loss = values.sum() * 0.0
                success_imitation_samples = 0.0
            teacher_log_probs = all_log_probs.gather(
                1, teacher_actions[index, None]
            ).squeeze(1)
            teacher = teacher_mask[index]
            if teacher_coefficient != 0.0 and teacher.any():
                teacher_imitation_loss = -teacher_log_probs[teacher].mean()
                teacher_imitation_samples = float(teacher.sum().item())
            else:
                teacher_imitation_loss = values.sum() * 0.0
                teacher_imitation_samples = 0.0
            successful_teacher = successful_teacher_mask[index]
            if successful_teacher.any():
                successful_teacher_imitation_loss = -teacher_log_probs[
                    successful_teacher
                ].mean()
                successful_teacher_imitation_samples = float(
                    successful_teacher.sum().item()
                )
            else:
                successful_teacher_imitation_loss = values.sum() * 0.0
                successful_teacher_imitation_samples = 0.0
            value_loss = functional.mse_loss(values, returns[index])
            loss = (
                policy_loss
                + float(config["value_coefficient"]) * value_loss
                - float(config["entropy_coefficient"]) * entropy_loss
                + float(config.get("success_imitation_coefficient", 0.0))
                * success_imitation_loss
                + float(
                    config.get("successful_teacher_imitation_coefficient", 0.0)
                )
                * successful_teacher_imitation_loss
                + teacher_coefficient * teacher_imitation_loss
            )
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(), float(config["max_grad_norm"])
            )
            optimizer.step()
            metrics["policy_loss"] += float(policy_loss.item())
            metrics["value_loss"] += float(value_loss.item())
            metrics["entropy"] += float(entropy_loss.item())
            metrics["success_imitation_loss"] += float(
                success_imitation_loss.item()
            )
            metrics["success_imitation_samples"] += success_imitation_samples
            metrics["successful_teacher_imitation_loss"] += float(
                successful_teacher_imitation_loss.item()
            )
            metrics["successful_teacher_imitation_samples"] += (
                successful_teacher_imitation_samples
            )
            metrics["teacher_imitation_loss"] += float(
                teacher_imitation_loss.item()
            )
            metrics["teacher_imitation_samples"] += teacher_imitation_samples
            metrics["batches"] += 1.0
    divisor = max(1.0, metrics["batches"])
    return {
        key: value / divisor
        if key
        not in {
            "batches",
            "success_imitation_samples",
            "successful_teacher_imitation_samples",
            "teacher_imitation_samples",
        }
        else value
        for key, value in metrics.items()
    }


def _teacher_trajectory_imitation_update(
    model: SelectorActorCritic,
    optimizer: torch.optim.Optimizer,
    episodes: list[EpisodeRollout],
    shuffle_generator: torch.Generator,
    *,
    epochs: int,
    batch_size: int,
    success_only: bool,
    max_grad_norm: float,
    schema: str,
    samples_per_epoch: int | None = None,
) -> dict[str, Any]:
    """Apply deterministic CE-only updates from teacher-controlled trajectories."""

    eligible_episodes = [
        episode
        for episode in episodes
        if not success_only or episode.outcome == "win"
    ]
    transitions = [
        item
        for episode in eligible_episodes
        for item in episode.transitions
        if item.policy_loss_mask and item.teacher_action is not None
    ]
    if not transitions:
        raise RuntimeError("teacher warmup produced no unforced labeled transitions")
    for transition in transitions:
        teacher_action = int(transition.teacher_action)
        if (
            teacher_action < 0
            or teacher_action >= transition.action_mask.numel()
            or not bool(transition.action_mask[teacher_action])
        ):
            raise RuntimeError("teacher warmup labeled a masked action")
    candidates = torch.stack([item.candidates for item in transitions])
    scalars = torch.stack([item.scalars for item in transitions])
    present = torch.stack([item.candidate_present for item in transitions])
    masks = torch.stack([item.action_mask for item in transitions])
    teacher_actions = torch.tensor(
        [int(item.teacher_action) for item in transitions], dtype=torch.long
    )
    loss_total = 0.0
    batches = 0
    samples = 0
    sampled_orders: list[list[int]] = []
    for _ in range(epochs):
        order = torch.randperm(len(transitions), generator=shuffle_generator)
        if samples_per_epoch is not None:
            order = order[: min(samples_per_epoch, len(transitions))]
            sampled_orders.append([int(index) for index in order.tolist()])
        for start in range(0, len(order), batch_size):
            index = order[start : start + batch_size]
            _, masked_logits, _ = model(
                candidates[index], scalars[index], present[index], masks[index]
            )
            loss = functional.cross_entropy(masked_logits, teacher_actions[index])
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_grad_norm)
            optimizer.step()
            loss_total += float(loss.item())
            batches += 1
            samples += int(index.numel())
    metrics = {
        "schema": schema,
        "epochs": epochs,
        "batches": batches,
        "samples": samples,
        "unique_transitions": len(transitions),
        "eligible_episodes": len(eligible_episodes),
        "total_episodes": len(episodes),
        "success_only": success_only,
        "mean_cross_entropy": loss_total / max(1, batches),
    }
    if samples_per_epoch is not None:
        metrics.update(
            {
                "samples_per_epoch_cap": samples_per_epoch,
                "sampled_unique_transitions": len(
                    {index for order in sampled_orders for index in order}
                ),
                "sampled_transition_indices_by_epoch": sampled_orders,
                "sample_schedule_sha256": _json_digest(sampled_orders),
            }
        )
    return metrics


def teacher_trajectory_warmup_update(
    model: SelectorActorCritic,
    optimizer: torch.optim.Optimizer,
    episodes: list[EpisodeRollout],
    config: dict[str, Any],
    shuffle_generator: torch.Generator,
) -> dict[str, Any]:
    """Run deterministic CE-only warmup on teacher-controlled train trajectories."""

    policy = _teacher_warmup_policy(config)
    if policy is None:
        raise ValueError("teacher trajectory warmup is disabled")
    return _teacher_trajectory_imitation_update(
        model,
        optimizer,
        episodes,
        shuffle_generator,
        epochs=int(policy["epochs"]),
        batch_size=int(policy["minibatch_size"]),
        success_only=bool(policy["success_only"]),
        max_grad_norm=float(config["max_grad_norm"]),
        schema="teacher_trajectory_warmup_v1",
        samples_per_epoch=policy.get("samples_per_epoch"),
    )


def teacher_trajectory_rehearsal_update(
    model: SelectorActorCritic,
    optimizer: torch.optim.Optimizer,
    episodes: list[EpisodeRollout],
    config: dict[str, Any],
    shuffle_generator: torch.Generator,
) -> dict[str, Any]:
    """Rehearse the governed warmup corpus after one ordinary PPO update."""

    warmup_policy = _teacher_warmup_policy(config)
    rehearsal_policy = _teacher_rehearsal_policy(config)
    if warmup_policy is None or rehearsal_policy is None:
        raise ValueError("teacher trajectory rehearsal is disabled")
    return _teacher_trajectory_imitation_update(
        model,
        optimizer,
        episodes,
        shuffle_generator,
        epochs=int(rehearsal_policy["epochs_per_update"]),
        batch_size=int(warmup_policy["minibatch_size"]),
        success_only=bool(warmup_policy["success_only"]),
        max_grad_norm=float(config["max_grad_norm"]),
        schema="teacher_trajectory_rehearsal_v1",
        samples_per_epoch=rehearsal_policy.get("samples_per_epoch"),
    )


def _episode_summary(episode: EpisodeRollout) -> dict[str, Any]:
    action_state_trace = [
        {
            key: transition[key]
            for key in (
                "tick",
                "advanced_ticks",
                "action",
                "agent_actions",
                "action_index",
                "policy_loss_mask",
                "reward_components",
                "boundary_reasons",
                "state_hash",
                "outcome",
            )
        }
        for transition in episode.trace
    ]
    return {
        "seed": episode.seed,
        "outcome": episode.outcome,
        "tick": episode.tick,
        "core_health": episode.core_health,
        "return": sum(episode.reward_components.values()),
        "reward_components": episode.reward_components,
        "decisions": len(episode.transitions),
        "policy_decisions": sum(item.policy_loss_mask for item in episode.transitions),
        "idle_fraction": float(episode.coordination_metrics.get("idle_fraction", 0.0)),
        "duplicate_work_incidents": int(
            episode.coordination_metrics.get("duplicate_work_incidents", 0)
        ),
        "trace_digest": _json_digest(action_state_trace),
    }


def _evaluate(
    model: SelectorActorCritic,
    seeds: list[int],
    config: dict[str, Any],
    *,
    java: str,
    port: int,
) -> list[EpisodeRollout]:
    model.eval()
    generator = torch.Generator().manual_seed(int(config["action_sampling_seed"]))
    with RlServerProcess(
        LaunchConfig(port=port, java=java, build_if_missing=False)
    ) as env:
        env.handshake("m8-ppo-evaluation")
        return [
            rollout_episode(
                env,
                model,
                seed=seed,
                scenario_id=str(config["scenario_id"]),
                scenario_version=int(config["scenario_version"]),
                evaluation=True,
                action_generator=generator,
                reward_schema=str(config.get("reward_schema", REWARD_SCHEMA)),
                quality_reward=config.get("quality_reward"),
            )
            for seed in seeds
        ]


def save_checkpoint(
    path: Path,
    model: SelectorActorCritic,
    optimizer: torch.optim.Optimizer,
    *,
    config_sha256: str,
    parent_checkpoint: str,
    update: int,
    reward_schema: str = REWARD_SCHEMA,
) -> str:
    payload = {
        "feature_schema": FEATURE_SCHEMA,
        "reward_schema": reward_schema,
        "model_schema": MODEL_SCHEMA,
        "config_sha256": config_sha256,
        "parent_checkpoint": parent_checkpoint,
        "update": update,
        "model_state_sha256": _model_state_digest(model.state_dict()),
        "model_state": model.state_dict(),
        "optimizer_state": optimizer.state_dict(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)
    return _sha256(path)


def load_checkpoint(
    path: Path,
    model: SelectorActorCritic,
    *,
    reward_schema: str = REWARD_SCHEMA,
) -> dict[str, Any]:
    payload = torch.load(path, map_location="cpu", weights_only=False)
    expected = (FEATURE_SCHEMA, reward_schema, MODEL_SCHEMA)
    actual = (
        payload.get("feature_schema"),
        payload.get("reward_schema"),
        payload.get("model_schema"),
    )
    if actual != expected:
        raise ValueError(f"checkpoint schema mismatch: {actual} != {expected}")
    model_digest = _model_state_digest(payload["model_state"])
    recorded_digest = payload.get("model_state_sha256")
    if recorded_digest is not None and recorded_digest != model_digest:
        raise ValueError("checkpoint model state digest mismatch")
    model.load_state_dict(payload["model_state"])
    model.eval()
    return payload


def _git_evidence(root: Path) -> dict[str, Any]:
    git_executable = os.environ.get("M8_GIT", "git")
    git_root = os.environ.get("M8_GIT_ROOT", str(root))

    def run(*args: str, strip: bool = True) -> str:
        output = subprocess.run(
            [git_executable, "-C", git_root, *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        return output.strip() if strip else output

    status = run("status", "--short", strip=False).splitlines()
    return {
        "commit": run("rev-parse", "HEAD"),
        "dirty": bool(status),
        "status": status,
        "executable": git_executable,
    }


def _write_teacher_warmup_report(
    root: Path,
    output_dir: Path,
    config_path: Path,
    config: dict[str, Any],
    train_set: dict[str, Any],
    seed_schedule: list[int],
    episode_summaries: list[dict[str, Any]],
    optimizer_metrics: dict[str, Any],
    initial_model_state_sha256: str,
    post_warmup_model_state_sha256: str,
) -> tuple[Path, dict[str, Any]]:
    """Persist compact warmup evidence before ordinary PPO can fail."""

    report = {
        "schema": "selector_teacher_trajectory_warmup_report_v1",
        "source_config": {
            "path": str(config_path.relative_to(root)),
            "sha256": _sha256(config_path),
        },
        "train_seed_set": {
            key: train_set[key]
            for key in ("seed_set_id", "seed_set_version", "split")
        },
        "seed_schedule": seed_schedule,
        "configuration": {
            key: config[key]
            for key in (
                "teacher_warmup_cycles",
                "teacher_warmup_epochs",
                "teacher_warmup_minibatch_size",
                "teacher_warmup_success_only",
                "teacher_warmup_shuffle_seed",
                "teacher_warmup_minibatch_seed",
            )
        },
        "optimizer": optimizer_metrics,
        "initial_model_state_sha256": initial_model_state_sha256,
        "post_warmup_model_state_sha256": post_warmup_model_state_sha256,
        "episodes": episode_summaries,
        "wins": sum(item["outcome"] == "win" for item in episode_summaries),
    }
    if "teacher_warmup_samples_per_epoch" in config:
        report["configuration"]["teacher_warmup_samples_per_epoch"] = config[
            "teacher_warmup_samples_per_epoch"
        ]
    path = output_dir / "selector-v1-teacher-warmup.json"
    temporary_path = path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary_path.replace(path)
    return path, report


def _write_teacher_rehearsal_report(
    root: Path,
    output_dir: Path,
    config_path: Path,
    config: dict[str, Any],
    warmup_report_path: Path,
    corpus_summaries: list[dict[str, Any]],
    optimizer_updates: list[dict[str, Any]],
    post_rehearsal_model_state_sha256: str,
) -> tuple[Path, dict[str, Any]]:
    """Atomically preserve rehearsal evidence even if construction later fails."""

    report = {
        "schema": "selector_teacher_trajectory_rehearsal_report_v1",
        "source_config": {
            "path": str(config_path.relative_to(root)),
            "sha256": _sha256(config_path),
        },
        "source_warmup_report": {
            "path": str(warmup_report_path.relative_to(root)),
            "sha256": _sha256(warmup_report_path),
        },
        "configuration": {
            key: config[key]
            for key in (
                "teacher_rehearsal_epochs_per_update",
                "teacher_rehearsal_minibatch_seed",
            )
        },
        "corpus": {
            "episodes": corpus_summaries,
            "eligible_episodes": len(corpus_summaries),
            "unique_transitions": sum(
                int(item["policy_decisions"]) for item in corpus_summaries
            ),
        },
        "optimizer_updates": optimizer_updates,
        "updates": len(optimizer_updates),
        "post_rehearsal_model_state_sha256": post_rehearsal_model_state_sha256,
    }
    if "teacher_rehearsal_samples_per_epoch" in config:
        report["configuration"]["teacher_rehearsal_samples_per_epoch"] = config[
            "teacher_rehearsal_samples_per_epoch"
        ]
    path = output_dir / "selector-v1-teacher-rehearsal.json"
    temporary_path = path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary_path.replace(path)
    return path, report


def _manifest(
    root: Path,
    config_path: Path,
    config: dict[str, Any],
    train_set: dict[str, Any],
    teacher_warmup_set: dict[str, Any],
    dev_set: dict[str, Any],
    checkpoint_path: Path,
    checkpoint_sha256: str,
    train_summaries: list[dict[str, Any]],
    dev_summaries: list[dict[str, Any]],
    verification: dict[str, Any],
    optimizer_updates: list[dict[str, Any]],
    dev_selection: list[dict[str, Any]],
    parent_checkpoint: str,
    produced_checkpoints: list[Path],
    verification_paths: list[Path],
    training_seed_schedule: list[int],
    initial_model_state_sha256: str,
    selected_model_state_sha256: str,
    selected_update: int,
    teacher_warmup: dict[str, Any] | None,
    teacher_rehearsal: dict[str, Any] | None,
) -> dict[str, Any]:
    lock = root / "python" / "requirements-rl-linux-py312.lock"
    selection_policy = _dev_checkpoint_selection_policy(config)
    manifest = {
        "schema": "selector_training_run_v1",
        "engine": {"tag": ENGINE_TAG, "commit": ENGINE_COMMIT, "arc": ARC_HASH},
        "protocol_version": PROTOCOL_VERSION,
        "scenario": {"id": config["scenario_id"], "version": config["scenario_version"]},
        "schemas": {
            "feature": FEATURE_SCHEMA,
            "reward": str(config.get("reward_schema", REWARD_SCHEMA)),
            "model": MODEL_SCHEMA,
        },
        "repository": _git_evidence(root),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "wsl_distribution": os.environ.get("WSL_DISTRO_NAME", ""),
            "processor": platform.processor(),
            "torch": torch.__version__,
            "device": "cpu",
            "torch_threads": torch.get_num_threads(),
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "jvm_args": list(DEFAULT_JVM_ARGS),
            "rl_lockfile": str(lock.relative_to(root)),
            "rl_lock_sha256": _sha256(lock),
        },
        "seed_sets": {
            "train": {key: train_set[key] for key in ("seed_set_id", "seed_set_version", "split")},
            "dev": {key: dev_set[key] for key in ("seed_set_id", "seed_set_version", "split")},
            "held_out": {"seed_set_id": config["held_out_seed_set_id"], "seed_set_version": config["held_out_seed_set_version"], "active": False},
            "active_splits": ["train", "dev"],
        },
        "rng_seeds": {
            key: config[key]
            for key in ("model_init_seed", "action_sampling_seed", "shuffle_seed", "minibatch_seed")
        } | {
            "environment_root_seeds": {
                "train": list(train_set["seeds"]),
                "dev": list(dev_set["seeds"]),
            },
            "training_seed_schedule": training_seed_schedule,
        },
        "controller": {
            "learned_seat_id": LEARNED_SEAT,
            "scripted_teammate_policy": SCRIPTED_POLICY,
            "lifecycle_policy": LIFECYCLE_POLICY,
            "action_cadence": "server decision events with stop_on_decision_event=true",
            "jvm_cap": 4,
        },
        "normalizers": config["normalizers"],
        "model_architecture": config["model_architecture"],
        "optimizer_ppo": config["optimizer_ppo"],
        "rollout_update_counts": {
            "train_episodes": len(train_summaries),
            "dev_episodes": len(dev_summaries),
            "updates": len(optimizer_updates),
            "training_cycles": int(config.get("training_cycles", 1)),
        },
        "source_config": {
            "path": str(config_path.relative_to(root)),
            "sha256": _sha256(config_path),
        },
        "checkpoint": {
            "path": str(checkpoint_path.relative_to(root)),
            "sha256": checkpoint_sha256,
            "parent_checkpoint": parent_checkpoint,
            "update": selected_update,
            "model_state_sha256": selected_model_state_sha256,
        },
        "initial_model_state_sha256": initial_model_state_sha256,
        "optimizer_updates": optimizer_updates,
        "dev_checkpoint_selection": dev_selection,
        "train": train_summaries,
        "dev": dev_summaries,
        "reward_component_totals": {
            key: sum(float(row["reward_components"].get(key, 0.0)) for row in train_summaries)
            for key in train_summaries[0]["reward_components"]
        } if train_summaries else {},
        "scorecard": {
            "dev_wins": sum(row["outcome"] == "win" for row in dev_summaries),
            "dev_episodes": len(dev_summaries),
            "dev_mean_core_health": sum(row["core_health"] for row in dev_summaries) / max(1, len(dev_summaries)),
            "dev_mean_idle_fraction": sum(row["idle_fraction"] for row in dev_summaries) / max(1, len(dev_summaries)),
        },
        "action_state_trace_digest": _json_digest([row["trace_digest"] for row in dev_summaries]),
        "deterministic_checkpoint_verification": verification,
        "artifacts": [
            *(str(path.relative_to(root)) for path in produced_checkpoints),
            *(str(path.relative_to(root)) for path in verification_paths),
            *(
                [str((checkpoint_path.parent / "reward-adversaries.json").relative_to(root))]
                if (checkpoint_path.parent / "reward-adversaries.json").exists()
                else []
            ),
            str(checkpoint_path.with_suffix(".manifest.json").relative_to(root)),
        ],
    }
    if teacher_warmup is not None:
        manifest["teacher_warmup"] = teacher_warmup
        manifest["rollout_update_counts"]["teacher_warmup_episodes"] = len(
            teacher_warmup["episodes"]
        )
        manifest["rng_seeds"]["teacher_warmup_shuffle_seed"] = config[
            "teacher_warmup_shuffle_seed"
        ]
        manifest["rng_seeds"]["teacher_warmup_minibatch_seed"] = config[
            "teacher_warmup_minibatch_seed"
        ]
        if config.get("teacher_warmup_seed_set") is not None:
            manifest["seed_sets"]["teacher_warmup"] = {
                key: teacher_warmup_set[key]
                for key in ("seed_set_id", "seed_set_version", "split")
            }
            manifest["rng_seeds"]["environment_root_seeds"][
                "teacher_warmup"
            ] = list(teacher_warmup_set["seeds"])
    if teacher_rehearsal is not None:
        manifest["teacher_rehearsal"] = teacher_rehearsal
        manifest["rollout_update_counts"]["teacher_rehearsal_updates"] = len(
            teacher_rehearsal["optimizer_updates"]
        )
        manifest["rng_seeds"]["teacher_rehearsal_minibatch_seed"] = config[
            "teacher_rehearsal_minibatch_seed"
        ]
    if selection_policy is not None:
        manifest["dev_checkpoint_selection_policy"] = selection_policy
    return manifest


def _reproducibility_evidence(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the path-independent fields that define one complete training run."""

    selection_policy = manifest.get("dev_checkpoint_selection_policy")
    selection_keys = ("update", "wins", "mean_return", "mean_core_health")
    if selection_policy is not None:
        selection_keys += ("mean_idle_fraction",)
    evidence = {
        "source_config_sha256": manifest["source_config"]["sha256"],
        "jvm_args": manifest["runtime"]["jvm_args"],
        "rng_seeds": manifest["rng_seeds"],
        "initial_model_state_sha256": manifest["initial_model_state_sha256"],
        "selected_checkpoint": {
            key: manifest["checkpoint"][key]
            for key in ("update", "model_state_sha256")
        },
        "optimizer_updates": manifest["optimizer_updates"],
        "dev_checkpoint_selection": [
            {
                key: row[key]
                for key in selection_keys
            }
            for row in manifest["dev_checkpoint_selection"]
        ],
        "train": manifest["train"],
        "dev": manifest["dev"],
        "scorecard": manifest["scorecard"],
        "action_state_trace_digest": manifest["action_state_trace_digest"],
        "deterministic_checkpoint_verification": {
            key: manifest["deterministic_checkpoint_verification"][key]
            for key in ("seed", "fresh_runs", "trace_digest_a", "trace_digest_b", "bit_exact")
        },
    }
    if selection_policy is not None:
        evidence["dev_checkpoint_selection_policy"] = selection_policy
    if manifest.get("teacher_warmup") is not None:
        evidence["teacher_warmup"] = manifest["teacher_warmup"]
    if manifest.get("teacher_rehearsal") is not None:
        evidence["teacher_rehearsal"] = manifest["teacher_rehearsal"]
    return evidence


def compare_run_manifests(first: Path, second: Path) -> str:
    """Require two independent full runs to have identical behavioral evidence."""

    manifests = [_load_json(path) for path in (first, second)]
    evidence = [_reproducibility_evidence(manifest) for manifest in manifests]
    digests = [_json_digest(item) for item in evidence]
    recorded = [
        manifest.get("full_run_reproducibility", {}).get("digest")
        for manifest in manifests
    ]
    if any(value != digest for value, digest in zip(recorded, digests)):
        raise RuntimeError("manifest reproducibility digest is missing or invalid")
    if evidence[0] != evidence[1]:
        raise RuntimeError(
            "independent full training runs diverged: "
            f"{digests[0][:16]} != {digests[1][:16]}"
        )
    print(f"full_run_reproducibility={digests[0][:16]} bit_exact=True")
    print("M8-PPO-REPRODUCIBILITY OK")
    return digests[0]


def train(config_path: Path, output_dir: Path, *, java: str, port: int) -> dict[str, Any]:
    root = repo_root()
    config = _load_json(config_path)
    selection_policy = _dev_checkpoint_selection_policy(config)
    teacher_warmup_policy = _teacher_warmup_policy(config)
    teacher_rehearsal_policy = _teacher_rehearsal_policy(config)
    _configure_torch(config)
    train_set = _seed_set(root, str(config["train_seed_set"]), "train")
    teacher_warmup_set = _teacher_warmup_train_set(root, train_set, config)
    dev_set = _seed_set(root, str(config["dev_seed_set"]), "dev")
    model = SelectorActorCritic(int(config["model_init_seed"]))
    initial_model_state_sha256 = _model_state_digest(model.state_dict())
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=float(config["learning_rate"]),
        eps=float(config["adam_epsilon"]),
    )
    action_generator = torch.Generator().manual_seed(int(config["action_sampling_seed"]))
    minibatch_generator = torch.Generator().manual_seed(int(config["minibatch_seed"]))
    teacher_warmup_generator = torch.Generator().manual_seed(
        int(teacher_warmup_policy["minibatch_seed"])
        if teacher_warmup_policy is not None
        else 0
    )
    teacher_rehearsal_generator = torch.Generator().manual_seed(
        int(teacher_rehearsal_policy["minibatch_seed"])
        if teacher_rehearsal_policy is not None
        else 0
    )
    train_episodes: list[EpisodeRollout] = []
    optimizer_updates: list[dict[str, Any]] = []
    seeds = _training_seed_schedule(train_set, config)
    teacher_warmup_seeds = _teacher_warmup_seed_schedule(
        teacher_warmup_set, config
    )
    teacher_warmup_report: dict[str, Any] | None = None
    teacher_warmup_path: Path | None = None
    teacher_rehearsal_episodes: list[EpisodeRollout] = []
    teacher_rehearsal_summaries: list[dict[str, Any]] = []
    teacher_rehearsal_updates: list[dict[str, Any]] = []
    teacher_rehearsal_report: dict[str, Any] | None = None
    teacher_rehearsal_path: Path | None = None
    episodes_per_update = int(config["episodes_per_update"])
    output_dir.mkdir(parents=True, exist_ok=True)
    dev_seeds = [int(seed) for seed in dev_set["seeds"]]
    dev_candidates: list[list[EpisodeRollout]] = []
    dev_selection: list[dict[str, Any]] = []
    produced_checkpoints: list[Path] = []
    parent_checkpoint = ""

    def record_dev_candidate(update: int, checkpoint: Path, checkpoint_sha: str) -> None:
        candidate_dev = _evaluate(
            model, dev_seeds, config, java=java, port=port + 1
        )
        dev_candidates.append(candidate_dev)
        summaries = [_episode_summary(item) for item in candidate_dev]
        row = {
            "update": update,
            "checkpoint_path": str(checkpoint.relative_to(root)),
            "checkpoint_sha256": checkpoint_sha,
            "wins": sum(item["outcome"] == "win" for item in summaries),
            "mean_return": sum(item["return"] for item in summaries)
            / len(summaries),
            "mean_core_health": sum(item["core_health"] for item in summaries)
            / len(summaries),
        }
        if selection_policy is not None:
            row["mean_idle_fraction"] = sum(
                item["idle_fraction"] for item in summaries
            ) / len(summaries)
        dev_selection.append(row)

    with RlServerProcess(
        LaunchConfig(port=port, java=java, build_if_missing=False)
    ) as env:
        env.handshake("m8-ppo-training")
        if teacher_warmup_seeds:
            model.eval()
            warmup_episodes = [
                rollout_episode(
                    env,
                    model,
                    seed=seed,
                    scenario_id=str(config["scenario_id"]),
                    scenario_version=int(config["scenario_version"]),
                    evaluation=True,
                    action_generator=action_generator,
                    reward_schema=str(config.get("reward_schema", REWARD_SCHEMA)),
                    quality_reward=config.get("quality_reward"),
                    teacher_controlled=True,
                )
                for seed in teacher_warmup_seeds
            ]
            model.train()
            warmup_metrics = teacher_trajectory_warmup_update(
                model,
                optimizer,
                warmup_episodes,
                config,
                teacher_warmup_generator,
            )
            warmup_summaries = [
                _episode_summary(episode) for episode in warmup_episodes
            ]
            teacher_warmup_path, teacher_warmup_report = (
                _write_teacher_warmup_report(
                    root,
                    output_dir,
                    config_path,
                    config,
                    teacher_warmup_set,
                    teacher_warmup_seeds,
                    warmup_summaries,
                    warmup_metrics,
                    initial_model_state_sha256,
                    _model_state_digest(model.state_dict()),
                )
            )
            if teacher_rehearsal_policy is not None:
                assert teacher_warmup_policy is not None
                teacher_rehearsal_episodes = [
                    episode
                    for episode in warmup_episodes
                    if not bool(teacher_warmup_policy["success_only"])
                    or episode.outcome == "win"
                ]
                teacher_rehearsal_summaries = [
                    _episode_summary(episode)
                    for episode in teacher_rehearsal_episodes
                ]
            del warmup_episodes
        for start in range(0, len(seeds), episodes_per_update):
            model.eval()
            batch = [
                rollout_episode(
                    env,
                    model,
                    seed=seed,
                    scenario_id=str(config["scenario_id"]),
                    scenario_version=int(config["scenario_version"]),
                    evaluation=False,
                    action_generator=action_generator,
                    reward_schema=str(config.get("reward_schema", REWARD_SCHEMA)),
                    quality_reward=config.get("quality_reward"),
                )
                for seed in seeds[start : start + episodes_per_update]
            ]
            train_episodes.extend(batch)
            model.train()
            update_number = len(optimizer_updates) + 1
            update_metrics = ppo_update(
                model, optimizer, batch, config, minibatch_generator
            )
            if teacher_rehearsal_policy is not None:
                rehearsal_metrics = teacher_trajectory_rehearsal_update(
                    model,
                    optimizer,
                    teacher_rehearsal_episodes,
                    config,
                    teacher_rehearsal_generator,
                )
                teacher_rehearsal_updates.append(
                    {"update": update_number, **rehearsal_metrics}
                )
                update_metrics["teacher_trajectory_rehearsal"] = rehearsal_metrics
                assert teacher_warmup_path is not None
                teacher_rehearsal_path, teacher_rehearsal_report = (
                    _write_teacher_rehearsal_report(
                        root,
                        output_dir,
                        config_path,
                        config,
                        teacher_warmup_path,
                        teacher_rehearsal_summaries,
                        teacher_rehearsal_updates,
                        _model_state_digest(model.state_dict()),
                    )
                )
            optimizer_updates.append(update_metrics)
            checkpoint = output_dir / f"selector-v1-update-{len(optimizer_updates)}.pt"
            checkpoint_sha = save_checkpoint(
                checkpoint,
                model,
                optimizer,
                config_sha256=_sha256(config_path),
                parent_checkpoint=parent_checkpoint,
                update=len(optimizer_updates),
                reward_schema=str(config.get("reward_schema", REWARD_SCHEMA)),
            )
            produced_checkpoints.append(checkpoint)
            parent_checkpoint = checkpoint_sha
            record_dev_candidate(
                len(optimizer_updates), checkpoint, checkpoint_sha
            )

    dev_frontier_path, best_index = _write_dev_checkpoint_frontier(
        root,
        output_dir,
        config_path,
        config,
        dev_set,
        dev_selection,
    )
    checkpoint_path = produced_checkpoints[best_index]
    checkpoint_sha = str(dev_selection[best_index]["checkpoint_sha256"])
    selected_payload = load_checkpoint(
        checkpoint_path,
        model,
        reward_schema=str(config.get("reward_schema", REWARD_SCHEMA)),
    )
    selected_model_state_sha256 = _model_state_digest(model.state_dict())
    dev_episodes = dev_candidates[best_index]

    verify_seed = int(dev_set["seeds"][0])
    traces = []
    for offset in (2, 3):
        replay_model = SelectorActorCritic(int(config["model_init_seed"]))
        load_checkpoint(
            checkpoint_path,
            replay_model,
            reward_schema=str(config.get("reward_schema", REWARD_SCHEMA)),
        )
        replay = _evaluate(
            replay_model, [verify_seed], config, java=java, port=port + offset
        )[0]
        traces.append(replay.trace)
    verification = {
        "seed": verify_seed,
        "fresh_runs": 2,
        "trace_digest_a": _json_digest(traces[0]),
        "trace_digest_b": _json_digest(traces[1]),
        "bit_exact": traces[0] == traces[1],
    }
    if not verification["bit_exact"]:
        raise RuntimeError("frozen checkpoint evaluation traces diverged")
    verification_paths = [
        output_dir / "checkpoint-replay-a.jsonl",
        output_dir / "checkpoint-replay-b.jsonl",
    ]
    for path, replay_trace in zip(verification_paths, traces):
        path.write_text(
            "".join(
                json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n"
                for item in replay_trace
            ),
            encoding="utf-8",
        )
    verification["trace_paths"] = [
        str(path.relative_to(root)) for path in verification_paths
    ]
    verification_paths.append(dev_frontier_path)
    if teacher_warmup_path is not None:
        verification_paths.append(teacher_warmup_path)
    if teacher_rehearsal_path is not None:
        verification_paths.append(teacher_rehearsal_path)

    train_summaries = [_episode_summary(item) for item in train_episodes]
    dev_summaries = [_episode_summary(item) for item in dev_episodes]
    training_trace_path = output_dir / "training-trace.jsonl"
    training_trace_path.write_text(
        "".join(
            json.dumps(
                {"seed": episode.seed, "transition": transition},
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
            for episode in train_episodes
            for transition in episode.trace
        ),
        encoding="utf-8",
    )
    verification_paths.append(training_trace_path)
    manifest = _manifest(
        root,
        config_path,
        config,
        train_set,
        teacher_warmup_set,
        dev_set,
        checkpoint_path,
        checkpoint_sha,
        train_summaries,
        dev_summaries,
        verification,
        optimizer_updates,
        dev_selection,
        str(selected_payload.get("parent_checkpoint", "")),
        produced_checkpoints,
        verification_paths,
        seeds,
        initial_model_state_sha256,
        selected_model_state_sha256,
        int(selected_payload["update"]),
        teacher_warmup_report,
        teacher_rehearsal_report,
    )
    reproducibility_digest = _json_digest(_reproducibility_evidence(manifest))
    manifest["full_run_reproducibility"] = {
        "schema": "selector_training_reproducibility_v1",
        "digest": reproducibility_digest,
    }
    manifest_path = checkpoint_path.with_suffix(".manifest.json")
    stable_manifest_path = output_dir / "selector-v1-run.manifest.json"
    rendered_manifest = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    manifest_path.write_text(rendered_manifest, encoding="utf-8")
    stable_manifest_path.write_text(rendered_manifest, encoding="utf-8")
    print(
        f"train={len(train_summaries)} dev={len(dev_summaries)} "
        f"dev_wins={manifest['scorecard']['dev_wins']} checkpoint={checkpoint_sha[:16]}"
    )
    print(
        f"checkpoint_replay={verification['trace_digest_a'][:16]} "
        f"bit_exact={verification['bit_exact']}"
    )
    print(f"manifest={manifest_path}")
    print(f"full_run_reproducibility={reproducibility_digest[:16]}")
    print("M8-PPO OK")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M8.4 one-seat masked PPO selector")
    root = repo_root()
    parser.add_argument(
        "--config",
        type=Path,
        default=root / "configs" / "training" / "m8-selector-v1.json",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=root / "runs" / "m8-selector-v1"
    )
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--compare-manifests", nargs=2, type=Path)
    args = parser.parse_args(argv)
    if args.compare_manifests:
        compare_run_manifests(*(path.resolve() for path in args.compare_manifests))
        return 0
    train(args.config.resolve(), args.output_dir.resolve(), java=args.java, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
