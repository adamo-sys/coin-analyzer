# Sprint 13 - Confirmed Metadata Boundary

## Sprint purpose

Sprint 13 establishes the collection-independent trust boundary between a
completed, human-reviewed OCR session and future collection operations. It
turns resolved review output into immutable confirmed observations, validates
their exact submitted values, applies only explicit canonical values, checks
the small set of implemented cross-field rules, and produces a bounded
readiness result.

Sprint 13 does not:

- map confirmed fields to collection fields;
- compare with, plan changes to, overwrite, or mutate collection records;
- persist confirmed observations;
- invoke OCR, mapping, canonicalization, or readiness automatically;
- provide a GUI or desktop integration for confirmed/readiness results; or
- claim comprehensive historical, issuer, denomination, or catalog
  correctness.

`READY` means that a set is safe under the rules implemented in Sprint 13. It
does not mean the metadata is complete, historically authoritative,
collection-mapped, approved for a collection change, or ready to mutate a
collection.

## Architecture and public pipeline

Unit 1A defines the output contracts before Unit 1B maps into them. At runtime,
the public flow is:

```text
completed Sprint 10 human review
    |
    v
Unit 1B - ConfirmedObservationMapper
    |
    v
Unit 1A - ConfirmedObservationSet / ConfirmedFieldObservation
    |
    v
Unit 1C - field validation
    |
    v
Unit 1D - canonical-value application
    |
    v
Unit 1E - compatibility validation
    |
    v
Unit 1F - readiness assessment
    |
    v
future collection-mapping boundary
```

The Unit 1F public assessor invokes Unit 1D and then Unit 1E. Unit 1D delegates
field validation to Unit 1C before constructing a new immutable set. Unit 1E
also invokes Unit 1C validation defensively at its public boundary. Unit 1F
does not invoke the Unit 1B mapper automatically.

Dependencies remain directional. The mapper alone imports the immutable Sprint
10 review-session result and its source report/review inputs. The remaining
Sprint 13 services depend only on lower Sprint 13 contracts or services.

## Units

### Unit 1A - Confirmed-observation contracts

`capture_import/workflow_confirmed_observation_models.py`

- Defines frozen, slotted provenance, field-observation, and aggregate
  contracts.
- Requires explicit schema version `1`; unsupported versions raise
  `UnsupportedConfirmedObservationSchemaVersion`.
- Preserves reviewer, source type, source linkage, exact submitted value,
  optional canonical value, rationale, and ordered provenance.
- Distinguishes submitted from canonical values without defaulting one to the
  other.
- Rejects grade and exact unresolved/deferred markers.
- Uses strict, deterministic, JSON-safe dictionary representations.

### Unit 1B - Final projection mapper

`capture_import/workflow_confirmed_observation_mapper.py`

- Accepts only complete Sprint 10 review-session results with complete final
  projections and no deferred, missing, or unresolved state.
- Groups observations deterministically by source coin and field.
- Preserves exact human-approved or corrected values as `submitted_value`.
- Reconstructs and verifies provenance against both the source OCR report and
  exact human field review.
- Rejects grade and fields outside the current OCR vocabulary.
- Fails atomically; it returns no partial tuple when any field is invalid.

### Unit 1C - Field-specific validators

`capture_import/workflow_confirmed_observation_validators.py`

- Uses an immutable exact-name registry that must match
  `ALLOWED_OCR_FIELDS`.
- Applies bounded structural and semantic checks to every current field.
- Preserves every submitted value exactly.
- Produces a canonical value only for `silver_indicator`.
- Contains no cross-field compatibility logic.

### Unit 1D - Canonical-value application

`capture_import/workflow_confirmed_observation_canonicalization.py`

- Applies only canonical values explicitly returned by Unit 1C.
- Returns new immutable field observations and sets without changing source
  objects.
- Leaves non-silver canonical values as `None`.
- Accepts a matching preexisting canonical value.
- Rejects conflicting or unverifiable preexisting canonical values.
- Performs no hidden normalization.

### Unit 1E - Compatibility validation

`capture_import/workflow_confirmed_observation_compatibility.py`

- Implements one conservative exact-name `monarch_year` rule.
- Treats inclusive accession years as compatible for either adjacent monarch.
- Returns `NOT_EVALUATED` when either field is absent or the exact monarch name
  is unknown.
- Raises for a known monarch paired with a year outside its bounded range.
- Defers weaker country, issuer, denomination, banknote, and material rules.

### Unit 1F - Readiness assessment

