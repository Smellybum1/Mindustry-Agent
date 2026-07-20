"""Training loops and configuration.

Will host the IPPO-then-MAPPO training pipeline, checkpointing, and model export,
driven by configs under ``configs/training/``. Imports the RL stack (the ``[rl]``
extra) and is the only layer permitted to depend on a specific learning
framework.

M8.3 provides the shadow inference/collector throughput gate. M8.4 adds the
framework-neutral selector/reward adapters, the pinned masked actor/critic,
one-seat PPO, manifests, and exact checkpoint replay. No training module is
imported by the dependency-free environment/protocol/process layers.
"""
