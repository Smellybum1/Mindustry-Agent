"""M2 env-facade tests — EnvClient round-trip and ParallelEnv API shape.

Uses ``fake_server.py`` (a python subprocess speaking the real protocol) so no
JVM is needed. Covers: protocol round-trip through :class:`EnvClient`, and the
PettingZoo-style dict in/out surface of :class:`MindustryParallelEnv`.
"""

import sys
import unittest
from contextlib import contextmanager
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parents[0] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from mindustry_agents.env.client import EnvClient  # noqa: E402
from mindustry_agents.env.parallel_env import MindustryParallelEnv  # noqa: E402
from mindustry_agents.process.launcher import LaunchConfig, RlServerProcess  # noqa: E402

FAKE = str(_HERE / "fake_server.py")


@contextmanager
def fake_env(tmp: Path, port: int = 48300, agents: int = 2):
    """Spawn one fake server and yield a handshaked EnvClient over it."""
    cmd = [sys.executable, FAKE, "--port", str(port), "--agents", str(agents)]
    proc = RlServerProcess(
        LaunchConfig(
            port=port,
            command=cmd,
            log_dir=tmp,
            log_name=f"fake-{port}",
            ready_timeout_s=10.0,
            connect_timeout_s=10.0,
        )
    )
    proc.start()
    try:
        client = EnvClient(proc.conn, agent_count=agents)
        client.handshake()
        yield client
    finally:
        proc.shutdown()


class TestEnvClient(unittest.TestCase):
    def test_protocol_roundtrip(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            with fake_env(Path(td), port=48301) as client:
                hs = client.handshake_response
                self.assertIsNotNone(hs)
                self.assertEqual(hs.engine_version, "v159.7")

                res = client.reset(12345)
                self.assertEqual(len(res.observations), 2)
                self.assertEqual(res.info["tick"], 0)
                self.assertTrue(res.info["state_hash"])
                self.assertEqual(client.tick, 0)

                obs, rewards, terms, truncs, info = client.step([{}, {}], ticks=60)
                self.assertEqual(len(obs), 2)
                self.assertEqual(info["tick"], 60)
                self.assertEqual(info["previous_tick"], 0)
                self.assertEqual(client.tick, 60)
                self.assertEqual(terms, [False, False])
                self.assertEqual(truncs, [False, False])
                self.assertIn("engine_ms", info["timing"])
                self.assertEqual(info["coordination_metrics"], {})

                h = client.health()
                self.assertTrue(h.ok)

    def test_reset_purity_same_seed(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            with fake_env(Path(td), port=48302) as client:
                a = client.reset(777).info["state_hash"]
                b = client.reset(777).info["state_hash"]
                self.assertEqual(a, b)

    def test_step_before_reset_raises(self):
        import tempfile
        from mindustry_agents.env.client import EnvClientError

        with tempfile.TemporaryDirectory() as td:
            with fake_env(Path(td), port=48303) as client:
                with self.assertRaises(EnvClientError):
                    client.step([{}, {}], ticks=1)


class TestParallelEnv(unittest.TestCase):
    def test_api_shape(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            with fake_env(Path(td), port=48304) as client:
                env = MindustryParallelEnv(client)
                self.assertEqual(env.possible_agents, ["agent_0", "agent_1"])
                self.assertEqual(env.agents, [])

                obs, infos = env.reset(seed=42)
                self.assertEqual(set(obs.keys()), {"agent_0", "agent_1"})
                self.assertEqual(set(infos.keys()), {"agent_0", "agent_1"})
                self.assertEqual(env.agents, ["agent_0", "agent_1"])
                # Every agent receives the (identical) world observation in M1.
                self.assertEqual(obs["agent_0"]["tick"], 0)
                self.assertEqual(obs["agent_0"], obs["agent_1"])

                actions = {"agent_0": {"skill": "wait"}, "agent_1": {"skill": "wait"}}
                o, r, term, trunc, i = env.step(actions)
                for d in (o, r, term, trunc, i):
                    self.assertEqual(set(d.keys()), {"agent_0", "agent_1"})
                self.assertIsInstance(r["agent_0"], float)
                self.assertIsInstance(term["agent_0"], bool)
                self.assertIsInstance(trunc["agent_0"], bool)
                self.assertEqual(o["agent_0"]["tick"], 1)

                # Space stubs are framework-neutral dict descriptors.
                self.assertIn("keys", env.observation_space("agent_0"))
                self.assertIn("note", env.action_space("agent_0"))

    def test_ticks_control_key(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            with fake_env(Path(td), port=48305) as client:
                env = MindustryParallelEnv(client)
                env.reset(seed=1)
                o, _, _, _, _ = env.step({"agent_0": {}, "agent_1": {}, "__ticks__": 60})
                self.assertEqual(o["agent_0"]["tick"], 60)


if __name__ == "__main__":
    unittest.main()
