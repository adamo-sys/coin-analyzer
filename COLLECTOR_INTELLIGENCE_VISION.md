# Collector Intelligence Vision

Status: v9.0 Phase 0 - design only

Implementation: Not started

Baseline: v8.8 Phase 6 complete at `1095887` with 1,506 tests passing

## Collector Intelligence Manifesto

Coin Analyzer exists to help collectors reason, not to replace them.

Every recommendation must be:

- explainable
- deterministic where practical
- evidence-based
- source-attributed
- reproducible
- revisable when new evidence arrives

## Mission

Define how Coin Analyzer is allowed to reason before it implements candidate identification, condition assessment, or grading-readiness intelligence.

Coin Analyzer should reduce collector uncertainty without pretending that uncertain evidence is certain. It should help a collector understand what the available evidence supports, what it does not support, and what additional evidence would be most useful.

> Coin Analyzer advises. The collector decides.

This document is a product and architecture boundary. It authorizes no code, no candidate engine, no OCR integration, and no grading feature.

## The Humility Principle

Coin Analyzer is an evidence engine, not an authority.

It gathers observations.

It compares evidence.

It ranks possibilities.

It explains its reasoning.

It requests additional evidence when confidence is insufficient.

It never pretends certainty it does not possess.

The collector always remains the final decision-maker.

## Reproducible Conclusions

Every conclusion must be reproducible.

When the collector selects `Explain this result`, the system must be able to reconstruct the conclusion from the same explicit inputs and show:

- the conclusion scope, candidate, confidence state, and software/rule version
- every observation considered, with its source image, collector input, or OCR context
- every supporting, contradicting, missing, and unevaluable evidence item
- the reference claims used, including source, source-record ID, raw value, normalized value, and conflicts
- competing candidates and the evidence that kept them in or moved them below the displayed candidate
- the deterministic rank or decision rule that produced the result
- the specific additional evidence most likely to revise the conclusion

An explanation must not merely restate the result. It must provide enough structured evidence for a collector to understand and challenge the reasoning. If the original evidence, source configuration, or rule version is unavailable, the report must say that reproducibility is degraded rather than presenting a result as fully reproducible.

## 1. Allowed Conclusions

With sufficient, explicit evidence, Collector Intelligence may:

- report that supplied photos are or are not suitable for a named downstream task using Image Readiness
- report OCR observations as observations, including uncertainty and source image context
- retrieve and display reference facts, provenance, validation findings, and source disagreements
- produce a ranked list of candidate reference issues when a future approved candidate engine has evidence to compare
- explain which observations and source claims increased, reduced, or blocked a candidate's rank
- state that evidence is incomplete, conflicting, unreadable, or insufficient
- request a specific additional photo, measurement, reading, or collector confirmation
- distinguish an exact reference lookup from an identification candidate
- preserve more than one viable candidate when the evidence does not justify a single answer

Every conclusion must be scoped. For example, a conclusion may say that photos are adequate for broad identification but inadequate for variety attribution. A candidate may be plausible for a date and denomination while remaining unresolved on a mintmark or variety.

## 2. Prohibited Conclusions

Collector Intelligence must not:

- present a candidate as a confirmed identification without sufficient evidence and collector confirmation where confirmation is required
- infer a candidate solely from a collection item's country, year, denomination, notes, or filename without explicit approval of that evidence path
- describe a reference claim as the canonical fact when providers disagree
- select a conflict winner based on provider order, source type, manual entry, or an unexplained score
- imply image recognition, OCR certainty, variety attribution, or grade prediction that has not been implemented and validated
- treat an OCR string as a verified date, legend, mintmark, or catalogue number
- convert a candidate confidence into a market, grading, authenticity, or submission recommendation
- hide missing, contradictory, malformed, or unavailable evidence
- use decorative percentages, colour, or ranking order as a substitute for an explanation
- mutate collection records, provider records, photo metadata, files, or source data while reasoning

When these boundaries conflict with a desire to be helpful, the boundary wins.

## 3. Evidence Model and Minimum Evidence Requirements

Collector Intelligence reasons over explicit evidence packages. Evidence must remain typed, attributable, and separable from conclusions.

| Evidence layer | Owner | Permitted meaning | Not permitted to mean |
| --- | --- | --- | --- |
| Image readiness | `ImageAssessmentEngine` | Whether supplied photos meet stated technical readiness gates | Identity, variety, grade, or authenticity |
| OCR observations | future OCR adapter | Text observed from a named image and confidence/quality metadata | Verified legend, date, or attribution |
| Reference facts | providers and aggregator | Source-specific claims, provenance, validation, and disagreements | A canonical truth or preferred source |
| Collector input | collector-facing UI | Explicit facts, measurements, and confirmations supplied by the collector | Unverified source data |
| Identification candidates | future candidate engine | A transparent comparison between evidence and one reference issue | Confirmation, grade, valuation, or submission advice |

