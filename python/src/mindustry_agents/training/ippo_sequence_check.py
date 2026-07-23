"""Cross-process deterministic optimizer/checkpoint gate for ADR-0073."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import torch

from mindustry_agents.process.launcher import repo_root
from mindustry_agents.training.ippo import (
    AGENT_COUNT,
    SharedRecurrentSelector,
    model_state_digest,
)
from mindustry_agents.training.ippo_artifacts import (
    load_ippo_checkpoint,
    save_ippo_checkpoint,
)
from mindustry_agents.training.ippo_ppo import (
    IPPO_V2_CONFIG_SHA256,
    IPPOEpisodeRollout,
    IPPOTransition,
    ippo_sequence_windows,
    ippo_update,
    load_ippo_v2_config,
    sha256_path,
)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _synthetic_episodes(
    model: SharedRecurrentSelector,
) -> tuple[IPPOEpisodeRollout, ...]:
    episodes = []
    for episode_index in range(2):
        hidden = torch.zeros((AGENT_COUNT, 64))
        transitions = []
        for boundary in range(5):
            for agent_id in range(AGENT_COUNT):
                candidates = torch.zeros((8, 37))
                candidates[:, 0] = (
                    episode_index + boundary / 10 + agent_id / 100
                )
                candidates[:, 1] = torch.arange(8) / 8
                scalars = torch.zeros(160)
                scalars[0] = episode_index
                scalars[1] = boundary / 5
                scalars[2] = agent_id / 3
                present = torch.ones(8, dtype=torch.bool)
                mask = torch.ones(10, dtype=torch.bool)
                forced = (
                    episode_index == 1
                    and boundary == 2
                    and agent_id == 2
                )
                action = 9 if forced else (boundary + agent_id) % 8
                if forced:
                    mask[9] = False
                hidden_input = hidden[agent_id].detach().clone()
                with torch.no_grad():
                    _, logits, value, next_hidden = model(
                        candidates[None],
                        scalars[None],
                        present[None],
                        mask[None],
                        torch.tensor([agent_id]),
                        hidden_input[None],
                    )
                hidden[agent_id] = next_hidden[0]
                transitions.append(
                    IPPOTransition(
                        agent_id=agent_id,
                        candidates=candidates,
                        scalars=scalars,
                        candidate_present=present,
                        action_mask=mask,
                        hidden_input=hidden_input,
                        action=action,
                        old_log_prob=float(
                            torch.log_softmax(logits[0], dim=-1)[action]
                        ),
                        old_value=float(value[0]),
                        team_reward=1.0 + boundary / 10,
                        individual_reward=-0.01 * agent_id,
                        advanced_ticks=30 + boundary,
                        done=boundary == 4,
                        policy_loss_mask=not forced,
                        recurrent_reset=boundary == 0,
                    )
                )
        episodes.append(
            IPPOEpisodeRollout(
                seed=18_500_000_001 + episode_index,
                outcome="win",
                transitions=tuple(transitions),
            )
        )
    return tuple(episodes)


def _worker(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = load_ippo_v2_config(config_path)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(int(config["torch_threads"]))
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    model = SharedRecurrentSelector(int(config["model_init_seed"]))
    initial = model_state_digest(model)
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=float(config["learning_rate"]),
        eps=float(config["adam_epsilon"]),
    )
    episodes = _synthetic_episodes(model)
    windows = ippo_sequence_windows(
        episodes,
        sequence_length=int(
            config["recurrent_backpropagation"]["sequence_length"]
        ),
    )
    metrics = ippo_update(
        model,
        optimizer,
        episodes,
        config,
        torch.Generator().manual_seed(int(config["minibatch_seed"])),
    )
    checkpoint = save_ippo_checkpoint(
        output_dir / "sequence-checkpoint.pt",
        model,
        optimizer,
        update=1,
        parent_checkpoint_content_sha256=None,
        config_sha256_value=IPPO_V2_CONFIG_SHA256,
    )
    loaded = SharedRecurrentSelector(1)
    loaded_optimizer = torch.optim.Adam(
        loaded.parameters(),
        lr=float(config["learning_rate"]),
        eps=float(config["adam_epsilon"]),
    )
    payload = load_ippo_checkpoint(
        Path(checkpoint["path"]),
        loaded,
        loaded_optimizer,
        expected_config_sha256=IPPO_V2_CONFIG_SHA256,
    )
    if model_state_digest(loaded) != model_state_digest(model):
        raise AssertionError("M9 v2 loaded checkpoint model drifted")
    result = {
        "initial_model_state_sha256": initial,
        "final_model_state_sha256": model_state_digest(model),
        "episodes": len(episodes),
        "transitions": sum(len(item.transitions) for item in episodes),
        "actor_transitions": sum(
            item.policy_loss_mask
            for episode in episodes
            for item in episode.transitions
        ),
        "critic_only_transitions": sum(
            not item.policy_loss_mask
            for episode in episodes
            for item in episode.transitions
        ),
        "recurrent_resets": sum(
            item.recurrent_reset
            for episode in episodes
            for item in episode.transitions
        ),
        "window_lengths": [len(window) for window in windows],
        "metrics": metrics,
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
        "checkpoint_file_integrity_verified": (
            checkpoint["file_sha256"]
            == sha256_path(Path(checkpoint["path"]))
        ),
        "loaded_checkpoint_content_sha256": payload[
            "checkpoint_content_sha256"
        ],
    }
    _write_json(output_dir / "worker.json", result)
    return result


def _project_commit(root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
    ).strip()


def _parent(config_path: Path, output: Path) -> dict[str, Any]:
    root = repo_root()
    with tempfile.TemporaryDirectory(
        dir=root / "runs", prefix="m9-v2-sequence-check-"
    ) as directory:
        temporary = Path(directory)
        worker_paths = []
        for label in ("a", "b"):
            worker_dir = temporary / label
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mindustry_agents.training.ippo_sequence_check",
                    "--config",
                    str(config_path),
                    "--worker-output",
                    str(worker_dir),
                ],
                cwd=root,
                text=True,
                capture_output=True,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"M9 v2 sequence worker {label} failed: {result.stderr}"
                )
            worker_paths.append(worker_dir / "worker.json")
        workers = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in worker_paths
        ]
    if workers[0] != workers[1]:
        raise RuntimeError("M9 v2 independent sequence workers diverged")
    worker = workers[0]
    report = {
        "schema": "m9_ippo_v2_sequence_check_v1",
        "candidate_version": "m9-ippo-v2-sequence16",
        "implementation_commit": _project_commit(root),
        "config_sha256": IPPO_V2_CONFIG_SHA256,
        "processes": 2,
        "independent_processes_exact": True,
        "optimizer_and_checkpoint_exact": True,
        "synthetic_public_free_evidence": {
            key: worker[key]
            for key in (
                "episodes",
                "transitions",
                "actor_transitions",
                "critic_only_transitions",
                "recurrent_resets",
                "window_lengths",
            )
        },
        "initial_model_state_sha256": worker[
            "initial_model_state_sha256"
        ],
        "final_model_state_sha256": worker["final_model_state_sha256"],
        "optimizer_metrics": worker["metrics"],
        "checkpoint": {
            **worker["checkpoint"],
            "file_integrity_verified_in_both_processes": worker[
                "checkpoint_file_integrity_verified"
            ],
            "raw_serializer_hash_excluded_from_replica_identity": True,
        },
        "confirmation_or_held_out_access": False,
    }
    _write_json(output, report)
    return report


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=root / "configs/training/m9-ippo-v2-sequence16.json",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker-output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.worker_output is not None:
            _worker(args.config.resolve(), args.worker_output.resolve())
            return 0
        output = (
            args.output.resolve()
            if args.output is not None
            else root / "runs/m9-ippo-v2-sequence-check.json"
        )
        report = _parent(args.config.resolve(), output)
    except Exception as error:
        print(f"M9 IPPO V2 SEQUENCE FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "M9 IPPO V2 SEQUENCE OK "
        f"model={report['final_model_state_sha256'][:16]} "
        f"checkpoint={report['checkpoint']['checkpoint_content_sha256'][:16]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
