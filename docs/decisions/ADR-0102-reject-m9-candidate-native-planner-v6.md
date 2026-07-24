# ADR-0102: Reject M9 candidate-native planner v6

**Status:** Accepted

V6 at `6697c7f976` reaches 27/40 wins with exact twin-JVM/reset replay and
99.6804% non-WAIT coverage. It misses the 30-win bar and still has eight
BUILD_LINE `reservation_overlap` rejections. Public board inspection shows the
expert fortification is RUNNING at those boundaries, so v6's COMPLETED-only
predicate activates too late.

Full/compact SHA-256 values are
`5ec82da9824c5bf1feedd6d0ba876f21b6776f39a37fb37d2412f9fd82fb8eda` /
`930b617186248ea334540191b5d24b145a2b8c1eac52ae90b1a86f6a727c24d4`.

Reject v6. A successor may widen only the fortification predicate to CLAIMED,
RUNNING, BLOCKED, or COMPLETED. Training and restricted access remain
prohibited.
