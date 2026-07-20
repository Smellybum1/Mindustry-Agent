"""Training loops and configuration.

Will host the IPPO-then-MAPPO training pipeline, checkpointing, and model export,
driven by configs under ``configs/training/``. Imports the RL stack (the ``[rl]``
extra) and is the only layer permitted to depend on a specific learning
framework.

Currently a skeleton package; training lands in roadmap M7+.
"""
