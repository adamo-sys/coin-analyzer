# Sprint 12 — OCR Review-Session Persistence

## Sprint objective

Sprint 12 adds durable, versioned persistence for explicitly reviewed OCR
sessions without weakening the advisory OCR boundary established in Sprints 10
and 11.

The completed scope allows an explicitly composed desktop workflow to:

- create and save an in-progress reviewed session;
- resume a known session when its source fingerprint still matches;
- abandon and save a terminal audit state;
- complete and save a domain-validated terminal state; and
- reconstruct candidate and conflict review state through public APIs.

Persistence remains explicitly opt-in. The default desktop composition does not
create a repository, select a storage path, construct persistence controls, run
OCR, or write review-session data.

Persisted reviewed sessions remain collection-independent. Completion does not
authorize collection mutation.

## Units completed

### Unit 1A — Versioned persistence contracts

Commit:

```text
7e9a8e3 feat: add versioned OCR review persistence contracts
```

Unit 1A introduced the strict, immutable persistence envelope, lifecycle,
reconstruction DTO, stored conflict-resolution DTO, unsupported-version error,
and minimal repository Protocol.

The schema version is mandatory and explicit. It is never silently defaulted
during deserialization.

### Unit 1B — Local review-session repository

Commit:

```text
f59cf8b feat: add local OCR review session repository
```

Unit 1B implemented deterministic local storage behind the Unit 1A repository
contract. The repository root is injected by the caller and created lazily.

Writes use a same-directory temporary file, complete buffered writing, flush,
file `fsync`, and `os.replace`. Corrupt data and write failure have explicit
error types.

### Unit 1C — Persistence service

Commit:

```text
619d918 feat: add OCR review persistence service
```

Unit 1C added stateless lifecycle and repository coordination. It creates
in-progress envelopes, performs explicit saves, loads sessions, checks exact
source fingerprints, reconstructs resumable domain input, and returns immutable
completed or abandoned envelopes.

Sprint 10 remains authoritative for completion truth.

### Unit 1D — Desktop persistence coordinator

Commit:

```text
3718f1e feat: add desktop OCR review persistence integration
```

Unit 1D added a headless desktop coordinator and immutable resume state. It
bridges the persistence service to the existing review controller without
choosing storage, opening dialogs, running OCR, serializing data, or saving
automatically.

The candidate-review model also gained public, optional `reviews` and `mode`
inputs so restored decisions can be supplied without accessing private widget
state.

### Unit 1E — Desktop persistence controls

Commit:

```text
941708f feat: add desktop OCR review persistence controls
```

Unit 1E added a headless persistence-controls model and a thin, opt-in
Tkinter/ttk surface for:

- Save;
- Resume;
- Abandon and Save; and
- Complete and Save.

The model retains only explicit ephemeral draft/envelope state and the last
immutable command result. Abandon and Complete require confirmation. No
autosave, retries, timers, background persistence, session browser, listing, or
deletion behavior exists.

## Final architecture

The verified Sprint 12 flow is:

```text
immutable OCR report, field reviews, conflict resolutions, and review mode
    ↓
OCRReviewSessionEnvelope with explicit schema and lifecycle
    ↓
OCRReviewSessionPersistenceService
    ↓
injected OCRReviewSessionRepository
    ↓
LocalOCRReviewSessionRepository with atomic replacement
    ↓
DesktopOCRReviewPersistenceCoordinator
    ↓
DesktopOCRReviewPersistenceControlsModel
    ↓
explicit Save / Resume / Abandon and Save / Complete and Save commands
    ↓
DesktopOCRReviewResumeState
    ↓
public candidate-review and conflict-review model inputs
```

Responsibilities remain separated:

- Sprint 10 owns review, reconciliation, consolidation, conflict resolution,
  projection, and completion truth.
- Sprint 11 owns presentation and explicit desktop review interaction.
- Unit 1A owns the persisted envelope and reconstruction contracts.
- Unit 1B owns local storage, path safety, canonical bytes, and atomic file
  replacement.
- Unit 1C owns explicit lifecycle and repository delegation.
- Unit 1D owns headless desktop persistence coordination.
- Unit 1E owns user-triggered control state and the thin control surface.

No layer treats persistence as collection approval.

## End-to-end persistence and resume flow

### Save

1. The caller supplies an immutable reviewed-session draft or envelope.
2. If a draft is supplied, Unit 1E asks Unit 1D to create an in-progress
   envelope.
3. Unit 1E performs one explicit save through Unit 1D.
4. Unit 1C validates lifecycle truth and delegates one repository write.
5. Unit 1B writes canonical bytes to a temporary file and exposes the new
   target only with `os.replace`.
6. The controls model adopts the saved immutable envelope only after success.

A failed save preserves the prior active state. There is no retry and no hidden
lifecycle transition.

### Resume

1. The user supplies a known session ID and the current source fingerprint.
2. Unit 1E calls Unit 1D `load_for_resume`.
3. Unit 1C loads the envelope, rejects terminal sessions, and compares the
   fingerprint exactly.
