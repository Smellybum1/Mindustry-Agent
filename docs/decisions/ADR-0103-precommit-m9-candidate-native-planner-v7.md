# ADR-0103: Precommit M9 candidate-native planner v7

**Status:** Accepted

Freeze `candidate-native-planner-v7-active-fortification` at protocol SHA-256
`df0427db128c8543b3f45c6f9cbd16eea81afe3bc4e3be9be73f6003af902d75`.
Inherit v6 exactly and widen only the expert-fortification board predicate from
COMPLETED to CLAIMED/RUNNING/BLOCKED/COMPLETED before suppressing BUILD_LINE.
The public gates and prohibited authorities remain unchanged.
Implementation/tests must be committed before evaluation.