`capture_import/workflow_confirmed_observation_readiness.py`

- Provides a success-only `READY` assessment.
- Applies Unit 1D and then Unit 1E.
- Preserves Unit 1C, Unit 1D, and Unit 1E typed failures unchanged.
- Permits readiness when the compatibility outcome is either `COMPATIBLE` or
  `NOT_EVALUATED`.
- Returns the new canonicalized observation set plus compatibility evidence.

## Supported field vocabulary

The exact current `ALLOWED_OCR_FIELDS` vocabulary is:

```text
year
denomination
country
monarch
mintmark
series_type
banknote_prefix
certification_number
silver_indicator
variety_keyword
```

`grade` is excluded. Arbitrary future fields and aliases such as `series`,
`type`, and `variety` fail closed. Tests require the immutable Unit 1C registry
and the Sprint 9 allowlist to contain exactly the same names.

## Validation policies

Every field requires a string that is nonblank after trimming, already
NFC-normalized, within its field limit, free of Unicode control characters and
surrogate code points, and not an exact case-insensitive unresolved marker
after trimming. The current markers are `defer`, `deferred`, `missing`,
`reject`, `rejected`, and `unresolved`. Validation does not trim or otherwise
rewrite accepted submitted values.

The field-specific policies are:

| Field | Implemented policy |
| --- | --- |
| `year` | Exactly four ASCII decimal digits representing 1000 through 2999. |
| `denomination` | At most 64 characters and an exact case-insensitive match for the bounded forms: a nonzero integer through six digits plus `cent`, `cents`, `c`, `¢`, `dollar`, or `dollars`; a `$` amount in the same numeric range; `penny`, `nickel`, `dime`, `quarter`, `half dollar`, or `dollar`; or `five`, `ten`, `twenty`, `fifty`, or `one hundred` followed by `cents` or `dollars`. |
| `country` | General validated text, at most 128 characters. |
| `monarch` | General validated text, at most 128 characters. |
| `mintmark` | One 1-16 character token: an initial ASCII letter or digit followed only by ASCII letters, digits, periods, or hyphens. `none` and `no mintmark` are rejected case-insensitively. |
| `series_type` | General validated text, at most 256 characters. |
| `banknote_prefix` | 1-4 ASCII letters followed by 5-9 ASCII digits, with a total maximum of 13 characters. |
| `certification_number` | A 3-64 character ASCII alphanumeric identifier permitting internal spaces and hyphens, containing at least one digit, and not matching the bounded grade-like token pattern. |
| `silver_indicator` | At most 16 characters. Exact case-insensitive `true`, `yes`, or `silver` produces canonical `true`; `false`, `no`, or `non-silver` produces canonical `false`. Surrounding whitespace is not accepted. |
| `variety_keyword` | General validated text, at most 256 characters. |

Only `silver_indicator` currently produces a non-`None` canonical value.

## Compatibility policy

The immutable exact-name monarch ranges are:

| Monarch | Inclusive years |
| --- | --- |
| Victoria | 1837-1901 |
| Edward VII | 1901-1910 |
| George V | 1910-1936 |
| Edward VIII | 1936 |
| George VI | 1936-1952 |
| Elizabeth II | 1952-2022 |
| Charles III | 2022-2999 |

Ranges overlap intentionally at accession years: 1901, 1910, 1936, 1952, and
2022 can be compatible with either adjacent monarch. Matching is exact and
case-sensitive; aliases and normalized spellings are not inferred. A missing
`monarch` or `year`, or an unknown exact monarch, produces `NOT_EVALUATED`.
A known exact monarch with an out-of-range validated year raises
`IncompatibleConfirmedObservationError`.

## Trust guarantees and invariants

- Human-review completion precedes Unit 1B OCR mapping.
- Incomplete, deferred, missing, unresolved, or ambiguous review state cannot
  map.
- Submitted values remain exact and provenance remains attached.
- Grade never crosses the confirmed-observation boundary.
- Validation, canonicalization, compatibility, and readiness are deterministic.
- Compatibility is deliberately conservative and does not guess.
- Contracts and service outputs are immutable; source objects remain unchanged.
- Each public operation either returns its complete result or raises without a
  partial result.
- Equivalent inputs produce equivalent outputs.
- The Sprint 13 domain layer has no filesystem, environment, network, GUI,
  persistence, collection, generated-ID, or timestamp dependency.

Unit 1A also permits explicitly sourced `MANUAL_ENTRY` observations. Unit 1B's
completion requirement applies specifically to the reviewed-OCR mapping path.
Readiness validates the fields present in a nonempty confirmed set; it does not
claim that every possible metadata field is present.

