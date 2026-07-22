"""Reproducible V42 train-only teacher-conflict relabel evidence."""

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
    DEFAULT_JVM_ARGS,
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    jar_path,
    repo_root,
)
from mindustry_agents.training.model import SelectorActorCritic
from mindustry_agents.training.ppo_selector import (
    EpisodeRollout,
    _configure_torch,
    _partner_intent_duplication_risk,
    _partner_intent_teacher_conflict_filter,
    _partner_intent_teacher_conflict_relabel,
    _policy_logit_adjustment,
    _scripted_partner_opening,
    _teacher_rehearsal_policy,
    _teacher_warmup_policy,
    _teacher_warmup_seed_schedule,
    rollout_episode,
)
from mindustry_agents.training.reward import REWARD_SCHEMA

REPORT_SCHEMA = "m8_v42_teacher_conflict_relabel_diagnostic_v1"
V42_CONFIG_RELATIVE = (
    "configs/training/m8-selector-v42-partner-intent-teacher-conflict-relabel.json"
)
TEACHER_SET_RELATIVE = (
    "configs/evaluation/bootstrap-defense-v1-teacher-train-v1.json"
)
EXPECTED_SOURCE_SHA256 = {
    "v42_config": "3fcb0c8800c638a333068ab116f8270be076c1cbae2438b55cc6f193c0583d0d",
    "teacher_train_set": (
        "a1552f7937edea413f92542d41477a0c367c316eaced90b4da2a7601007a46de"
    ),
}
EXPECTED_COUNTS = {
    "episodes": 256,
    "wins": 94,
    "policy_eligible_transitions": 3956,
    "original_conflicts": 752,
    "relabeled": 682,
    "fallback": 70,
    "successful_policy_eligible_transitions": 1079,
    "successful_original_conflicts": 189,
    "successful_relabeled": 174,
    "successful_fallback": 15,
    "tick_0_relabeled": 256,
    "tick_0_fallback": 0,
    "later_relabeled": 426,
    "later_fallback": 70,
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
    config: dict[str, Any],
    teacher_set: dict[str, Any],
    *,
    source_sha256: dict[str, str],
) -> list[int]:
    """Fail closed unless inputs are the exact precommitted V42 train coordinate."""

    if source_sha256 != EXPECTED_SOURCE_SHA256:
        raise ValueError("immutable V42 diagnostic source digest drift")
    if config.get("schema") != "selector_training_config_v1":
        raise ValueError("unexpected V42 config schema")
    if config.get("candidate_version") != "v42":
        raise ValueError("diagnostic target is not candidate V42")
    if config.get("teacher_warmup_seed_set") != TEACHER_SET_RELATIVE:
        raise ValueError("V42 does not name the bound teacher train set")
    if _partner_intent_duplication_risk(config) is None:
        raise ValueError("V42 does not enable partner-intent risk")
    if _partner_intent_teacher_conflict_filter(config) is not None:
        raise ValueError("V42 unexpectedly enables the conflict filter")
    if _partner_intent_teacher_conflict_relabel(config) is None:
        raise ValueError("V42 does not enable conflict relabeling")
    if _teacher_warmup_policy(config) is None:
        raise ValueError("V42 teacher warmup schedule is disabled")
    if _teacher_rehearsal_policy(config) is None:
        raise ValueError("V42 teacher rehearsal schedule is disabled")

    if teacher_set.get("split") != "train":
        raise ValueError("teacher corpus is not a train split")
    if teacher_set.get("seed_set_id") != "bootstrap-defense-v1-teacher-train-v1":
        raise ValueError("unexpected teacher train seed-set identity")
    if teacher_set.get("seed_set_version") != 1:
        raise ValueError("unexpected teacher train seed-set version")
    if teacher_set.get("scenario_id") != config.get("scenario_id"):
        raise ValueError("teacher train scenario identity differs from config")
    if teacher_set.get("scenario_version") != config.get("scenario_version"):
        raise ValueError("teacher train scenario version differs from config")
    expected_seeds = list(range(291001, 291257))
    seeds = teacher_set.get("seeds")
    if seeds != expected_seeds or any(type(seed) is not int for seed in seeds):
        raise ValueError("unexpected teacher train seed membership")
    schedule = _teacher_warmup_seed_schedule(teacher_set, config)
    if len(schedule) != 256 or sorted(schedule) != expected_seeds:
        raise ValueError("unexpected V42 teacher episode schedule")
    return schedule


