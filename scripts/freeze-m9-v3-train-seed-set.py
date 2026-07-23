#!/usr/bin/env python3
"""Freeze or verify ADR-0075's deterministic public M9 v3 train roots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "configs"
    / "evaluation"
    / "bootstrap-defense-v1-m9-train-diverse2048-v1.json"
)
FIRST_SEED = 18_000_100_001
COUNT = 2_048


def document() -> dict:
    """Return the immutable public train-only membership."""

    return {
        "seed_set_id": "bootstrap-defense-v1-m9-train-diverse2048-v1",
        "seed_set_version": 1,
        "scenario_id": "bootstrap-defense-v1",
        "scenario_version": 2,
        "split": "train",
        "seeds": list(range(FIRST_SEED, FIRST_SEED + COUNT)),
        "policy": (
            "Public M9.1 v3 train-only roots frozen by ADR-0075 before "
            "candidate implementation or training; one unique root per "
            "authorized training episode."
        ),
    }


def encoded() -> str:
    """Return canonical human-readable JSON."""

    return json.dumps(document(), indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the frozen file instead of creating it",
    )
    args = parser.parse_args()
    expected = encoded()
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != expected:
            raise SystemExit("M9 v3 public train seed set drifted")
        print(f"M9 V3 TRAIN ROOTS OK count={COUNT} first={FIRST_SEED}")
        return 0
    if OUTPUT.exists():
        raise SystemExit("M9 v3 public train seed set already exists")
    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"M9 V3 TRAIN ROOTS FROZEN count={COUNT} first={FIRST_SEED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
