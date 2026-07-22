# Human demo session capture

Milestone 10.3 adds local, explicit-opt-in JSONL capture to the public-candidate
demo. Capture is disabled by default and does not change training observations,
actions, hashes, protocol fields, or demo policy decisions.

## Run a captured private session

Create a new path under the existing `runs/` directory and start join mode from
Git Bash:

```bash
DEMO_CAPTURE_PATH="$PWD/runs/human-session-001.jsonl" \
DEMO_JOIN=1 bash scripts/demo-server.sh
```

The writer uses `CREATE_NEW`: it refuses to overwrite an existing file and
requires the parent directory to exist. Use `/agents stop` before shutting down
the server for the normal explicit session end. A process-shutdown hook is only
the abrupt-exit fallback. After a normal server exit, the launcher validates
the capture, replays its structured controls, prints partner-style statistics,
and creates `runs/human-session-001.scorecard.unrated.json`. Both artifact
targets are checked before the server opens, so an existing path fails before
play begins. Set `DEMO_SCORECARD_PATH` to choose a different create-new
scorecard path.

The deterministic, no-port acceptance gate is:

```bash
bash scripts/human-session-check.sh
```

It runs the complete human-control/presence probe, validates the JSONL pins and
digest, replays every applied control event in simulation-tick order, derives
partner-style statistics, and validates all five scripted partner profiles.

An existing completed capture can be checked without third-party dependencies:

```bash
PYTHONPATH=python/src python -m mindustry_agents.tools.human_session \
  --session runs/human-session-001.jsonl \
  --population configs/partners/human-scripted-v1.json
```

To create the objective M10.4 scorecard manually for an older capture without
asserting any human rating:

```bash
PYTHONPATH=python/src python -m mindustry_agents.tools.human_scorecard \
  --session runs/human-session-001.jsonl \
  --output runs/human-session-001.scorecard.unrated.json
```

Both capture and scorecard output are create-new and refuse overwrite.

## Capture schemas

Every line has `capture_schema_version`, `record_type`, and simulation `tick`.
Records are ordered and have these types:

- `session_start`: engine tag/commit, Arc hash, protocol version, scenario and
  policy identity, and explicit not-applicable demo values for the Python
  training lockfile/config fields. Current schema v3 also records the project
  commit plus canonical agent-plugin and server runtime-content SHA-256 values;
- `trajectory`: the existing public-candidate team observations, candidate
  masks, typed actions, and action results at one decision boundary;
- `control`: queued tick, applied tick, sequence, hashed/canonical author ID,
  canonical structured command, accepted result/reason, revision, goal, and
  agent;
- `coordination`: the authoritative task event plus `rendered`, `suppressed`,
  `empty`, or `not_requested` announcement status;
- `human_presence`: deterministic additions/removals of plan or recent-build
  footprints and their rules-scaled resource floor;
- `session_end`: close reason, record count, and SHA-256 over every preceding
  UTF-8 JSONL line.

Chat prose is not recorded as authority. Player display names, raw UUIDs, chat
messages, secrets, and wall-clock timestamps are not captured. Player author
IDs use the existing truncated SHA-256 identity; server/probe authors use their
canonical local IDs.

The loader remains backward-compatible with schema-v1/v2 captures. V1 lacks
project and executable provenance. V2 recorded whole-JAR byte hashes, but the
upstream server archive contains volatile generated packaging metadata, so
fresh byte-identical builds cannot be expected. Both are exploratory only.
Schema v3 hashes sorted entry names and decompressed bytes while normalizing
only `version.properties` comments and `buildDate`; stable build/version fields,
all classes, and every other resource remain authoritative. Only v3 sessions
can contribute to a provenance-complete serious-session floor.

The committed schema-v3 reference at project commit
`c19e652324d356112fcbc84bbb2b89d7e88eda8c` reproduces across two fresh JVMs:

- session content SHA-256:
  `7a2c68e638e9fff3bbce4de60fe7ad14ceb5b1d37a0b8403a0605788289c7d99`;
- control schedule SHA-256:
  `d30d529355b07ce18c45d074f58a11d4c444b3dff0a2ec70b89bfeb8cbbef6ce`;
- agent-plugin runtime-content SHA-256:
  `faca436f81b865bd2ed7ab58528bc04bda6c69467af064bdcb22ac7232da41d0`;