### Minimum Evidence by Conclusion

| Requested conclusion | Minimum evidence |
| --- | --- |
| Broad candidate generation | At least one explicit discriminating observation plus an Image Readiness result that permits broad identification, unless the input is non-image collector-entered data. |
| Candidate refinement | At least one additional discriminating observation that can separate the remaining candidates, such as date, denomination, authority, design marker, mintmark, diameter, weight, or confirmed legend text. |
| Exact reference lookup | An explicit normalized `issue_id`; no inference required. |
| Variety-level candidate | Evidence that addresses the variety discriminator and a readiness result appropriate for variety attribution. |
| Condition assessment | A separately approved condition evidence model; photo readiness alone is never enough. |
| Grading readiness | A separately approved grading-readiness model with explicit condition, economics, and submission-policy evidence. |

No evidence threshold may be bypassed because a source record is familiar, a result looks likely, or only one candidate happens to be returned.

## 4. Confidence Semantics

Confidence communicates the strength and completeness of evidence for a specific conclusion. It is not a cosmetic percentage, a source-preference score, or a promise of correctness.

Before any numeric presentation is approved, confidence must have:

- a named conclusion scope
- a documented evidence rubric
- deterministic inputs and deterministic output
- a complete explanation of positive, negative, missing, and conflicting evidence
- explicit handling for unknown and unavailable evidence
- test cases at every decision boundary

Until a calibrated numeric model is approved, use discrete, defined states:

| State | Meaning |
| --- | --- |
| `INSUFFICIENT_EVIDENCE` | The system cannot responsibly rank or narrow candidates. |
| `LOW` | Some evidence is present, but it is weak, incomplete, or materially conflicted. |
| `MODERATE` | Evidence supports a candidate comparison, but a meaningful discriminator remains unresolved. |
| `HIGH` | Multiple independent, relevant observations support a candidate and no unresolved blocker remains for the stated scope. |
| `NOT_APPLICABLE` | The requested conclusion is outside the implemented or evidence-supported scope. |

`HIGH` does not mean confirmed. It means the system has strong evidence for the stated candidate and still reports its provenance, assumptions, and remaining limitations.

## 5. Candidate Ranking Rules

Candidate generation, when separately approved, must be deterministic and evidence-based.

1. Start with explicit candidate records from the configured reference-provider layer. Do not create a candidate from a source that lacks provenance.
2. Evaluate each candidate only against typed observations permitted for the requested scope.
3. Record evidence that supports, contradicts, or cannot evaluate each candidate.
4. Apply documented weights only to discriminating evidence. A shared country or broad denomination cannot dominate a date, mintmark, measurement, or design conflict.
5. Treat missing required evidence as a reduction or a blocker according to the named conclusion scope.
6. Treat contradictory evidence as visible negative evidence. Do not discard it to improve a rank.
7. Preserve ties and close alternatives. Do not force a single candidate when multiple candidates remain materially plausible.
8. Order equal candidates deterministically using stable identifiers, not source preference or runtime order.
9. Do not rank beyond the precision supported by the evidence. A broad-issue candidate cannot silently become a variety candidate.

Candidate ranking must never use provider registration order as a hidden weight. Manual records remain attributed source claims, not implicit overrides.

## 6. Explainability Requirements

Every candidate or readiness conclusion must answer:

- **What is this conclusion?** State the conclusion scope and status.
- **Why is it shown?** List the observations and reference claims considered.
- **Why is it ranked here?** Separate supporting, contradicting, missing, and unresolved evidence.
- **Which sources support the reference facts?** Retain provider, source, source-record, raw value, normalized value, and validation context.
- **What conflicts remain?** Display source disagreements without selecting a winner.
- **What would change the conclusion?** Name the highest-value next observation, photo, measurement, or collector confirmation.
- **What is not being claimed?** State relevant limitations, especially where the system is not identifying, grading, authenticating, or pricing.

Explanations must be generated from structured evidence records, not post-hoc prose that cannot be traced to a decision input.

## 7. When to Request More Evidence

The system should request more evidence when a specific missing observation can materially distinguish candidates or unlock a requested conclusion.

Appropriate requests include:

- a readable obverse/front or reverse/back image when required coverage is missing
- a closer image of a date, legend, mintmark, edge, variety marker, or certification label
- a scale weight or measured diameter when these values distinguish candidates
- confirmation of a collector-entered fact that conflicts with observations or sources
- a clearer image when Image Readiness blocks the requested task

