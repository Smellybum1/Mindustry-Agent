"""Governed candidate-native behavioral-cloning warm start for M9."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any, Sequence

import torch

from mindustry_agents.policies import CandidateNativePlannerV11
from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.training.ippo import (
    IPPO_MODEL_ARCHITECTURE,
    SharedRecurrentSelector,
    SharedSeatState,
    commit_all_seat_boundary,
    decide_all_seats,
    model_state_digest,
)
from mindustry_agents.training.ippo_artifacts import (
    load_ippo_checkpoint,
    save_ippo_checkpoint,
)
from mindustry_agents.training.ippo_diverse_roots import (
    diverse_training_seed_schedule,
)
from mindustry_agents.training.ippo_ppo import IPPOTransition, sha256_path


CONFIG_SHA256 = (
    "9fc15d1a0dd256452873fe7953374bb251ad1fbf172add0eb399d2c3541457e0"
)
PROTOCOL_SHA256 = (
    "72ced8386fdbdb8b076f95b2d2ec416235b339703b932e878b033f738942618a"
)
SOURCE_RESULT_SHA256 = (
    "81ea8df1d7dcf21ed945337dd23b93b804e4d187605282e6d98cffe4077695fa"
)
TRAIN_MINIMUM = 18_000_000_000
TRAIN_MAXIMUM = 19_000_000_000
DEV_MINIMUM = 19_000_000_000
DEV_MAXIMUM = 20_000_000_000


@dataclass(frozen=True)
class TeacherEpisode:
    seed: int
    outcome: str
    tick: int
    core_health: float
    transitions: tuple[IPPOTransition, ...]
    eligible_labels: int
    forced_controls: int
    trace_sha256: str


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _git_commit(root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()


def load_distillation_config(path: Path) -> dict[str, Any]:
    """Load ADR-0113's exact public-only recipe."""

    if sha256_path(path) != CONFIG_SHA256:
        raise ValueError("M9 distillation config digest drifted")
    config = json.loads(path.read_text(encoding="utf-8"))
    if (
        config.get("schema") != "m9_candidate_native_distillation_config_v1"
        or config.get("candidate_version")
        != "m9-candidate-native-distill-v1"
        or config.get("model_architecture") != IPPO_MODEL_ARCHITECTURE
        or config.get("confirmation_seed_set") is not None
        or config.get("held_out_seed_set") is not None
        or int(config.get("torch_threads", 0)) != 1
        or int(config.get("training_updates", 0)) != 32
        or int(config.get("episodes_per_update", 0)) != 64
    ):
        raise ValueError("M9 distillation config contract drifted")
    if config.get("distillation") != {
        "schema": "candidate_native_one_boundary_nll_v1",
        "teacher_controls_environment": True,
        "teacher_action_source": "candidate_native_planner_v11",
        "transition_filter": (
            "alive_and_no_forced_task_action_and_teacher_action_"
            "authoritatively_legal"
        ),
        "forced_controls": "executed_but_excluded_from_actor_loss",
        "loss": "mean_negative_log_probability_of_teacher_action",
        "hidden_input": (
            "current_model_private_hidden_at_teacher_boundary_detached"
        ),
        "hidden_state_reset": "episode_reset_or_authoritative_seat_death",
        "cross_agent_state": False,
        "critic_loss": False,
        "ppo_loss": False,
        "entropy_loss": False,
        "extra_rng": False,
    }:
        raise ValueError("M9 distillation learning contract drifted")
    return config


