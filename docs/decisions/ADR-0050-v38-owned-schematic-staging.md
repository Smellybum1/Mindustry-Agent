# ADR-0050: V38 learned-seat staging beside partner-owned schematics

**Status:** Accepted

## Context

V37 reproduces exactly at 9/10 reusable wins and passes every matched-greedy
scorecard, but its permanent-greedy announcement, idle, and recovery intervals
remain uncertain. The frozen gate therefore rejects V37. ADR-0049 also retires
the membership-exposed, unexecuted dev-v33 and held-out-v4 sets and requires a
committed umbrella reservation before replacement membership is created or
read.

Two reusable-only collision interventions are not viable. Redirecting
conflicting selections falls to 6/10 and increases total idle by 48.07%, mostly
by moving the problem to scripted seat 2. Masking learned selections that match
same-boundary partner intent falls to 7/10; it saves only 39 learned-seat idle
ticks and flips seeds 2005 and 2010 from wins to losses. Collision rerouting
changes task allocation without guaranteeing productive replacement work.

A behavior-preserving observer then replays all ten V37 reusable episodes with
exact action, tick, state-hash, and outcome parity over 1,128 boundaries. All
4,658 learned-seat idle ticks overlap the structured
`expert_fortification_v1` schematic. Of those, 1,607 ticks occur with no
server-valid non-`WAIT` action and no exposed proactive staging candidate.
Six low-urgency harvest claim losses account for another 3,011 ticks: learned
seat 0 and scripted seat 2 select the same harvest task while scripted seat 1
continues owning/running fortification, then the learned seat remains idle for
478--552 ticks. In total, 4,611/4,658 learned idle ticks occur while the
fortification task is `RUNNING` and owned by seat 1. No learned-idle interval
has an exposed proactive staging action.

The existing V32 runtime already defines the desired productive fallback: a
learned-seat-only, nonexclusive `DEFEND_REGION` staging candidate during the
quiet interval before the ordinary defend-lead boundary. Its current catalog
condition requires the raw ordinary-task list to be empty. That condition does
not account for ordinary work already owned by a partner or likely to be lost
atomically to a fixed partner.

## Decision

1. V38 keeps the complete V37 construction and changes one candidate-catalog
   coordinate. While the episode is quiet and before the ordinary defend-lead
   boundary, expose the existing proactive staging candidate to learned seat 0
   whenever another seat owns a live `BUILD_SCHEMATIC`, even if ordinary raw
   candidates are also present.
2. The added candidate retains the existing staging contract exactly:
   `DEFEND_REGION`, nonexclusive, priority `1.0`, target equal to the governed
   defend region, and deterministic duration ending at the existing defend-lead
   boundary. It is not exposed to scripted seats 1 or 2.
3. V38 does not force, redirect, suppress, or rewrite any action. The candidate
   enters the ordinary bounded catalog and authoritative server mask. The
   learned model or teacher selects it through the existing structured action
   surface, and accepted selection follows the existing board/skill lifecycle.
4. V37's fixed seat-2 harvest opening, fixed seat-1 claim-loss wake, task
   catalog apart from this additional staging eligibility, reward, teacher
   coefficients/corpora, model, optimizer, training budget, RNGs, reusable
   roots, checkpoint selection, and scorecard gates remain exact.
5. Permanent baselines are refreshed under the V38 runtime. Matched controls,
   teacher/PPO collection, checkpoint replay, reusable evaluation,
   confirmation, and final evaluation all observe the same V38 catalog.
6. Before replica A, the committed implementation must pass focused
   engine-free and live checks proving positive learned-seat exposure beside a
   partner-owned schematic, negative partner-seat exposure, no exposure after
   fortification/at defend lead, authoritative mask validity, and unchanged
   lifecycle semantics. It must also pass the complete public candidate gate,
   pinned Java/Python suites, smoke, determinism, negative replay, and all 44
   exact-config reward adversaries.
7. Replica A must reach at least 9/10 reusable construction wins with mean idle
   below `0.25` before replica B. Passing twins must reproduce checkpoint,
   model state, frontier, replay, teacher evidence, canonical full-run digest,
   and direct lineage before reusable scorecards may run.
8. Reusable preflight must pass observed win-rate comparisons and both frozen
   permanent-greedy and matched-greedy scorecards. Uncertainty is failure. No
   replacement confirmation manifest may be consumed before that result.
9. The tracked V38 umbrella reservation is committed before replacement
   membership creation. Primary-agent-only construction must then freeze 160
   globally disjoint roots each for dev-v34 and held-out-v5 without rendering
   membership into agent output. Both documents must be committed before V38
   runtime implementation or model work begins.
10. Primary-only construction may internally read membership for disjointness
    and hash verification provided no value is rendered into agent output.
    After the freeze documents are committed, a committed one-way consumer must
    atomically create the set-specific umbrella attempt before the first
    semantic membership load for episode scheduling or any baseline episode. A
    started, aborted, failed, exposed, or completed attempt consumes the set.
    Confirmation requires exact replicas and reusable parity; final evaluation
    additionally requires a passing confirmation.

