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
   `29085f124d958f56...`, and `2e4d5b853ba9c8a6...`. No v3 trajectory or
   optimizer update exists; implementation and the exact-commit gate are next.
5. Later M9 stages add partner-population cells, board ablation, centralized
   critic, dropout/recovery curriculum, and finally fresh sealed evaluation.

## D7. Non-negotiable invariants

External fixed stepping, one environment per JVM, simulation-thread state
ownership, structured-authoritative communication, deterministic replay,
framework-neutral environment code, and pinned engine/dependency identities
remain exact.
