# ADR-0132: Accept M9 planner trajectory-divergence signal

**Status:** Accepted

## Context

ADR-0131 froze a public-only comparison between the exact rejected update-64
student and unchanged planner v11. The complete exact-current-commit gate
passed at `26f96ed4b6df2d3ca80ef525982b074364ebf097`.

Two fresh JVM reports and terminal-reset replay match exactly. The student
reproduces its frozen 13/40 wins and mean core health `242.975`; planner v11
reproduces 32/40 wins and mean core health `436.075`. Their paired outcomes are
13 both-win, zero student-only, 19 planner-only, and eight both-loss roots.

On the 19 prospectively primary planner-win/student-loss roots, median
three-seat task-family occupancy mismatch is `0.5982905982905983` and median
normalized compressed-sequence distance is `0.6428571428571429`. These exceed
the frozen `0.5` thresholds with at least 15 planner-only roots.

The full report SHA-256 is
`f54a4d3369b1c8c619810b3d76e342c53cc3307138b4d102416396a202628f0e`
and its canonical report SHA-256 is
`fb389c6b5f728a4258a48f25df7f64cb575c3e5723c85ab1f62d0d2857d3bc4e`.
The compact result SHA-256 is
`9557714141a239b4e1f092a6f4009157876ae52a52d02e6435359f6dab3204bd`.

## Decision

1. Accept the frozen `trajectory_supervision_signal`.
2. Keep update 64 and every prior learned checkpoint rejected, unselected,
   unrepaired, and unpromotable.
3. The result supports one separately prospective trajectory-supervision
   architecture that represents macro task-family intent; it does not support
   an atomic joint-bundle actor, another pointwise-NLL pressure/cadence change,
   or online planner correction.
4. The successor must bind the exact rejected source, public roots, planner,
   model inheritance, new parameters, optimizer-state treatment, trajectory
   labels, losses, budget, dev floor, and replica rule before implementation.
5. No training is authorized by this result alone.
6. No target identifiers or raw observations were published. No model,
   optimizer, confirmation, held-out, or other restricted data was touched.
   M8 held-out-v7 remains sealed.

## Consequences

The next permitted action is to draft and commit one prospective
trajectory-supervision candidate. Its failure cannot be converted into a
hyperparameter or horizon sweep without another owner-authorized decision.
