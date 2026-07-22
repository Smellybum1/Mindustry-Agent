"""Print the canonical entry-content SHA-256 for one JAR/ZIP artifact."""

from __future__ import annotations

import argparse
from pathlib import Path

from mindustry_agents.telemetry.artifact_provenance import jar_content_sha256


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    print(jar_content_sha256(args.artifact))


if __name__ == "__main__":
    main()
