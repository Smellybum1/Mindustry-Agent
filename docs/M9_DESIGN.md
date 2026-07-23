# M9 design: multi-agent learning and partner robustness

Status: accepted initial boundary under ADR-0069. This document describes the
target architecture and the staged evidence required before broader M9 claims.

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
   unchanged authoritative stepping.
2. Training precommit: exact reward, optimizer, budget, checkpoint selection,
   partner mix, and public comparison protocol are frozen.
3. IPPO construction: two independent runs reproduce checkpoint and replay
   evidence.
4. Public development evaluation: the learned all-seat team must beat the
   fixed-role scripted baseline on at least one randomized scenario family
   before MAPPO work is authorized.
5. Later M9 stages add partner-population cells, board ablation, centralized
   critic, dropout/recovery curriculum, and finally fresh sealed evaluation.

## D7. Non-negotiable invariants

External fixed stepping, one environment per JVM, simulation-thread state
ownership, structured-authoritative communication, deterministic replay,
framework-neutral environment code, and pinned engine/dependency identities
remain exact.
