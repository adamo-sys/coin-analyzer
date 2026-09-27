# E7 v2 remaining review-case classification

Status: metadata-only preflight analysis. This note does **not** authorize reference-image downloads, embedding/model inference, cloud inference, or benchmark-truth edits.

Canonical observed preflight state after PR #334: **24 auto-resolved / 6 review-required**.

## Case classification

| Case | Frozen identity | Observed metadata result | Classification | Safe next action |
| --- | --- | --- | --- | --- |
| CA-R30-007 | Singapore, 50 cents, 1996, Second Series / Floral Series | Two nominally exact Singapore 50-cent candidates remain in range; frozen design text does not uniquely discriminate them | Genuine catalogue/design ambiguity | Keep fail-closed; require direct discriminating evidence before selecting a type |
| CA-R30-009 | Spain, 1 peseta, 1975, Juan Carlos I; KM#806 | 1975 nominal candidate is Francisco Franco and does not match KM#806; Juan Carlos candidate begins later in returned metadata | Frozen-truth/catalogue conflict requiring evidence | Keep fail-closed; do not alter truth without direct source/specimen evidence |
| CA-R30-020 | Dominican Republic, 1/2 peso, 1973 | Single returned 1/2-peso candidate spans 1967-1975, but issuer is labelled `Dominican Republic (1844-date)` | Historical-issuer label normalization gap | Candidate for a narrow, tested issuer alias; no fuzzy issuer matching |
| CA-R30-022 | Ireland, half crown, 1954 | Returned Irish candidate is `½ Crown`, 1951-1967; current denomination normalization does not equate `half crown` and `½ Crown` | Denomination notation normalization gap | Candidate for a narrow, tested whole-value alias; no fuzzy denomination matching |
| CA-R30-023 | West Germany, 2 Deutsche Mark, 1976, Theodor Heuss; D mintmark | Current metadata query returned zero candidates | Search/issuer vocabulary gap | Investigate query formulation/issuer vocabulary separately; do not synthesize a candidate |
| CA-R30-028 | Switzerland, 2 francs, 1968, Standing Helvetia; copper-nickel; KM#21a.1 | Expected 2-franc Standing Helvetia family is present, but Numista issuer is `Switzerland (1848-date)` and current exact issuer comparison fails | Historical-issuer label normalization gap, with catalogue-reference gate still authoritative | Candidate for a narrow, tested issuer alias; retain catalogue-reference fail-closed gate |

## Implementation boundary

The normalization candidates above are intentionally narrow equivalences derived from observed catalogue labels. Any implementation must:

1. add explicit aliases rather than fuzzy matching;
2. add focused regression tests proving the intended equivalence and nearby non-equivalence;
3. preserve the rule that a frozen catalogue reference, when present, must match before automatic resolution;
4. rerun the metadata-only audit before claiming any change to the 24/6 state; and
5. leave CA-R30-007, CA-R30-009, and CA-R30-023 unresolved unless new direct evidence justifies resolution.

No benchmark truth was changed by this classification.