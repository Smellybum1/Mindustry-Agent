# M9 design: multi-agent learning and partner robustness

Status: initial architecture boundary implemented and verified under ADR-0069;
the immutable IPPO optimization/reward/public-comparison recipe was frozen by
ADR-0070. ADR-0071 corrected a pre-update forced-control validator incident and
retired A0. The exact correction-commit gate then passed, and clean 2,048-
episode replicas A1/B1 completed with byte-identical manifests and canonical
full-run digest `186b7745c079f85a...`. ADR-0072 rejects `m9-ippo-v1`: its best
public checkpoint reached only 16/40 dev wins versus the required 30/40 and
the fixed expert's 36/40. No checkpoint was selected, MAPPO is unauthorized,
and no confirmation or held-out data was accessed. ADR-0073 prospectively
freezes `m9-ippo-v2-sequence16`: the sole learning change is deterministic
16-boundary truncated recurrent backpropagation within one seat and reset
segment. Its implementation and complete public-only pretraining gate now pass;
Replica A completed and ADR-0074 rejects v2 after an 11/40 best public result.
Replica B did not run, no checkpoint was selected, and MAPPO remains blocked.
ADR-0075 then froze the unique-root v3 test. Its exact gate passed and Replica
A completed, but every deterministic public-dev checkpoint was 0/40; ADR-0076
rejects v3 and prohibits Replica B.
This document describes the target architecture and the staged evidence
required before broader M9 claims.

## Scope

M9 removes M8's one-learned-brain constraint. All three controllable seats use
one parameter-shared policy, with seat identity and private temporal state
supplied as inputs. IPPO is implemented and evaluated before any centralized
critic is introduced. Partner-population training, communication ablation,
MAPPO, and robustness curriculum remain later M9 items.

M8 remains not promoted. Its checkpoints and public diagnostics may inform
architecture, but its sealed held-out-v7 membership is unavailable to M9.

## D1. Authoritative boundary

At a decision boundary the client receives one immutable observation bundle,
one action-mask bundle, the structured task board, and structured boundary
reasons. It builds features for alive seats in ascending agent-id order, runs
the same model parameters once per alive seat, and submits the three resulting
task actions in one `StepRequest`. Dead seats use the existing lifecycle-safe
action. The server applies the bundle on the simulation thread before the next
fixed-step advance.

No seat may observe another seat's newly selected action before choosing its
own action at that boundary. Coordination information comes only from the
authoritative pre-step board, observations, and bounded private history.

## D2. Parameter sharing and role context

There is exactly one actor/critic parameter set per environment process.
Every seat uses the same candidate encoder and action heads. A learned
three-entry role embedding distinguishes seats without creating seat-specific
models. Run telemetry records the model-state digest and verifies that every
seat references it.

The initial M9 model uses the ordinary ten-action selector vocabulary:
eight candidate slots, CONTINUE, and WAIT. Expert-DEFER is not present.

## D3. Hidden state

Each seat owns a fixed-width recurrent state. States begin at exact zeros on
reset, update only from that seat's boundary features, and reset independently
when the seat dies. A state is never transferred or copied to another seat.
Training initially uses deterministic one-boundary truncation: the hidden input
stored with a transition is treated as rollout state while gradients update the
shared recurrent cell and heads for that boundary. Longer sequence unrolling
requires a later measured change, not an implicit trainer variation.

## D4. IPPO data and rewards

One environment episode yields a time-ordered transition stream per seat.
The actor and local critic are parameter-shared; advantages are computed per
seat across that seat's decision sequence. The team reward is shared. Any
individual shaping must be a separately metered, capped component in
`docs/REWARD_AUDIT.md` before training and must not change environment or
scorecard semantics.

The first immutable training recipe will be committed only after the all-seat
runtime boundary passes ADR-0069 item 9. Replica A and B must use identical
public train/dev documents, schedules, optimizer values, RNG streams, engine
pins, and dependency lock.

## D5. Seed governance

- Train v1: 64 public roots in `[18B,19B)`.
- Dev v1: 40 public roots in `[19B,20B)`.
- Neither may support a final promotion claim.
- Confirmation and held-out namespaces are not allocated yet.
- M8 held-out-v7 remains sealed and unavailable.

## D6. Evidence stages

1. Architecture boundary: unit tests and real-JVM teacher-controlled parity
   prove shared parameters, private state, deterministic action order, and
   unchanged authoritative stepping. **Complete 2026-07-23:** 375 Python tests,
   pinned Java checks, five direct/traversed JVM pairs, 1,424 alive-seat model
   evaluations, repeated terminal-reset replay, smoke, deterministic replay,
   and 40 reward adversaries pass. The shared model digest is
   `e82745a19729aa3183df197cb91c5e2fa9ba17ee334748b979d6d623e402de21`.
