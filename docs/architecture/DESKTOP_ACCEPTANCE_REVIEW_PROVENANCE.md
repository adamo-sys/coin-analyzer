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

## Review-execution artifacts

The deterministic review-execution layer sits between prepared evidence and the
authoring plan. It has three distinct artifact types:

1. reviewer-facing packets generated for one case, reviewer, and review track;
2. machine-readable reviewer submissions and adjudications; and
3. reconciliation and progress reports derived from the execution records and
   the authoring plan.

The execution record is the source of truth for human-review activity. The
authoring plan remains the source of truth for the candidate roster and freeze
readiness. Evidence-preparation notes and source ledgers are supporting inputs;
they are not reviewer decisions and must not be interpreted as completed review
state.

Generation and validation must be deterministic: identical authoring, evidence,
assignment, and submission inputs produce byte-equivalent normalized records,
packets, and reports. Malformed, incomplete, ambiguous, or internally
inconsistent inputs fail closed and do not upgrade review or eligibility state.

Each machine-readable case record must identify `case_id` and `specimen_id` and
contain separate `ground_truth_review` and `action_review` tracks. Each track
contains its state, exactly two reviewer submissions when complete, and either a
null adjudication for exact agreement or a distinct adjudication record for
disagreement. A reviewer submission contains only:

- an opaque `reviewer_id`;
- the track-appropriate `decision`; and
- one or more stable `evidence_references`.

An adjudication record additionally contains a non-empty `rationale`. Submitted
decisions are immutable audit evidence: reconciliation or adjudication must not
overwrite either original submission.

Reviewer identifiers and evidence identifiers committed to the repository must
be opaque, sanitized tokens. They must not contain names, email addresses,
credentials, machine-local absolute paths, private collection notes, or other
personal or confidential information. A private mapping from opaque reviewer
identifiers to real people, if one is operationally required, remains outside the
repository. Evidence references must resolve to durable, permitted records and
must not expose protected local material.

## Blinded packets

A ground-truth packet must not contain the authoring plan's candidate identity,
candidate expected action, another reviewer's assignment or decision, or any
adjudication result. It may contain the case and specimen identifiers, sanitized
inventory and evidence references, the identity fields the reviewer must decide,
and review instructions. The reviewer derives country/jurisdiction,
denomination, and year from the permitted evidence rather than confirming a
supplied answer.

An expected-action packet may be generated only after ground truth for that case
has been resolved through exact reviewer agreement or completed adjudication. It
contains that independently resolved identity and the frozen v1 domain and
canonicalization references needed to decide the action. It must not contain the
authoring plan's candidate expected action, another action reviewer's assignment
or decision, or any action adjudication result.

Packet generation must reject a request that would violate these disclosure or
sequencing rules. A reviewer may receive only their own packet for the active
track through the controlled review workflow; repository access outside that
workflow is not treated as a substitute for blinding.

## Ground-truth review

Each case requires two independent reviewer records. Each reviewer must record:

- a reviewer identifier;
- a complete decision containing country/jurisdiction, denomination, and year; and
- an evidence reference sufficient to reproduce the decision.

The two reviewers must make their decisions independently. A reviewer must not copy the other reviewer's decision into their own record.

The two `reviewer_id` values within the ground-truth track must be distinct.

If both decisions agree exactly, `ground_truth_review.state` may be set to `complete` with `adjudication: null`.

If the decisions disagree, a distinct adjudicator is required. The adjudication must contain a reviewer/adjudicator identifier, the resolved identity, an evidence reference, and a rationale. The resolved identity must match the candidate identity retained in the authoring plan before readiness can pass.

For abstain cases, the known identity is still required and must be reviewed completely. Abstention is an expected system action, not an absence of ground truth.

## Expected-action review

Expected-action review is separate from identity review. Each case again requires two independent reviewer records, each with:

- a reviewer identifier;
- a decision of exactly `identify` or `abstain`; and
- an evidence reference.

The two `reviewer_id` values within the expected-action track must be distinct.
The same opaque reviewer identifier may appear once in the ground-truth track
and once in the expected-action track for the same case. Cross-track overlap does
not weaken the requirement for independence within either track, and the action
reviewer must still receive only the blinded action packet.

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

The execution record represents each provider-eligibility field as a state plus
one or more stable `evidence_references`. An `approved` state without at least one
resolvable supporting reference is invalid and must fail closed. Reconciliation
may copy the approved state into the existing authoring-plan flag only after this
linkage validates; the supporting evidence remains in the execution layer. This
contract does not change the authoring-plan schema.

## Evidence references

Evidence references must be reproducible and stable enough for later audit. Examples include repository-relative review records, inventory references, dated policy/terms review notes, or other durable evidence artifacts. Avoid ephemeral chat text as the sole evidence record.

The authoring plan stores references, not fabricated evidence. Supporting records may live in separate repository artifacts where appropriate.

Evidence references may be reused when the same durable evidence supports more
than one decision or case, but every submission and approval must declare its
own explicit linkage. Reference reuse does not imply review completion.

## Reconciliation

Reconciliation occurs only after the blinded human decisions for a track have
resolved. It compares the resolved ground-truth identity or expected action with
the corresponding candidate value in the authoring plan.

An exact match permits a proposed authoring-plan update. A mismatch is a named
reconciliation blocker and must preserve both the roster candidate and the
resolved human decision for audit. It must never silently mutate the roster,
rewrite a reviewer submission, select whichever value is convenient, or mark the
track complete in the authoring plan. Resolving such a blocker requires an
explicitly authorized roster correction or a new review cycle under the same
blindness and evidence requirements.

Progress and reconciliation reporting must be available in deterministic
machine-readable and human-readable forms across all 30 cases. Reports must
distinguish at least unassigned, awaiting submissions, disagreement awaiting
adjudication, resolved awaiting reconciliation, reconciliation blocked, and
reconciled states, together with unresolved provenance and provider-eligibility
gates. Reports are advisory views of the execution record and must not themselves
change review state.

## Repeated specimens

Cases 028, 029, and 030 remain separate case-level review records even though
they reuse the physical specimens from cases 006, 011, and 012 respectively.
Durable specimen-level identity, provenance, ownership, or authorization
evidence may be referenced by both cases. Each case must nevertheless retain its
own two ground-truth submissions, two expected-action submissions, any required
adjudications, reconciliation result, and explicit evidence linkage. Reusing
supporting evidence must not copy a peer decision or automatically complete the
repeat case.

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
