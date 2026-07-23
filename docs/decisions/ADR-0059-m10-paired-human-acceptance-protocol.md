# ADR-0059: M10 acceptance uses preassigned absent/scripted/learned blocks

**Status:** Accepted

## Context

ADR-0058 requires a paired-condition schema and scorecard targets before M10.6
acceptance sessions begin. Rating v1 binds useful per-session judgments, but its
`keep_this_team` and scripted comparison fields do not prove that the project
owner prefers agents present over agents absent on the same scenario. Pooling
unassigned sessions would also permit post-hoc condition labels, unmatched
runtimes, or order effects to masquerade as paired evidence.

M8 has not promoted a learned policy, so final acceptance play cannot start.
The comparison contract and human-only runtime can nevertheless be frozen now,
before a learned policy or human result exists.

## Decision

1. Final M10 evidence uses exactly three complete blocks. Every block contains
   `absent`, `scripted`, and `learned` conditions on one shared trial seed. The
   three orders form a Latin square: absent/scripted/learned,
   scripted/learned/absent, and learned/absent/scripted.
2. A create-new protocol is frozen from a capture-v4 reference after M8
   promotion identifies the exact learned policy. It pins engine, Arc,
   protocol, scenario, project commit, and canonical plugin/server content.
   The learned policy must be distinct from both canonical controls.
3. Capture v4 records the agent condition plus the experiment id, block,
   condition, order, and trial seed at `session_start`. These fields enter the
   capture digest. All assignment fields are present together or absent
   together. Evidence labels added after play are not authoritative.
4. The absent condition runs the same project/runtime/scenario with zero
   controlled agent units and policy id `agents-absent-human-only-v1`. It is
   restricted to captured private join mode. The scripted condition remains
   `public-greedy-candidates-v1`. The learned condition remains unavailable
   until M8 promotion and M10.5 live-seat integration.
5. Each session retains its existing digest-bound rating. After all three
   sessions in a block, one additional create-new rating binds the three
   capture digests and records direct learned-versus-absent and
   learned-versus-scripted preferences on the fixed `-2..2` scale. No identity,
   free text, chat, or wall-clock field is collected.
6. A serious acceptance block requires `serious_block=true` and all three
   per-session ratings to set `serious_session=true`. Duplicate blocks or
   capture digests fail closed.
7. Learned-versus-scripted objective acceptance requires observed paired means
   to be non-regressing for every scorecard-v1 capability metric: intervention
   rate, plan conflicts, yield latency, goal compliance, time to help, and
   announcement usefulness. Lower is better except for compliance and
   usefulness. A missing observation fails the affected metric.
8. Owner-preference acceptance requires all of the following across the three
   serious blocks:
   - learned is preferred over absent in at least two blocks and has a strictly
     positive mean rating;
   - learned is no worse than scripted in at least two blocks and has a
     non-negative mean rating;
   - `keep_this_team=true` for the learned condition in at least two blocks.
9. The report may say `passed` only when the serious-block floor, every
   objective target, and every direct-preference target pass. Protocol creation
   and human-only runtime readiness do not close an M10 roadmap checkbox.

## Alternatives

- Reuse three positive `keep_this_team` ratings: rejected because it does not
  compare agents present and absent directly.
- Compare only learned and scripted: rejected because it cannot prove the
  north-star present-versus-absent preference.
- Let the owner choose session order: rejected because condition/order effects
  would not be controlled.
- Choose a composite score after sessions: rejected as post-hoc weighting. All
  six objective dimensions must be observed and non-regressing.
- Start scripted/absent acceptance blocks before a learned policy exists:
  rejected because shared runtime pins and within-block order would be broken.

## Consequences

- Acceptance requires nine serious captures: three counterbalanced blocks of
  three conditions. Exploratory v3/v4 sessions remain useful but cannot be
  relabeled into protocol slots.
- The project now has a real human-only comparison runtime, but learned blocks
  remain fail-closed until M8 promotion and M10.5.
- The strict per-metric bar favors interpretable teammate quality over a
  compensating composite score.

## Reversal conditions

Supersede this ADR only before the first serious protocol-assigned session. A
successor must retain capture-time assignment, exact runtime/policy provenance,
direct agents-present-versus-absent judgment, counterbalancing, explicit
pre-result targets, and the existing privacy boundary.
