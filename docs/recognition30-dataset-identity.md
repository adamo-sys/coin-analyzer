# Recognition30 v1 dataset identity

## Current executable identity

Recognition30 uses `recognition30-dataset-fingerprint-v1` for its executable
dataset identity. The canonical Recognition30 v1 fingerprint is:

```text
5ce59a80db35b58950358eb3441cdd78b350f5bcecf0326678202366ab737a20
```

The algorithm is SHA-256 over the actual runner inputs, sorted by basename:

1. `pair_manifest.csv`
2. `ground_truth.csv`
3. Every direct file under `images/`

For each input it feeds the UTF-8 basename, a NUL byte, the raw file bytes,
and a final NUL byte. It excludes filesystem paths, timestamps, filesystem
metadata, CSV normalization, `benchmark_freeze.json`, and
`integrity_manifest.csv`.

The harness validates `recognition30_v1` against this exact fingerprint before
it creates the provider or starts case execution. Checkpoint continuation and
join validation require the same fingerprint scheme as well as the fingerprint.

## Historical freeze provenance

`benchmark_freeze.json` preserves the legacy historical freeze fingerprint:

```text
4f6988ed84fd5c4db1e06452e942bcfb75b0f495f74c5d54ad37e44c17b534de
```

Its original derivation is unrecovered. It remains provenance for the historical
freeze and is not accepted as the executable runner identity. Reconciliation on
2026-09-22 independently verified unchanged benchmark content: all 60 images,
`ground_truth.csv`, `benchmark_freeze.json`, and `integrity_manifest.csv` are
byte-identical to preserved source data; the reconstructed `pair_manifest.csv`
matches the preserved integrity record and all 30 mappings.
