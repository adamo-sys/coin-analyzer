# Canadian Phase 1A offline contract foundation

This directory defines supplemental issue/design metadata and an offline,
recorded-outcome benchmark. It contains **no real metadata corpus, query captures,
images, or independently validated holdout truth**. Every value in
`synthetic-contract-fixtures.json`, including its sources, review identities,
timestamps, source hashes, issue labels, truth, and proposal outcomes, is generated
synthetic test data. A synthetic `VERIFIED`/`APPROVED` value exercises a contract
branch; it is not a real independent review.

This contract grants **no whole-identity ACCEPT, HUMAN VERIFY, save, collection
mutation, or suggestion enablement authority**. `SUPPORTED` refers only to one
recorded advisory field. Existing CanadianIssue, desktop canonicalization,
production proposal projection, recognition gates, persistence, and human/save
safeguards remain authoritative and unchanged. There is no production import or
UI integration. No provider, capture, acquisition, image download, or real-world
evaluation is performed by this module.

## Files and API

`metadata.schema.json` and `benchmark.schema.json` are strict Draft 2020-12 JSON
schemas with closed objects. The benchmark schema also defines recorded outcomes
at `#/$defs/outcomes`. All versions are exact, fail-closed constants:

- `ca-phase1a-metadata-v1`, `ca-phase1a-benchmark-v1`, `ca-phase1a-outcomes-v1`;
- `ca-phase1a-policy-v1`;
- `ca-phase1a-normalization-v1`.

The standalone standard-library module
`capture_import/canadian_phase1a_contract.py` exposes:

```python
validate_metadata(metadata)                  # Readiness(valid, ready, diagnostics)
validate_benchmark(metadata, benchmark)      # Readiness(valid, ready, diagnostics)
score_recorded_outcomes(metadata, benchmark, outcomes)  # ScoreReport
normalize_document(value)
canonical_digest(value)
benchmark_digest(benchmark)
```

Only the two fixed local schema files are read. Their URI identifiers are never
fetched. The internal validator implements the assertions used in these bundled
schemas, not arbitrary JSON Schema; unknown assertion keywords/references fail
closed. Cross-record, date, review, coverage, leakage, and evidence semantics are
enforced by the Python validator in addition to the JSON schemas. Call the Python
API for readiness; passing a structural JSON-schema check alone is insufficient.

## Metadata declarations

Metadata carries explicit denomination, monarch, inclusive issue date range,
obverse design, reverse design, standard/alternate/unresolved disposition,
unsupported status, record review, and field-level source references. Phase 1A
denominations are `1c`, `5c`, `10c`, `25c`, `$1`, `$2`; monarchs are
`ELIZABETH_II` and `CHARLES_III`. Varieties remain disabled.

Conservative historical exclusions follow the existing approved planning
boundary: no $1 before 1987, $2 before 1996, Elizabeth II penny after 2012,
Charles III before 2023, or Charles III penny. Elizabeth II ranges are bounded
to 1953–2023. These are rejection constraints, **not provenance establishing an
issued combination**. Unsupported combinations can be recorded only with
`unsupported: true`; they cannot satisfy covered declarations or design support.
An unresolved design must also be explicitly unsupported.

Each source declares an immutable content hash, edition, locator, licence,
attribution, retrieval timestamp, local metadata permission, and independent
review. Each issue references the source record and location for denomination,
monarch, years, both designs, and disposition. Missing/unresolved licensing,
provenance, or independent review blocks readiness. Source and issue IDs must be
unique. Approved review requires distinct author/reviewer IDs and a valid UTC
timestamp/reference. Source retrieval timestamps must also be valid UTC dates.

Coverage is declared with interval, family, disposition, state (`COVERED`, `GAP`,
`EXCLUDED`), referenced issue IDs, and rationale. Covered intervals must be backed
by the union of compatible supported issue ranges, with no holes; supported
issue rows must appear in a covered declaration. Ranges only constrain metadata,
never populate a proposed year. Readiness is scoped to declared coverage; it does
not prove the entire Canadian Phase 1A family matrix is populated. Owner review
must assess corpus completeness before real evaluation.

The validator checks declared source/review information; it cannot authenticate
the source bytes, verify licence terms, confirm that named reviewers are real, or
establish historical truth. Those remain separately authorized human provenance
and licensing review prerequisites. Synthetic provenance cannot qualify as real
metadata or truth, including when only the root classification is changed.

## Benchmark, freeze, and split integrity

Every case names sanitized relative input reference/hash, privacy classification,
coin group, capture group, split, issue alternatives, design disposition, and
field expectations. Input references are never opened. Absolute, network, drive,
backslash, traversal, and encoded references are rejected. Private/uncertain
material is outside this contract. The splits are `REFERENCE`, `DEVELOPMENT`,
`HOLDOUT`; only holdout cases are scored. Sharing an input hash/reference, coin
group, or capture group across splits blocks evaluation readiness.

