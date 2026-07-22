"""Reproducible V40 teacher-conflict evidence on the ordinary train corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

import torch

from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.training.model import SelectorActorCritic
from mindustry_agents.training.ppo_selector import (
    EpisodeRollout,
    _configure_torch,
    _partner_intent_duplication_risk,
    _partner_intent_teacher_conflict_filter,
    _policy_logit_adjustment,
    _scripted_partner_opening,
    _teacher_rehearsal_policy,
    _teacher_warmup_policy,
    _teacher_warmup_seed_schedule,
    rollout_episode,
)
from mindustry_agents.training.reward import REWARD_SCHEMA

REPORT_SCHEMA = "m8_v40_teacher_conflict_diagnostic_v1"
V39_CONFIG_RELATIVE = (
    "configs/training/m8-selector-v39-partner-intent-duplication-risk.json"
)
V40_CONFIG_RELATIVE = (
    "configs/training/m8-selector-v40-partner-intent-teacher-conflict-filter.json"
)
TEACHER_SET_RELATIVE = (
    "configs/evaluation/bootstrap-defense-v1-teacher-train-v1.json"
)
EXPECTED_SOURCE_SHA256 = {
    "v39_config": "54d76bb209ec31f24bc2711b208cb2995e6d538534ba0b99a150091596ccf924",
    "v40_config": (
        "230759e7e02dcca9a6b7608f7784b20f85845c40da0f7a28dd1ec13641d0013a"
    ),
    "teacher_train_set": (
        "a1552f7937edea413f92542d41477a0c367c316eaced90b4da2a7601007a46de"
    ),
}
EXPECTED_COUNTS = {
    "episodes": 256,
    "wins": 94,
    "policy_eligible_transitions": 3956,
    "conflicting_transitions": 752,
    "successful_policy_eligible_transitions": 1079,
    "successful_conflicting_transitions": 189,
    "warmup_presentations": 968,
    "warmup_conflict_presentations": 177,
    "rehearsal_presentations": 3872,
    "rehearsal_conflict_presentations": 734,
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_digest(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _source_binding(path: Path, root: Path) -> dict[str, str]:
    return {
        "path": path.resolve().relative_to(root.resolve()).as_posix(),
        "sha256": _sha256(path),
    }


def validate_bound_inputs(
    v39_config: dict[str, Any],
    v40_config: dict[str, Any],
    teacher_set: dict[str, Any],
    *,
    source_sha256: dict[str, str],
) -> list[int]:
    """Fail closed unless this is exactly the precommitted train-only coordinate."""

    if source_sha256 != EXPECTED_SOURCE_SHA256:
        raise ValueError("immutable V39/V40 diagnostic source digest drift")
    if v39_config.get("schema") != "selector_training_config_v1":
        raise ValueError("unexpected V39 config schema")
    if v40_config.get("schema") != "selector_training_config_v1":
        raise ValueError("unexpected V40 config schema")
    if v39_config.get("candidate_version") != "v39":
        raise ValueError("diagnostic source is not candidate V39")
    if v40_config.get("candidate_version") != "v40":
        raise ValueError("diagnostic target is not candidate V40")
    if _partner_intent_duplication_risk(v39_config) is None:
        raise ValueError("V39 does not enable partner-intent risk")
    if _partner_intent_duplication_risk(v40_config) is None:
        raise ValueError("V40 does not enable partner-intent risk")
    if _partner_intent_teacher_conflict_filter(v39_config) is not None:
        raise ValueError("V39 unexpectedly enables the teacher-conflict filter")
    if _partner_intent_teacher_conflict_filter(v40_config) is None:
        raise ValueError("V40 does not enable the teacher-conflict filter")

    allowed_differences = {
        "candidate_version",
        "quality_intervention",
        "confirmation_seed_set",
        "partner_intent_teacher_conflict_filter",
    }
    shared_keys = set(v39_config) | set(v40_config)
    for key in sorted(shared_keys - allowed_differences):
        if v39_config.get(key) != v40_config.get(key):
            raise ValueError(f"unexpected V39/V40 config drift: {key}")

    if v39_config.get("teacher_warmup_seed_set") != TEACHER_SET_RELATIVE:
        raise ValueError("V39 does not name the bound teacher train set")
    if v40_config.get("teacher_warmup_seed_set") != TEACHER_SET_RELATIVE:
        raise ValueError("V40 does not name the bound teacher train set")
    if teacher_set.get("split") != "train":
        raise ValueError("teacher corpus is not a train split")
    if teacher_set.get("seed_set_id") != "bootstrap-defense-v1-teacher-train-v1":
        raise ValueError("unexpected teacher train seed-set identity")
    if teacher_set.get("seed_set_version") != 1:
        raise ValueError("unexpected teacher train seed-set version")
    if teacher_set.get("scenario_id") != v39_config.get("scenario_id"):
        raise ValueError("teacher train scenario identity differs from config")
    if teacher_set.get("scenario_version") != v39_config.get("scenario_version"):
        raise ValueError("teacher train scenario version differs from config")
    seeds = teacher_set.get("seeds")
    expected_seeds = list(range(291001, 291257))
    if seeds != expected_seeds or any(type(seed) is not int for seed in seeds):
        raise ValueError("unexpected teacher train seed membership")

    warmup = _teacher_warmup_policy(v39_config)
    rehearsal = _teacher_rehearsal_policy(v39_config)
    if warmup is None or rehearsal is None:
        raise ValueError("V39 teacher warmup/rehearsal schedule is disabled")
    episode_schedule = _teacher_warmup_seed_schedule(teacher_set, v39_config)
    if len(episode_schedule) != len(expected_seeds) or sorted(
        episode_schedule
    ) != expected_seeds:
        raise ValueError("unexpected V39 teacher episode schedule")
    return episode_schedule


def sampling_conflict_mapping(
    conflict_flags: Sequence[bool],
    *,
    epochs: int,
    samples_per_epoch: int,
    generator_seed: int,
    calls: int = 1,
) -> dict[str, Any]:
    """Map the exact V39 randperm schedule onto corpus conflict labels."""

    if not conflict_flags:
        raise ValueError("sampling corpus cannot be empty")
    if epochs < 1 or samples_per_epoch < 1 or calls < 1:
        raise ValueError("sampling schedule dimensions must be positive")
    if any(type(flag) is not bool for flag in conflict_flags):
        raise ValueError("conflict flags must be boolean")
    generator = torch.Generator().manual_seed(generator_seed)
    schedules: list[list[int]] = []
    for _ in range(calls):
        for _ in range(epochs):
            order = torch.randperm(len(conflict_flags), generator=generator)
            order = order[: min(samples_per_epoch, len(conflict_flags))]
            schedules.append([int(index) for index in order.tolist()])
    sampled = [index for schedule in schedules for index in schedule]
    conflict_sampled = [index for index in sampled if conflict_flags[index]]
    return {
        "epochs": epochs,
        "calls": calls,
        "samples_per_epoch_cap": samples_per_epoch,
        "sampled_presentations": len(sampled),
        "sampled_conflict_presentations": len(conflict_sampled),
        "sampled_unique_transitions": len(set(sampled)),
        "sampled_unique_conflict_transitions": len(set(conflict_sampled)),
        "sampled_transition_indices_by_epoch": schedules,
        "sample_schedule_sha256": _json_digest(schedules),
    }


def build_report(
    episodes: Sequence[EpisodeRollout],
    *,
    source_bindings: dict[str, dict[str, str]],
    v39_config: dict[str, Any],
) -> dict[str, Any]:
    """Summarize conflict incidence and the pre-filter V39 sample schedules."""

    if not episodes:
        raise ValueError("diagnostic produced no episodes")
    total_transitions = 0
    eligible: list[Any] = []
    successful_eligible: list[Any] = []
    conflicts_by_task_type: dict[str, int] = {}
    conflicts_by_boundary = {"tick_0": 0, "later": 0}
    affected = {"winning": 0, "losing": 0}

    for episode in episodes:
        if len(episode.transitions) != len(episode.trace):
            raise ValueError(f"transition/trace length drift for seed {episode.seed}")
        episode_conflict = False
        total_transitions += len(episode.transitions)
        for transition, trace in zip(episode.transitions, episode.trace):
            is_eligible = bool(transition.policy_loss_mask) and (
                transition.teacher_action is not None
            )
            if not is_eligible:
                continue
            eligible.append(transition)
            if episode.outcome == "win":
                successful_eligible.append(transition)
            if not bool(transition.teacher_partner_intent_risk_conflict):
                continue
            episode_conflict = True
            diagnostics = trace.get("teacher_candidate_diagnostics")
            if not isinstance(diagnostics, dict):
                raise ValueError("conflicting transition lacks teacher diagnostics")
            task_type = diagnostics.get("task_type")
            tick = trace.get("tick")
            if not isinstance(task_type, str) or not task_type:
                raise ValueError("conflicting transition lacks teacher task type")
            if type(tick) is not int or tick < 0:
                raise ValueError("conflicting transition has invalid tick")
            conflicts_by_task_type[task_type] = (
                conflicts_by_task_type.get(task_type, 0) + 1
            )
            conflicts_by_boundary["tick_0" if tick == 0 else "later"] += 1
        if episode_conflict:
            affected["winning" if episode.outcome == "win" else "losing"] += 1

    successful_flags = [
        bool(item.teacher_partner_intent_risk_conflict)
        for item in successful_eligible
    ]
    warmup = sampling_conflict_mapping(
        successful_flags,
        epochs=int(v39_config["teacher_warmup_epochs"]),
        samples_per_epoch=int(v39_config["teacher_warmup_samples_per_epoch"]),
        generator_seed=int(v39_config["teacher_warmup_minibatch_seed"]),
    )
    rehearsal = sampling_conflict_mapping(
        successful_flags,
        epochs=int(v39_config["teacher_rehearsal_epochs_per_update"]),
        samples_per_epoch=int(v39_config["teacher_rehearsal_samples_per_epoch"]),
        generator_seed=int(v39_config["teacher_rehearsal_minibatch_seed"]),
        calls=int(v39_config["training_cycles"]),
    )
    payload = {
        "schema": REPORT_SCHEMA,
        "sources": source_bindings,
        "coordinate": {
            "scenario_id": v39_config["scenario_id"],
            "scenario_version": v39_config["scenario_version"],
            "teacher_controlled": True,
            "optimizer_updates": 0,
            "episode_seed_schedule_sha256": _json_digest(
                [int(episode.seed) for episode in episodes]
            ),
            "historical_action_state_behavior": "diagnostic_only",
        },
        "episodes": {
            "total": len(episodes),
            "wins": sum(episode.outcome == "win" for episode in episodes),
            "losses": sum(episode.outcome != "win" for episode in episodes),
            "affected_by_conflict": affected,
        },
        "transitions": {
            "total": total_transitions,
            "policy_eligible": len(eligible),
            "conflicting": sum(
                bool(item.teacher_partner_intent_risk_conflict) for item in eligible
            ),
            "conflicts_by_teacher_task_type": dict(
                sorted(conflicts_by_task_type.items())
            ),
            "conflicts_by_boundary": conflicts_by_boundary,
        },
        "successful_corpus": {
            "policy_eligible": len(successful_eligible),
            "conflicting": sum(successful_flags),
        },
        "v39_sample_schedule_mapping": {
            "warmup": warmup,
            "rehearsal": rehearsal,
        },
    }
    return {**payload, "report_payload_sha256": _json_digest(payload)}


def validate_acceptance_counts(report: dict[str, Any]) -> None:
    """Require the exact reusable precommit counts before writing evidence."""

    actual = {
        "episodes": report.get("episodes", {}).get("total"),
        "wins": report.get("episodes", {}).get("wins"),
        "policy_eligible_transitions": report.get("transitions", {}).get(
            "policy_eligible"
        ),
        "conflicting_transitions": report.get("transitions", {}).get("conflicting"),
        "successful_policy_eligible_transitions": report.get(
            "successful_corpus", {}
        ).get("policy_eligible"),
        "successful_conflicting_transitions": report.get(
            "successful_corpus", {}
        ).get("conflicting"),
        "warmup_presentations": report.get("v39_sample_schedule_mapping", {})
        .get("warmup", {})
        .get("sampled_presentations"),
        "warmup_conflict_presentations": report.get(
            "v39_sample_schedule_mapping", {}
        )
        .get("warmup", {})
        .get("sampled_conflict_presentations"),
        "rehearsal_presentations": report.get("v39_sample_schedule_mapping", {})
        .get("rehearsal", {})
        .get("sampled_presentations"),
        "rehearsal_conflict_presentations": report.get(
            "v39_sample_schedule_mapping", {}
        )
        .get("rehearsal", {})
        .get("sampled_conflict_presentations"),
    }
    if actual != EXPECTED_COUNTS:
        raise RuntimeError(
            "V40 teacher-conflict acceptance counts differ: "
            f"expected={EXPECTED_COUNTS} actual={actual}"
        )


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    """Atomically replace a deterministic JSON report."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception as error:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise RuntimeError(f"could not atomically write report: {path}") from error


