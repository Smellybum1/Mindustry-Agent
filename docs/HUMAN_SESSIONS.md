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
the abrupt-exit fallback.

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

Create the objective M10.4 scorecard without asserting any human rating:

```bash
PYTHONPATH=python/src python -m mindustry_agents.tools.human_scorecard \
  --session runs/human-session-001.jsonl \
  --output runs/human-session-001.scorecard.json
```

Both capture and scorecard output are create-new and refuse overwrite.

## Capture schema v1

Every line has `capture_schema_version`, `record_type`, and simulation `tick`.
Records are ordered and have these types:

- `session_start`: engine tag/commit, Arc hash, protocol version, scenario
  identity, policy identity, and explicit not-applicable demo values for the
  Python training lockfile/config fields;
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

Human judgments live in a separate local JSON file and are never inferred. A
rating file must match this exact schema and capture digest:

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
exit criterion.
