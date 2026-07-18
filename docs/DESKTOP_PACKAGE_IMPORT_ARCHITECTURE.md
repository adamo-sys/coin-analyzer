# Desktop Capture Package Import Architecture

## Status

Design contract only. The desktop `.ca-package` importer is not implemented by
this document. Production code, collection-schema changes, dependencies, and UI
changes require a separate approved implementation phase.

Companion contracts:

- [Desktop Capture Package Import Test Plan](DESKTOP_PACKAGE_IMPORT_TEST_PLAN.md)
- [Desktop Capture Package Import Threat Model](DESKTOP_PACKAGE_IMPORT_THREAT_MODEL.md)

## Mission

Import a version `1.0` Coin Analyzer Mobile Companion capture package into the
authoritative desktop collection without trusting the archive, mutating anything
in the collection/import domain before confirmation, or leaving collection
records and image ownership in an ambiguous state. The immutable package
snapshot is the only pre-confirmation temporary-state exception.

```text
.ca-package
  -> bounded digest capture
  -> immutable package snapshot
  -> bounded archive inspection of snapshot
  -> strict manifest and media validation
  -> immutable preview and duplicate review
  --------------------------------------------
  no collection, journal, managed image, or audit state changed yet
  temporary immutable package snapshot only
  --------------------------------------------
  -> explicit collector decisions
  -> durable import journal
  -> import-owned image directory
  -> one atomic collection JSON replacement
  -> completed audit record
```

The initial importer supports only **Skip** and **Import as new**. It never
merges, replaces, overwrites, or silently deduplicates collection records.

## Existing Constraints

The supported desktop application is `CoinCollectionGUI` in
`coin_collection_gui.py`. The authoritative collection model and persistence
boundary are `CoinItem`, `ItemPhoto`, `PhotoRole`, and `CoinCollection` in
`coin_collection.py`.

The collection is a JSON list at `data/collection.json`. A complete save uses
`atomic_json.write_json_atomically()`, which writes and flushes a same-directory
temporary file before `os.replace()`. This provides atomic replacement of one
JSON document, not a transaction spanning collection data, image files, or an
audit store.

Current photo workflows reference files in place. `PhotoVault` indexes metadata
but does not own files, and Photo Inbox deliberately does not copy or move files.
Imported package media therefore needs a new, explicit ownership boundary.

`LegacyPortfolioImporter` is the closest existing preview pattern: it parses an
external workbook into reviewable staged DTOs, reports duplicates and skipped
rows, and does not save the collection. The package preview follows that pattern
without reusing workbook-specific models.

## Architectural Principles

1. Treat every package as untrusted, including packages apparently created by
   the official mobile app.
2. Keep selection, validation, preview, and conflict resolution read-only with
   respect to collection records, managed images, journals, and audit history.
   The bounded immutable package snapshot is the sole temporary-state exception.
3. Separate parsing and validation from collection mutation.
4. Reuse authoritative `CoinItem` acquisition normalization and photo roles.
5. Generate desktop IDs and managed paths; never promote package names to local
   identities or filesystem paths.
6. Perform one collection save for the complete selected batch.
7. Make every filesystem mutation import-owned and compensatable.
8. Persist enough journal state to recover after process or machine failure.
9. Preserve provenance without retaining absolute source or temporary paths.
10. Keep importer business rules outside `coin_collection_gui.py`.

## Supported Package Contract

The initial reader accepts only the contract documented by the Mobile Companion
`CAPTURE_PACKAGE_SPEC.md`:

```text
extension:       .ca-package
container:       ZIP
manifest:        capture_package.json
schema:          coin-analyzer.capture-package
package_version: 1.0
media:           image/jpeg (.jpg), image/png (.png)
```

Format `1.0` requires front and reverse photographs for every coin; edge is
optional. `path` is the authoritative archive entry. `original_name` is display
metadata only and is never used for extraction or managed naming.

Unknown additive fields may be ignored only after the known format `1.0`
structure has passed validation. Unknown schema or package versions fail closed.

The normative desktop v0.2 ceilings are: 256 MiB package, 256 archive entries,
100 coins, three media records per coin, 1 MiB manifest, 40 MiB per compressed
entry, 40 MiB per uncompressed media entry, 256 MiB aggregate declared
uncompressed bytes, 100:1 per-entry and aggregate compression ratio, 12,000
pixels on either image axis, and 80,000,000 decoded pixels per image. These may
change only through a reviewed versioned policy update.

Manifest structure is additionally limited to eight nesting levels, 64 keys per
object, 16,384 Unicode code points per string, and 262,144 aggregate string code
points. Integers may not exceed the exact signed 53-bit range; quantity is
limited to 1 through 1,000,000. Decimal source strings are plain, non-negative,
non-exponent notation and at most 64 characters before exact `Decimal` parsing.

