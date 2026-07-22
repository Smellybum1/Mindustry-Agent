import hashlib
import json

import pytest

from mindustry_agents.tools.public_demo_parity import load_trace, replay_trace


def _record(action):
    candidates = [
        {
            "index": 0,
            "task_id": "expert:harvest:copper:at-10",
            "task_type": "HARVEST_RESOURCE",
            "valid": True,
            "utility": 2.0,
        },
        {
            "index": 1,
            "task_id": "wait:0:at-10",
            "task_type": "WAIT",
            "valid": True,
            "utility": 0.0,
        },
    ]
    return {
        "tick": 10,
        "observations": [
            {
                "agent_id": 0,
                "skill": {"type": "", "status": "READY", "reason": "NONE"},
                "team": {"tick": 10, "enemy_count": 0, "defense_ammo_coverage": 1.0},
                "task_candidates": candidates,
            }
        ],
        "action_masks": [
            {
                "candidate_task": [True, True],
                "continue_current_task": False,
                "abandon": False,
            }
        ],
        "actions": [action],
        "action_results": [{"agent_id": 0, "accepted": True}],
    }


def test_replay_requires_exact_actions_and_reproduces_normalized_digest():
    action = {
        "agent_id": 0,
        "task_action": {"type": "SELECT_CANDIDATE_TASK", "candidate_index": 0},
    }
    digest, selections, actions = replay_trace([_record(action)])
    row = "0\x1fexpert:harvest:copper:at-*\x1fHARVEST_RESOURCE\n"
    assert digest == hashlib.sha256(row.encode()).hexdigest()
    assert (selections, actions) == (1, 1)


def test_replay_rejects_action_drift():
    wrong = {"agent_id": 0, "task_action": {"type": "WAIT"}}
    with pytest.raises(AssertionError, match="action mismatch at tick 10"):
        replay_trace([_record(wrong)])


def test_load_trace_requires_records_and_final_digest():
    action = {
        "agent_id": 0,
        "task_action": {"type": "SELECT_CANDIDATE_TASK", "candidate_index": 0},
    }
    record = _record(action)
    lines = [
        f"prefix AGENT-DEMO PUBLIC TRACE {json.dumps(record)}",
        "prefix AGENT-DEMO DECISION DIGEST digest=" + "a" * 64 + " selections=1",
    ]
    records, digest, selections = load_trace(lines)
    assert records == [record]
    assert digest == "a" * 64
    assert selections == 1
