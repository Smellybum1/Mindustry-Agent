"""Emit exact-commit evidence for ADR-0087's success-margin boundary."""

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
    IPPO_V6_CONFIG_SHA256,
    IPPO_V6_PROTOCOL_SHA256,
    IPPOEpisodeRollout,
    IPPOTransition,
    ippo_update,
    load_ippo_v4_config,
    load_ippo_v6_config,
    sha256_path,
)


def _json_digest(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalized_v6_config(config: dict[str, Any]) -> dict[str, Any]:
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
    result.pop("success_conditioned_margin_alignment")
    result["optimizer_ppo"].pop("success_conditioned_margin_alignment")
    return result


def _normalized_v6_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(protocol)
    result["schema"] = "m9_ippo_public_protocol_v4"
    result["candidate_version"] = "m9-ippo-v4-entropy-anneal"
    return result


def _transition(
    model: SharedRecurrentSelector,
    *,
    agent_id: int,
    action: int | None,
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
        selected_action = (
            int(torch.argmin(logits[0]).item()) if action is None else action
        )
        old_log_prob = torch.log_softmax(logits[0], dim=-1)[selected_action]
    return IPPOTransition(
        agent_id=agent_id,
        candidates=candidates,
        scalars=scalars,
        candidate_present=present,
        action_mask=action_mask,
        hidden_input=hidden,
        action=selected_action,
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
                    action=None,
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
        raise ValueError("M9 IPPO v6 optimizer probe is not exact")
    metrics = replicas[0]["metrics"]
    if (
        metrics["success_margin_coefficient"] != 0.02
        or metrics["success_margin_target"] != 0.1
        or metrics["success_margin_qualifying_episodes"] != 1.0
        or metrics["success_margin_qualifying_transitions"] != 1.0
        or metrics["success_margin_active_minibatches"] != 8.0
        or metrics["success_margin_mean_active_minibatch_loss"] <= 0.0
    ):
        raise ValueError("M9 IPPO v6 success filter or telemetry drifted")
    return {
        "independent_runs_exact": True,
        "metrics": metrics,
        "model_state_sha256": replicas[0]["model_state_sha256"],
        "probe_sha256": _json_digest(replicas[0]),
    }


def build_report(root: Path) -> dict[str, Any]:
    """Return current exact-commit v6 inheritance and optimizer evidence."""

    torch.set_num_threads(1)
    v4_path = root / "configs/training/m9-ippo-v4-entropy-anneal.json"
    v6_path = root / "configs/training/m9-ippo-v6-success-margin.json"
    v4 = load_ippo_v4_config(v4_path)
    v6 = load_ippo_v6_config(v6_path)
    if _normalized_v6_config(v6) != v4:
        raise ValueError("M9 IPPO v6 changed more than success margin")

    v4_protocol_path = (
        root
        / "configs/evaluation/m9-ippo-v4-entropy-anneal-public-protocol.json"
    )
    v6_protocol_path = (
        root
        / "configs/evaluation/m9-ippo-v6-success-margin-public-protocol.json"
    )
    if (
        sha256_path(v4_protocol_path) != IPPO_V4_PROTOCOL_SHA256
        or sha256_path(v6_protocol_path) != IPPO_V6_PROTOCOL_SHA256
    ):
        raise ValueError("M9 IPPO v6 protocol hash drifted")
    v4_protocol = json.loads(v4_protocol_path.read_text(encoding="utf-8"))
    v6_protocol = json.loads(v6_protocol_path.read_text(encoding="utf-8"))
    if _normalized_v6_protocol(v6_protocol) != v4_protocol:
        raise ValueError("M9 IPPO v6 public protocol changed semantically")

    optimizer = _optimizer_probe(v6)
    return {
        "schema": "m9_ippo_v6_success_margin_check_v1",
        "candidate_version": "m9-ippo-v6-success-margin",
        "implementation_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
        ).strip(),
        "config_sha256": IPPO_V6_CONFIG_SHA256,
        "protocol_sha256": IPPO_V6_PROTOCOL_SHA256,
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
        default=root / "runs/m9-ippo-v6-success-margin-check.json",
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
        "M9 IPPO V6 SUCCESS MARGIN OK "
        f"probe={report['optimizer']['probe_sha256'][:16]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
