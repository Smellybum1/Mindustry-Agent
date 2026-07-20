import pytest

from mindustry_agents.tools.scripted_demo import ScenarioLayout


def metadata() -> dict:
    return {
        "tile_size": 10,
        "win_tick": 500,
        "tick_cap": 600,
        "wave_ticks": [100, 250],
        "core_x": 7,
        "core_y": 8,
        "ore_patches": [
            {
                "role": "east_ammo_feed",
                "rect": {"x": 20, "y": 30, "w": 5, "h": 3},
            }
        ],
        "reference_schematic": {
            "anchor": [40, 50],
            "blocks": [
                {"block": "duo", "offset": [0, -2]},
                {"block": "copper-wall", "offset": [1, 0]},
                {"block": "duo", "offset": [0, 2]},
            ],
        },
        "build_line": {"blocks": [{}, {}, {}, {}]},
        "objectives": {
            "DEFEND_REGION": {"target_ref": "lane"},
            "REPAIR_REGION": {"target_ref": "repairs"},
        },
        "regions": {
            "lane": {"rect": {"x": 10, "y": 20, "w": 5, "h": 3}},
            "repairs": {"rect": {"x": 1, "y": 2, "w": 3, "h": 4}},
        },
    }


def test_layout_derives_coordinates_and_timing_from_metadata():
    layout = ScenarioLayout(metadata())

    assert layout.core_tile == (7, 8)
    assert layout.mine_tiles == ((20, 30), (24, 30), (20, 32))
    assert layout.reference_turrets == ((40, 48), (40, 52))
    assert layout.first_drill_progress == 0.25
    assert layout.wave_ticks == (100, 250)
    assert layout.win_tick == 500

    defend = layout.defend_command()
    assert defend["x"] == 110
    assert defend["y"] == 210
    assert defend["radius"] == pytest.approx(58.309519)
    assert defend["ticks"] == 600


def test_layout_rejects_too_small_support_patch():
    value = metadata()
    value["ore_patches"][0]["rect"]["w"] = 1

    with pytest.raises(ValueError, match="at least 2x2"):
        _ = ScenarioLayout(value).mine_tiles
