# M9 IPPO v1--v6 public design synthesis

Date: 2026-07-24
Classification: public construction evidence only
Restricted access: none

## Outcome

M9's all-seat parameter-shared recurrent boundary is sound, but the completed
v1--v6 line has not learned a deterministic policy that reliably reproduces a
surviving coordination sequence. The next experiment should change the source
of action supervision. It should not retune PPO, entropy, successful-episode
NLL, or successful-action margin coefficients.

## Evidence

| Candidate | Sole design coordinate | Best public dev | Result |
|---|---|---:|---|
| v1 | teacher-free one-boundary IPPO, 64 roots repeated | 16/40 | rejected |
| v2 | sequence-16 recurrent backpropagation | 11/40 | rejected |
| v3 | 2,048 unique training roots | 0/40 | rejected |
| v4 | inclusive entropy anneal `0.02 -> 0.0` | 18/40 | rejected |
| v5 | winning-transition sampled-action NLL | 1/40 | rejected |
| v6 | winning-transition strongest-other margin | 2/40 | rejected |

V3, v4, and v5 diagnostics show that categorical policies retain successful
rollouts after deterministic argmax degrades. V5 and v6 then apply two
different objectives to every actor-valid transition from a winning episode;
both sharply underperform v4's deterministic frontier. Terminal success is
therefore too coarse to turn every sampled transition into a deterministic
label.

The ordinary Python/Java greedy candidate policy is action-path compatible but
lost all five randomized M9 architecture-parity episodes. The frozen
simulation-thread `ExpertCoordinationDriver` instead wins 36/40 on the public
M9 dev roots, but it currently owns skills internally rather than submitting
ordinary candidate actions. Earlier M8 teacher work does not settle this
question: it trained one learned seat against different partners and a weak
adaptive teacher corpus, while M9's source expert is the strong all-seat
structured driver.

## Recommended next boundary

Before any v7 model work, test whether the strong structured expert is a valid
source of candidate-native labels:

1. expose its `SELECT_TASK` decisions as additive structured telemetry on the
   simulation thread;
2. match each decision to exactly one actor-valid candidate in the
   same-boundary authoritative M9 catalog using agent, task type, and semantic
   target only;
3. reject ambiguity instead of resolving it with utility, outcome, or a WAIT
   fallback;
4. replay the projected semantic sequence through ordinary external candidate
   actions in two fresh JVMs; and
5. require full winning-episode projection coverage, at least 95% coverage
   overall, all projected actions accepted, semantic sequence parity, and at
   least 30/40 replay wins while retaining at least 80% of source-expert wins.

ADR-0089 and protocol SHA-256
`3aea109ad7d876fb4f0b220162a8b545a0adf2e0de5ea7d6f823e28d21369dc9`
freeze that diagnostic. Passing would support, but not itself authorize, a
separately precommitted v7 candidate-native distillation corpus. Failing would
close legacy-expert projection and require a new candidate-native planner
before learning resumes.

## Projection result

ADR-0090 records the completed negative diagnostic. Two fresh JVM source runs
reproduced the expert's 36/40 wins, but exact candidate projection covered only
65/3,833 selections overall and 51/3,585 selections in winning episodes.
BUILD_LINE, BUILD_SCHEMATIC, and SUPPLY_TURRET had zero unique matches. The
frozen thresholds failed before replay, so direct legacy-expert distillation is
closed. The recommended new supervision source is now a separately governed
planner that itself acts through ordinary authoritative candidates and masks.

## Preserved boundaries

External fixed stepping, one environment per JVM, simulation-thread ownership,
structured-authoritative communication, deterministic replay, the ordinary
ten-action actor vocabulary, engine/dependency pins, public-only governance,
and the sealed M8 held-out-v7 state remain unchanged.
