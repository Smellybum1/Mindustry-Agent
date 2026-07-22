"""Reproducible V39 partner-intent evidence over the reusable dev-v1 set."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from mindustry_agents.process.launcher import DEFAULT_PORT, repo_root
from mindustry_agents.training.model import SelectorActorCritic
from mindustry_agents.training.ppo_selector import (
    EpisodeRollout,
    _configure_torch,
    _episode_summary,
    _evaluate,
    _partner_intent_duplication_risk,
    load_checkpoint,
)

REPORT_SCHEMA = "m8_v39_partner_intent_replay_diagnostic_v1"
EXPECTED_DEV_SET_ID = "bootstrap-defense-v1-dev-v1"
EXPECTED_DEV_SET_VERSION = 1
EXPECTED_DEV_SEEDS = list(range(2001, 2011))
ACTION_STATE_KEYS = (
    "tick",
    "advanced_ticks",
    "action",
    "agent_actions",
    "action_index",
    "state_hash",
    "outcome",
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        rows.append(value)
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_digest(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _display_path(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _source_binding(path: Path, root: Path) -> dict[str, str]:
    return {"path": _display_path(path, root), "sha256": _sha256(path)}


def validate_reusable_inputs(
    legacy_config: dict[str, Any],
    enabled_config: dict[str, Any],
    seed_set: dict[str, Any],
) -> tuple[list[int], dict[str, Any]]:
    """Validate that only the precommitted V38/V39 reusable coordinate is run."""

    if legacy_config.get("schema") != "selector_training_config_v1":
        raise ValueError("legacy config schema is not selector_training_config_v1")
    if enabled_config.get("schema") != "selector_training_config_v1":
        raise ValueError("enabled config schema is not selector_training_config_v1")
    if legacy_config.get("candidate_version") != "v38":
        raise ValueError("legacy config is not candidate v38")
    if enabled_config.get("candidate_version") != "v39":
        raise ValueError("enabled config is not candidate v39")
    if _partner_intent_duplication_risk(legacy_config) is not None:
        raise ValueError("legacy V38 config unexpectedly enables partner intent")
    intervention = _partner_intent_duplication_risk(enabled_config)
    if intervention is None:
        raise ValueError("V39 config does not enable partner intent")

    shared_keys = (
        "scenario_id",
        "scenario_version",
        "model_architecture",
        "reward_schema",
        "quality_reward",
        "model_init_seed",
        "action_sampling_seed",
        "dev_seed_set",
    )
    for key in shared_keys:
        if legacy_config.get(key) != enabled_config.get(key):
            raise ValueError(f"V38/V39 shared field differs: {key}")

    if seed_set.get("split") != "dev":
        raise ValueError("reusable seed set is not a dev split")
    if seed_set.get("seed_set_id") != EXPECTED_DEV_SET_ID:
        raise ValueError("unexpected reusable dev seed-set ID")
    if seed_set.get("seed_set_version") != EXPECTED_DEV_SET_VERSION:
        raise ValueError("unexpected reusable dev seed-set version")
    if seed_set.get("scenario_id") != legacy_config.get("scenario_id"):
        raise ValueError("reusable seed-set scenario ID differs from config")
    if seed_set.get("scenario_version") != legacy_config.get("scenario_version"):
        raise ValueError("reusable seed-set scenario version differs from config")
    seeds = seed_set.get("seeds")
    if seeds != EXPECTED_DEV_SEEDS or any(type(seed) is not int for seed in seeds):
        raise ValueError("unexpected reusable dev seed membership")
    expected_seed_path = "configs/evaluation/bootstrap-defense-v1-dev-v1.json"
    if legacy_config.get("dev_seed_set") != expected_seed_path:
        raise ValueError("config does not name the reusable dev-v1 set")
    return list(seeds), intervention


def exact_legacy_trace_parity(
    actual: list[dict[str, Any]], expected: list[dict[str, Any]], *, seed: int
) -> dict[str, Any]:
    """Return full-object equality evidence for the checked-in legacy replay."""

    return {
        "seed": seed,
        "bit_exact": actual == expected,
        "actual_rows": len(actual),
        "expected_rows": len(expected),
        "actual_trace_digest": _json_digest(actual),
        "expected_trace_digest": _json_digest(expected),
    }


def _action_state_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in ACTION_STATE_KEYS}


def common_action_state_prefix(
    disabled: list[dict[str, Any]], enabled: list[dict[str, Any]]
) -> int:
    """Count exact action/state rows shared from the episode boundary."""

    count = 0
    for disabled_row, enabled_row in zip(disabled, enabled):
        if _action_state_row(disabled_row) != _action_state_row(enabled_row):
            break
        count += 1
    return count


def first_causally_comparable_action_difference(
    disabled: list[dict[str, Any]], enabled: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Describe an action flip only at the first previously identical boundary."""

    ordinal = common_action_state_prefix(disabled, enabled)
    if ordinal >= len(disabled) or ordinal >= len(enabled):
        return None
    disabled_row = disabled[ordinal]
    enabled_row = enabled[ordinal]
    if disabled_row.get("tick") != enabled_row.get("tick"):
        return None
    disabled_action = disabled_row.get("action")
    enabled_action = enabled_row.get("action")
    disabled_index = disabled_row.get("action_index")
    enabled_index = enabled_row.get("action_index")
    if disabled_action == enabled_action and disabled_index == enabled_index:
        return None
    return {
        "decision_ordinal": ordinal,
        "tick": enabled_row.get("tick"),
        "disabled_action": disabled_action,
        "disabled_action_index": disabled_index,
        "enabled_action": enabled_action,
        "enabled_action_index": enabled_index,
        "enabled_intended_task_ids": list(
            enabled_row.get("fixed_partner_intended_task_ids", [])
        ),
        "enabled_risk_candidate_indices": list(
            enabled_row.get(
                "partner_intent_duplication_risk_candidate_indices", []
            )
        ),
    }