4. Unit 1A reconstructs the Sprint 10 review inputs and exact conflict targets.
5. Unit 1D rebuilds controller presentation state through the public Unit 1B
   controller.
6. Unit 1E invokes the injected resume callback once.
7. The controls model adopts the resumed envelope only after the callback
   succeeds.

Resume performs no write and executes no OCR. Not-found, stale source, terminal
session, corrupt data, unsupported schema, repository access, and invalid input
remain distinguishable.

### Abandon and Save

1. An in-progress envelope must exist.
2. The user must confirm.
3. Unit 1D delegates the immutable abandoned transition to Unit 1C.
4. Unit 1E explicitly saves the returned abandoned envelope once.
5. The original envelope remains unchanged.

Declining confirmation performs no transition or write. Abandon does not delete
the session.

### Complete and Save

1. An in-progress envelope must exist.
2. The user must confirm.
3. Unit 1C asks Sprint 10 to validate completion.
4. Unit 1D returns a new completed envelope only if the final projection is
   complete.
5. Unit 1E explicitly saves the completed envelope once.

Incomplete reviews cannot complete. Completion creates no collection-ready
object and performs no collection or confirmed-observation mapping.

## Public APIs introduced

### Persistence contracts

- `CURRENT_OCR_REVIEW_SESSION_SCHEMA_VERSION`
- `UnsupportedOCRReviewSessionSchemaVersion`
- `OCRReviewSessionLifecycle`
- `OCRStoredConflictResolution`
- `OCRReviewSessionReconstruction`
- `OCRReviewSessionEnvelope`
- `OCRReviewSessionRepository`

### Local repository

- `OCRReviewSessionRepositoryError`
- `OCRReviewSessionCorruptError`
- `OCRReviewSessionWriteError`
- `LocalOCRReviewSessionRepository`

### Persistence service

- `OCRReviewSessionPersistenceServiceError`
- `OCRReviewSessionStaleSourceError`
- `OCRReviewSessionNotResumableError`
- `OCRReviewSessionPersistenceService`

### Desktop persistence coordinator

- `DesktopOCRReviewResumeState`
- `DesktopOCRReviewPersistenceCoordinator`
- `create_desktop_ocr_review_persistence_coordinator`

### Desktop persistence controls

- `DesktopOCRReviewPersistenceOperation`
- `DesktopOCRReviewPersistenceOutcome`
- `DesktopOCRReviewPersistenceErrorCategory`
- `DesktopOCRReviewSessionDraft`
- `DesktopOCRReviewPersistenceCommandResult`
- `DesktopOCRReviewPersistenceControlsDisplay`
- `DesktopOCRReviewPersistenceControlsModel`
- `DesktopOCRReviewPersistenceControls`
- `create_desktop_ocr_review_persistence_controls`

The controls model exposes:

- `set_current_state`
- `save`
- `resume`
- `abandon_and_save`
- `complete_and_save`

## Storage format and atomic-write behavior

Each session is stored as one canonical JSON document under an explicitly
injected repository root.

The filename is:

```text
sha256(session_id encoded as UTF-8).hexdigest() + ".json"
```

Raw session IDs are never interpolated into paths. Blank, overlong,
separator-bearing, traversal-like, absolute, and drive-prefixed identities are
rejected. Valid Unicode session IDs remain supported. A loaded envelope must
contain exactly the requested session ID.

Serialization reuses the Unit 1A canonical envelope representation. Equivalent
envelopes produce byte-identical bytes. Unknown fields, missing fields,
malformed nested payloads, invalid enum values, and inconsistent identities
fail closed.

The write sequence is:

1. lazily create the injected root;
2. create a temporary file in that root;
3. write all canonical bytes;
4. flush the file;
5. call file `fsync`;
6. call `os.replace` to expose the new target; and
7. attempt temporary cleanup on failed paths.

A failed first save leaves no visible target. A failed replacement preserves
the prior valid target. The repository does not claim directory-entry durability
because directory `fsync` is not implemented.

No migration or silent repair occurs. Unsupported schema versions propagate as
`UnsupportedOCRReviewSessionSchemaVersion`; malformed or inconsistent stored
content becomes `OCRReviewSessionCorruptError`.

## Lifecycle policy

The persisted lifecycle values are:

- `IN_PROGRESS`
- `COMPLETED`
- `ABANDONED`

`IN_PROGRESS` sessions may be saved, loaded, and resumed.

`COMPLETED` sessions may be saved and loaded for audit purposes but cannot be
resumed or transitioned again. Completion succeeds only when Sprint 10 reports
a complete final projection.

`ABANDONED` sessions may be saved and loaded for audit purposes but cannot be
resumed or transitioned again.

Transitions return new immutable envelopes. They do not save automatically.
Unit 1E combines each terminal transition with one explicit user-confirmed save.

Persistence before the first field review remains unsupported because the
existing `OCRReportReview` aggregate requires at least one field review.

## Source-staleness policy

The persistence layer accepts an externally generated 64-character lowercase
hexadecimal source fingerprint. Sprint 12 does not hash source files or define
fingerprint generation policy.