def _mask_values(value: Any) -> list[bool]:
    raw = value.tolist() if hasattr(value, "tolist") else list(value)
    return [bool(item) for item in raw]


def _validate_behavior_trace(episode: EpisodeRollout, trace: dict[str, Any]) -> None:
    action_index = trace.get("action_index")
    teacher_index = trace.get("teacher_action_index")
    if action_index != teacher_index:
        raise ValueError(f"teacher-controlled action drift for seed {episode.seed}")
    if trace.get("action") != trace.get("teacher_action"):
        raise ValueError(
            f"teacher-controlled task action drift for seed {episode.seed}"
        )
    actions = trace.get("agent_actions")
    if not isinstance(actions, list) or not actions:
        raise ValueError(f"missing submitted action bundle for seed {episode.seed}")
    learned = actions[0]
    if not isinstance(learned, dict) or learned.get("task_action") != trace.get(
        "action"
    ):
        raise ValueError(f"submitted learned action drift for seed {episode.seed}")
    if not isinstance(trace.get("state_hash"), str) or not trace["state_hash"]:
        raise ValueError(f"missing state hash for seed {episode.seed}")


def build_report(
    episodes: Sequence[EpisodeRollout],
    *,
    source_bindings: dict[str, dict[str, str]],
    config: dict[str, Any],
    tool_inputs: dict[str, Any],
) -> dict[str, Any]:
    """Validate production relabel fields and summarize without full traces."""

    if not episodes:
        raise ValueError("diagnostic produced no episodes")
    eligible_count = 0
    conflicts = 0
    relabeled = 0
    fallback = 0
    successful = {
        "policy_eligible": 0,
        "original_conflicts": 0,
        "relabeled": 0,
        "fallback": 0,
    }
    boundary = {
        "tick_0": {"relabeled": 0, "fallback": 0},
        "later": {"relabeled": 0, "fallback": 0},
    }
    task_status: dict[str, dict[str, int]] = {}
    behavior_rows: list[dict[str, Any]] = []
    total_transitions = 0

    for episode in episodes:
        if len(episode.transitions) != len(episode.trace):
            raise ValueError(f"transition/trace length drift for seed {episode.seed}")
        total_transitions += len(episode.transitions)
        for transition, trace in zip(episode.transitions, episode.trace):
            _validate_behavior_trace(episode, trace)
            tick = trace.get("tick")
            if type(tick) is not int or tick < 0:
                raise ValueError("transition has invalid tick")
            behavior_rows.append({
                "seed": int(episode.seed),
                "tick": tick,
                "agent_actions": trace["agent_actions"],
                "state_hash": trace["state_hash"],
            })
            original = transition.teacher_action
            effective = transition.teacher_effective_action
            conflict = bool(transition.teacher_partner_intent_risk_conflict)
            status = transition.teacher_partner_intent_relabel_status
            mask = _mask_values(transition.action_mask)
            if type(original) is not int or original < 0 or original >= len(mask):
                raise ValueError("invalid original teacher index")
            if trace.get("teacher_action_index") != original:
                raise ValueError("transition/trace original teacher index drift")
            if trace.get("teacher_effective_action_index") != effective:
                raise ValueError("transition/trace effective teacher index drift")
            if (
                trace.get("teacher_original_partner_intent_risk_conflict")
                is not conflict
            ):
                raise ValueError("transition/trace conflict flag drift")
            if trace.get("teacher_conflict_relabel_status") != status:
                raise ValueError("transition/trace relabel status drift")
            risk = trace.get("partner_intent_duplication_risk_candidate_indices")
            if not isinstance(risk, list) or any(
                type(index) is not int or index < 0 or index >= 8 for index in risk
            ):
                raise ValueError("invalid production risk candidate indices")

            if conflict:
                if original not in risk:
                    raise ValueError("conflict flag is inconsistent with risk indices")
                if status == "relabeled_nonconflict":
                    if (
                        type(effective) is not int
                        or effective == original
                        or effective < 0
                        or effective >= 8
                        or effective >= len(mask)
                        or not mask[effective]
                        or effective in risk
                        or trace.get("teacher_alternate_action_index") != effective
                    ):
                        raise ValueError("invalid relabeled effective teacher index")
                elif status == "fallback_excluded":
                    if (
                        effective is not None
                        or trace.get("teacher_alternate_action_index") is not None
                    ):
                        raise ValueError(
                            "fallback must have no effective teacher index"
                        )
                else:
                    raise ValueError("conflict has inconsistent relabel status")
            else:
                if original in risk:
                    raise ValueError("nonconflict original teacher index is risky")
                if (
                    status != "original_nonconflict"
                    or effective != original
                    or trace.get("teacher_alternate_action_index") is not None
                ):
                    raise ValueError("nonconflict must preserve original teacher index")

            eligible = bool(transition.policy_loss_mask) and original is not None
            if not eligible:
                continue
            eligible_count += 1
            if episode.outcome == "win":
                successful["policy_eligible"] += 1
            if not conflict:
                continue
            conflicts += 1
            bucket = "tick_0" if tick == 0 else "later"
            key = "relabeled" if status == "relabeled_nonconflict" else "fallback"
            if key == "relabeled":
                relabeled += 1
            else:
                fallback += 1
            boundary[bucket][key] += 1
            diagnostics = trace.get("teacher_candidate_diagnostics")
            if not isinstance(diagnostics, dict):
                raise ValueError("conflicting transition lacks teacher diagnostics")
            task_type = diagnostics.get("task_type")
            if not isinstance(task_type, str) or not task_type:
                raise ValueError("conflicting transition lacks teacher task type")
            counts = task_status.setdefault(task_type, {"relabeled": 0, "fallback": 0})
            counts[key] += 1
            if episode.outcome == "win":
                successful["original_conflicts"] += 1
                successful[key] += 1

    payload = {
        "schema": REPORT_SCHEMA,
        "sources": source_bindings,
        "tool_inputs": tool_inputs,
        "coordinate": {
            "candidate_version": config["candidate_version"],
            "scenario_id": config["scenario_id"],
            "scenario_version": config["scenario_version"],
            "teacher_controlled": True,
            "jvm_processes": 1,
            "jvm_execution": "sequential",
            "optimizer_constructed": False,
            "optimizer_updates": 0,
            "episode_seed_schedule_sha256": _json_digest(
                [int(item.seed) for item in episodes]
            ),
            "behavior_neutral_evidence": (
                "submitted original teacher actions and resulting state hashes"
            ),
            "action_state_sha256": _json_digest(behavior_rows),
        },
        "episodes": {
            "total": len(episodes),
            "wins": sum(item.outcome == "win" for item in episodes),
            "losses": sum(item.outcome != "win" for item in episodes),
        },
        "transitions": {
            "total": total_transitions,
            "policy_eligible": eligible_count,
            "original_conflicts": conflicts,
            "relabeled": relabeled,
            "fallback": fallback,
            "conflict_status_by_boundary": boundary,
            "conflict_status_by_original_teacher_task_type": dict(
                sorted(task_status.items())
            ),
        },
        "successful_corpus": successful,
    }
    return {**payload, "report_payload_sha256": _json_digest(payload)}