v0.2 preserves validated JPEG/PNG bytes exactly, generates a matching `.jpg` or
`.png` owned filename, and rejects animated, multi-frame, or other formats.
Ordinary ZIP directory entries are permitted only as required parents of
referenced files. Every unexpected directory tree and unreferenced
non-directory entry is rejected. Zero-coin packages return `EMPTY_PACKAGE`.

## Proposed Module Boundary

The implementation should use one focused package-import module or a small
package of modules. Exact file splitting may be chosen during implementation,
but the public responsibilities below must remain distinct.

### `CapturePackageArchiveReader`

**Responsibility:** Open the selected file only for bounded size/digest capture.
After snapshot acceptance, expose bounded ZIP metadata and entry streams from
the immutable package snapshot without extracting the archive.

**Input:** Selected local path for bounded digest capture, then the accepted
immutable package snapshot descriptor for ZIP access.

**Output:** An immutable archive view containing the package basename, digest,
central-directory records, and bounded entry readers.

**Dependencies:** Python standard-library `zipfile`, `hashlib`, and path tools.

**Mutation:** None.

**Test seam:** In-memory and temporary ZIP files; injectable limits.

**Status:** New abstraction.

### `CapturePackageSnapshotService`

**Responsibility:** Create one bounded, application-owned immutable package
snapshot at
`data/imports/snapshots/<snapshot-token>/package.ca-package`. The service
exclusively creates the token directory, `snapshot-owner.json`, lease file, and
package file. The owner record contains `snapshot_schema_version`, hostname,
process ID, creation time, and cryptographically random snapshot token. The
service holds a platform advisory exclusive lease for the snapshot lifetime,
streams the source through a bounded buffer, computes the snapshot SHA-256 while
copying, and accepts it only when that digest equals the validation digest.

All manifest parsing, media validation, preview construction, and commit-time
image copying use the accepted snapshot. The original source package is never
reopened during commit. A snapshot is temporary application state rather than a
collection mutation: creating it must not create collection records, managed
collection images, or audit history.

**Input:** Selected local path, validation digest, configured 256 MiB limit, and
an application-generated snapshot name.

**Output:** Immutable snapshot descriptor containing its private relative path,
SHA-256, and byte length.

**Mutation:** Creates only the exclusive temporary snapshot directory and its
ownership/lease files. Cancellation, validation failure, successful rollback,
and successful import remove the exact directory after obtaining its lease and
verifying the owner record. Only an active journal may persist its relative
path; terminal audit records and user-facing output must not retain it.

Before import is enabled, `cleanup_orphaned_snapshots()` enumerates only direct
children of the snapshot root. It skips any snapshot whose advisory lease cannot
be acquired, delegates journal-referenced snapshots to import recovery, and
deletes an unjournaled snapshot only after its regular-file owner record, token,
matching hostname, non-live owner PID, advisory lease acquisition, root
containment, and absence of links/reparse points are proven together. PID status
alone is insufficient. Corrupt or unprovable snapshot ownership returns
`SNAPSHOT_RECOVERY_REQUIRED`, preserves evidence, and blocks new imports.
Repeated cleanup is idempotent.

**Failure:** A source/snapshot digest mismatch or later snapshot integrity change
returns `PACKAGE_CHANGED` and creates no preview or import mutation.

**Test seam:** Injected snapshot root, bounded reader, exclusive-create failure,
copy interruption, digest mutation, and cleanup failure.

**Status:** New abstraction.

### `CapturePackageBoundaryValidator`

**Responsibility:** Enforce container, entry, path, collision, compression, size,
manifest-count, and regular-file rules before manifest or media interpretation.

**Input:** Archive view.

**Output:** Validated archive index or categorized validation failures.

**Dependencies:** No GUI or collection dependency.

**Mutation:** None.

**Test seam:** Synthetic central-directory records and hostile ZIP fixtures.

**Status:** New abstraction. Backup ZIP verification is not sufficiently strict
for this boundary and must not be used as the validator.

### `CapturePackageManifestParser`

**Responsibility:** Strict UTF-8 and JSON parsing, duplicate-key rejection,
schema/version checking, type and cardinality checks, date and decimal parsing,
and creation of immutable package DTOs.

**Input:** Bounded manifest bytes.

**Output:** `CapturePackageManifest`, `CaptureSessionManifest`,
`CaptureCoinManifest`, and `CapturePhotoManifest` values.

**Dependencies:** Reuse the semantics of `parse_optional_money()`,
`normalize_acquisition_date()`, and `normalize_purchase_currency()` without
accepting the looser defaults of `CoinItem.from_dict()`.

**Mutation:** None.

**Test seam:** JSON strings and deterministic clocks only where required.

**Status:** New abstraction.

### `CapturePackageMediaValidator`

**Responsibility:** Confirm that every referenced entry exists exactly once and
that declared path, MIME type, byte length, dimensions, extension, magic bytes,
and decoded image agree. Enforce compressed, decoded-byte, and pixel limits.

**Input:** Validated archive index and photo manifests.

