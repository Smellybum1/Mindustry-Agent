"""Run ADR-0077's bounded public stochastic-versus-argmax diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from statistics import fmean
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
from mindustry_agents.training.ippo_ppo import (
    IPPO_V3_CONFIG_SHA256,
    load_ippo_v3_config,
    sha256_path,
)
from mindustry_agents.training.ippo_rollout import (
    IPPOEpisodeEvidence,
    rollout_ippo_episode,
)

PROTOCOL_RELATIVE = (
    "configs/evaluation/m9-ippo-v3-policy-mode-diagnostic-protocol.json"
)
PROTOCOL_SHA256 = (
    "89fecf69b76cd0fb79ed2fbafb97dc5b16446ee21648ceeabd4ddc892322b0c7"
)
CONFIG_RELATIVE = "configs/training/m9-ippo-v3-diverse2048.json"


def _json_digest(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _episode_summary(evidence: IPPOEpisodeEvidence) -> dict[str, Any]:
    return {
        "seed": evidence.rollout.seed,
        "outcome": evidence.rollout.outcome,
        "tick": evidence.tick,
        "core_health": evidence.core_health,
        "transitions": len(evidence.rollout.transitions),
        "team_return": sum(evidence.shared_reward_components.values()),
        "team_idle_fraction": float(
            evidence.coordination_metrics["idle_fraction"]
        ),
        "trace_sha256": evidence.trace_sha256,
        "model_state_sha256": evidence.model_state_sha256,
    }


def _aggregate(episodes: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not episodes:
        raise ValueError("M9 policy-mode diagnostic cannot aggregate no episodes")
    return {
        "episodes": len(episodes),
        "wins": sum(item["outcome"] == "win" for item in episodes),
        "mean_team_return": fmean(
            float(item["team_return"]) for item in episodes
        ),
        "mean_core_health": fmean(
            float(item["core_health"]) for item in episodes
        ),
        "mean_team_idle_fraction": fmean(
            float(item["team_idle_fraction"]) for item in episodes
        ),
    }


def classify(stochastic_wins: int, minimum: int) -> dict[str, Any]:
    if minimum != 32:
        raise ValueError("M9 policy-mode diagnostic threshold drifted")
    if not 0 <= stochastic_wins <= 160:
        raise ValueError("M9 policy-mode diagnostic win count is invalid")
    signal = stochastic_wins >= minimum
    return {
        "minimum_stochastic_wins_total": minimum,
        "stochastic_wins_total": stochastic_wins,
        "stochastic_episode_total": 160,
        "sampling_signal": signal,
        "interpretation": (
            "fixed categorical sampling transfers a public-dev survival signal"
            if signal
            else "fixed categorical sampling does not transfer the frozen survival signal"
        ),
        "candidate_status": "rejected",
        "checkpoint_selection_authorized": False,
        "training_authorized": False,
        "promotion_authorized": False,
    }


def validate_inputs(root: Path) -> tuple[dict[str, Any], dict[str, Any], list[int]]:
    protocol_path = root / PROTOCOL_RELATIVE
    if sha256_path(protocol_path) != PROTOCOL_SHA256:
        raise ValueError("M9 policy-mode diagnostic protocol hash drifted")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    authority = protocol.get("authority", {})
    if (
        protocol.get("schema")
        != "m9_ippo_v3_policy_mode_diagnostic_protocol_v1"
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
        raise ValueError("M9 policy-mode diagnostic authority drifted")

    source = protocol["source_candidate"]
    result_path = root / source["result_path"]
    manifest_path = root / source["manifest_path"]
    if (
        sha256_path(result_path) != source["result_sha256"]
        or sha256_path(manifest_path) != source["manifest_sha256"]
    ):
        raise ValueError("M9 policy-mode diagnostic source evidence drifted")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        result.get("decision", {}).get("candidate_status") != "rejected"
        or result.get("restricted_state", {}).get(
            "confirmation_or_held_out_access"
        )
        is not False
        or manifest.get("construction_passed") is not False
        or manifest.get("repository", {}).get("commit")
        != source["training_commit"]
    ):
        raise ValueError("M9 policy-mode diagnostic rejected source is invalid")

    checkpoint = protocol["source_checkpoint"]
    checkpoint_path = root / checkpoint["path"]
    if sha256_path(checkpoint_path) != checkpoint["file_sha256"]:
        raise ValueError("M9 policy-mode diagnostic checkpoint file drifted")
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
        or row["model_state_sha256"] != checkpoint["model_state_sha256"]
        or row["wins"]
        != protocol["modes"]["deterministic_argmax"][
            "expected_immutable_manifest_wins"
        ]
    ):
        raise ValueError("M9 policy-mode diagnostic checkpoint identity drifted")

    roots = protocol["public_roots"]
    roots_path = root / roots["path"]
    if sha256_path(roots_path) != roots["sha256"]:
        raise ValueError("M9 policy-mode diagnostic public roots drifted")
    roots_document = json.loads(roots_path.read_text(encoding="utf-8"))
    seeds = [int(seed) for seed in roots_document.get("seeds", [])]
    if (
        roots_document.get("split") != "dev"
        or len(seeds) != int(roots["count"])
        or len(set(seeds)) != len(seeds)
        or any(seed < 19_000_000_000 or seed >= 20_000_000_000 for seed in seeds)
    ):
        raise ValueError("M9 policy-mode diagnostic public roots are invalid")
    return protocol, manifest, seeds


def _run_once(
    root: Path,
    protocol: dict[str, Any],
    manifest: dict[str, Any],
    seeds: Sequence[int],
    *,
    java: str,
    port: int,
) -> dict[str, Any]:
    config = load_ippo_v3_config(root / CONFIG_RELATIVE)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(int(config["torch_threads"]))
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    if torch.get_num_threads() != 1:
        raise RuntimeError("M9 policy-mode diagnostic torch pin failed")

    model = SharedRecurrentSelector(int(config["model_init_seed"]))
    checkpoint_path = root / protocol["source_checkpoint"]["path"]
    payload = load_ippo_checkpoint(
        checkpoint_path,
        model,
        expected_config_sha256=IPPO_V3_CONFIG_SHA256,
    )
    checkpoint = protocol["source_checkpoint"]
    if (
        int(payload["update"]) != int(checkpoint["update"])
        or payload["checkpoint_content_sha256"]
        != checkpoint["checkpoint_content_sha256"]
        or model_state_digest(model) != checkpoint["model_state_sha256"]
    ):
        raise ValueError("M9 policy-mode diagnostic loaded checkpoint drifted")
    initial_model = model_state_digest(model)
    model.eval()

    with RlServerProcess(
        LaunchConfig(
            port=port,
            java=java,
            build_if_missing=False,
        )
    ) as env:
        env.handshake("m9-ippo-v3-policy-mode-diagnostic")
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
        for action_seed in protocol["modes"]["stochastic_categorical"][
            "action_sampling_seeds"
        ]:
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
        raise RuntimeError("M9 policy-mode diagnostic mutated model parameters")
    deterministic_aggregate = _aggregate(deterministic)
    expected = next(
        item
        for item in manifest["checkpoint_selection"]
        if int(item["update"]) == int(checkpoint["update"])
    )
    for key in (
        "episodes",
        "wins",
        "mean_team_return",
        "mean_core_health",
        "mean_team_idle_fraction",
    ):
        if deterministic_aggregate[key] != expected[key]:
            raise RuntimeError(
                f"M9 policy-mode deterministic replay drifted: {key}"
            )
    return {
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
        raise RuntimeError("M9 policy-mode fresh-JVM reports diverged")
    run_digest = _json_digest(runs[0])
    stochastic = runs[0]["stochastic_categorical"]["aggregate"]
    classification = classify(
        int(stochastic["wins"]),
        int(
            protocol["classification"][
                "minimum_stochastic_wins_total_for_sampling_signal"
            ]
        ),
    )
    return {
        "schema": "m9_ippo_v3_policy_mode_diagnostic_report_v1",
        "implementation_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
        ).strip(),
        "protocol_sha256": PROTOCOL_SHA256,
        "source_candidate_status": "rejected",
        "source_checkpoint": protocol["source_checkpoint"],
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
        default=root / "runs/m9-ippo-v3-policy-mode-diagnostic.json",
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
        print(f"M9 IPPO POLICY-MODE FAIL: {error}", file=sys.stderr)
        return 1
    aggregate = report["result"]["stochastic_categorical"]["aggregate"]
    print(
        "M9 IPPO POLICY-MODE OK "
        f"stochastic={aggregate['wins']}/{aggregate['episodes']} "
        f"signal={report['classification']['sampling_signal']} "
        f"digest={report['run_sha256_by_jvm'][0][:16]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