def diagnostic_exposure(trace: list[dict[str, Any]]) -> dict[str, Any]:
    """Count intent/risk evidence and require diagnostics on every enabled row."""

    required = (
        "fixed_partner_intended_task_ids",
        "partner_intent_duplication_risk_candidate_indices",
    )
    diagnostics_complete = True
    intent_decisions = 0
    risk_exposures = 0
    for row in trace:
        intents = row.get(required[0], [])
        risks = row.get(required[1], [])
        diagnostics_complete = diagnostics_complete and (
            all(key in row for key in required)
            and isinstance(intents, list)
            and all(isinstance(task_id, str) and task_id for task_id in intents)
            and isinstance(risks, list)
            and all(
                type(candidate_index) is int and candidate_index >= 0
                for candidate_index in risks
            )
        )
        if isinstance(intents, list) and intents:
            intent_decisions += 1
        if isinstance(risks, list):
            risk_exposures += len(risks)
    return {
        "diagnostics_complete": diagnostics_complete,
        "intent_exposed_decisions": intent_decisions,
        "exact_risk_candidate_exposures": risk_exposures,
    }


def _compact_summary(episode: EpisodeRollout) -> dict[str, Any]:
    summary = _episode_summary(episode)
    return {
        key: summary[key]
        for key in (
            "seed",
            "outcome",
            "tick",
            "core_health",
            "decisions",
            "trace_digest",
        )
    }


def _action_sequence(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "action": row.get("action"),
            "action_index": row.get("action_index"),
        }
        for row in trace
    ]


def build_report(
    *,
    source_bindings: dict[str, dict[str, str]],
    seeds: list[int],
    disabled_episodes: list[EpisodeRollout],
    enabled_episodes: list[EpisodeRollout],
    legacy_parity: dict[str, Any],
) -> dict[str, Any]:
    """Build compact deterministic evidence without claiming beyond divergence."""

    disabled_by_seed = {episode.seed: episode for episode in disabled_episodes}
    enabled_by_seed = {episode.seed: episode for episode in enabled_episodes}
    if set(disabled_by_seed) != set(seeds) or set(enabled_by_seed) != set(seeds):
        raise ValueError("evaluation episodes do not cover the reusable seeds exactly")

    comparisons: list[dict[str, Any]] = []
    disabled_summaries: list[dict[str, Any]] = []
    enabled_summaries: list[dict[str, Any]] = []
    total_intents = 0
    total_risks = 0
    complete = True
    action_change_seeds = 0
    for seed in seeds:
        disabled = disabled_by_seed[seed]
        enabled = enabled_by_seed[seed]
        disabled_summary = _compact_summary(disabled)
        enabled_summary = _compact_summary(enabled)
        disabled_summaries.append(disabled_summary)
        enabled_summaries.append(enabled_summary)
        exposure = diagnostic_exposure(enabled.trace)
        total_intents += exposure["intent_exposed_decisions"]
        total_risks += exposure["exact_risk_candidate_exposures"]
        complete = complete and exposure["diagnostics_complete"]
        prefix = common_action_state_prefix(disabled.trace, enabled.trace)
        changed = _action_sequence(disabled.trace) != _action_sequence(enabled.trace)
        action_change_seeds += int(changed)
        comparisons.append(
            {
                "seed": seed,
                "disabled": disabled_summary,
                "enabled": enabled_summary,
                "common_action_state_prefix_rows": prefix,
                "trajectories_differ": (
                    [_action_state_row(row) for row in disabled.trace]
                    != [_action_state_row(row) for row in enabled.trace]
                ),
                "action_sequence_changed": changed,
                "first_causally_comparable_action_difference": (
                    first_causally_comparable_action_difference(
                        disabled.trace, enabled.trace
                    )
                ),
                "non_comparable_tail_rows": {
                    "disabled": len(disabled.trace) - prefix,
                    "enabled": len(enabled.trace) - prefix,
                },
                "enabled_diagnostics": exposure,
            }
        )

    return {
        "schema": REPORT_SCHEMA,
        "sources": source_bindings,
        "seeds": seeds,
        "disabled_legacy_parity": legacy_parity,
        "disabled_summary_digest": _json_digest(disabled_summaries),
        "enabled_summary_digest": _json_digest(enabled_summaries),
        "disabled_outcomes": [row["outcome"] for row in disabled_summaries],
        "enabled_outcomes": [row["outcome"] for row in enabled_summaries],
        "total_intent_exposed_decisions": total_intents,
        "total_exact_risk_candidate_exposures": total_risks,
        "seeds_with_action_change": action_change_seeds,
        "enabled_diagnostics_complete": complete,
        "per_seed": comparisons,
    }