def _load_protocol(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    path = root / str(config["public_evaluation_protocol"])
    if sha256_path(path) != PROTOCOL_SHA256:
        raise ValueError("M9 distillation public protocol digest drifted")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if (
        protocol.get("schema")
        != "m9_candidate_native_distillation_public_protocol_v1"
        or protocol.get("seed_set") != config["dev_seed_set"]
        or any(
            protocol.get("downstream_authority", {}).get(key) is not False
            for key in (
                "may_promote",
                "may_authorize_mappo",
                "may_access_confirmation",
                "may_access_held_out",
                "may_authorize_human_session",
            )
        )
    ):
        raise ValueError("M9 distillation public authority drifted")
    return protocol


def _load_source(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    source = config["source_policy"]
    path = root / str(source["accepted_result"])
    if (
        str(source.get("accepted_result_sha256")) != SOURCE_RESULT_SHA256
        or sha256_path(path) != SOURCE_RESULT_SHA256
    ):
        raise ValueError("M9 distillation source result digest drifted")
    result = json.loads(path.read_text(encoding="utf-8"))
    if (
        result.get("schema")
        != "m9_candidate_native_planner_compact_result_v11"
        or result.get("passed") is not True
        or result.get("classification")
        != "candidate_native_supervision_source_supported"
        or result.get("confirmation_or_held_out_access") is not False
    ):
        raise ValueError("M9 distillation source is not accepted")
    return result


def _load_seed_set(
    root: Path,
    relative: str,
    *,
    split: str,
    count: int,
    lower: int,
    upper: int,
) -> tuple[dict[str, Any], Path]:
    path = root / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    seeds = [int(seed) for seed in document.get("seeds", [])]
    if (
        document.get("split") != split
        or len(seeds) != count
        or len(set(seeds)) != count
        or any(seed < lower or seed >= upper for seed in seeds)
    ):
        raise ValueError(f"M9 distillation {split} seed set drifted")
    return document, path


def _configure_torch(config: dict[str, Any]) -> None:
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(int(config["torch_threads"]))
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    if torch.get_num_threads() != 1:
        raise RuntimeError("M9 distillation torch thread pin failed")


def _teacher_episode(
    env: RlServerProcess,
    model: SharedRecurrentSelector,
    config: dict[str, Any],
    *,
    seed: int,
) -> TeacherEpisode:
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
    forced = 0
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
            teacher_actions=teacher,
        )
        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, int(metadata["tick_cap"]) - tick),
            agent_actions=decision.agent_actions,
            stop_on_decision_event=True,
        )
        if any(
            not result.get("accepted", False)
            for result in response.action_results
        ):
            raise RuntimeError("M9 distillation teacher action was rejected")
        planner.observe_action_results(response.action_results)
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
        for agent_id in decision.evaluation_order:
            features = decision.features[agent_id]
            action = decision.action_indices[agent_id]
            eligible = (
                features.forced_task_action is None
                and bool(features.action_mask[action])
            )
            if not eligible:
                forced += 1
                continue
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
                    action=action,
                    old_log_prob=decision.old_log_probabilities[agent_id],
                    old_value=decision.old_values[agent_id],
                    team_reward=0.0,
                    individual_reward=0.0,
                    advanced_ticks=advanced,
                    done=done,
                    policy_loss_mask=True,
                    recurrent_reset=decision.recurrent_resets[agent_id],
                )
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

    if outcome == "running" or not transitions:
        raise RuntimeError("M9 distillation teacher episode was incomplete")
    return TeacherEpisode(
        seed=seed,
        outcome=outcome,
        tick=tick,
        core_health=float(observations[0]["team"]["core_health"]),
        transitions=tuple(transitions),
        eligible_labels=len(transitions),
        forced_controls=forced,
        trace_sha256=_canonical_sha256(trace),
    )


def distillation_update(
    model: SharedRecurrentSelector,
    optimizer: torch.optim.Optimizer,
    transitions: Sequence[IPPOTransition],
    config: dict[str, Any],
    generator: torch.Generator,
) -> dict[str, float]:
    """Apply ADR-0113's detached one-boundary teacher-action NLL."""

    if not transitions:
        raise ValueError("M9 distillation update has no labels")
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
    if not bool(
        masks[torch.arange(len(transitions)), actions].all().item()
    ):
        raise ValueError("M9 distillation label is outside its mask")
    batch_size = int(config["minibatch_size"])
    losses = 0.0
    batches = 0
    correct = 0
    presentations = 0
    for _ in range(int(config["epochs_per_update"])):
        order = torch.randperm(len(transitions), generator=generator)
        for start in range(0, len(transitions), batch_size):
            index = order[start : start + batch_size]
            _, logits, _, _ = model(
                candidates[index],
                scalars[index],
                present[index],
                masks[index],
                agent_ids[index],
                hidden[index],
            )
            log_probabilities = torch.log_softmax(logits, dim=-1)
            loss = -log_probabilities.gather(
                1, actions[index, None]
            ).mean()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(), float(config["max_grad_norm"])
            )
            optimizer.step()
            losses += float(loss.item())
            batches += 1
            correct += int((torch.argmax(logits, dim=-1) == actions[index]).sum())
            presentations += len(index)
    return {
        "teacher_nll": losses / max(1, batches),
        "batches": float(batches),
        "labels": float(len(transitions)),
        "presentations": float(presentations),
        "presentation_top1_accuracy": correct / max(1, presentations),
    }


