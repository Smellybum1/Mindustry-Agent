"""Launch and supervise a single ``rl-server`` JVM (roadmap M1 / M2 seed).

One environment maps to one persistent JVM process (ADR-0003). This module owns
the child process lifecycle: it builds the fat jar if missing, launches the JVM
with the working directory set to ``core/assets`` (required for headless asset
resolution — see ``docs/ENGINE_NOTES.md`` and ``rl-server/build.gradle``), waits
for the ``READY <port>`` line on stdout, and owns the loopback-TCP control
connection. Shutdown is graceful (``CloseRequest``) with a hard ``terminate`` of
**the PID we spawned** as a fallback — never a kill-by-name (AGENTS.md).

M2 additions (used by :mod:`mindustry_agents.process.supervisor`): per-child
stderr is captured to a rolling in-memory ring buffer and optionally teed to a
log file under ``runs/`` for diagnosis; a ``command`` override lets tests spawn a
fake server process in place of the JVM; the control connection exposes a
per-call socket timeout so a hung child can be detected and replaced.

Standard-library only (ADR-0007): no third-party imports.
"""

from __future__ import annotations

import collections
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Deque, Optional

from mindustry_agents import protocol as P

DEFAULT_PORT = 47810
_READY_PREFIX = "READY"
_DEFAULT_STDERR_RING = 400


def repo_root() -> Path:
    """Repository root, derived from this file's location."""
    return Path(__file__).resolve().parents[4]


def jar_path(root: Optional[Path] = None) -> Path:
    root = root or repo_root()
    return root / "rl-server" / "build" / "libs" / "rl-server.jar"


def assets_dir(root: Optional[Path] = None) -> Path:
    root = root or repo_root()
    return root / "core" / "assets"


def _gradlew(root: Path) -> list[str]:
    if sys.platform.startswith("win"):
        return [str(root / "gradlew.bat")]
    return ["bash", str(root / "gradlew")]


def build_jar(root: Optional[Path] = None, *, force: bool = False) -> Path:
    """Build ``rl-server:dist`` if the jar is missing (or ``force``)."""
    root = root or repo_root()
    jar = jar_path(root)
    if jar.exists() and not force:
        return jar
    cmd = _gradlew(root) + ["rl-server:dist", "--console=plain"]
    subprocess.run(cmd, cwd=str(root), check=True)
    if not jar.exists():
        raise FileNotFoundError(f"build did not produce {jar}")
    return jar


class LaunchError(RuntimeError):
    """Raised when the JVM fails to become ready."""


class Connection:
    """Length-prefixed JSON control connection to one rl-server."""

    def __init__(self, sock: socket.socket):
        self._sock = sock
        self._request_id = 0

    def next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def set_timeout(self, timeout_s: Optional[float]) -> None:
        """Set the blocking socket timeout (``None`` = block forever)."""
        try:
            self._sock.settimeout(timeout_s)
        except OSError:
            pass

    def send(self, message: Any) -> None:
        self._sock.sendall(P.encode(message))

    def recv(self) -> Any:
        return P.read_message(self._sock.recv)

    def call(self, message: Any) -> Any:
        self.send(message)
        return self.recv()

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass


@dataclass
class LaunchConfig:
    port: int = DEFAULT_PORT
    java: str = "java"
    jvm_args: tuple[str, ...] = ()
    ready_timeout_s: float = 60.0
    connect_timeout_s: float = 30.0
    build_if_missing: bool = True
    # M2: per-child stderr is teed to ``log_dir/<log_name>.stderr.log`` when set.
    log_dir: Optional[Path] = None
    log_name: Optional[str] = None
    # M2: recorded for provenance; the seed is applied at reset(), not launch.
    seed: Optional[int] = None
    # M2 test hook: full argv override (skips jar build); with ``cwd`` override.
    command: Optional[list[str]] = None
    cwd: Optional[Path] = None
    stderr_ring_lines: int = _DEFAULT_STDERR_RING


