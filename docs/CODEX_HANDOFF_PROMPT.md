# Codex Handoff Prompt

Take over `C:\Codex\Mindustry Agent` on branch `coop-agent/v159.7`.

Read first, in order:

1. `AGENTS.md` in full. Its no-delegation and sealed-data rules are mandatory.
2. The newest dated file in `docs/codex-handoffs/`.
3. Only the roadmap subsection and accepted ADRs named by that dated handoff.

Do not read all of `docs/HANDOFF.md`, `docs/STATUS.md`, or `docs/ROADMAP.md`
during ordinary startup; they are cumulative reference histories. Drill into
them only when the active handoff identifies a specific section.

Run:

```bash
bash scripts/codex-status.sh
```

Preserve and never stage these user-owned local modifications:

- `AGENTS.md`
- `annotations/src/main/resources/classids.properties`
- `core/src/mindustry/ai/BlockIndexer.java`
- `core/src/mindustry/entities/Units.java`

Preserve engine pins, fixed-step determinism, simulation-thread ownership,
structured-authoritative communication, the four-JVM cap, and every accepted
ADR. Do not access sealed, held-out, confirmation, or embargoed manifests
unless the active handoff identifies a committed eligible gate. Do not make
machine-global changes.

The GitHub remote is authorized for project commits and pushes. Continue the
active handoff's recommended task; do not merely summarize it.
