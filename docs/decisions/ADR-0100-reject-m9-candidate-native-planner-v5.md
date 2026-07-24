# ADR-0100: Reject M9 candidate-native planner v5

**Status:** Accepted

V5 at `1e77d0ede6` improves to 12/40 wins with exact twin-JVM/reset
reproducibility and 99.9560% non-WAIT coverage. Eight episodes still reject a
BUILD_LINE selection with `reservation_overlap` at ticks 1921--2031. Public
traces show these are retries after the expert fortification has occupied the
line footprint.

Full/compact SHA-256 values are
`ef4df95d0b85ab2da538ea476b941a9b8e28d704fa915e8f1ee52639b2d7d713` /
`3ac6102e640ee8f70d09a1eee8aa6c4c9a030c7b51bf9db985bdf25083360e05`.

Reject v5. A successor may suppress only BUILD_LINE candidates after the
authoritative board records `region expert_fortification_v1` completed.
Training and restricted access remain prohibited.
