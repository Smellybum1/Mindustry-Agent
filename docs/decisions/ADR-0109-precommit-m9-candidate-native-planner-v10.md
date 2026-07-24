# ADR-0109: Precommit M9 candidate-native planner v10

**Status:** Accepted

Freeze `candidate-native-planner-v10-wave-spawn-preempt` at protocol SHA-256
`e10833fd3d862239ad8244399f104d8095f2ea68c8539a69dd7ee3537a804463`.
Inherit v9 exactly. Track only the last authoritative `team.wave` value in
reset-local planner state. When the current wave is greater, abandonment is
actor-masked, and the current skill is neither empty, DEFEND, nor SUPPLY, emit
ABANDON with reason `wave_spawn_preempt`. The first reset observation is not a
wave increment.

The public gates and prohibited authorities remain unchanged. Implementation
and tests must be committed before evaluation.