Resume compares the supplied current fingerprint to the stored fingerprint
exactly. A mismatch raises `OCRReviewSessionStaleSourceError`. Stale-source
failure performs no write and does not alter current desktop state.

## Default-path and opt-in safety

Sprint 12 does not:

- modify default desktop startup;
- enable OCR automatically;
- select a repository root;
- read an environment variable for storage;
- construct a global repository or controls instance;
- open candidate, conflict, or persistence dialogs automatically;
- write during construction or navigation; or
- persist transient status text.

The caller must explicitly compose the repository, persistence service, desktop
coordinator, controls model, and controls surface.

## Trust boundaries

OCR output remains advisory. Human field review remains mandatory.

Persistence records source facts and explicit human review decisions; it does
not grant authority to mutate a collection.

Grade remains excluded from OCR candidates, stored conflict resolutions,
persisted review payloads, reconstructed state, and final reviewed projection.

There is no confirmed-observation mapper. There is no collection change planner
and no collection mutation command. A completed review session is therefore not
collection-ready.

## Test coverage and latest validation

### Unit 1E authoritative regression

Command:

```text
python -m unittest discover -s . -p "test_*.py"
```

Result:

```text
2,889 total
2,866 passed
22 skipped
1 known unrelated failure
0 errors
145.229 seconds
```

No Unit 1E test failed or errored.

### Sprint 12 focused group

Covered modules:

- persistence models;
- local repository;
- persistence service;
- desktop persistence coordinator; and
- desktop persistence controls.

Result:

```text
193 passed
```

### Supporting Sprint 10/11 group

Covered modules:

- review session;
- review controller;
- candidate review;
- conflict review; and
- desktop review integration.

Result:

```text
128 passed
```

The Unit 1E focused controls module independently passed 41 tests. Its earlier
supporting validation group passed 229 tests.

Headless tests cover construction, command availability, exact delegation,
immutable transitions, confirmation, failure preservation, error categories,
candidate/conflict reconstruction, and default-path safety. Real repository
integration tests use `TemporaryDirectory`; no repository-root session files
are created.

## Known unrelated regression failure

The sole authoritative-suite failure is:

```text
test_melt_value_engine.TestApiSpotPriceProvider.test_cache_persistence
```

The test uses the relative path:

```text
data/test_silver_spot_cache.json
```

Repository-root execution can fail when the environment cannot write that path.
The test passes from a writable temporary working directory. This is unrelated
to OCR review persistence and remains separate maintenance debt.

## Known technical debt

- Persistence before the first field review is unsupported by the current
  `OCRReportReview` aggregate.
- The serialized schema has no migration framework.
- Source fingerprint generation remains external.
- Session listing, deletion, and browsing are absent.
- Repository locking and optimistic concurrency are absent.
- Stale-write detection is absent.
- Backup and rollback policy beyond atomic target replacement is absent.
- Directory-entry `fsync` is absent.
- Authentication, authorization, cloud sync, and multi-user ownership policy
  are absent.
- The persistence-controls production and test modules are large but cohesive.
- Repeated test builders and control-surface formatting may be extracted if
  future units demonstrate reuse.
- The melt-value relative cache-path weakness remains separate maintenance
  debt.

## Deferred work

- Schema migration execution and migration UI.
- Session browser, listing, deletion, and recovery discovery UI.
- Autosave, periodic save, retry queues, and background persistence.
- Source-file fingerprint generation.
- Concurrency control and stale-write protection.
- Collection-ready metadata mapping.
- Confirmed-observation mapping.
- Collection change planning and second approval.
- Collection mutation and durable collection audit.
- Authentication, authorization, and cloud synchronization.

## Sprint 12 exit-gate assessment

| Exit criterion | Assessment |
| --- | --- |
| Review sessions survive restarts through the explicit local repository | PASS |
| Persistence schema is explicit, versioned, deterministic, and strict | PASS |
| Corrupt and incompatible data fail safely and distinctly | PASS |
| Source-staleness detection is exact and explicit | PASS |
| In-progress sessions resume through public review APIs | PASS |
| Completed and abandoned sessions remain terminal | PASS |
| Save, Resume, Abandon, and Complete are explicit user commands | PASS |
| Default desktop behavior remains unchanged | PASS |
| Persistence remains explicitly opt-in | PASS |
| OCR remains advisory and human-reviewed | PASS |
| Grade remains excluded | PASS |
| No collection or confirmed-observation mutation exists | PASS |
| Sprint 12 focused validation passes | PASS |
| Supporting Sprint 10/11 validation passes | PASS |
| Full regression has no Sprint 12-related failure or error | PASS |
| Known unrelated environment debt is documented separately | PASS |

Sprint 12 is ready to close after this document is validated and committed.

## Recommended Sprint 13 starting point

```text
Sprint 13 Unit 1A — confirmed-observation contracts
```

Begin with immutable contracts and an explicit trust boundary. Do not start
with collection mutation.

The first unit should define how a completed reviewed session can be represented
as a proposed confirmed observation without granting collection authority. It
should keep grade excluded, preserve provenance, require an explicit approval
boundary, and avoid introducing a collection change planner or mutation command
until separately authorized.
