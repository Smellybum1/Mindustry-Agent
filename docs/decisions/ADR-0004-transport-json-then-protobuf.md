# ADR-0004: Transport — length-prefixed JSON now, Protobuf later

**Status:** Accepted

## Context

The Python controller and each JVM environment exchange handshake/reset/step/
health/close messages over a local socket. We need something inspectable and
fast to build for the first vertical slice, without paying codegen cost up front.

## Decision

For the **bootstrap phase**, use **length-prefixed JSON over loopback TCP**:
4-byte big-endian length prefix + UTF-8 JSON object, `type` field discriminates,
16 MiB max message. Schema-versioned; message names `Handshake/Reset/Step/Health/
Close` (+ `Error`) as in brief §18 and `docs/PROTOCOL.md`. **Migrate to Protobuf
before large-scale training (Stage D)** if/when profiling shows serialization
>10% of step time (brief §24 Gate 6) or schema drift becomes a risk.

## Alternatives considered

- **Protobuf from day one**: rejected for bootstrap — puts protoc/codegen on the
  critical path of the first slice; messages are small and inspectable in JSON.
- **Shared memory / Unix-domain sockets first**: premature optimization; loopback
  TCP is portable across Windows dev and Linux/WSL2.
- **Pickle / Java serialization across the boundary**: rejected — insecure,
  language-coupled, not schema-versioned.

## Consequences

- Fast to implement and debug; human-readable transcripts.
- Higher serialization cost than Protobuf; acceptable while messages are small.
- The JSON message shapes are the contract the future Protobuf schema preserves.

## Reversal conditions

Switch to Protobuf (or shared memory) when Gate 6 fails or schema drift bites.
