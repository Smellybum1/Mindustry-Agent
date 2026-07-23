"""Run ADR-0085's immutable-v5 public mode-margin diagnostic."""

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
    IPPO_V5_CONFIG_SHA256,
    IPPO_V5_PROTOCOL_SHA256,
    IPPOEpisodeRollout,
    load_ippo_v5_config,
    sha256_path,
)
from mindustry_agents.training.ippo_rollout import (
    IPPOEpisodeEvidence,
    rollout_ippo_episode,
)

PROTOCOL_RELATIVE = (
    "configs/evaluation/"
    "m9-ippo-v5-mode-margin-diagnostic-protocol.json"
)
PROTOCOL_SHA256 = (
    "9a9b44e36a22d68dcc37216db377ff29fcecf9ad6525e2d89bd6092a694dad0b"
)
CONFIG_RELATIVE = "configs/training/m9-ippo-v5-success-imitation.json"


def classify(
    *,
    update_7_argmax_wins: int,
    update_32_argmax_wins: int,
    update_7_stochastic_wins: int,
    update_32_stochastic_wins: int,
    rules: dict[str, Any],
) -> dict[str, Any]:
    """Apply ADR-0085's exact integer-only classification."""

    expected = {
        "maximum_argmax_wins_for_unconsolidated": 1,
        "minimum_update_32_stochastic_wins_for_retention": 16,
        "retention_ratio_numerator": 4,
        "retention_ratio_denominator": 5,
        "minimum_update_7_stochastic_wins_for_erosion_reference": 16,
        "erosion_ratio_numerator": 1,
        "erosion_ratio_denominator": 2,
    }
    if any(int(rules.get(key, -1)) != value for key, value in expected.items()):
        raise ValueError("M9 v5 mode-margin classification rules drifted")
    wins = (
        update_7_argmax_wins,
        update_32_argmax_wins,
        update_7_stochastic_wins,
        update_32_stochastic_wins,
    )
    if (
        any(value < 0 for value in wins)
        or update_7_argmax_wins > 40
        or update_32_argmax_wins > 40
        or update_7_stochastic_wins > 160
        or update_32_stochastic_wins > 160
    ):
        raise ValueError("M9 v5 mode-margin win count is invalid")

    retained = (
        update_7_argmax_wins <= 1
        and update_32_argmax_wins <= 1
        and update_32_stochastic_wins >= 16
        and update_32_stochastic_wins * 5
        >= update_7_stochastic_wins * 4
    )
    eroded = (
        update_7_stochastic_wins >= 16
        and update_32_stochastic_wins * 2
        <= update_7_stochastic_wins
    )
    if retained and eroded:
        raise RuntimeError("M9 v5 mode-margin classifications overlap")
    if retained:
        outcome = (
            "stochastic_success_retained_without_"
            "deterministic_consolidation"
        )
        next_direction = (
            "precommit_one_deterministic_margin_alignment_mechanism"
        )
    elif eroded:
        outcome = "success_distribution_eroded"
        next_direction = (
            "precommit_one_optimizer_or_auxiliary_loss_"
            "stabilization_mechanism"
        )
    else:
        outcome = "inconclusive"
        next_direction = "do_not_authorize_another_training_recipe"
    return {
        "outcome": outcome,
        "update_7_argmax_wins": update_7_argmax_wins,
        "update_32_argmax_wins": update_32_argmax_wins,
        "update_7_stochastic_wins": update_7_stochastic_wins,
        "update_32_stochastic_wins": update_32_stochastic_wins,
        "retained_without_consolidation_signal": retained,
        "success_distribution_eroded_signal": eroded,
        "next_direction": next_direction,
        "candidate_status": "rejected",
        "checkpoint_selection_authorized": False,
        "training_authorized": False,
        "promotion_authorized": False,
    }


def _measurement_totals() -> dict[str, float]:
    return {
        "transition_count": 0.0,
        "chosen_action_probability_sum": 0.0,
        "top_two_logit_margin_sum": 0.0,
    }


def _measure_rollout(
    model: SharedRecurrentSelector,
    rollout: IPPOEpisodeRollout,
) -> dict[str, float]:
    active = [
        transition
        for transition in rollout.transitions
        if transition.policy_loss_mask
    ]
    totals = _measurement_totals()
    if not active:
        return totals
    candidates = torch.stack([item.candidates for item in active])
    scalars = torch.stack([item.scalars for item in active])
    present = torch.stack([item.candidate_present for item in active])
    masks = torch.stack([item.action_mask for item in active])
    hidden = torch.stack([item.hidden_input for item in active])
    agent_ids = torch.tensor(
        [item.agent_id for item in active], dtype=torch.long
    )
    actions = torch.tensor(
        [item.action for item in active], dtype=torch.long
    )
    if bool((masks.sum(dim=1) < 2).any()):
        raise ValueError(
            "M9 v5 mode-margin actor transition has fewer than two legal actions"
        )
    with torch.no_grad():
        _, logits, _, _ = model(
            candidates,
            scalars,
            present,
            masks,
            agent_ids,
            hidden,
        )
        probabilities = torch.softmax(logits, dim=-1)
        chosen = probabilities.gather(1, actions[:, None]).squeeze(1)
        top_two = torch.topk(logits, k=2, dim=1).values
        margins = top_two[:, 0] - top_two[:, 1]
    return {
        "transition_count": float(len(active)),
        "chosen_action_probability_sum": float(chosen.sum().item()),
        "top_two_logit_margin_sum": float(margins.sum().item()),
    }


