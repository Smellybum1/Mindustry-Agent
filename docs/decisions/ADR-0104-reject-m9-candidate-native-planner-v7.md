# ADR-0104: Reject M9 candidate-native planner v7

**Status:** Accepted

V7 at `81831b4baf` removes all action rejections and reaches 27/40 wins with
exact twin-JVM/reset replay and 99.7620% non-WAIT coverage. It therefore misses
the frozen 30-win public construction bar by three wins.

Public-only boundary inspection shows that losing roots retain DEFEND tasks
through the safe inter-wave interval. On the inspected early-loss root, one
exposed defender is dead when the next wave spawns, leaving too few live seats
to allocate both defense and supply. The same boundary on a winning root has
all seats off defense before the spawn and reallocates defense plus supply.

Full/compact SHA-256 values are
`e4d1a3d4e7157a5c8dcc434a13ff3afce59b091bd13944a73b1a5c53c83448ba` /
`d46d86025d0e45ec0ed8a786731e7e7b54b4ea914c6885c3f862925718adfa88`.
Reject v7. A successor may add only safe-interwave DEFEND demobilization.
Training and restricted access remain prohibited.
