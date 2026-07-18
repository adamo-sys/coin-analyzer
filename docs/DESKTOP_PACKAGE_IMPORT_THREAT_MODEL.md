# Desktop Capture Package Import Threat Model

## Status

Design contract only. This document defines the security boundary for a future
desktop `.ca-package` importer. It does not implement or certify that importer.

This boundary supports the
[architecture contract](DESKTOP_PACKAGE_IMPORT_ARCHITECTURE.md) and is verified
by the [test plan](DESKTOP_PACKAGE_IMPORT_TEST_PLAN.md).

## Security Objective

Accept valid Coin Analyzer capture packages while preventing an untrusted file
from:

- writing outside an import-owned directory;
- exhausting disk, memory, CPU, file handles, or image-decoder resources;
- confusing archive identity through duplicate or colliding names;
- bypassing the manifest/media contract;
- introducing malformed collection values;
- creating a partial collection batch;
- causing deletion of collector-owned files during rollback;
- leaking absolute local paths through UI, logs, or audit history;
- replaying an already imported package without an explicit decision.

The validator must be stricter than the mobile exporter because desktop users
may receive packages from arbitrary or compromised sources.

## Trust Boundaries

```text
Untrusted local file
  -> bounded digest capture
       -> immutable package snapshot
            -> archive boundary
                 -> validated archive index
                      -> manifest parser
                           -> typed immutable manifest
                                -> media validator
                                     -> immutable import preview
                                          -> collector decisions
  ------------------------------------------------------
  no collection, journal, managed image, or audit mutation above
  temporary immutable package snapshot is the sole exception
  ------------------------------------------------------
                                          -> journal and managed image boundary
                                               -> atomic collection replacement
                                                    -> terminal audit/recovery state
```

Untrusted values include:

- file extension and basename;
- all ZIP headers, flags, sizes, names, attributes, comments, and extra fields;
- manifest bytes and every JSON value;
- declared media types, sizes, dimensions, dates, and names;
- image compressed and decoded contents;
- producer, application version, session IDs, and mobile coin IDs;
- error messages originating from decoders or the operating system.

The official schema and package version describe syntax and semantics, not
publisher authenticity. `created_by` is not a trust credential.

## Protected Assets

- `data/collection.json` and its previous valid contents;
- collector photographs and arbitrary files outside the managed import root;
- existing managed imports;
- local app-state and backup data;
- disk space, memory, CPU, and application availability;
- collector privacy, including local usernames and absolute paths;
- deterministic collection IDs and duplicate decisions;
- audit integrity and recovery evidence.

## Adversary Capabilities

Assume an attacker can construct arbitrary bytes with a `.ca-package` suffix,
including manually crafted ZIP metadata and valid image prefixes. The attacker
may know the desktop implementation and Windows path rules. The package may be
malicious, truncated, corrupted in transit, produced by a future incompatible
writer, or accidentally inconsistent without malicious intent.

The design does not attempt to defend against an attacker who already has
arbitrary code execution under the user's account or can modify the repository
and application installation.

## Security Invariants

1. No archive-supplied string becomes a destination path component.
2. No archive entry is extracted before its metadata and canonical name pass
   boundary validation.
3. Preview performs no persistent extraction, managed-image creation,
   collection mutation, journal write, or terminal audit write. The bounded
   immutable package snapshot is the sole temporary-state exception.
4. Every byte read or decoded is subject to an explicit budget.
5. One canonical archive name identifies at most one regular entry.
6. Every referenced media entry is used by exactly one coin role.
7. Actual bytes, extension, MIME type, byte length, and dimensions agree.
8. Collection mutation occurs once for the selected batch.
9. Rollback deletes only paths generated and recorded for that import beneath
   the configured managed root.
10. Audit and UI output never retain absolute source or temporary paths.
11. Unknown schema or package versions fail closed.
12. A completed package replay is visible and never silently duplicated.

## Archive Boundary Controls

### File identity

- Require a case-insensitive `.ca-package` filename suffix.
- Verify ZIP structure/signature independently of the suffix.
- Reject multipart, encrypted, or unsupported compression/encryption features.
- Compute SHA-256 by streaming the original file with a bounded buffer.
- Record only the basename and digest outside the in-memory selector context.

