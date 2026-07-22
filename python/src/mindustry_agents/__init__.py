"""mindustry_agents — Python side of the mindustry-coop-agents project.

Hosts the PettingZoo ``ParallelEnv`` facade, the JVM process supervisor,
policies, training, evaluation, and telemetry for a deterministic,
externally-stepped, multi-agent Mindustry environment.

Design constraints (see ``docs/decisions/``):

* The core package imports **only the Python standard library**. Heavy RL
  dependencies (pettingzoo, numpy, torch) live behind the ``[rl]`` extra and are
  never imported by the env or protocol layers (ADR-0007).
* The wire protocol is length-prefixed JSON over loopback TCP for the bootstrap
  phase (ADR-0004); see :mod:`mindustry_agents.protocol` and ``docs/PROTOCOL.md``.
"""

__all__ = ["protocol"]

# Kept in sync with ENGINE_VERSION and docs/PROTOCOL.md.
PROTOCOL_VERSION = 1
ENGINE_TAG = "v159.7"
ENGINE_COMMIT = "c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c"
ARC_VERSION = "208a754044"
__version__ = "0.0.1"
