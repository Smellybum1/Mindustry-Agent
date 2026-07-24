"""Exact-commit public preflight for ADR-0135 joint-bundle training."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

import torch

from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.training.candidate_distill import (
    _configure_torch,
    _git_commit,
    _write_json,
)
from mindustry_agents.training.candidate_joint_bundle import (
    ACTION_COUNT,
    CONFIG_SHA256,
    PROTOCOL_SHA256,
    JointBundleBoundary,
    JointBundleEpisode,
    JointBundleSelector,
    _bundle_index,
    collect_joint_bundle_episode,
    joint_bundle_update,
    load_joint_bundle_config,
    source_model_and_optimizer,
    validate_protocol,
)
from mindustry_agents.training.candidate_joint_bundle_train import (
    load_checkpoint,
    save_checkpoint,
)
from mindustry_agents.training.ippo import (
    SharedRecurrentSelector,
    model_state_digest,
)
from mindustry_agents.training.ippo_artifacts import _state_digest
from mindustry_agents.training.ippo_ppo import IPPOTransition, sha256_path


def _synthetic_transition(agent_id: int, action: int) -> IPPOTransition:
    candidates = torch.zeros((8, 37), dtype=torch.float32)
    for index in range(8):
        candidates[index, index % 13] = (index + 1) / 10.0
        candidates[index, 13 + (index % 16)] = 1.0
    scalars = torch.linspace(0.0, 1.0, 160)
    scalars = torch.roll(scalars, agent_id)
    return IPPOTransition(
        agent_id=agent_id,
        candidates=candidates,
        scalars=scalars,
        candidate_present=torch.ones(8, dtype=torch.bool),
        action_mask=torch.ones(ACTION_COUNT, dtype=torch.bool),
        hidden_input=torch.full((64,), agent_id / 10.0),
        action=action,
        old_log_prob=0.0,
        old_value=0.0,
        team_reward=0.0,
        individual_reward=0.0,
        advanced_ticks=60,
        done=False,
        policy_loss_mask=True,
        recurrent_reset=False,
    )


def _synthetic_episode() -> JointBundleEpisode:
    boundaries = (
        JointBundleBoundary(
            transitions=tuple(
                _synthetic_transition(agent_id, agent_id + 1)
                for agent_id in range(3)
            ),
            student_actions=(0, 0, 0),
        ),
        JointBundleBoundary(
            transitions=(
                _synthetic_transition(0, 4),
                _synthetic_transition(2, 5),
            ),
            student_actions=(0, 0),
        ),
        JointBundleBoundary(
            transitions=(_synthetic_transition(1, 6),),
            student_actions=(0,),
        ),
    )
    return JointBundleEpisode(
        seed=1,
        outcome="loss",
        tick=120,
        core_health=0.0,
        boundaries=boundaries,
        actor_labels=6,
        forced_controls=0,
        student_teacher_matches=0,
        rejected_student_actions=0,
        trace_sha256="0" * 64,
    )


def _inherited_digest(model: JointBundleSelector) -> str:
    inherited = {
        name: value
        for name, value in model.state_dict().items()
        if not name.startswith("pairwise_head.")
    }
    base = SharedRecurrentSelector(1)
    base.load_state_dict(inherited)
    return model_state_digest(base)


def _zero_factorization(
    model: JointBundleSelector,
) -> dict[str, Any]:
    transitions = [
        _synthetic_transition(agent_id, agent_id + 1)
        for agent_id in range(3)
    ]
    masked_rows = []
    descriptors = []
    per_seat_losses = []
    for transition in transitions:
        arguments = (
            transition.candidates.unsqueeze(0),
            transition.scalars.unsqueeze(0),
            transition.candidate_present.unsqueeze(0),
            transition.action_mask.unsqueeze(0),
            torch.tensor([transition.agent_id]),
            transition.hidden_input.unsqueeze(0),
        )
        with torch.no_grad():
            _, masked, _, _, descriptor = (
                model.forward_with_descriptors(*arguments)
            )
        masked_rows.append(masked[0])
        descriptors.append(descriptor[0])
        per_seat_losses.append(
            -torch.log_softmax(masked[0], dim=-1)[transition.action]
        )
    masked = torch.stack(masked_rows)[None, :]
    descriptor_batch = torch.stack(descriptors)[None, :]
    with torch.no_grad():
        scores = model.joint_scores(masked, descriptor_batch)
    expected = (
        masked_rows[0][:, None, None]
        + masked_rows[1][None, :, None]
        + masked_rows[2][None, None, :]
    ).reshape(1, 1000)
    target = _bundle_index([item.action for item in transitions])
    joint_loss = -torch.log_softmax(scores[0], dim=-1)[target] / 3.0
    independent_loss = torch.stack(per_seat_losses).mean()
    difference = abs(float((joint_loss - independent_loss).item()))
    if not torch.equal(scores, expected) or difference > 5e-6:
        raise RuntimeError("M9 joint-bundle zero factorization drifted")
    return {
        "bundle_scores_bit_exact": True,
        "joint_argmax": int(torch.argmax(scores[0]).item()),
        "independent_bundle_index": _bundle_index(
            [int(torch.argmax(row).item()) for row in masked_rows]
        ),
        "normalized_nll_absolute_difference": difference,
        "normalized_nll_equivalent": True,
    }


def _configured_replicas(
    root: Path, config: dict[str, Any]
) -> dict[str, Any]:
    rows = []
    models = []
    optimizers = []
    for _ in range(2):
        model, optimizer, _ = source_model_and_optimizer(root, config)
        metrics = joint_bundle_update(
            model,
            optimizer,
            [_synthetic_episode()],
            config,
            torch.Generator().manual_seed(int(config["shuffle_seed"])),
        )
        rows.append(
            {
                "model_state_sha256": model_state_digest(model),
                "optimizer_state_sha256": _state_digest(
                    optimizer.state_dict()
                ),
                "metrics": metrics,
            }
        )
        models.append(model)
        optimizers.append(optimizer)
    if rows[0] != rows[1]:
        raise RuntimeError("M9 joint-bundle optimizer replicas diverged")
    if torch.count_nonzero(models[0].pairwise_head[-1].weight) == 0:
        raise RuntimeError("M9 joint-bundle pairwise head received no gradient")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "checkpoint.pt"
        saved = save_checkpoint(
            path,
            models[0],
            optimizers[0],
            update=65,
            parent_checkpoint_content_sha256="a" * 64,
        )
        restored, restored_optimizer, _ = source_model_and_optimizer(
            root, config
        )
        loaded = load_checkpoint(path, restored, restored_optimizer)
        if (
            saved["checkpoint_content_sha256"]
            != loaded["checkpoint_content_sha256"]
            or model_state_digest(restored)
            != model_state_digest(models[0])
            or _state_digest(restored_optimizer.state_dict())
            != _state_digest(optimizers[0].state_dict())
        ):
            raise RuntimeError("M9 joint-bundle checkpoint replay drifted")
    return {
        "replicas_equal": True,
        "model_state_sha256": rows[0]["model_state_sha256"],
        "optimizer_state_sha256": rows[0]["optimizer_state_sha256"],
        "metrics": rows[0]["metrics"],
        "pairwise_gradient_nonzero": True,
        "checkpoint_round_trip_exact": True,
    }


def _live_reset_check(
    root: Path,
    config: dict[str, Any],
    *,
    java: str,
    port: int,
) -> dict[str, Any]:
    train_set = json.loads(
        (root / str(config["train_seed_set"])).read_text(encoding="utf-8")
    )
    seed = int(train_set["seeds"][0])
    model, _, _ = source_model_and_optimizer(root, config)
    before = model_state_digest(model)
    with RlServerProcess(
        LaunchConfig(
            port=port,
            java=java,
            build_if_missing=False,
        )
    ) as env:
        env.handshake("m9-joint-bundle-live-preflight")
        first = collect_joint_bundle_episode(env, model, config, seed=seed)
        second = collect_joint_bundle_episode(env, model, config, seed=seed)
    summaries = [
        {
            "outcome": item.outcome,
            "tick": item.tick,
            "core_health": item.core_health,
            "atomic_boundaries": len(item.boundaries),
            "actor_labels": item.actor_labels,
            "forced_controls": item.forced_controls,
            "student_teacher_matches": item.student_teacher_matches,
            "rejected_student_actions": item.rejected_student_actions,
            "trace_sha256": item.trace_sha256,
        }
        for item in (first, second)
    ]
    if summaries[0] != summaries[1] or model_state_digest(model) != before:
        raise RuntimeError("M9 joint-bundle live reset replay drifted")
    return {
        "seed": seed,
        "terminal_reset_reports_equal": True,
        "summary": summaries[0],
        "model_unchanged": True,
    }


def build_report(
    root: Path,
    config_path: Path,
    *,
    java: str,
    port: int,
    live: bool,
) -> dict[str, Any]:
    """Build the complete local public-only preflight report."""

    config = load_joint_bundle_config(config_path)
    validate_protocol(root, config)
    _configure_torch(config)
    source_file = root / str(config["source_checkpoint"]["path"])
    source_file_before = sha256_path(source_file)
    model, optimizer, payload = source_model_and_optimizer(root, config)
    inherited_digest = _inherited_digest(model)
    if inherited_digest != payload["model_state_sha256"]:
        raise RuntimeError("M9 joint-bundle inherited model drifted")
    if len(optimizer.param_groups) != 2 or any(
        parameter in optimizer.state
        for parameter in optimizer.param_groups[1]["params"]
    ):
        raise RuntimeError("M9 joint-bundle new Adam group is not empty")
    if torch.count_nonzero(model.pairwise_head[-1].weight) or torch.count_nonzero(
        model.pairwise_head[-1].bias
    ):
        raise RuntimeError("M9 joint-bundle final head is not zero")
    factorization = _zero_factorization(model)
    replicas = _configured_replicas(root, config)
    live_result = (
        _live_reset_check(root, config, java=java, port=port)
        if live
        else {"skipped": True}
    )
    if sha256_path(source_file) != source_file_before:
        raise RuntimeError("M9 joint-bundle source checkpoint changed")
    return {
        "schema": "m9_candidate_native_joint_bundle_preflight_v1",
        "passed": True,
        "implementation_commit": _git_commit(root),
        "config_sha256": CONFIG_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_checkpoint": {
            "file_sha256": source_file_before,
            "checkpoint_content_sha256": payload[
                "checkpoint_content_sha256"
            ],
            "model_state_sha256": payload["model_state_sha256"],
            "optimizer_state_sha256": payload["optimizer_state_sha256"],
            "selected_or_promoted": False,
            "repaired": False,
            "unchanged": True,
        },
        "inherited_model_state_sha256": inherited_digest,
        "inherited_optimizer_state_entries": len(
            payload["optimizer_state"]["state"]
        ),
        "new_optimizer_group_empty": True,
        "pairwise_final_layer_zero": True,
        "zero_factorization": factorization,
        "configured_optimizer_replicas": replicas,
        "live_terminal_reset": live_result,
        "confirmation_or_held_out_access": False,
    }


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=(
            root
            / "configs/training/m9-candidate-native-joint-bundle-v1.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "runs/m9-candidate-joint-bundle-preflight.json",
    )
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--skip-live", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build_report(
            root,
            args.config.resolve(),
            java=args.java,
            port=args.port,
            live=not args.skip_live,
        )
        _write_json(args.output.resolve(), report)
    except Exception as error:
        print(f"M9 JOINT BUNDLE PREFLIGHT FAIL: {error}")
        return 1
    print(
        "M9 JOINT BUNDLE PREFLIGHT OK "
        f"commit={report['implementation_commit'][:12]} "
        f"live={not args.skip_live}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
