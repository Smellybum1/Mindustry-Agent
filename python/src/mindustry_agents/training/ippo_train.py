"""Governed full-run orchestration for ADR-0070's exact M9 IPPO replicas."""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path
from statistics import fmean
from typing import Any, Sequence

import torch

from mindustry_agents.evaluation.ladder import bootstrap_interval
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
from mindustry_agents.training.ippo_artifacts import (
    atomic_write_manifest,
    base_run_manifest,
    compare_ippo_run_manifests,
    finalize_run_manifest,
    load_ippo_checkpoint,
    save_ippo_checkpoint,
)
from mindustry_agents.training.ippo_diverse_roots import (
    diverse_training_seed_schedule,
)
from mindustry_agents.training.ippo_preflight import GATES, V2_GATES, V3_GATES
from mindustry_agents.training.ippo_ppo import (
    IPPO_V1_CONFIG_SHA256,
    IPPO_V2_CONFIG_SHA256,
    IPPO_V3_CONFIG_SHA256,
    config_sha256,
    ippo_update,
    load_ippo_config,
    load_ippo_v1_config,
    protocol_sha256,
    sha256_path,
)
from mindustry_agents.training.ippo_rollout import (
    IPPOEpisodeEvidence,
    rollout_ippo_episode,
)

TRAIN_MINIMUM = 18_000_000_000
TRAIN_MAXIMUM = 19_000_000_000
DEV_MINIMUM = 19_000_000_000
DEV_MAXIMUM = 20_000_000_000


def _candidate_contract(config: dict[str, Any]) -> dict[str, Any]:
    candidate = config.get("candidate_version")
    if candidate == "m9-ippo-v1":
        return {
            "preflight_schema": "m9_ippo_preflight_v1",
            "gates": GATES,
            "prefix": "ippo-v1",
            "baseline": "configs/evaluation/m9-ippo-v1-shared-expert-baseline.json",
        }
    if candidate == "m9-ippo-v2-sequence16":
        return {
            "preflight_schema": "m9_ippo_v2_preflight_v1",
            "gates": V2_GATES,
            "prefix": "ippo-v2-sequence16",
            "baseline": "configs/evaluation/m9-ippo-v1-shared-expert-baseline.json",
        }
    if candidate == "m9-ippo-v3-diverse2048":
        return {
            "preflight_schema": "m9_ippo_v3_preflight_v1",
            "gates": V3_GATES,
            "prefix": "ippo-v3-diverse2048",
            "baseline": "configs/evaluation/m9-ippo-v1-shared-expert-baseline.json",
        }
    raise ValueError("M9 IPPO candidate identity is unsupported")


