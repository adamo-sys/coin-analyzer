# E7 v2 review-case classification

Status: PRE-FLIGHT EVIDENCE ONLY — no reference-image acquisition, embedding inference, benchmark-truth mutation, or execution authorization.

Canonical observed metadata audit state after PR #334: 30 cases, 24 auto-resolved, 6 review-required. This note classifies those six failures before any further matcher changes.

## Classification

| Case | Frozen identity | Observed audit evidence | Classification | Safe next action |
| --- | --- | --- | --- | --- |
| CA-R30-007 | Singapore, 50 cents, 1996, Second Series / Floral Series | Two nominally exact Numista candidates remain: type 478485 `50 Cents (Silver)` and type 1672 `50 Cents (ribbon downwards)`. Frozen design text does not discriminate them. | Genuine catalogue/type ambiguity | Keep REVIEW_REQUIRED until independent identity evidence discriminates the type. Do not add a heuristic. |
| CA-R30-009 | Spain, 1 peseta, 1975, Juan Carlos I; KM#806 | The 1975 nominal candidate is type 786, Francisco Franco, and does not match KM#806. The Juan Carlos candidate exposed by search starts in 1976. | Frozen truth/type-year conflict requiring evidence | Keep REVIEW_REQUIRED. Do not mutate frozen truth or weaken catalogue-reference authority without direct source evidence. |
| CA-R30-020 | Dominican Republic, 1/2 peso, 1973 | Search exposes one plausible type, Numista 5900 `½ Peso`, issuer `Dominican Republic (1844-date)`, 1967–1975, but exact matching fails. | Historical issuer-label + denomination representation normalization candidate | Test narrow explicit equivalences only; no fuzzy matching. |
| CA-R30-022 | Ireland, half crown, 1954 | Search exposes Numista 5188 `½ Choróin / 2 Scilling 6 Phingin`, issuer Ireland, value `½ Crown`, 1951–1967. Exact matching fails on `half crown` vs `½ Crown`. | Denomination representation normalization candidate | Test a narrow whole-value equivalence; remain fail-closed for unrelated values. |
| CA-R30-023 | West Germany, 2 Deutsche Mark, 1976, Theodor Heuss; D mintmark | Current query returns zero candidates. | Search/issuer vocabulary failure, not enough evidence to resolve identity | Investigate query vocabulary separately. Do not invent a catalogue ID or bypass candidate discovery. |
| CA-R30-028 | Switzerland, 2 francs, 1968, Standing Helvetia; copper-nickel; KM#21a.1 | Search exposes the expected Standing Helvetia 2-franc family, including type 189 with issuer `Switzerland (1848-date)`, but exact matching fails and no observed candidate matches the frozen catalogue reference. | Historical issuer-label normalization candidate plus unresolved catalogue-reference evidence | An issuer-label equivalence may improve nominal matching, but KM#21a.1 remains authoritative; keep REVIEW_REQUIRED unless the candidate reference also matches. |

## Decision

The six cases are **not** justification for six case-specific hacks.

* 007 and 009 remain evidence-review cases.
* 020 and 022 justify bounded normalization tests for observed label/denomination representations.
* 023 needs query-vocabulary investigation before matcher changes.
* 028 may justify a bounded historical issuer-label normalization, but the frozen KM reference must continue to fail closed if catalogue evidence does not match.

Any implementation should preserve the current rule that a frozen catalogue reference, when present, is discriminating identity evidence and cannot be overridden by issuer/value/year agreement alone.

## Boundary

This classification consumes metadata already produced by the E7 audit. It authorizes no image-byte downloads, no model acquisition or inference, no cloud inference, no benchmark-truth edits, and no E7 execution.