# Codex Handoff Prompt

Take over **mindustry-coop-agents** in `C:\Codex\Mindustry Agent`, branch
`coop-agent/v159.7`, after the failed M8.5 one-way final.

Read first, in order:

1. `AGENTS.md` in full; obey the no-subagent rule.
2. `docs/codex-handoffs/2026-07-21-m8-5.md` in full.
3. Only M8.5 and the M8 exit criteria in `docs/ROADMAP.md` initially.
4. `docs/M8_DESIGN.md`, `docs/REWARD_AUDIT.md`, ADR-0011, and ADR-0012.

Run `bash scripts/codex-status.sh`, preserve the user's modified `AGENTS.md`,
and never stage generated `annotations/src/main/resources/classids.properties`.
Then run the baseline from the dated handoff.

M8.5's frozen 75/25 candidate passed dev preflight but was not promoted by the
one-way held-out-v1 final. The completed attempt marker forbids any rerun. Do not
inspect individual held-out episodes or choose behavior from their outcomes.
M9.1 is explicitly gated on a promoted single learned seat, so do not bypass it.
First govern an honest post-failure path—such as a separately versioned sealed
contract or superseding ADR—before any more training or evaluation. Preserve
engine pins, fixed-step determinism, simulation-thread ownership,
structured-authoritative communication, and the four-JVM cap. Do not push or
make machine-global changes.
