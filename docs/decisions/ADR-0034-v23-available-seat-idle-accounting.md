# ADR-0034: V23 available-seat idle-accounting retraining

**Status:** Accepted

## Context

V22 replica A completed all 2,048 training episodes and 32 updates, then failed
the precommitted reusable-dev quality gate because every reported checkpoint had
mean idle at least `0.43868123`. The run stopped correctly: replica B did not
start, dev-v18 remained unopened, and held-out-v4 remained sealed.

The retry and real-agent-loss lifecycle corrections were semantically sound,
but honest death cleanup exposed an occupancy-metric defect. A fixed registry
seat continued increasing `agent_ticks` and `idle_agent_ticks` after its unit
was permanently dead. The resulting idle fraction charged policy behavior for
work that seat could not perform, and the same counter contaminated V22's idle
reward during training. A diagnostic re-evaluation of V22 update 17 changes
from 10/10 wins at mean idle `0.48320387` to 10/10 at `0.13474577` after the
metric correction, but a checkpoint trained with the contaminated reward cannot
be relabeled or promoted.

The runtime now partitions every fixed-seat tick: alive/available ticks increase
`agent_ticks`, dead/unavailable ticks increase `unavailable_agent_ticks`, and
only available, unassigned ticks increase `idle_agent_ticks`. Per-agent arrays
and the team ledger make the partition directly auditable. This changes reward
and observation metrics without changing engine stepping or gameplay state, so
it requires a new runtime contract and from-scratch training.

## Decision

1. V23 retrains from scratch under runtime contract
   `abandon_wait_retry_agent_death_available_idle_v4`.
2. V23 keeps V22's train/dev roots, reward coefficients and caps, quality
   intervention, model, optimizer, RNGs, schedule, checkpoint-selection rule,
   teacher coefficient, and every other config field exact. Candidate ID,
   runtime contract, and confirmation path are the only differences.
3. Two pinned 2,048-episode replicas must reproduce the selected checkpoint,
   checkpoint frontier, model state, replay, full-run digest, and direct lineage.
   A rejected quality gate must retain its complete frontier artifact.
4. Reusable dev-v1 must reach at least 9/10 construction wins, mean idle strictly
   below 0.25, and pass both permanent-greedy and matched-greedy scorecards.
5. Retire V22's unopened dev-v18. Freeze dev-v19 now at globally disjoint roots
   `191001..191160` for one exclusive confirmation only after all reusable gates
   pass. Held-out-v4 remains sealed.
6. Training may begin only after the exact-config reward adversaries, Python
   suite, pinned build, five-seed candidate-policy availability ledger, smoke,
   and determinism including negative replay pass from this precommit.

## Alternatives

- Relabeling V22 under corrected evaluation was rejected because the faulty idle
  counter also entered its training reward.
- Treating a dead seat as idle was rejected because no policy action can make an
  unavailable unit productive.
- Removing dead seats from all metrics was rejected because explicit
  `unavailable_agent_ticks` and per-agent counters preserve the full seat-time
  ledger and expose losses to audit.
- Changing reward strength, teacher coefficient, or checkpoint ranking was
  rejected because the isolated hypothesis is the metric contract correction.
- Opening dev-v18 was rejected because V22 failed before confirmation and the
  successor requires a newly frozen, untouched set.

## Consequences

- V23 changes no engine pin, task lifecycle, action mask, structured
  communication authority, simulation-thread ownership, or framework-neutral
  boundary.
- Idle reward and scorecards now measure controllable scheduling gaps only;
  forced agent-loss abandonment and recovery remain separately visible.
- V22 and its reconstructed frontier remain immutable failure evidence.
- V23 may fail reproduction, construction, or either reusable scorecard. Any
  such failure stops before dev-v19 and held-out-v4.

Pretraining validation passes all 44 exact-config reward adversaries, the full
145-test Python suite, the pinned build, five-seed candidate-policy availability
ledger, smoke, and golden determinism including the negative replay. Config
SHA-256 is
`17e741e63f9862bc9c2c8050b52635302bf1ef5a07ea47c2a794f22a7303ba45`;
adversary report SHA-256 is
`e2043acefb24a0163dc3645a56a44175cca33d1aa122d6f473b49186fb9a0e5b`.
No V23 model work began before this precommit.
