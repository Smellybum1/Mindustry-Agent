"""Training loops and configuration.

Will host the IPPO-then-MAPPO training pipeline, checkpointing, and model export,
driven by configs under ``configs/training/``. Imports the RL stack (the ``[rl]``
extra) and is the only layer permitted to depend on a specific learning
framework.

M8.3 contains only the shadow inference/collector throughput gate. Policy
optimization, rewards, and checkpointing remain gated behind M8.4.
"""
