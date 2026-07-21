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

V6 restores 32 visits per each of 64 train roots. Two pinned runs reproduce
exactly and selected update 31 at 9/10 dev wins; direct-checkpoint lineage is
implemented. Construct lineage and run the full frozen dev scorecard preflight
before deciding whether v2 is eligible. Do not treat the 9/10 screen alone as
held-out authorization.

The dev-v1 preflight passed all win-rate comparisons but failed scorecard
certainty. ADR-0014 now freezes `bootstrap-defense-v1-dev-v2` as a 40-root
one-way V6 confirmation with an exclusive attempt. Refresh permanent baselines
on dev-v2 and run that confirmation before considering held-out-v2.

That exclusive attempt was created but aborted before result artifacts on a
matched-control catalog-WAIT indexing bug. ADR-0014 consumes the attempt, so do
not rerun dev-v2 and do not open held-out-v2 for V6. The control bug is fixed;
the next step requires a newly governed successor candidate/confirmation path.

ADR-0015 now precommits that successor: V7 is a 90/10 V6 update-31 / V4
update-5 blend with explicit cross-commit lineage. Construct it twice from the
A/B parent replicas and require exact equality, then run dev-v1. Dev-v3 is
frozen for one confirmation only if V7 qualifies; held-out-v2 stays sealed.
