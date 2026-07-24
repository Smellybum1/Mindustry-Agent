# ADR-0106: Reject M9 candidate-native planner v8

**Status:** Accepted

V8 at `bf12185d88` improves to 28/40 public wins with exact twin-JVM/reset
replay, zero rejected actions, zero cross-seat conflicts, and 99.4083% non-WAIT
coverage. It remains two wins below the frozen 30-win construction bar.

Public boundary inspection confirms safe-interwave demobilization preserves the
team through the next spawn. It also exposes the next coordination defect: the
wave begins with two active defenders and one supplier, but immediately after
the two-tick supply task completes, the freed seat selects a third DEFEND task
because active board claims are outside the atomic allocation conflict check.

Full/compact SHA-256 values are
`d8939218781c5900a19f175625bd30911f5e9fcde62a11dd7f31f7bc19c7d8b0` /
`9f23893a896e9ffe4f7135266802f5462ec310a5b575a8d0dfe12189b77019e0`.
Reject v8. A successor may add only an authoritative active-DEFEND cap of two.
Training and restricted access remain prohibited.
