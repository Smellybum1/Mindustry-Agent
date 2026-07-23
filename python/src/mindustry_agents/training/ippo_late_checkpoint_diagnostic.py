"""Run ADR-0081's immutable-v4 late-checkpoint mode diagnostic."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

import torch

from mindustry_agents.process.launcher import (
    DEFAULT_PORT,
    LaunchConfig,
    RlServerProcess,
    repo_root,
)
from mindustry_agents.training.ippo import (
    SharedRecurrentSelector,
    model_state_digest,
)
from mindustry_agents.training.ippo_artifacts import load_ippo_checkpoint
from mindustry_agents.training.ippo_policy_mode_diagnostic import (
    _aggregate,
    _episode_summary,
    _json_digest,
    _write_json,
)
from mindustry_agents.training.ippo_ppo import (
    IPPO_V4_CONFIG_SHA256,
    IPPO_V4_PROTOCOL_SHA256,
    load_ippo_v4_config,
    sha256_path,
)
from mindustry_agents.training.ippo_rollout import rollout_ippo_episode

PROTOCOL_RELATIVE = (
    "configs/evaluation/"
    "m9-ippo-v4-late-checkpoint-diagnostic-protocol.json"
)
PROTOCOL_SHA256 = (
    "d68fee034d3b90e720988639bb47b3e6df2961c7fabc46a0b9b161bab32b2dc1"
)
CONFIG_RELATIVE = "configs/training/m9-ippo-v4-entropy-anneal.json"


def classify(
    *,
    update_31_argmax_wins: int,
    update_32_argmax_wins: int,
    update_31_stochastic_wins: int,
    update_32_stochastic_wins: int,
    rules: dict[str, Any],
) -> dict[str, Any]:
    """Apply ADR-0081's exact integer-only classification."""

    expected = {
        "required_argmax_win_drop": 10,
        "minimum_update_32_stochastic_wins_for_retention": 32,
        "mode_instability_retention_ratio_numerator": 4,
        "mode_instability_retention_ratio_denominator": 5,
        "optimizer_collapse_ratio_numerator": 1,
        "optimizer_collapse_ratio_denominator": 2,
    }
    if any(int(rules.get(key, -1)) != value for key, value in expected.items()):
        raise ValueError("M9 late-checkpoint classification rules drifted")
    wins = (
        update_31_argmax_wins,
        update_32_argmax_wins,
        update_31_stochastic_wins,
        update_32_stochastic_wins,
    )
    if (
        any(value < 0 for value in wins)
        or update_31_argmax_wins > 40
        or update_32_argmax_wins > 40
        or update_31_stochastic_wins > 160
        or update_32_stochastic_wins > 160
    ):
        raise ValueError("M9 late-checkpoint win count is invalid")

    argmax_drop = update_31_argmax_wins - update_32_argmax_wins
    mode_instability = (
        argmax_drop >= 10
        and update_32_stochastic_wins >= 32
        and update_32_stochastic_wins * 5
        >= update_31_stochastic_wins * 4
    )
    distribution_collapse = (
        argmax_drop >= 10
        and update_31_stochastic_wins >= 32
        and update_32_stochastic_wins * 2
        <= update_31_stochastic_wins
    )
    if mode_instability and distribution_collapse:
        raise RuntimeError("M9 late-checkpoint classifications overlap")
    if mode_instability:
        outcome = "deterministic_mode_instability"
        next_direction = "precommit_one_successful_mode_consolidation_mechanism"
    elif distribution_collapse:
        outcome = "optimizer_distribution_collapse"
        next_direction = "precommit_one_optimizer_step_stabilization_mechanism"
    else:
        outcome = "inconclusive"
        next_direction = "do_not_authorize_another_training_recipe"
    return {
        "outcome": outcome,
        "argmax_win_drop": argmax_drop,
        "update_31_stochastic_wins": update_31_stochastic_wins,
        "update_32_stochastic_wins": update_32_stochastic_wins,
        "mode_instability_signal": mode_instability,
        "optimizer_distribution_collapse_signal": distribution_collapse,
        "next_direction": next_direction,
        "candidate_status": "rejected",
        "checkpoint_selection_authorized": False,
        "training_authorized": False,
        "promotion_authorized": False,
    }