## Alternatives

- Broad collision redirect and same-boundary partner-intent masking are rejected
  by their 6/10 and 7/10 reusable survival results.
- Keeping a collision mask only when a non-`WAIT` replacement exists is rejected
  as the primary coordinate because later productive-looking supply reroutes
  still precede both partner-mask losses and do not address the 1,607 ticks with
  no selectable ordinary work.
- Waking or retrying learned-seat claim loss without adding productive work is
  rejected by the earlier V34/V36 evidence: scheduling changes alone either
  remove required public staging or preserve the idle interval.
- Implicitly converting claim loss into help is rejected because the accepted
  helper contract remains explicit request/offer/accept and has no
  `ASSIST_BUILD` skill.
- Exposing staging to every seat is rejected by V33's 4/5 public survival
  result. V38 remains learned-seat-only.

## Consequences

- V38 changes the runtime catalog and must retrain from scratch. V37 checkpoints
  remain diagnostic history only.
- The coordinate gives the learned selector a productive, structured,
  nonexclusive choice exactly where reusable traces show fortification-related
  idle, without embedding fixed-partner intent in the model mask or overwriting
  its selected action.
- Candidate count/order and golden hashes may change at affected boundaries;
  deterministic replay evidence must be regenerated only after the complete
  implementation gates identify the expected semantic delta.
- Fresh permanent baselines are required because learned seat 0 in those
  policies also observes the V38 runtime catalog.
- Dev-v33 and held-out-v4 remain membership-exposed, unexecuted, and retired.
  Their successors are not authorized for consumption merely because their
  identities are reserved.

The behavior-preserving actionability artifact is
`runs/m8-selector-v38-v37-actionability.json`, SHA-256
`0500a74377b740556e3012635491318acbde3939c7f179bd24e79aa46ebf2099`.
It binds V37 config `78bb87f459afc926f68068aa7f6f5881b3e1fa9f4d7026dca2fb2bb216acbb32`,
checkpoint `a9a55110fe2266b8ba0c34053e79eb99ef14a06c9b12727d4810cc7513df8297`,
direct-lineage digest `fd69503ae40e977bd695b9a51a129e8769ba1cb623252777e4e4a213a29ceea0`,
and public reusable set
`1ad81503238dcffa5f8ff28811e06a211523f67c02d312afaaf4dcc8facbc71b`.
The immutable V38 config SHA-256 is
`d92bf9aa2050a5a4d62fc29566fb2514feec84eb421f62b6cac2e24b0969f2bf`.
The pre-membership umbrella reservation SHA-256 is
`a2e2389925797a5f5a8c93224561f68f36fd443afbebdc07f888aaf6bef6f27a`.
No V38 runtime implementation, model work, replacement membership document,
confirmation baseline, or final evidence preceded this decision.

The umbrella was committed in `de597c8462` before membership construction. The
primary-only freezer committed at `a7504a4781` then generated both documents,
verified global disjointness internally, and emitted no seed value. Dev-v34 and
held-out-v5 contain 160 unique roots each and hash to
`bef6bb17c7759530dc216961733839808dbff228bb96a09232dced89a7ca5ac7` and
`1118ef59b0953aacd86176737777013bb2c6498e128f28bcbb7850e6ad586910`.
The value-free freeze record hashes to
`7282a3cd405f2d6b00dd3942fb8da2b2f62eb3a8f567dc067edc07756787018e`.
Both sets remain unconsumed; no baseline episode or policy evidence has used
either membership.

The V38 runtime implementation is committed at `8b3f9cc749`. Its focused live
owned-schematic probe passes on public seed 12345: seat 1 is running
`BUILD_SCHEMATIC`; learned seat 0 receives one valid `DEFEND_REGION` staging
candidate alongside ordinary `BUILD_LINE`; scripted seats receive no staging
candidate; and no synthetic claim, helper, or event is created. Focused
`CandidateGenerator` tests and Gradle `agent-core:test rl-server:test
agent-plugin:classes` pass, as do all 166 Python tests. The public
candidate-policy gate wins 5/5 with 10 proactive staging starts, and smoke
passes all 9 checks.

The remaining pretraining gates are green from that implementation checkpoint.
Cross-process determinism ends at `20a97f36407167597981e77c`, reset purity at
`a2cf4a73ee901c844f30f486`, and alternate-seed sensitivity at
`495ba05fa71697bdc8ff2951`. Golden replay covers 664 checkpoints, 16,200 ticks,
and two episodes; the negative control detects a one-line `MINE` mutation. All
44 exact-config reward adversaries pass for config SHA-256
`d92bf9aa2050a5a4d62fc29566fb2514feec84eb421f62b6cac2e24b0969f2bf`; the
temporary, uncommitted report hashes to
`e44865297a31ab1625bf4a43116cf1ff712b96657043c200c0af629ddd4f59bf`.
At that implementation checkpoint, dev-v34 and held-out-v5 remained unconsumed,
and no baseline episode or model work had begun. Replica B remained prohibited
unless replica A reached at least 9/10 construction wins with mean idle below
`0.25`.

