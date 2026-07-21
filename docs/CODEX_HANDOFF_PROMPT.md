# Codex Handoff Prompt

Take over **mindustry-coop-agents** in `C:\Codex\Mindustry Agent`, branch
`coop-agent/v159.7`, after the failed M8.5 one-way final.

Read first, in order:

1. `AGENTS.md` in full; obey the no-subagent rule.
2. `docs/codex-handoffs/2026-07-21-m8-5.md` in full.
3. Only M8.5 and the M8 exit criteria in `docs/ROADMAP.md` initially.
4. `docs/M8_DESIGN.md`, `docs/REWARD_AUDIT.md`, ADR-0011, ADR-0012, and
   ADR-0013.

Run `bash scripts/codex-status.sh`, preserve the user's modified `AGENTS.md`,
and never stage generated `annotations/src/main/resources/classids.properties`.
Then run the baseline from the dated handoff.

M8.5's frozen 75/25 candidate passed dev preflight but was not promoted by the
one-way held-out-v1 final. The completed attempt marker forbids any rerun. Do not
inspect individual held-out episodes or choose behavior from their outcomes.
M9.1 is explicitly gated on a promoted single learned seat, so do not bypass it.
ADR-0013 has frozen the 40-root `bootstrap-defense-v1-held-out-v2` contract
before successor model work; development tools must refuse it and it permits
one exclusive future final. Choose any next M8 candidate using train/dev
evidence only and make its immutable config name v2 before training. Preserve
engine pins, fixed-step determinism, simulation-thread ownership,
structured-authoritative communication, and the four-JVM cap. Do not push or
make machine-global changes.

The first successor diversity hypothesis, `m8-selector-v3-diverse`, reproduced
exactly but achieved only 3/10 dev wins and was rejected before preflight. Do
not open v2 for it.
