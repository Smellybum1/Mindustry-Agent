# Codex Handoff Prompt

Take over **mindustry-coop-agents** in `C:\Codex\Mindustry Agent`, branch
`coop-agent/v159.7`, after ADR-0056 precommits and implements V42's training-only
partner-intent teacher-conflict relabel. The complete public/pretraining boundary
is green and dev-v38 is frozen value-free and unopened. Exact V42 replicas
complete, but reusable scorecards reject V42 before confirmation. Dev-v38 is
retired unopened/unconsumed and no restricted membership access began.

Read first, in order:

1. `AGENTS.md` in full; obey its no-agent-delegation and sealed-data rules.
2. `docs/HANDOFF.md`, focusing on the V41 rejection, V42 precommit, and the
   next-five queue.
3. M8.5 and the M8 exit criteria in `docs/ROADMAP.md`.
4. ADR-0053, ADR-0054, ADR-0055, and ADR-0056.

Run `bash scripts/codex-status.sh`. Preserve and never stage the user-modified
`AGENTS.md`, generated
`annotations/src/main/resources/classids.properties`, or protected stat-only
upstream files `core/src/mindustry/ai/BlockIndexer.java` and
`core/src/mindustry/entities/Units.java`. Then run the baseline:

```bash
bash scripts/smoke.sh && bash scripts/determinism.sh
```

V29 replica A completed 256 teacher episodes and all 2,048 PPO episodes/32
updates but failed construction. Its frozen teacher set yielded 37 wins and 860
eligible transitions. Warmup/rehearsal/frontier SHA-256 values are
`582f362322e4aa43916f0e80c65bcfec3fe1e33e713e2bf590f02ad7e96fe736`,
`b5c089bf4d85acd238f8c8cc3d0ed1b42e7916e877dbd3b8eb4b8c5391e0efcc`,
and `26c6270efca0c85210fb4c4fb9486ecd6cfe9e4fc7fe71618c33bb811bb31c1a`.
No checkpoint exceeded 4/10. Replica B did not start, dev-v25 was retired
unopened, and held-out-v4 remains sealed.

ADR-0041 precommitted V30 as the isolated correction. V29 increased the corpus
from 121 to 860 transitions while leaving epoch counts fixed, multiplying CE
optimization roughly sevenfold. V30 keeps the complete diverse corpus but caps
each warmup and rehearsal epoch at 121 deterministic samples. This restores
V28's 968 warmup presentations and one rehearsal batch per PPO update while
rotating through V29's broader corpus. Exact sampled indices, coverage, and
schedule hashes are reproducibility evidence. Historical cap-free configs keep
their full-corpus behavior.

The immutable V30 config is
`configs/training/m8-selector-v30-budgeted-diverse-teacher-corpus.json`, SHA-256
`c57556695157dcd4b405ea7a69a527ee6f3c304a67cd042599e9ebf84571473d`.
Pretraining gates are green: 44 exact-config reward adversaries (report SHA-256
`a3bcf116478e1be0948c8653deccba749bd5f97b84b058093275eb22c5298677`),
155 Python tests, pinned build, 5/5 candidate-policy survival, smoke, golden
determinism, and negative replay. Dev-v26 is frozen at roots `261001..261160`
and was unopened at precommit. No V30 teacher collection or model work preceded
the committed packet.

V30 replica A then completed all construction work but peaked at 8/10. Warmup
restored 968 presentations/eight batches and sampled 603/860 transitions;
rehearsal restored 3,872 presentations and covered 855/860 transitions across
updates. Twenty-one checkpoints reached 8/10; best-ranked update 11 has mean
return `1.18132`, core health `686.5`, and idle `0.06573742`. Warmup,
rehearsal, and frontier SHA-256 values are
`7f92ee1bdaa59d8ff1138f876d30c62bc9d5600b17bf3b50e2231a5dbc5edd8e`,
`a2559f5651cc0d54a0c8cee8d179a9155a66fd9604a281d2f99d2f90e3c203c3`,
and `e841b620424e0299b8fb099128b53a827c6f77973551e5386601d00bc2bd2ebe`.
Replica B did not start, dev-v26 is retired unopened, and held-out-v4 remains
sealed.