Field truth is independently reviewed separately from producer output, with
field-level source references and `VERIFIED`/`UNVERIFIED` state. Unverified or
unreviewed truth is unscorable and blocks readiness. Non-supported expected
states select no truth value; reviewed null values establish routing expectations
only. Contradictory expected support fails closed. Expected conflict cases must
retain at least two identified evidence records.

The manifest freezes normalized metadata SHA-256, policy SHA-256 (including
owner-reviewed thresholds), immutable producer reference, and manifest SHA-256.
`benchmark_digest` omits only `freeze.manifest_sha256` to avoid self-reference.
Recorded outcomes must bind to the same manifest and producer; the returned
`outcomes_sha256` identifies their exact normalized snapshot. A changed metadata,
policy, producer, case, expectation, input identity, or version requires a new
reviewed freeze. Missing/mismatched hashes block readiness. Hashes bind declared
content, not the authenticity of external evidence.

Normalization uses NFC, trimmed/collapsed whitespace, sorted object keys, and
arrays ordered by canonical JSON. Arrays are unordered declaration sets;
duplicates are **retained** and duplicate semantic IDs rejected. Numeric, date,
or identity aliases are never repaired. Existing canonicalization is not called
or changed. Diagnostics and field results have deterministic ordering, and the
returned normalized recorded snapshot retains every submitted evidence record.

## Recorded-outcome scoring and safety

Executions are distinct: `SUCCESS`, `MALFORMED_OUTPUT`, `RUNTIME_FAILURE`,
`UNATTEMPTED`. A missing recorded case is unattempted. Only a successful field
can report `ABSTAIN`; runtime or malformed output is never credited as abstention.
Unknown/duplicate cases, fields, authority properties, versions, or malformed
output fail closed. Other field states are `SUPPORTED`, `AMBIGUOUS`, `CONFLICTING`.
All non-supported fields select `null`.

Year support requires exact ASCII four-digit direct evidence with at least one
resolved side; every retained direct date must agree, including records whose
side is unresolved (`NONE`). Metadata-only years, uncertain/partial
dates, direct ranges, and conflicting direct or metadata dates cannot count as
correct `SUPPORTED` years. Candidate metadata ranges constrain/reject only.
Monarch/reverse-design support requires a unique compatible supported issue plus
matching direct evidence on `OBVERSE`/`REVERSE`, respectively. Unresolved
alternatives, wrong-side evidence, and contradictory retained labels block
support; an alternate design cannot be overwritten by a standard label. Country
and denomination scoring requires matching side-bearing direct evidence and
compatibility with selected Canadian issue metadata; this conservative offline
contract does not reproduce production candidate-verification authority.

For eligible reviewed field truth:

- precision = correct supported / recorded supported;
- coverage = correct supported / eligible reviewed field cases;
- routing accuracy = correctly routed / eligible reviewed field cases;
- abstentions count only successful, explicit field abstentions.

Zero denominators yield `None`, never a passing score. Eligible routing truth
includes independently reviewed abstention/ambiguity/conflict expectations, so
coverage counts those cases in its denominator. Unverified truth produces no
true/false accuracy label; unsupported evidence still produces safety diagnostics.
Safety counts are separate: false supported years, false support on known
alternate-design cases, and loss of required conflict evidence. Conflict
retention compares the whole evidence record, including ID, side, origin, value;
an ID alone cannot hide a changed or missing observation.

Policies predeclare per-field minimum truth, supported count, precision, and
coverage, with independent owner review. There are no invented real-data
thresholds in this foundation. Gates also require zero false support and correct
routing of every eligible case. Overall evaluation success requires real
readiness, all declared field gates, no error diagnostics, and zero safety
violations. Every successful field must retain all required evidence, irrespective
of its state label. Missing evidence on expected ambiguity/conflict routes is also
counted when execution fails or is unattempted. The conservative
`conflict_evidence_loss` counter therefore includes loss of any mandatory evidence
on successful fields; missing records prevent correct support/routing credit.
Synthetic diagnostic scores can exercise these formulas but
`evaluation_pass` always remains false. No probability confidence is reported.

## Validation and next prerequisites

Run focused synthetic tests:

```powershell
C:/Projects/coin-analyzer/.venv/Scripts/python.exe -m unittest tests.test_canadian_phase1a_contract
```

Relevant unchanged checks cover reference provider core/local/conflicts,
canonical identity, generic field proposals, date and denomination extraction.
Bounded Ruff/Pyright apply to the two new Python files. This foundation does not
rerun Bake-Off, T9/T10, Visual Shelf, challenger evaluations, or existing frozen
benchmarks, and does not change CI or dependencies.

Real-data blockers remain: owner-authorized authoritative metadata curation and
licensing/source review; complete family/alternate coverage; separately authorized
sanitized query captures; independently reviewed per-field holdout truth and
split isolation; owner-approved thresholds and immutable producer/freeze identity.
Real evaluation and any selective UI enablement need later explicit authority.
