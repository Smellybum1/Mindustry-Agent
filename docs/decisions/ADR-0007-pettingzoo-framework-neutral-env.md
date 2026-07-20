# ADR-0007: PettingZoo ParallelEnv facade; framework-neutral env layer

**Status:** Accepted

## Context

We want a standard multi-agent RL interface and the freedom to swap training
frameworks without rewriting the environment. Coupling the env to a specific
tensor library would make it hard to test and hard to reuse.

## Decision

Expose the environment through a **PettingZoo `ParallelEnv` facade** in Python
that batches all agents in a world into one atomic step. The **environment API is
framework-neutral: no `torch` import in the env layer or the protocol code.** RL
framework imports are confined to `policies` (learning ones) and `training`.

## Alternatives considered

- **Gym/Gymnasium single-agent API**: rejected — multi-agent is first-class here.
- **A bespoke env interface**: rejected — PettingZoo is the community standard and
  interops with existing MARL tooling.
- **Env directly emits torch tensors**: rejected — couples env to a framework,
  blocks stdlib-only testing.

## Consequences

- Env is testable without importing PyTorch; the core Python package stays
  zero-dependency.
- Trainer/framework choices are swappable behind the facade.

## Reversal conditions

If a chosen trainer cannot consume PettingZoo, add a thin adapter rather than
polluting the env layer with framework imports.