ADR-0042 precommits V31 from reusable diagnosis. V30 update 11 loses the same
seeds 2004/2005 as V24. Every reusable seed chooses `BUILD_LINE` over the
teacher's `BUILD_SCHEMATIC` at tick 0 by `0.83764815..0.85484707`; seed 2004 has
only six policy decisions and two disagreements. V31 keeps V30 exact and adds a
`+1.0` prior only to a valid tick-0 `BUILD_SCHEMATIC` logit. Masked selection
still chooses the action. The same tensor is used by rollout, PPO, teacher CE,
preflight, and final evaluation; historical configs remain exact.

The immutable config is
`configs/training/m8-selector-v31-initial-schematic-prior.json`, SHA-256
`861f34bd07db43a54aafb2b88ef725a0185c1aca685b533b32e99995ada1594b`.
Pretraining gates are green: 44 exact-config adversaries (report SHA-256
`e7eb2f8826db46171fd5f4c8a08666b8138f4c04b66511f260a95546321412d9`),
156 Python tests, pinned build, 5/5 candidate gate, smoke, determinism, and
negative replay. Dev-v27 is frozen at `271001..271160` and remains unopened.
No V31 model work preceded the committed packet.

V31 replicas reproduce selected update 16 exactly at 9/10 reusable wins.
Canonical full-run/direct-lineage hashes are `b2dacf42484258fb...` and
`78e923796393ca58...`. Reusable preflight beats all win-rate comparators but
rejects V31 on permanent idle/abandonment and matched abandonment, with
additional uncertain intervals. Dev-v27 is retired unopened. Diagnose and
precommit any successor only from reusable evidence, freeze a new disjoint
confirmation set before model work, and never open held-out-v4 without every
governed prerequisite.

ADR-0043 records V32's completed result. Exact replicas select update 28 at
10/10 with checkpoint `72e10ec9dcf9b30c...`, replay
`837102913ff2596d...`, canonical full-run `f4495f671fd72430...`, and direct
lineage `3744c81c88dd435f...`. Fresh V32-runtime reusable preflight eliminates
non-forced abandonment but still rejects permanent-greedy idle by
`+0.02116306` (95% CI `[+0.00659211,+0.03839977]`); permanent
announcements/recovery and matched recovery are uncertain. V32 is rejected and
dev-v28 is retired unopened.

ADR-0044 records V33's pretraining rejection. Reusable idle ticks by seat were
`[4.2, 408.8, 487.4]` versus permanent greedy
`[274.8, 51.5, 298.8]`, so V33 tested the exact V32 staging rule on seats 0 and
1 only. The hard live boundary failed before training: seed 23456 lost at tick
7593 and the gate was only 4/5. The experimental runtime edit was removed and
the accepted V32 runtime restored. V33 is rejected, dev-v29 is retired unopened,
and no model work began.

ADR-0045 precommits V34 from the reusable trace at
`runs/m8-selector-v32-partner-idle.json`. In all ten wins, seat 1's mask-valid
harvest claim loses at tick 254 but does not advance the decision revision, so
the unassigned seat remains idle until tick 660. Its all-seat wake was rejected:
survival stayed 5/5 but proactive-staging starts fell from five to zero. Every
public claim loss was learned-seat 0 (`[9,14,10,10,9]` by seed), whereas the
reusable defect is scripted seat 1. The experiment was removed and V32 rebuilt;
its complete gate again passes.

ADR-0046 precommits V35's fixed-seat correction. Wake only scripted seat 1 on
final atomic `claim_lost`; seat 0 and seat 2 preserve V32 scheduling. The focused
positive seat-1/negative seat-0 check, pinned Java build, and complete public
gate already pass; public survival is 5/5 with all five staging starts restored.
From implementation commit `673042bfd0`, smoke, determinism, the 16,200-tick
golden replay, and negative replay also pass. Exact replicas select update 8 at
9/10 and reproduce every governed digest, but reusable preflight rejects
permanent-greedy idle by `+0.01815752` with CI entirely above zero. Learned seat
0 loses the biased tick-0 schematic claim and idles 250 ticks in every episode;
without the prior its first choice is `BUILD_LINE`, but the off-contract
checkpoint wins only 6/10. Reject V35 and precommit a from-scratch collision-free
opening successor before model work. Dev-v31 is retired unopened; held-out-v4
remains sealed.

