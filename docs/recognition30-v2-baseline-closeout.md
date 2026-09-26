# Recognition30 v2 grounded baseline closeout

## Status

`COMPLETE — CANONICAL V2 BASELINE`

This closeout records the first grounded baseline run against the frozen
`recognition30_v2` dataset. It supersedes the v1 grounded baseline for future
Recognition30 experiment comparisons. Historical v1 artifacts remain historical
evidence and must not be rewritten.

## Frozen dataset identity

- Dataset: `recognition30_v2`
- Cases: 30
- Query images: 60
- Dataset fingerprint scheme: `recognition30-dataset-fingerprint-v1`
- Canonical fingerprint:
  `ad1525098b5b1bfd8f6385518ec641962b31c197d544de43421c7902facc965d`
- The known CA-R30-006 ground-truth defect was repaired before this run.
- No claim is made that the other 29 cases received a new independent visual
  re-verification.

## Run configuration

- Runner schema: `coin-analyzer-recognition30-grounded-v1`
- Dataset version reported by runner: `recognition30_v2`
- Provider: `openai-responses-grounded-observation`
- Model: `gpt-5.6-terra`
- Reasoning effort: `low`
- Retrieval limit: 10
- Provider timeout: 120 seconds
- Adaptive routing: none
- Grounded runner retrieval mode remains the benchmark oracle catalogue; this
  baseline measures the downstream evidence/retrieval/verification pipeline
  under that benchmark contract and is not a production retrieval benchmark.

## Headline result

- Cases: 30
- Correct: 1
- Identified: 1
- Abstained: 29
- Unsafe wrong identifications: 0
- Full identity accuracy: 1/30 = 3.3%
- Coverage: 1/30 = 3.3%
- Selective accuracy: 1/1 = 100%
- Unsafe wrong-identification rate: 0/30 = 0%

The only identified case was CA-R30-011, with reason
`unique_verified_candidate_with_two_side_support`.

## Retrieval endpoint

The correct benchmark candidate was present in the retrieved candidate set for
11/30 cases at K=10:

- CA-R30-003
- CA-R30-005
- CA-R30-006
- CA-R30-007
- CA-R30-011
- CA-R30-013
- CA-R30-014
- CA-R30-017
- CA-R30-019
- CA-R30-028
- CA-R30-030

Therefore the canonical v2 correct-candidate Recall@10 control is:

- 11/30
- 36.7%

This is the control endpoint for Experiment 7. Do not recreate it with additional
paid observation calls.

## Failure disposition

Evidence-report decision reasons:

- `none_verified`: 13
- `no_candidates`: 12
- `conflicting evidence cannot be sent to catalogue retrieval.`: 4
- `unique_verified_candidate_with_two_side_support`: 1

No provider failures were reported.

CA-R30-006 is now a useful repaired-case diagnostic: the corrected candidate
CA-R30-006 is retrieved as the sole candidate, but it does not pass verification.
The repaired ground truth therefore no longer causes the old identity mismatch;
the case remains an abstention because downstream evidence is insufficient under
the frozen verifier.

## Interpretation boundary

The 3.3% full-identity accuracy is not a claim that Coin Analyzer has 3.3%
production recognition accuracy. This benchmark is deliberately conservative and
uses its frozen oracle-catalogue retrieval contract. The result establishes two
separable experimental facts:

1. correct-candidate Recall@10 is 11/30 under the current control; and
2. only 1 of those 11 retrieved-correct cases clears the current verification
   gate.

Experiment 7 changes retrieval only. Verifier or identity-gate changes must not
be bundled into E7.

## Experiment 7 migration

All earlier E7 gallery-audit, readiness, leakage, and acquisition artifacts were
derived from `recognition30_v1`. They remain historical evidence but are not
authoritative execution inputs for v2.

Before E7 execution:

1. rebuild E7 metadata/audit inputs against the canonical v2 fingerprint;
2. replace the obsolete CA-R30-006 Netherlands reference identity with the
   corrected Peru 1/2 Sol de Oro 1972 identity and re-establish source,
   rights/provenance, and leakage status;
3. re-evaluate gallery coverage and leakage declarations for the full 30-case
   v2 set;
4. freeze one exact embedding model artifact/revision and its safe-loading,
   license, integrity, preprocessing, ranking, aggregation, tie-breaking and
   resource contract;
5. implement/validate the offline evaluator fixtures;
6. pass a zero-inference v2 preflight before any private-image embedding run.

No model acquisition, embeddings, inference, production retriever change,
verifier change, identity-gate change, benchmark mutation, or new provider calls
are authorized by this closeout.

## Next gate

`E7_V2_PREFLIGHT_PENDING`

The treatment must beat the frozen 11/30 Recall@10 control without leakage,
post-hoc model/gallery selection, or unacceptable resource failures to support
further work on the tested visual-retrieval configuration.
