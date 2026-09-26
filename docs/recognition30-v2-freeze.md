# Recognition30 v2 freeze record

## Status

**V2 DATASET IDENTITY FROZEN — BASELINE RERUN PENDING**

Recognition30 v1 remains immutable historical evidence. Recognition30 v2 is a
separate local dataset derived from v1 with the confirmed CA-R30-006
ground-truth repair.

## Dataset identity

- dataset: `recognition30_v2`
- cases: 30
- query images: 60
- fingerprint scheme: `recognition30-dataset-fingerprint-v1`
- canonical executable fingerprint:
  `ad1525098b5b1bfd8f6385518ec641962b31c197d544de43421c7902facc965d`

The fingerprint was computed from the actual local v2 runner inputs after the
repair. It is the identity to require for new Recognition30 v2 benchmark
artifacts.

## CA-R30-006 correction

The v2 ground-truth row is:

- case: `CA-R30-006`
- images: `IMG_8810.JPEG`, `IMG_8811.JPEG`
- issuer: Peru
- denomination: 1/2 Sol de Oro
- year: 1972
- variety: Large Coat of Arms; KM#247
- notes: Standard circulation issue
- truth status: verified

The year was established from a dataset-owner-supplied close-up photograph of
the physical coin showing `1972`. This is direct specimen evidence, not a year
inferred from a catalogue example.

## Integrity boundary

The local v2 construction reported:

- 30 cases
- 60 image files
- only the known CA-R30-006 ground-truth identity was intentionally repaired
- v1 was not edited in place

This record does **not** claim that every other case received a new independent
visual re-verification during the v2 repair. No additional ground-truth defect
has been established in this repair.

## Historical boundary

The v1 fingerprint
`5ce59a80db35b58950358eb3441cdd78b350f5bcecf0326678202366ab737a20`
continues to identify the historical v1 dataset and its reports. V1 reports
must not be relabelled as v2.

New v2 results must use the v2 fingerprint above and must be written to new
artifacts rather than overwriting v1 outputs.

## Next gate

Before resuming E7 visual-reference retrieval work:

1. run a new grounded baseline against `recognition30_v2`;
2. preserve its report/checkpoint/evidence artifacts separately from v1;
3. rebuild E7 metadata audit, readiness, leakage-manifest, and acquisition
   artifacts from the v2 identity;
4. re-evaluate the E7 gates from those v2 artifacts.

This freeze record does not authorize Coin-CLIP/model acquisition, embedding
inference, production retriever replacement, or benchmark tuning.
