# ADR-0105: Precommit M9 candidate-native planner v8

**Status:** Accepted

Freeze `candidate-native-planner-v8-interwave-demobilize` at protocol SHA-256
`168317b2e5a34e64535059346f4bcecec3125151382c3c98f116be20600a6b1a`.
Inherit v7 exactly and add one fixed-action rule: when the current skill is
DEFEND, abandonment is actor-masked, there are no enemies, and
`time_to_next_wave` is greater than the authoritative `defend_lead_ticks`,
emit ABANDON with reason `safe_interwave_demobilize`. Inside the defend-lead
window and during combat, v7 behavior remains unchanged.

The public gates and prohibited authorities remain unchanged. Implementation
and tests must be committed before evaluation.
