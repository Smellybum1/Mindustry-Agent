"""Executable reward-hacking adversaries with machine-readable evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from mindustry_agents.process.launcher import repo_root
from mindustry_agents.training.reward import (
    COMPONENT_KEYS,
    RewardAuditError,
    SelectorReward,
)

CASES = (
    "rebuild-loop",
    "wait-only",
    "fake-wave-clear",
    "survival-only",
    "forced-truncation",
    "reckless-minimal-win",
    "early-suicide",
    "chunk-size",
    "readiness-then-abandon",
    "invalid-spam",
    "mask-corruption",
    "invalid-probe",
    "claim-abandon-churn",
    "blocked-never-release",
    "forced-abandon-exclusions",
    "idle-farming",
    "duplicate-bids",
    "message-spam",
    "unsafe-help",
    "build-rebuild-loop",
    "chunk-manipulation",
    "item-cycling",
    "repair-farming",
    "damage-farming",
    "task-spam",
    "production-stockpile",
    "reckless-wave-progress",
)


def _team(tick: int, **overrides: Any) -> dict[str, Any]:
    value = {
        "tick": tick,
        "line_operational": False,
        "defense_readiness": 0.0,
        "enemy_count": 0,
        "wave": 1,
    }
    value.update(overrides)
    return value


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _report(
    case: str,
    transitions: list[dict[str, Any]],
    components: dict[str, float],
    reason: str,
    **extra: Any,
) -> dict[str, Any]:
    report = {
        "case": case,
        "pass": True,
        "reason": reason,
        "action_hashes": [_digest(item.get("action", {})) for item in transitions],
        "state_hashes": [_digest(item.get("current", {})) for item in transitions],
        "structured_events": [
            event for item in transitions for event in item.get("task_events", [])
        ],
        "components": {key: float(components.get(key, 0.0)) for key in COMPONENT_KEYS},
        "total_return": sum(components.values()),
    }
    report.update(extra)
    return report


def run_case(case: str) -> dict[str, Any]:
    """Run one deterministic synthetic trace through the production accumulator."""

    if case not in CASES:
        raise ValueError(f"unknown reward adversary: {case}")
    reward = SelectorReward()
    transitions: list[dict[str, Any]] = []
    totals = {key: 0.0 for key in COMPONENT_KEYS}

    def apply(previous: dict[str, Any], current: dict[str, Any], **kwargs: Any):
        transition = {
            "previous": previous,
            "current": current,
            "action": kwargs.pop("action", {"type": "WAIT"}),
            "task_events": kwargs.get("task_events", []),
        }
        transitions.append(transition)
        result = reward.observe(previous, current, tick_cap=9000, **kwargs)
        for key, value in result.components.items():
            totals[key] += value
        return result

    if case in {"rebuild-loop", "build-rebuild-loop"}:
        apply(_team(0), _team(10, line_operational=True), advanced_ticks=10)
        apply(_team(10, line_operational=True), _team(20), advanced_ticks=10)
        result = apply(_team(20), _team(30, line_operational=True), advanced_ticks=10)
        assert totals["reward.team.milestone_highwater"] == 1.0
        assert not result.milestone_ids
        reason = "physical line high-water paid exactly once"
    elif case in {"wait-only", "survival-only", "idle-farming", "blocked-never-release"}:
        result = apply(_team(0), _team(600), advanced_ticks=600)
        assert result.total < 0.0
        assert totals["reward.team.milestone_highwater"] == 0.0
        reason = "idle/survival work earned no positive signal"
    elif case == "fake-wave-clear":
        result = apply(
            _team(0, enemy_count=1), _team(10), advanced_ticks=10,
            boundary_reasons=["wave_clear"],
        )
        assert result.components["reward.team.milestone_highwater"] == 0.0
        reason = "clear without an observed scheduled spawn paid zero"
    elif case == "forced-truncation":
        result = apply(_team(0), _team(100), advanced_ticks=100, outcome="truncated")
        assert result.components["reward.team.terminal_outcome"] == -10.0
        assert result.charged_ticks == 9000
        reason = "truncation was charged exactly as a full-horizon loss"
    elif case == "reckless-minimal-win":
        result = apply(_team(0), _team(8100), advanced_ticks=8100, outcome="win")
        assert result.components["reward.team.milestone_highwater"] == 0.0
        reason = "terminal win did not waive the separate scorecard gate"
        return _report(case, transitions, totals, reason, promotion_eligible=False)
    elif case == "early-suicide":
        result = apply(_team(0), _team(100), advanced_ticks=100, outcome="loss")
        assert result.charged_ticks == 9000
        reason = "early loss retained the complete unresolved tick horizon"
    elif case in {"chunk-size", "chunk-manipulation"}:
        whole = SelectorReward().observe(_team(0), _team(600), advanced_ticks=600, tick_cap=9000)
        for tick in range(0, 600, 100):
            apply(_team(tick), _team(tick + 100), advanced_ticks=100)
        assert abs(whole.total - sum(totals.values())) < 1e-12
        reason = "identical engine ticks matched across step chunkings"
    elif case == "readiness-then-abandon":
        apply(_team(0), _team(10, defense_readiness=1.0), advanced_ticks=10)
        apply(_team(10, defense_readiness=1.0), _team(20), advanced_ticks=10)
        apply(_team(20), _team(30, defense_readiness=1.0), advanced_ticks=10)
        assert totals["reward.team.milestone_highwater"] == 1.0
        reason = "readiness high-water neither reversed nor repeated"
    elif case == "invalid-spam":
        for tick in range(8):
            apply(
                _team(tick), _team(tick + 1), advanced_ticks=1,
                raw_action_valid=False, action={"raw_index": 99, "fallback": "WAIT"},
            )
        assert totals["reward.penalty.invalid_action"] == -1.0
        reason = "invalid penalty capped at -1 while every action fell back to WAIT"
    elif case == "mask-corruption":
        try:
            apply(
                _team(0), _team(1), advanced_ticks=1,
                environment_mask_valid=False,
            )
        except RewardAuditError:
            reason = "environment mask corruption failed the run instead of blaming policy"
        else:
            raise AssertionError("mask corruption did not fail")
    elif case == "invalid-probe":
        result = apply(
            _team(0), _team(1), advanced_ticks=1, raw_action_valid=False,
            action={"raw_index": 99, "submitted": "WAIT", "retry": False},
        )
        assert result.components["reward.penalty.invalid_action"] == -0.25
        assert len(transitions) == 1
        reason = "invalid probe produced one WAIT transition and no retry"
    elif case == "claim-abandon-churn":
        reward.record_learned_selection("learned-task")
        for tick in range(15):
            event = {
                "act": "ABANDON", "agent_id": 0, "task_id": "learned-task",
                "reason_code": "blocked_replan",
            }
            apply(_team(tick), _team(tick + 1), advanced_ticks=1, task_events=[event])
        assert abs(totals["reward.penalty.abandonment_liability"] + 0.5) < 1e-12
        reason = "learned claim/abandon churn liability capped at -0.5"
    elif case == "forced-abandon-exclusions":
        reward.record_learned_selection("learned-task")
        for tick, abandon_reason in enumerate(
            ("wave_preemption", "readiness_rebalance", "death", "lease_failure", "human_override", "terminal_cleanup")
        ):
            event = {
                "act": "ABANDON", "agent_id": 0, "task_id": "learned-task",
                "reason_code": abandon_reason,
            }
            apply(_team(tick), _team(tick + 1), advanced_ticks=1, task_events=[event])
        assert totals["reward.penalty.abandonment_liability"] == 0.0
        reason = "all forced safety/death/lease/human/terminal exclusions paid zero"
    elif case == "duplicate-bids":
        result = apply(
            _team(0), _team(1), advanced_ticks=1,
            task_events=[{"act": "CLAIM_LOST", "agent_id": 0, "reason_code": "duplicate"}],
        )
        assert result.components["reward.penalty.invalid_action"] == 0.0
        reason = "mask-valid atomic claim loss received no reward or invalid penalty"
    elif case in {
        "message-spam",
        "unsafe-help",
        "item-cycling",
        "repair-farming",
        "damage-farming",
        "task-spam",
        "production-stockpile",
        "reckless-wave-progress",
    }:
        events = {
            "message-spam": [{"act": "MESSAGE", "agent_id": 0}],
            "unsafe-help": [{"act": "OFFER_HELP", "agent_id": 0}],
            "item-cycling": [
                {"act": "MINE", "agent_id": 0, "amount": 100},
                {"act": "DELIVER", "agent_id": 0, "amount": 100},
            ],
            "repair-farming": [{"act": "REPAIR", "agent_id": 0, "amount": 1000}],
            "damage-farming": [{"act": "DAMAGE", "agent_id": 0, "amount": 5000}],
            "task-spam": [{"act": "PROPOSE", "agent_id": 0, "count": 100}],
            "production-stockpile": [{"act": "PRODUCE", "agent_id": 0, "amount": 4000}],
            "reckless-wave-progress": [{"act": "WAVE_TRIGGER", "agent_id": 0}],
        }[case]
        plain = SelectorReward().observe(_team(0), _team(10), advanced_ticks=10, tick_cap=9000)
        result = apply(
            _team(0), _team(10), advanced_ticks=10,
            task_events=events,
        )
        assert result.components == plain.components
        reason = f"{case} telemetry did not enter any reward component"
    else:
        raise AssertionError(f"unhandled reward adversary: {case}")
    return _report(case, transitions, totals, reason)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M8.4 selector reward adversaries")
    parser.add_argument("--case", action="append", choices=CASES)
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "runs" / "m8-reward-adversaries.json",
    )
    args = parser.parse_args(argv)
    selected = args.case or list(CASES)
    reports = [run_case(case) for case in selected]
    document = {
        "schema": "selector_reward_adversary_report_v1",
        "reward_schema": "selector_reward_v1",
        "cases": reports,
        "pass": all(item["pass"] for item in reports),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for item in reports:
        print(f"{item['case']}: PASS - {item['reason']}")
    print(f"report={args.output}")
    print("REWARD-ADVERSARY OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