### Package and entry budgets

These are normative v0.2 security ceilings:

| Resource | Ceiling |
| --- | ---: |
| Package file | 256 MiB |
| Archive entries, including directories | 256 |
| Coins | 100 |
| Media records per coin | 3 |
| Manifest | 1 MiB |
| One compressed entry | 40 MiB |
| One uncompressed media entry | 40 MiB |
| Aggregate uncompressed entries | 256 MiB |
| Image width or height | 12,000 pixels |
| Image pixels | 80,000,000 pixels |
| Compression ratio | 100:1 per entry and aggregate |

Manifest limits are eight nesting levels, 64 keys per object, 16,384 Unicode
code points per string, 262,144 aggregate string code points, signed 53-bit
integers, quantity from 1 through 1,000,000, and at most 64 characters for a
plain non-negative decimal string. Exponent notation and non-finite decimal
spellings are rejected.

These are desktop v0.2 policy limits, not changes to package format `1.0`. A
later release may raise them only through a reviewed, versioned policy change.

Declared ZIP sizes are attacker-controlled hints. Streaming readers must stop
after the applicable limit even when metadata claims a smaller value.

### Canonical names and collisions

Inspect `ZipInfo` records, not only `namelist()`.

Reject:

- empty names or NUL characters;
- leading `/` or `\`;
- backslashes anywhere;
- `.` or `..` path segments;
- drive letters, colons, UNC-like prefixes, and alternate data stream syntax;
- repeated separators or empty internal segments under a strict policy;
- Windows reserved device names;
- components ending in a dot or space;
- duplicate raw names;
- duplicate names after Unicode normalization;
- duplicate names after Windows-compatible case folding;
- file/directory prefix conflicts;
- symbolic links, hard-link metadata, devices, sockets, and other non-regular
  entries.

Archive names use POSIX `/` separators. Canonicalization is for comparison and
validation only; archive names never become local destination paths.

### Manifest uniqueness

Require exactly one regular root entry named `capture_package.json` after all
collision rules are applied. Reject nested, duplicate, case-varied, or
normalization-varied alternatives.

Ordinary directory entries are permitted only when they are required parents of
referenced files and pass every canonical-name, collision, and regular-directory
check. Empty or unexpected directory trees are rejected. Every unreferenced
non-directory entry is rejected, including metadata, thumbnails, executables,
hidden payloads, and alternate manifests. A package with zero coins is rejected
as `EMPTY_PACKAGE`.

## Manifest Parser Controls

- Read the manifest through a bounded stream.
- Decode strict UTF-8.
- Reject malformed JSON and duplicate object keys.
- Require a JSON object root.
- Require exact `schema` and supported `package_version`.
- Validate required fields before constructing domain DTOs.
- Enforce exact JSON types; booleans do not satisfy integer fields.
- Enforce string, list, map, and nesting limits.
- Validate UTC/RFC 3339 timestamps and real calendar dates.
- Parse money and ASW from strings to finite non-negative `Decimal` values.
- Require positive bounded quantity.
- Require unique coin IDs and deterministic positions.
- Validate composition enum and true booleans.
- Require front and reverse and allow at most one edge.
- Require each photo path to identify one validated archive entry.
- Ignore bounded unknown additive fields only after known contract validation.

Manifest validation must not instantiate `CoinItem` through permissive
`from_dict()` and assume that constitutes package validation.

## Media Controls

For every referenced image:

1. Resolve its already validated canonical archive entry.
2. Enforce declared and streamed compressed/uncompressed limits.
3. Inspect magic bytes.
4. Require `.jpg` with `image/jpeg` or `.png` with `image/png`.
5. Verify exact streamed byte length.
6. Decode with Pillow under explicit decompression-bomb handling.
7. Require positive decoded dimensions matching the manifest.
8. Enforce width, height, pixel, and aggregate budgets.
9. Fully validate/traverse image data so a valid header with corrupt later data
   cannot pass.
10. Compute SHA-256 over the exact accepted archive bytes.
11. Close streams and decoder objects deterministically.

v0.2 preserves accepted JPEG and PNG bytes exactly and does not re-encode them.
The desktop ignores EXIF and other embedded GPS, device, date, software, owner,
and filesystem metadata rather than mapping it to collection facts. Animated,
multi-frame, or non-JPEG/PNG media is rejected. The desktop-generated owned
filename extension must match the validated byte format. A future metadata-
stripping policy would be a separately reviewed behavior change because it
changes bytes and may affect quality.

## Extraction and Managed-Path Controls

Validation copies the selected package, with bounded streaming and exclusive
creation, to
`data/imports/snapshots/<snapshot-token>/package.ca-package`. The exclusively
created directory also contains a bounded owner record and lease file; the
creating process holds an OS advisory exclusive lease for the snapshot lifetime.
The source SHA-256 and the digest computed while copying the snapshot must
match. All parsing, media validation, preview, and commit copying use that
snapshot only; commit never reopens the original package. The snapshot is
rehashed before mutation, and a mismatch returns `PACKAGE_CHANGED`.

The snapshot is temporary application state, not a collection mutation. Preview
creates no collection records, managed collection images, or terminal audit
history. Active journals may retain only its private relative path. Cancellation,
invalidation, success, rollback, and startup cleanup remove snapshots
idempotently without exposing their paths to users or terminal audit records.
Startup cleanup skips an advisory-locked snapshot, delegates journal-referenced
snapshots to import recovery, and removes an unjournaled snapshot only after its
owner record, token, matching hostname, non-live PID, acquired advisory lease,
direct-root containment, regular-file types, and absence of links/reparse points
are proven together. PID status alone is insufficient. Uncertain ownership returns
`SNAPSHOT_RECOVERY_REQUIRED`, preserves evidence, and blocks imports.

After confirmation:

- generate import and desktop item IDs locally;
- generate every destination component locally;
- create one import-owned directory beneath
  `coin_photos/collection/imports/`;
- resolve the absolute root and destination and verify containment before every
  create, copy, open, rename, or delete;
- exclusively create the import root, item directories, and every role file;
- return `MANAGED_PATH_COLLISION` for any existing destination and never
  overwrite or reuse it;
- do not follow symlinks, junctions, mount points, or reparse points;
- verify copied bytes before collection commit;
- record only managed relative paths in journal/audit data;
- never call `extractall()`;
- never reuse `original_name` as a destination.

The selected commit architecture uses stable managed paths before collection
save and performs no post-save move. The journal distinguishes pending from
owned state.

Import and desktop item IDs are cryptographically random UUIDs or equivalent.
Owned files use only fixed desktop-generated role names. Every expected path is
journalled before creation, and each successfully created path is journalled
atomically before the next mutable operation. Cleanup is idempotent, never
follows links, and deletes only the one verified import-owned root. Partial image
sets are removed on pre-commit rollback. Retries use a fresh import ID unless
resuming the exact journaled recovery.

The exclusively created import root contains an exclusively created
`.import-owner.json` marker with `ownership_schema_version`, `import_id`, and the
same cryptographically random ownership token as the journal. Recovery requires
an exact journal/marker match plus containment and link checks before cleanup;
directory placement or name alone never proves ownership.

## Collection Baseline and Integrity Controls

- The preview baseline is SHA-256 plus byte length of the exact
  `data/collection.json` bytes, or `MISSING_COLLECTION_V1` plus zero bytes when
  the file is absent. Never hash parsed or reserialized collection objects.
- Under the import lock, discard stale in-memory state, reload the file, and
  compare the exact baseline before creating a journal or owned image.
- Recheck the same locked baseline immediately before `os.replace` and verify
  committed bytes immediately afterward.
- Return `COLLECTION_CHANGED` and require a fresh preview and duplicate analysis
  if external edits, another instance/import, OneDrive, or stale GUI state
  changed the baseline.
- Allocate collision-resistant desktop IDs and verify they do not already exist.
- Build all selected `CoinItem` records in memory.
- Use authoritative acquisition normalization.
- Serialize the complete prospective collection before replacement.
- Perform exactly one atomic collection JSON replacement.
- Restore the in-memory baseline if the save reports failure.
- Never call per-record `add_item()` during the batch.
- Never mutate existing items in v0.2.
- Never accept manifest `total_cost`, grade, valuation, OCR, or AI facts.

All Coin Analyzer collection writers, including ordinary
`CoinCollection.save_collection()` paths in other application instances, must
use the same lock or an already-held verified lease. This prevents cooperating
application writers from committing simultaneously. An external editor or
OneDrive process can ignore the lock and race after the final comparison; v0.2
cannot eliminate that operating-system-independent JSON compare-and-swap gap.
The user must not externally edit/synchronize the collection during import, and
share/replace failures fail without blind retry.

## Concurrency and Import Lock

Only one collection writer, package-import commit, or recovery operation may
execute at a time. `PackageImportCoordinator` acquires an exclusive lock at
`data/imports/package_import.lock` before journal creation, managed-root
creation, image copying, or collection mutation, and holds it until replacement
or compensation finishes and the journal is terminal or recovery-required.
Preview and validation do not require the lock.

The lock uses `O_CREAT | O_EXCL`-equivalent creation plus a held OS advisory
exclusive lock, flushes and `fsync`s its metadata, and remains owned by its
caller until release. It contains
`schema_version`, `process_id`, `hostname`, `created_at`, cryptographically
random `random_lock_token`, and `import_id` when known. Acquisition uses no wait
or a short bounded wait; contention returns sanitized `IMPORT_LOCKED`. Release
requires the current process's in-memory token and identity to match the bounded
on-disk metadata, then closes its handle and deletes only that exact lock.

PID liveness alone is insufficient to clear a stale lock. v0.2 never
automatically deletes a pre-existing lock it did not create. Deliberate recovery
requires all application instances closed, exact regular-path and schema checks,
matching hostname, a non-live PID, successful acquisition of the same advisory
lock, and explicit user confirmation. It then exclusively renames the lock to a
token-qualified quarantine name before deletion. Failure of any condition
preserves the lock and reports `RECOVERY_REQUIRED`.

Concurrent dialogs and application instances therefore cannot commit
simultaneously. OneDrive, sharing, or atomic-replacement failures are commit
failures; no caller retries overwrite blindly.

## Journal, Rollback, and Recovery Controls

The journal is security-sensitive because it authorizes cleanup. It must:

- use one versioned validated file per import at
  `data/imports/journals/<import-id>.json`;
- use atomic JSON replacement;
- record immutable import identity and package digest;
- record generated desktop IDs and managed relative paths before copying;
- permit only defined state transitions;
- reject conflicting reuse of an import ID;
- never store arbitrary source paths as cleanup targets;
- preserve terminal records for replay detection;
- treat malformed or escaping managed paths as rollback-failed, not as deletion
  instructions.

Every journal requires:

```text
journal_schema_version, import_id, random_ownership_token, phase,
created_at, updated_at, package_sha256, package_version, package_basename,
snapshot_relative_path, snapshot_byte_length,
collection_baseline_sha256_or_sentinel, collection_baseline_byte_length,
selected_source_coin_ids, desktop_item_ids, import_root_relative_path,
created_relative_paths, expected_relative_paths,
committed_collection_item_ids, proposed_count, imported_count,
skipped_count, error_category, recovery_attempt_count, cleanup_pending,
audit_finalization_pending, terminal_audit
```

`terminal_audit` is required and JSON `null` while active. It becomes the
validated audit DTO only for `SUCCEEDED`, `ROLLED_BACK`, or `CANCELLED`.
Recovery-required and rollback-failed records retain private recovery evidence
and are not completed audit-history records.

Allowed durable transitions are normative:

```text
PREPARED -> COPYING_IMAGES | ROLLING_BACK
COPYING_IMAGES -> FILES_READY | ROLLING_BACK
FILES_READY -> COMMITTING_COLLECTION | ROLLING_BACK
COMMITTING_COLLECTION -> COLLECTION_COMMITTED
COMMITTING_COLLECTION -> ROLLING_BACK only when reserved IDs are absent
COLLECTION_COMMITTED -> SUCCEEDED | RECOVERY_REQUIRED
ROLLING_BACK -> ROLLED_BACK | CANCELLED | RECOVERY_REQUIRED | ROLLBACK_FAILED
any nonterminal phase -> RECOVERY_REQUIRED when reconciliation is uncertain
any nonterminal phase -> ROLLBACK_FAILED when verified owned cleanup fails
RECOVERY_REQUIRED -> ROLLING_BACK when IDs are absent and ownership is proven
RECOVERY_REQUIRED -> COLLECTION_COMMITTED when all IDs/files are present
ROLLBACK_FAILED -> ROLLING_BACK only during explicit proven recovery
```

Illegal transitions and conflicting reuse of immutable identity are rejected,
never coerced. `SUCCEEDED`, `ROLLED_BACK`, `CANCELLED`, `RECOVERY_REQUIRED`, and
`ROLLBACK_FAILED` are terminal for ordinary coordinator operations. Only the
explicit recovery transitions above may leave the latter two states.

Same-phase writes are restricted to documented progress fields. In
`SUCCEEDED`, only `updated_at` and the true-to-false clearing of
`cleanup_pending` may change; immutable identity and `terminal_audit` never do.

Rollback resolves every target against the managed root and deletes only the
single import-owned directory when its identity and containment are proven.
Failure to prove ownership stops cleanup.

Startup recovery reconciles journal IDs, collection IDs, and expected managed
files. It does not infer success from directory existence alone.

`PackageImportRecoveryService.reconcile_pending_imports()` runs before import is
enabled. It enumerates only regular journal files under the approved root,
validates the schema and every relative path, acquires the import lock before
mutation, reloads collection state from disk, examines only the verified import
root, increments `recovery_attempt_count`, and atomically records an idempotent
result. Corrupt journals, escaping or link-crossing paths, uncertain ownership,
ambiguous collection state, repeated cleanup failure, and interrupted recovery
preserve all evidence, report `RECOVERY_REQUIRED`, and block new imports.

Under that lock, startup first runs the snapshot cleanup contract. Active leased
snapshots are skipped, journal-referenced snapshots are delegated to their
journal reconciliation, and unprovable orphan ownership returns
`SNAPSHOT_RECOVERY_REQUIRED` before journal mutation continues.

## Duplicate and Replay Controls

Package SHA-256 is the primary exact replay signal. Producer/session/mobile coin
IDs and media hashes strengthen record-level evidence but are attacker-controlled
and do not authorize mutation.

The importer:

- defaults a completed exact replay to Skip;
- displays the prior import timestamp and counts without exposing paths;
- permits Import as new only through explicit collector choice;
- never merges or replaces based on duplicate score;
- records the collector's decision in the audit record.

## Privacy and Error Handling

### Data minimization

Persist:

- package basename and SHA-256;
- declared schema/writer versions;
- bounded session ID, name, description, session date, created timestamp, and
  updated timestamp, plus package export timestamp;
- per-coin source ID, imported desktop ID when applicable, decision, position,
  mint, composition, bullion flag, ASW, source timestamps, source quantity, and
  role hashes;
- managed relative paths and hashes;
- decisions, counts, phase, and status.

Those values are audit/provenance only and are not inserted into notes,
reference, grade, or unrelated collection fields. Skipped records may retain the
minimum provenance needed to explain their decision.

Do not persist:

- absolute package or temporary paths;
- picker-supplied original source filenames;
- raw decoder or OS exceptions;
- complete manifest copies;
- extracted embedded image metadata in collection fields, journal/audit fields,
  UI text, or logs. Preserved managed JPEG/PNG bytes may still contain metadata,
  as stated by the normative media policy;
- credentials, environment variables, or unrelated collection facts.

### Error taxonomy

User and audit errors use stable categories such as:

```text
PACKAGE_NOT_FOUND
PACKAGE_NOT_ZIP
PACKAGE_CHANGED
PACKAGE_LIMIT_EXCEEDED
ARCHIVE_ENTRY_UNSAFE
ARCHIVE_NAME_COLLISION
ARCHIVE_ENTRY_UNREFERENCED
MANIFEST_MISSING
MANIFEST_INVALID
EMPTY_PACKAGE
UNSUPPORTED_PACKAGE_VERSION
MEDIA_MISSING
MEDIA_INVALID
PREVIEW_STALE
COLLECTION_CHANGED
IMPORT_LOCKED
MANAGED_PATH_COLLISION
SNAPSHOT_FAILED
SNAPSHOT_RECOVERY_REQUIRED
COPYING_IMAGES_FAILED
COLLECTION_COMMIT_FAILED
AUDIT_FINALIZATION_PENDING
ROLLED_BACK
RECOVERY_REQUIRED
ROLLBACK_FAILED
```

Detailed local diagnostics may include exception classes and generated import
IDs, but path-bearing strings must be sanitized before UI or durable logging.
Hostile manifest text must not be rendered as markup or used as a format string.

## Denial-of-Service Considerations

Validation is local but still exposed to resource exhaustion. Required
mitigations include:

- early central-directory rejection;
- streaming hash and copy operations;
- bounded buffers;
- aggregate budgets shared across entries;
- decoder pixel limits;
- cooperative cancellation between bounded work units;
- no unbounded thread creation;
- no rendering of full hostile strings or unlimited error lists;
- capped preview rows and warning details with accurate totals;
- deterministic cleanup of handles and scratch state.

Timeout alone is not a sufficient defense because Python cannot safely terminate
an arbitrary decoder thread. Hard resource isolation may be considered later if
real-world hostile-image risk warrants a subprocess boundary.

## Existing Patterns: Reuse and Rejection

### Reuse

- `LegacyPortfolioImporter` separation between preview and mutation.
- `atomic_json.write_json_atomically()` for collection and journal documents.
- acquisition normalization in `coin_collection.py`.
- result DTOs with warnings and errors.
- worker queue plus Tk `after()` polling.
- backup restore's root-containment principle.

### Do not reuse as-is

- `CoinCollection.import_from_csv()` parsing/mutation coupling.
- `NumistaImporter` collection clearing and incremental saves.
- `BackupManager.verify_backup_package()` as the hostile-package validator.
- `ZipFile.extractall()` or unbounded `archive.read()`.
- Photo Inbox's reference-in-place ownership policy.
- `CoinItem.from_dict()` as external schema validation.
- generic `print()` of raw external rows or exceptions.

## Security Test Obligations

The companion test plan is normative. At minimum, implementation must prove:

- traversal and collision rejection across Windows path semantics;
- ZIP and image resource limits;
- duplicate JSON-key rejection;
- MIME/extension/byte/dimension agreement;
- no persistent mutation during preview;
- one atomic collection commit;
- compensation at every mutable failure point;
- restart recovery for every journal phase;
- no deletion outside the managed import root;
- path-free user and audit errors;
- exact replay detection;
- full existing regression compatibility.

## Residual Risks and Deferred Controls

- Pillow and Python ZIP parser vulnerabilities remain dependency risks; normal
  dependency maintenance is required.
- SHA-256 proves content identity, not publisher authenticity.
- The design does not include package signing.
- Imported image backup is not guaranteed until backup coverage is extended and
  documented.
- Existing item deletion does not remove managed files, so long-term orphan
  management is deferred.
- Previewing extremely complex but limit-compliant images may still consume
  noticeable CPU.
- Preserving validated image bytes also preserves embedded metadata; v0.2 does
  not interpret it, and any later stripping/re-encoding policy requires review.
- Rollback-failed recovery may require manual review rather than aggressive
  automated deletion.
- Non-cooperating external editors and synchronization tools can race within the
  final exact-byte-check/replace interval; all application writers coordinate,
  but v0.2 cannot provide filesystem-independent compare-and-swap against tools
  that ignore the lock.

## Resolved v0.2 Security Policy

- The numeric ceilings in this document are normative.
- JPEG and PNG bytes are preserved exactly; animated and multi-frame media is
  rejected.
- Ordinary directory entries are accepted only as required parents.
- Every unreferenced non-directory entry and every zero-coin package is rejected.
- The lock, journal, snapshot, and image roots are normative.
- Import audit history is retained indefinitely; recovery-required evidence is
  never removed automatically.
- Imported images are not claimed as application-backed-up data in v0.2.

The only repository precondition remaining before implementation is reconciling
public application version metadata with the authoritative checkout. It does not
alter these security decisions.

## Explicit Stop Line

This threat model does not authorize importer code, dependency changes,
collection migrations, package-format changes, live-data testing, cleanup of
existing files, commits, pushes, tags, releases, or visibility changes.
