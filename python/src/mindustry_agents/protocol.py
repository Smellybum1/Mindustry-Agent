"""Length-prefixed JSON protocol for the bootstrap phase (ADR-0004).

Wire format (see ``docs/PROTOCOL.md`` for the authoritative spec):

* Each message is a 4-byte big-endian unsigned length prefix followed by that
  many bytes of a UTF-8 encoded JSON object.
* The JSON object always carries a ``type`` field that discriminates the message.
* Maximum message size is 16 MiB (the length prefix, and any decoded frame, is
  rejected above this bound).

This module is **standard-library only** (dataclasses, json, struct, enum). It
must never import an RL framework (ADR-0007). Message field names mirror the Java
side; if you change a field here, change ``docs/PROTOCOL.md`` and the Java
protocol in the same commit.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field, asdict
from typing import Any, ClassVar

PROTOCOL_VERSION: int = 1
LENGTH_PREFIX_BYTES: int = 4
MAX_MESSAGE_SIZE: int = 16 * 1024 * 1024  # 16 MiB
_LENGTH_STRUCT = struct.Struct(">I")  # 4-byte big-endian unsigned


class ProtocolError(Exception):
    """Raised on framing violations or unknown/oversized messages."""


# --------------------------------------------------------------------------- #
# Message dataclasses. Every message declares TYPE, used as the JSON ``type``.
# --------------------------------------------------------------------------- #


@dataclass
class Timing:
    """Per-step timing breakdown in milliseconds (brief §18.5)."""

    engine_ms: float = 0.0
    observation_ms: float = 0.0
    serialization_ms: float = 0.0
    io_ms: float = 0.0


@dataclass(frozen=True)
class BuildPlanObservation:
    """Current first engine build plan in ordered queue execution order (M4.7)."""

    breaking: bool = False
    block: str = ""
    tile_x: int = 0
    tile_y: int = 0
    rotation: int = 0
    progress: float = 0.0


@dataclass(frozen=True)
class TurretAmmoObservation:
    """One ID-ordered team turret summary using native ammo units (M4.7)."""

    id: int = 0
    block: str = ""
    tile_x: int = 0
    tile_y: int = 0
    total_ammo: int = 0


@dataclass
class HandshakeRequest:
    TYPE: ClassVar[str] = "handshake_request"
    protocol_version: int = PROTOCOL_VERSION
    client_name: str = ""
    requested_features: list[str] = field(default_factory=list)


@dataclass
class HandshakeResponse:
    TYPE: ClassVar[str] = "handshake_response"
    protocol_version: int = PROTOCOL_VERSION
    engine_version: str = ""
    engine_commit: str = ""
    arc_version: str = ""
    scenario_schema_version: int = 1
    supported_features: list[str] = field(default_factory=list)
    process_id: int = 0


@dataclass
class ResetRequest:
    TYPE: ClassVar[str] = "reset_request"
    request_id: int = 0
    scenario_id: str = ""
    scenario_version: int = 1
    root_seed: int = 0
    agent_count: int = 0
    difficulty: str = "normal"
    deterministic: bool = True
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResetResponse:
    TYPE: ClassVar[str] = "reset_response"
    request_id: int = 0
    episode_id: str = ""
    tick: int = 0
    initial_observations: list[dict[str, Any]] = field(default_factory=list)
    action_masks: list[dict[str, Any]] = field(default_factory=list)
    state_hash: str = ""
    # Scenario episode outcome: "running" at reset; "win"/"loss"/"truncated" once terminal.
    outcome: str = "running"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepRequest:
    TYPE: ClassVar[str] = "step_request"
    request_id: int = 0
    episode_id: str = ""
    expected_tick: int = 0
    ticks_to_advance: int = 1
    agent_actions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class StepResponse:
    TYPE: ClassVar[str] = "step_response"
    request_id: int = 0
    episode_id: str = ""
    previous_tick: int = 0
    tick: int = 0
    observations: list[dict[str, Any]] = field(default_factory=list)
    action_masks: list[dict[str, Any]] = field(default_factory=list)
    # M3 (additive): per-action accept/reject with a machine-readable reason
    # (docs/PROTOCOL.md §2.3, docs/M3_DESIGN.md D5). One entry per submitted action.
    action_results: list[dict[str, Any]] = field(default_factory=list)
    team_state: dict[str, Any] = field(default_factory=dict)
    reward_breakdowns: list[dict[str, Any]] = field(default_factory=list)
    terminations: list[bool] = field(default_factory=list)
    truncations: list[bool] = field(default_factory=list)
    # Scenario episode outcome: "running", or terminal "win"/"loss"/"truncated".
    outcome: str = "running"
    task_events: list[dict[str, Any]] = field(default_factory=list)
    game_events: list[dict[str, Any]] = field(default_factory=list)
    state_hash: str = ""
    timing: dict[str, Any] = field(default_factory=lambda: asdict(Timing()))


@dataclass
class HealthRequest:
    TYPE: ClassVar[str] = "health_request"
    request_id: int = 0


@dataclass
class HealthResponse:
    TYPE: ClassVar[str] = "health_response"
    request_id: int = 0
    ok: bool = True
    uptime_ticks: int = 0
    episode_id: str = ""
    detail: str = ""


@dataclass
class CloseRequest:
    TYPE: ClassVar[str] = "close_request"
    request_id: int = 0
    reason: str = ""


@dataclass
class ErrorResponse:
    TYPE: ClassVar[str] = "error_response"
    request_id: int = 0
    code: str = "unknown"
    message: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


# Registry mapping the wire ``type`` discriminator to its dataclass.
_MESSAGE_TYPES: dict[str, type] = {
    cls.TYPE: cls
    for cls in (
        HandshakeRequest,
        HandshakeResponse,
        ResetRequest,
        ResetResponse,
        StepRequest,
        StepResponse,
        HealthRequest,
        HealthResponse,
        CloseRequest,
        ErrorResponse,
    )
}


def message_types() -> dict[str, type]:
    """Return a copy of the discriminator -> dataclass registry."""
    return dict(_MESSAGE_TYPES)


# --------------------------------------------------------------------------- #
# (De)serialization to/from plain dicts.
# --------------------------------------------------------------------------- #


def to_dict(message: Any) -> dict[str, Any]:
    """Convert a message dataclass to a wire dict with its ``type`` field set."""
    type_name = getattr(type(message), "TYPE", None)
    if type_name is None:
        raise ProtocolError(f"not a protocol message: {type(message)!r}")
    payload = asdict(message)
    payload["type"] = type_name
    return payload


def from_dict(payload: dict[str, Any]) -> Any:
    """Rebuild the matching message dataclass from a decoded wire dict."""
    if not isinstance(payload, dict):
        raise ProtocolError("message payload must be a JSON object")
    type_name = payload.get("type")
    if type_name is None:
        raise ProtocolError("message payload missing 'type' discriminator")
    cls = _MESSAGE_TYPES.get(type_name)
    if cls is None:
        raise ProtocolError(f"unknown message type: {type_name!r}")
    known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
    kwargs = {k: v for k, v in payload.items() if k in known}
    return cls(**kwargs)


# --------------------------------------------------------------------------- #
# Frame encode/decode: 4-byte BE length prefix + UTF-8 JSON.
# --------------------------------------------------------------------------- #


def encode(message: Any) -> bytes:
    """Encode a message dataclass into a complete length-prefixed frame."""
    body = json.dumps(to_dict(message), separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_MESSAGE_SIZE:
        raise ProtocolError(
            f"message body {len(body)} bytes exceeds max {MAX_MESSAGE_SIZE}"
        )
    return _LENGTH_STRUCT.pack(len(body)) + body


def decode(frame: bytes) -> Any:
    """Decode a single complete length-prefixed frame into a message dataclass.

    Raises :class:`ProtocolError` if the frame is truncated, mis-sized, or has a
    length prefix that does not match the body length.
    """
    if len(frame) < LENGTH_PREFIX_BYTES:
        raise ProtocolError("frame shorter than length prefix")
    (declared,) = _LENGTH_STRUCT.unpack(frame[:LENGTH_PREFIX_BYTES])
    if declared > MAX_MESSAGE_SIZE:
        raise ProtocolError(
            f"declared length {declared} exceeds max {MAX_MESSAGE_SIZE}"
        )
    body = frame[LENGTH_PREFIX_BYTES:]
    if len(body) != declared:
        raise ProtocolError(
            f"frame body length {len(body)} != declared length {declared}"
        )
    return from_dict(json.loads(body.decode("utf-8")))


def decode_stream(buffer: bytes) -> tuple[list[Any], bytes]:
    """Decode zero or more whole frames from a byte buffer.

    Returns ``(messages, remainder)`` where ``remainder`` holds any trailing
    bytes that do not yet form a complete frame. Useful for streaming sockets
    where reads do not align to frame boundaries.
    """
    messages: list[Any] = []
    offset = 0
    n = len(buffer)
    while n - offset >= LENGTH_PREFIX_BYTES:
        (declared,) = _LENGTH_STRUCT.unpack(buffer[offset : offset + LENGTH_PREFIX_BYTES])
        if declared > MAX_MESSAGE_SIZE:
            raise ProtocolError(
                f"declared length {declared} exceeds max {MAX_MESSAGE_SIZE}"
            )
        frame_end = offset + LENGTH_PREFIX_BYTES + declared
        if frame_end > n:
            break  # incomplete frame; wait for more bytes
        body = buffer[offset + LENGTH_PREFIX_BYTES : frame_end]
        messages.append(from_dict(json.loads(body.decode("utf-8"))))
        offset = frame_end
    return messages, buffer[offset:]


def read_message(recv) -> Any:
    """Read one framed message using a blocking ``recv(n) -> bytes`` callable.

    ``recv`` is any function returning up to ``n`` bytes (e.g. ``socket.recv``);
    an empty return signals a closed peer. Kept transport-agnostic so this module
    does not import ``socket``.
    """
    header = _recv_exactly(recv, LENGTH_PREFIX_BYTES)
    (declared,) = _LENGTH_STRUCT.unpack(header)
    if declared > MAX_MESSAGE_SIZE:
        raise ProtocolError(
            f"declared length {declared} exceeds max {MAX_MESSAGE_SIZE}"
        )
    body = _recv_exactly(recv, declared)
    return from_dict(json.loads(body.decode("utf-8")))


def _recv_exactly(recv, count: int) -> bytes:
    chunks: list[bytes] = []
    remaining = count
    while remaining > 0:
        chunk = recv(remaining)
        if not chunk:
            raise ProtocolError("peer closed connection mid-frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
