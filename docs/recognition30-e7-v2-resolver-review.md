# Recognition30 E7 v2 resolver review

## Scope

This review covers the eight `REVIEW_REQUIRED` rows in the first
`recognition30_v2` metadata-only audit. It does not download image bytes or run
embedding inference.

## Deterministic resolver defects

### CA-R30-005

Frozen truth: Philippines, 25 sentimo, 1990, KM#241.1.

The audit returned Numista type 2462 with issuer Philippines, year range
1983–1990, value `25 Sentimos`, and a matching KM#241.1 catalogue reference.
The intended narrow token alias `sentimo -> sentimos` was already present in
code and covered by a regression test, but the regex used a double-escaped word
boundary and therefore never applied.

Disposition: repair the regex only. No fuzzy denomination matching.

### CA-R30-006

Frozen v2 truth: Peru, 1/2 Sol de Oro, 1972, Large Coat of Arms, KM#247.

The audit returned Numista type 909 with issuer Peru, year range 1966–1973,
displayed value `½ Sol`, matching KM#247, and matching Large/Coat/Arms design
tokens. The nominal mismatch is the catalogue's shortened displayed value.

Disposition: add one explicit whole-value canonical equivalence between
`1/2 Sol de Oro` and `½ Sol`. This is deliberately narrower than token
deletion or fuzzy value matching. A negative test keeps `1 Sol` non-equivalent.

## Cases intentionally left review-required

- CA-R30-007: two nominal Singapore 50-cent candidates remain and the frozen
  design text does not supply a catalogue reference that uniquely selects one.
- CA-R30-009: the frozen year and frozen KM#806 reference point at different
  returned catalogue types; fail closed pending truth/catalogue review.
- CA-R30-020: no returned candidate established the frozen identity.
- CA-R30-022: no returned candidate established the frozen identity.
- CA-R30-023: no returned candidate established the frozen identity.
- CA-R30-028: no returned candidate established the frozen identity.

These six cases are not auto-resolved by this patch. Their ambiguity or catalogue
coverage must not be hidden with broader aliases.

## Expected next audit

With unchanged Numista metadata, the bounded normalization repair should make
CA-R30-005 and CA-R30-006 eligible for normal catalogue-reference resolution,
moving the audit from 22 resolved / 8 review-required toward 24 / 6.

That expectation is not an authoritative audit result. A fresh metadata-only v2
audit is required after merge because selected reference/rights metadata is only
materialized when the live audit resolves a case.

No reference-image acquisition, model acquisition, embeddings, verifier changes,
or production changes are authorized here.
