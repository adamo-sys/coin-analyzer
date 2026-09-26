# Recognition30 Experiment 7 — visual-reference retrieval design

## Status

`DESIGN_ONLY_NOT_EXECUTION_AUTHORITY`

Experiment 6 closed with no lexical-retrieval improvement: control and treatment
both retrieved the correct candidate for 11/30 cases at K=10. Experiment 7 tests
a distinct hypothesis: whether image-embedding retrieval against a legitimate
reference gallery can improve correct-candidate recall before the existing
verifier.

This document authorizes neither downloads nor execution. Model/artifact,
license, reference-gallery provenance, leakage controls, and local resource
budgets must be frozen before an E7 run.

## Hypothesis

A visual embedding retriever operating on coin images will retrieve the correct
Recognition30 candidate more often than the current deterministic lexical
retriever when both are evaluated against the same candidate identities.

This is a retrieval experiment, not a recognition-accuracy experiment.

## Frozen query set

- Dataset: `recognition30_v1`.
- Dataset fingerprint:
  `5ce59a80db35b58950358eb3441cdd78b350f5bcecf0326678202366ab737a20`.
- Exactly 30 specimens.
- Use the existing benchmark query images without mutation.
- Do not tune on Recognition30 outcomes.
- No new VLM/provider observations are required.

## Reference-gallery requirement

E7 must use reference images independent of the Recognition30 query photographs.

For every gallery item preserve:

- candidate identity;
- source and provenance;
- permitted processing/use;
- image digest;
- obverse/reverse/unknown role where known;
- whether the image is derived from, duplicates, or depicts the same physical
  specimen as a query image.

Same-image, derived-image, and known same-specimen leakage is prohibited. If an
independent reference gallery cannot be established for all 30 candidate
identities, stop and report the coverage gap rather than manufacture a result.

## Arms

### Control

The E6/current deterministic lexical retriever result is the fixed control:

- correct candidate @10: 11/30;
- Recall@10: 36.7%.

Do not rerun paid observation calls to recreate it.

### Treatment

A frozen image-embedding model produces embeddings for query and reference
images. Candidate ranking must be deterministic from declared image-similarity
scores and a frozen two-sided aggregation rule.

The first E7 implementation should be backend-neutral. “Coin-CLIP” is the
working architectural label, not permission to select a model after seeing
Recognition30 results.

## Preregistered metrics

Primary:

- correct-candidate Recall@10 across all 30 specimens.

Secondary:

- Recall@1;
- Recall@3;
- per-case control/treatment win, loss, or tie;
- gallery coverage;
- retrieval failures;
- cold model/index load time;
- warm query latency median and p95;
- peak process RAM;
- embedding/index storage.

Report exact counts as well as percentages.

## Decision rule

E7 supports further visual-retrieval work only if the frozen treatment improves
correct-candidate Recall@10 over the fixed 11/30 control without leakage,
post-hoc gallery/model selection, or unacceptable resource failures.

A positive bounded result does not authorize production adoption. A tie or loss
closes the tested configuration without searching Recognition30 for a favorable
model/configuration.

## Safety and architecture boundaries

- No production retriever replacement.
- No verifier changes.
- No identity-gate changes.
- No collection mutation or evidence promotion.
- No cloud/provider calls unless separately authorized.
- No benchmark image modification.
- No model training or fine-tuning on Recognition30.
- No vector database is required for this 30-case experiment.
- No threshold tuning against Recognition30 labels.
- Keep private query/reference image bytes and generated embeddings outside Git.

The existing conservative verifier remains downstream and is deliberately not
part of the primary E7 endpoint.

## Required preflight before implementation/execution

1. Select one exact candidate embedding artifact/revision.
2. Verify upstream source, license, integrity, modality/task suitability, and safe
   loading requirements.
3. Establish the independent 30-identity reference gallery and leakage audit.
4. Freeze image preprocessing, side aggregation, similarity metric, tie-breaking,
   K values, hardware/thread settings, and resource budgets.
5. Record hashes for the model/configuration and reference-gallery manifest.
6. Implement an offline evaluator with synthetic/unit fixtures before touching
   private benchmark images.
7. Run a zero-inference preflight that validates identities, gallery coverage,
   hashes, and leakage declarations.

Only after those items are recorded should a bounded E7 execution be authorized.
