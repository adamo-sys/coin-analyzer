# E7 v2 review-case classification

Status: preflight evidence note only. This document does not authorize image acquisition, embedding inference, benchmark-truth mutation, or E7 execution.

Canonical post-#334 metadata audit state: 24 auto-resolved / 6 review-required. The unresolved cases are CA-R30-007, 009, 020, 022, 023, and 028.

## Classification

| Case | Classification | Evidence from post-#334 audit | Safe next step |
| --- | --- | --- | --- |
| CA-R30-007 | Genuine catalogue ambiguity | Two Singapore 50 Cents candidates cover 1996 and both satisfy nominal issuer/value/year identity. Frozen `Second Series / Floral Series` text does not currently discriminate them. | Keep review-required until direct catalogue/design evidence identifies one type. Do not add a fuzzy rule. |
| CA-R30-009 | Frozen-truth/catalogue conflict requiring evidence review | Frozen identity says Spain, 1 peseta, 1975, `Juan Carlos I; KM#806`. Audit results expose a 1975 Francisco Franco nominal match while the Juan Carlos candidate begins in 1976. The catalogue-reference gate correctly refuses the nominal 1975 candidate. | Keep review-required. Verify the frozen specimen/truth evidence before any truth change. Do not normalize around the contradiction. |
| CA-R30-020 | Historical issuer-label normalization candidate | The sole plausible result is Numista type 5900, `½ Peso`, issuer `Dominican Republic (1844-date)`, 1967-1975. It fails exact identity against frozen issuer `Dominican Republic` because the catalogue appends a historical date qualifier. | Test a narrow, deterministic issuer equivalence; retain fail-closed behavior for unrelated issuers. |
| CA-R30-022 | Denomination-label normalization candidate | Numista type 5188 is Ireland, 1951-1967, value `½ Crown`; frozen denomination is `half crown`. Current normalization drops the `½` glyph rather than equating the whole denomination. | Test an explicit whole-value equivalence for `half crown` ↔ `½ Crown`; do not introduce fuzzy denomination matching. |
| CA-R30-023 | Search/query vocabulary failure | Query `West Germany 2 Deutsche Mark 1976` returned zero candidates. There is therefore no candidate evidence on which exact identity resolution can operate. | Investigate a bounded query alias/search fallback separately. Do not auto-select a type without returned catalogue evidence. |
| CA-R30-028 | Historical issuer-label normalization candidate | Audit exposes the expected `2 Francs (Helvetia standing; copper-nickel)` family under issuer `Switzerland (1848-date)`, while frozen issuer is `Switzerland`. Exact identity remains false because of the issuer representation. | Test the same narrow historical-date-suffix issuer normalization used for 020, with negative controls. |

## Decision

Do not treat the six rows as one matcher defect. Preserve CA-R30-007 and CA-R30-009 as evidentiary review cases. Treat CA-R30-020, CA-R30-022, and CA-R30-028 as candidates for a small deterministic normalization patch with focused positive and negative tests. Treat CA-R30-023 as a separate query-recall problem.

No benchmark truth is changed by this classification. No reference-image bytes are acquired. No embedding/model inference is run. The 24/6 post-#334 audit remains the canonical observed state until a later metadata-only audit produces new evidence.