"""Shared scripted skill trace for the M3 smoke and determinism harnesses.

A single, fixed action+tick schedule that both harnesses replay verbatim, so the
determinism check (two JVMs, identical hashes at every boundary) now exercises the
skill state machines and their engine effects, not just the clock.

The trace (against the in-code ``bootstrap-defense-v0`` scenario, 48x48, core at tile
(24,24), copper patch at tiles 30..35):

* ``agent_0`` mines copper from tile (32,32) targeting 20 units, then delivers to the
  core. Mining accrues ~1 copper / 10 ticks and the mine->inventory transfer lands 12
  ticks late (docs/ENGINE_NOTES.md), so the mine phase is budgeted generously.
* ``agent_1`` is pointed at a plain stone tile (20,20) — not ore — to exercise the
  ``BLOCKED(invalid_target)`` skill status.

Everything here is deterministic: fixed tiles, fixed amounts, fixed tick counts.
"""

from __future__ import annotations

# Copper ore tile in the in-code scenario patch (tiles 30..35 inclusive).
COPPER_TILE = (32, 32)
# A plain stone tile (no ore overlay) — an invalid mine target.
STONE_TILE = (20, 20)
MINE_AMOUNT = 20

CHUNK = 20  # ticks per scripted step (fine enough to observe skill transitions)


def mine_action(agent_id: int, tile, amount: int = MINE_AMOUNT) -> dict:
    return {
        "agent_id": agent_id,
        "command": {"type": "MINE", "tile_x": tile[0], "tile_y": tile[1], "amount": amount},
    }


def deliver_action(agent_id: int) -> dict:
    return {"agent_id": agent_id, "command": {"type": "DELIVER_CORE"}}


def scripted_steps() -> list[tuple[str, list[dict], int]]:
    """The fixed schedule: list of ``(label, agent_actions, ticks_to_advance)``.

    Step 0 issues the MINE commands (agent_0 valid, agent_1 invalid); subsequent
    ``CONTINUE`` steps (empty bundle) keep the active skills running. The deliver
    command is issued once the mine phase has completed.
    """
    steps: list[tuple[str, list[dict], int]] = []

    # Mine phase: issue MINE, then continue for a generous window (20 * 20 = 400 ticks).
    steps.append(
        ("mine", [mine_action(0, COPPER_TILE), mine_action(1, STONE_TILE)], CHUNK)
    )
    for _ in range(19):
        steps.append(("mine_cont", [], CHUNK))

    # Deliver phase: issue DELIVER_CORE for agent_0, then continue (4 * 20 = 80 ticks).
    steps.append(("deliver", [deliver_action(0)], CHUNK))
    for _ in range(3):
        steps.append(("deliver_cont", [], CHUNK))

    return steps
