# Codex Handoff Prompt

Take over **mindustry-coop-agents** in `C:\Codex\Mindustry Agent`, branch
`coop-agent/v159.7`, after the V30 construction rejection.

Read first, in order:

1. `AGENTS.md` in full; obey its project-wide no-subagent rule.
2. `docs/HANDOFF.md`, focusing on the V24–V30 entries and next-five queue.
3. M8.5 and the M8 exit criteria in `docs/ROADMAP.md`.
4. ADR-0035 through ADR-0041.

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
sealed. Precommit the next hypothesis from reusable train/dev evidence before
any new model work; never open held-out-v4 without every governed prerequisite.

Preserve engine pins, fixed-step determinism, simulation-thread ownership,
structured-authoritative communication, and the four-JVM cap. Do not push or
make machine-global changes.
