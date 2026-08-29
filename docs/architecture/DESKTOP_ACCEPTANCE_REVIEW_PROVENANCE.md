# Desktop Acceptance Review and Provenance Protocol

This protocol governs the pre-photography review phase for the real-world desktop acceptance v1 corpus. It is intentionally fail-closed: no review, provenance, privacy, licensing, or provider-authorization state is upgraded unless the corresponding evidence actually exists.

## Scope

The merged specimen roster fixes corpus composition. This phase does **not** authorize recognition, benchmark execution, threshold tuning, or production changes. It resolves only:

1. ground-truth identity review;
2. expected-action review;
3. provenance evidence;
4. privacy approval;
5. licensing approval; and
6. provider authorization.

Official benchmark photography begins only after the roster and the review/authorization plan are stable.

## Ground-truth review

Each case requires two independent reviewer records. Each reviewer must record:

- a reviewer identifier;
- a complete decision containing country/jurisdiction, denomination, and year; and
- an evidence reference sufficient to reproduce the decision.

The two reviewers must make their decisions independently. A reviewer must not copy the other reviewer's decision into their own record.

If both decisions agree exactly, `ground_truth_review.state` may be set to `complete` with `adjudication: null`.

If the decisions disagree, a distinct adjudicator is required. The adjudication must contain a reviewer/adjudicator identifier, the resolved identity, an evidence reference, and a rationale. The resolved identity must match the candidate identity retained in the authoring plan before readiness can pass.

For abstain cases, the known identity is still required and must be reviewed completely. Abstention is an expected system action, not an absence of ground truth.

## Expected-action review

Expected-action review is separate from identity review. Each case again requires two independent reviewer records, each with:

- a reviewer identifier;
- a decision of exactly `identify` or `abstain`; and
- an evidence reference.

The decision must be based on the v1 domain boundary, not on perceived image difficulty, expected model performance, rarity, or a desire to improve benchmark scores.

The current intended domain boundary is:

- standard Canadian circulation coinage: `identify`;
- Newfoundland issues outside the v1 Canada canonical identify jurisdiction: `abstain`;
- historical Province of Canada / token material outside standard Canadian circulation coinage: `abstain`; and
- foreign coinage: `abstain`.

Any disagreement requires a distinct adjudicator with evidence and rationale. The resolved action must match `expected_action` in the authoring plan before readiness can pass.

## Provenance

Every case must retain a non-empty `ownership_or_source` and `evidence_reference`. For the current roster, the physical specimens are user-owned and the inventory references identify the source specimens.

Provenance evidence should be sufficient to answer:

- where the physical specimen came from;
- who owns or controls the specimen and resulting photographs;
- whether the image capture is original to this benchmark; and
- whether any third-party material is incorporated.

Do not replace provenance evidence with assumptions or inferred ownership.

## Provider eligibility

Provider eligibility is evaluated independently across three fields:

### Privacy

Set `privacy` to `approved` only when the planned image contains no disallowed personal or confidential information and the evidence supporting that conclusion is recorded outside the state flag itself.

### Licensing

Set `licensing` to `approved` only when the benchmark has the right to use the planned image bytes for the intended evaluation. Original photographs of user-owned physical specimens are the preferred path because they minimize third-party licensing ambiguity.

### Provider authorization

Set `provider_authorization` to `approved` only after confirming that the intended provider may receive the planned benchmark images under the applicable account, product, and data-use terms. Provider authorization must not be inferred merely because an API call is technically possible.

A rejected or unresolved field remains a readiness blocker.

## Evidence references

Evidence references must be reproducible and stable enough for later audit. Examples include repository-relative review records, inventory references, dated policy/terms review notes, or other durable evidence artifacts. Avoid ephemeral chat text as the sole evidence record.

The authoring plan stores references, not fabricated evidence. Supporting records may live in separate repository artifacts where appropriate.

## Review sequence

For each case:

1. Reviewer A independently determines ground truth and records evidence.
2. Reviewer B independently determines ground truth and records evidence.
3. If needed, a distinct adjudicator resolves disagreement.
4. Reviewer A independently determines expected action under the v1 domain boundary.
5. Reviewer B independently determines expected action under the same boundary.
6. If needed, a distinct adjudicator resolves disagreement.
7. Provenance evidence is confirmed.
8. Privacy, licensing, and provider authorization are each reviewed and recorded.
9. Only then may the corresponding authoring-plan fields be changed from unresolved to complete/approved.

## Independence and anti-leakage

Do not run recognition on candidate benchmark coins or photographs to help decide ground truth or expected action. Do not use model output as review evidence. Ground truth and expected action must be established before the frozen benchmark is executed.

Reviewers may use authoritative numismatic references and the physical specimens themselves. Any reference used to resolve a case should be cited in the evidence record.

## Completion gate

This phase is complete only when all 30 cases have:

- completed ground-truth review;
- completed expected-action review;
- confirmed provenance evidence; and
- approved privacy, licensing, and provider authorization.

Completion of this phase still does not make the corpus ready for freeze. Photography, capture metadata, repeated-capture difference declarations, and near-duplicate review must subsequently be completed before `ready_for_freeze` can become true.