def _evaluate_episode(
    env: RlServerProcess,
    model: SharedRecurrentSelector,
    config: dict[str, Any],
    *,
    seed: int,
) -> dict[str, Any]:
    reset = env.reset(
        seed,
        scenario_id=str(config["scenario_id"]),
        scenario_version=int(config["scenario_version"]),
        agent_count=3,
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
        raise RuntimeError("M9 distillation evaluation was incomplete")
    return {
        "seed": seed,
        "outcome": outcome,
        "tick": tick,
        "core_health": float(observations[0]["team"]["core_health"]),
        "team_idle_fraction": float(metrics["idle_fraction"]),
        "trace_sha256": _canonical_sha256(trace),
    }


def _aggregate(episodes: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "episodes": len(episodes),
        "wins": sum(item["outcome"] == "win" for item in episodes),
        "mean_core_health": fmean(
            float(item["core_health"]) for item in episodes
        ),
        "mean_team_idle_fraction": fmean(
            float(item["team_idle_fraction"]) for item in episodes
        ),
    }


def _selection_key(row: dict[str, Any]) -> tuple[float, ...]:
    return (
        float(row["wins"]),
        float(row["mean_core_health"]),
        -float(row["mean_team_idle_fraction"]),
        -float(row["update"]),
    )


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_preflight(
    path: Path, root: Path, config: dict[str, Any]
) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    if (
        result.get("schema") != "m9_candidate_native_distill_preflight_v1"
        or result.get("passed") is not True
        or result.get("implementation_commit") != _git_commit(root)
        or result.get("config_sha256") != CONFIG_SHA256
        or result.get("protocol_sha256") != PROTOCOL_SHA256
        or result.get("confirmation_or_held_out_access") is not False
    ):
        raise ValueError("M9 distillation preflight is invalid")
    return result


def train(
    config_path: Path,
    output_dir: Path,
    preflight_path: Path,
    *,
    java: str,
    port: int,
) -> dict[str, Any]:
    """Run one full non-resumable candidate-native distillation replica."""

    root = repo_root()
    config = load_distillation_config(config_path)
    protocol = _load_protocol(root, config)
    source = _load_source(root, config)
    preflight = validate_preflight(preflight_path, root, config)
    _configure_torch(config)
    train_set, train_path = _load_seed_set(
        root,
        str(config["train_seed_set"]),
        split="train",
        count=2048,
        lower=TRAIN_MINIMUM,
        upper=TRAIN_MAXIMUM,
    )
    dev_set, dev_path = _load_seed_set(
        root,
        str(config["dev_seed_set"]),
        split="dev",
        count=40,
        lower=DEV_MINIMUM,
        upper=DEV_MAXIMUM,
    )
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("M9 distillation output directory is not empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    schedule = diverse_training_seed_schedule(
        train_set["seeds"], shuffle_seed=int(config["shuffle_seed"])
    )
    model = SharedRecurrentSelector(int(config["model_init_seed"]))
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=float(config["learning_rate"]),
        eps=float(config["adam_epsilon"]),
    )
    generator = torch.Generator().manual_seed(int(config["shuffle_seed"]))
    initial_digest = model_state_digest(model)
    updates: list[dict[str, Any]] = []
    selection: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    dev_by_update: list[list[dict[str, Any]]] = []
    parent: str | None = None
    dev_seeds = [int(seed) for seed in dev_set["seeds"]]

    with RlServerProcess(
        LaunchConfig(
            port=port,
            java=java,
            build_if_missing=False,
            log_dir=output_dir,
            log_name="rl-server",
        )
    ) as env:
        env.handshake("m9-candidate-native-distill-v1")
        for update in range(1, int(config["training_updates"]) + 1):
            start = (update - 1) * int(config["episodes_per_update"])
            seeds = schedule[
                start : start + int(config["episodes_per_update"])
            ]
            model.eval()
            episodes = []
            for index, seed in enumerate(seeds, start=1):
                episodes.append(
                    _teacher_episode(env, model, config, seed=int(seed))
                )
                if index % 8 == 0:
                    print(
                        "M9 DISTILL TRAIN "
                        f"update={update}/32 episode={index}/64",
                        flush=True,
                    )
            labels = [
                transition
                for episode in episodes
                for transition in episode.transitions
            ]
            model.train()
            metrics = distillation_update(
                model, optimizer, labels, config, generator
            )
            update_row = {
                "update": update,
                **metrics,
                "teacher_wins": sum(
                    episode.outcome == "win" for episode in episodes
                ),
                "forced_controls": sum(
                    episode.forced_controls for episode in episodes
                ),
                "teacher_trace_digest": _canonical_sha256(
                    [episode.trace_sha256 for episode in episodes]
                ),
            }
            updates.append(update_row)
            checkpoint_path = (
                output_dir / f"candidate-distill-update-{update}.pt"
            )
            checkpoint = save_ippo_checkpoint(
                checkpoint_path,
                model,
                optimizer,
                update=update,
                parent_checkpoint_content_sha256=parent,
                config_sha256_value=CONFIG_SHA256,
            )
            parent = str(checkpoint["checkpoint_content_sha256"])
            checkpoints.append(checkpoint)
            model.eval()
            dev = [
                _evaluate_episode(env, model, config, seed=seed)
                for seed in dev_seeds
            ]
            dev_by_update.append(dev)
            row = {
                "update": update,
                **_aggregate(dev),
                "checkpoint_content_sha256": checkpoint[
                    "checkpoint_content_sha256"
                ],
                "model_state_sha256": checkpoint["model_state_sha256"],
                "optimizer_state_sha256": checkpoint[
                    "optimizer_state_sha256"
                ],
            }
            row["eligible"] = (
                row["wins"]
                >= int(
                    config["checkpoint_selection"]["minimum_wins"]
                )
                and row["mean_team_idle_fraction"]
                < float(
                    config["checkpoint_selection"][
                        "maximum_mean_team_idle_fraction_exclusive"
                    ]
                )
            )
            selection.append(row)
            _write_json(
                output_dir / "progress.json",
                {
                    "schema": "m9_candidate_native_distill_progress_v1",
                    "update": update,
                    "train_episodes": update * 64,
                    "latest_dev": row,
                    "complete": False,
                },
            )
            print(
                "M9 DISTILL DEV "
                f"update={update}/32 wins={row['wins']}/40 "
                f"idle={row['mean_team_idle_fraction']:.6f} "
                f"eligible={row['eligible']}",
                flush=True,
            )

    eligible = [
        index for index, row in enumerate(selection) if row["eligible"]
    ]
    selected_index = (
        max(eligible, key=lambda index: _selection_key(selection[index]))
        if eligible
        else None
    )
    manifest: dict[str, Any] = {
        "schema": "m9_candidate_native_distillation_run_v1",
        "implementation_commit": _git_commit(root),
        "config_sha256": CONFIG_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_result_sha256": SOURCE_RESULT_SHA256,
        "source": source,
        "preflight_sha256": sha256_path(preflight_path),
        "preflight": preflight,
        "train_seed_set_sha256": sha256_path(train_path),
        "dev_seed_set_sha256": sha256_path(dev_path),
        "initial_model_state_sha256": initial_digest,
        "optimizer_updates": updates,
        "checkpoint_selection": selection,
        "construction_passed": selected_index is not None,
        "confirmation_or_held_out_access": False,
    }
    if selected_index is not None:
        selected = checkpoints[selected_index]
        manifest["selected_checkpoint"] = {
            **{
                key: selected[key]
                for key in (
                    "file_sha256",
                    "checkpoint_content_sha256",
                    "model_state_sha256",
                    "optimizer_state_sha256",
                    "update",
                    "parent_checkpoint_content_sha256",
                )
            },
            "path": str(Path(selected["path"]).relative_to(root).as_posix()),
        }
        manifest["dev"] = dev_by_update[selected_index]
        replay_summaries = []
        for model_seed, replay_port in ((1, port), (2, port)):
            replay_model = SharedRecurrentSelector(model_seed)
            load_ippo_checkpoint(
                Path(selected["path"]),
                replay_model,
                expected_config_sha256=CONFIG_SHA256,
            )
            with RlServerProcess(
                LaunchConfig(
                    port=replay_port,
                    java=java,
                    build_if_missing=False,
                )
            ) as replay_env:
                replay_env.handshake("m9-distill-checkpoint-replay")
                replay_summaries.append(
                    _evaluate_episode(
                        replay_env,
                        replay_model,
                        config,
                        seed=dev_seeds[0],
                    )
                )
        if replay_summaries[0] != replay_summaries[1]:
            raise RuntimeError("M9 distillation checkpoint replay diverged")
        manifest["deterministic_checkpoint_verification"] = {
            "fresh_runs": 2,
            "seed": dev_seeds[0],
            "summary": replay_summaries[0],
            "bit_exact": True,
        }
    manifest["canonical_run_sha256"] = _canonical_sha256(manifest)
    manifest_path = output_dir / "candidate-distill-run.manifest.json"
    _write_json(manifest_path, manifest)
    _write_json(
        output_dir / "progress.json",
        {
            "schema": "m9_candidate_native_distill_progress_v1",
            "update": 32,
            "train_episodes": 2048,
            "complete": True,
            "construction_passed": manifest["construction_passed"],
            "selected_update": (
                manifest.get("selected_checkpoint", {}).get("update")
            ),
        },
    )
    return manifest


