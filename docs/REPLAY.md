# Deterministic replay traces

M6 records complete externally stepped action and coordination traces as compact
JSONL. `tests/golden/bootstrap-defense-v0-scripted-v1.jsonl` is the pinned
reference: two complete scripted-expert episodes, seeds 12345 and 23456, for
**16,200 total advanced ticks** and 678 reset/step hash checkpoints.

The first row is a manifest containing the engine tag/commit, Arc hash, protocol
and scenario versions, policy name, episode count, and total tick count. Each
episode begins with a reset row (`seed`, `agent_count`, initial `state_hash`).
Every step row then records `expected_tick`, `ticks_to_advance`, the complete
ordered `agent_actions`, resulting `state_hash`, structured `task_events`, and
outcome. Runtime episode strings are deliberately excluded because the control
server uses a nonce for connection safety; structured coordination `episode_id`
remains the deterministic root seed and is verified.

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