2. Training precommit: **complete 2026-07-23.** ADR-0070 freezes the exact
   reward, optimizer, 2,048-episode budget, checkpoint selection, no-teacher
   decision, and public fixed-role comparison protocol. Implementation,
   adversaries, baseline evidence, and the full gate must be committed before
   training.
3. IPPO construction: reward/rollout/optimizer boundary complete 2026-07-23.
   The hash-bound loader, per-seat cumulative reward, private-seat GAE,
   stored-hidden one-boundary optimizer, stochastic real-JVM rollout, and six
   individual-reward adversaries pass. The rollout repeats exactly after
   terminal combat reset. Run/checkpoint manifest orchestration and exact
   checkpoint replay are now implemented: canonical model/optimizer/content
   lineage and path-independent manifest evidence reproduce across processes
   and fresh JVMs. The full runner now enforces exact-commit preflight
   authority, 32 deterministic all-root cycles, per-update public dev frontier,
   eligible-only selection, progress telemetry, paired bootstrap comparison,
   two fresh-JVM selected-checkpoint replays, per-file serializer integrity, and
   canonical semantic replica identity. Clean replicas A1 and B1 completed all
   2,048 public training episodes and 32 updates each. Their raw manifests are
   byte-identical and their canonical full-run digest is
   `186b7745c079f85a...`.
   The fixed server-expert baseline is frozen from implementation commit
   `dea79c487a`: 36/40 public wins, mean core `967.95`, mean team return
   `-1.641725`, exact terminal-reset replay, report `ba4c9182f346a6ee...`.
   The first authorized A0 attempt stopped after 64 collected train episodes
   and before GAE/optimizer execution. ADR-0071 preserves forced ABANDON as a
   policy-loss-masked critic boundary, retains strict mask validation for actor
   samples, and retires A0. The replacement exact-commit gate passed before the
   clean runs.
