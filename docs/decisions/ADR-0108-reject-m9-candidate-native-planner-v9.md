# ADR-0108: Reject M9 candidate-native planner v9

**Status:** Accepted

V9 at `0f61a9772f` improves to 29/40 public wins with exact twin-JVM/reset
replay, zero rejected actions, zero cross-seat conflicts, and 99.3769% non-WAIT
coverage. It satisfies the 29-win expert-retention count but remains one win
below the separately frozen 30-win construction floor.

Public boundary inspection exposes a decision-sequence parity gap. On an
inspected loss, authoritative `team.wave` advances at tick 4522 while enemies
are still approaching and not yet counted. The strong expert starts DEFEND at
that boundary, but v9 continues mining until visible contact at tick 4604,
where one miner is dead before external reallocation.

Full/compact SHA-256 values are
`bee303348e6da2afdf0e17bf16cdc10635d9beafa105917fa09c97a1cc7d64fc` /
`ae096f65349ea8738eb0ca4cec8fdc4959a732433f2211bf2808ee98dc1c2a86`.
Reject v9. A successor may add only wave-increment preemption of noncombat work.
Training and restricted access remain prohibited.
