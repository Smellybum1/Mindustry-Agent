# ADR-0038: V27 successful teacher-trajectory warmup

**Status:** Accepted

## Context

V24's low `0.05` full-boundary teacher coefficient peaked at 8/10 reusable
construction wins. V25 moved early optimization and teacher-relative logits at
`0.10` but still peaked at 8/10; V26 regressed to 5/10 at `0.20`. ADR-0037
therefore closes coefficient-only tuning.

Those online losses label only boundaries reached by the learned policy. A
current-runtime adaptive-v1 census over all 64 governed train-v2 roots wins
5/64 and exposes 952 unforced teacher labels in total. The five successful
trajectories contain 121 unforced labels. A deterministic diagnostic applied
eight success-only cross-entropy epochs to those 121 transitions: 968 sample
presentations in eight batches, mean cross-entropy `1.41309726238`, with a
changed model-state digest. Losing teacher trajectories were retained as
evidence but contributed no gradient.

This supports a trajectory-quality intervention, not another coefficient step:
initialize from the complete successful teacher decision sequences before the
unchanged V24 PPO construction begins.

## Decision

1. V27 retrains from scratch under runtime contract
   `abandon_wait_resource_scoped_retry_agent_death_available_idle_v5` and uses
   V24 as its exact base, including the low online teacher coefficient `0.05`.
2. Before ordinary PPO, adaptive-v1 controls the learned seat for one separately
   shuffled cycle over all 64 train-v2 roots. Only unforced transitions from
   winning episodes enter eight deterministic cross-entropy epochs with
   minibatch size 128. Warmup shuffle/minibatch seeds are `8605`/`8606` and do
   not consume ordinary action-sampling or PPO-minibatch RNG state.
3. The same Adam instance continues from warmup into PPO. The atomic warmup
   report, pre/post model-state digests, schedule, episode summaries, and
   optimizer metrics join full-run reproducibility evidence.
4. Candidate ID, quality label, confirmation path, and six warmup coordinates
   are the only differences from V24. Reward, runtime, train/reusable-dev roots,
   model, ordinary optimizer and RNG coordinates, schedule, checkpoint
   selection, and inference remain exact.
5. Replica B starts only if replica A reaches at least 9/10 reusable construction
   wins with mean idle below 0.25. Passing replicas must reproduce warmup
   evidence, checkpoint, complete frontier, model state, replay, full-run
   digest, and direct lineage.
6. Reusable preflight still requires both permanent-greedy and matched-greedy
   scorecards before any one-way confirmation. Retire V26's unopened dev-v22;
   freeze dev-v23 at globally disjoint roots `231001..231160`. It remains
   unopened until every reusable gate passes. Held-out-v4 stays sealed.
7. Training may begin only after exact-config reward adversaries, the Python
   suite, pinned build, five-seed candidate gate, smoke, and determinism
   including negative replay pass from a committed packet.

## Alternatives

- Another full-boundary coefficient was rejected because ADR-0037 closed that
  line after V26 regressed.
- Warming on all 952 labels was rejected because losing teacher trajectories do
  not demonstrate the demo-survival sequence V27 is intended to transfer.
- Changing reward, runtime, model capacity, PPO budget, or root membership was
  rejected because it would confound the initialization test.
- Opening dev-v22 was rejected because V26 failed before confirmation.

## Consequences

- V27 adds 64 training-only environment episodes and a bounded deterministic CE
  warmup, but keeps the 2,048-episode/32-update PPO construction exact.
- Reward, evaluation action selection, externally stepped timing, simulation-
  thread ownership, communication authority, masks, lifecycle, and engine pins
  remain unchanged.
- Construction failure retires dev-v23 unopened. Construction success still
  authorizes only exact reproduction and reusable preflight, never direct
  confirmation or held-out access.

No V27 model work began before this precommit.

Pretraining validation passes all 44 exact-config reward adversaries, the full
152-test Python suite, the pinned build, five-seed candidate-policy gate, smoke,
and golden determinism including the negative replay. Config SHA-256 is
`189ef438574524946d41828b168c60ee850a4fc997c2f513613cc11c89091124`;
adversary report SHA-256 is
`d1c1da02ed7d3a4ed6ca5c6e82bce8fa942f9844b8ec2dd43b53027861e6ea6b`.