V38 replica A subsequently completed from committed repository
`3effefed781b88c2e71354d784db58eb787ed7e6` with the exact config above and
lock SHA-256
`8d865c8c710a61d7e37b8896b38166a1dcf121e40d17fbb1a47e948b4861bf6c`.
It completed 256 warmup episodes, 2,048 training episodes, and all 32 updates.
The governed selector chose update 20 at 9/10 construction wins, mean return
`4.859680000000006`, mean core health `565.2`, and mean idle
`0.021071738935729764`. The checkpoint and model-state SHA-256 digests are
`3bc4a3a1cc9c2ef4450e20c689c3909a8bf9ae8ba35b194e8710df1acf737b5e` and
`b9f592ffe58d1b866f200cd3544a2ecfd48f6d662f517aece3dffa745fa66540`.
Both replay passes are bit-exact at
`272dfb7a5793c1b79be95ce9b7e2407c3752cb6ee183cf9440dbe388ee4553af`;
the action-state digest is
`5ba7991a0dd10f0d857c5fcbf75ccbbb573eb7a7c59b975967c3432463f3c68c`,
the canonical full-run digest is
`356a2065c8c2001ba6e9b2b480949e0c4ff3fdfd39b88ac8747c49e2838f57a2`,
the frontier SHA-256 is
`9955422e926e955700370f6dcf792c1c1054e6501e8b5b46afb151911ea78c7b`,
and the manifest SHA-256 is
`e61516546eabb0cf35d53f699c1e24fa20f214f9a534678cf69ff5361ecd63ad`.
Replica A therefore passes the precommitted gate exactly: wins are at the
`>=9/10` floor and idle is below `0.25`. Exact replica B is now authorized from
the same repository commit, config, and toolchain in an independent output.
Dev-v34 and held-out-v5 remain unconsumed; no scorecard, confirmation, or final
episode has run. M8.5 remains unmet.

V38 replica B then ran independently from the exact training/repository commit
`3effefed781b88c2e71354d784db58eb787ed7e6`, config
`d92bf9aa2050a5a4d62fc29566fb2514feec84eb421f62b6cac2e24b0969f2bf`, and lock
`8d865c8c710a61d7e37b8896b38166a1dcf121e40d17fbb1a47e948b4861bf6c`.
It selected update 20 with the exact same 9/10 wins, return
`4.859680000000006`, core health `565.2`, and idle
`0.021071738935729764`. All 32 checkpoint files are byte-identical, including
selected checkpoint
`3bc4a3a1cc9c2ef4450e20c689c3909a8bf9ae8ba35b194e8710df1acf737b5e`,
update-32 checkpoint
`c76d9638be562eeb69e994d80b06bf6d0063dd7b5b364ba5efb3d10da6050061`,
and model state
`b9f592ffe58d1b866f200cd3544a2ecfd48f6d662f517aece3dffa745fa66540`.
Replay is bit-exact at
`272dfb7a5793c1b79be95ce9b7e2407c3752cb6ee183cf9440dbe388ee4553af`;
the replay JSONL raw SHA-256 is
`151841cfdf4e8d23ee48943a6ba8530ad4ea8034c90c5afae084c6a91d3e6700`,
action-state is
`5ba7991a0dd10f0d857c5fcbf75ccbbb573eb7a7c59b975967c3432463f3c68c`,
canonical full-run is
`356a2065c8c2001ba6e9b2b480949e0c4ff3fdfd39b88ac8747c49e2838f57a2`,
and training-trace raw SHA-256 is
`dec25b683499f748e0bef3bba3746e3688c14b99f954d8f5e085b12b30543771`.
Warmup is raw-hash exact at
`d1dab1c2d438ba95800d43b4caea217509e7a40aa842e4e750b4b75ad026088a`.
Path-bearing rehearsal, frontier, and manifest raw hashes differ as expected;
their governed canonical forms match at rehearsal
`bc1c5a88a4601a0a2b7e4bf1f549745ed24ead097da04a8282ffd1383207734c`,
frontier `9f369a04161be4b74d041f315c3f5b7dce20ecfbbb779c82ea8d9d4ac6c40fff`,
and manifests
`451f0c5bc967ba51349698f01d566ce189b9413fc41839df4e26588e86e923a0`.

Direct-lineage validation passes under schema
`selector_checkpoint_direct_lineage_v1`: selected update 20 and the
training/repository commit, checkpoint, model state, and config all match
exactly. The lineage digest is
`ada0bcca1d60b25bc9bcb1e5e0d2a94d890c456018b7459821bbfd76317fed40`,
and the lineage artifact SHA-256 is
`9a608dc354ff06ba30a922a14750361d1a877146334cd0bfd74e74b5381a3a1b`.
The next authorized work is to refresh permanent random and greedy plus matched
baselines under the V38 runtime, then run reusable scorecard preflight. Dev-v34
and held-out-v5 remain unconsumed; confirmation and final evaluation remain
prohibited. M8.5 remains unmet.
