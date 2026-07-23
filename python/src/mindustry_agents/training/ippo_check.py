"""Real-JVM parity gate for the M9 all-seat learned action boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from mindustry_agents.policies.scripted import GreedyUtilityPolicy
from mindustry_agents.process.launcher import DEFAULT_PORT, LaunchConfig, RlServerProcess
from mindustry_agents.training.ippo import (
    AGENT_COUNT,
    SharedRecurrentSelector,
    SharedSeatState,
    canonical_teacher_bundle,
    commit_all_seat_boundary,
    decide_all_seats,
    model_state_digest,
)

DEFAULT_SEEDS = (12345, 12346, 12347, 12348, 12349)


def _trace_digest(trace: list[dict[str, Any]]) -> str:
    encoded = json.dumps(
        trace, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _run(
    env: RlServerProcess,
    *,
    seed: int,
    model: SharedRecurrentSelector | None,
) -> dict[str, Any]:
    reset = env.reset(
        seed,
        scenario_id="bootstrap-defense-v1",
        scenario_version=2,
        agent_count=AGENT_COUNT,
    )
    observations = reset.initial_observations
    masks = reset.action_masks
    metadata = reset.metadata
    board: list[dict[str, Any]] = []
    reasons: list[str] = []
    tick = reset.tick
    outcome = "running"
    policy = GreedyUtilityPolicy()
    state = SharedSeatState.fresh()
    trace: list[dict[str, Any]] = []
    model_evaluations = 0
    maximum_models = 0

    while outcome == "running" and tick < int(metadata["tick_cap"]):
        teacher = canonical_teacher_bundle(
            policy.actions(observations, masks), observations
        )
        evaluation_order: tuple[int, ...] = ()
        if model is None:
            bundle = teacher
        else:
            decision = decide_all_seats(
                model,
                state,
                observations,
                masks,
                metadata,
                task_board=board,
                boundary_reasons=reasons,
                evaluation=True,
                teacher_actions=teacher,
            )
            bundle = decision.agent_actions
            if bundle != teacher:
                raise AssertionError("teacher-controlled M9 bundle changed decisions")
            evaluation_order = decision.evaluation_order
            model_evaluations += len(evaluation_order)
            maximum_models = 1
        response = env.step(
            reset.episode_id,
            expected_tick=tick,
            ticks_to_advance=max(1, int(metadata["tick_cap"]) - tick),
            agent_actions=bundle,
            stop_on_decision_event=True,
        )
        policy.observe_action_results(response.action_results)
        if model is not None:
            commit_all_seat_boundary(
                state,
                decision,
                response.action_results,
                observations,
                tick=tick,
            )
        trace.append(
            {
                "tick": tick,
                "next_tick": response.tick,
                "actions": bundle,
                "action_results": response.action_results,
                "evaluation_order": list(evaluation_order),
                "state_hash": response.state_hash,
                "outcome": response.outcome,
            }
        )
        observations = response.observations
        masks = response.action_masks
        board = response.task_board
        reasons = list(response.decision_boundary.get("reasons", []))
        tick = response.tick
        outcome = response.outcome
    return {
        "seed": seed,
        "outcome": outcome,
        "tick": tick,
        "trace": trace,
        "trace_sha256": _trace_digest(trace),
        "model_evaluations": model_evaluations,
        "maximum_shared_model_instances": maximum_models,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="M9 all-seat shared-policy teacher parity"
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--java", default="java")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    args = parser.parse_args(argv)

    try:
        model = SharedRecurrentSelector(seed=9601)
        rows = []
        direct_runs = []
        direct_reset_replay = None
        with RlServerProcess(LaunchConfig(port=args.port, java=args.java)) as env:
            env.handshake("m9-shared-policy-check-direct")
            for seed in args.seeds:
                direct_runs.append(_run(env, seed=seed, model=None))
            direct_reset_replay = _run(env, seed=args.seeds[0], model=None)
        if direct_reset_replay["trace"] != direct_runs[0]["trace"]:
            raise AssertionError(
                "terminal reset changed the repeated first-seed action/state trace"
            )
        traversed_runs = []
        traversed_reset_replay = None
        with RlServerProcess(LaunchConfig(port=args.port, java=args.java)) as env:
            env.handshake("m9-shared-policy-check-traversed")
            for seed in args.seeds:
                traversed_runs.append(_run(env, seed=seed, model=model))
            traversed_reset_replay = _run(env, seed=args.seeds[0], model=model)
        if traversed_reset_replay["trace"] != traversed_runs[0]["trace"]:
            raise AssertionError(
                "terminal reset changed the repeated M9 first-seed trace"
            )
        for seed, direct, traversed in zip(
            args.seeds, direct_runs, traversed_runs, strict=True
        ):
            direct_projection = [
                {key: value for key, value in row.items() if key != "evaluation_order"}
                for row in direct["trace"]
            ]
            traversed_projection = [
                {key: value for key, value in row.items() if key != "evaluation_order"}
                for row in traversed["trace"]
            ]
            if direct_projection != traversed_projection:
                mismatch = next(
                    (
                        index
                        for index, (left, right) in enumerate(
                            zip(
                                direct_projection,
                                traversed_projection,
                                strict=False,
                            )
                        )
                        if left != right
                    ),
                    min(len(direct_projection), len(traversed_projection)),
                )
                raise AssertionError(
                    "M9 teacher-controlled parity diverged for seed "
                    f"{seed} at decision {mismatch}: "
                    f"direct={direct_projection[mismatch] if mismatch < len(direct_projection) else None!r} "
                    f"traversed={traversed_projection[mismatch] if mismatch < len(traversed_projection) else None!r}"
                )
            if traversed["model_evaluations"] < AGENT_COUNT:
                raise AssertionError("M9 path did not evaluate all three seats")
            if traversed["maximum_shared_model_instances"] != 1:
                raise AssertionError("M9 path did not use exactly one shared model")
            rows.append(
                {
                    "seed": seed,
                    "outcome": traversed["outcome"],
                    "tick": traversed["tick"],
                    "decision_count": len(traversed["trace"]),
                    "model_evaluations": traversed["model_evaluations"],
                    "direct_trace_sha256": _trace_digest(direct_projection),
                    "traversed_trace_sha256": _trace_digest(traversed_projection),
                }
            )
        report = {
            "schema": "m9_shared_policy_check_v1",
            "model_schema": model.model_schema,
            "model_state_sha256": model_state_digest(model),
            "agent_count": AGENT_COUNT,
            "maximum_shared_model_instances": 1,
            "all_teacher_controlled_traces_equal": True,
            "terminal_reset_replay_equal": True,
            "episodes": rows,
        }
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    except Exception as exc:
        print(f"M9 SHARED-POLICY FAIL: {exc}", file=sys.stderr)
        return 1

    print(
        "M9 SHARED-POLICY OK "
        f"seeds={len(rows)} model={report['model_state_sha256']} "
        f"evaluations={sum(row['model_evaluations'] for row in rows)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