ADR-0047 precommits V36. It changes only the existing tick-0 `+1.0` prior from
`BUILD_SCHEMATIC` to `BUILD_LINE`; runtime/reward/teacher/training fields remain
V35-exact. Config/seed governance, 161 Python tests, and all reward adversaries
pass. From committed packet `f8b191c582`, inherited focused/public/Java, smoke,
cross-process/reset/seed determinism, the 16,200-tick golden replay, and negative
replay all pass. Replica A is authorized and must be trained from scratch under
the exact V36 config; require at least 9/10 reusable wins and mean idle below
0.25 before replica B. Dev-v32 is frozen at disjoint roots `285001..285160` but
unopened; held-out-v4 remains sealed.

V36 replica A completes all 32 updates, but no checkpoint reaches the 9/10
construction floor. Rank-best update 5 is 7/10 with return `-0.17522`, core
health `488.3`, and idle `0.05917146`; replica B is prohibited. Reusable-only
harvest and one-tick-replan diagnostics each win 6/10, while forced WAIT
reproduces V35's exact 9/10 outcomes and rejected idle profile. The accepted
public policy also loses the schematic claim at tick 0, so a server-side wake
is not isolated from V34's staging failure. Reject V36, retire dev-v32 unopened,
and diagnose accepted-task timelines for losses 2001/2003/2004 versus V35 wins
before precommitting any one-coordinate successor. Held-out-v4 remains sealed.

ADR-0048 precommits V37 from the accepted-task timelines. V37 restores the
complete V35 construction and changes only fixed scripted seat 2's tick-0
opening to the unique valid `HARVEST_RESOURCE` candidate. The unchanged V35
checkpoint wins 9/10 off-contract with mean core health `720.0` and idle ticks
`[267.0,0.7,308.2]`; seat-2 build-line and learned alternatives win only 6/10.
Config/seed governance and all 44 reward adversaries pass. The fail-closed
opening is implemented across training, replay, matched controls, confirmation,
and final evaluation; the full structured action is archived, legacy configs
and permanent public baselines remain unchanged, and 165 Python tests pass.
From implementation commit `0c4a09659f`, pinned Java build/tests, focused and
5/5 public gates, smoke, cross-process/reset/seed determinism, the 664-checkpoint/
16,200-tick golden replay, negative replay, and all 44 exact-config reward
adversaries pass. Replica A selects update 16 at 9/10, return `4.18676`, core
health `805.5`, and idle
`0.05108287`; checkpoint/model/replay/full-run digests are
`a9a55110fe2266b8...`, `21b665232664f79e...`, `9b67d5d468f86a55...`, and
`614c071b7f3003b0...`. Replica B reproduces checkpoint/model/replay/teacher/
canonical-frontier/full-run evidence exactly, and direct lineage passes with
digest `fd69503ae40e977b...`. Reusable preflight is ineligible: candidate wins
9/10 and strongly passes matched greedy, but permanent-greedy announcement,
idle, and recovery intervals remain uncertain; idle is `+0.01323943` with 95%
CI `[-0.00258843,+0.03051348]`. Reject V37 and isolate one causal V38 coordinate
from reusable per-seat/accepted-task evidence only.
After rejection, a delegated review improperly read dev-v33 and held-out-v4
manifests. ADR-0049 retires both unexecuted; no outcomes were observed. A
successor needs globally disjoint dev-v34 and held-out-v5 sets and a committed
umbrella marker before any membership read or baseline episode.

