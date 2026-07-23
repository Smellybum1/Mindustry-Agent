# Deterministic replay traces

M6 records complete externally stepped action and coordination traces as compact
JSONL. `tests/golden/bootstrap-defense-v0-scripted-v1.jsonl` is the pinned
reference: two complete scripted-expert episodes, seeds 12345 and 23456, for
**16,200 total advanced ticks** and 664 reset/step hash checkpoints.

The first row is a manifest containing the engine tag/commit, Arc hash, protocol
and scenario versions, policy name, episode count, and total tick count. Each
episode begins with a reset row (`seed`, `agent_count`, initial `state_hash`).
Every step row then records `expected_tick`, `ticks_to_advance`, the complete
ordered `agent_actions`, resulting `state_hash`, structured `task_events`, and
outcome. Runtime episode strings are deliberately excluded because replay identity
comes from the manifest/seed rather than a transport handle. The transport handle
is nevertheless deterministic and unique within one server process
(`ep-<root_seed>-<reset_counter>`); structured coordination `episode_id` remains
the deterministic root seed and is verified.

Commands:

```sh
# Re-record intentionally after an accepted behavior change.
python -m mindustry_agents.tools.record_replay

# Verify the checked-in trace through a fresh JVM.
python -m mindustry_agents.tools.replay

# Also mutate the first MINE target in memory and require a hash mismatch.
python -m mindustry_agents.tools.replay --negative-check
```

`make determinism` runs the legacy 79-boundary engine/skill replay first and the
checked-in M6 golden second. Set `REPLAY_NEGATIVE=1` to include the deliberate
negative test. The mutation is never written to disk.

M7.3 intentionally regenerated the checked-in trace in a separate commit.
Recurring and retry task IDs now encode current board state so that repeated
work is distinguishable at the protocol boundary; those IDs participate in the
canonical coordination hash. The frozen macro still records two wins over
16,200 ticks and 664 checkpoints, and the negative MINE mutation still forces a
replay mismatch. M8.4 regenerated the trace for the accepted deterministic
external runtime (synchronous async phases/pathfinding, authoritative
tile-backed buildings, and canonical sleeping-building order); both episodes
still win.

M9.1 regenerated the hash fields after reset began clearing Arc free-object
pools. The accepted actions, task events, ticks, outcomes, episode count, and
16,200-tick budget are byte-identical after removing `state_hash`; 128 hashes
change beginning at checkpoint 535, where combat-created pool history formerly
affected later entity identity. The replacement fixture SHA-256 is
`c753376fbe6db2ecd44bdcaf87d2e224eb05d0e1c4569ddd22e653fcb4fbf6fa`,
and its negative mutation gate passes.