class RlServerProcess:
    """Context-managed handle to one rl-server JVM and its control connection."""

    def __init__(self, config: Optional[LaunchConfig] = None, **kwargs: Any):
        if config is None:
            config = LaunchConfig(**kwargs)
        self.config = config
        self.root = repo_root()
        self.proc: Optional[subprocess.Popen] = None
        self.conn: Optional[Connection] = None
        self._ready = threading.Event()
        self._ready_port: Optional[int] = None
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._stderr_ring: Deque[str] = collections.deque(
            maxlen=config.stderr_ring_lines
        )
        self._log_fh = None

    # -- lifecycle ---------------------------------------------------------

    def _build_command(self) -> tuple[list[str], Path]:
        """Return ``(argv, cwd)`` for the child process."""
        if self.config.command is not None:
            cwd = self.config.cwd or self.root
            return list(self.config.command), Path(cwd)
        jar = jar_path(self.root)
        if not jar.exists():
            if self.config.build_if_missing:
                build_jar(self.root)
            else:
                raise FileNotFoundError(f"jar not found: {jar} (build it first)")
        cmd = [
            self.config.java,
            *self.config.jvm_args,
            "-jar",
            str(jar),
            "--port",
            str(self.config.port),
        ]
        return cmd, assets_dir(self.root)

    @property
    def log_path(self) -> Optional[Path]:
        if self.config.log_dir is None:
            return None
        name = self.config.log_name or f"child-{self.config.port}"
        return Path(self.config.log_dir) / f"{name}.stderr.log"

    def start(self) -> "RlServerProcess":
        cmd, cwd = self._build_command()

        capture_stderr = self.config.log_dir is not None
        if capture_stderr:
            log_path = self.log_path
            assert log_path is not None
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_fh = open(log_path, "a", encoding="utf-8", errors="replace")
            self._log_fh.write(
                f"# rl-server launch port={self.config.port} "
                f"seed={self.config.seed} cmd={' '.join(cmd)}\n"
            )
            self._log_fh.flush()
            stderr_target: Any = subprocess.PIPE
        else:
            stderr_target = subprocess.DEVNULL

        self.proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=stderr_target,
            text=True,
            bufsize=1,
        )
        self._stdout_thread = threading.Thread(
            target=self._read_stdout, name="rl-stdout", daemon=True
        )
        self._stdout_thread.start()
        if capture_stderr:
            self._stderr_thread = threading.Thread(
                target=self._read_stderr, name="rl-stderr", daemon=True
            )
            self._stderr_thread.start()

        if not self._ready.wait(self.config.ready_timeout_s):
            code = self.proc.poll()
            tail = "\n".join(self.stderr_tail(20))
            self.terminate()
            raise LaunchError(
                f"rl-server did not report READY within "
                f"{self.config.ready_timeout_s}s (exit code={code})"
                + (f"\n--- last stderr ---\n{tail}" if tail else "")
            )
        self._connect()
        return self

    def _read_stdout(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        for line in self.proc.stdout:
            line = line.strip()
            if line.startswith(_READY_PREFIX):
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    self._ready_port = int(parts[1])
                self._ready.set()

    def _read_stderr(self) -> None:
        assert self.proc is not None and self.proc.stderr is not None
        for line in self.proc.stderr:
            line = line.rstrip("\n")
            self._stderr_ring.append(line)
            if self._log_fh is not None:
                try:
                    self._log_fh.write(line + "\n")
                    self._log_fh.flush()
                except (OSError, ValueError):
                    pass

    def stderr_tail(self, n: int = 20) -> list[str]:
        """Return up to the last ``n`` captured stderr lines (newest last)."""
        if n <= 0:
            return []
        ring = list(self._stderr_ring)
        return ring[-n:]

    def _connect(self) -> None:
        deadline = time.monotonic() + self.config.connect_timeout_s
        last_err: Optional[Exception] = None
        port = self._ready_port or self.config.port
        while time.monotonic() < deadline:
            try:
                sock = socket.create_connection(("127.0.0.1", port), timeout=5.0)
                self.conn = Connection(sock)
                return
            except OSError as exc:  # noqa: PERF203
                last_err = exc
                time.sleep(0.05)
        raise LaunchError(f"could not connect to 127.0.0.1:{port}: {last_err}")

    @property
    def pid(self) -> Optional[int]:
        return self.proc.pid if self.proc else None

    @property
    def ready_port(self) -> Optional[int]:
        return self._ready_port

    def is_alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def exit_code(self) -> Optional[int]:
        return self.proc.poll() if self.proc else None

    def terminate(self, timeout_s: float = 5.0) -> None:
        """Terminate the spawned PID (never kill-by-name)."""
        if self.proc is None:
            return
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=timeout_s)
        self._close_log()

    def _close_log(self) -> None:
        if self._log_fh is not None:
            try:
                self._log_fh.flush()
                self._log_fh.close()
            except (OSError, ValueError):
                pass
            finally:
                self._log_fh = None

    def shutdown(self) -> None:
        """Graceful close: CloseRequest, then terminate the PID if still alive."""
        if self.conn is not None:
            try:
                self.conn.set_timeout(2.0)
                self.conn.send(
                    P.CloseRequest(request_id=self.conn.next_request_id(), reason="shutdown")
                )
                # best-effort drain of the close ack
                try:
                    self.conn.recv()
                except Exception:
                    pass
            except Exception:
                pass
            finally:
                self.conn.close()
                self.conn = None
        self.terminate()

    def _sock_settimeout(self, t: float) -> None:
        if self.conn is not None:
            self.conn.set_timeout(t)

    # -- protocol convenience ---------------------------------------------

    def handshake(self, client_name: str = "mindustry-agents") -> P.HandshakeResponse:
        assert self.conn is not None
        return self.conn.call(
            P.HandshakeRequest(protocol_version=P.PROTOCOL_VERSION, client_name=client_name)
        )

    def reset(
        self,
        root_seed: int,
        *,
        scenario_id: str = "bootstrap-defense-v0",
        agent_count: int = 2,
        deterministic: bool = True,
        options: Optional[dict] = None,
    ) -> P.ResetResponse:
        assert self.conn is not None
        return self.conn.call(
            P.ResetRequest(
                request_id=self.conn.next_request_id(),
                scenario_id=scenario_id,
                root_seed=root_seed,
                agent_count=agent_count,
                deterministic=deterministic,
                options=options or {},
            )
        )

    def step(
        self,
        episode_id: str,
        expected_tick: int,
        ticks_to_advance: int,
        agent_actions=None,
        *,
        stop_on_decision_event: bool = False,
    ) -> P.StepResponse:
        assert self.conn is not None
        return self.conn.call(
            P.StepRequest(
                request_id=self.conn.next_request_id(),
                episode_id=episode_id,
                expected_tick=expected_tick,
                ticks_to_advance=ticks_to_advance,
                agent_actions=agent_actions or [],
                stop_on_decision_event=stop_on_decision_event,
            )
        )

    def health(self) -> P.HealthResponse:
        assert self.conn is not None
        return self.conn.call(P.HealthRequest(request_id=self.conn.next_request_id()))

    # -- context manager ---------------------------------------------------

    def __enter__(self) -> "RlServerProcess":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.shutdown()