## Typed error model

Unit 1B mapping uses `ConfirmedObservationMappingError` and these specific
subclasses:

- `IncompleteConfirmedObservationSourceError`
- `UnsupportedConfirmedObservationFieldError`
- `DuplicateConfirmedObservationFieldError`
- `MissingConfirmedObservationProvenanceError`
- `MalformedConfirmedObservationSourceError`

Unit 1C validation uses `ConfirmedObservationValidationError`, with
`UnsupportedConfirmedObservationFieldError` and
`InvalidConfirmedObservationValueError`. The mapper and validator modules have
distinct exception classes that currently share the unsupported-field class
name.

Unit 1D uses `ConfirmedObservationCanonicalizationError` and
`ConflictingCanonicalValueError`. Unit 1E uses
`ConfirmedObservationCompatibilityError` and
`IncompatibleConfirmedObservationError`.

Unit 1F defines no generic readiness failure. It preserves the authoritative
Unit 1C validation, Unit 1D canonical-conflict, Unit 1E incompatibility, and
ordinary contract/type errors unchanged.

## Deliberate scope exclusions

The following are intentional boundaries, not Sprint 13 defects:

- collection-field mapping, record comparison, change planning, overwrite
  policy, approval, and mutation;
- persistence of confirmed observations;
- desktop/session-browser integration and confirmed/readiness GUI;
- automatic OCR, mapper, canonicalizer, compatibility, or readiness execution;
- grade handling;
- fuzzy field names, monarch aliases, implicit canonicalization, and weak
  historical or catalog heuristics;
- external authority lookups; and
- comprehensive country, issuer, denomination, banknote, and variety
  compatibility.

## Technical debt and future decisions

- Decide whether confirmed observations require persistence and, if so, define
  repository, lifecycle, and migration behavior without coupling it to
  collection mutation.
- Define migrations before future confirmed-observation schema versions are
  accepted.
- Revisit shared ownership of the OCR field vocabulary if the Sprint 9
  allowlist and Unit 1C registry coupling becomes awkward.
- Expand canonicalization only through explicit field policies.
- Add broader issuer/country/denomination and catalog compatibility knowledge
  only with an identified authority source.
- Define monarch aliases or normalized names before accepting anything other
  than exact matches.
- Add GUI presentation and session/browser integration only through explicit
  composition boundaries.
- Keep collection mapping policy, coin-versus-banknote mapping, existing-value
  conflicts, change-plan DTOs, explicit approval, and the mutation executor in
  later collection-focused sprints.

## Recommended next sprint

The locked roadmap names the next boundary:

```text
Sprint 14 - Collection Change Planning
```

Sprint 12 already established durable persistence for reviewed OCR sessions,
so another persistence sprint need not precede collection mapping. Confirmed
observation persistence remains optional technical debt and should not block
the roadmap's next safe step: immutable collection mapping and dry-run change
planning.

A bounded Sprint 14 sequence consistent with the locked roadmap is:

1. collection mapping design and immutable mapping contracts;
2. explicit confirmed-field to collection-field mapping;
3. existing-record comparison;
4. immutable proposed-change plans;
5. blank/overwrite/conflict policy;
6. preview and a second explicit approval boundary.

The mutation executor remains a later Sprint 15 concern and must accept only an
approved plan.

## Validation record

The authoritative Unit 1F baseline at commit `3f5d922` was:

```text
3,050 total
3,028 passed
22 skipped
0 failures
0 errors
```

This baseline validates the Sprint 13 implementation. Closure-document
validation is recorded separately during the documentation pre-commit review.

The documentation closure candidate was checked with the six focused Sprint 13
test modules:

```text
161 passed
0 skipped
0 failures
0 errors
```

The full repository suite was not rerun for this documentation-only candidate.
Project governance can require that authoritative regression at the final
pre-commit gate.

## Commit inventory

```text
24a30fe feat: add confirmed observation contracts
8f1e2f1 feat: add confirmed observation mapper
0a41b34 feat: add confirmed observation validators
a88507d feat: add confirmed observation canonicalization
ed55c49 feat: add confirmed observation compatibility validation
3f5d922 feat: add confirmed observation readiness assessment
```

## Architecture closure verdict

**PASS.** The six units form a deterministic, immutable, collection-independent
trust boundary. Their dependency direction is coherent, their public failures
remain typed and fail closed, and no production or test inconsistency requires
correction during closure.
