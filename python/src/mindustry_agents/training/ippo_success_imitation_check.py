"""Emit exact-commit evidence for ADR-0083's success-imitation boundary."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import torch

from mindustry_agents.process.launcher import repo_root
from mindustry_agents.training.ippo import (
    SharedRecurrentSelector,
    model_state_digest,
)
from mindustry_agents.training.ippo_ppo import (
    IPPO_V4_CONFIG_SHA256,
    IPPO_V4_PROTOCOL_SHA256,
    IPPO_V5_CONFIG_SHA256,
    IPPO_V5_PROTOCOL_SHA256,
    IPPOEpisodeRollout,
    IPPOTransition,
    ippo_update,
    load_ippo_v4_config,
    load_ippo_v5_config,
    sha256_path,
)


def _json_digest(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalized_v5_config(config: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(config)
    result["schema"] = "ippo_training_config_v4"
    result["candidate_version"] = "m9-ippo-v4-entropy-anneal"
    result["parent_candidate_version"] = "m9-ippo-v3-diverse2048"
    result["sole_learning_change"] = (
        "linear_entropy_coefficient_anneal_0.02_to_0.0"
    )
    result["public_evaluation_protocol"] = (
        "configs/evaluation/m9-ippo-v4-entropy-anneal-public-protocol.json"
    )
    result.pop("success_conditioned_self_imitation")
    result["optimizer_ppo"].pop("success_conditioned_self_imitation")
    return result


def _normalized_v5_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(protocol)
    result["schema"] = "m9_ippo_public_protocol_v4"
    result["candidate_version"] = "m9-ippo-v4-entropy-anneal"
    return result


def _transition(
    model: SharedRecurrentSelector,
    *,
    agent_id: int,
    action: int,
    policy_loss_mask: bool,
) -> IPPOTransition:
    candidates = torch.zeros((8, 37))
    candidates[:, 0] = agent_id / 10
    scalars = torch.zeros(160)
    scalars[0] = agent_id / 10
    present = torch.ones(8, dtype=torch.bool)
    action_mask = torch.ones(10, dtype=torch.bool)
    hidden = torch.zeros(64)
    with torch.no_grad():
        _, logits, value, _ = model(
            candidates[None],
            scalars[None],
            present[None],
            action_mask[None],
            torch.tensor([agent_id]),
            hidden[None],
        )
        old_log_prob = torch.log_softmax(logits[0], dim=-1)[action]
    return IPPOTransition(
        agent_id=agent_id,
        candidates=candidates,
        scalars=scalars,
        candidate_present=present,
        action_mask=action_mask,
        hidden_input=hidden,
        action=action,
        old_log_prob=float(old_log_prob),
        old_value=float(value[0]),
        team_reward=1.0,
        individual_reward=-0.01 * agent_id,
        advanced_ticks=60,
        done=True,
        policy_loss_mask=policy_loss_mask,
        recurrent_reset=True,
    )


def _fixture(model: SharedRecurrentSelector) -> list[IPPOEpisodeRollout]:
    return [
        IPPOEpisodeRollout(
            18000000001,
            "win",
            (
                _transition(
                    model,
                    agent_id=0,
                    action=0,
                    policy_loss_mask=True,
                ),
                _transition(
                    model,
                    agent_id=1,
                    action=1,
                    policy_loss_mask=False,
                ),
            ),
        ),
        IPPOEpisodeRollout(
            18000000002,
            "loss",
            (
                _transition(
                    model,
                    agent_id=2,
                    action=2,
                    policy_loss_mask=True,
                ),
            ),
        ),
    ]


def _optimizer_probe(config: dict[str, Any]) -> dict[str, Any]:
    replicas = []
    for _ in range(2):
        model = SharedRecurrentSelector(int(config["model_init_seed"]))
        optimizer = torch.optim.Adam(
            model.parameters(),
            lr=float(config["learning_rate"]),
            eps=float(config["adam_epsilon"]),
        )
        metrics = ippo_update(
            model,
            optimizer,
            _fixture(model),
            config,
            torch.Generator().manual_seed(int(config["minibatch_seed"])),
            update_number=16,
        )
        replicas.append(
            {
                "metrics": metrics,
                "model_state_sha256": model_state_digest(model),
            }
        )
    if replicas[0] != replicas[1]:
        raise ValueError("M9 IPPO v5 optimizer probe is not exact")
    metrics = replicas[0]["metrics"]
    if (
        metrics["success_imitation_coefficient"] != 0.02
        or metrics["success_imitation_qualifying_episodes"] != 1.0
        or metrics["success_imitation_qualifying_transitions"] != 1.0
        or metrics["success_imitation_active_minibatches"] != 8.0
        or metrics["success_imitation_mean_active_minibatch_loss"] <= 0.0
    ):
        raise ValueError("M9 IPPO v5 success filter or telemetry drifted")
    return {
        "independent_runs_exact": True,
        "metrics": metrics,
        "model_state_sha256": replicas[0]["model_state_sha256"],
        "probe_sha256": _json_digest(replicas[0]),
    }


def build_report(root: Path) -> dict[str, Any]:
    """Return current exact-commit v5 inheritance and optimizer evidence."""

    torch.set_num_threads(1)
    v4_path = root / "configs/training/m9-ippo-v4-entropy-anneal.json"
    v5_path = root / "configs/training/m9-ippo-v5-success-imitation.json"
    v4 = load_ippo_v4_config(v4_path)
    v5 = load_ippo_v5_config(v5_path)
    if _normalized_v5_config(v5) != v4:
        raise ValueError("M9 IPPO v5 changed more than success imitation")

    v4_protocol_path = (
        root
        / "configs/evaluation/m9-ippo-v4-entropy-anneal-public-protocol.json"
    )
    v5_protocol_path = (
        root
        / "configs/evaluation/m9-ippo-v5-success-imitation-public-protocol.json"
    )
    if (
        sha256_path(v4_protocol_path) != IPPO_V4_PROTOCOL_SHA256
        or sha256_path(v5_protocol_path) != IPPO_V5_PROTOCOL_SHA256
    ):
        raise ValueError("M9 IPPO v5 protocol hash drifted")
    v4_protocol = json.loads(v4_protocol_path.read_text(encoding="utf-8"))
    v5_protocol = json.loads(v5_protocol_path.read_text(encoding="utf-8"))
    if _normalized_v5_protocol(v5_protocol) != v4_protocol:
        raise ValueError("M9 IPPO v5 public protocol changed semantically")

    optimizer = _optimizer_probe(v5)
    return {
        "schema": "m9_ippo_v5_success_imitation_check_v1",
        "candidate_version": "m9-ippo-v5-success-imitation",
        "implementation_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
        ).strip(),
        "config_sha256": IPPO_V5_CONFIG_SHA256,
        "protocol_sha256": IPPO_V5_PROTOCOL_SHA256,
        "parent_config_sha256": IPPO_V4_CONFIG_SHA256,
        "parent_protocol_sha256": IPPO_V4_PROTOCOL_SHA256,
        "semantic_inheritance_exact": True,
        "optimizer": optimizer,
        "confirmation_or_held_out_access": False,
        "all_passed": True,
    }


def main() -> int:
    root = repo_root()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "runs/m9-ippo-v5-success-imitation-check.json",
    )
    args = parser.parse_args()
    report = build_report(root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(
        "M9 IPPO V5 SUCCESS IMITATION OK "
        f"probe={report['optimizer']['probe_sha256'][:16]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