def validate_report_gates(report: dict[str, Any]) -> None:
    """Fail closed on missing compatibility or intervention evidence."""

    if not report.get("disabled_legacy_parity", {}).get("bit_exact", False):
        raise RuntimeError("disabled V38 trace does not match checked-in replay")
    if not report.get("enabled_diagnostics_complete", False):
        raise RuntimeError("enabled trace lacks partner-intent diagnostics")
    if int(report.get("total_intent_exposed_decisions", 0)) <= 0:
        raise RuntimeError("enabled evaluation observed no partner intent")
    if int(report.get("total_exact_risk_candidate_exposures", 0)) <= 0:
        raise RuntimeError("enabled evaluation observed no exact-risk candidates")


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    """Atomically replace a JSON report in its destination directory."""

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


def run_diagnostic(
    *,
    legacy_config_path: Path,
    enabled_config_path: Path,
    seed_set_path: Path,
    checkpoint_path: Path,
    legacy_replay_path: Path,
    output_path: Path,
    java: str,
    port: int,
) -> dict[str, Any]:
    """Evaluate the frozen checkpoint in separate disabled and enabled JVMs."""

    root = repo_root()
    legacy_config = _load_json(legacy_config_path)
    enabled_config = _load_json(enabled_config_path)
    seed_set = _load_json(seed_set_path)
    seeds, _ = validate_reusable_inputs(legacy_config, enabled_config, seed_set)
    _configure_torch(legacy_config)

    def fresh_evaluation(config: dict[str, Any]) -> list[EpisodeRollout]:
        model = SelectorActorCritic(int(config["model_init_seed"]))
        payload = load_checkpoint(
            checkpoint_path,
            model,
            reward_schema=str(config["reward_schema"]),
        )
        if payload.get("config_sha256") != _sha256(legacy_config_path):
            raise ValueError("checkpoint is not bound to the V38 legacy config")
        return _evaluate(model, seeds, config, java=java, port=port)

    disabled_episodes = fresh_evaluation(legacy_config)
    enabled_episodes = fresh_evaluation(enabled_config)
    expected_replay = _load_jsonl(legacy_replay_path)
    disabled_seed_2001 = next(
        episode for episode in disabled_episodes if episode.seed == 2001
    )
    legacy_parity = exact_legacy_trace_parity(
        disabled_seed_2001.trace, expected_replay, seed=2001
    )
    source_paths = {
        "legacy_config": legacy_config_path,
        "enabled_config": enabled_config_path,
        "reusable_seed_set": seed_set_path,
        "checkpoint": checkpoint_path,
        "legacy_replay": legacy_replay_path,
    }
    report = build_report(
        source_bindings={
            name: _source_binding(path, root) for name, path in source_paths.items()
        },
        seeds=seeds,
        disabled_episodes=disabled_episodes,
        enabled_episodes=enabled_episodes,
        legacy_parity=legacy_parity,
    )
    validate_report_gates(report)
    atomic_write_json(output_path, report)
    return report


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description="V39 reusable partner-intent checkpoint replay diagnostic"
    )
    parser.add_argument(
        "--legacy-config",
        type=Path,
        default=root / "configs/training/m8-selector-v38-owned-schematic-staging.json",
    )
    parser.add_argument(
        "--enabled-config",
        type=Path,
        default=(
            root
            / "configs/training/m8-selector-v39-partner-intent-duplication-risk.json"
        ),
    )
    parser.add_argument(
        "--seed-set",
        type=Path,
        default=root / "configs/evaluation/bootstrap-defense-v1-dev-v1.json",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=root / "runs/m8-selector-v38-a/selector-v1-update-20.pt",
    )
    parser.add_argument(
        "--legacy-replay",
        type=Path,
        default=root / "runs/m8-selector-v38-a/checkpoint-replay-a.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "runs/m8-selector-v39-partner-intent-diagnostic.json",
    )
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    try:
        report = run_diagnostic(
            legacy_config_path=args.legacy_config.resolve(),
            enabled_config_path=args.enabled_config.resolve(),
            seed_set_path=args.seed_set.resolve(),
            checkpoint_path=args.checkpoint.resolve(),
            legacy_replay_path=args.legacy_replay.resolve(),
            output_path=args.output.resolve(),
            java=args.java,
            port=args.port,
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"V39-PARTNER-INTENT-DIAGNOSTIC ERROR: {error}", file=sys.stderr)
        return 1
    print(
        "V39-PARTNER-INTENT-DIAGNOSTIC PASS "
        f"legacy_rows={report['disabled_legacy_parity']['actual_rows']} "
        f"intent_decisions={report['total_intent_exposed_decisions']} "
        f"risk_exposures={report['total_exact_risk_candidate_exposures']} "
        f"action_change_seeds={report['seeds_with_action_change']}"
    )
    print(f"report={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