def _merge_measurements(
    target: dict[str, float],
    source: dict[str, float],
) -> None:
    for key in target:
        target[key] += source[key]


def _finish_measurements(
    totals: dict[str, float],
) -> dict[str, float | None]:
    count = int(totals["transition_count"])
    if count == 0:
        return {
            "transition_count": 0,
            "mean_chosen_action_probability": None,
            "mean_top_two_logit_margin": None,
        }
    return {
        "transition_count": count,
        "mean_chosen_action_probability": (
            totals["chosen_action_probability_sum"] / count
        ),
        "mean_top_two_logit_margin": (
            totals["top_two_logit_margin_sum"] / count
        ),
    }


def _measure_evidence(
    model: SharedRecurrentSelector,
    evidence: Sequence[IPPOEpisodeEvidence],
) -> dict[str, dict[str, float | None]]:
    totals = {"win": _measurement_totals(), "loss": _measurement_totals()}
    for episode in evidence:
        outcome = episode.rollout.outcome
        if outcome not in totals:
            raise ValueError("M9 v5 mode-margin outcome is unsupported")
        _merge_measurements(
            totals[outcome],
            _measure_rollout(model, episode.rollout),
        )
    return {
        outcome: _finish_measurements(value)
        for outcome, value in totals.items()
    }