def validate_inputs(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[int]]:
    """Validate every immutable source before starting a diagnostic episode."""

    protocol_path = root / PROTOCOL_RELATIVE
    if sha256_path(protocol_path) != PROTOCOL_SHA256:
        raise ValueError("M9 late-checkpoint diagnostic protocol hash drifted")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    authority = protocol.get("authority", {})
    if (
        protocol.get("schema")
        != "m9_ippo_v4_late_checkpoint_diagnostic_protocol_v1"
        or protocol.get("status") != "precommitted"
        or protocol.get("data_classification") != "public_dev_only"
        or authority
        != {
            "checkpoint_selection_authorized": False,
            "candidate_repair_authorized": False,
            "promotion_authorized": False,
            "training_authorized": False,
            "confirmation_or_held_out_access": False,
        }
    ):
        raise ValueError("M9 late-checkpoint diagnostic authority drifted")

    source = protocol["source_candidate"]
    result_path = root / source["result_path"]
    manifest_path = root / source["manifest_path"]
    if (
        sha256_path(result_path) != source["result_sha256"]
        or sha256_path(manifest_path) != source["manifest_sha256"]
    ):
        raise ValueError("M9 late-checkpoint source evidence drifted")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        result.get("decision", {}).get("candidate_status") != "rejected"
        or result.get("restricted_state", {}).get(
            "confirmation_or_held_out_access"
        )
        is not False
        or result.get("recipe", {}).get("config_sha256")
        != IPPO_V4_CONFIG_SHA256
        or result.get("recipe", {}).get("protocol_sha256")
        != IPPO_V4_PROTOCOL_SHA256
        or manifest.get("construction_passed") is not False
        or manifest.get("repository", {}).get("commit")
        != source["training_commit"]
        or manifest.get("source_config", {}).get("sha256")
        != IPPO_V4_CONFIG_SHA256
        or manifest.get("public_protocol", {}).get("sha256")
        != IPPO_V4_PROTOCOL_SHA256
    ):
        raise ValueError("M9 late-checkpoint rejected source is invalid")

    checkpoints = protocol["source_checkpoints"]
    expected_order = protocol["execution"]["checkpoint_execution_order"]
    if [int(item["update"]) for item in checkpoints] != expected_order:
        raise ValueError("M9 late-checkpoint execution order drifted")
    for checkpoint in checkpoints:
        checkpoint_path = root / checkpoint["path"]
        if sha256_path(checkpoint_path) != checkpoint["file_sha256"]:
            raise ValueError("M9 late-checkpoint file identity drifted")
        row = next(
            (
                item
                for item in manifest["checkpoint_selection"]
                if int(item["update"]) == int(checkpoint["update"])
            ),
            None,
        )
        if (
            row is None
            or row["checkpoint_content_sha256"]
            != checkpoint["checkpoint_content_sha256"]
            or row["model_state_sha256"]
            != checkpoint["model_state_sha256"]
            or int(row["wins"])
            != int(checkpoint["expected_immutable_manifest_wins"])
        ):
            raise ValueError("M9 late-checkpoint content identity drifted")

    roots = protocol["public_roots"]
    roots_path = root / roots["path"]
    if sha256_path(roots_path) != roots["sha256"]:
        raise ValueError("M9 late-checkpoint public roots drifted")
    roots_document = json.loads(roots_path.read_text(encoding="utf-8"))
    seeds = [int(seed) for seed in roots_document.get("seeds", [])]
    if (
        roots_document.get("split") != "dev"
        or len(seeds) != int(roots["count"])
        or len(set(seeds)) != len(seeds)
        or any(seed < 19_000_000_000 or seed >= 20_000_000_000 for seed in seeds)
    ):
        raise ValueError("M9 late-checkpoint public roots are invalid")
    return protocol, manifest, seeds


def _run_checkpoint(
    *,
    root: Path,
    env: RlServerProcess,
    config: dict[str, Any],
    checkpoint: dict[str, Any],
    expected: dict[str, Any],
    seeds: Sequence[int],
    action_sampling_seeds: Sequence[int],
) -> dict[str, Any]:
    model = SharedRecurrentSelector(int(config["model_init_seed"]))
    payload = load_ippo_checkpoint(
        root / checkpoint["path"],
        model,
        expected_config_sha256=IPPO_V4_CONFIG_SHA256,
    )
    if (
        int(payload["update"]) != int(checkpoint["update"])
        or payload["checkpoint_content_sha256"]
        != checkpoint["checkpoint_content_sha256"]
        or model_state_digest(model) != checkpoint["model_state_sha256"]
    ):
        raise ValueError("M9 late-checkpoint loaded identity drifted")
    initial_model = model_state_digest(model)
    model.eval()

    deterministic_generator = torch.Generator().manual_seed(9602)
    deterministic = [
        _episode_summary(
            rollout_ippo_episode(
                env,
                model,
                config,
                seed=seed,
                evaluation=True,
                action_generator=deterministic_generator,
            )
        )
        for seed in seeds
    ]
    streams = []
    all_stochastic: list[dict[str, Any]] = []
    for action_seed in action_sampling_seeds:
        generator = torch.Generator().manual_seed(int(action_seed))
        episodes = [
            _episode_summary(
                rollout_ippo_episode(
                    env,
                    model,
                    config,
                    seed=seed,
                    evaluation=False,
                    action_generator=generator,
                )
            )
            for seed in seeds
        ]
        all_stochastic.extend(episodes)
        streams.append(
            {
                "action_sampling_seed": int(action_seed),
                "aggregate": _aggregate(episodes),
                "episodes": episodes,
            }
        )

    final_model = model_state_digest(model)
    if final_model != initial_model:
        raise RuntimeError("M9 late-checkpoint diagnostic mutated a model")
    deterministic_aggregate = _aggregate(deterministic)
    for key in (
        "episodes",
        "wins",
        "mean_team_return",
        "mean_core_health",
        "mean_team_idle_fraction",
    ):
        if deterministic_aggregate[key] != expected[key]:
            raise RuntimeError(
                f"M9 late-checkpoint deterministic replay drifted: {key}"
            )
    return {
        "update": int(checkpoint["update"]),
        "model_state_sha256": initial_model,
        "model_unchanged": True,
        "deterministic_argmax": {
            "aggregate": deterministic_aggregate,
            "episodes": deterministic,
        },
        "stochastic_categorical": {
            "aggregate": _aggregate(all_stochastic),
            "streams": streams,
        },
    }


