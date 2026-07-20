"""M8.3 event-driven collector throughput with shadow selector inference.

The probe follows the real supervised multi-JVM path, submits the existing
adaptive scripted team actions, and stops only at the server's decision events.
A frozen, seeded tensor graph matching the M8 v1 dimensions runs in shadow mode
at every boundary. Its logits never affect actions; selector behavior and
rewards remain M8.4 work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

import torch
from torch import nn

from mindustry_agents import ENGINE_COMMIT, ENGINE_TAG, PROTOCOL_VERSION
from mindustry_agents.env.vector import VectorCollector
from mindustry_agents.policies.scripted import GreedyUtilityPolicy
from mindustry_agents.process.launcher import DEFAULT_PORT, repo_root
from mindustry_agents.process.supervisor import ProcessSupervisor, SupervisorConfig

REAL_TIME_TPS = 60.0
GATE_REALTIME_MULTIPLE = 50.0
DEFAULT_MAX_CHUNK = 600
MAX_BOUNDARY_BATCHES = 5000
ARC_HASH = "208a754044"


class ShadowSelectorProbe(nn.Module):
    """Frozen M8-shape inference graph used only for throughput measurement."""

    def __init__(self, seed: int = 8003):
        super().__init__()
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            self.candidate_encoder = nn.Sequential(
                nn.Linear(37, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh()
            )
            self.scalar_encoder = nn.Sequential(
                nn.Linear(56, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh()
            )
            self.select_head = nn.Sequential(
                nn.Linear(128, 64), nn.Tanh(), nn.Linear(64, 1)
            )
            self.special_head = nn.Sequential(
                nn.Linear(64, 64), nn.Tanh(), nn.Linear(64, 2)
            )
            self.critic = nn.Sequential(
                nn.Linear(128, 64), nn.Tanh(), nn.Linear(64, 1)
            )
        self.eval()
        for parameter in self.parameters():
            parameter.requires_grad_(False)

    def forward(
        self,
        candidates: torch.Tensor,
        scalars: torch.Tensor,
        candidate_present: torch.Tensor,
        action_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        encoded_candidates = self.candidate_encoder(candidates)
        encoded_scalars = self.scalar_encoder(scalars)
        repeated_scalars = encoded_scalars[:, None, :].expand(-1, 8, -1)
        select_logits = self.select_head(
            torch.cat((encoded_candidates, repeated_scalars), dim=-1)
        ).squeeze(-1)
        logits = torch.cat((select_logits, self.special_head(encoded_scalars)), dim=-1)
        logits = logits.masked_fill(~action_mask, torch.finfo(logits.dtype).min)

        weights = candidate_present.to(encoded_candidates.dtype).unsqueeze(-1)
        pooled = (encoded_candidates * weights).sum(dim=1) / weights.sum(
            dim=1
        ).clamp_min(1.0)
        value = self.critic(torch.cat((encoded_scalars, pooled), dim=-1)).squeeze(-1)
        return logits, value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_evidence(root: Path) -> dict[str, Any]:
    git_executable = os.environ.get("M8_GIT", "git")
    git_root = os.environ.get("M8_GIT_ROOT", str(root))

    def run(*args: str) -> str:
        return subprocess.run(
            [git_executable, "-C", git_root, *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    status = run("status", "--short").splitlines()
    return {
        "commit": run("rev-parse", "HEAD"),
        "dirty": bool(status),
        "status": status,
        "executable": git_executable,
    }


def _java_evidence(java: str) -> str:
    result = subprocess.run(
        [java, "-version"], check=True, capture_output=True, text=True
    )
    return (result.stderr or result.stdout).strip()


def _inference_inputs(batch: int) -> tuple[torch.Tensor, ...]:
    candidates = torch.zeros((batch, 8, 37), dtype=torch.float32)
    scalars = torch.zeros((batch, 56), dtype=torch.float32)
    candidate_present = torch.ones((batch, 8), dtype=torch.bool)
    action_mask = torch.ones((batch, 10), dtype=torch.bool)
    return candidates, scalars, candidate_present, action_mask


def _shadow_inference(
    probe: ShadowSelectorProbe, inputs: tuple[torch.Tensor, ...]
) -> tuple[float, str]:
    start = time.perf_counter()
    with torch.inference_mode():
        logits, values = probe(*inputs)
        choices = logits.argmax(dim=-1)
    elapsed = time.perf_counter() - start
    payload = torch.cat((logits.flatten(), values, choices.to(values.dtype))).numpy().tobytes()
    return elapsed, hashlib.sha256(payload).hexdigest()


def _actions(
    policies: list[GreedyUtilityPolicy], resets_or_steps: list[Any]
) -> list[list[dict[str, Any]]]:
    bundles = []
    for policy, result in zip(policies, resets_or_steps):
        bundles.append(policy.actions(result.observations, result.info["action_masks"]))
    return bundles


def bench_pool(
    pool_size: int,
    *,
    java: str,
    base_port: int,
    episodes: int,
    seed: int,
    max_chunk: int,
    warmup_inferences: int,
    log_dir: Path,
) -> dict[str, Any]:
    """Run complete same-seed episodes through one supervised pool."""

    probe = ShadowSelectorProbe()
    inputs = _inference_inputs(pool_size)
    for _ in range(warmup_inferences):
        _shadow_inference(probe, inputs)

    config = SupervisorConfig(
        pool_size=pool_size,
        base_port=base_port,
        java=java,
        agent_count=3,
        seeds=[seed] * pool_size,
        step_timeout_s=120.0,
        log_dir=log_dir / f"pool-{pool_size}",
        build_if_missing=False,
    )
    total_ticks = 0
    step_batches = 0
    decision_event_batches = 0
    horizon_batches = 0
    decision_reasons: dict[str, int] = {}
    inference_samples = 0
    inference_s = 0.0
    inference_digests: list[str] = []
    final_hashes: list[str] = []
    outcomes: list[str] = []

    with ProcessSupervisor(config) as supervisor:
        collector = VectorCollector(supervisor)
        start = time.perf_counter()
        for episode_index in range(episodes):
            resets = collector.reset_all(seed=seed)
            if len(resets) != pool_size:
                raise RuntimeError("reset result count does not match pool size")
            policies = [GreedyUtilityPolicy() for _ in range(pool_size)]
            bundles = _actions(policies, resets)
            current_tick = int(resets[0].info["tick"])
            win_tick = int(resets[0].info["metadata"]["win_tick"])

            elapsed, digest = _shadow_inference(probe, inputs)
            inference_s += elapsed
            inference_digests.append(digest)
            inference_samples += pool_size

            for _ in range(MAX_BOUNDARY_BATCHES):
                requested_ticks = min(max_chunk, max(1, win_tick - current_tick))
                result = collector.step_all(
                    bundles,
                    ticks=requested_ticks,
                    stop_on_decision_event=True,
                )
                step_batches += 1
                total_ticks += result.ticks_advanced
                if len(result.outcomes) != pool_size:
                    raise RuntimeError("step result count does not match pool size")
                if any(outcome.crashed for outcome in result.outcomes):
                    raise RuntimeError("collector child crashed during throughput gate")

                state_hashes = [str(outcome.info["state_hash"]) for outcome in result.outcomes]
                if len(set(state_hashes)) != 1:
                    raise RuntimeError(
                        f"same-seed pool diverged in episode {episode_index}: {state_hashes}"
                    )
                current_tick = int(result.outcomes[0].info["tick"])

                done = [
                    all(outcome.terminations) or all(outcome.truncations)
                    for outcome in result.outcomes
                ]
                if any(done) and not all(done):
                    raise RuntimeError(
                        f"same-seed pool terminated on different boundaries: {done}"
                    )
                for policy, outcome in zip(policies, result.outcomes):
                    policy.observe_action_results(outcome.info["action_results"])
                if all(done):
                    final_hashes.extend(state_hashes)
                    outcomes.extend(str(item.info["outcome"]) for item in result.outcomes)
                    break
                decision = result.outcomes[0].info["decision_boundary"]
                if bool(decision.get("triggered", False)):
                    decision_event_batches += 1
                    for reason in decision.get("reasons", []):
                        key = str(reason)
                        decision_reasons[key] = decision_reasons.get(key, 0) + 1
                    elapsed, digest = _shadow_inference(probe, inputs)
                    inference_s += elapsed
                    inference_digests.append(digest)
                    inference_samples += pool_size
                else:
                    horizon_batches += 1
                bundles = _actions(policies, result.outcomes)
            else:
                raise RuntimeError("event-driven collector exceeded boundary guard")
        wall_s = time.perf_counter() - start

    aggregate_tps = total_ticks / wall_s
    realtime_multiple = aggregate_tps / REAL_TIME_TPS
    if set(outcomes) != {"win"}:
        raise RuntimeError(f"throughput gate expected scripted wins, got {outcomes}")
    return {
        "pool_size": pool_size,
        "episodes_per_jvm": episodes,
        "episodes": len(outcomes),
        "max_chunk_ticks": max_chunk,
        "outcomes": {"win": outcomes.count("win")},
        "advanced_ticks": total_ticks,
        "step_batches": step_batches,
        "decision_event_batches": decision_event_batches,
        "horizon_batches": horizon_batches,
        "decision_reasons": dict(sorted(decision_reasons.items())),
        "inference_samples": inference_samples,
        "wall_s": wall_s,
        "aggregate_ticks_per_s": aggregate_tps,
        "realtime_multiple": realtime_multiple,
        "per_jvm_realtime_multiple": realtime_multiple / pool_size,
        "inference_total_ms": inference_s * 1000.0,
        "inference_mean_batch_ms": inference_s * 1000.0 / (inference_samples / pool_size),
        "inference_mean_sample_ms": inference_s * 1000.0 / inference_samples,
        "inference_digest": hashlib.sha256("".join(inference_digests).encode()).hexdigest(),
        "final_state_hash": final_hashes[0],
        "same_seed_hashes_identical": len(set(final_hashes)) == 1,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M8.3 event-driven throughput gate")
    parser.add_argument("--java", default="java")
    parser.add_argument("--base-port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--pools", type=int, nargs="+", default=[1, 2, 4])
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--max-chunk", type=int, default=DEFAULT_MAX_CHUNK)
    parser.add_argument("--warmup-inferences", type=int, default=20)
    parser.add_argument(
        "--output", type=Path, default=repo_root() / "runs" / "m8-throughput.json"
    )
    args = parser.parse_args(argv)
    if args.episodes < 1:
        parser.error("--episodes must be >= 1")
    if args.max_chunk < 1:
        parser.error("--max-chunk must be >= 1")
    if any(pool not in {1, 2, 4} for pool in args.pools):
        parser.error("--pools entries must be 1, 2, or 4")

    try:
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    root = repo_root()
    lock = root / "python" / "requirements-rl-linux-py312.lock"
    run_dir = args.output.resolve().parent
    run_dir.mkdir(parents=True, exist_ok=True)
    print("== M8.3 event-driven training throughput ==")
    print(f"pools={args.pools} episodes_per_jvm={args.episodes} seed={args.seed}")

    results = []
    for offset, pool_size in enumerate(args.pools):
        result = bench_pool(
            pool_size,
            java=args.java,
            base_port=args.base_port + offset * 20,
            episodes=args.episodes,
            seed=args.seed,
            max_chunk=args.max_chunk,
            warmup_inferences=args.warmup_inferences,
            log_dir=run_dir / "m8-throughput-children",
        )
        results.append(result)
        print(
            f"  {pool_size} JVM: {result['aggregate_ticks_per_s']:,.0f} ticks/s, "
            f"{result['realtime_multiple']:.1f}x real-time, "
            f"inference={result['inference_mean_batch_ms']:.3f} ms/batch"
        )

    four = next((result for result in results if result["pool_size"] == 4), None)
    gate_pass = four is not None and four["realtime_multiple"] >= GATE_REALTIME_MULTIPLE
    manifest = {
        "schema": "m8_training_throughput_v1",
        "engine": {"tag": ENGINE_TAG, "commit": ENGINE_COMMIT, "arc": ARC_HASH},
        "protocol_version": PROTOCOL_VERSION,
        "scenario": {"id": "bootstrap-defense-v0", "version": 1, "seed": args.seed},
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "torch": torch.__version__,
        "torch_threads": torch.get_num_threads(),
        "device": "cpu",
        "java": _java_evidence(args.java),
        "lockfile": str(lock.relative_to(root)),
        "lock_sha256": _sha256(lock),
        "git": _git_evidence(root),
        "shadow_inference_only": True,
        "gate": {"required_realtime_multiple": GATE_REALTIME_MULTIPLE, "pass": gate_pass},
        "results": results,
    }
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"manifest={args.output}")
    print("M8-THROUGHPUT", "OK" if gate_pass else "FAILED")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
