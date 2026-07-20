"""Environment facade layer.

Will host the PettingZoo ``ParallelEnv`` implementation that batches all agents
in a single world into one atomic step, plus the framework-neutral env contracts
(observation/action space descriptors). This layer must stay free of any RL
framework import (no ``torch``, no training-only deps) so the environment is
testable in isolation (ADR-0007).

Currently a skeleton package; the facade lands in roadmap M2.
"""
