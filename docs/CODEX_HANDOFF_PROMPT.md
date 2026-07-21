# Codex Handoff Prompt

Take over **mindustry-coop-agents** in `C:\Codex\Mindustry Agent`, branch
`coop-agent/v159.7`, and continue from M8.5.

Read first, in order:

1. `AGENTS.md` in full; obey the no-subagent rule.
2. `docs/codex-handoffs/2026-07-21-m8-5.md` in full.
3. Only M8.5 and the M8 exit criteria in `docs/ROADMAP.md` initially.
4. `docs/M8_DESIGN.md`, `docs/REWARD_AUDIT.md`, ADR-0011, and ADR-0012.

Run `bash scripts/codex-status.sh`, preserve the user's modified `AGENTS.md`,
and never stage generated `annotations/src/main/resources/classids.properties`.
Then run the baseline from the dated handoff.

M8.4 is complete but its selected checkpoint is 0/10 on dev and is not a
promotion candidate. Improve/freeze candidates with train/dev only, run the
required matched ablations and scorecard checks, and keep every reward change
behind a renewed audit/adversary gate. Do **not** open held-out until all M8.5
preconditions are satisfied and the code/checkpoint/comparators are frozen;
held-out is a one-way final evaluation, not a tuning set. Preserve engine pins,
fixed-step determinism, simulation-thread ownership, structured-authoritative
communication, and the four-JVM cap. Do not push or make machine-global changes.