**Output:** Immutable validated-media descriptors including SHA-256 digests.

**Dependencies:** Pillow is already a core dependency. Validation must use
bounded streams and explicit decompression-bomb handling.

**Mutation:** None during preview.

**Test seam:** Generated JPEG/PNG bytes and corrupt or oversized fixtures.

**Status:** New abstraction.

### `PackageImportPreviewBuilder`

**Responsibility:** Map compatible manifest facts to proposed desktop values,
allocate no persistent resources, identify unmapped fields, and build a
deterministically ordered immutable preview.

**Input:** Validated manifest/media descriptors, immutable package snapshot
descriptor, and read-only collection bytes captured with their exact baseline.

**Output:** `PackageImportPreview` containing proposed records, warnings,
duplicate evidence, package provenance, display-safe media information, the
snapshot digest/byte length, and `CollectionBaseline` digest-or-sentinel plus
byte length.

**Dependencies:** `CoinItem`, acquisition normalizers, `PhotoRole`, and the
duplicate service.

**Mutation:** None. It must not call `CoinCollection.add_item()` or save files.

**Test seam:** Plain DTOs and collection fixtures.

**Status:** New abstraction following the `LegacyPortfolioImporter` preview
pattern.

### `PackageDuplicateDetectionService`

**Responsibility:** Produce explained duplicate signals without making the
collector's decision.

**Input:** Proposed records, existing `CoinItem` values, validated media hashes,
and completed import-audit records.

**Output:** Ordered `DuplicateCandidate` records with category, confidence,
matched desktop IDs, and human-readable reasons.

**Dependencies:** Existing normalization ideas from `LegacyPortfolioImporter`,
`CollectionIntelligenceEngine`, and `CoinCollection.find_matching_coins()`.

**Mutation:** None.

**Test seam:** Injected item and audit snapshots.

**Status:** New service; it must not change existing intelligence engines merely
to route package import through them.

### `ImportDecisionModel`

**Responsibility:** Record one explicit decision per proposed coin.

**Input:** Immutable preview and collector selections.

**Output:** Validated ordered decisions: `SKIP` or `IMPORT_AS_NEW`.

**Mutation:** In-memory only.

**Test seam:** Plain enum/DTO validation.

**Status:** New.

### `ManagedCollectionImageStore`

**Responsibility:** Generate desktop-owned relative paths, copy selected media
through bounded streams, verify copied bytes, and remove only paths owned by a
specified import.

**Input:** Import ID, generated desktop item IDs, photo roles, and bounded archive
streams.

**Output:** `ItemPhoto` values using stable managed paths and an ownership
inventory for recovery.

**Dependencies:** Filesystem and media validator. It does not depend on Tk.

**Mutation:** Begins only after confirmation.

**Test seam:** Injected root directory and copy/finalization failure hooks.

**Status:** New. `PhotoVault` remains a metadata/reporting abstraction and is not
repurposed as the physical store.

### `PackageImportLock`

**Responsibility:** Serialize every desktop collection writer, mutable
package-import operation, and package-import recovery operation with one
exclusive filesystem lock at `data/imports/package_import.lock`.

The lock file is created with `O_CREAT | O_EXCL`-equivalent semantics, an OS
advisory exclusive lock is held on its handle, its metadata is flushed and
`fsync`ed before mutation begins, and its handle remains owned by the caller for
the operation. It contains
`schema_version`, `process_id`, `hostname`, `created_at`, `random_lock_token`, and
`import_id` when known. `random_lock_token` is cryptographically random and must
match before the owner releases the lock. Acquisition is non-blocking or uses a
short bounded wait; contention returns sanitized `IMPORT_LOCKED`.

Release rereads the bounded lock metadata, requires the current process's
in-memory token and identity to match, releases/closes its advisory-locked
handle, and immediately deletes only that exact regular lock file. A crash in
that release window leaves a conservative stale file rather than permitting a
second writer. PID liveness alone never authorizes deletion. v0.2 never
automatically clears a pre-existing lock it did not create.

The supported deliberate stale-lock procedure requires all of the following:
the user has closed every Coin Analyzer instance; the lock is the exact regular
file under `data/imports/` with no link/reparse traversal; its bounded schema and
hostname are valid; its PID is not live; a recovery process can acquire the same
OS advisory exclusive lock; and the user explicitly confirms recovery. The
recovery process then exclusively renames the file to a token-qualified
quarantine name before deletion. Failure of any condition preserves the lock,
returns `RECOVERY_REQUIRED`, and blocks imports. PID status alone is never proof.

Preview and validation do not acquire this lock. The coordinator acquires it
before creating a journal, import-owned root, or managed image, and holds it
until collection replacement and compensation finish and the journal reaches a
terminal or recovery-required phase. `PackageImportRecoveryService` uses the
same lock. OneDrive or file-sharing errors are commit failures; callers do not
blindly retry replacement or overwrite.

