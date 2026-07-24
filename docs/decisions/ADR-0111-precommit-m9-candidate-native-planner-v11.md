# ADR-0111: Precommit M9 candidate-native planner v11

**Status:** Accepted

Freeze `candidate-native-planner-v11-single-defender` at protocol SHA-256
`d670ff4503cdc8e3ca696a501115e4a93ac5246360731940f1099a8d9416ab7d`.
Branch from v9, not rejected v10. Inherit v9 exactly and change only the
authoritative active DEFEND_REGION cap from two to one. When the single slot is
occupied, allocate from v9's unchanged remaining candidates.

The public gates and prohibited authorities remain unchanged. Implementation
and tests must be committed before evaluation.
