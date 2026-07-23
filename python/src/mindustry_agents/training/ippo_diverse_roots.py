"""Deterministic public train-root governance for M9 IPPO v3."""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any, Sequence


V3_TRAIN_SEED_SHA256 = (
    "2e4d5b853ba9c8a6b568b107537756e257d3c19205af71c0445ea5ea730088c4"
)
V3_TRAIN_SEED_PATH = (
    "configs/evaluation/bootstrap-defense-v1-m9-train-diverse2048-v1.json"
)
V1_TRAIN_SEED_PATH = "configs/evaluation/bootstrap-defense-v1-m9-train-v1.json"
DEV_SEED_PATH = "configs/evaluation/bootstrap-defense-v1-m9-dev-v1.json"
TRAIN_MINIMUM = 18_000_000_000
TRAIN_MAXIMUM = 19_000_000_000
ROOT_COUNT = 2_048
UPDATES = 32
EPISODES_PER_UPDATE = 64


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"M9 v3 seed document is not an object: {path}")
    return value


def diverse_training_seed_schedule(
    seeds: Sequence[int], *, shuffle_seed: int
) -> list[int]:
    """Shuffle all 2,048 public roots once and use every root exactly once."""

    schedule = [int(seed) for seed in seeds]
    if (
        len(schedule) != ROOT_COUNT
        or len(set(schedule)) != ROOT_COUNT
        or any(seed < TRAIN_MINIMUM or seed >= TRAIN_MAXIMUM for seed in schedule)
    ):
        raise ValueError("M9 IPPO v3 public train roots are invalid")
    random.Random(int(shuffle_seed)).shuffle(schedule)
    if len(set(schedule)) != ROOT_COUNT:
        raise AssertionError("M9 IPPO v3 schedule lost unique roots")
    return schedule


def schedule_sha256(schedule: Sequence[int]) -> str:
    """Hash the exact ordered training schedule."""

    encoded = json.dumps(
        [int(seed) for seed in schedule],
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def validate_diverse_root_packet(root: Path) -> dict[str, Any]:
    """Validate membership, public namespace isolation, and exact schedule."""

    train_path = root / V3_TRAIN_SEED_PATH
    if _sha256(train_path) != V3_TRAIN_SEED_SHA256:
        raise ValueError("M9 IPPO v3 public train root hash drifted")
    train = _load(train_path)
    v1_train = _load(root / V1_TRAIN_SEED_PATH)
    dev = _load(root / DEV_SEED_PATH)
    seeds = [int(seed) for seed in train.get("seeds", [])]
    if (
        train.get("seed_set_id")
        != "bootstrap-defense-v1-m9-train-diverse2048-v1"
        or train.get("seed_set_version") != 1
        or train.get("scenario_id") != "bootstrap-defense-v1"
        or train.get("scenario_version") != 2
        or train.get("split") != "train"
    ):
        raise ValueError("M9 IPPO v3 public train document drifted")
    schedule = diverse_training_seed_schedule(seeds, shuffle_seed=9603)
    if set(seeds) & {int(seed) for seed in v1_train.get("seeds", [])}:
        raise ValueError("M9 IPPO v3 train roots overlap v1 train roots")
    if set(seeds) & {int(seed) for seed in dev.get("seeds", [])}:
        raise ValueError("M9 IPPO v3 train roots overlap public dev roots")
    updates = [
        schedule[start : start + EPISODES_PER_UPDATE]
        for start in range(0, ROOT_COUNT, EPISODES_PER_UPDATE)
    ]
    if len(updates) != UPDATES or any(
        len(update) != EPISODES_PER_UPDATE for update in updates
    ):
        raise AssertionError("M9 IPPO v3 schedule slicing drifted")
    return {
        "train_seed_sha256": V3_TRAIN_SEED_SHA256,
        "root_count": len(seeds),
        "unique_root_count": len(set(seeds)),
        "minimum_seed": min(seeds),
        "maximum_seed": max(seeds),
        "v1_train_overlap": 0,
        "public_dev_overlap": 0,
        "shuffle_seed": 9603,
        "schedule_sha256": schedule_sha256(schedule),
        "updates": len(updates),
        "episodes_per_update": EPISODES_PER_UPDATE,
        "root_reuse_count": 1,
        "confirmation_or_held_out_access": False,
    }
