# Visual Identification Responsibility Amendment

Status: APPROVED — Benchmark v2.0 frozen; headless experiments only

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

## Prospective Terra experiment boundary

The second headless experiment retains the first experiment's model, Responses
API, low reasoning effort, original image detail, two image roles, maximum of
three candidates, neutral identification task, and prohibition on tools,
retrieval, history, fusion, review, or production integration.

It adds a second score view using only the merged canonical identity layer.
The original exact score remains independently reported. Raw provider values,
canonical values, and normalization-rule provenance remain distinct. Unknown
or historically ambiguous jurisdiction values remain unmapped, and no
Benchmark v2 answer may create a canonical alias.

The structured output contract is bounded to two evidence observations of at
most 72 characters each, country at 48 characters, denomination at 40, year at
16, type/design at 80, and three candidates. The output-token ceiling changes
from 1,200 to 2,000 to provide bounded reasoning/output headroom; text
verbosity remains low. Truncated or malformed output remains an infrastructure
failure with billed usage retained.

Prospective retention requires canonical country accuracy >= 75%, canonical
denomination accuracy >= 70%, canonical full-required identity accuracy >=
50%, zero infrastructure failures, abstention <= 50%, and mean provider
latency <= 5 seconds. A separate exact-label diagnostic records cases where
canonical required fields match while the type/design label differs. It may
include semantically equivalent descriptions and is never a substantive-error
count or autonomous full-coin correctness. Substantive design confusion
requires separate adjudication. Passing authorizes only a future deterministic
visual-plus-OCR fusion evaluation.

### Prospective result: PASS

The frozen prospective run achieved 75% canonical country, 85% canonical
denomination, 65% canonical year, and 50% canonical full required identity,
with zero infrastructure failures, 3.562 seconds mean provider latency, and
approximately $0.0043 mean cost per coin. This supports visual-first candidate
generation. It does not authorize autonomous acceptance, saving, or production
rollout. Human review remains mandatory and production integration remains
unapproved.

The exact-label diagnostic contains nine cases. It is not a count of nine
substantive design errors. Separately adjudicated substantive examples include
Old Spanish Trail being identified as Connecticut Tercentenary and Elgin
Centennial being identified as Oregon Trail Memorial.

## Deterministic fusion experiment boundary

The authorized headless fusion experiment combines the archived prospective
Terra result with the unchanged production preprocessing and Tesseract PSM-11
provider. It is an evaluation adapter only: it is not imported by the desktop
composition, GUI, review controller, or collection persistence path.

Fusion compares canonical required-field evidence without confidence
arithmetic or provider priority. Equal values are `AGREED`; missing evidence
is `VISUAL_ONLY`, `OCR_ONLY`, or `UNRESOLVED`; and every non-empty disagreement
is `CONFLICT` with no selected value. OCR agreement with a lower-ranked visual
candidate is retained as diagnostic evidence and never promotes that
candidate. Raw values, image roles, ranks, providers, models, artifacts, and
normalization rules remain preserved.

### Fusion result: FAIL

The first frozen v2.0 fusion run retained the visual country and year results
but introduced an explicit denomination conflict on the Canada 1967 quarter.
That safely prevented silent acceptance, while reducing fused denomination
accuracy from 85% to 80% and full required identity from 50% to 45%. Tesseract
produced usable required-field evidence in 2 of 60 field slots, created one
false OCR conflict, and corrected no visual error. Country remained 75%, year
remained 65%, and no silent incorrect resolution was introduced. Deterministic
fusion behavior was safe, but Tesseract evidence was too weak to justify
production fusion. The formal verdict is `FAIL`; production fusion remains
unapproved.

## Reproducing the headless experiments

The preserved Terra experiment can be rerun with:

```text
python -m capture_import.visual_evaluation_cli benchmarks/v2/manifest.json
```

This command requires `OPENAI_API_KEY` in the runtime environment and incurs a
new API charge. The preserved reference run cost approximately $0.086 total.
A rerun is a new experiment result and must not overwrite the committed
historical report. The CLI defaults to timestamped paths under
`artifacts/reruns/` for that reason.

The fusion experiment can be rerun from the preserved Terra report with:

```text
python -m capture_import.fusion_evaluation_cli benchmarks/v2/manifest.json --visual-report artifacts/benchmark-v2-terra-prospective-report.json
```

Fusion performs no Terra API request and adds no Terra charge. Native
Tesseract must be installed and discoverable through `PATH`. The CLI validates
the frozen Terra artifact, configuration, PASS metrics, case inventory, and
Benchmark v2 manifest before executing the existing production OCR path. Its
outputs also default to timestamped paths under `artifacts/reruns/`.

## Benchmark interpretation limit

Benchmark v2.0 contains substantial controlled and studio imagery. Its results
are diagnostic evidence for this bounded dataset, not a claim of real-world
recognition robustness.