def validate_acceptance_counts(report: dict[str, Any]) -> None:
    """Require every precommitted production-path count before writing evidence."""

    episodes = report.get("episodes", {})
    transitions = report.get("transitions", {})
    successful = report.get("successful_corpus", {})
    boundary = transitions.get("conflict_status_by_boundary", {})
    actual = {
        "episodes": episodes.get("total"),
        "wins": episodes.get("wins"),
        "policy_eligible_transitions": transitions.get("policy_eligible"),
        "original_conflicts": transitions.get("original_conflicts"),
        "relabeled": transitions.get("relabeled"),
        "fallback": transitions.get("fallback"),
        "successful_policy_eligible_transitions": successful.get("policy_eligible"),
        "successful_original_conflicts": successful.get("original_conflicts"),
        "successful_relabeled": successful.get("relabeled"),
        "successful_fallback": successful.get("fallback"),
        "tick_0_relabeled": boundary.get("tick_0", {}).get("relabeled"),
        "tick_0_fallback": boundary.get("tick_0", {}).get("fallback"),
        "later_relabeled": boundary.get("later", {}).get("relabeled"),
        "later_fallback": boundary.get("later", {}).get("fallback"),
    }
    if actual != EXPECTED_COUNTS:
        raise RuntimeError(
            "V42 teacher-conflict relabel acceptance counts differ: "
            f"expected={EXPECTED_COUNTS} actual={actual}"
        )


