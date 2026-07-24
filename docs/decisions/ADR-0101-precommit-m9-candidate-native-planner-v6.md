# ADR-0101: Precommit M9 candidate-native planner v6

**Status:** Accepted

Freeze `candidate-native-planner-v6-completed-fortification` at protocol
SHA-256
`748032f71739c878b0634042999148433fee0758c0a011f01ff9f984b01210ea`.
Inherit v5 exactly. When the authoritative task board contains a COMPLETED
BUILD_SCHEMATIC targeted at `region expert_fortification_v1`, remove BUILD_LINE
candidates before the unchanged allocator runs. This is the only behavior
change. The same public gates and prohibited authorities remain exact.
Implementation/tests must be committed before evaluation.
