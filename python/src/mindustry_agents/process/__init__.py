"""JVM process supervision.

Will launch and supervise one persistent ``rl-server`` JVM per environment
(ADR-0003), own the loopback-TCP connections, enforce request timeouts, detect
dead children, and restart crashed processes. One environment maps to one JVM;
parallelism comes from many persistent processes, not many worlds per JVM.

Currently a skeleton package; the supervisor lands in roadmap M2.
"""
