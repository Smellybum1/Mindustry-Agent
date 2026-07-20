"""Policies.

Will provide scripted, heuristic, random-valid, IPPO, and MAPPO policies over
the high-level task-selection action space. Scripted baselines come before any
learning (ADR-0008); IPPO before MAPPO. Only the learning policies import an RL
framework — the scripted/random-valid baselines stay dependency-light.

Currently a skeleton package; baselines land in roadmap M6-M7.
"""
