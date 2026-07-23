from mindustry_agents.training.ippo_expert_projection import classify_projection


CLASSIFICATION = {
    "minimum_unique_projection_fraction_all": 0.95,
    "minimum_unique_projection_fraction_winning_episodes": 1.0,
    "minimum_projected_replay_wins": 30,
    "minimum_projected_replay_retention_fraction_of_source_wins": 0.8,
    "pass": "candidate_native_supervision_source_supported",
    "fail": "candidate_native_supervision_source_not_supported",
}


def _episode(seed: int, outcome: str, matches: list[int]):
    return {
        "seed": seed,
        "outcome": outcome,
        "projection_rows": [{"match_count": value} for value in matches],
    }


def _replay(seed: int, outcome: str, *, accepted=True, parity=True):
    return {
        "seed": seed,
        "outcome": outcome,
        "all_actions_accepted": accepted,
        "semantic_sequence_parity": parity,
    }


def test_projection_requires_replay_before_support():
    episodes = [_episode(seed, "win", [1, 1]) for seed in range(36)]
    episodes += [_episode(seed, "loss", [1, 1]) for seed in range(36, 40)]
    result = classify_projection(episodes, CLASSIFICATION, replay=None)
    assert result["projection_thresholds_passed"] is True
    assert result["passed"] is False


def test_projection_passes_only_with_frozen_coverage_and_replay_bars():
    episodes = [_episode(seed, "win", [1, 1]) for seed in range(36)]
    episodes += [_episode(seed, "loss", [1, 1]) for seed in range(36, 40)]
    replay = [_replay(seed, "win") for seed in range(30)]
    replay += [_replay(seed, "loss") for seed in range(30, 40)]
    result = classify_projection(episodes, CLASSIFICATION, replay)
    assert result["passed"] is True
    assert result["outcome"] == "candidate_native_supervision_source_supported"


def test_projection_rejects_missing_winning_label():
    episodes = [_episode(0, "win", [1, 0])]
    episodes += [_episode(seed, "loss", [1] * 20) for seed in range(1, 40)]
    result = classify_projection(episodes, CLASSIFICATION, replay=[])
    assert result["unique_projection_fraction_all"] > 0.95
    assert result["unique_projection_fraction_winning_episodes"] == 0.5
    assert result["passed"] is False


def test_projection_rejects_replay_fallback_or_sequence_drift():
    episodes = [_episode(seed, "win", [1]) for seed in range(36)]
    episodes += [_episode(seed, "loss", [1]) for seed in range(36, 40)]
    replay = [_replay(seed, "win") for seed in range(30)]
    replay += [_replay(seed, "loss") for seed in range(30, 40)]
    replay[0]["all_actions_accepted"] = False
    replay[1]["semantic_sequence_parity"] = False
    result = classify_projection(episodes, CLASSIFICATION, replay)
    assert result["projected_replay_wins"] == 30
    assert result["passed"] is False
