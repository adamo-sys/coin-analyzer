# Recognition30 E7-v2 metadata review-case classification

Status: evidence note; no execution authorization.

This note records the six `REVIEW_REQUIRED` cases from the post-#334 E7-v2 metadata-only audit. It does not modify frozen Recognition30 truth, download reference images, run embedding inference, or authorize E7 execution.

## Classification

| Case | Observed audit state | Classification | Safe next step |
| --- | --- | --- | --- |
| CA-R30-007 | Singapore 50 cents 1996 returns two nominally exact candidates: Numista 478485 (`50 Cents (Silver)`) and 1672 (`50 Cents (ribbon downwards)`); frozen design text does not provide a catalogue reference and does not discriminate them. | Genuine catalogue/design ambiguity. | Keep fail-closed. Resolve only from independent specimen/design evidence; do not add a normalization alias. |
| CA-R30-009 | Frozen truth is Spain 1 peseta 1975, `Juan Carlos I; KM#806`; the 1975 nominal candidate is Numista 786, Francisco Franco, and does not match the frozen catalogue reference. | Frozen truth/type-year conflict requiring evidence review. | Keep fail-closed. Do not alter truth or matcher without direct benchmark evidence. |
| CA-R30-020 | Dominican Republic 1/2 peso 1973 returns Numista 5900, `½ Peso`, issuer `Dominican Republic (1844-date)`, but exact identity is false. | Narrow issuer/value representation mismatch candidate. | Test explicit, evidence-backed normalization only; retain fail-closed behavior until covered by focused tests and a fresh metadata audit. |
| CA-R30-022 | Ireland half crown 1954 returns Numista 5188, `½ Choróin / 2 Scilling 6 Phingin`, issuer Ireland, value `½ Crown`, but exact identity is false. | Narrow denomination representation mismatch candidate. | Test explicit `half crown`/`½ Crown` equivalence only; avoid fuzzy denomination matching. |
| CA-R30-023 | West Germany 2 Deutsche Mark 1976, `Theodor Heuss; D mintmark`, returns zero candidates for the current query. | Search vocabulary/issuer retrieval failure, not yet an identity-resolution failure. | Investigate a deterministic query alias or fallback while preserving the frozen identity and exact post-retrieval checks. |
| CA-R30-028 | Switzerland 2 francs 1968, `Standing Helvetia; copper-nickel; KM#21a.1`, exposes the expected Standing Helvetia 2-franc family under issuer `Switzerland (1848-date)`, but exact identity is false. | Narrow historical-issuer representation mismatch candidate; catalogue-reference confirmation still required before auto-resolution. | Test explicit issuer normalization and require the existing frozen catalogue-reference gate to remain authoritative. |

## Engineering disposition

The six cases are not one class of matcher defect. `007` and `009` should remain review cases unless new direct evidence resolves their identity conflict. `020`, `022`, `023`, and `028` justify bounded investigation of explicit catalogue vocabulary normalization/retrieval, not broad fuzzy matching.

Any implementation slice must preserve these invariants:

1. frozen Recognition30-v2 truth is unchanged;
2. expected catalogue references remain authoritative when present;
3. ambiguous nominal matches remain fail-closed;
4. normalization is explicit and narrowly evidenced rather than fuzzy;
5. metadata preflight downloads no image bytes and runs no embedding/model inference;
6. a fresh owner-run metadata audit is required before accepting any changed resolved/review counts.

Canonical observed preflight state entering this classification: 30 cases, 24 auto-resolved, 6 review-required, 48 reference sides exposed, 24 sides with explicit rights metadata, zero image bytes downloaded, zero embedding inference, execution unauthorized.
