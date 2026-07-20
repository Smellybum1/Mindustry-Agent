from mindustry_agents.evaluation.ladder import (
    aggregate_records,
    bootstrap_interval,
    held_out_promotions,
    ladder_episode_record,
    teammate_scorecard,
)
from mindustry_agents.tools.expert_common import EpisodeResult


def _event(tick, act, task="task-a", **values):
    return {
        "tick": tick,
        "act": act,
        "task_id": task,
        "task_type": "BUILD_LINE",
        "agent_id": values.pop("agent_id", 0),
        "from_status": values.pop("from_status", "RUNNING"),
        "to_status": values.pop("to_status", "RUNNING"),
        "announce": values.pop("announce", False),
        **values,
    }


def test_scorecard_derives_help_announcements_abandonment_and_recovery():
    result = EpisodeResult(
        seed=7,
        outcome="win",
        tick=100,
        core_health=1000,
        metrics={
            "idle_fraction": 0.25,
            "duplicate_work_incidents": 2,
            "tasks_completed": 3,
            "tasks_abandoned": 1,
        },
        task_events=[
            _event(10, "START_TASK", from_status="CLAIMED", announce=True),
            _event(20, "REQUEST_HELP"),
            _event(35, "PROGRESS", reason_code="help_fulfilled", agent_id=1),
            _event(40, "PROGRESS"),
            _event(60, "START_TASK", task="task-b", agent_id=1, from_status="CLAIMED"),
        ],
        agent_loss_ticks={0: 50},
    )
    scorecard = teammate_scorecard(result)
    assert scorecard == {
        "idle_fraction": 0.25,
        "duplicate_work_incidents": 2,
        "time_to_help_ticks": 15.0,
        "help_requests": 1,
        "help_fulfilments": 1,
        "announcements_per_meaningful_transition": 0.5,
        "meaningful_transitions": 2,
        "announced_messages": 1,
        "task_abandonment_rate": 0.25,
        "recovery_time_after_agent_loss_ticks": 10.0,
        "agent_losses_observed": 1,
        "agent_loss_recoveries_observed": 1,
    }


def test_scorecard_uses_null_for_unobserved_help_and_loss_recovery():
    scorecard = teammate_scorecard(
        EpisodeResult(seed=1, outcome="loss", tick=50, core_health=0)
    )
    assert scorecard["time_to_help_ticks"] is None
    assert scorecard["recovery_time_after_agent_loss_ticks"] is None


def test_bootstrap_and_aggregate_are_byte_stable():
    assert bootstrap_interval([0, 1, 1], seed=123, resamples=100) == bootstrap_interval(
        [0, 1, 1], seed=123, resamples=100
    )
    seed_set = {
        "seed_set_id": "fixture",
        "seed_set_version": 1,
        "split": "dev",
    }
    records = [
        ladder_episode_record(
            EpisodeResult(
                seed=seed,
                outcome=outcome,
                tick=100,
                core_health=health,
                metrics={"agent_ticks": 3, "idle_fraction": 1 / 3},
            ),
            {"policy": "adaptive-v1"},
            seed_set,
        )
        for seed, outcome, health in ((1, "win", 1000), (2, "loss", 0))
    ]
    assert aggregate_records(records) == aggregate_records(records)
    aggregate = aggregate_records(records)[0]
    assert aggregate["episodes"] == 2
    assert aggregate["wins"] == 1
    assert aggregate["win_rate"]["mean"] == 0.5


def test_promotion_requires_non_overlapping_held_out_win_intervals():
    base = {
        "seed_set": {"id": "held", "version": 1, "split": "held-out"},
        "win_rate": {"n": 10, "mean": 0.5, "ci95": [0.3, 0.7]},
    }
    promotions = held_out_promotions(
        [
            {**base, "policy": "greedy-utility"},
            {
                **base,
                "policy": "adaptive-v1",
                "win_rate": {"n": 10, "mean": 1.0, "ci95": [0.8, 1.0]},
            },
            {
                **base,
                "policy": "role-assignment",
                "win_rate": {"n": 10, "mean": 0.6, "ci95": [0.4, 0.8]},
            },
        ]
    )
    assert [(row["candidate"], row["status"]) for row in promotions] == [
        ("adaptive-v1", "better_ci_separated"),
        ("role-assignment", "not_ci_separated"),
    ]