**Test seam:** Injected lock path, clock, hostname, process-liveness evidence,
token generator, contention, and release failures.

Every `CoinCollection.save_collection()` path must acquire this same lock, or
receive an already-held verified lease from the transaction service, before
writing. The package transaction passes its existing lease to the new internal
batch-save primitive so it does not reacquire the non-reentrant lock. This is a
coordination safeguard, not a change to CRUD data semantics.

**Status:** New abstraction used by `CoinCollection`,
`PackageImportCoordinator`, and recovery.

### `PackageImportJournalRepository`

**Responsibility:** Atomically persist active import phase, generated IDs,
package digest, managed relative paths, selected decisions, and recovery status.

**Input/output:** One validated JSON object per import at
`data/imports/journals/<import-id>.json`. Required fields are:

```text
journal_schema_version
import_id
random_ownership_token
phase
created_at
updated_at
package_sha256
package_version
package_basename
snapshot_relative_path
snapshot_byte_length
collection_baseline_sha256_or_sentinel
collection_baseline_byte_length
selected_source_coin_ids
desktop_item_ids
import_root_relative_path
created_relative_paths
expected_relative_paths
committed_collection_item_ids
proposed_count
imported_count
skipped_count
error_category
recovery_attempt_count
cleanup_pending
audit_finalization_pending
terminal_audit
```

The immutable identity fields after `PREPARED` are `import_id`,
`random_ownership_token`, package digest/version/basename, collection baseline,
selected source IDs, desktop item IDs, import root, and expected paths.
`snapshot_relative_path` is required while active and is atomically set to JSON
`null` after successful snapshot cleanup before terminal audit retention.
`terminal_audit` is required and JSON `null` in every nonterminal phase. It
becomes the complete validated audit DTO in `SUCCEEDED`, `ROLLED_BACK`, or
`CANCELLED`; `RECOVERY_REQUIRED` and `ROLLBACK_FAILED` retain recovery evidence
and are not exposed as completed audit history. Every write validates the
complete schema and allowed transition, then uses atomic JSON replacement.
Illegal transitions and conflicting import-ID reuse fail closed.

Same-phase writes are permitted only for phase-owned progress: adding a proven
created path during `COPYING_IMAGES`; setting committed IDs and pending flags in
their documented phases; incrementing recovery attempts and sanitized errors
during recovery; and changing `cleanup_pending` from true to false in
`SUCCEEDED`. A terminal audit DTO and immutable identity fields never change.

Schema types are normative: versions, IDs, tokens, phase, timestamps, digests,
basename, relative paths, baseline sentinel/digest, and error category are
bounded UTF-8 strings; ID/path fields that may be unavailable are JSON `null`;
ID and path collections are arrays of unique bounded strings; counts, byte
lengths, and `recovery_attempt_count` are non-negative JSON integers; and pending
flags are JSON booleans. Timestamps are UTC RFC 3339 strings. Digests are lowercase
64-character SHA-256 hex. Managed and snapshot paths use POSIX `/`, are relative
to their configured roots, and are validated before every use. Unknown journal
fields or schema versions fail closed; defaults are never inferred during
recovery.

**Dependencies:** `atomic_json.write_json_atomically()`.

**Mutation:** Atomic JSON replacement in a dedicated local app-state file.

**Test seam:** Injected path, clock, and ID provider.

**Status:** New.

### `PackageImportAuditRepository`

**Responsibility:** Expose terminal import history and idempotency evidence.

In v0.2 each per-import journal file is the authoritative versioned record.
Nonterminal phases support recovery; after terminal transition the same file is
the sanitized audit/history and duplicate-detection record. v0.2 does not split
active and terminal storage.

**Status:** New. The generic runtime `audit_summaries` list is not authoritative
enough for this purpose.

### `PackageImportRecoveryService`

**Public entry point:**
`PackageImportRecoveryService.reconcile_pending_imports()`.

**Responsibility:** Run before package import is enabled; enumerate only regular
`<import-id>.json` files beneath `data/imports/journals/`; validate their schema;
acquire `PackageImportLock` before mutation; reload `collection.json`; reconcile
reserved desktop IDs and the single verified import-owned root; update the
journal atomically; and release the lock only after a terminal or
recovery-required result.

After acquiring the lock, the entry point first invokes
`CapturePackageSnapshotService.cleanup_orphaned_snapshots()`. An active advisory
lease is skipped safely; a journal-referenced snapshot is handled with that
journal; and any unprovable orphan blocks import as
`SNAPSHOT_RECOVERY_REQUIRED`. Journal reconciliation begins only after this
snapshot pass is safe.

Journal paths that are absolute, traverse, escape a configured root, or cross a
symlink, junction, mount point, or reparse point are never followed. Corrupt
journals, uncertain ownership, ambiguous collection state, repeated cleanup
failure, and interrupted reconciliation preserve all evidence, return
`RECOVERY_REQUIRED`, and block new imports. Repeated reconciliation is
idempotent.

