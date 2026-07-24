# ADR-0107: Precommit M9 candidate-native planner v9

**Status:** Accepted

Freeze `candidate-native-planner-v9-active-defend-cap` at protocol SHA-256
`20ba635f3ab468b8750e4d6244bc8db8292c1fa61539391282f1259ac9cb7a2c`.
Inherit v8 exactly and add one task-board allocation constraint: count
DEFEND_REGION tasks in CLAIMED, RUNNING, or BLOCKED state, allow at most two
including new atomic selections, and otherwise allocate from v8's unchanged
remaining candidates.

The public gates and prohibited authorities remain unchanged. Implementation
and tests must be committed before evaluation.
