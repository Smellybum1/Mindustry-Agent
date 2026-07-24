# ADR-0110: Reject M9 candidate-native planner v10

**Status:** Accepted

The first v10 invocation was invalid because a rule-order defect violated its
DEFEND exemption. After correction and a committed real-timer regression, the
unchanged protocol produces a valid 19/40 result at `61f30da03e`, with exact
twin-JVM/reset replay, zero action defects, and 95.1780% non-WAIT coverage.

Wave-increment preemption therefore regresses v9's 29/40 result. Moving ordinary
agents into candidate DEFEND tasks earlier increases their exposure and does
not reproduce the stronger internal expert's fortification path.

Full/compact SHA-256 values are
`24b1faa6aeb2cef197507b91b255e5ff473f031f498d5d907063c5a0c56de5a6` /
`1b18e4330716df98f55032c72c5bcf5c70982faddad58444db1802906066bf6a`.
Reject v10 and retain v9 as the strongest candidate-native planner. Training
and restricted access remain prohibited.
