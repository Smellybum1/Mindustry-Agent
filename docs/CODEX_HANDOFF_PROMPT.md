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
cross-entropy on every unforced transition. Reward and inference remain
unchanged. The implementation and zero-default telemetry are complete. Two
pinned runs reproduce exactly but select update 6 at only 1/10 dev wins
(`a20f44d6ec093076...`; full run `787b5d4bd6548eea...`), so V10 is rejected.
Dev-v6 and held-out-v4 remain unopened. Choose the next candidate from existing
train/dev evidence and precommit it before implementation or execution.

ADR-0021 now precommits V11 as a 90/10 interpolation of reproducible V6 update
31 and V10 update 6, using V7's established blend weight. Construct it twice
with cross-commit lineage, then require at least 9/10 dev-v1 wins. Construction
matches at checkpoint `0a8fa8b4ba98581d...`, lineage `845282326c58308c...`,
and dev-v1 is 9/10. Dev-v6 is retired unopened. Dev-v7 is frozen as a new
160-root one-way confirmation under the corrected permanent-plus-matched
scorecard gate. It completes at V11 137/160, permanent random 69/160,
permanent greedy 100/160, matched random 19/160, and matched greedy 12/160.
All win and matched scorecard gates pass, but permanent announcements, idle,
recovery, and abandonment fail. V11 is rejected and dev-v7 consumed.
Held-out-v4 stays sealed. Precommit any next candidate and confirmation path
before execution.

ADR-0022 now precommits V12 and dev-v8. Implement `selector_reward_v2` exactly
as audited: v1 plus bounded negative-only idle-tick, duplicate-work,
announcement, and non-forced team-abandonment costs. Preserve v1 behavior and
make cross-schema checkpoint loading fail. Expand reward adversaries before any
training. V12 then uses V6's long recipe and must reproduce, reach 9/10 dev-v1,
and lower mean idle below 0.25 before exclusive dev-v8. Held-out-v4 stays sealed.

V12's exact runs select update 28 at 10/10 wins but idle 0.26628148, so it is
rejected and dev-v8 is retired unopened. ADR-0023 precommits V13 as the same
construction with a strict 9/10-win and `<0.25`-idle checkpoint gate. Two exact
V13 runs select update 24 at 10/10 and idle 0.24980951; checkpoint
`ff5c21bc6644d903...`, full-run digest `842ac034e91e84ae...`, and lineage
`8aff4629be3090b3...` reproduce. Dev-v9 is frozen at roots `91001..91160` for
one exclusive dual-scorecard confirmation. It completes at V13 152/160,
permanent random 62/160, permanent greedy 92/160, matched random 13/160, and
matched greedy 15/160. All win and matched scorecards pass; permanent
announcements, idle, recovery, and abandonment fail. V13 is rejected and
held-out-v4 remains sealed. Precommit any successor before construction.

Preserve engine pins, fixed-step determinism, simulation-thread ownership,
structured-authoritative communication, and the four-JVM cap. Do not push or
make machine-global changes.