ADR-0050's V38 exact replicas completed from committed repository
`3effefed781b88c2e71354d784db58eb787ed7e6`, exact config
`d92bf9aa2050a5a4d62fc29566fb2514feec84eb421f62b6cac2e24b0969f2bf`, and
lock `8d865c8c710a61d7e37b8896b38166a1dcf121e40d17fbb1a47e948b4861bf6c`.
After 256 warmup and 2,048 training episodes/32 updates, update 20 was selected
at 9/10 wins, return `4.859680000000006`, core health `565.2`, and idle
`0.021071738935729764`. Checkpoint/model hashes are `3bc4a3a1cc9c2ef4...` and
`b9f592ffe58d1b86...`; both replay passes are bit-exact at
`272dfb7a5793c1b79...`, with action-state `5ba7991a0dd10f0d...`, canonical
full-run `356a2065c8c2001b...`, frontier `9955422e926e9557...`, and manifest
`e61516546eabb0cf...`. Replica B selected update 20 with the exact same metrics;
all 32 checkpoints are byte-identical and governed replay, action-state,
canonical full-run, warmup, frontier, and manifest evidence validates. Expected
path-bearing rehearsal/frontier/manifest raw differences do not affect their
canonical equality. Direct lineage passes
`selector_checkpoint_direct_lineage_v1` with exact commit, update, checkpoint,
model, and config; digest is `ada0bcca1d60b25b...` and artifact SHA-256 is
`9a608dc354ff06ba3...`.

ADR-0051 accepts the selected-only reusable-evaluation contract implemented by
guard commit `9bc96f91c7219ad9e9656f99b29f15331b78b399`: explicit-only
`--seed-set-file`, required declared split and pre-read held-out gate, no
implicit Gradle, runtime config/repository/JAR provenance, and fail-closed stale
promotion provenance. Legacy registry loading remains an explicit diagnostic
compatibility path and may not be used as a promotion fallback. Python passes
176/176. Exact-config reward adversaries remain 44/44 with report
`e44865297a31ab1625bf4a43116cf1ff712b96657043c200c0af629ddd4f59bf`.

Fresh permanent baselines bind config `d92bf9aa2050a5a4...`, repository
`9bc96f91c7219ad9e9656f99b29f15331b78b399`, and JAR `5d4fc89f...`;
records/aggregate hashes are `aaf28dd1...`/`4bbc3aa3...`. Permanent random is
4/10, idle `0.0153280914`, core `217.7`; permanent greedy is 8/10, idle
`0.0157205468`, core `707.2`. Candidate update 20/checkpoint `3bc4a3a1...`
reproduces on reusable dev-v1 at 9/10, return `4.85968`, core `565.2`, idle
`0.0210717389`. Matched random is 5/10 with idle `0.1635828272`; matched greedy
is 6/10 with idle `0.0888449994`. All observed win comparisons pass.

The frozen dual scorecards reject V38. Against permanent greedy,
announcements, duplicates, and idle are uncertain; recovery and abandonment
pass. Against matched greedy, announcements, idle, and abandonment pass, while
duplicates and recovery are uncertain. Preflight is false with records,
aggregate, and report hashes `99575abd...`, `aa3fa1fe...`, and `e6c9cf27...`.
ADR-0050 defines uncertainty as failure, so no confirmation set was opened.
Dev-v34 is retired unopened and unconsumed without any membership read.
Held-out-v5 remains sealed and unconsumed. M8.5 remains unmet.

Four subsequent reusable-only V39 diagnostics have byte-exact twins and full
candidate/matched/permanent parity, but none yields a narrow precommittable
coordinate. The WAIT communication artifact
`014085de7007e4d6227e6c5ae89ee1cd636b60f036c6b1db23a8acdd41908ad6`
records structured/suppressed counts candidate `17641/74`, matched `16161/69`,
and permanent `17252/74`. Candidate-minus-permanent announcements remain
uncertain before filtering (`-0.00307796`, CI
`[-0.01502905,0.00748813]`) and after filtering (`+0.00176772`, CI
`[-0.00574127,0.00877167]`), while matched stays pass.

The claim-loss artifact
`e3c726380516e9762566ab5b98dc3312758f52d2c943b979e49263cefbb9f794`
has 10/10 canonical parity and finds 19 learned-seat-0 losses: 18 supply, one
harvest, zero with partner schematic staged/live, 19/19 ordinary non-WAIT
alternatives, and zero extra boundary reconvergences. Seed 2005's harvest at
tick 2053/gap 695 could expose `BUILD_LINE` at 694 only through a trajectory
change that recreates V34 staging-disappearance risk. Reject it.

