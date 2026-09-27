# Recognition30 E7 v2 metadata-preflight closeout

## Status

`CLOSED — E7 PARKED`

This is the final metadata-only closeout for Recognition30 Experiment 7 v2.
It records the authoritative post-PR-#341 audit result and parks E7. It does
not authorize reference-image acquisition, model acquisition, embeddings,
inference, frozen-truth changes, or further recognition optimization.

## Authoritative audit evidence

- Artifact: `C:\Projects\recognition30-runs\e7-v2-post341-20260927\gallery-audit.json`
- SHA-256: `6ec82cb78d24726b67499dfc1573f7b7bb592ab2ce3fd4e370da002b07404ee9`
- Schema: `coin-analyzer-recognition30-e7-gallery-audit-v3`
- Mode: `NUMISTA_METADATA_ONLY_ZERO_INFERENCE`
- Repository base: post-PR-#341 `main` (`320fdfd0c3fe0d3d060e958faa14a53cbbaca772`)

The artifact contains 30 unique case rows. It reports 27 auto-resolved cases
and 3 `REVIEW_REQUIRED` cases: CA-R30-007, CA-R30-009, and CA-R30-028.
This is an observed audit result, not a target used to relax a gate.

## CA-R30-023 disposition

CA-R30-023 resolved as `AUTO_DESIGN_TOKEN_UNIQUE` through the bounded West
Germany discovery path:

- Initial query: `West Germany 2 Deutsche Mark 1976`
- Query used: `Federal Republic of Germany 2 Deutsche Mark 1976 Theodor Heuss`
- Selected Numista type: `1935`, `2 Deutsche Mark (Theodor Heuss)`
- Issuer: `Germany, Federal Republic of`
- Value: `2 Deutsche Mark`
- Year range: 1970–1987
- Exact identity match: true
- Design evidence: `theodor` and `heuss` overlap the frozen design terms.
  There is no frozen catalogue-reference match for this case, so resolution is
  deliberately based on the bounded design-token discovery rule rather than a
  manufactured catalogue identifier.

## Remaining fail-closed cases

| Case | Artifact evidence | Disposition |
| --- | --- | --- |
| CA-R30-007 | Two candidates are exact issuer/value/year matches: type 478485 (`50 Cents (Silver)`, 1992–2005) and type 1672 (`50 Cents (ribbon downwards)`, 1992–2013). The frozen `Second Series / Floral Series` design has neither a matching catalogue reference nor design-token overlap for either candidate. | Genuine catalogue/type ambiguity; retain `REVIEW_REQUIRED`. |
| CA-R30-009 | Type 786 is the only exact issuer/value/year match (`1 Peseta - Francisco Franco (Ávalos)`, 1967–1975), but does not match frozen `KM#806`. Type 787 matches `KM#806` and Juan Carlos design terms, but its year range is 1976–1980 and therefore excludes frozen year 1975. | Frozen truth/type-year/catalogue conflict; retain `REVIEW_REQUIRED`. |
| CA-R30-028 | Type 189 is an exact issuer/value/year match (`2 Francs (Helvetia standing; copper-nickel)`, 1968–2026) and overlaps `standing`, `helvetia`, `copper`, and `nickel`, but lacks the frozen `KM#21a.1` catalogue-reference match. | Frozen catalogue-reference requirement remains unsupported; retain `REVIEW_REQUIRED`. |

## Safety and authority invariants

- `image_bytes_downloaded`: `0`
- `embedding_inference_run`: `false`
- `execution_authorized`: `false`
- No reference-image acquisition, embedding/model inference, or E7 execution
  was started by this audit or closeout.
- The audit is metadata-only and records image references as metadata; it does
  not fetch image bytes.
- The audit's design-reference rule remains fail closed: an identity with a
  frozen catalogue reference is auto-resolved only when exactly one exact
  candidate carries that reference. CA-R30-009 and CA-R30-028 demonstrate that
  the authority was not weakened to increase coverage.
- No frozen Recognition30 benchmark truth was modified by this closeout.

## Parking decision

E7 is **PARKED** at this metadata-preflight endpoint. Do not begin
reference-image acquisition, download Numista images, acquire or run Coin-CLIP
or another embedding model, run E7 inference, modify frozen Recognition30
truth, or try to force CA-R30-007, CA-R30-009, or CA-R30-028 to resolve.

The next milestone is outside E7: plan and deliver a usable, showable mobile
coin-entry plus human-verification vertical slice.