def run_diagnostic(*, output_path: Path, java: str, port: int) -> dict[str, Any]:
    """Collect teacher-controlled V39 episodes without optimizer construction."""

    root = repo_root().resolve()
    paths = {
        "v39_config": root / V39_CONFIG_RELATIVE,
        "v40_config": root / V40_CONFIG_RELATIVE,
        "teacher_train_set": root / TEACHER_SET_RELATIVE,
    }
    v39_config = _load_json(paths["v39_config"])
    v40_config = _load_json(paths["v40_config"])
    teacher_set = _load_json(paths["teacher_train_set"])
    source_sha256 = {name: _sha256(path) for name, path in paths.items()}
    seeds = validate_bound_inputs(
        v39_config, v40_config, teacher_set, source_sha256=source_sha256
    )
    _configure_torch(v39_config)
    model = SelectorActorCritic(int(v39_config["model_init_seed"]))
    model.eval()
    action_generator = torch.Generator().manual_seed(
        int(v39_config["action_sampling_seed"])
    )
    episodes: list[EpisodeRollout] = []
    with RlServerProcess(
        LaunchConfig(port=port, java=java, build_if_missing=False)
    ) as env:
        env.handshake("m8-v40-teacher-conflict-diagnostic")
        for seed in seeds:
            episodes.append(
                rollout_episode(
                    env,
                    model,
                    seed=seed,
                    scenario_id=str(v39_config["scenario_id"]),
                    scenario_version=int(v39_config["scenario_version"]),
                    evaluation=True,
                    action_generator=action_generator,
                    reward_schema=str(v39_config.get("reward_schema", REWARD_SCHEMA)),
                    quality_reward=v39_config.get("quality_reward"),
                    teacher_controlled=True,
                    policy_logit_adjustment=_policy_logit_adjustment(v39_config),
                    scripted_partner_opening=_scripted_partner_opening(v39_config),
                    partner_intent_duplication_risk=(
                        _partner_intent_duplication_risk(v39_config)
                    ),
                )
            )
    report = build_report(
        episodes,
        source_bindings={
            name: _source_binding(path, root) for name, path in paths.items()
        },
        v39_config=v39_config,
    )
    validate_acceptance_counts(report)
    atomic_write_json(output_path, report)
    return report


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="V40 train-only teacher/partner-intent conflict diagnostic"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "runs/m8-selector-v40-teacher-conflict-diagnostic.json",
    )
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    try:
        report = run_diagnostic(
            output_path=args.output.resolve(), java=args.java, port=args.port
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"V40-TEACHER-CONFLICT-DIAGNOSTIC ERROR: {error}", file=sys.stderr)
        return 1
    print(
        "V40-TEACHER-CONFLICT-DIAGNOSTIC PASS "
        f"episodes={report['episodes']['total']} "
        f"eligible={report['transitions']['policy_eligible']} "
        f"conflicts={report['transitions']['conflicting']}"
    )
    print(f"report={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
