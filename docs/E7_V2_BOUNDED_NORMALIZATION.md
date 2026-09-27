# E7 v2 bounded historical normalization

Status: PRE-FLIGHT ONLY. No reference-image acquisition, embedding/model inference, cloud inference, benchmark-truth mutation, or execution authorization.

This slice implements only the deterministic normalization candidates justified by the post-#334 24/6 audit and the review-case classification merged from PR #338.

## Included

- `Dominican Republic` ↔ Numista `Dominican Republic (1844-date)` issuer-label normalization.
- `Switzerland` ↔ Numista `Switzerland (1848-date)` issuer-label normalization.
- Unicode `½` expansion before denomination normalization so `1/2 peso` can match `½ Peso` without fuzzy matching.
- Explicit whole-value `half crown` ↔ `½ Crown` equivalence.

## Fail-closed boundaries

- CA-R30-007 remains a genuine catalogue/type ambiguity; no heuristic is added.
- CA-R30-009 remains a frozen truth/type-year conflict; truth is not changed.
- CA-R30-023 remains a query-vocabulary/candidate-discovery problem; no catalogue ID is invented.
- CA-R30-028 may now pass nominal issuer/value/year matching, but its frozen `KM#21a.1` remains authoritative. A candidate without that exact catalogue reference must remain `REVIEW_REQUIRED`.

The focused tests include negative controls for adjacent denominations and an explicit CA-R30-028 regression proving issuer normalization cannot bypass catalogue-reference authority.
