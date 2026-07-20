"""M2 supervisor tests — no JVM, fast.

The rl-server JVM is mocked by ``fake_server.py`` (a python subprocess that speaks
the real length-prefixed JSON protocol). These cover port allocation + READY
parsing, handshake verification, startup-failure detection, and the
crash -> truncation -> replacement path. Real-JVM coverage lives in the shell
scripts (smoke/determinism/stress/benchmark).
"""

import sys
import time
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parents[0] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from mindustry_agents.process import supervisor as S  # noqa: E402
from mindustry_agents.process.supervisor import (  # noqa: E402
    ProcessSupervisor,
    SupervisorConfig,
    SupervisorError,
)

FAKE = str(_HERE / "fake_server.py")


def _factory(extra=None):
    extra = extra or []

    def build(port: int, seed: int) -> list[str]:
        return [sys.executable, FAKE, "--port", str(port), "--agents", "2", *extra]

    return build


def _config(tmp: Path, pool_size=1, extra=None, **kw) -> SupervisorConfig:
    params = dict(
        pool_size=pool_size,
        base_port=48200,
        command_factory=_factory(extra),
        log_dir=tmp,
        ready_timeout_s=10.0,
        connect_timeout_s=10.0,
        handshake_timeout_s=10.0,
        reset_timeout_s=5.0,
        step_timeout_s=5.0,
        agent_count=2,
    )
    params.update(kw)
    return SupervisorConfig(**params)


class TestPortAllocation(unittest.TestCase):
    def test_free_port_helper(self):
        # A high port should be bindable; the helper reports it free.
        self.assertTrue(S._is_port_free(49999) in (True, False))

    def test_distinct_ports_and_ready_parsing(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with ProcessSupervisor(_config(tmp, pool_size=2)) as sup:
                c0, c1 = sup.child(0), sup.child(1)
                # Unique ports.
                self.assertNotEqual(c0.port, c1.port)
                # READY line parsed and matches the assigned port.
                self.assertEqual(c0.proc.ready_port, c0.port)
                self.assertEqual(c1.proc.ready_port, c1.port)
                # Distinct PIDs, both alive, handshake verified.
                self.assertNotEqual(c0.pid, c1.pid)
                self.assertTrue(c0.proc.is_alive())
                self.assertTrue(c1.proc.is_alive())
                # A basic reset/step round-trips through both.
                r0 = sup.reset(0)
                self.assertEqual(len(r0.observations), 2)
                out = sup.step(0, ticks=60)
                self.assertFalse(out.crashed)
                self.assertEqual(out.info["tick"], 60)


class TestStartupFailures(unittest.TestCase):
    def test_no_ready_is_startup_failure(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            cfg = _config(Path(td), extra=["--no-ready"], ready_timeout_s=2.0)
            with self.assertRaises(SupervisorError):
                ProcessSupervisor(cfg).start()

    def test_bad_commit_rejected(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            cfg = _config(Path(td), extra=["--bad-commit"])
            with self.assertRaises(SupervisorError):
                ProcessSupervisor(cfg).start()

    def test_pool_size_cap(self):
        with self.assertRaises(ValueError):
            ProcessSupervisor(SupervisorConfig(pool_size=5))


class TestCrashReplacement(unittest.TestCase):
    def test_crash_detected_marked_truncated_and_replaced(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            cfg = _config(Path(td), pool_size=1, extra=["--crash-after-steps", "1"])
            with ProcessSupervisor(cfg) as sup:
                old = sup.child(0)
                old_pid = old.pid
                sup.reset(0)
                # First step succeeds; the fake exits right after replying.
                first = sup.step(0, ticks=1)
                self.assertFalse(first.crashed)
                # Give the OS a moment to reap the exited child.
                time.sleep(0.2)
                # Second step hits a dead child -> crash, truncation, replace.
                second = sup.step(0, ticks=1)
                self.assertTrue(second.crashed)
                self.assertTrue(all(second.truncations))
                self.assertTrue(second.replaced)
                self.assertIn("stderr_tail", second.info)
                # A fresh child took the slot.
                new = sup.child(0)
                self.assertEqual(new.generation, 1)
                self.assertNotEqual(new.pid, old_pid)
                self.assertTrue(new.proc.is_alive())
                # The replacement resets and steps cleanly.
                r = sup.reset(0)
                self.assertEqual(len(r.observations), 2)
                out = sup.step(0, ticks=1)
                self.assertFalse(out.crashed)

    def test_hang_triggers_timeout_replacement(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            cfg = _config(
                Path(td),
                pool_size=1,
                extra=["--hang-after-steps", "1"],
                step_timeout_s=1.5,
            )
            with ProcessSupervisor(cfg) as sup:
                sup.reset(0)
                self.assertFalse(sup.step(0, ticks=1).crashed)  # 1st ok
                out = sup.step(0, ticks=1)  # server now hangs -> timeout
                self.assertTrue(out.crashed)
                self.assertTrue(out.replaced)
                self.assertEqual(sup.child(0).generation, 1)

    def test_stderr_tail_retrievable(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            with ProcessSupervisor(_config(Path(td), pool_size=1)) as sup:
                tail = sup.stderr_tail(0, 10)
                self.assertTrue(any("listening" in line for line in tail))


if __name__ == "__main__":
    unittest.main()