def _git_commit(root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
    ).strip()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def validate_training_authority(
    path: Path,
    root: Path | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Require a passing complete-gate result bound to the current commit."""

    root = root or repo_root()
    config = config or load_ippo_v1_config(
        root / "configs/training/m9-ippo-v1.json"
    )
    contract = _candidate_contract(config)
    expected_config_sha256 = config_sha256(config)
    expected_protocol_sha256 = protocol_sha256(config)
    result = json.loads(path.read_text(encoding="utf-8"))
    if (
        result.get("schema") != contract["preflight_schema"]
        or result.get("passed") is not True
        or result.get("confirmation_or_held_out_access") is not False
        or result.get("config_sha256") != expected_config_sha256
        or result.get("protocol_sha256") != expected_protocol_sha256
        or result.get("gates") != list(contract["gates"])
    ):
        raise ValueError("M9 training authority is incomplete or invalid")
    commit = _git_commit(root)
    if result.get("implementation_commit") != commit:
        raise ValueError(
            "M9 training authority is not bound to the current commit"
        )
    return {
        "schema": result["schema"],
        "implementation_commit": commit,
        "sha256": sha256_path(path),
        "config_sha256": result["config_sha256"],
        "protocol_sha256": result["protocol_sha256"],
        "confirmation_or_held_out_access": False,
        "passed": True,
    }


def _load_seed_set(
    root: Path,
    relative: str,
    *,
    split: str,
    expected_count: int,
    lower: int,
    upper: int,
    config: dict[str, Any],
) -> tuple[dict[str, Any], Path]:
    if split not in {"train", "dev"}:
        raise ValueError("M9 IPPO may load only public train or dev roots")
    path = root / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    seeds = [int(seed) for seed in document.get("seeds", [])]
    if (
        document.get("split") != split
        or document.get("scenario_id") != config["scenario_id"]
        or int(document.get("scenario_version", -1))
        != int(config["scenario_version"])
        or len(seeds) != expected_count
        or len(set(seeds)) != len(seeds)
        or any(seed < lower or seed >= upper for seed in seeds)
    ):
        raise ValueError(f"M9 IPPO {split} seed set is invalid")
    return document, path


def _seed_identity(root: Path, document: dict[str, Any], path: Path) -> dict:
    return {
        "id": document["seed_set_id"],
        "version": document["seed_set_version"],
        "split": document["split"],
        "path": str(path.relative_to(root).as_posix()),
        "sha256": sha256_path(path),
    }


def training_seed_schedule(
    train_seeds: Sequence[int], config: dict[str, Any]
) -> list[int]:
    """Construct one candidate's immutable public training schedule."""

    seeds = [int(seed) for seed in train_seeds]
    cycles = int(config["training_cycles"])
    episodes_per_update = int(config["episodes_per_update"])
    if config.get("candidate_version") == "m9-ippo-v3-diverse2048":
        if (
            cycles != 32
            or episodes_per_update != 64
            or cycles * episodes_per_update != len(seeds)
        ):
            raise ValueError("M9 IPPO v3 training schedule drifted")
        return diverse_training_seed_schedule(
            seeds,
            shuffle_seed=int(config["shuffle_seed"]),
        )
    if (
        cycles < 1
        or episodes_per_update != len(seeds)
        or cycles * episodes_per_update != 2048
    ):
        raise ValueError("M9 IPPO training schedule drifted")
    schedule: list[int] = []
    for cycle in range(cycles):
        cycle_seeds = list(seeds)
        random.Random(int(config["shuffle_seed"]) + cycle).shuffle(cycle_seeds)
        schedule.extend(cycle_seeds)
    return schedule


def _configure_torch(config: dict[str, Any]) -> None:
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(int(config["torch_threads"]))
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    if torch.get_num_threads() != 1:
        raise RuntimeError("M9 IPPO torch thread pin was not applied")


def _episode_summary(evidence: IPPOEpisodeEvidence) -> dict[str, Any]:
    metrics = evidence.coordination_metrics
    return {
        "seed": evidence.rollout.seed,
        "outcome": evidence.rollout.outcome,
        "tick": evidence.tick,
        "core_health": evidence.core_health,
        "transitions": len(evidence.rollout.transitions),
        "team_return": sum(evidence.shared_reward_components.values()),
        "team_idle_fraction": float(metrics["idle_fraction"]),
        "shared_reward_components": evidence.shared_reward_components,
        "individual_reward_totals": list(evidence.individual_reward_totals),
        "trace_sha256": evidence.trace_sha256,
        "model_state_sha256": evidence.model_state_sha256,
    }


def _aggregate(episodes: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not episodes:
        raise ValueError("cannot aggregate an empty M9 episode set")
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


def _selection_key(row: dict[str, Any]) -> tuple[float, ...]:
    return (
        float(row["wins"]),
        float(row["mean_team_return"]),
        float(row["mean_core_health"]),
        -float(row["mean_team_idle_fraction"]),
        -float(row["update"]),
    )


def select_checkpoint(
    rows: Sequence[dict[str, Any]], policy: dict[str, Any]
) -> int | None:
    """Return the eligible frontier index under ADR-0070's exact ranking."""

    eligible = [
        index
        for index, row in enumerate(rows)
        if int(row["wins"]) >= int(policy["minimum_wins"])
        and float(row["mean_team_idle_fraction"])
        < float(policy["maximum_mean_team_idle_fraction_exclusive"])
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda index: _selection_key(rows[index]))


def public_comparison(
    candidate: Sequence[dict[str, Any]],
    baseline: dict[str, Any],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    """Compute the frozen paired construction and MAPPO-authorization evidence."""

    candidate_by_seed = {int(item["seed"]): item for item in candidate}
    baseline_by_seed = {
        int(item["seed"]): item for item in baseline["episodes"]
    }
    if set(candidate_by_seed) != set(baseline_by_seed) or len(candidate_by_seed) != 40:
        raise ValueError("M9 public comparison seed pairing is invalid")
    bootstrap = protocol["paired_bootstrap"]
    resamples = int(bootstrap["iterations"])
    seed = int(bootstrap["seed"])

    def interval(name: str) -> dict[str, Any]:
        differences = []
        for episode_seed in sorted(candidate_by_seed):
            learned = candidate_by_seed[episode_seed]
            expert = baseline_by_seed[episode_seed]
            if name == "win_rate":
                value = float(learned["outcome"] == "win") - float(
                    expert["outcome"] == "win"
                )
            elif name == "team_return":
                value = float(learned["team_return"]) - float(
                    expert["team_return"]
                )
            elif name == "team_idle_fraction":
                value = float(learned["team_idle_fraction"]) - float(
                    expert["team_idle_fraction"]
                )
            else:
                raise ValueError(f"unsupported M9 comparison metric: {name}")
            differences.append(value)
        return bootstrap_interval(
            differences,
            seed=seed,
            resamples=resamples,
        )

    intervals = {
        name: interval(name)
        for name in ("win_rate", "team_return", "team_idle_fraction")
    }
    authorization = protocol["mappo_authorization"]
    checks = {
        "win_rate_lower_bound": (
            intervals["win_rate"]["ci95"][0]
            >= float(
                authorization[
                    "win_rate_difference_lower_bound_minimum"
                ]
            )
        ),
        "team_return_lower_bound": (
            intervals["team_return"]["ci95"][0]
            > float(
                authorization[
                    "team_return_difference_lower_bound_exclusive"
                ]
            )
        ),
        "team_idle_upper_bound": (
            intervals["team_idle_fraction"]["ci95"][1]
            <= float(
                authorization[
                    "team_idle_fraction_difference_upper_bound_maximum"
                ]
            )
        ),
    }
    return {
        "schema": "m9_ippo_public_comparison_v1",
        "direction": "candidate_minus_shared_expert",
        "paired_seeds": len(candidate_by_seed),
        "bootstrap": bootstrap,
        "candidate": _aggregate(candidate),
        "baseline": baseline["aggregate"],
        "differences": intervals,
        "mappo_checks": checks,
        "mappo_statistical_thresholds_passed": all(checks.values()),
        "confirmation_or_held_out_access": False,
    }


def _evaluate(
    env: RlServerProcess,
    model: SharedRecurrentSelector,
    config: dict[str, Any],
    seeds: Sequence[int],
) -> list[IPPOEpisodeEvidence]:
    model.eval()
    generator = torch.Generator().manual_seed(
        int(config["action_sampling_seed"])
    )
    return [
        rollout_ippo_episode(
            env,
            model,
            config,
            seed=int(seed),
            evaluation=True,
            action_generator=generator,
        )
        for seed in seeds
    ]


def _write_trace(path: Path, evidence: IPPOEpisodeEvidence) -> None:
    path.write_text(
        "".join(
            json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n"
            for item in evidence.trace
        ),
        encoding="utf-8",
    )


def _fresh_checkpoint_replay(
    checkpoint_path: Path,
    config: dict[str, Any],
    *,
    seed: int,
    java: str,
    port: int,
    model_seed: int,
    expected_config_sha256: str,
) -> IPPOEpisodeEvidence:
    model = SharedRecurrentSelector(model_seed)
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=float(config["learning_rate"]),
        eps=float(config["adam_epsilon"]),
    )
    load_ippo_checkpoint(
        checkpoint_path,
        model,
        optimizer,
        expected_config_sha256=expected_config_sha256,
    )
    with RlServerProcess(
        LaunchConfig(
            port=port,
            java=java,
            build_if_missing=False,
        )
    ) as env:
        env.handshake(f"{config['candidate_version']}-checkpoint-replay")
        return _evaluate(env, model, config, [seed])[0]


def _progress(
    output_dir: Path,
    *,
    update: int,
    train_episodes: int,
    selection: Sequence[dict[str, Any]],
    model: SharedRecurrentSelector,
) -> None:
    _write_json(
        output_dir / "progress.json",
        {
            "schema": "m9_ippo_training_progress_v1",
            "update": update,
            "train_episodes": train_episodes,
            "model_state_sha256": model_state_digest(model),
            "latest_dev": selection[-1],
            "complete": False,
        },
    )


def train(
    config_path: Path,
    output_dir: Path,
    preflight_path: Path,
    *,
    java: str,
    port: int,
) -> dict[str, Any]:
    """Execute one full, non-resumable exact M9 IPPO replica."""

    root = repo_root()
    config = load_ippo_config(config_path)
    contract = _candidate_contract(config)
    expected_config_sha256 = config_sha256(config)
    expected_protocol_sha256 = protocol_sha256(config)
    authority = validate_training_authority(preflight_path, root, config)
    _configure_torch(config)
    train_set, train_path = _load_seed_set(
        root,
        str(config["train_seed_set"]),
        split="train",
        expected_count=(
            2048
            if config["candidate_version"] == "m9-ippo-v3-diverse2048"
            else 64
        ),
        lower=TRAIN_MINIMUM,
        upper=TRAIN_MAXIMUM,
        config=config,
    )
    dev_set, dev_path = _load_seed_set(
        root,
        str(config["dev_seed_set"]),
        split="dev",
        expected_count=40,
        lower=DEV_MINIMUM,
        upper=DEV_MAXIMUM,
        config=config,
    )
    baseline_path = root / contract["baseline"]
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    protocol_path = root / str(config["public_evaluation_protocol"])
    if sha256_path(protocol_path) != expected_protocol_sha256:
        raise ValueError("M9 IPPO public protocol hash drifted")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if (
        protocol.get("seed_set") != config["dev_seed_set"]
        or protocol.get("held_out_access_authorized") is not False
        or protocol.get("confirmation_or_final_claim_authorized") is not False
        or (
            config["candidate_version"]
            in ("m9-ippo-v2-sequence16", "m9-ippo-v3-diverse2048")
            and protocol.get("baseline", {}).get("evidence")
            != contract["baseline"]
        )
    ):
        raise ValueError("M9 IPPO public protocol authority drifted")

    model = SharedRecurrentSelector(int(config["model_init_seed"]))
    initial_model_state_sha256 = model_state_digest(model)
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=float(config["learning_rate"]),
        eps=float(config["adam_epsilon"]),
    )
    action_generator = torch.Generator().manual_seed(
        int(config["action_sampling_seed"])
    )
    minibatch_generator = torch.Generator().manual_seed(
        int(config["minibatch_seed"])
    )
    schedule = training_seed_schedule(train_set["seeds"], config)
    try:
        output_dir.relative_to(root)
    except ValueError as error:
        raise ValueError("M9 IPPO output must remain inside the repository") from error
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("M9 IPPO output directory is not empty")
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = base_run_manifest(
        config_path,
        initial_model_state_sha256=initial_model_state_sha256,
        train_seed_set=_seed_identity(root, train_set, train_path),
        dev_seed_set=_seed_identity(root, dev_set, dev_path),
        baseline_path=baseline_path,
    )
    manifest["pretraining_gate"] = authority
    train_summaries: list[dict[str, Any]] = []
    optimizer_updates: list[dict[str, Any]] = []
    checkpoint_selection: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    dev_by_update: list[list[dict[str, Any]]] = []
    parent: str | None = None
    episodes_per_update = int(config["episodes_per_update"])
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
        env.handshake(f"{config['candidate_version']}-training")
        for cycle in range(int(config["training_cycles"])):
            first = cycle * episodes_per_update
            seeds = schedule[first : first + episodes_per_update]
            model.eval()
            batch = []
            for index, seed in enumerate(seeds):
                evidence = rollout_ippo_episode(
                    env,
                    model,
                    config,
                    seed=seed,
                    evaluation=False,
                    action_generator=action_generator,
                )
                batch.append(evidence.rollout)
                summary = _episode_summary(evidence)
                summary["cycle"] = cycle + 1
                summary["cycle_episode"] = index + 1
                train_summaries.append(summary)
                if (index + 1) % 8 == 0 or index + 1 == len(seeds):
                    print(
                        "M9 IPPO TRAIN "
                        f"update={cycle + 1}/32 "
                        f"episode={index + 1}/{len(seeds)} "
                        f"total={len(train_summaries)}/2048",
                        flush=True,
                    )
            model.train()
            update = cycle + 1
            metrics = ippo_update(
                model,
                optimizer,
                batch,
                config,
                minibatch_generator,
            )
            optimizer_updates.append({"update": update, **metrics})
            checkpoint_path = (
                output_dir / f"{contract['prefix']}-update-{update}.pt"
            )
            checkpoint = save_ippo_checkpoint(
                checkpoint_path,
                model,
                optimizer,
                update=update,
                parent_checkpoint_content_sha256=parent,
                config_sha256_value=expected_config_sha256,
            )
            checkpoints.append(checkpoint)
            parent = str(checkpoint["checkpoint_content_sha256"])

            dev_evidence = _evaluate(env, model, config, dev_seeds)
            dev_summaries = [_episode_summary(item) for item in dev_evidence]
            dev_by_update.append(dev_summaries)
            aggregate = _aggregate(dev_summaries)
            row = {
                "update": update,
                "checkpoint_content_sha256": checkpoint[
                    "checkpoint_content_sha256"
                ],
                "model_state_sha256": checkpoint["model_state_sha256"],
                "optimizer_state_sha256": checkpoint[
                    "optimizer_state_sha256"
                ],
                "parent_checkpoint_content_sha256": checkpoint[
                    "parent_checkpoint_content_sha256"
                ],
                **aggregate,
            }
            row["eligible"] = (
                row["wins"]
                >= int(config["checkpoint_selection"]["minimum_wins"])
                and row["mean_team_idle_fraction"]
                < float(
                    config["checkpoint_selection"][
                        "maximum_mean_team_idle_fraction_exclusive"
                    ]
                )
            )
            checkpoint_selection.append(row)
            _progress(
                output_dir,
                update=update,
                train_episodes=len(train_summaries),
                selection=checkpoint_selection,
                model=model,
            )
            print(
                "M9 IPPO DEV "
                f"update={update}/32 wins={row['wins']}/40 "
                f"return={row['mean_team_return']:.6f} "
                f"idle={row['mean_team_idle_fraction']:.6f} "
                f"eligible={row['eligible']}",
                flush=True,
            )

    manifest["optimizer_updates"] = optimizer_updates
    manifest["checkpoint_selection"] = checkpoint_selection
    manifest["train"] = train_summaries
    selected_index = select_checkpoint(
        checkpoint_selection, config["checkpoint_selection"]
    )
    if selected_index is None:
        manifest["construction_passed"] = False
        manifest["failure"] = "no checkpoint passed the public quality gate"
        manifest = finalize_run_manifest(manifest)
        atomic_write_manifest(
            output_dir / f"{contract['prefix']}-run.manifest.json",
            manifest,
        )
        _write_json(
            output_dir / "progress.json",
            {
                "schema": "m9_ippo_training_progress_v1",
                "update": len(optimizer_updates),
                "train_episodes": len(train_summaries),
                "complete": True,
                "construction_passed": False,
            },
        )
        return manifest

    selected = checkpoints[selected_index]
    selected_path = Path(selected["path"])
    payload = load_ippo_checkpoint(
        selected_path,
        model,
        optimizer,
        expected_config_sha256=expected_config_sha256,
    )
    selected_summary = {
        key: selected[key]
        for key in (
            "file_sha256",
            "checkpoint_content_sha256",
            "model_state_sha256",
            "optimizer_state_sha256",
            "update",
            "parent_checkpoint_content_sha256",
        )
    }
    selected_summary["path"] = str(selected_path.relative_to(root).as_posix())
    manifest["selected_checkpoint"] = selected_summary
    manifest["dev"] = dev_by_update[selected_index]
    manifest["public_comparison"] = public_comparison(
        manifest["dev"], baseline, protocol
    )

    verify_seed = dev_seeds[0]
    replays = [
        _fresh_checkpoint_replay(
            selected_path,
            config,
            seed=verify_seed,
            java=java,
            port=port,
            model_seed=model_seed,
            expected_config_sha256=expected_config_sha256,
        )
        for model_seed in (1, 2)
    ]
    if _episode_summary(replays[0]) != _episode_summary(replays[1]):
        raise RuntimeError("M9 selected checkpoint fresh replays diverged")
    trace_paths = [
        output_dir / "checkpoint-replay-a.jsonl",
        output_dir / "checkpoint-replay-b.jsonl",
    ]
    for trace_path, evidence in zip(trace_paths, replays, strict=True):
        _write_trace(trace_path, evidence)
    manifest["deterministic_checkpoint_verification"] = {
        "seed": verify_seed,
        "fresh_runs": 2,
        "trace_digest_a": replays[0].trace_sha256,
        "trace_digest_b": replays[1].trace_sha256,
        "bit_exact": True,
    }
    manifest["construction_passed"] = True
    manifest["mappo_statistical_thresholds_passed"] = manifest[
        "public_comparison"
    ]["mappo_statistical_thresholds_passed"]
    manifest["selected_checkpoint_payload_update"] = int(payload["update"])
    manifest = finalize_run_manifest(manifest)
    manifest_path = (
        output_dir / f"{contract['prefix']}-run.manifest.json"
    )
    atomic_write_manifest(manifest_path, manifest)
    atomic_write_manifest(
        selected_path.with_suffix(".manifest.json"), manifest
    )
    _write_json(
        output_dir / "progress.json",
        {
            "schema": "m9_ippo_training_progress_v1",
            "update": len(optimizer_updates),
            "train_episodes": len(train_summaries),
            "selected_update": selected["update"],
            "selected_checkpoint_content_sha256": selected[
                "checkpoint_content_sha256"
            ],
            "complete": True,
            "construction_passed": True,
        },
    )
    return manifest


def compare_replicas(
    first_manifest: Path,
    second_manifest: Path,
    *,
    output: Path | None = None,
) -> dict[str, Any]:
    """Require semantic, per-file-integrity, replay, and full-run identity."""

    root = repo_root()
    digest = compare_ippo_run_manifests(first_manifest, second_manifest)
    manifests = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (first_manifest, second_manifest)
    ]
    if manifests[0].get("construction_passed") != manifests[1].get(
        "construction_passed"
    ):
        raise RuntimeError("M9 replica construction outcomes diverged")
    selected = [manifest.get("selected_checkpoint") for manifest in manifests]
    if (selected[0] is None) != (selected[1] is None):
        raise RuntimeError("M9 replica checkpoint selection diverged")
    if bool(manifests[0].get("construction_passed")) != (
        selected[0] is not None
    ):
        raise ValueError("M9 replica construction/selection state is invalid")
    config_hashes = [
        manifest.get("source_config", {}).get("sha256")
        for manifest in manifests
    ]
    if (
        config_hashes[0] != config_hashes[1]
        or config_hashes[0]
        not in (
            IPPO_V1_CONFIG_SHA256,
            IPPO_V2_CONFIG_SHA256,
            IPPO_V3_CONFIG_SHA256,
        )
    ):
        raise ValueError("M9 replica config identity is invalid")
    result = {
        "schema": "m9_ippo_replica_comparison_v1",
        "full_run_reproducibility_digest": digest,
        "construction_passed": bool(manifests[0].get("construction_passed")),
        "exact_replica": True,
        "direct_checkpoint_lineage": False,
        "confirmation_or_held_out_access": False,
    }
    if selected[0] is not None:
        paths = [root / item["path"] for item in selected]
        file_hashes = [sha256_path(path) for path in paths]
        for checkpoint, file_hash in zip(selected, file_hashes, strict=True):
            if checkpoint["file_sha256"] != file_hash:
                raise ValueError("M9 replica checkpoint file integrity failed")
        payloads = []
        for index, path in enumerate(paths):
            model = SharedRecurrentSelector(index + 100)
            payloads.append(
                load_ippo_checkpoint(
                    path,
                    model,
                    expected_config_sha256=str(config_hashes[0]),
                )
            )
        content_hashes = [
            payload["checkpoint_content_sha256"] for payload in payloads
        ]
        if content_hashes[0] != content_hashes[1]:
            raise RuntimeError("M9 replica checkpoint content diverged")
        result.update(
            {
                "direct_checkpoint_lineage": True,
                "checkpoint_file_sha256_by_replica": file_hashes,
                "checkpoint_content_sha256": content_hashes[0],
                "selected_update": int(payloads[0]["update"]),
                "mappo_statistical_thresholds_passed": bool(
                    manifests[0].get(
                        "mappo_statistical_thresholds_passed"
                    )
                ),
            }
        )
    result["mappo_authorized"] = bool(
        result["construction_passed"]
        and result["exact_replica"]
        and result["direct_checkpoint_lineage"]
        and result.get("mappo_statistical_thresholds_passed")
    )
    if output is not None:
        _write_json(output, result)
    return result


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=root / "configs/training/m9-ippo-v1.json",
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--preflight",
        type=Path,
        default=root / "runs/m9-ippo-preflight.json",
    )
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--compare-runs", nargs=2, type=Path)
    parser.add_argument("--comparison-output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.compare_runs:
            result = compare_replicas(
                *(path.resolve() for path in args.compare_runs),
                output=(
                    args.comparison_output.resolve()
                    if args.comparison_output is not None
                    else None
                ),
            )
            print(
                "M9 IPPO REPLICAS OK "
                f"digest={result['full_run_reproducibility_digest'][:16]} "
                f"construction={result['construction_passed']}"
            )
            return 0 if result["construction_passed"] else 2
        if args.output_dir is None:
            parser.error("--output-dir is required for training")
        manifest = train(
            args.config.resolve(),
            args.output_dir.resolve(),
            args.preflight.resolve(),
            java=args.java,
            port=args.port,
        )
    except Exception as error:
        print(f"M9 IPPO FAIL: {error}", file=sys.stderr)
        return 1
    selected = manifest.get("selected_checkpoint")
    prefix = _candidate_contract(
        load_ippo_config(args.config.resolve())
    )["prefix"]
    manifest_path = args.output_dir / f"{prefix}-run.manifest.json"
    print(
        "M9 IPPO COMPLETE "
        f"construction={manifest['construction_passed']} "
        f"selected_update={selected['update'] if selected else 'none'} "
        f"manifest={manifest_path}"
    )
    return 0 if manifest["construction_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