def compare_replicas(
    first: Path, second: Path, *, output: Path | None = None
) -> dict[str, Any]:
    documents = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (first, second)
    ]
    ignored = {"preflight_sha256", "canonical_run_sha256"}
    canonical = [
        {key: value for key, value in document.items() if key not in ignored}
        for document in documents
    ]
    if canonical[0] != canonical[1]:
        raise RuntimeError("M9 distillation replicas diverged")
    result = {
        "schema": "m9_candidate_native_distillation_replica_comparison_v1",
        "construction_passed": bool(
            documents[0].get("construction_passed")
        ),
        "canonical_full_run_sha256": _canonical_sha256(canonical[0]),
        "selected_checkpoint_content_sha256": documents[0]
        .get("selected_checkpoint", {})
        .get("checkpoint_content_sha256"),
        "exact_replica": True,
        "confirmation_or_held_out_access": False,
    }
    if output is not None:
        _write_json(output, result)
    return result


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=root
        / "configs/training/m9-candidate-native-distill-v1.json",
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--compare-runs", nargs=2, type=Path)
    parser.add_argument("--comparison-output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.compare_runs:
            result = compare_replicas(
                *args.compare_runs,
                output=args.comparison_output,
            )
            print(
                "M9 DISTILL REPLICAS OK "
                f"construction={result['construction_passed']}"
            )
            return 0 if result["construction_passed"] else 2
        if args.output_dir is None or args.preflight is None:
            parser.error("--output-dir and --preflight are required")
        manifest = train(
            args.config.resolve(),
            args.output_dir.resolve(),
            args.preflight.resolve(),
            java=args.java,
            port=args.port,
        )
    except Exception as error:
        print(f"M9 DISTILL FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "M9 DISTILL COMPLETE "
        f"construction={manifest['construction_passed']} "
        f"selected={manifest.get('selected_checkpoint', {}).get('update')}"
    )
    return 0 if manifest["construction_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
