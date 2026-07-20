"""Shared scenario metadata and result records for scripted expert runners."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScenarioLayout:
    """Runtime view of the authoritative scenario/schematic reset metadata."""

    metadata: dict[str, Any]

    @property
    def tile_size(self) -> int:
        return int(self.metadata["tile_size"])

    @property
    def win_tick(self) -> int:
        return int(self.metadata["win_tick"])

    @property
    def tick_cap(self) -> int:
        return int(self.metadata["tick_cap"])

    @property
    def wave_ticks(self) -> tuple[int, ...]:
        return tuple(int(tick) for tick in self.metadata["wave_ticks"])

    @property
    def core_tile(self) -> tuple[int, int]:
        return int(self.metadata["core_x"]), int(self.metadata["core_y"])

    @property
    def mine_tiles(self) -> tuple[tuple[int, int], ...]:
        patch = next(
            item
            for item in self.metadata["ore_patches"]
            if item["role"] == "east_ammo_feed"
        )
        rect = patch["rect"]
        x, y = int(rect["x"]), int(rect["y"])
        w, h = int(rect["w"]), int(rect["h"])
        if w < 2 or h < 2:
            raise ValueError("east_ammo_feed ore patch must be at least 2x2")
        return (x, y), (x + w - 1, y), (x, y + h - 1)

    @property
    def reference_turrets(self) -> tuple[tuple[int, int], ...]:
        schematic = self.metadata["reference_schematic"]
        anchor_x, anchor_y = (int(value) for value in schematic["anchor"])
        result = tuple(
            (anchor_x + int(block["offset"][0]), anchor_y + int(block["offset"][1]))
            for block in schematic["blocks"]
            if block["block"] == "duo"
        )
        if len(result) != 2:
            raise ValueError("reference schematic must contain two expert turrets")
        return result

    @property
    def first_drill_progress(self) -> float:
        count = len(self.metadata["build_line"]["blocks"])
        if count <= 0:
            raise ValueError("build-line schematic has no blocks")
        return 1.0 / count

    def region_for(self, task_type: str) -> dict[str, int]:
        region_id = self.metadata["objectives"][task_type]["target_ref"]
        return self.metadata["regions"][region_id]["rect"]

    def defend_command(self) -> dict[str, Any]:
        rect = self.region_for("DEFEND_REGION")
        tile_size = self.tile_size
        # Hold the western quarter of the lane: agents screen the core without
        # overextending toward the spawn, while the radius covers the full region.
        x = (int(rect["x"]) + (int(rect["w"]) - 1) / 4) * tile_size
        y = (int(rect["y"]) + (int(rect["h"]) - 1) / 2) * tile_size
        radius = math.hypot(int(rect["w"]) * tile_size, int(rect["h"]) * tile_size)
        return {"type": "DEFEND", "x": x, "y": y, "radius": radius, "ticks": self.tick_cap}


@dataclass
class EpisodeResult:
    seed: int
    outcome: str
    tick: int
    core_health: float
    announcements: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    line_complete_tick: int = -1
    schematic_complete_tick: int = -1
    wave_clear_ticks: list[int] = field(default_factory=list)
    resources_short_replans: int = 0
    first_drill_tick: int = -1
    turrets_supplied_tick: int = -1
    copper_start: int = 250
    copper_final: int = 0
    copper_peak: int = 250
    copper_min: int = 250
    copper_boundary_in: int = 0
    copper_boundary_out: int = 0
    units_lost: int = 0
    win_tick: int = 0
