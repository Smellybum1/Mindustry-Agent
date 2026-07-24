"""Exact-commit preflight for ADR-0127 sequence relabeling."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

import torch

from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.training.candidate_distill import (
    _configure_torch,
    _write_json,
    distillation_update,
)
from mindustry_agents.training.candidate_distill_check import (
    _synthetic_transitions,
)
from mindustry_agents.training.candidate_on_policy_relabel import (
    _git_commit,
    _student_episode,
)
from mindustry_agents.training.candidate_sequence_relabel import (
    CONFIG_SHA256,
    PROTOCOL_SHA256,
    SEQUENCE_LENGTH,
    SOURCE_CHECKPOINT_CONTENT_SHA256,
    SOURCE_DIAGNOSTIC_SHA256,
    SOURCE_RESULT_SHA256,
    _load_protocol,
    _load_source,
    _sequence_distillation_update_contract,
    _source_model_and_optimizer,
    _student_sequence_episode,
    load_sequence_relabel_config,
    sequence_distillation_update,
    supervised_sequence_windows,
)
from mindustry_agents.training.ippo import (
    SharedRecurrentSelector,
    model_state_digest,
)
from mindustry_agents.training.ippo_artifacts import save_ippo_checkpoint
from mindustry_agents.training.ippo_ppo import (
    IPPOEpisodeRollout,
    IPPOTransition,
)


def _episodes_for_synthetic_sequence(
    transitions: Sequence[IPPOTransition],
) -> list[IPPOEpisodeRollout]:
    seen: set[int] = set()
    prepared = []
    for item in transitions:
        prepared.append(
            replace(
                item,
                recurrent_reset=item.agent_id not in seen,
                policy_loss_mask=(len(prepared) % 5 != 0),
            )
        )
        seen.add(item.agent_id)
    return [
        IPPOEpisodeRollout(
            seed=1,
            outcome="win",
            transitions=tuple(prepared),
        )
    ]


def _single_transition_episodes(
    transitions: Sequence[IPPOTransition],
) -> list[IPPOEpisodeRollout]:
    return [
        IPPOEpisodeRollout(
            seed=index,
            outcome="win",
            transitions=(
                replace(
                    item,
                    recurrent_reset=True,
                    policy_loss_mask=True,
                ),
            ),
        )
        for index, item in enumerate(transitions)
    ]


def _length_one_equivalence_probe(
    root: Path,
    config: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    transitions = _synthetic_transitions()
    episodes = _single_transition_episodes(transitions)
    old_model, old_optimizer, _ = _source_model_and_optimizer(root, config)
    new_model, new_optimizer, _ = _source_model_and_optimizer(root, config)
    seed = int(config["shuffle_seed"])
    old_metrics = distillation_update(
        old_model,
        old_optimizer,
        transitions,
        config,
        torch.Generator().manual_seed(seed),
    )
    new_metrics = _sequence_distillation_update_contract(
        new_model,
        new_optimizer,
        episodes,
        config,
        torch.Generator().manual_seed(seed),
        sequence_length=1,
        sequences_per_minibatch=int(config["minibatch_size"]),
    )
    old_checkpoint = save_ippo_checkpoint(
        output.with_name(f"{output.stem}-length1-flat.pt"),
        old_model,
        old_optimizer,
        update=65,
        parent_checkpoint_content_sha256=(
            SOURCE_CHECKPOINT_CONTENT_SHA256
        ),
        config_sha256_value=CONFIG_SHA256,
    )
    new_checkpoint = save_ippo_checkpoint(
        output.with_name(f"{output.stem}-length1-sequence.pt"),
        new_model,
        new_optimizer,
        update=65,
        parent_checkpoint_content_sha256=(
            SOURCE_CHECKPOINT_CONTENT_SHA256
        ),
        config_sha256_value=CONFIG_SHA256,
    )
    if (
        old_metrics["teacher_nll"] != new_metrics["teacher_nll"]
        or old_metrics["presentation_top1_accuracy"]
        != new_metrics["presentation_top1_accuracy"]
        or old_checkpoint["checkpoint_content_sha256"]
        != new_checkpoint["checkpoint_content_sha256"]
    ):
        raise RuntimeError(
            "M9 sequence length-one flat optimizer equivalence diverged"
        )
    return {
        "matches_flat_optimizer_exactly": True,
        "checkpoint_content_sha256": old_checkpoint[
            "checkpoint_content_sha256"
        ],
        "model_state_sha256": old_checkpoint["model_state_sha256"],
        "optimizer_state_sha256": old_checkpoint[
            "optimizer_state_sha256"
        ],
        "teacher_nll": old_metrics["teacher_nll"],
    }


def _configured_optimizer_probe(
    root: Path,
    config: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    episodes = _episodes_for_synthetic_sequence(_synthetic_transitions())
    rows = []
    for replica in ("a", "b"):
        model, optimizer, _ = _source_model_and_optimizer(root, config)
        metrics = sequence_distillation_update(
            model,
            optimizer,
            episodes,
            config,
            torch.Generator().manual_seed(int(config["shuffle_seed"])),
        )
        checkpoint = save_ippo_checkpoint(
            output.with_name(
                f"{output.stem}-sequence-{replica}.pt"
            ),
            model,
            optimizer,
            update=65,
            parent_checkpoint_content_sha256=(
                SOURCE_CHECKPOINT_CONTENT_SHA256
            ),
            config_sha256_value=CONFIG_SHA256,
        )
        rows.append(
            {
                "model_state_sha256": model_state_digest(model),
                "optimizer_state_sha256": checkpoint[
                    "optimizer_state_sha256"
                ],
                "checkpoint_content_sha256": checkpoint[
                    "checkpoint_content_sha256"
                ],
                "metrics": metrics,
            }
        )
    if rows[0] != rows[1]:
        raise RuntimeError("M9 sequence optimizer replicas diverged")
    metrics = rows[0]["metrics"]
    if (
        metrics["labels"] != 32.0
        or metrics["sequence_windows"] <= 0
        or metrics["retained_context_transitions"] <= 0
        or metrics["real_transition_presentations"] != 320.0
        or metrics["padded_transition_slots"] != 64.0
    ):
        raise RuntimeError("M9 sequence optimizer telemetry drifted")
    return {"replicas_equal": True, **rows[0]}


def _context_gradient_probe(config: dict[str, Any]) -> dict[str, Any]:
    transitions = _synthetic_transitions()[:2]
    first = replace(
        transitions[0],
        agent_id=0,
        recurrent_reset=True,
        policy_loss_mask=False,
    )
    label = replace(
        transitions[1],
        agent_id=0,
        recurrent_reset=False,
        policy_loss_mask=True,
    )
    altered = replace(first, scalars=first.scalars + 1.0)
    episodes = [
        IPPOEpisodeRollout(1, "win", (first, label)),
        IPPOEpisodeRollout(1, "win", (altered, label)),
    ]
    digests = []
    for episode in episodes:
        selector = SharedRecurrentSelector(9601)
        optimizer = torch.optim.Adam(
            selector.parameters(),
            lr=float(config["learning_rate"]),
            eps=float(config["adam_epsilon"]),
        )
        local = copy.deepcopy(config)
        local["epochs_per_update"] = 1
        _sequence_distillation_update_contract(
            selector,
            optimizer,
            [episode],
            local,
            torch.Generator().manual_seed(int(config["shuffle_seed"])),
            sequence_length=2,
            sequences_per_minibatch=1,
        )
        digests.append(model_state_digest(selector))
    if digests[0] == digests[1]:
        raise RuntimeError(
            "M9 sequence loss ignored preceding masked context"
        )
    return {
        "masked_context_changes_supervised_gradient": True,
        "baseline_model_state_sha256": digests[0],
        "altered_context_model_state_sha256": digests[1],
    }


def _inherited_contract_probe(
    root: Path, config: dict[str, Any]
) -> dict[str, Any]:
    parent = json.loads(
        (
            root
            / "configs/training/"
            "m9-candidate-native-on-policy-relabel-v1.json"
        ).read_text(encoding="utf-8")
    )
    exact_keys = (
        "teacher_policy",
        "runtime_contract",
        "scenario_id",
        "scenario_version",
        "agent_count",
        "train_seed_set",
        "train_seed_set_sha256",
        "dev_seed_set",
        "dev_seed_set_sha256",
        "confirmation_seed_set",
        "held_out_seed_set",
        "shuffle_seed",
        "torch_threads",
        "continuation_updates",
        "episodes_per_update",
        "learning_rate",
        "adam_epsilon",
        "epochs_per_update",
        "minibatch_size",
        "max_grad_norm",
        "model_architecture",
    )
    schedule_keys = (
        "root_count",
        "reuse_count",
        "shuffle",
        "shuffle_seed",
        "updates",
        "episodes_per_update",
    )
    selection_keys = (
        "minimum_wins",
        "maximum_mean_team_idle_fraction_exclusive",
        "ranking",
    )
    if any(config[key] != parent[key] for key in exact_keys):
        raise ValueError("M9 sequence inherited config drifted")
    if any(
        config["training_root_schedule"][key]
        != parent["training_root_schedule"][key]
        for key in schedule_keys
    ):
        raise ValueError("M9 sequence inherited schedule drifted")
    if any(
        config["checkpoint_selection"][key]
        != parent["checkpoint_selection"][key]
        for key in selection_keys
    ):
        raise ValueError("M9 sequence inherited selection drifted")
    return {
        "parent_candidate": parent["candidate_version"],
        "exact_config_fields": list(exact_keys),
        "exact_schedule_fields": list(schedule_keys),
        "exact_selection_fields": list(selection_keys),
        "only_learning_change": "contiguous_truncated_bptt_teacher_nll",
        "passed": True,
    }


def _transitions_equal(
    first: IPPOTransition, second: IPPOTransition
) -> bool:
    scalar_fields = (
        "agent_id",
        "action",
        "old_log_prob",
        "old_value",
        "team_reward",
        "individual_reward",
        "advanced_ticks",
        "done",
        "policy_loss_mask",
        "recurrent_reset",
    )
    tensor_fields = (
        "candidates",
        "scalars",
        "candidate_present",
        "action_mask",
        "hidden_input",
    )
    return all(
        getattr(first, key) == getattr(second, key)
        for key in scalar_fields
    ) and all(
        torch.equal(getattr(first, key), getattr(second, key))
        for key in tensor_fields
    )


def _supervised_projection_matches(
    sequence_episode: Any, flat_episode: Any
) -> bool:
    supervised = [
        item
        for item in sequence_episode.transitions
        if item.policy_loss_mask
    ]
    return len(supervised) == len(flat_episode.transitions) and all(
        _transitions_equal(first, second)
        for first, second in zip(
            supervised, flat_episode.transitions, strict=True
        )
    )


def build_report(
    root: Path,
    output: Path,
    *,
    java: str,
    port: int,
    live: bool = True,
) -> dict[str, Any]:
    config_path = (
        root
        / "configs/training/"
        "m9-candidate-native-sequence-relabel-v1.json"
    )
    config = load_sequence_relabel_config(config_path)
    _load_protocol(root, config)
    _load_source(root, config)
    _configure_torch(config)
    inherited = _inherited_contract_probe(root, config)
    length_one = _length_one_equivalence_probe(root, config, output)
    configured = _configured_optimizer_probe(root, config, output)
    context = _context_gradient_probe(config)
    live_result: dict[str, Any] = {"ran": False}
    if live:
        from mindustry_agents.training.candidate_distill import (
            TRAIN_MAXIMUM,
            TRAIN_MINIMUM,
            _load_seed_set,
        )

        train_set, _ = _load_seed_set(
            root,
            str(config["train_seed_set"]),
            split="train",
            count=2048,
            lower=TRAIN_MINIMUM,
            upper=TRAIN_MAXIMUM,
        )
        seed = int(train_set["seeds"][0])
        model, _, _ = _source_model_and_optimizer(root, config)
        with RlServerProcess(
            LaunchConfig(
                port=port,
                java=java,
                build_if_missing=False,
            )
        ) as env:
            env.handshake("m9-candidate-sequence-relabel-preflight")
            first = _student_sequence_episode(
                env, model, config, seed=seed
            )
            second = _student_sequence_episode(
                env, model, config, seed=seed
            )
            flat = _student_episode(env, model, config, seed=seed)

        def identity(item: Any) -> dict[str, Any]:
            return {
                "seed": item.seed,
                "outcome": item.outcome,
                "tick": item.tick,
                "core_health": item.core_health,
                "eligible_labels": item.eligible_labels,
                "forced_controls": item.forced_controls,
                "student_teacher_matches": (
                    item.student_teacher_matches
                ),
                "rejected_student_actions": (
                    item.rejected_student_actions
                ),
                "trace_sha256": item.trace_sha256,
            }

        _, windows, metrics = supervised_sequence_windows(
            [first], sequence_length=SEQUENCE_LENGTH
        )
        if identity(first) != identity(second):
            raise RuntimeError(
                "M9 sequence terminal reset replay diverged"
            )
        if identity(first) != identity(flat):
            raise RuntimeError(
                "M9 sequence student control diverged from flat collector"
            )
        if not _supervised_projection_matches(first, flat):
            raise RuntimeError(
                "M9 sequence supervised projection diverged"
            )
        if (
            first.context_transitions <= 0
            or not windows
            or metrics["retained_transitions"]
            > len(first.transitions)
        ):
            raise RuntimeError("M9 sequence live context is invalid")
        live_result = {
            "ran": True,
            "terminal_reset_replay_equal": True,
            "student_control_matches_flat_collector": True,
            "supervised_projection_matches_flat_collector": True,
            "context_transitions": first.context_transitions,
            "retained_windows": len(windows),
            **identity(first),
        }
    report = {
        "schema": "m9_candidate_native_sequence_relabel_preflight_v1",
        "implementation_commit": _git_commit(root),
        "config_sha256": CONFIG_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_result_sha256": SOURCE_RESULT_SHA256,
        "source_diagnostic_sha256": SOURCE_DIAGNOSTIC_SHA256,
        "source_checkpoint_content_sha256": (
            SOURCE_CHECKPOINT_CONTENT_SHA256
        ),
        "inherited_contract_probe": inherited,
        "length_one_equivalence_probe": length_one,
        "configured_optimizer_probe": configured,
        "context_gradient_probe": context,
        "live_student_state_probe": live_result,
        "confirmation_or_held_out_access": False,
        "passed": (
            inherited["passed"]
            and length_one["matches_flat_optimizer_exactly"]
            and configured["replicas_equal"]
            and context["masked_context_changes_supervised_gradient"]
            and (
                not live
                or (
                    live_result["terminal_reset_replay_equal"]
                    and live_result[
                        "student_control_matches_flat_collector"
                    ]
                    and live_result[
                        "supervised_projection_matches_flat_collector"
                    ]
                )
            )
        ),
    }
    _write_json(output, report)
    return report


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=root
        / "runs/m9-candidate-sequence-relabel-preflight.json",
    )
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-live", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build_report(
            root,
            args.output.resolve(),
            java=args.java,
            port=args.port,
            live=not args.no_live,
        )
    except Exception as error:
        print(f"M9 SEQUENCE PREFLIGHT FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "M9 SEQUENCE PREFLIGHT "
        f"{'PASS' if report['passed'] else 'FAIL'}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