**Test seam:** Injected roots, collection path, lock, journal repository,
filesystem classifier, and crash/failure points.

**Status:** New startup service.

### `PackageImportTransactionService`

**Responsibility:** Convert approved preview records to new `CoinItem` objects,
create import-owned images, and perform exactly one collection JSON replacement.
It owns compensation and never performs merge or update behavior in v0.2.

**Input:** Current collection baseline, immutable preview, validated decisions,
and active journal record.

**Output:** Structured import result or categorized failure with recovery state.

**Dependencies:** `CoinCollection`, managed image store, and journal repository.

**Mutation:** Yes, within the explicit commit phase only.

**Test seam:** Injected collection, storage root, journal, ID provider, clock, and
failure points.

**Status:** New. Repeated calls to `CoinCollection.add_item()` are prohibited.

### `PackageImportCoordinator`

**Responsibility:** Own the state machine, worker execution, cancellation,
progress events, validation-to-commit handoff, and startup recovery.

**Dependencies:** All services through constructor injection.

**Mutation:** Delegated; the coordinator does not write collection or image files
itself.

**Test seam:** Fake services and synchronous executor.

**Status:** New application service.

## Data Mapping Contract

| Mobile format `1.0` | Desktop v0.2 behavior |
| --- | --- |
| `coin.id` | Preserve in audit mapping; generate a new desktop ID |
| `position` | Preserve proposal/import ordering |
| `country` | Map to `CoinItem.country` after validation |
| `denomination` | Map to `CoinItem.denomination` after validation |
| `year` | Map to `CoinItem.year` after validation |
| `mint` | Display as unmapped; do not overload `reference` without approval |
| `purchase_price` | Parse as exact `Decimal` and map to `purchase_price` |
| `purchase_currency` | Normalize and map to `purchase_currency` |
| `seller` | Map to `purchase_source`, labelled clearly in preview |
| `purchase_date` | Map to `acquisition_date` |
| `notes` | Map to `notes` |
| `quantity` | Preserve as one `CoinItem.quantity` value for v0.2 |
| `composition` | Display and retain in audit; no `CoinItem` field currently exists |
| `is_bullion` | Display and retain in audit; no `CoinItem` field currently exists |
| `asw_troy_ounces` | Display and retain in audit; no `CoinItem` field currently exists |
| `front` | Managed `ItemPhoto` with role `FRONT`; primary by default |
| `reverse` | Managed `ItemPhoto` with role `BACK` |
| `edge` | Managed `ItemPhoto` with role `EDGE` |
| mobile timestamps | Retain in audit; set desktop `date_added` to commit time |
| session metadata | Retain in import audit, not in `CoinItem` free text |

Preserving quantity as one record matches the package contract and the existing
`CoinItem.quantity` model. It intentionally differs from the legacy CSV import,
which expands quantity into multiple records. That CSV behavior remains
unchanged.

Grade, reference/variety, Numista number, certification, valuation, OCR, and AI
results remain blank or absent because format `1.0` does not supply them.

## Duplicate Policy

Signals are evidence, not automatic actions.

| Confidence | Signals |
| --- | --- |
| Exact | Completed audit with the same package SHA-256; same active journal IDs during recovery |
| High | Same producer/session/mobile coin ID with identical front and reverse hashes; both photo hashes match one existing imported record |
| Medium | Normalized country, denomination, year, and compatible acquisition details |
| Weak | Country/denomination/year alone; price, seller, date, notes, or one image alone |

The default for an exact package replay is Skip. The collector may explicitly
choose Import as new after seeing the warning. No record is merged or replaced.

## Image Ownership and Naming

Imported images become desktop-owned and remain usable after the package is
deleted. The normative v0.2 root is:

```text
coin_photos/
  collection/
    imports/
      <import-id>/
        <desktop-item-id>/
          front.jpg
          reverse.jpg
          edge.jpg
```

All path components are generated by the desktop. The package's `path` selects a
validated archive entry but does not provide any local path component.
`original_name` is never used for storage.

Import IDs and desktop item IDs are cryptographically random UUIDs or an
equivalent collision-resistant representation. The import root, each item
directory, and every fixed role file (`front.jpg`, `reverse.jpg`, or `edge.jpg`)
must be created exclusively. Any pre-existing destination returns
`MANAGED_PATH_COLLISION`; no path is overwritten, reused, or merged. A retry
allocates a fresh import ID unless it is reconciling the exact journaled import.

Immediately after exclusive import-root creation, the image store exclusively
creates `.import-owner.json` inside that root containing only
`ownership_schema_version`, `import_id`, and `random_ownership_token`. Its
relative path is predeclared in `expected_relative_paths` and then recorded in
`created_relative_paths`. Recovery may treat the directory as owned only when
the validated journal and marker match and containment/link checks pass.

