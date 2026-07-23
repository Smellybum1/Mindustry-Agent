# ADR-0073: Precommit M9 IPPO v2 sequence-16 optimization

**Status:** Accepted

## Context

ADR-0072 rejects the exact, teacher-free `m9-ippo-v1` construction. Across
2,048 repeated public train episodes, later cycles continued to win on 15 to 28
of 64 roots while public dev performance peaked at 16/40 on update 11 and then
fell to zero. Runtime traces, manifests, optimizer states, and the full
frontier reproduced exactly across independent processes.

V1 carried a private recurrent state for each seat at runtime, but its
one-boundary optimizer treated every stored hidden input as detached rollout
data. Gradients therefore never passed from a later boundary through the
recurrent update that produced its context. That is the only M9-specific
temporal mechanism not exercised by v1 optimization and is a prospective,
architecture-grounded explanation for repeated-root learning with weak public
generalization. It is a hypothesis to test, not a retrospective claim of root
cause.

## Decision

1. Freeze the successor as `m9-ippo-v2-sequence16`. Its immutable config is
   `configs/training/m9-ippo-v2-sequence16.json`, SHA-256
   `266e50429902de0d97049eaeb80558b22bb20fffedda926e92091102489a76da`.
   Its public protocol is
   `configs/evaluation/m9-ippo-v2-sequence16-public-protocol.json`, SHA-256
   `ec9a69612b709290a339b1e44f202b65d6dabc5d47b513021ab474dee54934b0`.
2. V2 changes exactly one learning mechanism: recurrent backpropagation uses
   deterministic per-seat windows of at most 16 consecutive transitions.
   Windows are ordered by episode, then agent id, then boundary; they never
   cross an episode or authoritative seat reset. Each window starts from the
   stored rollout hidden state detached from earlier history, then recomputes
   and propagates the private hidden state through the remaining window.
3. Minibatches contain 16 right-padded windows, at most 256 real transitions.
   Padding contributes to neither actor nor critic loss. Actor-excluded forced
   boundaries remain critic-only under ADR-0071. No hidden state or gradient
   crosses seats.
4. The model architecture, ordinary ten-action vocabulary, runtime inference,
   atomic all-seat boundary, reward and every coefficient/cap, train/dev roots,
   2,048-episode/32-update budget, Adam/PPO values, four RNG seeds, torch
   single-thread pin, checkpoint ranking, and 30/40 plus idle `<0.25`
   construction bar remain v1-exact. No teacher, imitation term, initialization
   transfer, or reward change is authorized.
5. The existing 40-root dev-v1 document remains reusable public development
   evidence. It may select or reject v2 but cannot support a confirmation or
   final claim. The already frozen server-expert baseline remains the paired
   comparator.
6. Before any v2 trajectory or model update, the implementation must be
   committed and pass:
   - window construction tests proving episode, seat, reset, order, length, and
     padding boundaries;
   - a length-one equivalence test against the accepted v1 optimizer math;
   - a gradient test proving a later valid loss reaches an earlier recurrent
     step without crossing a seat/reset boundary;
   - forced-control critic-only and padding-invariance tests;
   - independent-process deterministic optimizer/checkpoint evidence;
   - the full Python and pinned Java suites, exact reward adversaries,
     all-seat parity, stochastic terminal-reset replay, smoke, determinism, and
     golden replay.
7. Replica A runs the full immutable budget after that exact-commit gate. If A
   has no eligible checkpoint, v2 is rejected and replica B does not run. If A
   passes construction, replica B must reproduce the full run, selected
   checkpoint, direct replay, and lineage before public comparison can
   authorize MAPPO.
8. MAPPO remains prohibited unless the exact replicas also satisfy the frozen
   paired win, team-return, and team-idle interval gates. No M9 confirmation or
   held-out namespace is allocated. M8 held-out-v7 remains sealed and M8-only.

## Alternatives

- Lowering the 30/40 gate or selecting v1 update 11 is rejected because it
  would redefine success after observing the result.
- Extending v1's budget is rejected because later updates already improved
  repeated-root training while public dev survival collapsed.
- Changing learning rate, entropy, PPO epochs, reward, model width, roots, and
  sequence training together is rejected because it would not isolate the
  recurrent-credit hypothesis.
- Teacher warmup is rejected for this test. The ordinary public-path greedy
  teacher lost all five architecture-parity episodes, while the stronger
  server expert does not act through the same external action surface.
- Starting MAPPO is rejected by ADR-0008 and the failed v1 performance gate.

## Consequences

- V2 is a bounded public-only test of whether the recurrent actor can learn
  temporal coordination rather than treating its history as fixed features.
- The existing v1 runner and artifacts must become candidate-aware without
  weakening v1 hash validation or checkpoint lineage.
- Failed replica A costs one full CPU run rather than two; successful
  construction still requires exact independent reproduction.
- No v2 trajectory, optimizer update, checkpoint, or model-state change exists
  at the time of this precommit.

## Reversal conditions

Reject v2 if sequence optimization cannot preserve deterministic CPU execution,
seat/reset isolation, or exact external stepping. Any further successor must be
prospectively named and frozen from public evidence; do not mutate v2 after its
first trajectory.
