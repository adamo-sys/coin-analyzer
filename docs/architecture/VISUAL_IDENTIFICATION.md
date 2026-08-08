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