- server runtime-content SHA-256:
  `e02c4208749ee2ed944c013743def761b0d0f75a06c864fd834ce3cd9a130902`.

## Statistics, replay, and staged partner models

`mindustry_agents.telemetry.human_session` validates complete captures and
derives command pace, goal-role preference, cancellations/releases, presence
changes, announcement outcomes, and human-yield counts. Its control replay
reconstructs active goals, assignments, autonomy, quiet state, revision, and a
canonical schedule digest from applied structured events only.

`configs/partners/human-scripted-v1.json` and `scripted_partner_decision()` define
the deterministic fast-expert, slow-beginner, cautious, plan-changer, and
help-requester models. They are **staged, not activated**: M9 training remains
closed until the M8 promotion gate authorizes it. No held-out or confirmation
membership is read by capture, validation, statistics, or profile execution.

## Human teammate scorecard v1

The objective scorecard uses only captured structure:

- human intervention rate is the fraction of trajectory-boundary ticks with at
  least one accepted human control;
- plan conflicts are `yield_to_human` coordination events;
- yield latency pairs human-presence additions FIFO with later conflict events;
- goal compliance counts completed human goals over goals that were not
  cancelled before completion (unresolved uncancelled goals remain eligible);
- time-to-help pairs `REQUEST_HELP` intent by task ID with `help_fulfilled`;
- rendered and quiet-suppressed announcement counts come from recorded render
  status, not reconstructed chat text.

Human judgments live in a separate local JSON file and are never inferred.
Create that file from explicit answers after the session; the tool validates
the completed capture, binds its digest, uses create-new output, and accepts no
free-text or identity field:

```bash
PYTHONPATH=python/src python -m mindustry_agents.tools.human_rating \
  --session runs/human-session-001.jsonl \
  --output runs/human-session-001.rating.json \
  --announcement-usefulness-rating 4 \
  --keep-this-team yes \
  --comparative-rating-vs-scripted 1 \
  --serious-session yes
```

The resulting rating file has this exact schema and capture digest:

```json
{
  "schema": "human_session_rating_v1",
  "version": 1,
  "session_content_sha256": "<64 lowercase hex characters from session_end>",
  "announcement_usefulness_rating": 4,
  "keep_this_team": true,
  "comparative_rating_vs_scripted": 1,
  "serious_session": true
}
```

Announcement usefulness is an integer from 1 (not useful) to 5 (very useful).
Comparison is -2 (much worse than the scripted team), -1, 0 (same), 1, or 2
(much better). `serious_session` distinguishes north-star evidence from a smoke
test. Bind and write the rated scorecard with:

```bash
PYTHONPATH=python/src python -m mindustry_agents.tools.human_scorecard \
  --session runs/human-session-001.jsonl \
  --rating runs/human-session-001.rating.json \
  --output runs/human-session-001.scorecard.json
```

The rating file contains no free-text field, identity, or secret. Real ratings
must be entered by the human after play; the probe deliberately emits
`rating_status=not_provided` and cannot satisfy the project-owner preference
exit criterion. Keep the automatically generated `.scorecard.unrated.json` as
the objective record and write the later digest-bound rated result to the
separate `.scorecard.json` path shown above.

## Aggregate serious-session evidence

Aggregate only complete capture/rating pairs; a scorecard alone does not carry
enough runtime, scenario, and policy identity to establish comparability:

```bash
PYTHONPATH=python/src python -m mindustry_agents.tools.human_evidence \
  --entry runs/human-session-001.jsonl runs/human-session-001.rating.json \
  --entry runs/human-session-002.jsonl runs/human-session-002.rating.json \
  --entry runs/human-session-003.jsonl runs/human-session-003.rating.json \
  --output runs/human-evidence-001.json
```

The current evidence-report schema v2 rejects duplicate capture digests and
groups sessions by matching engine, Arc, protocol, scenario, and policy pins.
Only explicit
`serious_session=true` ratings count toward the minimum-three-session floor.
That floor is readiness evidence, not acceptance: rating v1 does not measure a
paired agents-present versus agents-absent preference, and no learned/scripted
target thresholds are precommitted yet. Legacy v1/v2 groups remain exploratory;
v3 groups additionally require exact project-commit and canonical runtime-
content hashes. The report therefore states `acceptance_status=not_evaluated` even when a v3
group meets the collection floor. See ADR-0058.