The recovery catalog
`727e62145895a5a9435a6c62372156a7887c5dd12d2d5d204d8d7b89bc5d298e`
finds 30 deaths and zero same-type valid choices at the exact boundary. Seeds
2004/2006 first permit `HARVEST` next tick, but require bias-to-tie above
`3.822402`/`3.973103` against defense, so this is not narrow. The
supply-collision artifact
`9b9905b208dceb95b9ddbf240a4050d63a85779b321eec7b6fc35bdfb1e26870`
records 18 collisions/seven bursts, alternate supply in 11/18, and 18 masking
changes (11 supply, six schematic, one harvest), with a `+1` alternate-supply
prior in only 6/18. This is the same 18/37 rejected redirect-rewrite and 18/48
rejected-mask coordinate and changes duplicates only, not recovery or idle.
Reject it.

ADR-0052 now precommits V39's one selector-input coordinate. Exact
same-boundary fixed-partner `task_id` intent raises only the matching learned
candidate's existing `duplication_risk` input to `1.0`. It does not mask,
redirect, force, reorder, suppress, or apply an action. The model shape, reward,
runtime, roots, teacher, budget, RNGs, and checkpoint ranking remain V38-exact.
The immutable config SHA-256 is
`54d76bb209ec31f24bc2711b208cb2995e6d538534ba0b99a150091596ccf924`
after ADR-0053's final-identity-only repair.

The exact feature and its fail-closed/disabled-feature parity, public
survival/staging, suites, smoke, determinism, golden/negative replay, and
exact-config reward gates all pass. Dev-v34 and held-out-v5 are retired;
held-out-v6 is frozen value-free and unconsumed. Do not inspect any membership
or run confirmation/final episodes. Keep ADR-0051 unchanged.

V39 replica A has now failed construction after all 32 updates: rank-best
update 25 is 8/10 with idle `0.01845563475648595`, checkpoint
`1af02875472f54a6...`, and frontier `181ed3e7069b429b...`. Replica B is
prohibited. Dev-v35 is retired unopened/unconsumed; held-out-v6 stays sealed.
ADR-0054 subsequently precommits one narrow V40 training coordinate. Exact
partner-intent teacher-label conflicts are excluded from warmup, rehearsal,
and PPO teacher imitation only; PPO policy/value, runtime, reward, model,
roots, budget, and RNGs remain V39-exact. The immutable config hashes to
`230759e7e02dcca9a6b7608f7784b20f85845c40da0f7a28dd1ec13641d0013a`.
A value-free umbrella reserves primary-only dev-v36 in `[4B,5B)`. The exact
filter implementation is committed at
`c9459c58f4`; the bound train-only diagnostic passes, with
report SHA `4fe2960225d659cb...`. Pinned Java, public/runtime/replay, and all
44 exact-config reward gates now pass; reward report SHA is
`9677e5caed4d891...`; gate evidence is committed at `a94cb9e534`. The
primary-only `[4B,5B)` dev-v36 freezer packet is prepared and the 211-test suite
passes. It was committed at `54db674e2e` before construction. Dev-v36 is now
frozen value-free and unconsumed; membership/receipt hashes are
`d4bfbcf88d99f4f...` / `fce63a49f80d165...`. Replica A is authorized from the
exact committed config/toolchain; 212 receipt-aware Python tests pass. Never
render or delegate membership, and never inspect held-out-v6 membership.

V40 replica A has now completed from committed repository `c288483436` and
passes construction. The frozen rank selects update 28 at 10/10 reusable wins,
return `7.77414`, core health `656.3`, and idle `0.008388499062201467`.
Checkpoint SHA is `9ff618797d8ae593...`; two fresh checkpoint replays are
bit-exact at `5af990a3ec8ff7fb...`, and action-state/full-run digests are
`4f0726c7dc8f127...` / `b6dd3c958762c082...`. Run Replica B next from the
identical committed config/toolchain and require exact governed hashes before
refreshing permanent baselines or running reusable scorecards. Dev-v36 and
held-out-v6 remain unopened/unconsumed; confirmation and final access are still
prohibited.

