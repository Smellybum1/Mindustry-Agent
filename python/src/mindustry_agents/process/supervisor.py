"""Persistent pool of rl-server JVM environments (roadmap M2).

The :class:`ProcessSupervisor` owns *N* long-lived JVM children (ADR-0003 — one
world per JVM, parallelism from many processes). It is the piece that turns a
single launcher into a fleet:

* **Unique port per child**, probed upward from a base port, with EADDRINUSE
  races handled by retrying on the next port.
* **Explicit seed and log dir per child.** Seeds are recorded and applied at
  ``reset()``; each child's stderr is teed to ``runs/<run>/childK-...stderr.log``
  (gitignored) with the last *N* lines retrievable for diagnosis.
* **Handshake verification**: the server's ``engine_commit`` must equal the pin
  in ``ENGINE_VERSION`` (or a mismatch is a hard startup failure).
* **Startup-failure detection**: a child that never prints ``READY`` (or whose
  handshake fails) aborts the launch with its captured stderr tail attached.
* **Crash / hang detection with automatic replacement**: reset/step run under a
  socket timeout; a dead or unresponsive child has its current episode marked
  *truncated*, is terminated (by the PID we spawned — never kill-by-name), and is
  transparently replaced by a fresh, re-handshaked child.
* **Clean shutdown**: ``CloseRequest`` then terminate every tracked PID, wired to
  both an ``atexit`` hook and the context-manager protocol so JVMs are never
  orphaned.

Standard-library only (ADR-0007).
"""

from __future__ import annotations

import atexit
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from mindustry_agents import ENGINE_COMMIT as _PKG_ENGINE_COMMIT
from mindustry_agents import protocol as P
from mindustry_agents.env.client import EnvClient
from mindustry_agents.process.launcher import (
    LaunchConfig,
    LaunchError,
    RlServerProcess,
    repo_root,
)

DEFAULT_BASE_PORT = 47810
# Machine constraint: other unrelated projects share this host. Never run more
# than four JVM environments at once (see docs/BENCHMARKS.md M2 notes).
MAX_POOL_SIZE = 4
_PORT_PROBE_SPAN = 2000


class SupervisorError(RuntimeError):
    """Raised for pool-level failures (startup, handshake, crash loop)."""


