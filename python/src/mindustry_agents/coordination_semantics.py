"""Shared structured coordination reason semantics."""

from __future__ import annotations

FORCED_ABANDON_REASON_TOKENS = (
    "wave",
    "readiness",
    "death",
    "lease",
    "human",
    "terminal",
    "cleanup",
)


def is_forced_abandon_reason(reason: object) -> bool:
    """Return whether an authoritative reason is a forced lifecycle exclusion."""

    normalized = str(reason).lower()
    return any(token in normalized for token in FORCED_ABANDON_REASON_TOKENS)
