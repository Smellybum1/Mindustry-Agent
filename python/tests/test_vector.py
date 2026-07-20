"""Framework-neutral vector collector timing and event-mode tests."""

import unittest

from mindustry_agents.env.vector import VectorCollector
from mindustry_agents.process.supervisor import StepOutcome


class _Supervisor:
    size = 2

    def __init__(self):
        self.calls = []

    def step(self, index, bundle, ticks, *, stop_on_decision_event=False):
        self.calls.append((index, bundle, ticks, stop_on_decision_event))
        advanced = 7 if index == 0 else 11
        return StepOutcome(
            observations=[],
            rewards=[],
            terminations=[],
            truncations=[],
            info={"previous_tick": 100, "tick": 100 + advanced},
        )


class TestVectorCollector(unittest.TestCase):
    def test_event_mode_uses_actual_per_child_advance(self):
        supervisor = _Supervisor()
        result = VectorCollector(supervisor).step_all(
            actions=[[{"agent_id": 0}], [{"agent_id": 1}]],
            ticks=9000,
            stop_on_decision_event=True,
        )

        self.assertEqual(result.ticks_advanced, 18)
        self.assertEqual(len(result.outcomes), 2)
        self.assertEqual(
            sorted(supervisor.calls),
            [
                (0, [{"agent_id": 0}], 9000, True),
                (1, [{"agent_id": 1}], 9000, True),
            ],
        )


if __name__ == "__main__":
    unittest.main()
