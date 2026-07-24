# ADR-0112: Accept M9 candidate-native planner v11

**Status:** Accepted

V11 at `07ec5dfa38` passes its frozen public source gate:

- 32/40 wins, above the 30-win floor and 29-win expert-retention count;
- exact reports across two fresh JVMs and terminal reset replay;
- zero rejected actions and zero cross-seat exclusive conflicts;
- 96.5548% non-WAIT selection coverage; and
- no confirmation or held-out access.

The planner is therefore accepted as a candidate-native supervision source,
not as a learned policy and not as M9 completion. It uses only ordinary
externally stepped candidate actions, authoritative structured observations,
the task board, masks, action results, and bounded reset-local state.

Full report, canonical episode-report, and compact SHA-256 values are
`3c0a3d6b877f9f03407b0dafd9ae7d03ebf4a45cc5b6be32e022a92609e75e28` /
`dc2dc4c30fd63c0e148866b776eb51bc8458432b530642710756defe407752f1` /
`81ea8df1d7dcf21ed945337dd23b93b804e4d187605282e6d98cffe4077695fa`.
Any learned successor still requires a prospective protocol and all existing
M9 governance.
