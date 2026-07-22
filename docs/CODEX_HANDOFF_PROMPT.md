# Codex Handoff Prompt

Take over **mindustry-coop-agents** in `C:\Codex\Mindustry Agent`, branch
`coop-agent/v159.7`, after V38's exact twin replicas and direct-lineage
validation.

Read first, in order:

1. `AGENTS.md` in full; obey its project-wide no-subagent rule.
2. `docs/HANDOFF.md`, focusing on the V38 entry and next-five queue.
3. M8.5 and the M8 exit criteria in `docs/ROADMAP.md`.
4. ADR-0050.

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

Next, refresh permanent random and greedy plus matched random and greedy
baselines under the exact V38 runtime, then run reusable scorecard preflight.
Require both permanent-greedy and matched-greedy parity; uncertainty is failure.
Dev-v34 and held-out-v5 remain unconsumed. Do not inspect their membership and
do not run confirmation or final episodes. M8.5 remains unmet.

Preserve engine pins, fixed-step determinism, simulation-thread ownership,
structured-authoritative communication, and the four-JVM cap. Do not push or
make machine-global changes.
