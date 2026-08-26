# Adversarial Reference Retrieval Benchmark

This benchmark is the next validation stage for Coin Analyzer's independent reference-image retrieval architecture. It is intentionally isolated from the successful 8-case pilot so the pilot cannot be expanded opportunistically after seeing retrieval results.

## Objective

Test whether the current, unchanged reference-image retrieval backend generalizes from the 8/8 pilot to a deliberately difficult 25-case validation set.

Primary success gate:

- **Top-1 accuracy >= 23/25 (92%)**

Secondary metrics:

- Recall@5
- score and Top-1/Top-2 margin distributions
- 100%-selective / 0%-unsafe acceptance coverage
- performance by adversarial class

The 25-case result is a validation milestone, not a production-accuracy claim. A later 50+ case benchmark with broader catalogue competition remains required before making strong generalization claims.

## Freeze rule

The benchmark identities, query images, independently sourced reference images, and provenance metadata must be frozen **before retrieval results are inspected**.

After freeze:

- do not remove or replace a case because retrieval misses it;
- do not add an easier reference image because a case scores poorly;
- do not tune ORB/HSV weights, preprocessing, rotations, thresholds, or ranking using this validation set;
- algorithm changes require a new experiment/version and must report the original frozen result first;
- failed or unavailable references remain recorded rather than silently disappearing.

## Target composition: 25 cases

The set should deliberately contain near-neighbour competition rather than mostly easy cross-country separation.

| Bucket | Target | Purpose |
| --- | ---: | --- |
| Same country + denomination + nearby year/design | 6 | Tests date/design discrimination within a series |
| Same monarch/portrait across denominations | 4 | Punishes portrait-driven false matches |
| Visually similar commemoratives | 5 | Tests motif/layout discrimination among near-neighbours |
| World-coin legend/layout lookalikes | 4 | Tests issuer/denomination ambiguity |
| Worn/toned/rotated/realistic photography | 4 | Tests robustness to acquisition conditions |
| Distinctive controls | 2 | Confirms the retrieval pipeline still handles easy positives |
| **Total** | **25** | |

Cases may satisfy more than one difficulty tag, but the frozen manifest must document a primary adversarial bucket for each identity.

## Independence and leakage rules

Every candidate must have independently sourced reference imagery. The query-side benchmark image and reference image must not be byte-identical or derivatives of the same source asset when that provenance is known.

Required provenance per side/reference:

- source page
- source file URL when available
- author/photographer when available
- licence/reuse status
- retrieval date
- source asset identifier/hash when available
- note explaining why the reference is independent from the query source

The existing exact-byte leakage guard remains mandatory, but provenance review is also required because resized/cropped derivatives of the same source can evade a byte hash check.

## Retrieval backend freeze

The first 25-case run must use the existing backend unchanged:

- OpenCV ORB local features
- HSV histogram similarity
- four-way rotation handling
- geometric-mean two-side combination
- existing ORB/HSV weighting

No thresholding is applied to Top-1 accuracy. Acceptance-frontier analysis happens only after the raw retrieval artifact is saved.

## Planned files

The expansion should ultimately produce:

- `benchmarks/adversarial_reference/manifest.json` — frozen 25 query cases
- `benchmarks/adversarial_reference/reference_catalogue/manifest.json` — independent reference images + provenance
- `benchmarks/adversarial_reference/FREEZE.json` — case IDs, hashes, catalogue version, freeze timestamp, and protocol version
- `artifacts/adversarial-reference-retrieval-25.json` — first untouched retrieval result
- `artifacts/adversarial-reference-frontier-25.json` — offline acceptance frontier

Generated image bytes should use the repository's existing benchmark/reference storage conventions and must not overwrite Benchmark v2 assets.

## Decision gates

Interpret the first frozen run as follows:

- **23-25 / 25 Top-1:** strong evidence that reference retrieval is the leading recognition architecture; expand to 50+ adversarial cases without tuning on these 25.
- **20-22 / 25:** promising but below the 90% target; analyze failure classes and test a separately versioned improvement.
- **<20 / 25:** the 8/8 pilot did not generalize sufficiently; keep the result and reconsider the visual representation/retrieval method.

A result is never improved by deleting failed cases.

## Current baseline

The preceding independent-reference pilot produced **8/8 Top-1 and 8/8 Recall@5** on its available cases. That result motivates this benchmark but is not included in the 25-case success count unless a case is deliberately selected and frozen here with independent validation assets.
