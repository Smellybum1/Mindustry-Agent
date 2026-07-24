# ADR-0117: Precommit M9 candidate-native on-policy relabel v1

**Status:** Accepted

## Context

ADR-0116 accepts one closed-loop-shift signal: rejected distillation update 32
matches planner v11 on 4,071/4,232 planner-visited public-dev boundaries at NLL
`0.1524716850`, but wins only 9/40 when its own actions determine later states.
The next isolated mechanism must therefore expose learning to states visited
under learned control without changing the model, expert, optimizer, roots,
budget, or construction bar.

## Decision

Freeze `m9-candidate-native-on-policy-relabel-v1`. It loads the exact rejected
distillation update-32 model **and optimizer** states as immutable training
initialization; this is neither checkpoint selection nor promotion. Over the
same deterministically shuffled 2,048 unique public train roots, the
deterministic-argmax student controls the environment. Candidate-native planner
v11 labels each same pre-action student-visited boundary but is not executed.
Eight deterministic Adam epochs per 64-episode update minimize teacher-action
NLL over actor-valid labels from that current update only. Forced controls
execute as student actions and are excluded. No replay, mixture schedule,
critic/PPO/entropy loss, sequence gradient, extra RNG, model change, root
change, or reward change is authorized.

All 32 continuation checkpoints are evaluated by deterministic argmax on the
unchanged 40 public-dev roots. At least 30 wins and mean team idle below `0.25`
are required. Replica B is authorized only if Replica A passes and must
reproduce the full run plus selected checkpoint exactly. A passing pair may
initialize only a separately precommitted IPPO successor.

Configuration/public-protocol SHA-256 values are
`7fadf9ae9130775fffebe52b86407dfeafaf47ea5e1383524818a6d0012d72d4` /
`548ba5fe1478c6cdfb40fc2c2c390a9af57f2cbd1e14d9fb9f6c620ffac38d31`.

## Constraints

- The source checkpoint file/content/model/optimizer hashes, source and
  diagnostic results, public root files/hashes, schedule, model, optimizer
  values/state, update budget, selection rule, and replica rule are frozen
  before implementation.
- Student actions alone control the environment; planner labels cannot alter
  the action bundle or task board.
- Implementation, focused state/label/action-authority tests, deterministic
  optimizer evidence, and a complete exact-commit public-only gate must be
  committed before Replica A.
- The candidate cannot promote, authorize MAPPO or human sessions, or access
  confirmation/held-out data. M8 held-out-v7 remains sealed.

## Consequences

- This construction tests only whether current-update supervision on
  student-visited states repairs the observed closed-loop gap.
- Failure prohibits Replica B and requires a separate result/decision before
  any further learned recipe.