4. Public development evaluation: the learned all-seat team must beat the
   fixed-role scripted baseline on at least one randomized scenario family
   before MAPPO work is authorized. **V1 rejected 2026-07-23:** no checkpoint
   reached the frozen 30/40 construction floor. Update 11 was best at 16/40,
   mean return `-7.878245`, and idle `0.14656396`; later development survival
   collapsed to zero while repeated-root training survival continued. ADR-0072
   records the reproducible public generalization failure. A separately
   governed IPPO successor is required; MAPPO remains blocked.
   **V2 precommitted 2026-07-24:** ADR-0073 holds the v1 model, reward,
   roots, budget, optimizer, RNGs, selection, and public comparison fixed while
   replacing detached one-boundary optimization with deterministic sequence-16
   windows. Windows cannot cross seats, episodes, or authoritative seat resets;
   padding is loss-masked. Implementation, focused gradient/isolation tests,
   and the complete exact-commit gate must pass before replica A.
   The sequence optimizer and candidate-aware checkpoint/runner boundary are
   now implemented locally. Authoritative reset markers are emitted by private
   seat state, windows partition every transition without crossing a reset,
   and right padding is excluded from both losses. Focused tests prove
   length-one v1 equivalence, cross-boundary gradient flow, padding invariance,
   v2 checkpoint/config binding, and deterministic twin updates; the full
   Python suite passes 397 tests. Two public-free synthetic workers rerun from
   exact implementation commit `9428d90055` and reproduce model state
   `b5495c745f29c311...`, optimizer state `95fdc80083899212...`, and canonical
   checkpoint `bb134fd817965992...`; report SHA is `580493699e7c342b...`.
   The v2 preflight/training packet is committed. The complete public-only gate
   passed at implementation commit `bd28be1b8f`: 397 Python tests, pinned Java
   checks, every focused M9 check, live smoke, cross-process/reset determinism,
   and the M6 golden replay are green. The versioned result SHA is
   `70cbefcc779bea60...`; it records no confirmation or held-out access. Because
   the evidence commit changes HEAD, the same complete gate must pass once more
   at that exact commit before replica A starts.
   **V2 rejected 2026-07-24:** the final exact-commit gate passed at
   `e6a29fb351`. Replica A completed 2,048 episodes and 32 updates, but its best
   public result was update 2 at 11/40 wins, return `-14.70004`, core `260.425`,
   and idle `0.29205803`; final performance was 0/40. Training won 513/2,048,
   below v1's 598. ADR-0074 rejects v2, blocks replica B and MAPPO, and records
   compact result SHA `42b4a2c4ee6eb542...`. No confirmation or held-out data
   was accessed.
   **V3 precommitted 2026-07-24:** ADR-0075 returns to v1's accepted
   one-boundary optimizer and changes only train-root diversity. The exact
   2,048-episode budget now contains 2,048 unique public train roots shuffled
   once by the existing seed 9603 and sliced into 32 updates of 64. Model,
   reward, PPO values, dev roots, thresholds, and comparator remain exact.
   Config/protocol/train-root hashes are `5d437c390fc54423...`,
   `29085f124d958f56...`, and `2e4d5b853ba9c8a6...`. Candidate-aware
   config/checkpoint/manifest/training
   authority is committed at `f32cba6f72`. The shared schedule validator proves
   exact membership, zero v1-train/dev overlap, one-use coverage, deterministic
   32-by-64 slicing, and schedule digest `a58244f31f21c24b...`; focused tests
   prove v1 optimizer dispatch and fail-closed v3 authority. Its twice-identical
   implementation-bound report is committed with SHA `e8334ee662e718b7...`.
   The complete 404-test Python suite and full gate passed at exact commit
   `89de310520`. Replica A then completed 2,048 unique-root episodes and 32
   updates. Every deterministic public-dev checkpoint was 0/40; update 29 was
   best by return at `-14.022125`, core `0.0`, and idle `0.12201736`.
   Stochastic training won 585/2,048, close to v1's 598. ADR-0076 rejects v3,
   prohibits replica B and MAPPO, and records compact result SHA
   `2e3ed1c113bcd1c0...`. No restricted data was accessed. A bounded
   precommitted public diagnostic of stochastic-policy survival versus
   deterministic argmax collapse is next. ADR-0077 freezes that diagnostic:
   immutable v3 update 29, the same 40 public dev roots, one argmax stream,
   four categorical streams with seeds 9602/19602/29602/39602, and two
   exact fresh-JVM runs. At least 32/160 stochastic wins denotes a diagnostic
   sampling signal but cannot repair or promote v3. No diagnostic episode has
   run yet. Fail-closed source/checkpoint/root validation, immutable-model
   execution, exact twin-JVM comparison, and focused tests are implemented
   at `8f574ef2b6`. Both fresh-JVM runs reproduce at digest `8b0b5fdd9083953d...`.
   Argmax remains 0/40, while fixed categorical sampling wins 56/160 with
   all four streams contributing 11--17 wins. ADR-0078 accepts the predeclared
   sampling signal but keeps v3 rejected. Compact result SHA is
   `50c823d2d3d6123d...`; no restricted data was accessed. The recommended v4
   isolates entropy annealing toward zero over the unchanged v3 recipe and
   requires a separate precommit before model work.
   **V4 precommitted 2026-07-24:** ADR-0079 freezes
   `m9-ippo-v4-entropy-anneal`. V4 inherits v3 exactly and changes only the
   entropy coefficient from constant 0.02 to the inclusive linear schedule
   `0.02 * (32 - update) / 31` across updates 1--32. Config/protocol hashes are
   `9b9495e03b11e0fd...` and `db9b5647f249d308...`. Collection remains
   categorical and public dev remains deterministic argmax. The full gate
   passed at evidence commit `fbca0c6bbc`; Replica A then completed all 2,048
   public episodes and 32 updates. The late frontier improved to 16/40 at
   update 30 and 18/40 at update 31, with update-31 idle `0.09766800`, before
   the zero-entropy update 32 collapsed to 0/40. ADR-0080 rejects v4 and
   prohibits Replica B. Compact result SHA is `e85eb1d267412db4...`; no
   restricted data was accessed. A prospectively frozen immutable-v4
   late-checkpoint diagnostic is required before any v5 recipe.
   **Late-checkpoint diagnostic precommitted 2026-07-24:** ADR-0081 freezes
   immutable updates 31 and 32 across one argmax plus four fixed categorical
   streams on the 40 public roots, twice in fresh JVMs. Frozen 80%-retention and
   50%-collapse rules distinguish mode instability from optimizer-distribution
   collapse. Protocol SHA is `d68fee034d3b90e7...`; the diagnostic has no
   candidate repair, selection, training, promotion, or restricted-data
   authority. Fail-closed source validation, immutable-model execution, exact
   twin-JVM comparison, and classification are implemented locally; all 420
   Python tests pass. The two fresh JVMs reproduce exactly at digest
   `a69c48c6120b87f1...`. Update 31 is 18/40 argmax and 64/160 categorical;
   update 32 is 0/40 argmax but 60/160 categorical, retaining 93.75%. ADR-0082
   accepts deterministic mode instability, keeps v4 rejected, and recommends
   a separately precommitted success-conditioned self-imitation mechanism.
   Compact result SHA is `7273098097889601...`; no restricted data was
   accessed.
   **V5 precommitted 2026-07-24:** ADR-0083 freezes
   `m9-ippo-v5-success-imitation`. V5 inherits v4 and changes only one learning
   mechanism: add coefficient `0.02` times sampled-action NLL for actor-valid
   transitions from winning episodes in the current 64-episode update. Losses,
   forced controls, prior updates, replay, teachers, extra passes/RNGs, and
   restricted data are excluded. Config/protocol SHA prefixes are
   `056a6ee24363b55a...` and `205508d8cfaba910...`. Implementation commit
   `d6969679ad` adds only that optimizer term and its authoritative telemetry.
   Ten focused tests pass; fresh twin CPU probes are byte-identical at report
   SHA `c8676245cee741f0...` and optimizer digest `27bd5804b512ccf1...`.
   The full public gate passed at `84af0016f6`. Replica A completed the exact
   budget, but its deterministic public-dev best was only 1/40 at update 7 and
   its final was 0/40. ADR-0084 rejects v5 and prohibits Replica B. Compact
   result SHA is `f969cb595526763c...`; no restricted access occurred. An
   immutable-v5 public diagnostic must be separately precommitted before v6.
   ADR-0085 freezes that diagnostic before execution: updates 7 and 32, the
   same public roots, one argmax plus four fixed categorical streams, two
   fresh JVMs, descriptive chosen-action probability/top-two logit margins,
   and exact retained-versus-eroded classification. Protocol SHA is
   `9a9b44e36a22d68d...`. Its fail-closed runner, measurement path,
   classification, command, and four focused tests are implemented at
   `e0efa3ac70`; all 434 Python tests pass. Two fresh JVMs reproduce exactly:
   update 7 is 1/40 argmax and 51/160 categorical, while update 32 is 0/40
   argmax but 62/160 categorical. ADR-0086 accepts retained stochastic success
   without deterministic consolidation. Compact result SHA is
   `0c0cbe21a53bf7d6...`; no restricted access occurred. A separately
   precommitted strongest-alternative margin mechanism is next.
   ADR-0087 now freezes `m9-ippo-v6-success-margin`: exact v4 plus coefficient
   `0.02`, target `0.1` hinge loss that pushes each current-update winning
   actor action above the strongest other legal action. V5's NLL is absent.
   Config/protocol SHA prefixes are `bd8e84acd0e340b6...` /
   `f0adddd4c8b2127a...`. Implementation commit `05e6b48772` adds the exact
   margin/filter/telemetry and preserves v1--v5. Nine focused tests and fresh
   byte-identical CPU probes pass; report SHA is `4dc0463838756789...` and
   optimizer digest is `c11f5ecf0de81d2f...`. The full gate passed at
   `f805e52842`, then Replica A completed all 2,048 episodes and 32 updates.
   Its deterministic public best was only 2/40 at update 29 and its final was
   0/40. ADR-0088 rejects v6 and prohibits Replica B. Compact result SHA is
   `37f3ecd470f7580a...`; no restricted access occurred. V5 and v6 now bound
   the failure of treating every actor-valid transition in a winning
   stochastic episode as a desirable deterministic label. A public-only
   v1--v6 design synthesis is complete in `docs/M9_V1_V6_SYNTHESIS.md`.
   ADR-0089 freezes the next diagnostic before execution: expose the strong
   36/40 internal shared expert's simulation-thread decisions, require unique
   same-boundary semantic projection to actor-valid ordinary candidates, and
   replay them exactly through the external action path in two fresh JVMs.
   Protocol SHA is `3aea109ad7d876fb...`. Implementation commit `6d9bd3708b`
   passed the complete gate. Two fresh JVM source runs reproduced 36/40 wins,
   but only 65/3,833 selections projected uniquely, including 51/3,585 from
   winning episodes; the thresholds failed before replay. ADR-0090 rejects
   direct shared-expert distillation. Compact result SHA is
   `1d8eb99978ebf148...`. A separately governed candidate-native planner is
   required before v7; no restricted access occurred.
   **Candidate-native source accepted 2026-07-24:** ADR-0112 accepts planner
   v11 at 32/40 public wins, exact twin-JVM/reset replay, zero action defects,
   and 96.5548% coverage. It is a supervision source only. ADR-0113 freezes a
   separate 2,048-root candidate-native behavioral-cloning warm start before
   any resumed PPO. Configuration/public-protocol SHA prefixes are
   `9fc15d1a0dd25645...` / `72ced8386fdbdb8b...`. Its deterministic teacher
   collector/optimizer/checkpoint/replica path and exact-commit preflight are
   implemented. At implementation commit `9583796ee1`, all 486 Python tests,
   the live terminal-reset teacher probe, pinned Java checks, smoke,
   cross-process determinism, and the 664-checkpoint golden replay pass.
   Preflight result SHA is `d18cf46b03449f25...`; rerun it at the evidence
   commit before Replica A.
5. Later M9 stages add partner-population cells, board ablation, centralized
   critic, dropout/recovery curriculum, and finally fresh sealed evaluation.

## D7. Non-negotiable invariants

External fixed stepping, one environment per JVM, simulation-thread state
ownership, structured-authoritative communication, deterministic replay,
framework-neutral environment code, and pinned engine/dependency identities
remain exact.
