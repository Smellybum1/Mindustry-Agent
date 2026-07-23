"""Pure M8.5 promotion comparisons over archived episode records."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from typing import Any

from mindustry_agents.evaluation.ladder import bootstrap_interval

SCORECARD_METRICS = (
    "idle_fraction",
    "duplicate_work_incidents",
    "time_to_help_ticks",
    "announcements_per_meaningful_transition",
    "task_abandonment_rate",
    "recovery_time_after_agent_loss_ticks",
)


def validate_scorecard_margins(
    margins: Mapping[str, Any] | None,
) -> dict[str, float]:
    """Return exact, finite, nonnegative scorecard margins."""

    if margins is None:
        return {metric: 0.0 for metric in SCORECARD_METRICS}
    if set(margins) != set(SCORECARD_METRICS):
        raise ValueError("scorecard margins must cover the exact metric schema")
    validated: dict[str, float] = {}
    for metric in SCORECARD_METRICS:
        value = margins[metric]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0.0
        ):
            raise ValueError(f"invalid scorecard margin: {metric}")
        validated[metric] = float(value)
    return validated


def _stable_seed(*parts: str) -> int:
    payload = "\0".join(parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def win_rate_comparison(
    candidate: dict[str, Any],
    baseline: dict[str, Any],
    *,
    require_ci_separation: bool,
) -> dict[str, Any]:
    """Compare win rates using the gate appropriate to the active split."""

    candidate_low, candidate_high = candidate["win_rate"]["ci95"]
    baseline_low, baseline_high = baseline["win_rate"]["ci95"]
    candidate_rate = float(candidate["win_rate"]["mean"])
    baseline_rate = float(baseline["win_rate"]["mean"])
    if require_ci_separation:
        passed = candidate_low > baseline_high
        status = "better_ci_separated" if passed else "not_ci_separated"
        mode = "strict_95pct_ci_separation"
    else:
        passed = candidate_rate > baseline_rate
        status = "better_observed_rate" if passed else "not_better_observed_rate"
        mode = "strict_observed_rate_improvement"
    return {
        "candidate": candidate["policy"],
        "baseline": baseline["policy"],
        "comparison_mode": mode,
        "candidate_rate": candidate_rate,
        "baseline_rate": baseline_rate,
        "candidate_ci95": [candidate_low, candidate_high],
        "baseline_ci95": [baseline_low, baseline_high],
        "status": status,
        "passed": passed,
    }


def paired_scorecard_non_regression(
    records: list[dict[str, Any]],
    *,
    candidate_policy: str,
    baseline_policy: str,
    margins: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Bootstrap matched-seed candidate-minus-baseline scorecard differences."""

    validated_margins = validate_scorecard_margins(margins)
    operational = any(value > 0.0 for value in validated_margins.values())
    by_policy: dict[str, dict[int, dict[str, Any]]] = {}
    for record in records:
        policy = str(record["manifest"]["policy"])
        by_policy.setdefault(policy, {})[int(record["seed"])] = record
    candidate = by_policy.get(candidate_policy, {})
    baseline = by_policy.get(baseline_policy, {})
    if set(candidate) != set(baseline) or not candidate:
        raise ValueError("scorecard comparison requires identical non-empty seed sets")

    metrics = {}
    for metric in SCORECARD_METRICS:
        differences = []
        for seed in sorted(candidate):
            candidate_value = candidate[seed]["scorecard"][metric]
            baseline_value = baseline[seed]["scorecard"][metric]
            if candidate_value is None or baseline_value is None:
                continue
            differences.append(float(candidate_value) - float(baseline_value))
        if not differences:
            metrics[metric] = {
                "status": "not_observed",
                "passed": None,
                "paired_seeds": 0,
                "difference": {"n": 0, "mean": None, "ci95": [None, None]},
            }
            continue
        interval = bootstrap_interval(
            differences,
            seed=_stable_seed(candidate_policy, baseline_policy, metric),
        )
        margin = validated_margins[metric]
        passed = interval["ci95"][1] <= margin and (
            not operational or interval["mean"] <= margin
        )
        metrics[metric] = {
            "status": (
                "operationally_noninferior"
                if passed and operational
                else "non_regressing"
                if passed
                else "regressing_or_uncertain"
            ),
            "passed": passed,
            "paired_seeds": len(differences),
            **({"noninferiority_margin": margin} if operational else {}),
            "difference": interval,
        }
    return {
        "candidate": candidate_policy,
        "baseline": baseline_policy,
        "direction": "candidate_minus_baseline; lower is better",
        **(
            {
                "decision_rule": (
                    "mean_and_ci95_upper_bound_at_or_below_metric_margin"
                ),
                "margins": validated_margins,
            }
            if operational
            else {}
        ),
        "metrics": metrics,
        "passed": all(item["passed"] is not False for item in metrics.values()),
    }


def promotion_preflight(
    records: list[dict[str, Any]],
    aggregates: list[dict[str, Any]],
    *,
    candidate_policy: str,
    win_rate_baselines: tuple[str, ...],
    scorecard_baseline: str | None = None,
    scorecard_baselines: tuple[str, ...] = (),
    reward_adversaries_passed: bool,
    scorecard_margins: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the dev-only qualification screen before freezing held-out inputs."""

    by_policy = {str(item["policy"]): item for item in aggregates}
    candidate = by_policy.get(candidate_policy)
    if candidate is None:
        raise ValueError(f"missing candidate aggregate: {candidate_policy}")
    if candidate["seed_set"]["split"] != "dev":
        raise ValueError("promotion preflight is restricted to the dev split")
    comparisons = []
    for baseline_policy in win_rate_baselines:
        baseline = by_policy.get(baseline_policy)
        if baseline is None:
            raise ValueError(f"missing baseline aggregate: {baseline_policy}")
        comparisons.append(
            win_rate_comparison(
                candidate, baseline, require_ci_separation=False
            )
        )
    if scorecard_baseline is not None and scorecard_baselines:
        raise ValueError("provide one scorecard baseline form")
    active_scorecard_baselines = scorecard_baselines or (
        (scorecard_baseline,) if scorecard_baseline is not None else ()
    )
    if not active_scorecard_baselines:
        raise ValueError("at least one scorecard baseline is required")
    scorecards = [
        paired_scorecard_non_regression(
            records,
            candidate_policy=candidate_policy,
            baseline_policy=baseline_policy,
            margins=scorecard_margins,
        )
        for baseline_policy in active_scorecard_baselines
    ]
    eligible = (
        reward_adversaries_passed
        and all(item["passed"] for item in comparisons)
        and all(item["passed"] for item in scorecards)
    )
    return {
        "schema": "selector_promotion_preflight_v1",
        "candidate": candidate_policy,
        "split": candidate["seed_set"]["split"],
        "win_rate_comparisons": comparisons,
        "scorecard_non_regression": scorecards[-1],
        "scorecard_non_regressions": scorecards,
        "reward_adversaries_passed": reward_adversaries_passed,
        "eligible_for_held_out": eligible,
    }
