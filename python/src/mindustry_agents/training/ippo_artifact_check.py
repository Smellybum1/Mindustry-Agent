"""Live checkpoint reconstruction and manifest-lineage gate for M9 IPPO."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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
from mindustry_agents.training.ippo_artifacts import (
    atomic_write_manifest,
    base_run_manifest,
    compare_ippo_run_manifests,
    finalize_run_manifest,
    load_ippo_checkpoint,
    save_ippo_checkpoint,
)
from mindustry_agents.training.ippo_ppo import load_ippo_v1_config, sha256_path
from mindustry_agents.training.ippo_rollout import rollout_ippo_episode


def _seed_identity(root: Path, path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    return {
        "id": document["seed_set_id"],
        "version": document["seed_set_version"],
        "split": document["split"],
        "path": str(path.relative_to(root).as_posix()),
        "sha256": sha256_path(path),
    }


def _episode_summary(evidence) -> dict:
    return {
        "seed": evidence.rollout.seed,
        "outcome": evidence.rollout.outcome,
        "tick": evidence.tick,
        "core_health": evidence.core_health,
        "transitions": len(evidence.rollout.transitions),
        "shared_reward_components": evidence.shared_reward_components,
        "individual_reward_totals": list(evidence.individual_reward_totals),
        "trace_sha256": evidence.trace_sha256,
        "model_state_sha256": evidence.model_state_sha256,
    }


def _fresh_replay(
    model: SharedRecurrentSelector,
    config: dict,
    *,
    seed: int,
    java: str,
    port: int,
) -> dict:
    with RlServerProcess(LaunchConfig(port=port, java=java)) as env:
        env.handshake("m9-ippo-checkpoint-replay")
        evidence = rollout_ippo_episode(
            env,
            model,
            config,
            seed=seed,
            evaluation=True,
            action_generator=torch.Generator().manual_seed(
                int(config["action_sampling_seed"])
            ),
        )
    return _episode_summary(evidence)


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=root / "configs/training/m9-ippo-v1.json",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=root / "runs/m9-ippo-pretraining-update-0.pt",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "runs/m9-ippo-artifact-check.json",
    )
    parser.add_argument("--seed", type=int, default=18000000001)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--java", default="java")
    args = parser.parse_args(argv)
    try:
        config = load_ippo_v1_config(args.config)
        torch.set_num_threads(int(config["torch_threads"]))
        torch.use_deterministic_algorithms(True)
        initial = SharedRecurrentSelector(int(config["model_init_seed"]))
        optimizer = torch.optim.Adam(
            initial.parameters(),
            lr=float(config["learning_rate"]),
            eps=float(config["adam_epsilon"]),
        )
        checkpoint = save_ippo_checkpoint(
            args.checkpoint,
            initial,
            optimizer,
            update=0,
            parent_checkpoint_content_sha256=None,
        )
        models = []
        for seed in (1, 2):
            model = SharedRecurrentSelector(seed)
            loaded_optimizer = torch.optim.Adam(
                model.parameters(),
                lr=float(config["learning_rate"]),
                eps=float(config["adam_epsilon"]),
            )
            payload = load_ippo_checkpoint(
                args.checkpoint, model, loaded_optimizer
            )
            if payload["optimizer_state_sha256"] != checkpoint[
                "optimizer_state_sha256"
            ]:
                raise AssertionError("loaded optimizer lineage drifted")
            models.append(model)
        rows = [
            _fresh_replay(
                model,
                config,
                seed=args.seed,
                java=args.java,
                port=args.port,
            )
            for model in models
        ]
        if rows[0] != rows[1]:
            raise AssertionError("fresh checkpoint replays diverged")

        train_path = root / config["train_seed_set"]
        dev_path = root / config["dev_seed_set"]
        baseline_path = (
            root
            / "configs/evaluation/m9-ippo-v1-shared-expert-baseline.json"
        )
        manifest = base_run_manifest(
            args.config,
            initial_model_state_sha256=model_state_digest(initial),
            train_seed_set=_seed_identity(root, train_path),
            dev_seed_set=_seed_identity(root, dev_path),
            baseline_path=baseline_path,
        )
        manifest["selected_checkpoint"] = {
            key: checkpoint[key]
            for key in (
                "checkpoint_content_sha256",
                "model_state_sha256",
                "optimizer_state_sha256",
                "update",
                "parent_checkpoint_content_sha256",
            )
        }
        manifest["deterministic_checkpoint_verification"] = {
            "seed": args.seed,
            "fresh_runs": 2,
            "trace_digest_a": rows[0]["trace_sha256"],
            "trace_digest_b": rows[1]["trace_sha256"],
            "bit_exact": True,
        }
        manifest = finalize_run_manifest(manifest)
        first_manifest = args.checkpoint.with_suffix(".manifest-a.json")
        second_manifest = args.checkpoint.with_suffix(".manifest-b.json")
        atomic_write_manifest(first_manifest, manifest)
        atomic_write_manifest(second_manifest, manifest)
        reproducibility_digest = compare_ippo_run_manifests(
            first_manifest, second_manifest
        )
        report = {
            "schema": "m9_ippo_artifact_check_v1",
            "config": str(args.config.relative_to(root).as_posix()),
            "checkpoint": {
                key: checkpoint[key]
                for key in (
                    "checkpoint_content_sha256",
                    "model_state_sha256",
                    "optimizer_state_sha256",
                    "update",
                    "parent_checkpoint_content_sha256",
                )
            },
            "fresh_checkpoint_replays_equal": True,
            "episode": rows[0],
            "manifest_reproducibility_digest": reproducibility_digest,
            "manifest_twins_equal": True,
            "confirmation_or_held_out_access": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception as error:
        print(f"M9 IPPO ARTIFACT FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "M9 IPPO ARTIFACT OK "
        f"checkpoint={checkpoint['checkpoint_content_sha256'][:16]} "
        f"trace={rows[0]['trace_sha256'][:16]} "
        f"manifest={reproducibility_digest[:16]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