def atomic_write_json(path: Path, value: dict[str, Any]) -> str:
    """Atomically write deterministic JSON and return the output-file SHA-256."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
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
    return _sha256(path)


def run_diagnostic(
    *, output_path: Path, java: str, port: int
) -> tuple[dict[str, Any], str]:
    """Collect V42 teacher episodes through one JVM and perform no optimization."""

    root = repo_root().resolve()
    paths = {
        "v42_config": root / V42_CONFIG_RELATIVE,
        "teacher_train_set": root / TEACHER_SET_RELATIVE,
    }
    config = _load_json(paths["v42_config"])
    teacher_set = _load_json(paths["teacher_train_set"])
    seeds = validate_bound_inputs(
        config,
        teacher_set,
        source_sha256={name: _sha256(path) for name, path in paths.items()},
    )
    server_jar = jar_path(root)
    if not server_jar.is_file():
        raise FileNotFoundError(f"jar not found: {server_jar} (build it first)")
    _configure_torch(config)
    model = SelectorActorCritic(int(config["model_init_seed"]))
    model.eval()
    action_generator = torch.Generator().manual_seed(
        int(config["action_sampling_seed"])
    )
    episodes: list[EpisodeRollout] = []
    launch = LaunchConfig(port=port, java=java, build_if_missing=False)
    with RlServerProcess(launch) as env:
        env.handshake("m8-v42-teacher-conflict-relabel-diagnostic")
        for seed in seeds:
            episodes.append(rollout_episode(
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
                policy_logit_adjustment=_policy_logit_adjustment(config),
                scripted_partner_opening=_scripted_partner_opening(config),
                partner_intent_duplication_risk=(
                    _partner_intent_duplication_risk(config)
                ),
                partner_intent_teacher_conflict_relabel=(
                    _partner_intent_teacher_conflict_relabel(config)
                ),
            ))
    report = build_report(
        episodes,
        source_bindings={
            name: _source_binding(path, root) for name, path in paths.items()
        }
        | {"rl_server_jar": _source_binding(server_jar, root)},
        config=config,
        tool_inputs={"java": java, "jvm_args": list(DEFAULT_JVM_ARGS), "port": port},
    )
    validate_acceptance_counts(report)
    return report, atomic_write_json(output_path, report)


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="V42 train-only production teacher-conflict relabel diagnostic"
    )
    parser.add_argument(
        "--output", type=Path,
        default=root / "runs/m8-selector-v42-teacher-conflict-relabel-diagnostic.json",
    )
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    try:
        report, output_sha256 = run_diagnostic(
            output_path=args.output.resolve(), java=args.java, port=args.port
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(
            f"V42-TEACHER-CONFLICT-RELABEL-DIAGNOSTIC ERROR: {error}",
            file=sys.stderr,
        )
        return 1
    print(
        "V42-TEACHER-CONFLICT-RELABEL-DIAGNOSTIC PASS "
        f"episodes={report['episodes']['total']} "
        f"conflicts={report['transitions']['original_conflicts']} "
        f"relabeled={report['transitions']['relabeled']} "
        f"fallback={report['transitions']['fallback']}"
    )
    print(f"report={args.output.resolve()}")
    print(f"report_payload_sha256={report['report_payload_sha256']}")
    print(f"output_file_sha256={output_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
