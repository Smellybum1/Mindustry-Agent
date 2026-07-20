import json
import unittest

from mindustry_agents.tools.replay import mutate_first_mine, parse_trace_lines


def test_trace_parser_and_negative_mutation():
    rows = [
        {"kind": "manifest", "format_version": 1},
        {"kind": "reset", "seed": 1, "agent_count": 1, "state_hash": "a"},
        {
            "kind": "step",
            "agent_actions": [
                {"agent_id": 0, "command": {"type": "MINE", "tile_x": 4, "tile_y": 5}}
            ],
            "state_hash": "b",
            "task_events": [],
        },
    ]
    manifest, records = parse_trace_lines(json.dumps(row) + "\n" for row in rows)
    assert manifest["format_version"] == 1
    changed = mutate_first_mine(records)
    assert changed[1]["agent_actions"][0]["command"]["tile_x"] == 5
    assert records[1]["agent_actions"][0]["command"]["tile_x"] == 4


def test_trace_parser_rejects_missing_manifest():
    with unittest.TestCase().assertRaisesRegex(ValueError, "manifest"):
        parse_trace_lines(['{"kind":"reset"}\n'])
