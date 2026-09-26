# Recognition30 Experiment 7 — v2 preflight migration

## Status

`E7_V2_PREFLIGHT_PENDING`

This note migrates the Experiment 7 preflight boundary from the quarantined
`recognition30_v1` truth to the canonical `recognition30_v2` dataset.

It authorizes no image acquisition, model acquisition, embeddings, inference, or
production changes.

## Canonical v2 boundary

- Dataset: `recognition30_v2`
- Cases: 30
- Query images: 60
- Fingerprint:
  `ad1525098b5b1bfd8f6385518ec641962b31c197d544de43421c7902facc965d`
- Frozen E7 control: correct-candidate Recall@10 = 11/30 (36.7%).
- Treatment must beat 11/30 under the preregistered E7 decision rule.

The v1 E7 audit/readiness/leakage/acquisition artifacts are historical only.
They must not be used as v2 execution authority.

## Existing tooling review

The current preflight utilities remain structurally suitable for a v2 rebuild:

- `recognition30_e7_gallery_audit.py` loads identity truth from the dataset
  supplied on the command line and performs metadata-only Numista resolution.
- `recognition30_e7_gallery_readiness.py` consumes an audit artifact and remains
  fail-closed on identity, rights, and leakage.
- `recognition30_e7_leakage_manifest.py` constructs a zero-download review
  surface only for identity-resolved, rights-eligible cases.
- `recognition30_e7_reference_acquisition.py` is a separate bounded download and
  byte-hashing step and does not infer specimen independence.

Therefore no v1 hard-coded dataset path needs to be replaced before a metadata
rebuild. New artifacts must nevertheless be generated from v2 and must preserve
the v2 fingerprint/provenance boundary.

## Known repair requiring fresh catalogue resolution

CA-R30-006 is no longer the v1 Netherlands identity. Its canonical v2 truth is:

- country: Peru
- denomination: `1/2 Sol de Oro`
- year: `1972`
- variety/design: `Large Coat of Arms; KM#247`

Any v1 Netherlands references associated with CA-R30-006 are invalid for v2 and
must not be carried forward. The Peru identity must be resolved afresh through
the metadata audit and then pass the same rights/provenance/leakage gates as any
other case.

## Preflight sequence

The v2 migration is intentionally staged:

1. **Metadata audit**
   - run the existing Numista metadata-only audit against
     `recognition30_v2`;
   - record the resulting v2 audit artifact;
   - inspect all review-required cases;
   - do not download image bytes.

2. **Readiness rebuild**
   - derive a new readiness matrix solely from the v2 audit;
   - require explicit identity resolution and per-reference rights metadata;
   - keep leakage and execution fail-closed.

3. **Zero-download leakage manifest**
   - build a new v2 leakage-review surface only for rights-eligible cases;
   - preserve `NOT_AUDITED` for claims not established by evidence.

4. **Independent-gallery gate**
   - establish same-image, derivative, and same-physical-specimen status;
   - require independent references for all 30 candidate identities;
   - stop and report any coverage gap rather than shrinking the benchmark.

5. **Model/evaluator freeze**
   - select one exact embedding artifact/revision before observing E7 outcomes;
   - verify source, license, integrity, modality and safe loading;
   - freeze preprocessing, two-sided aggregation, similarity, tie-breaking,
     K values, hardware/thread settings and resource budgets;
   - validate the offline evaluator on synthetic/unit fixtures.

6. **Zero-inference final preflight**
   - validate v2 identity count, fingerprint, gallery coverage, hashes, rights,
     leakage declarations, model/config hashes and evaluator configuration;
   - only a clean preflight may advance to a separately authorized bounded E7
     embedding run.

## Explicit non-authority

This migration does not authorize:

- downloading new reference images;
- downloading or loading Coin-CLIP or any other embedding model;
- embedding Recognition30 or reference images;
- cloud/provider inference;
- verifier or identity-gate changes;
- production retriever replacement;
- benchmark mutation;
- post-hoc model/gallery selection;
- training or fine-tuning on Recognition30.

## Next owner boundary

The next operation requiring owner participation is the metadata audit because it
uses the owner's locally held Numista API credential. The credential must remain
outside Git and chat.

Until a v2 metadata audit exists, the E7 state remains:

`E7_V2_PREFLIGHT_PENDING`
