from mindustry_agents.evaluation.scripted import aggregate, episode_summary
from mindustry_agents.tools.scripted_demo import EpisodeResult


def test_episode_summary_and_aggregate_are_stable():
    result = EpisodeResult(
        seed=7,
        outcome="win",
        tick=8100,
        core_health=900.0,
        metrics={
            "tasks_completed": 2,
            "tasks_abandoned": 1,
            "duplicate_work_incidents": 0,
            "idle_fraction": 0.25,
            "structured_messages": 20,
            "announced_messages": 4,
        },
        first_drill_tick=20,
        line_complete_tick=40,
        schematic_complete_tick=250,
        turrets_supplied_tick=1000,
        units_lost=1,
    )
    summary = episode_summary(result, {"engine_tag": "v159.7"})
    assert summary["milestones"]["line_complete_tick"] == 40
    assert summary["tasks"] == {"completed": 2, "abandoned": 1, "duplicated": 0}
    assert summary["core"]["damage"] == 200.0
    assert aggregate([summary]) == {
        "episodes": 1,
        "wins": 1,
        "win_rate": 1.0,
        "core_health_min": 900.0,
        "core_health_mean": 900.0,
        "units_lost": 1,
        "structured_messages": 20,
        "announced_messages": 4,
    }
