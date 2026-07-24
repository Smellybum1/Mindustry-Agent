# ADR-0113: Precommit M9 candidate-native distillation v1

**Status:** Accepted

Freeze `m9-candidate-native-distill-v1` as the first learned consumer of the
ADR-0112 source. The same shared recurrent M9 model is initialized at seed
9601. Candidate-native planner v11 controls 2,048 unique public train episodes
in 32 deterministic 64-episode updates. At each update, eight deterministic
Adam epochs minimize teacher-action NLL over alive boundaries with no forced
task action and an authoritatively legal teacher action. Current-model private
hidden inputs are detached at each boundary; seat death/reset semantics remain
exact. Critic, PPO, entropy, success filters, and extra RNG are absent.

Every checkpoint is evaluated by deterministic argmax on the unchanged 40
public dev roots. At least 30 wins and mean idle below 0.25 are required. If
Replica A passes, Replica B must reproduce the full run and selected checkpoint
exactly before the checkpoint may initialize a separately precommitted IPPO
successor. This experiment cannot promote, authorize MAPPO or human sessions,
or access confirmation/held-out data.

Configuration/public-protocol SHA-256 values are
`9fc15d1a0dd256452873fe7953374bb251ad1fbf172add0eb399d2c3541457e0` /
`72ced8386fdbdb8b076f95b2d2ec416235b339703b932e878b033f738942618a`.
Implementation, focused deterministic optimizer/teacher tests, and the complete
public-only gate must be committed before Replica A.
