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

### Canonical persistence layout

The authoritative persisted machine-readable `ReviewExecutionRecord` for the
v1 review workflow is:

`benchmarks/real-world-desktop-v1/reviews/execution/review-execution-v1.json`

This record is the sole persisted machine authority for human-review workflow
state, including submissions, adjudications, track completion, and provider
eligibility decisions. It may advance only through controlled, validated
workflow updates. Such an update must preserve every previously submitted
reviewer decision and adjudication as immutable audit evidence; reconciliation,
report generation, or later transcription must not rewrite that evidence.

The authoritative evidence-reference-to-resolution mapping for v1 is:

`benchmarks/real-world-desktop-v1/reviews/evidence/evidence-resolution-v1.json`

This catalog is the sole persisted machine authority for reviewed evidence
resolution state. It maps each accepted `evidence_reference` to its durable
`resolution_record` under the evidence-resolution contract. Adding or reviewing
a mapping does not change the referenced human decision, adjudication, approval,
or source evidence, and a derived report must not create, infer, or rebind a
catalog entry.

Reviewer-facing packets are persisted beneath:

`benchmarks/real-world-desktop-v1/reviews/packets/<batch-and-track-specific-directory>/`

Each leaf directory is a bounded human-review artifact set for one explicitly
identified batch and track. Packet production and controlled delivery must
preserve the active track's sequencing and blindness requirements. A packet
directory must not expose candidate answers, peer submissions, adjudication
results, or other material prohibited by the blinded-packet contract merely
because other repository artifacts exist.

The canonical derived v1 reporting artifacts are:

- progress report:
  `benchmarks/real-world-desktop-v1/reviews/reports/unit-4-progress-v1.json`;
- reconciliation handoff:
  `benchmarks/real-world-desktop-v1/reviews/reports/unit-4-reconciliation-handoff-v1.json`.

Both reports are deterministic derived views of validated authoring state, the
authoritative execution record, and the authoritative evidence-resolution
catalog. They are not sources of truth for reviewer or adjudicator decisions,
must not be edited to advance workflow state, and do not authorize authoring
mutation, freeze preparation, photography, recognition, or benchmark execution.
They may be regenerated only from their validated authoritative inputs.

Human-returned reviewer and adjudicator source evidence remains immutable and
separate from the transcribed execution record, the evidence-resolution catalog,
reviewer packets, and derived reports. Transcription preserves the source
decision; it does not replace or retroactively amend the human-returned artifact.
Any correction requires an explicit, auditable review or adjudication action
rather than alteration of the original human evidence.

The `-v1` artifact names bind these canonical locations to their compatible v1
persistence schemas. A file at one of these locations must not be silently
overwritten with an incompatible schema or meaning. Any future incompatible
persistence format requires an explicitly versioned successor filename and an
explicit architecture amendment; compatible regeneration or controlled state
advancement must continue to pass the corresponding schema validator.

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

### Evidence-resolution catalog

Sanitized reference syntax does not establish that evidence exists. Review and
provenance readiness therefore requires an explicit, immutable evidence-resolution
catalog supplied to the Unit 4 reporting layer. There is no permissive default.
The catalog has schema
`coin-analyzer-desktop-acceptance-evidence-resolution`, version `1.0.0`, and an
array of entries containing exactly:

- `evidence_reference`, the sanitized reference used by authoring or execution;
  and
- `resolution_record`, a sanitized repository-relative path to the durable
  attestation that resolves the reference.

Catalog entries must have unique `evidence_reference` values and normalize in
lexical `(evidence_reference, resolution_record)` order. Conflicting or duplicate
entries are invalid. A resolution record must be a permitted regular repository
file under one of these benchmark-owned roots:

- `benchmarks/real-world-desktop-v1/reviews/`; or
- `benchmarks/real-world-desktop-v1/evidence/`.

Resolution paths use canonical POSIX-style repository-relative spelling. Empty
or dot segments, traversal, absolute or drive-qualified paths, backslashes,
credentials, URI schemes, repository escape, symlink or reparse escape, and
protected/private locations are invalid. Validation resolves paths against an
explicit repository root rather than the process working directory. It must not
inspect protected collection material.

Each `resolution_record` has exactly one canonical repository spelling. Every
path component must exactly match the corresponding on-disk repository entry;
case-insensitive aliases and silent normalization are invalid. Windows alternate
data-stream syntax, trailing-dot or trailing-space aliases, and Windows-invalid
filename characters are prohibited even when the host filesystem would resolve
them to an existing target.

HTTPS, policy, terms, inventory, and other namespaced references resolve only
through their dated sanitized repository attestation. Readiness validation must
not contact a live URL. In particular, `inventory:` references attest to the
sanitized inventory linkage and do not expose or read private collection data.

The canonical catalog digest is lowercase SHA-256 over UTF-8 canonical JSON
containing only `schema`, `version`, and the normalized `entries`. Canonical JSON
uses sorted object keys, compact separators, ASCII escaping, and no trailing
newline. The digest field itself is not part of the hashed payload. This digest
binds the reference-to-resolution-record mapping; Git history remains the
version authority for the attestation file contents.

Unit 4 resolves only evidence that contributes to readiness:

- authoring provenance evidence;
- submissions and any adjudication for a completed ground-truth track;
- submissions and any adjudication for a completed expected-action track; and
- evidence for approved privacy, licensing, and provider authorization.

A well-formed catalog that lacks any such reference adds the stable category
blocker `ground_truth_evidence_unresolved`,
`expected_action_evidence_unresolved`, `provenance_evidence_unresolved`,
`privacy_evidence_unresolved`, `licensing_evidence_unresolved`, or
`provider_authorization_evidence_unresolved`, as applicable. Exact unresolved
references may accompany those blockers in sorted machine-readable diagnostics.
Missing resolution does not alter the underlying reviewer decision,
adjudication, approval, or evidence reference.

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

### Aggregate readiness ownership

Desktop acceptance v1 requires exactly 30 case records. The shared
`DESKTOP_ACCEPTANCE_V1_CASE_COUNT` authoring invariant is the sole numeric source
for that requirement; case identities and case-to-specimen mappings continue to
derive exclusively from validated authoring state. A Unit 4 report with any
other cardinality contains the deterministic aggregate blocker
`corpus_case_count_mismatch:expected=30:actual=N`.

Unit 4 is the sole review/provenance readiness authority. Overall readiness
requires no aggregate blockers and every supplied case to satisfy the existing
case-level review, reconciliation, provenance, eligibility, and evidence-resolution
requirements. Unit 5 must consume Unit 4 overall readiness, case blockers,
aggregate blockers, unresolved-reference diagnostics, and catalog digest
without independently counting cases or resolving evidence. Unit 5 may also
verify that its derived identity and action reconciliation records are matched;
any inconsistency with Unit 4 fails closed. A blocked diagnostic artifact remains
permitted, but it is not a successful reconciled handoff.

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
