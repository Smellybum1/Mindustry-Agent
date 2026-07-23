# ADR-0071: Treat forced control boundaries as critic-only M9 transitions

**Status:** Accepted

## Context

The first exact `m9-ippo-v1` replica-A attempt passed the complete gate from
commit `add8c278a2`, then collected its first 64 public train episodes. It
aborted before the first optimizer update because transition validation
required every recorded action to be legal in the learnable ten-action mask.

That requirement is wrong for an already accepted boundary. When a live skill
is blocked and server authority permits abandonment, feature construction
forces `ABANDON`, excludes the boundary from actor loss, and continues to expose
the ordinary learnable action mask. `ABANDON` is not an actor action; the
existing bookkeeping maps non-select/non-continue control actions to index 9.
WAIT can be illegal at that boundary, so index 9 is intentionally outside the
actor mask. The critic still needs the boundary reward and value target.

The aborted attempt produced no optimizer update, checkpoint, manifest, model
change, or performance inference. Its public-only incident record is
`configs/evaluation/m9-ippo-v1-aborted-attempt-a0.json`. No confirmation or
held-out data was accessed.

## Decision

1. Every IPPO transition must retain an in-range action index and a nonempty
   authoritative actor mask.
2. A transition with `policy_loss_mask=true` must also have its recorded action
   inside that mask. This remains the fail-closed learned-actor invariant.
3. A forced transition with `policy_loss_mask=false` may carry an out-of-mask
   placeholder action index. It contributes reward and a value target to the
   shared local critic, but contributes no policy ratio or entropy objective.
4. Forced server action behavior, action masks, reward values, roots, episode
   budget, optimizer values, RNG streams, architecture, and checkpoint
   selection remain unchanged. This is a validator correction implementing the
   already accepted forced-control semantics, not a new training recipe.
5. Replica A0 is retired. Replica A restarts from initial model/optimizer/RNG
   state in a new output directory only after this correction, its regression,
   and the incident documentation are committed and the complete pretraining
   gate passes from that exact commit.

## Alternatives

- Dropping forced boundaries is rejected because it discards authoritative
  rewards and value targets.
- Pretending `ABANDON` is WAIT or another legal actor action is rejected because
  it would train the policy on an action it did not choose.
- Adding ABANDON to the actor vocabulary is a recipe/architecture change and
  would require a prospective successor, not an incident fix.
- Declaring `m9-ippo-v1` a performance failure is rejected because no optimizer
  update, checkpoint, candidate evaluation, or inspected outcome was produced.

## Consequences

- A focused regression must reproduce forced blocked-ABANDON with WAIT masked,
  prove actor exclusion, run GAE and an optimizer step successfully, and still
  reject the same out-of-mask action when actor loss is enabled.
- The exact full gate must be rerun before any replacement replica episode.
- The aborted A0 output remains local and its hash-bound incident evidence is
  versioned. Replica comparison uses only the clean restarted A/B runs.
