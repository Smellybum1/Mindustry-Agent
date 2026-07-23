# ADR-0077: Precommit the M9 v3 policy-mode diagnostic

**Status:** Accepted

## Context

ADR-0076 rejects `m9-ippo-v3-diverse2048` after every deterministic public-dev
checkpoint lost 40/40 episodes. That same immutable run won 585/2,048
stochastic train episodes. V1 showed a smaller version of the same split:
598 stochastic train wins but a best deterministic dev result of 16/40.

This evidence does not establish whether categorical action sampling transfers
survival to public dev roots or whether train wins depend on the train
distribution and trajectory history. Changing another optimizer or data recipe
without answering that bounded question would mix hypotheses. The diagnostic
must be frozen before implementation or execution and cannot repair the
rejected candidate.

## Decision

1. Freeze the protocol at
   `configs/evaluation/m9-ippo-v3-policy-mode-diagnostic-protocol.json`,
   SHA-256
   `89fecf69b76cd0fb79ed2fbafb97dc5b16446ee21648ceeabd4ddc892322b0c7`.
2. Use only immutable v3 update 29. Its local checkpoint file SHA is
   `22cf7cb1ed08f9a1c5544ce5169f200d3f7ea9ddc71b7f487e80f7285eea791b`,
   canonical checkpoint-content SHA is
   `849d9f97f9ed0b9c23a3b20d23471fbdb423062f81b342d580a522398de4b7e2`,
   and model-state SHA is
   `87d85c4c78ae4c2d40e6c7f4bc67154bdd7ad94aa582baf4450048bd7826186e`.
   Update 29 is fixed because it had the highest deterministic public-dev
   return in the immutable rejected run, not because it passed selection.
3. Use the existing 40 public M9 dev roots only. Rerun one deterministic
   argmax stream and four categorical streams with fixed action seeds 9602,
   19602, 29602, and 39602. Each stream visits every root exactly once and
   resets private hidden state at the episode boundary.
4. Use temperature 1.0 and the existing masked softmax plus
   `torch.multinomial`. Do not change features, masks, model parameters,
   action vocabulary, scenario, rewards, or environment behavior.
5. Run the complete 200-episode diagnostic in two fresh JVMs. Reports must be
   byte-identical after excluding only process-local paths if any; model and
   checkpoint digests must remain unchanged.
6. Classify a stochastic survival signal only if the four categorical streams
   total at least 32 wins out of 160 episodes (20%). This is diagnostic, not a
   construction or promotion threshold. Report every stream, return, core
   health, idle fraction, trace digest, and aggregate.
7. V3 remains rejected regardless of the result. The deterministic 30/40 plus
   idle `<0.25` construction gate remains authoritative. The diagnostic cannot
   select or promote update 29, authorize replica B, start MAPPO, or access
   confirmation/held-out data.
8. If the signal passes, a separately precommitted v4 may isolate one
   deterministic-policy consolidation mechanism. If it fails, a v4 must
   instead address representation/supervision or another separately justified
   mechanism. No v4 trajectory is authorized by this ADR.

## Alternatives

- Treating 585 stochastic train wins as proof of a policy-mode mismatch is
  rejected because train roots and within-training model states differ from
  public dev evaluation.
- Testing temperatures, top-k rules, or choosing sampling seeds after results
  is rejected as post-hoc search.
- Using multiple checkpoints is rejected because it adds a checkpoint-choice
  dimension to a one-question diagnostic.
- Changing official construction evaluation to stochastic sampling is
  rejected. A deployable coordination policy must remain reproducible.
- Opening confirmation or held-out data is rejected; public evidence is
  sufficient for this diagnostic.

## Consequences

- The diagnostic is bounded to 400 public episodes across two fresh JVMs and
  performs no optimizer step.
- Its implementation must validate every source hash and fail closed on any
  model mutation, root drift, mode drift, or restricted-data authority.
- No diagnostic episode exists at this precommit.
