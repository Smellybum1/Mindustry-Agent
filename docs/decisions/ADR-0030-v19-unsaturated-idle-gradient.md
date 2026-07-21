# ADR-0030: V19 unsaturated idle gradient

**Status:** Accepted

## Context

V18 reproduced exactly and retained 9/10 construction wins, but reusable
dev-v1 rejected it. Permanent-greedy idle regressed by 0.06547793 (95% CI
+0.03188818..+0.09708444), and recovery remained uncertain against both
governed scorecards.

The selected V18 checkpoint reached the `-5.0` idle cap in eight of ten dev
episodes. At cost `0.004`, only the first 1,250 idle-agent ticks can influence
return; later differences are invisible. V17 reached the same cap in four of
ten episodes, while V16 did not reach it. This explains why another slope
increase reduced, rather than strengthened, useful differentiation.

A reusable dev-v1 diagnostic read the already-authoritative
`idle_agent_ticks_by_agent` counters without opening a confirmation or held-out
split. V18's mean per-agent idle fractions were `0.088045`, `0.174262`, and
`0.067062`, versus permanent greedy's `0.058412`, `0.031523`, and `0.043000`.
The excess is therefore dominated by downstream teammate idle, especially seat
1, rather than explicit learned-seat WAIT. The team-level idle component is the
correct causal signal, but its cap currently removes most late-episode credit
assignment.

## Decision

1. V19 keeps V18's engine/runtime contract, train/dev roots, model, optimizer,
   RNGs, schedule, checkpoint-selection rule, terminal/milestone terms,
   announcement term, abandonment term, and recovery term fixed.
2. Restore V17's idle slope `0.002` and raise the idle cap `5.0 -> 8.0`. The
   gradient now remains active through 4,000 idle-agent ticks, covering the
   observed V18 dev range without allowing full-horizon idle to outrank an
   early terminal loss.
3. Raise only the duplicate-work cap `4.0 -> 7.0`. Together with the unchanged
   `2.0` non-forced-abandon cap, capped churn costs `-9.0`, strictly worse than
   capped honest idle at `-8.0`. Normal episodes pay the unchanged `0.05` per
   duplicate.
4. Add an exact full-horizon idle-versus-busywork adversary. Historical V15/V17
   recipes are already rejected and retain their historical adversary sets;
   V18 and V19 must pass the stronger invariant. Generalize duplicate-cap
   saturation evidence to the configured cap rather than a fixed 100 events.
5. Two pinned 2,048-episode V19 replicas must reproduce checkpoint, frontier,
   model state, replay, and full-run digest exactly. Reusable dev-v1 must then
   pass construction and both permanent/matched scorecards.
6. Retire V18's unopened dev-v14. Freeze dev-v15 at globally disjoint roots
   `151001..151160` for one exclusive confirmation only after every reusable
   gate passes. Held-out-v4 remains sealed.

## Alternatives

- Another idle-slope increase was rejected because V18 proved it reaches the
  same cap earlier and removes late-episode differentiation.
- A new loss-specific reward was rejected because authoritative per-agent
  evidence attributes the failure to post-selection team idle already covered
  by the existing audited component.
- Changing scripted teammates or weakening the permanent baseline was rejected
  because it would change the accepted M8.5 comparison rather than improve the
  candidate.

## Consequences

- V19 changes reward scale only inside the existing negative, cumulative,
  simulation-thread-authored quality components. Inference behavior, masks,
  communication authority, and engine state are unchanged.
- The stronger full-horizon adversary closes a real cap-ordering gap without
  retroactively relabeling consumed candidate evidence.
- V19 may still fail construction or reusable scorecards. It stops before
  dev-v15 on any failure.

Pretraining validation passes all 44 exact-config adversaries, the full
140-test Python suite, smoke, and golden determinism. Config SHA-256 is
`4d9911a8f6dda1bb8c6a6f6a38f82bc4f64d18836a399e860ca1941db50f733f`;
adversary report SHA-256 is
`23262f5332cc9f52b9c1a58e835f6059075da5f1f7686771216f51e4df2e33f9`.

The two pinned replicas reproduce exactly and select update 24 at 9/10 wins
with mean idle 0.09911830. Checkpoint `1a9376a331b3aadc...`, model state
`510e07d964c84de0...`, replay `75bf5fb9cc34d5a6...`, full run
`4d15c3a728f33d4c...`, and direct lineage `121a7400b241ce77...` match. Cap hits
fall from V18's 8/10 selected dev episodes to 2/10 and the reusable
permanent-idle gap improves to 0.05480651, but remains definitively worse (95%
CI +0.02786525..+0.08510262). Recovery is uncertain against both scorecards and
non-forced abandonment regresses by 0.00131579. Dev-v15 therefore remains
unopened and held-out-v4 remains sealed. Reusable preflight report SHA-256 is
`cc7bfa34d06b400701530acc47fc976c9ec18af0492035ee29d90f8fc5edc16b`.
