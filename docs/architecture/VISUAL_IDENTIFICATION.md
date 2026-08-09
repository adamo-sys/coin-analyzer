# Visual Identification Responsibility Amendment

Status: APPROVED — Benchmark v2 dataset gate in progress

## Product invariant

Visual identification proposes. OCR corroborates. Human review authorizes.

Visual identity candidates remain composite identities so country,
denomination, date, and type/design correlations are not discarded. OCR
remains advisory evidence and must not silently overwrite a visual proposal.
Conflicts remain visible, deterministic, and subject to explicit human review.

## Pre-provider benchmark gate

Benchmark v2 must be selected, independently labelled, provenance-complete,
reviewed for bias/leakage, and frozen before any candidate visual provider is
run against it. Benchmark v1 remains the frozen historical OCR baseline.

The v2 dataset contract uses paired obverse/reverse images, relative paths,
allowlisted reusable licenses, source and retrieval provenance, source hashes,
documented transformations, stable underlying-identity IDs, and explicit
identity certainty. It measures externally supplied raw visual predictions;
it does not import or invoke a model.

Supported future measurements are country, denomination, year, type/design,
full required identity, top-k composite identity recall, abstention,
infrastructure failure, provider latency, and estimated cost. OCR comparison,
fusion, review, GUI, and persistence integration remain excluded from this
unit.

## Canonical identity representation boundary

Provider output may be projected into a small provider-neutral canonical
identity representation without changing the archived raw value. This layer
normalizes representation only: Unicode, case, whitespace, punctuation,
numeric words, exact fractions, singular/plural unit forms, and explicitly
controlled aliases. Every mapped value retains its raw provider value, its
canonical value, and the rules applied. Unknown values remain explicitly
unmapped.

Country aliases are limited to unambiguous controlled names such as United
States of America and USA for United States. Historical issuer or jurisdiction
relationships, including British India to India and United Kingdom (Australia)
to Australia, are not canonicalized without a separately approved historical
jurisdiction policy.

Denominations use an exact numeric value and controlled unit identifier.
Language-specific aliases require explicit jurisdiction context where needed.
The layer performs no fuzzy matching, recognition repair, type/design
adjudication, candidate selection, confidence adjustment, or benchmark-aware
logic. It is not connected to frozen Benchmark v2 scoring or production
composition in this unit.
