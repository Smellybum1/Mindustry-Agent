# Codex Handoff Prompt

Paste the block below into the replacement Codex task. The detailed current
state lives in the dated handoff so this entry point stays small.

---

Take over **mindustry-coop-agents** in `C:\Codex\Mindustry Agent`, branch
`coop-agent/v159.7`. Continue the Phase 2 roadmap from M7.2 without changing
the pinned Mindustry v159.7 engine or the deterministic externally stepped
environment.

Read first, in this order:

1. `AGENTS.md` in full. It is authoritative, including the project-wide rule
   that all work stays in the primary agent with no subagent delegation.
2. `docs/codex-handoffs/2026-07-20-m7-2.md` in full. It contains the verified
   state, dirty-file ownership, invariants, exact first task, and validation.
3. Only the M7.2 subsection of `docs/ROADMAP.md` initially. Read adjacent
   roadmap items when their work begins.
4. `docs/REVIEW_M6.md` finding 5 for the parity problem M7.2 resolves.

Read `docs/ARCHITECTURE.md`, accepted ADRs, `docs/ENGINE_NOTES.md`, and
`docs/UPSTREAM_PATCHES.md` only when the work enters their scope. Use the other
domain docs as references instead of loading the full project history up front.

Run `bash scripts/codex-status.sh`, then the required baseline:

```bash
bash scripts/smoke.sh && bash scripts/determinism.sh
```

If green, implement M7.2 (one coordination brain) to its decision-sequence
parity and demo-survival acceptance criteria. If red, diagnose before changing
behavior. Preserve unrelated dirty work, never stage the generated
`classids.properties`, make small descriptive local commits, do not push, and
keep `STATUS.md`, `HANDOFF.md`, and `ROADMAP.md` truthful.

---

Human note: the current dated handoff is the source for rollover state. Update
both files only when the verified state or next task changes.
