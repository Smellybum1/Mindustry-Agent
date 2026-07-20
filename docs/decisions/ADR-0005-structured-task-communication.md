# ADR-0005: Structured task communication; readable text rendered from structure

**Status:** Accepted

## Context

Agents must coordinate (who does what, who helps whom). The channel must be
reproducible, action-maskable, and faithful to actual commitments. Free-form
natural language fails all three in a training loop.

## Decision

The **authoritative communication channel is a typed, versioned protocol of
coordination acts on a shared task board** (`agentcore.CoordinationAct`, 13 acts;
required announcement fields per brief §11.3). **Human-readable announcements are
rendered from that structure**, never parsed back into it. **No LLM in the
training loop.**

## Alternatives considered

- **Free-form text / LLM messages in the loop**: rejected — slow, expensive,
  irreproducible, hard to action-mask, can emit text not matching real
  commitments (brief §4.3).
- **No explicit communication (implicit coordination only)**: rejected — we want
  to study and measure structured cooperation.

## Consequences

- Deterministic, maskable, auditable coordination; easy to log and replay.
- Natural-language parsing can be added later as an optional human interface that
  translates a human request into a validated structured goal.

## Reversal conditions

Add an NL layer only as a human-facing translator outside the training loop; the
structured channel remains authoritative regardless.
