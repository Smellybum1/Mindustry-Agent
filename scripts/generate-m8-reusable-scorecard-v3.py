#!/usr/bin/env python3
"""Generate the public, precommitted M8 reusable-scorecard v3 membership."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "configs"
    / "evaluation"
    / "bootstrap-defense-v1-reusable-scorecard-v3.json"
)
MINIMUM = 15_000_000_000
MAXIMUM_EXCLUSIVE = 16_000_000_000
COUNT = 160
DOMAIN = "mindustry-agent:m8:reusable-scorecard-v3"


def _seeds() -> list[int]:
    values: set[int] = set()
    counter = 0
    while len(values) < COUNT:
        digest = hashlib.sha256(f"{DOMAIN}:{counter}".encode()).digest()
        values.add(
            MINIMUM
            + int.from_bytes(digest[:8], "big")
            % (MAXIMUM_EXCLUSIVE - MINIMUM)
        )
        counter += 1
    return sorted(values)


def _manifest() -> dict[str, object]:
    return {
        "seed_set_id": "bootstrap-defense-v1-reusable-scorecard-v3",
        "seed_set_version": 3,
        "scenario_id": "bootstrap-defense-v1",
        "scenario_version": 2,
        "split": "dev",
        "seeds": _seeds(),
        "policy": (
            "Public reusable-only scorecard set precommitted by ADR-0068. "
            "Forbidden for training, checkpoint selection, confirmation, or "
            "held-out claims."
        ),
        "generation": {
            "schema": "sha256_domain_counter_modulo_namespace_v1",
            "domain": DOMAIN,
            "counter_start": 0,
            "digest_bytes": "first_8_big_endian",
            "minimum_inclusive": MINIMUM,
            "maximum_exclusive": MAXIMUM_EXCLUSIVE,
            "deduplication": "set_until_count_then_numeric_sort",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    if output != OUTPUT.resolve():
        raise ValueError("unexpected reusable-scorecard v3 output path")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.write_text(
        json.dumps(_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        "M8-REUSABLE-SCORECARD-V3 GENERATED "
        f"count={COUNT} namespace=[{MINIMUM},{MAXIMUM_EXCLUSIVE})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