def validate_inputs(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[int]]:
    """Validate every immutable source before starting a diagnostic episode."""

    protocol_path = root / PROTOCOL_RELATIVE
    if sha256_path(protocol_path) != PROTOCOL_SHA256:
        raise ValueError("M9 v5 mode-margin protocol hash drifted")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    authority = protocol.get("authority", {})
    if (
        protocol.get("schema")
        != "m9_ippo_v5_mode_margin_diagnostic_protocol_v1"
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
        raise ValueError("M9 v5 mode-margin authority drifted")

    source = protocol["source_candidate"]
    result_path = root / source["result_path"]
    manifest_path = root / source["manifest_path"]
    if (
        sha256_path(result_path) != source["result_sha256"]
        or sha256_path(manifest_path) != source["manifest_sha256"]
    ):
        raise ValueError("M9 v5 mode-margin source evidence drifted")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        result.get("decision") != "reject_before_replica_b"
        or result.get("confirmation_or_held_out_access") is not False
        or result.get("config_sha256") != IPPO_V5_CONFIG_SHA256
        or result.get("protocol_sha256") != IPPO_V5_PROTOCOL_SHA256
        or manifest.get("construction_passed") is not False
        or manifest.get("repository", {}).get("commit")
        != source["training_commit"]
        or manifest.get("source_config", {}).get("sha256")
        != IPPO_V5_CONFIG_SHA256
        or manifest.get("public_protocol", {}).get("sha256")
        != IPPO_V5_PROTOCOL_SHA256
    ):
        raise ValueError("M9 v5 mode-margin rejected source is invalid")

    checkpoints = protocol["source_checkpoints"]
    expected_order = protocol["execution"]["checkpoint_execution_order"]
    if [int(item["update"]) for item in checkpoints] != expected_order:
        raise ValueError("M9 v5 mode-margin execution order drifted")
    for checkpoint in checkpoints:
        checkpoint_path = root / checkpoint["path"]
        if sha256_path(checkpoint_path) != checkpoint["file_sha256"]:
            raise ValueError("M9 v5 mode-margin checkpoint file drifted")
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
            raise ValueError("M9 v5 mode-margin checkpoint identity drifted")

    roots = protocol["public_roots"]
    roots_path = root / roots["path"]
    if sha256_path(roots_path) != roots["sha256"]:
        raise ValueError("M9 v5 mode-margin public roots drifted")
    roots_document = json.loads(roots_path.read_text(encoding="utf-8"))
    seeds = [int(seed) for seed in roots_document.get("seeds", [])]
    if (
        roots_document.get("split") != "dev"
        or len(seeds) != int(roots["count"])
        or len(set(seeds)) != len(seeds)
        or any(seed < 19_000_000_000 or seed >= 20_000_000_000 for seed in seeds)
    ):
        raise ValueError("M9 v5 mode-margin public roots are invalid")
    expected_measurements = {
        "transition_filter": "policy_loss_mask_true",
        "logits": (
            "recomputed_from_stored_transition_inputs_and_private_hidden_input"
        ),
        "authoritative_mask": "stored_action_mask_before_softmax",
        "chosen_action_probability": (
            "masked_softmax_probability_of_executed_action"
        ),
        "top_two_logit_margin": (
            "largest_legal_logit_minus_second_largest_legal_logit"
        ),
        "groups": [
            "mode",
            "checkpoint_update",
            "authoritative_terminal_outcome",
        ],
        "aggregates": [
            "transition_count",
            "mean_chosen_action_probability",
            "mean_top_two_logit_margin",
        ],
        "no_model_or_environment_mutation": True,
    }
    if protocol.get("action_mode_measurements") != expected_measurements:
        raise ValueError("M9 v5 mode-margin measurement contract drifted")
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
        expected_config_sha256=IPPO_V5_CONFIG_SHA256,
    )
    if (
        int(payload["update"]) != int(checkpoint["update"])
        or payload["checkpoint_content_sha256"]
        != checkpoint["checkpoint_content_sha256"]
        or model_state_digest(model) != checkpoint["model_state_sha256"]
    ):
        raise ValueError("M9 v5 mode-margin loaded identity drifted")
    initial_model = model_state_digest(model)
    model.eval()

    deterministic_generator = torch.Generator().manual_seed(9602)
    deterministic_evidence = [
        rollout_ippo_episode(
            env,
            model,
            config,
            seed=seed,
            evaluation=True,
            action_generator=deterministic_generator,
        )
        for seed in seeds
    ]
    deterministic = [
        _episode_summary(item) for item in deterministic_evidence
    ]
    streams = []
    all_stochastic: list[dict[str, Any]] = []
    all_stochastic_evidence: list[IPPOEpisodeEvidence] = []
    for action_seed in action_sampling_seeds:
        generator = torch.Generator().manual_seed(int(action_seed))
        stream_evidence = [
            rollout_ippo_episode(
                env,
                model,
                config,
                seed=seed,
                evaluation=False,
                action_generator=generator,
            )
            for seed in seeds
        ]
        episodes = [_episode_summary(item) for item in stream_evidence]
        all_stochastic.extend(episodes)
        all_stochastic_evidence.extend(stream_evidence)
        streams.append(
            {
                "action_sampling_seed": int(action_seed),
                "aggregate": _aggregate(episodes),
                "episodes": episodes,
            }
        )

    final_model = model_state_digest(model)
    if final_model != initial_model:
        raise RuntimeError("M9 v5 mode-margin diagnostic mutated a model")
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
                f"M9 v5 mode-margin deterministic replay drifted: {key}"
            )
    return {
        "update": int(checkpoint["update"]),
        "model_state_sha256": initial_model,
        "model_unchanged": True,
        "deterministic_argmax": {
            "aggregate": deterministic_aggregate,
            "episodes": deterministic,
            "action_mode_measurements": _measure_evidence(
                model, deterministic_evidence
            ),
        },
        "stochastic_categorical": {
            "aggregate": _aggregate(all_stochastic),
            "streams": streams,
            "action_mode_measurements": _measure_evidence(
                model, all_stochastic_evidence
            ),
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
    config = load_ippo_v5_config(root / CONFIG_RELATIVE)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(int(config["torch_threads"]))
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    if torch.get_num_threads() != 1:
        raise RuntimeError("M9 v5 mode-margin torch pin failed")

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
        env.handshake("m9-ippo-v5-mode-margin-diagnostic")
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
        raise RuntimeError("M9 v5 mode-margin fresh-JVM reports diverged")
    run_digest = _json_digest(runs[0])
    by_update = {
        int(item["update"]): item for item in runs[0]["checkpoints"]
    }
    classification = classify(
        update_7_argmax_wins=int(
            by_update[7]["deterministic_argmax"]["aggregate"]["wins"]
        ),
        update_32_argmax_wins=int(
            by_update[32]["deterministic_argmax"]["aggregate"]["wins"]
        ),
        update_7_stochastic_wins=int(
            by_update[7]["stochastic_categorical"]["aggregate"]["wins"]
        ),
        update_32_stochastic_wins=int(
            by_update[32]["stochastic_categorical"]["aggregate"]["wins"]
        ),
        rules=protocol["classification"],
    )
    return {
        "schema": "m9_ippo_v5_mode_margin_diagnostic_report_v1",
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
            root / "runs/m9-ippo-v5-mode-margin-diagnostic.json"
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
        print(f"M9 IPPO V5 MODE-MARGIN FAIL: {error}", file=sys.stderr)
        return 1
    by_update = {
        int(item["update"]): item
        for item in report["result"]["checkpoints"]
    }
    print(
        "M9 IPPO V5 MODE-MARGIN OK "
        f"categorical={by_update[7]['stochastic_categorical']['aggregate']['wins']}"
        f"->{by_update[32]['stochastic_categorical']['aggregate']['wins']} "
        f"outcome={report['classification']['outcome']} "
        f"digest={report['run_sha256_by_jvm'][0][:16]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