Requests must be specific, proportional, and actionable. For example:

```text
The remaining candidates differ by mintmark.
Add a close-up of the mintmark area before narrowing the list.
```

Do not request more photos merely because photos exist. Do not ask for evidence the system cannot use in an approved conclusion.

## 8. Insufficient Evidence

`INSUFFICIENT_EVIDENCE` is a successful, informative result. It is required when the system cannot responsibly distinguish candidates or support the requested conclusion.

Return `INSUFFICIENT_EVIDENCE` when:

- no usable evidence was supplied
- Image Readiness blocks the requested downstream task
- required photo-role coverage is missing
- OCR observations are absent, unreadable, or too uncertain for the requested use
- reference claims are unavailable, invalid, or too conflicted to support a comparison
- multiple candidates remain tied without a discriminating observation
- the requested precision exceeds the available evidence
- a provider or engine failure prevents a trustworthy assessment

The result must include:

- what evidence was considered
- why it was insufficient
- which candidates, if any, remain broadly possible
- the smallest useful next action

It must not silently return a top candidate, a zero-confidence guess, or an empty result with no explanation.

## 9. Separation of Reasoning Layers

The following layers have distinct ownership and may not silently substitute for one another:

```text
Photos
-> Image Readiness
-> OCR observations
-> Reference facts and provenance
-> Identification candidates
-> Condition assessment
-> Grading readiness
```

### Image Readiness

Determines technical suitability for named downstream tasks. It does not identify, attribute, grade, or value an item.

### OCR Observations

Records observable text and extraction uncertainty from a named image. It does not convert text into verified facts or reference matches.

### Reference Facts

Carry provider-specific claims, validation findings, provenance, and conflicts. They are not a merged canonical catalogue.

### Identification Candidates

Are future, explainable comparisons between explicit observations and reference records. They are not confirmations and do not alter reference data.

### Condition Assessment

Requires a separately approved model and evidence standard. It must not be inferred from candidate rank, OCR, or basic image readiness.

### Grading Readiness

Requires a separately approved decision model. It may consume condition evidence, costs, policies, and collector goals, but cannot be implemented as a side effect of identification.

## 10. Human-Control Boundaries

The collector owns:

- whether to request research or candidate generation
- which evidence to add, correct, or withhold
- whether to accept, reject, defer, or record a candidate
- which source claims to trust for their own collecting decision
- whether to pursue authentication, certification, grading, purchase, sale, or insurance actions

The system may:

- present evidence and structured alternatives
- request additional evidence
- explain uncertainty and disagreement
- preserve an explicit collector confirmation as a separately labeled collector decision in a future approved phase

The system must not silently update a collection item's identity, variety, grade, provenance, or primary source choice because a candidate was generated.

## 11. Determinism Requirements

For identical inputs, configuration, reference-provider state, and software version, the system must produce identical:

- candidate set
- ordering and tie handling
- confidence state
- evidence order
- blocker list
- recommended next-evidence request
- serialized output

Determinism requires:

- stable provider and record ordering
- normalized comparison contracts that retain raw values
- explicit, versioned scoring/rule definitions
- no hidden randomization, wall-clock effects, network data, or mutable global state
- cache keys that include all relevant evidence and provider configuration

When deterministic reproduction is impossible because a provider changed, the report must identify the provider version or source metadata that changed.

## 12. Source and Provenance Requirements

Every reference-derived fact used by a future candidate must retain:

- provider ID
- source ID and source name
- source type, edition, attribution, and licence data where supplied
- source-record ID
- raw value and normalized value
- field-level source reference when available
- validation warnings and provider errors relevant to that fact

Candidate reports must be able to trace every reference comparison back to these records. A future local, manual, open, or licensed provider may add data only through the approved provider contracts and must never erase source-specific values during aggregation.

## 13. Conflict Handling

Conflicting source claims remain visible throughout research and candidate generation.

- A conflict is evidence, not an exception to suppress.
- The engine may explain that a candidate is limited by a conflict.
- The engine may request an observation that could help the collector interpret a conflict.
- The engine must not silently choose a winner or mutate a provider record.
- A collector's future explicit decision may be recorded separately, but it cannot rewrite or hide the source disagreement.

If a conflict is material to a requested conclusion, lower confidence or return `INSUFFICIENT_EVIDENCE` rather than concealing it.

## 14. Error and Degraded-State Behavior

Every reasoning request returns a structured report, including degraded states. The GUI must never receive an uncaught exception or stack trace as the collector-facing result.