Root containment and absence of symlinks, junctions, mount points, and reparse
points are checked before every create and delete. Cleanup is idempotent, never
follows links, and may act only on the single verified import-owned root. Partial
image sets are removed during pre-commit rollback. Every intended path is in
`expected_relative_paths` before creation; every successful exclusive creation
is added atomically to `created_relative_paths` before the next mutable step.

The import directory is the single physical ownership and rollback unit. v0.2
does not share files between records or deduplicate physical storage by content
hash. Hashes are retained for integrity and duplicate evidence only.

Removing an item through existing desktop behavior continues to remove only the
reference. Automated managed-image deletion is out of scope until ownership,
shared-reference, backup, and retention rules are designed together.

## Collection Baseline and Concurrency

The immutable preview stores a `CollectionBaseline` composed of the SHA-256 of
the exact `data/collection.json` bytes and their byte length. If the file does
not exist, the digest field uses the normative sentinel
`MISSING_COLLECTION_V1` and byte length zero. The baseline never hashes parsed,
normalized, or reserialized objects.

Immediately before the first import mutation, the coordinator acquires
`PackageImportLock`, discards stale in-memory assumptions, reloads
`collection.json` from disk, hashes its exact bytes, and compares both digest and
length with the preview baseline. A mismatch returns `COLLECTION_CHANGED`,
releases the lock without creating a journal or image root, and requires a fresh
preview and duplicate analysis.

This rule applies equally to external edits, another application instance,
another successful import, OneDrive synchronization, and stale GUI state. Only
one collection writer, package-import commit, or recovery operation may hold the
shared lock. Other Coin Analyzer instances therefore coordinate through the same
file. Atomic replacement protects a single write, not non-cooperating external
writers; immediately before `os.replace`, the transaction service rechecks the
locked baseline and fails closed on every change already visible then.

An external editor or OneDrive process that ignores the lock can still race in
the final interval between that check and replacement. v0.2 cannot provide an
operating-system-independent compare-and-swap for a JSON file, so the contracts
must not claim this race is eliminated. The importer minimizes the interval,
verifies the committed bytes after replacement, and documents that collectors
must not externally edit or synchronize `collection.json` during import. A
replace/share failure returns `COLLECTION_COMMIT_FAILED` without blind retry.

## Immutable Package Snapshot

Validation computes the source SHA-256 and copies the package into an
exclusive, bounded snapshot beneath `data/imports/snapshots/`. The snapshot
digest is computed during copying and must equal the source validation digest
before the preview is accepted. The 256 MiB package limit is enforced while
streaming even when file metadata is inaccurate.

All parsing, validation, preview, and copying use that snapshot. Commit never
reopens the original package. The snapshot is rehashed before the mutable commit
phase; mismatch returns `PACKAGE_CHANGED`. Its private relative path may appear
only in an active journal and is removed on cancellation, invalidation, success,
successful rollback, or later idempotent startup cleanup.

## Commit Protocol Decision

### Alternatives considered

**Move to final paths, then save collection.** Collection save failure leaves
orphaned managed images, but the collection never references missing files.
Compensation removes the import-owned directory.

**Save collection, then move staged images.** This has only a staging directory
before collection commit, but a move failure after JSON replacement leaves
authoritative records referencing missing paths. Recovery would need another
collection rewrite or delayed image finalization while the collection is
temporarily inconsistent.

**Selected: copy into stable import-owned paths, then save once, then finalize
ownership logically.** The import directory is created before the collection
save and its names are already the paths that `CoinItem` will reference. There
is no post-save image move. Before collection commit the directory is pending
according to the journal; after commit it is owned. Save failure has one cleanup
target, and successful collection records never depend on a later filesystem
rename.

### Required sequence

1. Stream the selected source for bounded size/digest capture while computing
   its SHA-256; do not parse its manifest or media directly.
2. Exclusively create the bounded immutable package snapshot, require matching SHA-256,
   and perform all parsing, media validation, and immutable preview from it.
3. Collect and validate Skip/Import-as-new decisions.
4. Acquire `PackageImportLock`; do not wait indefinitely.
5. Rehash the snapshot and recheck the exact-byte collection baseline under the
   lock. On mismatch, release the lock and require a fresh preview.
6. Generate the import ID, desktop item IDs, stable relative paths, and random
   ownership token; reject every collision.
7. Atomically write a `PREPARED` journal containing all expected paths and IDs.
8. Transition to `COPYING_IMAGES`; exclusively create the import root, item
   directories, and role files, journalling each creation before the next
   mutable operation.
9. Verify copied byte lengths, SHA-256 values, formats, dimensions, and decodes;
   transition to `FILES_READY`.
10. Reload the collection under the lock, construct and serialize the complete
    prospective list, and transition to `COMMITTING_COLLECTION`.
11. Recheck the exact-byte baseline immediately before atomically replacing
    `data/collection.json` once.
12. Transition to `COLLECTION_COMMITTED` with
    `audit_finalization_pending = true`.