def _run_once(
    root: Path,
    protocol: dict[str, Any],
    manifest: dict[str, Any],
    seeds: Sequence[int],
    *,
    java: str,
    port: int,
) -> dict[str, Any]:
    config = load_ippo_v4_config(root / CONFIG_RELATIVE)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(int(config["torch_threads"]))
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    if torch.get_num_threads() != 1:
        raise RuntimeError("M9 late-checkpoint diagnostic torch pin failed")

    expected_by_update = {
        int(item["update"]): item
        for item in manifest["checkpoint_selection"]
    }
    sampling_seeds = protocol["modes"]["stochastic_categorical"][
        "action_sampling_seeds"
    ]
    with RlServerProcess(
        LaunchConfig(
            port=port,
            java=java,
            build_if_missing=False,
        )
    ) as env:
        env.handshake("m9-ippo-v4-late-checkpoint-diagnostic")
        checkpoints = [
            _run_checkpoint(
                root=root,
                env=env,
                config=config,
                checkpoint=checkpoint,
                expected=expected_by_update[int(checkpoint["update"])],
                seeds=seeds,
                action_sampling_seeds=sampling_seeds,
            )
            for checkpoint in protocol["source_checkpoints"]
        ]
    return {"checkpoints": checkpoints}


def run_diagnostic(
    *,
    root: Path,
    java: str,
    port: int,
) -> dict[str, Any]:
    protocol, manifest, seeds = validate_inputs(root)
    runs = [
        _run_once(
            root,
            protocol,
            manifest,
            seeds,
            java=java,
            port=port,
        )
        for _ in range(int(protocol["execution"]["fresh_jvms"]))
    ]
    if runs[0] != runs[1]:
        raise RuntimeError("M9 late-checkpoint fresh-JVM reports diverged")
    run_digest = _json_digest(runs[0])
    by_update = {
        int(item["update"]): item for item in runs[0]["checkpoints"]
    }
    classification = classify(
        update_31_argmax_wins=int(
            by_update[31]["deterministic_argmax"]["aggregate"]["wins"]
        ),
        update_32_argmax_wins=int(
            by_update[32]["deterministic_argmax"]["aggregate"]["wins"]
        ),
        update_31_stochastic_wins=int(
            by_update[31]["stochastic_categorical"]["aggregate"]["wins"]
        ),
        update_32_stochastic_wins=int(
            by_update[32]["stochastic_categorical"]["aggregate"]["wins"]
        ),
        rules=protocol["classification"],
    )
    return {
        "schema": "m9_ippo_v4_late_checkpoint_diagnostic_report_v1",
        "implementation_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
        ).strip(),
        "protocol_sha256": PROTOCOL_SHA256,
        "source_candidate_status": "rejected",
        "source_checkpoints": protocol["source_checkpoints"],
        "public_roots": protocol["public_roots"],
        "fresh_jvm_runs": len(runs),
        "fresh_jvm_runs_equal": True,
        "run_sha256_by_jvm": [run_digest, run_digest],
        "result": runs[0],
        "classification": classification,
        "confirmation_or_held_out_access": False,
        "all_passed": True,
    }


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            root / "runs/m9-ippo-v4-late-checkpoint-diagnostic.json"
        ),
    )
    args = parser.parse_args(argv)
    try:
        report = run_diagnostic(
            root=root,
            java=args.java,
            port=args.port,
        )
        _write_json(args.output.resolve(), report)
    except Exception as error:
        print(f"M9 IPPO LATE-CHECKPOINT FAIL: {error}", file=sys.stderr)
        return 1
    by_update = {
        int(item["update"]): item
        for item in report["result"]["checkpoints"]
    }
    print(
        "M9 IPPO LATE-CHECKPOINT OK "
        f"categorical={by_update[31]['stochastic_categorical']['aggregate']['wins']}"
        f"->{by_update[32]['stochastic_categorical']['aggregate']['wins']} "
        f"outcome={report['classification']['outcome']} "
        f"digest={report['run_sha256_by_jvm'][0][:16]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