Replica B now reproduces Replica A exactly, including all 32 checkpoint files,
warmup, update-28 metrics, checkpoint/model, replay, action-state, and canonical
full-run evidence. The official comparator passes. Direct lineage validates at
digest `cfb0ec1b21fd49fb...`, artifact SHA `5fdc3bdabf24ee5e...`. Run fresh
selected-only permanent baselines on reusable dev-v1 next, followed by the
candidate/matched reusable preflight and both scorecards. Only a complete pass
may authorize the primary to open dev-v36. Held-out-v6 remains sealed.

Fresh selected-only baselines and reusable preflight now reject V40 before
confirmation. Candidate is 10/10 versus permanent random/greedy 4/10 and 8/10
and matched random/greedy 5/10 and 6/10; all observed win gates pass. The
permanent-greedy announcements and idle CIs and matched-greedy recovery CI cross
zero, so both frozen scorecards fail. Report SHA is `8453b0c4b75cd681...`.
Dev-v36 is retired unopened/unconsumed; held-out-v6 remains sealed/unconsumed.
Diagnose any V41 coordinate from reusable/train-only V40 evidence, precommit it,
and freeze a new disjoint value-free confirmation identity before model work.

ADR-0055 now precommits V41's single 50/50 adjacent-frontier midpoint. The
canonical diagnostic proves V40 updates 25, 26, and 28 are all 10/10 and all
fail the same permanent announcement/idle and matched recovery rows; updates 25
and 26 have complementary idle outliers. Config SHA is `c4705974f18512a...` and
the value-free dev-v37 umbrella SHA is `7ce8f5cf640978ef...`. The 44/44 reward
gate passes. Dev-v37 is frozen value-free and unopened in `[5B,6B)`;
membership/receipt hashes are `7874f5abaf230665...` /
`277264b80c6456f7...`. The constructor's reward-schema compatibility fix is
committed at `b081e39962`, with 224 Python tests passing. Pinned WSL Torch
2.12.1 constructions A/B are exact at checkpoint/model/lineage
`b6b5e98ddee56740...` / `93594bd64193740a...` /
`37c4b1e571fca96c...`. Fresh permanent random/greedy are 4/10 and 8/10; V41 is
10/10 and matched random/greedy are 5/10 and 6/10. Every win comparison passes,
but permanent-greedy idle and matched-greedy recovery remain uncertain. Report
SHA is `ca7b39c84a9f51d1...`; V41 is rejected before confirmation. Dev-v37 is
retired unopened/unconsumed and held-out-v6 remains sealed/unconsumed. Diagnose
any successor only from public/train evidence and precommit it before model or
seed construction.