| Condition | Required behavior |
| --- | --- |
| No evidence or no explicit request | Return `INSUFFICIENT_EVIDENCE` with a clear next step. |
| Readiness engine degraded | Preserve readiness warnings and block only affected downstream conclusions. |
| OCR unavailable or malformed | Preserve the observation error; do not invent text. |
| Provider failure | Preserve provider identity and healthy-provider results. |
| Reference validation finding | Preserve severity, code, message, and source/provider identity. |
| Source conflict | Preserve every claim and explain candidate impact. |
| Candidate engine failure | Return a concise degraded report with no candidate guess. |
| Unsupported task | Return `NOT_APPLICABLE` and identify the missing approved capability. |

Degraded reports must remain serializable, exportable, and deterministic.

## 15. Test Philosophy

Tests must prove reasoning boundaries as rigorously as ranking behavior.

Required test categories for every future intelligence phase:

- deterministic identical-input outputs
- evidence provenance preservation
- raw and normalized value preservation
- conflict preservation with no winner selection
- insufficient-evidence outcomes
- missing and malformed evidence
- partial-provider and engine-failure degradation
- evidence that supports, contradicts, and cannot evaluate a candidate
- tie and near-tie handling
- no collection, provider, photo, file, or source mutation
- no hidden network access or external API dependency
- explainability completeness and stable evidence order
- boundary tests proving prohibited conclusions are not emitted
- regression tests for existing Image Readiness, provider, workspace, and GUI contracts

Synthetic fixtures must cover all candidate outcomes before any external or licensed data is considered. Tests should assert structured facts and explanations, not merely a rank number.

## 16. Explicit Out of Scope

v9.0 Phase 0 does not authorize:

- candidate-generation implementation
- fuzzy matching or image matching implementation
- OCR integration or OCR improvements
- image segmentation, advanced computer vision, machine learning, or model training
- condition assessment, grade prediction, grading readiness, authentication, or submission recommendations
- pricing, valuations, market predictions, or purchase advice
- provider configuration UI, provider discovery, source ingestion, scraping, website automation, networking, cloud APIs, or background watchers
- Charlton, Coins and Canada, Numista, commercial, licensed, proprietary, or third-party catalogue ingestion/content
- collection schema changes, collection mutation, provider mutation, file movement, or persistence redesign
- GUI redesign beyond a separately approved future intelligence surface
- source precedence, automatic conflict resolution, or automatic collector decisions

## 17. Proposed v9.0 Phase Roadmap

| Phase | Goal | Boundary |
| --- | --- | --- |
| Phase 0 | Collector Intelligence Vision | Documentation only; this document. |
| Phase 1 | Candidate evidence contracts | DTOs, states, provenance links, and validation only; no candidate generation. |
| Phase 2 | Deterministic candidate strategy | Design and synthetic rule evaluation only; no GUI, OCR, or external data. |
| Phase 3 | Candidate engine core | Deterministic, explainable candidate generation against explicit synthetic/local reference evidence. |
| Phase 4 | Workspace integration | Read-only candidate report API, lifecycle, cache, export, and degraded states. |
| Phase 5 | Candidate GUI | Read-only evidence and candidate presentation; no automatic collection mutation. |
| Phase 6 | Controlled OCR evidence adapter | Only after OCR observation contracts and evidence gates receive separate approval. |
| Later | Condition and grading-readiness research | Separate vision and evidence models; no implied approval from identification work. |

Each phase requires design review, explicit scope approval, deterministic tests, and a release gate. No phase may skip directly from photos or OCR text to an asserted identification, grade, valuation, or submission decision.

## Collector Decision Support (Long-Term Vision)

The ultimate purpose of Collector Intelligence is not merely to identify a collectible. Its purpose is to help the collector make better collecting decisions.

Potential recommendation categories include:

- Keep
- Upgrade
- Research Further
- Slab Candidate
- Trade Candidate
- Sell Candidate
- Wishlist Priority
- Watch Market

These are recommendations only. Every recommendation must be evidence-based, explain its reasoning, identify its supporting evidence, acknowledge uncertainty, and preserve collector control.

Coin Analyzer must never automatically dispose of, trade, purchase, or otherwise make decisions on behalf of the collector.

Recommendations become available only after sufficient evidence has been gathered through image assessment, reference intelligence, collection context, and any future advisor systems.

The collector always remains the final decision-maker.

## Approval Gate

No v9.0 production code may begin until this document is reviewed and approved.

The first implementation phase must demonstrate this rule before anything else:

> When evidence is insufficient, Coin Analyzer says so clearly, explains why, and asks only for the evidence that can change the result.
