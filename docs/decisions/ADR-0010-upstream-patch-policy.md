# ADR-0010: Upstream patch policy

**Status:** Accepted

## Context

This is a fork of a live upstream project. Uncontrolled edits to engine files
would make rebasing onto new Mindustry releases painful and would obscure exactly
what we changed and why — a reproducibility and licensing hazard.

## Decision

- **Prefer new modules and adapters over editing core files.**
- **Every direct modification to an upstream file must be listed in
  `docs/UPSTREAM_PATCHES.md`** with reason and diff summary, in the same commit.
- Keep engine patches small and purpose-specific.
- **Never hand-edit generated `mindustry.gen` classes.**
- **Engine upgrades happen only in dedicated branches** with deterministic
  (golden-replay) and behavioural regression tests.
- Do not update the engine during an active training comparison.

## Alternatives considered

- **Freely edit upstream where convenient**: rejected — destroys rebase-ability
  and auditability.
- **Never touch upstream at all**: impractical — at minimum `settings.gradle`
  must register new modules; the policy allows minimal, catalogued edits.

## Consequences

- The delta from upstream stays small and auditable (supports the GPL
  source-availability obligation, `NOTICE.md`).
- Engine upgrades are deliberate, tested events, not incidental drift.
- Slightly more process overhead for any upstream edit.

## Reversal conditions

None. If the fork is ever split from the training code (ADR-0001 reversal), this
policy still governs the engine repository.