13. While retaining the lock, verify snapshot ownership and remove the immutable
    package snapshot. Failure preserves the committed collection and images and
    transitions to `RECOVERY_REQUIRED`; it does not report terminal success.
14. Atomically set the snapshot path to JSON `null`, populate `terminal_audit`,
    clear `audit_finalization_pending`, set `cleanup_pending = true`, and
    transition to `SUCCEEDED`.
15. Remove only other fixed, non-sensitive scratch resources; a failure here may
    retain `SUCCEEDED` with `cleanup_pending = true` because no snapshot/source
    path is needed in audit history. On success, clear the flag with the only
    permitted same-phase terminal update. Keep the managed import directory.
16. Release the lock and refresh the GUI from the committed collection.

The implementation may need a new batch replacement method on `CoinCollection`
or an injected serialization seam. It must preserve current rollback behavior and
must not expose a general unsafe replacement API to GUI code.

## Compensation and Crash Recovery

| Observed state | Recovery action |
| --- | --- |
| `PREPARED`; no owned paths; IDs absent | Transition through `ROLLING_BACK` to `ROLLED_BACK` |
| `COPYING_IMAGES`; partial verified root; IDs absent | Remove only that root idempotently, then `ROLLED_BACK` |
| `FILES_READY`; complete root; IDs absent | Remove only that root, then `ROLLED_BACK` |
| `COMMITTING_COLLECTION`; IDs absent | Treat as uncommitted, compensate, then `ROLLED_BACK` |
| `COMMITTING_COLLECTION`; all reserved IDs and files present | Transition to `COLLECTION_COMMITTED`, clean the proven snapshot, finalize audit, then `SUCCEEDED` |
| `COLLECTION_COMMITTED`; all reserved IDs and files present | Preserve collection/images, clean the proven snapshot, finalize audit, then `SUCCEEDED` |
| IDs present; any expected file missing | Preserve evidence, set `ROLLBACK_FAILED`, and block new imports |
| Collection save returned failure | Restore the in-memory disk baseline, compensate, then `ROLLED_BACK` |
| Audit update failed after collection commit | Preserve collection and images in `COLLECTION_COMMITTED` or `RECOVERY_REQUIRED`; reconcile before exposing terminal history |
| Snapshot cleanup failed after collection commit | Preserve collection, images, snapshot, and active journal; set `RECOVERY_REQUIRED` and block imports |
| Fixed non-sensitive scratch cleanup failed after success | Keep success, set `cleanup_pending`, and retry cleanup idempotently without retaining a snapshot path |
| Corrupt journal, uncertain ownership, escaping path, ambiguous collection, or interrupted recovery | Preserve all evidence, report `RECOVERY_REQUIRED`, and block new imports |

Recovery may delete only generated paths recorded in the journal and confirmed
to remain under the configured managed image root. It rejects symlink, junction,
mount-point, reparse-point, and root-escaping targets. It never deletes a source
package, pre-existing collector photo, or directory it does not own.

Startup calls `PackageImportRecoveryService.reconcile_pending_imports()` before
enabling the importer. Recovery acquires the same import lock, increments
`recovery_attempt_count`, operates only on validated journal files and the exact
verified import root, and writes each result atomically. Repeating recovery after
any interruption produces the same terminal state or preserves
`RECOVERY_REQUIRED`; it never duplicates records or broadens cleanup.

## State Machine

The durable journal accepts only these phases:

```text
PREPARED
  -> COPYING_IMAGES | ROLLING_BACK
COPYING_IMAGES
  -> FILES_READY | ROLLING_BACK
FILES_READY
  -> COMMITTING_COLLECTION | ROLLING_BACK
COMMITTING_COLLECTION
  -> COLLECTION_COMMITTED
  -> ROLLING_BACK only when reserved collection IDs are absent
COLLECTION_COMMITTED
  -> SUCCEEDED | RECOVERY_REQUIRED
ROLLING_BACK
  -> ROLLED_BACK | CANCELLED | RECOVERY_REQUIRED | ROLLBACK_FAILED
Any nonterminal phase
  -> RECOVERY_REQUIRED when safe reconciliation cannot be proved
  -> ROLLBACK_FAILED when verified owned cleanup was required but failed
RECOVERY_REQUIRED
  -> ROLLING_BACK when reserved IDs are absent and ownership is proven
  -> COLLECTION_COMMITTED when all reserved IDs and files are present
ROLLBACK_FAILED
  -> ROLLING_BACK when ownership is proven and cleanup is retried
```

`SUCCEEDED`, `ROLLED_BACK`, `CANCELLED`, `RECOVERY_REQUIRED`, and
`ROLLBACK_FAILED` are terminal for ordinary coordinator commands. The explicit
recovery transitions above are the only outgoing transitions from
`RECOVERY_REQUIRED` or `ROLLBACK_FAILED`. No other transition is legal or
silently coerced.

Allowed retry behavior:

