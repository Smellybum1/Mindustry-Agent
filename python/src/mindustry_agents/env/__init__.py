"""Environment facade layer.

Will host the PettingZoo ``ParallelEnv`` implementation that batches all agents
in a single world into one atomic step, plus the framework-neutral env contracts
(observation/action space descriptors). This layer must stay free of any RL
framework import (no ``torch``, no training-only deps) so the environment is
testable in isolation (ADR-0007).

M2 status: implemented (framework-neutral, stdlib only). ``client.EnvClient``
wraps one connection with episode/tick bookkeeping; ``parallel_env`` provides the
PettingZoo ``ParallelEnv`` method surface duck-typed (no pettingzoo import);
``vector.VectorCollector`` steps a pool of worlds in lockstep. Per-agent
observations remain world-level until M3 (the plumbing is per-agent; only the
payload changes).
"""