def read_engine_commit(root: Optional[Path] = None) -> str:
    """Return the pinned engine commit from ``ENGINE_VERSION`` (fallback: pkg)."""
    root = root or repo_root()
    path = root / "ENGINE_VERSION"
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("commit="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return _PKG_ENGINE_COMMIT


@dataclass
class SupervisorConfig:
    pool_size: int = 2
    base_port: int = DEFAULT_BASE_PORT
    java: str = "java"
    jvm_args: tuple[str, ...] = ()
    scenario_id: str = "bootstrap-defense-v0"
    agent_count: int = 2
    ready_timeout_s: float = 60.0
    connect_timeout_s: float = 30.0
    handshake_timeout_s: float = 30.0
    reset_timeout_s: float = 30.0
    step_timeout_s: float = 60.0
    log_dir: Optional[Path] = None
    verify_engine_commit: bool = True
    build_if_missing: bool = True
    max_replaces_per_child: int = 5
    # Test hook: build a full argv from ``(port, seed)`` to spawn a fake server
    # in place of the JVM. ``cwd_override`` sets its working directory.
    command_factory: Optional[Callable[[int, int], list[str]]] = None
    cwd_override: Optional[Path] = None
    # Provide explicit seeds per child; defaults to ``base_seed + index``.
    seeds: Optional[list[int]] = None
    base_seed: int = 1000


@dataclass
class ManagedChild:
    index: int
    seed: int
    port: int
    proc: RlServerProcess
    client: EnvClient
    handshake: P.HandshakeResponse
    generation: int = 0
    replaces: int = 0
    episode_truncated: bool = False

    @property
    def pid(self) -> Optional[int]:
        return self.proc.pid


@dataclass
class StepOutcome:
    """Result of a supervised step. On a crash, ``truncations`` are all ``True``."""

    observations: list[dict[str, Any]]
    rewards: list[dict[str, Any]]
    terminations: list[bool]
    truncations: list[bool]
    info: dict[str, Any]
    crashed: bool = False
    replaced: bool = False


@dataclass
class ResetOutcome:
    observations: list[dict[str, Any]]
    info: dict[str, Any]
    replaced: bool = False


class ProcessSupervisor:
    """Manage a pool of persistent rl-server JVM environments."""

    def __init__(self, config: Optional[SupervisorConfig] = None, **kwargs: Any):
        if config is None:
            config = SupervisorConfig(**kwargs)
        if config.pool_size < 1:
            raise ValueError("pool_size must be >= 1")
        if config.pool_size > MAX_POOL_SIZE:
            raise ValueError(
                f"pool_size {config.pool_size} exceeds MAX_POOL_SIZE "
                f"{MAX_POOL_SIZE} (this machine is shared; see docs/BENCHMARKS.md)"
            )
        self.config = config
        self.root = repo_root()
        self._expected_commit = read_engine_commit(self.root)
        self.children: list[Optional[ManagedChild]] = [None] * config.pool_size
        self._used_ports: set[int] = set()
        self._next_port = config.base_port
        self._lock = threading.Lock()
        self._closed = False
        self._started = False
        self._log_dir = self._resolve_log_dir()
        atexit.register(self.shutdown)

    def _resolve_log_dir(self) -> Path:
        if self.config.log_dir is not None:
            return Path(self.config.log_dir)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        return self.root / "runs" / f"pool-{stamp}"

    @property
    def log_dir(self) -> Path:
        return self._log_dir

    def _seed_for(self, index: int) -> int:
        if self.config.seeds is not None and index < len(self.config.seeds):
            return self.config.seeds[index]
        return self.config.base_seed + index

    # -- port allocation ---------------------------------------------------

    def _probe_free_port(self) -> int:
        """Return a free loopback port at/above ``_next_port``, skipping in-use."""
        with self._lock:
            start = self._next_port
            for candidate in range(start, start + _PORT_PROBE_SPAN):
                if candidate in self._used_ports:
                    continue
                if _is_port_free(candidate):
                    self._used_ports.add(candidate)
                    self._next_port = candidate + 1
                    return candidate
            raise SupervisorError(
                f"no free loopback port in [{start}, {start + _PORT_PROBE_SPAN})"
            )

    def _release_port(self, port: int) -> None:
        with self._lock:
            self._used_ports.discard(port)

    # -- child lifecycle ---------------------------------------------------

    def _spawn(self, index: int, generation: int) -> ManagedChild:
        seed = self._seed_for(index)
        last_err: Optional[Exception] = None
        for _ in range(8):  # retry across ports on bind races / early crashes
            port = self._probe_free_port()
            command = None
            if self.config.command_factory is not None:
                command = self.config.command_factory(port, seed)
            cfg = LaunchConfig(
                port=port,
                java=self.config.java,
                jvm_args=self.config.jvm_args,
                ready_timeout_s=self.config.ready_timeout_s,
                connect_timeout_s=self.config.connect_timeout_s,
                build_if_missing=self.config.build_if_missing,
                log_dir=self._log_dir,
                log_name=f"child{index}-gen{generation}-port{port}",
                seed=seed,
                command=command,
                cwd=self.config.cwd_override,
            )
            proc = RlServerProcess(cfg)
            try:
                proc.start()
            except LaunchError as exc:
                code = proc.exit_code()
                proc.terminate()
                self._release_port(port)
                last_err = exc
                # exit code 3 == BindException (port raced); retry next port.
                if code == 3:
                    continue
                raise SupervisorError(
                    f"child {index} failed to start on port {port}: {exc}"
                ) from exc

            try:
                child = self._handshake(index, seed, port, proc, generation)
            except Exception as exc:
                tail = "\n".join(proc.stderr_tail(20))
                proc.shutdown()
                self._release_port(port)
                raise SupervisorError(
                    f"child {index} handshake failed on port {port}: {exc}"
                    + (f"\n--- last stderr ---\n{tail}" if tail else "")
                ) from exc
            return child
        raise SupervisorError(
            f"child {index} could not acquire a bindable port: {last_err}"
        )

    def _handshake(
        self,
        index: int,
        seed: int,
        port: int,
        proc: RlServerProcess,
        generation: int,
    ) -> ManagedChild:
        assert proc.conn is not None
        client = EnvClient(
            proc.conn,
            scenario_id=self.config.scenario_id,
            agent_count=self.config.agent_count,
        )
        proc.conn.set_timeout(self.config.handshake_timeout_s)
        hs = client.handshake()
        if self.config.verify_engine_commit and hs.engine_commit != self._expected_commit:
            raise SupervisorError(
                f"engine commit mismatch: server={hs.engine_commit!r} "
                f"expected={self._expected_commit!r}"
            )
        proc.conn.set_timeout(None)
        return ManagedChild(
            index=index,
            seed=seed,
            port=port,
            proc=proc,
            client=client,
            handshake=hs,
            generation=generation,
        )

    def _replace(self, index: int, reason: str) -> ManagedChild:
        """Terminate a dead/hung child and spawn a fresh, re-handshaked one."""
        old = self.children[index]
        old_generation = old.generation if old is not None else 0
        old_replaces = old.replaces if old is not None else 0
        if old is not None:
            try:
                old.proc.terminate()
            except Exception:
                pass
            self._release_port(old.port)
        if old_replaces + 1 > self.config.max_replaces_per_child:
            raise SupervisorError(
                f"child {index} exceeded max replacements "
                f"({self.config.max_replaces_per_child}); likely a crash loop"
            )
        child = self._spawn(index, generation=old_generation + 1)
        child.replaces = old_replaces + 1
        self.children[index] = child
        return child

    # -- public API --------------------------------------------------------

    def start(self) -> "ProcessSupervisor":
        """Spawn the whole pool concurrently (respecting the size cap)."""
        if self._started:
            return self
        results: list[Optional[ManagedChild]] = [None] * self.config.pool_size
        errors: list[Optional[Exception]] = [None] * self.config.pool_size

        def _spawn_into(i: int) -> None:
            try:
                results[i] = self._spawn(i, generation=0)
            except Exception as exc:  # noqa: BLE001
                errors[i] = exc

        threads = [
            threading.Thread(target=_spawn_into, args=(i,), name=f"spawn-{i}")
            for i in range(self.config.pool_size)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if any(e is not None for e in errors):
            # Roll back any children that did come up, then fail loudly.
            for child in results:
                if child is not None:
                    try:
                        child.proc.shutdown()
                        self._release_port(child.port)
                    except Exception:
                        pass
            first = next(e for e in errors if e is not None)
            raise SupervisorError(f"pool startup failed: {first}") from first

        self.children = results
        self._started = True
        return self

    def child(self, index: int) -> ManagedChild:
        c = self.children[index]
        if c is None:
            raise SupervisorError(f"child {index} is not running")
        return c

    @property
    def size(self) -> int:
        return self.config.pool_size

    def stderr_tail(self, index: int, n: int = 20) -> list[str]:
        c = self.children[index]
        if c is None:
            return []
        return c.proc.stderr_tail(n)

    def reset(
        self,
        index: int,
        seed: Optional[int] = None,
        options: Optional[dict[str, Any]] = None,
    ) -> ResetOutcome:
        """Reset one child; a crashed child is replaced and reset once."""
        child = self.child(index)
        use_seed = child.seed if seed is None else seed
        child.episode_truncated = False
        try:
            child.proc.conn.set_timeout(self.config.reset_timeout_s)  # type: ignore[union-attr]
            result = child.client.reset(use_seed, options)
            return ResetOutcome(observations=result.observations, info=result.info)
        except Exception as exc:  # noqa: BLE001
            if not self._is_connection_failure(child, exc):
                raise
            new_child = self._replace(index, reason=f"reset crash: {exc}")
            new_child.proc.conn.set_timeout(self.config.reset_timeout_s)  # type: ignore[union-attr]
            result = new_child.client.reset(use_seed, options)
            info = dict(result.info)
            info["replaced"] = True
            info["crash_reason"] = str(exc)
            return ResetOutcome(observations=result.observations, info=info, replaced=True)

    def step(
        self,
        index: int,
        actions_bundle: Optional[list[dict[str, Any]]] = None,
        ticks: int = 1,
    ) -> StepOutcome:
        """Step one child. On crash: mark truncated, replace, return truncated."""
        child = self.child(index)
        actions_bundle = actions_bundle or []
        try:
            child.proc.conn.set_timeout(self.config.step_timeout_s)  # type: ignore[union-attr]
            obs, rewards, terms, truncs, info = child.client.step(actions_bundle, ticks)
            return StepOutcome(
                observations=obs,
                rewards=rewards,
                terminations=terms,
                truncations=truncs,
                info=info,
            )
        except Exception as exc:  # noqa: BLE001
            if not self._is_connection_failure(child, exc):
                raise
            n = self.config.agent_count
            tail = child.proc.stderr_tail(20)
            child.episode_truncated = True
            self._replace(index, reason=f"step crash: {exc}")
            return StepOutcome(
                observations=[],
                rewards=[{} for _ in range(n)],
                terminations=[False] * n,
                truncations=[True] * n,
                info={
                    "crashed": True,
                    "replaced": True,
                    "crash_reason": str(exc),
                    "stderr_tail": tail,
                },
                crashed=True,
                replaced=True,
            )

    def health(self, index: int) -> P.HealthResponse:
        child = self.child(index)
        child.proc.conn.set_timeout(self.config.step_timeout_s)  # type: ignore[union-attr]
        return child.client.health()

    @staticmethod
    def _is_connection_failure(child: ManagedChild, exc: Exception) -> bool:
        """A step/reset error counts as a crash if the socket/process is gone."""
        if isinstance(exc, (socket.timeout, OSError, P.ProtocolError, ConnectionError)):
            return True
        # EnvClient wraps a dead-peer read as EnvClientError only for ErrorResponse;
        # a genuinely dead child is caught above. Also treat a not-alive proc as crash.
        if not child.proc.is_alive():
            return True
        return False

    def shutdown(self) -> None:
        """CloseRequest + terminate every tracked PID. Idempotent; never orphans."""
        if self._closed:
            return
        self._closed = True
        for i, child in enumerate(self.children):
            if child is None:
                continue
            try:
                child.proc.shutdown()
            except Exception:
                pass
            finally:
                self._release_port(child.port)
            self.children[i] = None

    # -- context manager ---------------------------------------------------

    def __enter__(self) -> "ProcessSupervisor":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.shutdown()


def _is_port_free(port: int) -> bool:
    """True if ``127.0.0.1:port`` can currently be bound."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()
