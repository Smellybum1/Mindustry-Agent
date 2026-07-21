# Codex Handoff Prompt

Take over **mindustry-coop-agents** in `C:\Codex\Mindustry Agent`, branch
`coop-agent/v159.7`, after the failed V9 held-out-v3 final and ADR-0019 parity
correction.

Read first, in order:

1. `AGENTS.md` in full; obey the no-subagent rule.
2. `docs/codex-handoffs/2026-07-21-m8-5.md` in full.
3. Only M8.5 and the M8 exit criteria in `docs/ROADMAP.md` initially.
4. `docs/M8_DESIGN.md`, `docs/REWARD_AUDIT.md`, and ADR-0011 through ADR-0019.

Run `bash scripts/codex-status.sh`. Preserve and never stage the user-modified
`AGENTS.md`, generated `annotations/src/main/resources/classids.properties`, or
the two protected stat-only upstream files `core/src/mindustry/ai/BlockIndexer.java`
and `core/src/mindustry/entities/Units.java`. Then run the baseline from the
dated handoff.

V9 is the exact checkpoint
`3ae49108c913b0783300744d906eda0ca2b7846115f3919378fc7ab9e8d2c998`
with lineage
`c329bfc096122a13b2b5b18c4f1ff90bbaafa30fde621e70a7c25302ccc7f88c`.
It completed exclusive dev-v5 at 65/80, then consumed held-out-v3 exactly once.
The final was V9 70/80, permanent random 33/80, permanent greedy 49/80, and
matched greedy 5/80. Win gates passed, but permanent-greedy announcements,
idle, and abandonment regressed; permanent recovery and matched idle were
uncertain. V9 is not promoted. Never rerun v3 or inspect its individual
outcomes/traces for policy work.

The final exposed a real governance defect: development preflight had required
the paired teammate scorecard only against matched greedy, while final also
required permanent greedy. ADR-0019 corrects that mismatch. Future preflight
must load exact seed-level permanent records, require scorecard non-regression
against both permanent greedy and matched greedy, hash the permanent record
source, and have final revalidate it.

ADR-0019 freezes the 160-root, globally disjoint
`bootstrap-defense-v1-held-out-v4` contract before further model work.
Development tools refuse it. It permits one exclusive future final only after
a new immutable candidate names v4 and passes a newly governed confirmation
under the corrected dual-scorecard gate. Choose future behavior from train/dev
evidence only. M9.1 remains gated on an M8 promotion.

ADR-0020 precommits that next candidate as V10. It uses V6's 64-root, 32-cycle
PPO recipe and adds one training-only coefficient: `1.0` adaptive-v1
cross-entropy on every unforced transition. Reward, features, model, masks,
lifecycle, RNGs, and inference remain unchanged. Its config already names
held-out-v4. Implement zero-default telemetry compatibility, reproduce two
pinned runs, screen dev-v1, then use the frozen 160-root dev-v6 set for one
corrected dual-scorecard confirmation. Do not open held-out-v4 unless every
gate passes.

Preserve engine pins, fixed-step determinism, simulation-thread ownership,
structured-authoritative communication, and the four-JVM cap. Do not push or
make machine-global changes.
