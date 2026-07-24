# ADR-0127: Precommit M9 sequence relabel v1

**Status:** Accepted

## Context

The exact rejected update-64 student-state relabel checkpoint fits planner v11
labels well but wins only 13/40 public-dev episodes. Its optimizer presents
independently shuffled boundaries with the stored recurrent hidden input
detached at every example. Fixed disagreement reweighting failed construction,
and ADR-0126 records that online planner correction reduced both primary
checkpoints to 9/40. The supported next question is recurrent sequence
coherence, not more pressure on particular disagreements or planner takeover.

The repository already has a tested 16-boundary truncated recurrent optimizer
contract for PPO. That prior infrastructure establishes deterministic
non-overlapping per-seat windows, stored detached initial hidden state, and
right-padding behavior. This decision adapts only that sequence presentation
to the existing unweighted planner-label NLL. It does not import PPO rewards,
advantages, critic loss, entropy, or action sampling.

## Decision

Freeze `m9-candidate-native-sequence-relabel-v1` before implementation or model
work. It initializes the exact rejected update-64 model and Adam optimizer
states without selecting, repairing, or promoting that checkpoint.

The same deterministically shuffled 2,048 unique public train roots run for 32
updates of 64 episodes. The deterministic student controls the environment and
planner v11 labels the same pre-action student-visited boundaries. Every alive
student-evaluated seat boundary is retained as recurrent context. Teacher NLL
is active only on the unchanged actor-authoritative eligible labels; forced
student actions remain executed and are loss-masked context.

Within each episode and seat, boundaries remain in temporal order and split at
an authoritative recurrent reset or after 16 real transitions. Windows never
overlap or cross seats/episodes. Windows containing no eligible teacher label
are omitted. Each retained window starts from its stored rollout hidden state,
detached once, and recomputes private hidden state through its real boundaries.
Gradients from eligible teacher labels may flow only through preceding real
context in that same window. Right-padding follows the last real step and is
excluded from both context and loss.

Sixteen windows form a minibatch of at most 256 real slots. Each minibatch
minimizes summed eligible teacher-action NLL divided by its eligible-label
count. Windows are shuffled with the existing seed-9613 generator for the same
eight epochs. Partial final minibatches are allowed; every retained minibatch
must contain at least one eligible label. No example weighting is applied.

Everything else is inherited exactly from
`m9-candidate-native-on-policy-relabel-v1`: planner, features, masks, model,
optimizer values and state, learning rate, roots and schedule, deterministic
student control, episode/update budget, dev roots, checkpoint ranking, 30/40
construction floor, idle threshold, and conditional replica policy.

Configuration/public-protocol SHA-256 values are
`b7e17a6e74b6d18a261d7d4845dcff8d808ffef830641e0c4fb21dbe327233d1` /
`b79f6da9c24863d0765e127678f45471ca78fe9a215a26fe0fa15105951a261e`.

Replica A may start only after implementation and focused tests are committed,
length-one sequence presentation is checkpoint-exact with the existing flat
teacher NLL, deterministic configured-sequence optimizer replicas match, a
live terminal reset repeats, and the complete public-only exact-current-commit
preflight passes. Replica B is authorized only if Replica A reaches at least
30/40 wins and the idle threshold; otherwise it is prohibited. An authorized
Replica B must reproduce the full run and selected checkpoint exactly.

## Constraints

- The source checkpoint file/content/model/optimizer hashes, source
  manifest/result, ADR-0126 diagnostic, config/protocol, seed files, schedule,
  model, optimizer, budget, and replica policy are frozen and fail closed.
- Only recurrent optimizer presentation changes. No target identifier,
  candidate, feature, mask, planner, action authority, example weight, EMA,
  replay, learning rate, reward, critic, entropy, PPO, MAPPO, root, budget, or
  extra RNG change is authorized.
- Update 64 remains rejected, unselected, unrepaired, and unpromotable.
- No confirmation, held-out, or learned human-session access is authorized.
  M8 held-out-v7 remains sealed.
- A passing exact replica pair may initialize only a separately precommitted
  downstream successor.

## Consequences

Implementation may add one fail-closed sequence collector/optimizer,
checkpoint/manifest path, commands, tests, and public preflight. No candidate
trajectory, optimizer update, changed model state, or restricted-data access
preceded this precommit. Failure at Replica A must be recorded honestly and
prohibits Replica B.