Public/train-only diagnosis now closes learned WAIT-logit and danger-label
successors. The exact optimizer-free teacher diagnostic reproduces V40's 752
partner-intent conflicts and finds deterministic nonconflicting alternates for
682, including all 256 tick-zero conflicts and 174/189 successful-corpus
conflicts; 70 retain filter fallback. ADR-0056 precommits V42 to a pure,
adaptive-preference-preserving alternate teacher label across warmup, rehearsal,
and generic PPO teacher imitation. The original scripted action still drives the
trajectory and state. Runtime actions/masks, reward, features, model, optimizer,
roots, budget, RNGs, and engine pins remain V40-exact. Config/umbrella hashes are
`3fcb0c8800c638a3...` / `c1644d2dd6dde231...`. The implementation keeps
original/effective labels separate and covers all three generic teacher paths
plus deterministic telemetry. The live diagnostic reproduces 752 conflicts,
682 relabels, and 70 fallbacks; report/payload/action-state hashes are
`83f8dd6904e5356d...` / `e92436ffb3773b80...` /
`0e609742ba171c60...`. The complete 2026-07-23 boundary passes 243 Python tests,
Java, public policy (5/5, 10 proactive starts), both focused checks, smoke,
determinism, the 664-checkpoint/16,200-tick golden and negative replay, and all
44 exact-config reward adversaries (`272ac291ef143fa6...`). The primary-only
freezer/freeze commits are `3e328ce91e` / `949b73f987`; dev-v38 membership/
receipt hashes are `3f4b0d012cf87303...` / `fea431ae993d1072...`. The receipt
records zero membership reads and no values emitted; the full suite passes 257
tests. Exact pinned-toolchain replicas from training commit `12980ee2b9` both
select update 2 at 9/10 wins, return `4.73976`, core `568.8`, and idle
`0.03455784384563236`; all 32 checkpoint files and the canonical comparator are
exact. Checkpoint/model/replay/action-state/full-run hashes are
`65f8e3dc3a41bf89...` / `4363617f8535bc8b...` /
`d01d0dfe425d1b0d...` / `52751513f785c196...` /
`cb719361da11ab6c...`; direct lineage digest/artifact hashes are
`b1dbf1abc6a7dacd...` / `100945a4820b2039...`. Fresh permanent random/greedy
are 4/10 and 8/10; candidate is 9/10 and matched random/greedy are 5/10 and
6/10. Every win comparison passes, but permanent-greedy announcements and idle
and matched-greedy recovery remain uncertain, so both scorecards fail. Report
SHA is `01bf941060bc7e6f...`. V42 is rejected before confirmation; dev-v38 is
retired unopened/unconsumed and held-out-v6 remains sealed/unconsumed. Diagnose
any successor only from public/train/reusable evidence and precommit it before
model or seed construction. The off-contract build-line-prior diagnostic is
also rejected: it remains 9/10 and fails permanent announcements plus matched
recovery (`41e3b71b133f4c63...`). It has no promotion authority. No V43 is
currently authorized; require a new architecture hypothesis rather than
repeating accepted-ADR alternatives.

Preserve engine pins, fixed-step determinism, simulation-thread ownership,
structured-authoritative communication, and the four-JVM cap. Do not make
machine-global changes. The current-state section below governs remote
authorization.

## 2026-07-23 current M8 state (supersedes the stale queue above)

V43 through V46 were implemented and rejected before confirmation under their
frozen public gates. V47 then introduced exactly one sticky learned brain with
death-only lowest-living failover. Its exact replicas select update 25 at 10/10
public-dev wins and reusable-v2 reaches 125/160, but zero-margin idle and one
automatic abandonment remain uncertain. V48's per-seat history-cache retrain
reaches 127/160 but fails DEFER and idle; dev-v45 is retired
unopened/unconsumed.

ADR-0067 records an unauthorized held-out-v6 manifest read caused by a broad
metadata search. Only the set id was displayed and no episode ran, but v6 is
retired membership-exposed/unexecuted. The committed primary-only replacement
freezer created held-out-v7 value-free in `[17B,18B)`; receipt/membership hashes
are `8b78b27153d597fb...` / `f6d84b50d10ec6fc...`. Never open that manifest
unless a future committed one-way final gate is eligible.

ADR-0068 precommits the owner-authorized V49 prospective operational
non-inferiority protocol on fresh reusable-v3 while fixing V47's selected
checkpoint unchanged. Protocol SHA is `6711d6e43fab8f65...`. V49 wins 123/160
versus permanent random/greedy 61/82 and matched random/greedy 58/24. Every
win/control gate, matched scorecard, DEFER, one-brain, reward, lineage, and
reproducibility check passes, but permanent-greedy idle has mean
`+0.00567867`, CI `[-0.00022269,+0.01242934]`, exceeding the frozen `1/150`
margin. Result/preflight hashes are `9e2f31ee8053b296...` /
`4834b8c2832a0b6a...`. V49 is rejected; dev-v46 is unconstructed and
held-out-v7 remains sealed.

Do not continue with another transfer-local wrapper: public attribution shows
the residual without failover and on final seats 0/1, while seat 2 is
favorable. The next step requires an owner-level roadmap choice between a
materially new seat-context M8 hypothesis on fresh governance and explicitly
superseding the M9 entry gate. The user has authorized repository pushes to
`Smellybum1/Mindustry-Agent`; machine-global changes remain prohibited.
