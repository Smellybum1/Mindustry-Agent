"""Unit tests for the length-prefixed JSON protocol framing (docs/PROTOCOL.md)."""

import json
import struct
import unittest
from dataclasses import asdict

from mindustry_agents import protocol as p


class TestFraming(unittest.TestCase):
    def test_roundtrip_handshake(self):
        msg = p.HandshakeRequest(client_name="pytest", requested_features=["hash"])
        frame = p.encode(msg)
        # 4-byte prefix + body.
        self.assertEqual(len(frame), 4 + struct.unpack(">I", frame[:4])[0])
        decoded = p.decode(frame)
        self.assertIsInstance(decoded, p.HandshakeRequest)
        self.assertEqual(decoded.client_name, "pytest")
        self.assertEqual(decoded.requested_features, ["hash"])
        self.assertEqual(decoded.protocol_version, p.PROTOCOL_VERSION)

    def test_roundtrip_all_message_types(self):
        samples = [
            p.HandshakeRequest(),
            p.HandshakeResponse(engine_version="v159.7"),
            p.ResetRequest(request_id=1, scenario_id="bootstrap-defense-v0"),
            p.ResetResponse(request_id=1, episode_id="ep-1", state_hash="ab"),
            p.StepRequest(request_id=2, episode_id="ep-1", ticks_to_advance=600),
            p.StepResponse(request_id=2, episode_id="ep-1", tick=600),
            p.HealthRequest(request_id=3),
            p.HealthResponse(request_id=3, ok=True),
            p.CloseRequest(request_id=4, reason="done"),
            p.ErrorResponse(request_id=5, code="stale_tick", message="rejected"),
        ]
        for msg in samples:
            with self.subTest(type=type(msg).__name__):
                self.assertEqual(type(p.decode(p.encode(msg))), type(msg))

    def test_type_discriminator_present(self):
        d = p.to_dict(p.StepRequest())
        self.assertEqual(d["type"], "step_request")

    def test_step_action_results_roundtrip(self):
        # M3 additive field: per-action accept/reject results survive a roundtrip.
        results = [
            {"agent_id": 0, "accepted": True, "reason": "accepted", "command_type": "MINE"},
            {"agent_id": 1, "accepted": False, "reason": "out_of_bounds", "command_type": "MINE"},
        ]
        msg = p.StepResponse(request_id=7, episode_id="ep", tick=10, action_results=results)
        back = p.decode(p.encode(msg))
        self.assertEqual(back.action_results, results)

    def test_step_action_results_default_empty(self):
        # A pre-M3 StepResponse without action_results decodes to an empty list.
        payload = {"type": "step_response", "request_id": 1, "episode_id": "e", "tick": 1}
        msg = p.from_dict(payload)
        self.assertEqual(msg.action_results, [])

    def test_step_request_agent_actions_command(self):
        # An agent action carries a nested command object; it roundtrips intact.
        actions = [{"agent_id": 0, "command": {"type": "NAVIGATE", "x": 1.5, "y": 2.5}}]
        msg = p.StepRequest(request_id=1, episode_id="e", agent_actions=actions)
        back = p.decode(p.encode(msg))
        self.assertEqual(back.agent_actions, actions)

    def test_m5_task_action_board_and_events_roundtrip(self):
        actions = [
            {
                "agent_id": 0,
                "task_action": {
                    "type": "SELECT_CANDIDATE_TASK",
                    "candidate_index": 1,
                },
            }
        ]
        request = p.decode(p.encode(p.StepRequest(agent_actions=actions)))
        self.assertEqual(request.agent_actions, actions)

        board = [
            {
                "index": 0,
                "task_id": "T3:build:east_duo_v1",
                "status": "RUNNING",
                "owner_agent_id": 0,
            }
        ]
        events = [
            {
                "message_id": 0,
                "act": "START_TASK",
                "task_id": "T3:build:east_duo_v1",
            }
        ]
        response = p.decode(
            p.encode(p.StepResponse(task_board=board, task_events=events))
        )
        self.assertEqual(response.task_board, board)
        self.assertEqual(response.task_events, events)

    def test_m4_observation_records_roundtrip_in_step(self):
        plan = p.BuildPlanObservation(
            block="duo", tile_x=32, tile_y=23, rotation=1, progress=0.375
        )
        turret = p.TurretAmmoObservation(
            id=12, block="duo", tile_x=32, tile_y=23, total_ammo=30
        )
        observations = [
            {
                "agent_id": 0,
                "unit": {
                    "build_queue_depth": 1,
                    "build_plan_progress": plan.progress,
                    "build_plan": asdict(plan),
                },
                "team": {"broken_block_count": 2, "turrets": [asdict(turret)]},
            }
        ]
        back = p.decode(p.encode(p.StepResponse(observations=observations)))
        self.assertEqual(back.observations, observations)

    def test_unknown_type_rejected(self):
        with self.assertRaises(p.ProtocolError):
            p.from_dict({"type": "does_not_exist"})

    def test_missing_type_rejected(self):
        with self.assertRaises(p.ProtocolError):
            p.from_dict({"no": "type"})

    def test_extra_fields_ignored(self):
        # Forward-compat: unknown fields are dropped, known ones kept.
        payload = {"type": "health_request", "request_id": 9, "future_field": 1}
        msg = p.from_dict(payload)
        self.assertEqual(msg.request_id, 9)

    def test_length_prefix_mismatch_rejected(self):
        body = json.dumps({"type": "health_request", "request_id": 1}).encode()
        bad = struct.pack(">I", len(body) + 5) + body  # wrong declared length
        with self.assertRaises(p.ProtocolError):
            p.decode(bad)

    def test_oversized_declared_length_rejected(self):
        bad = struct.pack(">I", p.MAX_MESSAGE_SIZE + 1) + b"{}"
        with self.assertRaises(p.ProtocolError):
            p.decode(bad)

    def test_decode_stream_partial_and_multiple(self):
        blob = p.encode(p.HealthRequest(request_id=1)) + p.encode(
            p.HealthRequest(request_id=2)
        )
        # Split mid-second-frame to exercise the remainder path.
        cut = len(blob) - 3
        msgs, rem = p.decode_stream(blob[:cut])
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].request_id, 1)
        msgs2, rem2 = p.decode_stream(rem + blob[cut:])
        self.assertEqual(len(msgs2), 1)
        self.assertEqual(msgs2[0].request_id, 2)
        self.assertEqual(rem2, b"")

    def test_read_message_via_recv_callable(self):
        buf = bytearray(p.encode(p.CloseRequest(request_id=7, reason="bye")))

        def recv(n):
            take = bytes(buf[:n])
            del buf[:n]
            return take

        msg = p.read_message(recv)
        self.assertIsInstance(msg, p.CloseRequest)
        self.assertEqual(msg.request_id, 7)

    def test_read_message_truncated_raises(self):
        buf = bytearray(p.encode(p.HealthRequest(request_id=1))[:2])

        def recv(n):
            take = bytes(buf[:n])
            del buf[:n]
            return take

        with self.assertRaises(p.ProtocolError):
            p.read_message(recv)


if __name__ == "__main__":
    unittest.main()
