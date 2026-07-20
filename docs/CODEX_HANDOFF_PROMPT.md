# Codex Handoff Prompt

Paste the block below into the replacement Codex task. The detailed current
state lives in the dated handoff so this entry point stays small.

---

Take over **mindustry-coop-agents** in `C:\Codex\Mindustry Agent`, branch
`coop-agent/v159.7`. Continue the Phase 2 roadmap from M8.4 without changing
the pinned Mindustry v159.7 engine or the deterministic externally stepped
environment.

Read first, in this order:

1. `AGENTS.md` in full. It is authoritative, including the project-wide rule
   that all work stays in the primary agent with no subagent delegation.
2. `docs/codex-handoffs/2026-07-21-m8-4.md` in full. It contains the verified
   state, dirty-file ownership, invariants, exact first task, and validation.
3. Only the M8.4 subsection of `docs/ROADMAP.md` initially. Read adjacent
   roadmap items when their work begins.
4. `docs/M8_DESIGN.md`, `docs/REWARD_AUDIT.md`, ADR-0011/0012, and the public
   candidate/policy/collector code; they define M8.4's schemas and hard gates.

Read `docs/ARCHITECTURE.md`, accepted ADRs, `docs/ENGINE_NOTES.md`, and
`docs/UPSTREAM_PATCHES.md` only when the work enters their scope. Use the other
domain docs as references instead of loading the full project history up front.

Run `bash scripts/codex-status.sh`, then the required baseline:

```bash
bash scripts/smoke.sh && bash scripts/determinism.sh && \
  bash scripts/evaluate-ladder.sh
# Separately inside Ubuntu-24.04/WSL2:
UV=/path/to/uv-0.11.16 bash scripts/verify-rl-boundary.sh
```

If green, complete M8.4: expose the exact framework-neutral feature/reward
adapter from M8_DESIGN, pass every reward-audit adversary before reward can
influence training, train the one-seat PPO selector, and write exact
run/checkpoint manifests with bit-exact deterministic evaluation. Do not run or
tune against held-out seeds; that remains M8.5. If red,
diagnose before changing behavior. Preserve unrelated dirty work, never stage
the generated `classids.properties`, make small descriptive local commits, do
not push, and keep `STATUS.md`, `HANDOFF.md`, and `ROADMAP.md` truthful.

---

Human note: the current dated handoff is the source for rollover state. Update
both files only when the verified state or next task changes.
