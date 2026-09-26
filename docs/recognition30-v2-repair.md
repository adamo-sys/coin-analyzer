# Recognition30 v1 ground-truth defect and v2 repair gate

## Status

**V1 QUARANTINED FOR NEW BENCHMARK CLAIMS — V2 REPAIR PENDING EXACT DATE CONFIRMATION**

Recognition30 v1 remains immutable historical evidence. Do not edit it in place.

## Confirmed defect

On 2026-09-26, visual inspection of the frozen query pair assigned to
`CA-R30-006` found that the images do not depict the frozen ground-truth
identity `Netherlands / 25 cents / 1972 / Juliana; nickel; KM#183`.

The acquisition report binds `CA-R30-006` to:

- `IMG_8810.JPEG` — SHA-256 `bc84abb29c323c5c3ad15954fbe6d647e4b276c23558448a4f0dcd08ff384832`
- `IMG_8811.JPEG` — SHA-256 `3574d7aa55aba58d90bed1048b3eb2a459d0a4e066e8804fcd05246e1f9b1a16`

The visible coin is Peruvian and bears the legends `1/2 SOL DE ORO` and
`BANCO CENTRAL DE RESERVA DEL PERU`, with a vicuña reverse. External
catalogue/reference research identifies this design family as Peru 1/2 Sol de
Oro, small coat of arms, KM#260 / Numista N#9097 (1973–1975).

On 2026-09-26 the dataset owner supplied a new close-up photograph of the same
physical coin and directly reported the date as **1972**. The photograph visibly
shows the date at the bottom of the coat-of-arms side. This is direct specimen-level
evidence for the corrected year; it is not inferred from a catalogue example.

## Consequences

- The canonical v1 executable fingerprint
  `5ce59a80db35b58950358eb3441cdd78b350f5bcecf0326678202366ab737a20`
  remains the identity of the historical defective dataset.
- Existing v1 benchmark reports remain historical artifacts and must not be
  rewritten or relabelled as v2.
- New Recognition30 accuracy/retrieval claims must not treat v1 as verified
  30/30 ground truth.
- E7 leakage/retrieval work for `CA-R30-006` is blocked until the corrected
  identity is frozen.
- No Coin-CLIP/embedding execution is authorized by this document.

## V2 repair procedure

1. Preserve `recognition30_v1` byte-for-byte.
2. Exact year established from owner-supplied physical-coin close-up: `1972`.
3. Copy v1 to a new `recognition30_v2` dataset.
4. Change only the defective `CA-R30-006` ground-truth identity unless a
   separate integrity finding requires another correction.
5. Record the corrected identity and evidence in the v2 freeze record.
6. Recompute the executable dataset fingerprint using
   `recognition30-dataset-fingerprint-v1` over the actual v2 runner inputs.
7. Re-run integrity checks and require 30 unique cases / 60 unchanged query
   images.
8. Re-run the grounded baseline as a new v2 run. Do not overwrite v1 results.
9. Rebuild E7 audit/readiness/leakage artifacts from v2 before resuming visual
   retrieval evaluation.

## Expected corrected identity, pending year

- issuer: Peru
- denomination: 1/2 Sol de Oro
- design: Small Coat of Arms; vicuña reverse
- catalogue reference: KM#260
- Numista type: N#9097
- year: **1972 — DIRECTLY CONFIRMED FROM PHYSICAL COIN**
