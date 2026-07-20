# ADR-0001: Exact-engine fork-based monorepo

**Status:** Accepted

## Context

We need a training environment whose behaviour is the real Mindustry game, not an
approximation, and a workspace that moves cleanly between coding agents (Fable,
Codex). The full Java environment must be identifiable by a single commit.

## Decision

Use **one fork-based monorepo**: a fork of `Anuken/Mindustry` with an `upstream`
remote, pinned at tag `v159.7` (commit `c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c`,
Arc `208a754044`), on branch `coop-agent/v159.7`. Add custom modules on top.
**Never track `master`/`latest`** during experiments. Engine upgrades only in
dedicated branches with golden-replay regression.

## Alternatives considered

- **Two repos (engine fork + separate training repo)**: better license isolation
  but pays a coordination cost (version sync, cross-repo commits) before it is
  necessary.
- **Python clone of the game**: rejected — loses exactness, which is the whole
  point (brief §4.1).
- **Vendoring the engine as a binary dependency**: loses the ability to test
  engine + agent changes atomically and to read/patch engine source.

## Consequences

- Fable and Codex see one coherent workspace; one commit pins everything.
- Gradle modules depend directly on pinned engine source.
- Upstream changes remain available via the `upstream` remote.
- Larger repo; must guard against accidental upstream edits (ADR-0010).

## Reversal conditions

Split into two repositories if a separately licensed Python package is required,
or if engine updates become unwieldy to manage inside the monorepo.
