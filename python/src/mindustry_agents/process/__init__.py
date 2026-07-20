"""JVM process supervision.

Will launch and supervise one persistent ``rl-server`` JVM per environment
(ADR-0003), own the loopback-TCP connections, enforce request timeouts, detect
dead children, and restart crashed processes. One environment maps to one JVM;
parallelism comes from many persistent processes, not many worlds per JVM.

M2 status: implemented. ``launcher.py`` owns a single JVM (build/spawn, READY
parsing, control connection, stderr capture, graceful shutdown). ``supervisor.py``
manages a pool of them — unique ports, per-child seeds/logs, handshake
verification, crash/hang detection with automatic replacement, and orphan-free
shutdown (atexit + context manager).
"""
