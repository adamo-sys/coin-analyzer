# Canadian Assisted Common-Coin Identification Implementation Plan

> **For agentic workers:** This is planning only. It authorizes no product implementation, reference-image acquisition, model inference, E7 execution, collection mutation, or change to human verification/save authority.

**Goal:** Add useful, field-level Canadian common-coin suggestions to the existing phone review only after a bounded, provenance-backed Canadian benchmark proves that each enabled field is safe enough to present as a proposal.

**Architecture:** Reuse the existing provider-neutral observation, literal date/denomination extraction, candidate verification, and field-evidence concepts behind one generic `FieldProposal` projection. The projection is advisory, side-aware, and auditable; the phone service renders it separately from collector-owned fields, then preserves the collector's final values through the existing `PhoneIntake -> temporary capture package -> ReviewedCoinDraft -> persist_reviewed_coin` path.

**Tech stack:** Existing Python dataclasses/services, local JSON audit sidecar, server-rendered phone page, synthetic unittest fixtures, local reference metadata only when separately authorized.

**Planning base:** `main` / `25d7ecc11fe291c03f8236063a87d5a10e30f506` (PR #349 merged).

## Global constraints

- Recognition output is a proposal, never verified truth, a persistence command, or a confidence-derived authorization.
- `PhoneIntake`, temporary capture packages, `ReviewedCoinDraft`, server-issued HUMAN VERIFY approval, `persist_reviewed_coin`, separate CONFIRM SAVE, reconciliation, and provenance boundaries remain authoritative.
- Do not create a mobile recognizer, Canada-only recognition fork, second collection model, new verifier, cloud path, provider tournament, automatic save, grading, variety/error attribution, or self-learning system.
- Do not use the local-only `test_coins/` JPEGs, collection records, backups, or private benchmark material. The benchmark uses provenance-backed, sanitized references and synthetic tests.
- A date range, type, monarch, reverse, or catalogue row is never evidence of one specific year.

## Executive decision

The first product packet should be a **generic advisory-proposal adapter**, not Coin-CLIP and not a new Canadian classifier. The current phone slice has no recognition invocation at all: `PhoneEntryService.create_draft()` records only the pair and `PhoneEntryAuditStore.create()` writes `proposal: None`. Its HTML says “Manual entry only.” The existing recognition stack is nevertheless useful as a source of conservative, role-preserving evidence once an approved observation producer and bounded Canadian metadata are supplied.

The existing final `RecognitionGateResult` must not be inserted directly into mobile review. It deliberately produces a single `IDENTIFY`/`ABSTAIN` result only after a unique candidate has two-side support, at least a year or denomination match, textual support, and no conflict. That is an appropriate whole-identity gate, but it discards the partial-success behavior this product needs. Build a projection *below* that gate, retaining its evidence rather than weakening it.

No real-device suggestion is supportable **today**: there is no phone-to-observation adapter, no populated Canadian catalogue/reference corpus in the repository, and no validated phone benchmark. What can be reused immediately is the contract and safety plumbing: explicit front/reverse roles; literal date and denomination extractors; source/role/provenance values; conflict retention; candidate verification; canonical country/denomination comparison; and the existing audited human/save flow.

## Current-state architecture map

```text
phone obverse + reverse uploads
  -> PhoneEntryHost staging/normalization
  -> PhoneEntryService.create_draft
  -> PhoneIntake.confirm_pair
  -> PhoneEntryAuditStore { proposal: None }
  -> manual fields -> host-issued HUMAN VERIFY
  -> host-issued CONFIRM SAVE
  -> temporary capture package -> ReviewedCoinDraft
  -> persist_reviewed_coin -> guarded media + collection transaction / reconciliation

future, generic advisory branch (no persistence authority)
  validated two-side images
  -> approved observation producer
  -> GroundedVisualObservation(obverse, reverse)
  -> literal date + denomination envelopes / existing visual evidence
  -> Canadian metadata retriever (when provenanced)
  -> candidate verification and field-level proposal projection
  -> audit snapshot + separate assisted-review presentation
```

Relevant current seams:

| Current component | Verified present behavior | Planning implication |
| --- | --- | --- |
| `phone_entry_host.py`, `templates/phone_entry.html` | Captures distinct `front`/`reverse`; review POST accepts `country`, `denomination`, `year`, `type_design`; UI is manual-only. | Add a read-only proposal representation to the review GET and separate proposal copy; do not change verify/save authority. |
| `phone_entry_service.py` | Draft output has only media/human final/item ID. Audit schema has `proposal: None`, but verify currently overwrites every field change as proposal `None`. | Extend this existing path-free audit sidecar and projection; retain proposal snapshot and per-field accept/edit/ignore outcome. |
| `capture_import/date_numeral_extraction.py` | Retains literal 4-character date-like tokens, role and source; resolves only one exact reading; uncertain tokens do not resolve. | Reuse for year evidence, but require an independently defined year proposal threshold. |
| `capture_import/denomination_mark_extraction.py` | Accepts only explicit marks (unit/currency symbol); bare numerals are deliberately rejected. | Reuse as direct denomination evidence; never turn diameter/year numerals into a denomination. |
| `capture_import/evidence_fusion.py` | Has per-field `AGREED`, `VISUAL_ONLY`, `OCR_ONLY`, `CONFLICT`, `UNRESOLVED` for country/denomination/year; keeps role/provider/artifact and does no confidence arithmetic. | Reuse its evidence-value shape and conflict discipline; extend via a generic proposal contract rather than change its three-field semantics in-place. |
| `capture_import/grounded_recognition_pipeline.py` | Generic two-side evidence -> retriever -> verifier -> final all-or-nothing gate. | Keep it intact for its current contract. Add a sibling proposal projector over the same non-final artifacts. |
| `ocr_assisted_identification.py` | Produces OCR advisory candidates, including country/denomination/year/monarch/type-like text, but combines a heuristic score and is not a field-confidence contract. | It may be an input only after a phone-safe observation adapter and per-field validation; do not surface its score as confidence. |
| `canadian_reference_provider.py` | Provides provenance-aware Canadian issue/reference DTOs, filters, conflicts, and source refs; no populated catalogue is tracked. | It is the appropriate generic metadata shape, not evidence that Canada is already covered. |
| Recognition30 v2 | Current grounded baseline: 1/30 identified, 29 abstained, 0 unsafe wrong identities; correct candidate present at K=10 for 11/30. E6 lexical enrichment did not improve 11/30. | Do not use these as Canadian-phone accuracy. They support conservative abstention and show that retrieval/corpus work remains unproven. |

## Proposal contract

Introduce a provider-neutral immutable `CoinFieldProposalSet`, separate from `ReviewedCoinDraft` and `RecognitionGateResult`.

```text
CoinFieldProposalSet
  schema_version
  source_coin_id / capture-pair reference
  producer records (provider/model/retriever/version; no secrets or paths)
  fields: country, denomination, year, monarch, reverse_design, variety

FieldProposal
  field_name
  status: SUPPORTED | AMBIGUOUS | CONFLICTING | ABSTAIN
  proposed_value: string | null
  normalized_value: string | null
  evidence: tuple[EvidenceRef]       # side, source, artifact ID, raw bounded value
  reasons: tuple[stable reason code]
  scope: DIRECT_OBSERVATION | CANDIDATE_METADATA | CROSS_SIDE_AGREEMENT
  candidate_ids: tuple[str]          # optional, bounded, never an acceptance
```

`SUPPORTED` means that field alone meets its stated evidence rule; it does **not** mean the coin identity is verified. `AMBIGUOUS` preserves more than one compatible candidate/value without selection. `CONFLICTING` preserves incompatible direct/candidate evidence and selects no value. `ABSTAIN` is the normal no-evidence/insufficient-evidence outcome. All non-supported states have `proposed_value = null`.

Field rules:

- **Country/issuer:** direct issuer legend/canonical alias or a uniquely supported candidate; country metadata alone may not override conflicting observed text.
- **Denomination:** explicit mark plus canonical jurisdiction mapping, or a uniquely supported candidate. A bare numeral, size, or date is not denomination evidence.
- **Year:** only a directly observed, exact four-digit numeral retained by the date extractor and compatible with candidate evidence. A future OCR producer may contribute only by emitting the same role/source-bearing, exact-numeral evidence accepted by that extractor; it is not an alternate year path. A type range, monarch range, or design era cannot provide a year.
- **Monarch/obverse:** direct obverse legend/portrait evidence plus a uniquely matching, provenance-backed metadata label. It is not inferred from an unresolved year range.
- **Reverse design/type:** direct reverse evidence plus uniquely matching type/design metadata. If the reverse is unusual or a commemorative cannot be uniquely matched, emit `AMBIGUOUS`/`ABSTAIN`, never the common reverse.
- **Variety/subtype:** disabled in Phase 1A. The field remains `ABSTAIN` unless a later corpus defines direct, provenance-backed distinguishing evidence and a separate scope approves it.

Scores remain source-specific diagnostics, never probability confidence. The proposal surface exposes status, short reason, and evidence origin; detailed raw evidence is an expandable local review panel.

## Two-side evidence and year safety

Each `EvidenceRef` must include `image_role` (`obverse` or `reverse`). The projection takes observations as a pair; it does not concatenate independent answers.

| Evidence condition | Field behavior |
| --- | --- |
| Same normalized evidence from both sides, or one side directly supports the expected field and the other supplies compatible independent candidate evidence | `SUPPORTED` if the field's rule is met. |
| One side supplies sufficient evidence and the other side is silent | May be `SUPPORTED` only for the individual field; the field evidence states `one_side_supported`. It never becomes a whole-coin acceptance. |
| Direct sides disagree, or direct evidence conflicts with candidate metadata | `CONFLICTING`, no selected value, preserve both evidence trails. |
| Multiple candidates/designs remain compatible | `AMBIGUOUS`, no selected type/value. |
| No defensible direct/candidate evidence | `ABSTAIN`, no selected value. |

Year has an additional invariant: `FieldProposal(year, SUPPORTED)` requires `DateNumeralExtraction.resolved_value`, no exact date conflict, and at least one retained evidence reference naming the observed numeral. A catalogue's `year_range`, coin type, monarch, reverse, or source row may only constrain/reject candidates; none can populate `proposed_value`. One exact numeral conflicting with metadata is `CONFLICTING`, not a correction. Uncertain numerals (`?`) and multiple exact years abstain/conflict according to the extractor; they never get “repaired.”

## Canadian proving corpus

Phase 1A is a metadata-and-benchmark coverage target, not a claim of current repository support. Build the corpus as provenance-backed issue/type records with immutable source references, denomination, exact issue years/ranges, obverse/monarch label, reverse/design label, composition transition where materially identity-relevant, and a disposition for standard versus commemorative reverse. Use the Royal Canadian Mint's denomination timelines as the primary circulation reference, supplemented by authoritative catalogue/reference records only where the Mint timeline lacks a needed distinction.

The broad boundary is intentionally small:

| Monarch/period | Included families, only where issued | Explicit exclusions / handling |
| --- | --- | --- |
| Elizabeth II, modern circulation | 1c, 5c, 10c, 25c, $1, $2. The $1 coin starts in 1987 and $2 in 1996; penny production ended in 2012. | Do not fabricate $1/$2 before their issue dates or a post-2012 QEII penny. Commemoratives are corpus rows, not aliases for a common design. |
| Charles III, modern circulation | 5c, 10c, 25c, $1, $2 beginning with the documented 2023 Charles III circulation set. | No Charles III penny. Add a denomination/year only when an authoritative issue record exists. |
| George VI, Phase 1B | 1c, 5c, 10c, 25c; records will define exact issue/design/composition boundaries. | No inherited “modern” assumptions; no varieties/errors/grades. |
| George V, Phase 1B | 1c, 5c, 10c, 25c; records will define exact issue/design/composition boundaries. | Same generic contract and metadata schema; no Canada-specific recognition branch. |

The Mint documents the end of penny production in May 2012, the loonie's 1987 introduction, the toonie's 1996 introduction, and the Charles III obverse from 2023. Its denomination pages also explicitly show many alternate reverse designs. These facts justify boundaries, not field suggestions without capture evidence. Sources: [Royal Canadian Mint circulation index](https://www.mint.ca/en/discover/canadian-circulation), [1-cent timeline](https://www.mint.ca/en/discover/canadian-circulation/1-cent), [1-dollar timeline](https://www.mint.ca/en/discover/canadian-circulation/1-dollar), and [2-dollar timeline](https://www.mint.ca/en/discover/canadian-circulation/2-dollars).

Phase 1B is therefore a corpus-extension packet, not an architectural one: add source-reviewed rows and benchmark cases for George VI/V, including material type transitions and changed legends/reverses only when they affect recognition. Stop if authoritative evidence cannot resolve an issue boundary or licensing/provenance does not permit local reference metadata.

The current `CatalogueCandidate.year` is an exact string and its verifier compares exact normalized years. A corpus issue range must therefore be adapted before that verifier: either materialize only provenance-backed exact-year candidate rows for the requested observed year, or apply bounded range containment as **candidate filtering** before construction. A range never enters the candidate's `year` field and never becomes a proposed year.

## Benchmark and enablement gate

Create a new sanitized, versioned `canadian_common_coin_phase1a` benchmark. It must not alter Recognition30, reuse its frozen truth as Canadian ground truth, or use private/local phone images in CI. Each case carries record-level source provenance and field-level expected states/values. A real evaluation requires a separately authorized, provenance-backed and sanitized **query-capture** set (ideally two independent phone captures per eligible issue); it is not authorized by this planning task and is distinct from E7's independent reference-gallery acquisition. Until that set exists, run only synthetic proposal-contract tests and keep real-phone suggestions disabled.

Minimum representative suite: at least two standard cases for each applicable family/monarch combination; at least one real, provenance-backed alternate/commemorative reverse for each family where obtainable; targeted similar-denomination cases; obscured/partial-date cases; reversed/mislabelled side cases; disagreement cases; a foreign/out-of-corpus coin; and a Canadian in-range denomination with an unsupported design. All six QEII families are represented; Charles III represents 5c/10c/25c/$1/$2, never 1c.

Score independently by field:

- precision and coverage for country, denomination, year, monarch, and enabled reverse design;
- correct abstention/ambiguity/conflict routing, including unknown/out-of-corpus and commemoratives;
- false supported proposal count, with a separate zero-tolerance count for false year and false standard-design overwrite;
- role coverage and obverse/reverse conflict preservation; and
- human-review outcomes: accepted, edited, ignored, and manually completed after abstention.

Enable a field in the real phone UI only when its predeclared benchmark threshold is met on an independent holdout with provenance-backed truth. The minimum safety gate is **zero false `SUPPORTED` years**, **zero false `SUPPORTED` reverse designs that overwrite/label a documented alternate design as standard**, and **zero loss of conflict evidence**. Country/denomination/monarch thresholds, holdout size, and coverage floor must be owner-approved before implementation; do not invent a statistically impressive number from a tiny corpus. Any failure, unreviewed truth, unsupported case, provider/model change, schema change, or loss of evidence routes that field to hidden/`ABSTAIN` and blocks enablement.

## Mobile assisted-review UX

The review page remains an editable human form. Above it, render a clearly labeled “Coin Analyzer suggestions — not verified” section. A supported value can be copied into the corresponding input only through an explicit per-field **Use suggestion** action; default inputs remain blank until that action. This avoids a machine proposal looking like a verified collector value.

- `SUPPORTED`: show value, concise evidence source/side, and **Use suggestion** / **Edit manually**.
- `AMBIGUOUS`: show “More evidence needed” and the bounded alternatives; do not prefill.
- `CONFLICTING`: show “Evidence conflicts; enter after review,” never a selected value.
- `ABSTAIN`: show “No suggestion; enter manually.”
- HUMAN VERIFY serializes only the four current human final fields. It records, for every field, proposal snapshot + disposition `accepted`, `edited`, `ignored`, or `manual_after_abstention`; it does not promote a proposal.
- CONFIRM SAVE remains a second host-issued action and persists only the existing `ReviewedCoinDraft` fields. Proposal/audit data remains a local sidecar and cannot alter the collection item's authority.

## Strict implementation packets

1. **Proposal contract and projection (generic, no phone UI):** define immutable field proposal/evidence models, adapter from existing literal/fused/candidate artifacts, status rules, year invariant, bounded serialization, and synthetic tests. Preserve `RecognitionGateResult` unchanged.
2. **Phone proposal seam and audit:** add a dependency-injected, optional proposal producer to `PhoneEntryService`; extend safe reopen/audit projection and field-change provenance. Provider failure/absence returns all abstentions and manual entry continues. No model call is introduced by this packet.
3. **Assisted-review UI:** render separate proposal rows and explicit per-field use/edit/ignore handling; test that a proposal cannot verify or save and that manual-only/recovery paths are unchanged.
4. **Canadian Phase 1A metadata and benchmark contract:** acquire no images. Curate authoritative local metadata only with source/provenance review; build synthetic benchmark fixtures/case manifests and predeclare gates. Validate historical combinations before rows enter the corpus. This packet cannot enable the UI.
5. **Authorized capture evaluation and selective enablement:** only after a new task authorizes a sanitized, provenance-backed query-capture set, qualify the lowest-risk existing local observation/OCR capability against the Canadian field-level gate. It is not reference-gallery acquisition. If it does not pass, keep suggestions disabled and retain manual phone entry.
6. **Phase 1B corpus extension:** add George VI/V metadata and tests under the same contract. No architectural fork.

## Coin-CLIP/reference-corpus decision

**PARKED, not needed now.** E7 metadata preflight is closed/parked at 30 total cases, 27 auto-resolved and 3 review-required. Recognition30 v2's current grounded benchmark has only 1/30 final identifications and an 11/30 correct-candidate @10 diagnostic; it does not demonstrate a production-ready retrieval path. E6 lexical enrichment was a 0/30 improvement. Do not resume E7 or acquire reference images merely to make Phase 1A look complete.

Coin-CLIP/reference imagery earns reactivation only after packets 1–5 produce retained Canadian benchmark evidence showing that (a) a qualified local observation producer can obtain useful direct country/denomination/date evidence, (b) the remaining material failures are candidate-recall/design-disambiguation failures rather than OCR/metadata/projection failures, and (c) a frozen, independent, licensed, leakage-audited reference gallery can be specified. Then reopen it as a new bounded experiment against a stated Canadian retrieval endpoint; it still does not authorize production deployment.

## NOW / NEXT / LATER / ARCHIVE

| Status | Work |
| --- | --- |
| NOW | Plan approval; generic proposal contract; year-safety tests; phone audit/projection seam; manual-first UI contract. |
| NEXT | Provenance-backed Phase 1A metadata and field-level benchmark; qualify existing local observation/OCR source; enable only passed fields. |
| LATER | George VI/V corpus extension; alternate design coverage expansion; retrieval experiment if the stated failure evidence demands it. |
| ARCHIVE for this initiative | Broad world coins, Edward VII/Victoria expansion, provider tournaments, cloud recognition, model fine-tuning, reference-image acquisition, E7 execution, grading, errors/varieties, automatic persistence, autonomous learning. |

## Risks and stop conditions

- Stop if the frozen durable-persistence architecture would need amendment; an advisory projection must remain outside collection authority.
- Stop if a Canadian issue/type boundary lacks authoritative provenance, a source licence is incompatible, or benchmark truth is unresolved. Omit the row rather than invent it.
- Stop enablement on any false supported year, false standard-design overwrite, missing side/provenance record, conflict-selection bug, or benchmark gate failure.
- Stop and return to manual entry on provider absence/failure, malformed evidence, unsupported corpus coverage, or any ambiguity; do not retry persistence or widen scope.
- Do not treat Recognition30 evidence, an OCR heuristic score, a type range, or a demo capture as field-confidence or product acceptance evidence.

## Review focus

- A valid known type with no directly observed date must produce `year = ABSTAIN`, never a type-range year.
- A commemorative reverse sharing a denomination with a common reverse must not receive the common design as `SUPPORTED`.
- Contradictory obverse/reverse values must preserve both side references and select neither.
- A proposal producer exception or absence must leave every manual field usable and must not change VERIFY/SAVE transition authority.
- An accepted suggestion edited before HUMAN VERIFY must retain proposal, edit, and human-final provenance without leaking paths, device details, tokens, or raw provider payloads.

---

## Planning evidence and self-review

Inspected implementation: `phone_entry_host.py`, `phone_entry_service.py`, `templates/phone_entry.html`, `capture_import/reviewed_coin_collection_entry.py`, `capture_import/date_numeral_extraction.py`, `capture_import/denomination_mark_extraction.py`, `capture_import/numeral_evidence_envelope.py`, `capture_import/evidence_fusion.py`, `capture_import/grounded_recognition_pipeline.py`, `capture_import/two_side_candidate_verification.py`, `capture_import/recognition_decision_gate.py`, `capture_import/catalogue_retrieval.py`, `ocr_assisted_identification.py`, and `canadian_reference_provider.py`, plus their focused tests and Recognition30 closeouts.

Self-review: the packets preserve the existing final gate and no-save-before-human boundaries; every requested field, two-side behavior, year rule, Phase 1A/1B boundary, benchmark gate, UX, E7 decision, ordering, risk, stop, and non-goal has a named section. No historical denomination × monarch matrix is claimed without record-level source review.