- Invalid returns to selecting.
- Read-only validation may retry only after selection or source fingerprint
  change.
- Rolled-back and cancelled imports may retry only with a fresh import ID,
  snapshot, collection baseline, and duplicate analysis.
- Recovery-required and rollback-failed block retry until deliberate
  reconciliation succeeds.
- Succeeded identical packages reopen as an exact replay warning.

Cancellation is disabled once the atomic collection commit begins. A worker may
observe cooperative cancellation during validation or copying, but a late worker
result cannot mutate after the coordinator has invalidated its request ID.

## UI Integration

Add the future entry point beside the existing collection CSV import:

```text
File -> Import Capture Package...
```

Use one modal `Toplevel` wizard with:

1. package selection;
2. validation progress;
3. package/session summary;
4. coin table and photo gallery;
5. unmapped-field and duplicate warnings;
6. per-record Skip/Import-as-new controls;
7. confirmation counts;
8. commit progress and final result.

Heavy ZIP hashing and image decoding run on a worker. Tk updates use the existing
`queue.Queue` plus `after()` polling pattern. The coordinator, not the dialog,
owns request IDs and state transitions.

Keyboard focus, labelled actions, copyable error text, scrollable tables, and
non-color-only status indicators are required. Closing the preview before commit
changes nothing.

## Audit and Privacy

Terminal audit records are retained indefinitely in v0.2 under
`data/imports/journals/` unless a future supported maintenance feature removes
them. The per-import root always retains the journal core schema; its required
`terminal_audit` member is JSON `null` while active and contains the following
DTO only after a valid terminal transition:

```text
audit_schema_version
import_id
started_at
completed_at
package_filename_basename
package_sha256
schema
package_version
created_by
created_with
exported_at
session_id
session_name
session_description
session_date
session_created_at
session_updated_at
coin_provenance[]:
  source_coin_id
  desktop_item_id when imported
  decision: IMPORT_AS_NEW or SKIP
  source_position
  mint
  composition
  is_bullion
  actual_silver_weight_oz
  source_created_at
  source_updated_at
  source_quantity
  image_role_hashes
managed relative image paths and hashes for imported records
proposed/imported/skipped counts
phase and final status
sanitized error category
```

These fields are provenance only. They are not inserted into `notes`,
`reference`, `grade`, or any unrelated `CoinItem` field. A skipped record may be
compacted to the source coin ID, decision, source position, and duplicate
evidence needed to explain the decision rather than retaining all optional
facts.

The `terminal_audit` DTO is a versioned JSON object. IDs, enum values, timestamps, hashes,
schema/writer values, bounded text, and relative paths are strings or JSON
`null` only where the mobile field is nullable. Counts, positions, and source
quantity are non-negative integers, with quantity at least one. `is_bullion` is
a JSON boolean. ASW remains its validated plain-decimal source string rather than
a binary float. `coin_provenance` is an ordered array keyed uniquely by
`source_coin_id`; `image_role_hashes` is an object whose only keys are `front`,
`reverse`, and optional `edge`, with lowercase SHA-256 values. Unknown audit
schema versions fail closed for replay/recovery decisions.

It does not contain absolute package paths, temporary paths, picker-supplied
source filenames, raw exception strings, credentials, or a complete duplicate
copy of the manifest. Successful records never retain snapshot paths.

The normative v0.2 storage locations are:

```text
import lock:              data/imports/package_import.lock
active/terminal journals: data/imports/journals/<import-id>.json
temporary snapshots:     data/imports/snapshots/<generated-name>.ca-package
managed imported images: coin_photos/collection/imports/<import-id>/
```

Terminal rolled-back or cancelled journals may be compacted into sanitized
audit records only after cleanup succeeds; the compacted file retains the same
schema and immutable identity, uses empty created paths, and sets the snapshot
path to JSON `null`. `RECOVERY_REQUIRED` and
`ROLLBACK_FAILED` journals are never deleted automatically. Imported images are
not covered by application backup until an explicit backup change is approved;
the user guide must not claim otherwise.

## Version and Repository Preconditions

Architecture work may proceed independently of release numbering. Before
implementation starts, reconcile the authoritative checkout with the released
repository and decide whether `APPLICATION_VERSION = "v8.8.0"` is an internal
milestone identifier or stale public release metadata. Implementation must not
invent a version based on README prose.

## Explicit Non-Goals

This design does not authorize:

- importer implementation;
- collection or package schema changes;
- merge, replace, overwrite, or automatic deduplication;
- OCR, AI, grading, melt value, valuation, or metadata inference;
- networking, synchronization, accounts, or telemetry;
- deleting source packages or existing collector photographs;
- shared content-addressed image ownership;
- support for package versions other than `1.0`;
- changes to existing CSV, Numista, backup, or Photo Inbox behavior;
- tags, releases, pushes, or repository visibility changes.

Implementation begins only after this architecture, the companion test plan,
and the threat model receive explicit approval.
