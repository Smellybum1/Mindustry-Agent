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
