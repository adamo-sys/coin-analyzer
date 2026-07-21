# Durable Persistence Architecture

## Status and authority

This document is the normative durability contract for the Desktop Capture
Package Importer. It refines the persistence, crash-recovery, and lock-ordering
parts of the approved [import architecture](../DESKTOP_PACKAGE_IMPORT_ARCHITECTURE.md),
[threat model](../DESKTOP_PACKAGE_IMPORT_THREAT_MODEL.md), and
[test plan](../DESKTOP_PACKAGE_IMPORT_TEST_PLAN.md). Package validation,
mapping, duplicate policy, and UI behavior remain governed by those documents.

Where an earlier document describes a persistence order that conflicts with
this document, this document controls. Implementing the target design requires
a separately reviewed production-code phase and, where the durable schema
changes, a journal schema-version change. This design does not authorize code,
test, public-contract, or repository-history changes.

## Terminology

- **Crash consistency** means that after process termination or operating-system
  failure, durable evidence describes either the old state, the new state, or an
  explicitly recoverable intermediate state. Power-loss consistency is claimed
  only where the platform section explicitly provides it. A write merely returning
  without error is never sufficient evidence.
- **Durable** means the required file data and containing-directory namespace
  updates have completed according to the supported platform protocol and its
  explicitly stated crash class. It does not silently elevate Windows namespace
  operations to a power-loss guarantee.
- **Identity** means a native filesystem object identity captured from an open
  no-follow handle, together with the verified identity of its parent directory.
- **Owned artifact** means an object whose contained path, schema, import ID,
  random ownership token, native identity, and expected bytes are all proven.
- **Cleanup-authorized incomplete candidate** means a regular, no-follow object
  that is not yet an owned artifact but may be removed because a prior durable
  intent names its exact parent-relative target and unpredictable token, its
  parent and held native identity still match, and no complete artifact can
  validly occupy that target. This narrower proof authorizes deletion only; it
  never authorizes adoption, publication, parsing, or successful recovery.
- **Journal generation** means one immutable, strictly validated state record in
  a hash-linked sequence for one import.
- **Ambiguous** means that the available evidence permits more than one safe
  interpretation, or that ownership, identity, ordering, or exact bytes cannot
  be proven.
- **Terminal** means `SUCCEEDED`, `ROLLED_BACK`, or `CANCELLED` recorded only in
  sanitized terminal history. An operational generation never becomes terminal
  history merely by carrying an outcome label.
- **Operational state** means the owner record, immutable generations, retirement
  manifest, and detailed recovery artifacts beneath the active or retirement
  roots. It may contain bounded relative operational paths while recovery remains
  possible.
- **Privacy-complete terminal state** means one sanitized final history record is
  durable and verified, and the active chain, retirement directory, pending
  terminal record, and all prohibited operational artifacts are absent.

## Design goals

The implementation shall provide:

1. Crash-consistent collection, journal, snapshot, and managed-image updates.
2. Deterministic recovery: equal durable evidence produces the same decision.
3. Idempotent recovery: repeating a completed reconciliation has no new effect.
4. Fail-closed behavior for corrupt, incomplete, substituted, or ambiguous state.
5. Correctness on explicitly supported Windows, Linux, and macOS filesystems.
6. Narrow ownership: no pathname alone authorizes reading, replacing, or deleting.
7. Minimal trusted state: only the global lock, verified journal chain, held
   object identities, exact collection bytes, and verified artifact inventories
   may drive mutation.
8. Bounded resource use and sanitized errors that do not persist private paths.

Availability is subordinate to integrity. Evidence is preserved and imports are
blocked whenever the implementation cannot prove the next action safe.

## Two related lifecycles

The UI preparation lifecycle and the confirmed-import transaction lifecycle are
distinct. This resolves the apparent ordering conflict in the shorthand
“Package Accepted, Journal Created, Snapshot Created.” A preview is built from
an immutable snapshot before the collector confirms an import; creating a
transaction journal for every abandoned preview would turn read-only preview
into durable transaction history.

### Read-only preparation lifecycle

```text
Package accepted
    -> immutable snapshot created and verified
    -> package validated
    -> preview and decisions created
    -> cancel: verified snapshot cleanup, no transaction journal
    -> confirm: hand snapshot lease and immutable preview to execution
```

Snapshot creation is the only preparation-side filesystem effect. It is owned
workspace state, never collection state. Its owner record and lease protocol
are defined below. If preparation crashes, startup orphan reconciliation handles
the snapshot without inventing an import transaction.

### Confirmed-import durability lifecycle

```text
Snapshot accepted under lock
    -> PREPARED journal durable
    -> images persisted and verified
    -> FILES_READY journal durable
    -> collection commit intent durable
    -> collection persisted and verified
    -> COLLECTION_COMMITTED journal durable
    -> terminal material durable
    -> cleanup intent durable
    -> snapshot cleanup durably confirmed
    -> COMPACTING head and retirement manifest durable
    -> sanitized pending terminal record durable
    -> operational generation chain retired
    -> sanitized final terminal history durable
```

The `PREPARED` generation is the “Journal Created” durability boundary. It must
reference an already existing, under-lock revalidated snapshot because that is
the evidence from which execution and recovery proceed. No collection or
managed-image mutation may occur before `PREPARED` is durable.

## Transaction state machine

### Durable states

Journal schema 2 uses these operational phases:

- `PREPARED`
- `COPYING_IMAGES`
- `FILES_READY`
- `COMMITTING_COLLECTION`
- `COLLECTION_COMMITTED`
- `ROLLING_BACK`
- `RECOVERY_REQUIRED`
- `ROLLBACK_FAILED`
- `COMPACTING`

`SUCCEEDED`, `ROLLED_BACK`, and `CANCELLED` are final outcomes in the sanitized
`TerminalHistoryRecord`, not operational journal phases. A caller may report a
provisional outcome while `COMPACTING`, but the transaction is not terminal and
new import remains disabled until privacy-complete terminalization.

Durability substate is represented by strict journal fields rather than inferred
from path existence. Journal schema 2.0 is closed and contains exactly the fields
defined below. It adds:

- monotonic `generation`;
- `previous_generation_sha256` (`null` only for generation zero);
- `transition_id` and random write token;
- exact expected collection baseline and prospective byte length/SHA-256;
- managed-image inventory with relative path, length, SHA-256, media facts, and
  captured native identity where the platform provides a stable identity;
- an append-only cleanup-operation ledger;
- complete pending terminal-audit material before cleanup begins.

Unknown fields, unknown schema versions, missing generation links, forks, gaps,
or a mismatch between a generation filename and its contents are corrupt state.

### Journal schema version 2

The target schema identifier is the string `2.0`. Every generation is one strict
canonical JSON object. Unknown or omitted fields are rejected; nullable fields
must be present with JSON `null`. Arrays are ordered, bounded, and duplicate-free.

`MAX_JOURNAL_GENERATIONS` is exactly 4096 and includes every retained operational
generation, including generation zero and the active head. Numbering begins at
zero, so valid generation numbers are 0 through 4095. Numbers never wrap and the
limit is neither configurable nor stored outside the schema contract. Generations
0 through 3583 are the normal-work budget; generations 3584 through 4095 are a
512-generation closure reserve. Before consuming generation 3584, forward work
that has not published the collection must enter rollback. A published collection
must enter cleanup/compaction. Recovery attempts also consume generations.

A `COMPACTING/PLANNING_MANIFEST` G at 4094 may publish its planned
`READY_FOR_TERMINAL` H at 4095, which completes external compaction without
another generation. Any other head at 4094, or any generation 4095 that is not
that exact H, cannot terminalize and produces the process-level
`JOURNAL_GENERATION_EXHAUSTED` blocked result requiring operator intervention.
Any generation number greater than 4095, wraparound, duplicate number, or attempt
to begin a new import whose conservative upper bound would enter the reserve is
rejected. Startup never deletes evidence or guesses a transition after exhaustion.

`MAX_IMPORT_STATE_MEMBERS` is exactly 10000 members in each of the journal and
history parents, counted before schema interpretation. It is not configurable.
Exceeding it preserves all entries, blocks import/recovery mutation with sanitized
`IMPORT_STATE_LIMIT_EXCEEDED`, requires operator intervention, and never causes
automatic history deletion.

| Field | Type and bound | Mutation rule |
| --- | --- | --- |
| `journal_schema_version` | string, exactly `2.0` | Immutable |
| `import_id`, `random_ownership_token` | canonical UUID strings | Immutable |
| `generation` | integer, 0–4095 | Increases by exactly one; no wraparound |
| `previous_generation_sha256` | lowercase SHA-256 or `null` at generation zero | Must hash the exact preceding generation bytes |
| `transition_id` | canonical UUID string | New and unique in every generation |
| `next_generation_token` | canonical UUIDv4 string or `null` | Required and unique in every generation that may have a successor; null only in the final `COMPACTING` head ready to publish terminal history |
| `phase` | one of `PREPARED`, `COPYING_IMAGES`, `FILES_READY`, `COMMITTING_COLLECTION`, `COLLECTION_COMMITTED`, `ROLLING_BACK`, `RECOVERY_REQUIRED`, `ROLLBACK_FAILED`, `COMPACTING` | Changes only by the legal transition table |
| `resume_phase` | one of `PREPARED`, `COPYING_IMAGES`, `FILES_READY`, `COMMITTING_COLLECTION`, `COLLECTION_COMMITTED`, `ROLLING_BACK`, or `null` | Required only in `RECOVERY_REQUIRED` or `ROLLBACK_FAILED` |
| `created_at`, `updated_at` | normalized UTC RFC 3339 strings | `created_at` immutable; `updated_at` nondecreasing |
| `package_sha256` | 64-character lowercase SHA-256 | Immutable |
| `package_version` | string, exactly `1.0` | Immutable |
| `package_basename` | basename string, 1–255 Unicode scalar values, ending `.ca-package` | Immutable |
| `snapshot_byte_length` | integer, 1–268435456 | Immutable |
| `snapshot_relative_path` | strict relative path or `null` | Required until a durable snapshot-cleanup receipt; forbidden terminally |
| `collection_baseline_sha256_or_sentinel` | 64-character lowercase SHA-256 or `MISSING_COLLECTION_V1` | Immutable |
| `collection_baseline_byte_length` | integer, 0–9007199254740991 | Immutable; zero with missing sentinel |
| `prospective_collection_byte_length`, `prospective_collection_sha256` | non-negative integer/SHA-256 or both `null` | Both become required at `COMMITTING_COLLECTION`; then immutable |
| `selected_source_coin_ids` | ordered unique array of 1–100 strings, each 1–16384 characters | Immutable |
| `desktop_item_ids` | ordered unique array of 1–100 canonical UUID strings; same length as selected source IDs | Immutable |
| `import_root_relative_path` | strict relative path, 1–1024 characters | Immutable |
| `expected_image_inventory` | ordered immutable array of 1–300 `ExpectedImage` objects | Complete in `PREPARED`; immutable |
| `verified_image_inventory` | ordered array of 0–300 `VerifiedImage` objects | May append exactly one matching expected item in `COPYING_IMAGES`; complete from `FILES_READY` onward |
| `committed_collection_item_ids` | empty or exact reserved desktop-ID sequence | Empty before verified prospective collection bytes; complete from `COLLECTION_COMMITTED` onward |
| `proposed_count`, `imported_count`, `skipped_count` | integers, each 0–100; proposed is positive and imported plus skipped equals proposed | Counts must agree with selections and committed IDs |
| `collection_publication` | `NONE`, `INTENT`, or `VERIFIED` | `INTENT` only in `COMMITTING_COLLECTION`; `VERIFIED` from `COLLECTION_COMMITTED` onward |
| `collection_temporary_artifact` | `CollectionPublicationArtifact` or `null` | Required from entry to `COMMITTING_COLLECTION` until `COMPACTING`; null before intent and in the final compaction head |
| `collection_backup_artifact` | `CollectionPublicationArtifact` or `null` | Required for an existing baseline from entry to `COMMITTING_COLLECTION` through `CLEANED`; cleared only on entry to `COMPACTING`; always null for a missing baseline |
| `cleanup_operations` | ordered array of 0–3 `CleanupOperation` objects | Append one intent, append one receipt to the final operation, or apply the completion-only successor after all receipts are durable; prior operations immutable |
| `pending_terminal_audit` | complete `AuditSession` or `null` | Required before success/rollback snapshot cleanup; immutable once set |
| `compaction` | `TerminalCompaction` or `null` | Non-null only in `COMPACTING`; immutable once the ready head is durable |
| `error_category` | one closed schema-2 `ErrorCategory` string defined below or `null` | Required in valid-chain recovery failure states; never raw exception text |
| `recovery_attempt_count` | bounded non-negative integer | May increase by exactly one per persisted recovery attempt |

All string bounds count Unicode scalar values after NFC normalization. A strict
relative path uses `/`, is 1–1024 characters, contains no empty, `.`, or `..`
component, and has the approved Windows-safe canonical key. Integers do not exceed
9007199254740991 unless a smaller bound is stated.

Nested schemas are closed and contain exactly these keys:

| Object | Exact keys and rules |
| --- | --- |
| `ExpectedImage` | `relative_path` (strict relative path), `role` (`front`, `reverse`, or `edge`), `byte_length` (1–41943040), `sha256` (lowercase SHA-256), `media_type` (`image/jpeg` or `image/png`), `width` and `height` (integers 1–12000) |
| `VerifiedImage` | All `ExpectedImage` keys plus `parent_identity` and `object_identity`; its expected fields equal the corresponding array item exactly |
| `ObjectIdentity` | `platform` (`WINDOWS` or `POSIX`), `volume_id`, `object_id`; Windows values are respectively 16 and 32 lowercase hexadecimal characters, POSIX values are canonical unsigned decimal strings of 1–20 digits without leading zero except `0` |
| `OwnershipDescriptor` | `root` (`JOURNAL`, `SNAPSHOT`, `MANAGED_IMAGE`, or `COLLECTION`), `relative_path`, `object_kind` (`FILE` or `DIRECTORY`), `ownership_token` (UUID), `expected_byte_length` (integer or `null`), `expected_sha256` (SHA-256 or `null`), `parent_identity`, `object_identity`; byte fields are both null only for a directory or incomplete candidate |
| `CleanupReceipt` | `target_relative_path`, `removed_object_identity`, `removal_generation` (integer greater than the operation's intent generation) |
| `CleanupOperation` | `kind` (`BASELINE_BACKUP`, `SUCCESS_SNAPSHOT`, or `ROLLBACK_ALL`), `intent_id` (UUID), `intent_generation` (integer), `targets` (ordered unique array of 1–301 `OwnershipDescriptor` objects), `receipts` (ordered prefix of targets represented by 0–301 `CleanupReceipt` objects), `status` (`INTENT` or `COMPLETE`), `completed_generation` (integer or `null`) |
| `CollectionPublicationArtifact` | Closed schema defined below; represents one prospective temporary object or one displaced-baseline backup across explicit pre-publication and post-publication states |
| `TerminalCompaction` | Closed schema defined below; G plans H and the retirement/terminal names, while H commits the manifest and sanitized outcome payload without a cyclic terminal-record hash |

For `CleanupOperation`, `INTENT` requires an ordered prefix of zero through all
target receipts and a null `completed_generation`; `COMPLETE` requires one receipt
per target in target order and a completion generation not earlier than the last
receipt. An operation is appended only as `INTENT`. Later same-phase generations
may append exactly one receipt to the last operation while leaving it `INTENT`.
Once all target receipts are durable, no additional deletion, receipt mutation,
or target mutation is legal. The only legal successor changes that operation to
`COMPLETE` and sets `completed_generation` to the successor's current generation;
every other field remains byte-for-byte unchanged. A new operation may be
appended only after every prior operation is complete; prior operations and their
receipts never change. Success with an existing baseline orders
`BASELINE_BACKUP` before `SUCCESS_SNAPSHOT`. Success with a missing baseline has
only `SUCCESS_SNAPSHOT`. Rollback has one `ROLLBACK_ALL` operation whose target
order is any verified collection temp, any verified baseline backup, managed
files, managed directories deepest-first, snapshot file, snapshot metadata, then
snapshot directory. Absent target classes are omitted without changing the order
of those present. Completed operations remain in operational generations and are
transformed into path-free cleanup summaries during compaction; they are not copied
as operational descriptors into terminal history.

### Collection publication artifact schema

`CollectionPublicationArtifact` has exactly these keys and no others:

| Field | Type and bounds |
| --- | --- |
| `kind` | `TEMPORARY` or `BACKUP` |
| `relative_name` | Strict ASCII basename of 1–255 bytes under the held collection parent |
| `token` | Canonical UUIDv4 unique within the transaction |
| `relationship` | `PROSPECTIVE_BYTES` for `TEMPORARY`; `BASELINE_BYTES` for `BACKUP` |
| `expected_byte_length` | Integer 0–`MAX_JSON_BYTES`; prospective length is positive, baseline may be zero |
| `expected_sha256` | Lowercase 64-character SHA-256 of the exact relationship bytes |
| `expected_parent_identity` | Non-null `ObjectIdentity` equal to the collection parent identity committed at intent |
| `state` | `PLANNED`, `CREATED`, `VERIFIED`, `EXCHANGED`, `PUBLISHED`, `RETAINED`, or `CLEANED` |
| `object_identity` | `ObjectIdentity` or null; identity of this relationship's bytes, not merely the current pathname |
| `verified_byte_length`, `verified_sha256` | Integer/hash pair or both null; when non-null they equal the expected commitment |
| `verified_generation` | Integer 0–4095 or null |
| `current_relative_name` | Strict basename or null; the verified current location after creation or exchange |
| `exchange_generation` | Integer 0–4095 or null; generation that records verified post-exchange layout |
| `published_relative_name` | Fixed collection basename or null |
| `publication_generation` | Integer 0–4095 or null |
| `cleanup_operation_id` | Canonical UUIDv4 or null |

Nullability and transitions are normative:

| Kind/state | Required non-null fields beyond the immutable plan | Required null fields | Meaning and legal successor |
| --- | --- | --- | --- |
| Either / `PLANNED` | none | identity, verified pair/generation, current/published names, exchange/publication generation, cleanup ID | No object for this relationship has been adopted; `TEMPORARY -> CREATED`; Windows `BACKUP -> CREATED`; POSIX `BACKUP -> EXCHANGED` only after atomic exchange |
| Either / `CREATED` | object identity, current name equal to relative name | verified pair/generation, exchange/publication fields, cleanup ID | Exact planned object exists but has not been byte-verified; successor `VERIFIED` |
| Either / `VERIFIED` | identity, verified pair/generation, current name equal to relative name | exchange/publication fields, cleanup ID | Exact bytes are held and verified before publication; Windows backup may reach this state; POSIX backup may not |
| `TEMPORARY` / `EXCHANGED` | original prospective identity and verified fields, current name equal to fixed collection basename, exchange generation | publication fields, cleanup ID | POSIX exchange was observed exactly but collection outcome generation is not yet durable; successor `PUBLISHED` |
| `BACKUP` / `EXCHANGED` | displaced baseline identity, verified fields equal baseline, current name equal to temporary basename, exchange generation | publication fields, cleanup ID | POSIX backup identity first becomes knowable after exchange; successor `RETAINED` |
| `TEMPORARY` / `PUBLISHED` | prospective identity/verified fields, current and published names equal fixed collection basename, exchange generation on POSIX only, publication generation | cleanup ID | Prospective bytes are the durable destination |
| `BACKUP` / `RETAINED` | baseline identity/verified fields, current name equal backup basename on Windows or temporary basename on POSIX, exchange generation on POSIX only, publication generation | published name, cleanup ID | Exact displaced baseline is retained for success cleanup or rollback |
| `BACKUP` / `CLEANED` | all `RETAINED` proof plus cleanup ID | published name | Matching completed cleanup operation removed the retained baseline |

`TEMPORARY/CLEANED`, `BACKUP/PUBLISHED`, a POSIX `BACKUP/CREATED` or
`BACKUP/VERIFIED`, and every unlisted transition are invalid. Fields do not change
except as the next row permits. Native identity is forbidden before an object for
that relationship exists and mandatory afterward.

The temporary artifact is named exactly
`.collection-<import-id>-<token>.tmp`. On Windows an existing-baseline backup is
`.collection-<import-id>-<backup-token>.bak`. On Linux/macOS exchange, the backup
descriptor uses the temporary artifact's name but has its own UUIDv4 token. The
baseline does not occupy that name until the exchange and therefore the POSIX
backup remains `PLANNED`, with null identity and verified fields, before exchange.
The two descriptors may share that planned name only on those platforms and only
with complementary relationships and distinct tokens. No filename is discovered
or accepted without the matching durable descriptor and exact layout proof.

The `TEMPORARY` plan is non-null in the first `COMMITTING_COLLECTION` generation.
An existing baseline also requires a planned `BACKUP`; a missing baseline forbids
one. Each explicit external creation is preceded by `PLANNED`, followed by one
same-phase generation recording `CREATED`, and one recording `VERIFIED`. POSIX
exchange creates the backup relationship atomically by moving the already-held
baseline to the temporary name, so its legal transition is directly from
`PLANNED` to `EXCHANGED` after exact post-exchange verification. Native identity is
forbidden before the corresponding relationship exists and mandatory afterward. If a crash
occurs after creation but before `CREATED` is durable, the planned name/token and
verified parent authorize only bounded opening and verification: a matching
complete object may advance to `CREATED`/`VERIFIED`, a partial matching object is
a cleanup-authorized candidate, and every conflicting object blocks recovery.

Collection publication uses these exact durable/effective substates:

| Durable fields and observed layout | Required null fields | Recovery or next action |
| --- | --- | --- |
| Before intent: phase `FILES_READY`, publication `NONE`, artifacts null | Both artifact descriptors and prospective commitment | Enter `COMMITTING_COLLECTION` with exact prospective commitment and planned artifact descriptor(s) |
| Intent durable: temporary `PLANNED`; backup `PLANNED` iff baseline exists | All created/verified/publication/cleanup fields | Create only the exact temporary target |
| Temp exists before identity generation | Temp identity/verified fields remain null durably | Open exact planned target; partial is cleanup-only, complete may be verified; conflict blocks |
| Temp `CREATED` | Temp verified/publication/cleanup fields | Verify exact bytes and identity |
| Windows temp `VERIFIED`; backup `PLANNED` when applicable | Temp publication fields; backup identity/verification | Create the exact independent backup target |
| Windows backup exists before identity generation | Backup identity/verified fields remain null durably | Open exact planned target; exact baseline may advance; conflict blocks |
| Windows temp and applicable backup `VERIFIED`; or POSIX temp `VERIFIED` and backup `PLANNED`; publication `INTENT` | Publication generations and cleanup IDs | Perform the one platform publication operation |
| Publication may have occurred but namespace durability/outcome generation did not | Last durable fields remain pre-publication | Use the exhaustive D/T/B exact-byte/identity table; never infer from IDs or return status; exact POSIX exchanged layout advances both descriptors to `EXCHANGED` in one generation |
| POSIX temp and backup `EXCHANGED` | Publication fields remain null | Sync/reverify parent and both identities, then publish the outcome generation |
| Namespace durable and destination exactly prospective | No required publication field remains null | Transition to `COLLECTION_COMMITTED`, temp `PUBLISHED`, backup `RETAINED` when present, publication `VERIFIED` |
| Backup cleanup complete | Backup state `CLEANED` with matching cleanup ID | Continue snapshot cleanup and compaction |
| Final `COMPACTING` head | Both collection artifact descriptors null | Path-free terminal proof retains only exact collection digest/length and aggregate cleanup evidence |

Each row after intent is represented by a new generation except the unavoidable
external interval between publication and directory durability. In that interval
the last durable row is Windows temporary and backup `VERIFIED`, or POSIX
temporary `VERIFIED` plus backup `PLANNED`, with publication `INTENT`; recovery
uses only the exact layout table. Replaying an already durable row is a
no-op; advancing requires the one next row and a fresh generation token.

### Terminal compaction schema

`TerminalCompaction` has exactly these keys:

| Field | Type, bounds, and nullability |
| --- | --- |
| `schema_version` | String `1.0` |
| `status` | `PLANNING_MANIFEST` or `READY_FOR_TERMINAL` |
| `final_phase`, `result` | Same value: `SUCCEEDED`, `ROLLED_BACK`, or `CANCELLED` |
| `completed_at` | Normalized UTC RFC 3339 fixed in G |
| `terminal_pending_name` | Exact `.pending-<import-id>.json` basename |
| `terminal_temporary_name` | Exact `.pending-<import-id>-<terminal-token>.tmp` basename |
| `terminal_token`, `retirement_token` | Distinct canonical UUIDv4 values |
| `retirement_directory_name` | Exact `.retire-<import-id>` basename |
| `retirement_manifest_name` | Exact `retirement-manifest.json` basename |
| `retirement_manifest_temporary_name` | Exact `.retirement-manifest-<retirement-token>.tmp` basename |
| `manifest_generation_first` | Integer `0` |
| `manifest_generation_last` | Integer G in 0–4094 |
| `manifest_generation_count` | Integer G+1 in 1–4095 |
| `compaction_commit_generation` | Integer H=G+1 in 1–4095 |
| `compaction_commit_transition_id` | Canonical UUIDv4 fixed in G |
| `compaction_commit_filename` | Exact generation filename derived from H and its transition ID |
| `owner_record_sha256` | Lowercase SHA-256 |
| `history_parent_identity`, `journal_parent_identity`, `operational_directory_identity` | Non-null `ObjectIdentity` |
| `manifest_byte_length` | Integer 1–1048576 or null |
| `manifest_sha256` | Lowercase SHA-256 or null |
| `manifest_object_identity` | `ObjectIdentity` or null |
| `outcome_payload_sha256` | Lowercase SHA-256 or null; hash of the closed sanitized outcome payload defined below |

The three manifest fields are either all null or all non-null.
`outcome_payload_sha256` is null only in G. `TerminalCompaction` contains no
terminal-object length, digest, or identity because the final terminal object is
constructed only after H exists; those proofs live in the pending/final terminal
record without creating a hash cycle.

`TerminalCompaction` has two exact rows:

| Status | Generation/token rule | Manifest and terminal commitments | Legal action |
| --- | --- | --- | --- |
| `PLANNING_MANIFEST` | Generation G has a non-null next token; manifest range is 0..G; commit generation is G+1 with its transition ID/final filename already fixed | Manifest triple and outcome-payload hash are null | Create, sync, publish, and verify the manifest; deterministically construct/hash the sanitized outcome payload; publish planned successor H |
| `READY_FOR_TERMINAL` | Generation H equals planned G+1, has the planned transition ID/name, links to G, and has null next token | Exact manifest triple and outcome-payload hash are non-null | Construct the terminal record using exact H byte/identity proof, create/write/sync/verify the terminal temp, then publish it no-overwrite to pending; no later generation is legal |

All other compaction combinations are invalid. Immutable compaction identity,
names, tokens, outcome, parent identities, generation range, and owner hash remain
equal from G to H. H adds only the verified manifest triple, exact sanitized
outcome-payload hash, and ready status. G's next-generation token authorizes H.
The terminal record recalculates that payload hash and additionally commits H's
exact bytes and native identity. H does not hash the full terminal record. This
one-way linkage is non-cyclic: G authorizes H, H commits the outcome payload, and
the later pending record commits exact H while reproducing the committed payload.

`AuditSession` means exactly the existing closed audit schema version 1.0; no
additional audit keys are permitted. Every schema-2 JSON object is at most
1048576 UTF-8 bytes, nesting is at most 8, each object has at most 64 keys, each
string at most 16384 characters, and aggregate string content at most 262144
characters.

For schema 2, `ErrorCategory` is closed to the current enum values
`PACKAGE_NOT_FOUND`, `PACKAGE_NOT_ZIP`, `PACKAGE_CHANGED`,
`PACKAGE_LIMIT_EXCEEDED`, `ARCHIVE_ENTRY_UNSAFE`, `ARCHIVE_NAME_COLLISION`,
`ARCHIVE_ENTRY_UNREFERENCED`, `MANIFEST_MISSING`, `MANIFEST_INVALID`,
`EMPTY_PACKAGE`, `UNSUPPORTED_PACKAGE_VERSION`, `MEDIA_MISSING`, `MEDIA_INVALID`,
`PREVIEW_STALE`, `COLLECTION_CHANGED`, `IMPORT_LOCKED`,
`MANAGED_PATH_COLLISION`, `SNAPSHOT_FAILED`, `SNAPSHOT_RECOVERY_REQUIRED`,
`COPYING_IMAGES_FAILED`, `COLLECTION_COMMIT_FAILED`,
`AUDIT_FINALIZATION_PENDING`, `ROLLED_BACK`, `RECOVERY_REQUIRED`,
`ROLLBACK_FAILED`, `JOURNAL_CORRUPT`, `DUPLICATE_PACKAGE`, plus
`UNSUPPORTED_DURABILITY_ENVIRONMENT`, `JOURNAL_GENERATION_EXHAUSTED`, and
`IMPORT_STATE_LIMIT_EXCEEDED`. Adding another value requires a journal
schema review even when the package schema is unchanged.

### Phase and evidence requirements

| Phase | Required evidence | Forbidden or incomplete evidence |
| --- | --- | --- |
| `PREPARED` | Snapshot identity; complete expected image inventory; empty verified inventory; collection baseline; next token | Prospective collection/artifacts, cleanup operations, committed IDs, terminal material, compaction |
| `COPYING_IMAGES` | Snapshot identity; verified inventory is an ordered prefix; next token | Collection intent/artifacts/outcome, committed IDs, terminal material, compaction |
| `FILES_READY` | Complete verified image inventory; next token | Collection intent/artifacts/outcome, committed IDs, terminal material, compaction |
| `COMMITTING_COLLECTION` | Complete images; exact baseline/prospective commitments; publication `INTENT`; temporary plan; backup plan exactly when baseline exists; next token | Committed IDs until prospective bytes are proven; terminal material, cleanup, compaction |
| `COLLECTION_COMMITTED` | Publication `VERIFIED`; temporary `PUBLISHED`; backup `RETAINED` or null; exact committed IDs; complete pending terminal audit; next token | Compaction before required cleanup operations complete |
| `ROLLING_BACK` | Final cleanup operation is `ROLLBACK_ALL` when deletion begins; exact remaining owned inventory; next token | Prospective collection committed by this import; compaction before rollback cleanup completes |
| `RECOVERY_REQUIRED` | Valid chain, sanitized error, `resume_phase`, incremented attempt count | Mutation not uniquely authorized by the resume evidence |
| `ROLLBACK_FAILED` | Valid chain, `resume_phase = ROLLING_BACK`, failed cleanup intent and remaining verified targets | Terminal audit |
| `COMPACTING` | Provisional final phase/result; complete pending audit; all cleanup operations complete; `TerminalCompaction`; no snapshot or collection artifact path | Any incomplete cleanup, unresolved artifact, raw error, or collection ambiguity |

New-field nullability is normative:

| Phase | `next_generation_token` | Temporary artifact | Backup artifact | `cleanup_operations` | Pending audit | `compaction` |
| --- | --- | --- | --- | --- | --- | --- |
| `PREPARED`, `COPYING_IMAGES`, `FILES_READY` | UUIDv4 | null | null | empty | null | null |
| `COMMITTING_COLLECTION` | UUIDv4 | non-null `PLANNED`/`CREATED`/`VERIFIED`, then POSIX `EXCHANGED` | non-null iff baseline exists; Windows `PLANNED`/`CREATED`/`VERIFIED`, POSIX `PLANNED` then `EXCHANGED` | empty | null | null |
| `COLLECTION_COMMITTED` before cleanup | UUIDv4 | `PUBLISHED` | `RETAINED` iff baseline exists | empty | non-null | null |
| `COLLECTION_COMMITTED` during/after cleanup | UUIDv4 | `PUBLISHED` | `RETAINED` then `CLEANED` iff baseline exists | ordered `INTENT` receipt prefix from zero through all targets, or completed operation; fully receipted `INTENT` has null `completed_generation` | non-null | null |
| `ROLLING_BACK` | UUIDv4 | current descriptor or null according to rollback origin | current descriptor or null according to baseline/platform | exactly one `ROLLBACK_ALL`: `INTENT` with zero through all target receipts and null `completed_generation`, or `COMPLETE` | non-null before cleanup starts | null |
| `RECOVERY_REQUIRED` | UUIDv4 unless head 4095 | Preserve exactly the `resume_phase` value | Preserve exactly the `resume_phase` value | Preserve prior operations; no broadening | Preserve prior value | null |
| `ROLLBACK_FAILED` | UUIDv4 unless head 4095 | Preserve rollback evidence | Preserve rollback evidence | final `ROLLBACK_ALL` remains incomplete | non-null | null |
| `COMPACTING` / `PLANNING_MANIFEST` | UUIDv4 authorizing H | null | null | all operations complete | non-null | non-null planning row |
| Final `COMPACTING` / `READY_FOR_TERMINAL` head | null | null | null | all operations complete | non-null | non-null ready row |

Any combination not listed is invalid. A created object with a still-`PLANNED`
descriptor is an external crash interval, not a different durable row; recovery
must establish its identity before writing `CREATED`. A published collection with
pre-publication artifact states and `INTENT` is likewise an external interval
resolved only by the exact layout table. On POSIX, the first durable post-exchange
generation advances both relationships to `EXCHANGED`; one descriptor may never
advance without the other.

Same-phase generations are permitted only for: one-image append in
`COPYING_IMAGES`; publication substeps in `COMMITTING_COLLECTION`; append of one
cleanup intent, one exact receipt, or the completion-only successor after all
receipts are durable in `COLLECTION_COMMITTED` or `ROLLING_BACK`; and
one recovery-attempt increment in `RECOVERY_REQUIRED` or `ROLLBACK_FAILED`.
`COMPACTING` permits only the G-to-H same-phase transition defined above; after
the `READY_FOR_TERMINAL` head sets `next_generation_token = null`,
no further operational generation is legal.
Every other same-phase semantic change is forbidden.

### Legal transitions

```text
PREPARED -> COPYING_IMAGES
PREPARED -> ROLLING_BACK

COPYING_IMAGES -> FILES_READY
COPYING_IMAGES -> ROLLING_BACK

FILES_READY -> COMMITTING_COLLECTION
FILES_READY -> ROLLING_BACK

COMMITTING_COLLECTION -> COLLECTION_COMMITTED
COMMITTING_COLLECTION -> ROLLING_BACK

COLLECTION_COMMITTED -> COMPACTING(final SUCCEEDED)

ROLLING_BACK -> COMPACTING(final ROLLED_BACK or CANCELLED)

PREPARED/COPYING_IMAGES/FILES_READY/COMMITTING_COLLECTION/
COLLECTION_COMMITTED/ROLLING_BACK -> RECOVERY_REQUIRED
ROLLING_BACK/RECOVERY_REQUIRED -> ROLLBACK_FAILED
RECOVERY_REQUIRED(resume PREPARED/COPYING_IMAGES/FILES_READY) -> ROLLING_BACK
RECOVERY_REQUIRED(resume COMMITTING_COLLECTION, exact baseline) -> ROLLING_BACK
RECOVERY_REQUIRED(resume COMMITTING_COLLECTION, exact prospective) -> COLLECTION_COMMITTED
RECOVERY_REQUIRED(resume COLLECTION_COMMITTED) -> COLLECTION_COMMITTED
RECOVERY_REQUIRED(resume ROLLING_BACK) -> ROLLING_BACK
ROLLBACK_FAILED(resume ROLLING_BACK) -> ROLLING_BACK after ownership is proven again
PREPARED/COPYING_IMAGES/FILES_READY -> ROLLING_BACK
COMMITTING_COLLECTION(exact baseline only) -> ROLLING_BACK
```

`RECOVERY_REQUIRED` may continue only by the listed exit whose predicate is
proved; it is not a general escape hatch. A same-phase generation may only record
one failed attempt. `ROLLBACK_FAILED` is entered only from `ROLLING_BACK`, or from
`RECOVERY_REQUIRED` whose `resume_phase` is `ROLLING_BACK`, after deletion of a
verified cleanup target fails while ownership evidence remains intact. Any
unlisted transition is forbidden.

### Forbidden transitions

- A final sanitized history record is immutable and has no outgoing transition.
- No state may skip the durable evidence required by an intermediate boundary.
- `PREPARED`, `COPYING_IMAGES`, or `FILES_READY` may not enter success compaction.
- `COMMITTING_COLLECTION` may not be treated as committed from reserved IDs alone.
- `COLLECTION_COMMITTED` may not enter success compaction until snapshot and
  baseline-backup cleanup have durable receipts and terminal audit material no
  longer depends on either artifact.
- A state with any unverified managed-image object may not become `FILES_READY`.
- Rollback may not delete collection records merely because their IDs collide.
- Recovery may not infer progress from timestamps, PID liveness, pathname
  existence, or an exception-free call alone.

### Persistence order for a transition

Every durable transition follows this order:

1. Hold the global import lock and reverify its identity and ownership token.
2. Rebind the journal directory and current generation by held identity.
3. Verify the current generation chain and all evidence required by the source state.
4. Build canonical next-generation bytes in memory and validate the complete schema.
5. Persist the next immutable generation with the durable-write protocol.
6. Verify exact published bytes, generation linkage, and parent identity.
7. Only then perform the external side effect authorized by that generation.
8. Persist a later generation recording the verified result.

The write-ahead generation therefore describes intent before an irreversible
side effect, and the following generation records its outcome. Same-phase
progress is a new generation, never an in-place semantic mutation.

## Journal storage and lifecycle

### Layout

Operational records live below `data/imports/journals/`; sanitized terminal
history lives separately below `data/imports/history/`. Each active import uses
one ownership-bound journal directory and immutable generation files:

```text
data/imports/journals/<import-id>/
    owner.json
    00000000-<transition-id>.json
    00000001-<transition-id>.json
    ...
```

Generation `n` is published as exactly
`<n-as-eight-decimal-digits>-<transition-id>.json`. Its same-directory temporary
name is exactly `.next-<n-as-eight-decimal-digits>-<token>.tmp`. A token is a
cryptographically random UUIDv4 lowercase canonical string generated by the
approved injected provider; it must be unique within the owner record and complete
chain. Filenames are ASCII and never inferred from timestamps or directory order.

Every operational generation except the final `READY_FOR_TERMINAL` H commits the
token for generation `n + 1` in
`next_generation_token`; that commitment becomes durable with the generation.
The token authorizes only the one exact next temporary name. A successor advances
the intent by carrying a fresh token for its own successor. Tokens are never
cleared by rewriting immutable generations. Consumption is represented by the
unique valid successor and absence of the predecessor-authorized temp. The final
`COMPACTING` head sets the field to null because terminal publication, not another
generation, is the next authority boundary.

Recovery validates a candidate's parent identity, exact name/token, regular-file
type, held identity, byte bound, complete canonical schema, generation number,
predecessor hash, immutable fields, and legal transition. A partial candidate may
be deleted as a cleanup-authorized incomplete candidate. One complete valid
candidate is published idempotently. No candidate means the predecessor remains
the head. A published successor with no candidate is authoritative. Both a
candidate and successor, multiple candidates, a conflicting successor, or any
uncommitted name is ambiguous and blocks recovery.

### Creation

The journal root, import directory, and owner record are created exclusively,
one path component at a time, after ancestor and reparse checks. Generation zero
is `PREPARED`. It is not accepted as durable until its exact bytes and the parent
namespace are durable and its hash matches the owner record's genesis commitment.

The owner record is immutable and commits the genesis generation, not the moving
chain head. Its schema is exactly:

| Field | Rule |
| --- | --- |
| `owner_schema_version` | String `1.0` |
| `journal_schema_version` | String `2.0` |
| `import_id` | Same canonical UUID as every generation |
| `random_ownership_token` | Same canonical UUID as every generation |
| `created_at` | Normalized UTC RFC 3339 timestamp |
| `genesis_filename` | Exact generation-zero basename |
| `genesis_sha256` | SHA-256 of the exact canonical generation-zero bytes |
| `genesis_temporary_token` | Canonical UUIDv4 authorizing only the genesis temp |
| `genesis_temporary_name` | Exact `.next-00000000-<token>.tmp` basename |

Creation precomputes and validates generation-zero bytes, including its fresh
`next_generation_token`, transition ID, final filename, SHA-256, and the distinct
genesis temporary token/name. It exclusively creates the import directory, writes
and syncs `owner.json`, syncs the directory, then creates the exact genesis temp,
writes/syncs/verifies it, publishes it no-overwrite, and syncs the directory. The
immutable owner intent is never physically cleared; an exact published genesis and
absent temp mean it is logically consumed. A crash
after the owner is durable but before genesis publication leaves an incomplete
journal directory, not a valid chain. It may be removed only as a
cleanup-authorized incomplete candidate after the owner, token, parent identity,
expected genesis name/hash, and complete directory inventory are proven. Any
extra object or substitution blocks cleanup.

Startup classifies genesis state exactly:

| Owner/genesis evidence | Decision |
| --- | --- |
| No import directory | No journal ever created |
| Partial/invalid owner | Preserve and block; ownership is unprovable |
| Valid owner; no temp; no genesis | Planned genesis not created; durably remove the owner and otherwise empty owned directory; no transaction journal exists |
| Valid owner; partial exact temp; no genesis | Delete only the proven incomplete candidate, then durably remove owner and empty directory; no transaction journal exists |
| Valid owner; complete valid temp; no genesis | Publish, sync, and verify genesis |
| Valid owner; exact genesis; no temp | Genesis is authoritative |
| Valid owner; exact genesis and any temp, conflicting genesis, multiple candidate, or unexpected member | Preserve and block |

An interruption during direct owner-record creation can leave bytes too incomplete
to prove the token or intended target. Such a directory is intentionally not an
incomplete candidate: startup preserves it and blocks automatic import until a
deliberate evidence-preserving recovery procedure is authorized. This availability
cost is preferable to guessing ownership. The expanded matrix must cover partial
journal and snapshot owner records explicitly.

If journal creation fails before generation zero becomes durable, no journal
exists for recovery purposes. Any cleanup-authorized incomplete candidate is
handled by temporary-file reconciliation; the snapshot remains preparation workspace.

### Generation selection

Startup validates all generations in lexical generation order. The authoritative
head is discovered only from generations; `owner.json` is never rewritten to
point at it. It is the longest unique contiguous sequence beginning at the
owner-committed genesis whose hashes, predecessor links, import ID, ownership
token, and immutable fields all match.
Two valid candidates for one next generation, a gap, a broken link, or a valid
record after an invalid one is ambiguous and blocks imports. Recovery never picks
the newest timestamp or filename as a tie-breaker.

## Sanitized terminal history

Operational generations and terminal audit state are separate durable structures.
The sole terminal authority is a `TerminalHistoryRecord` at
`data/imports/history/<import-id>.json`. The deterministic pending authority is
`data/imports/history/.pending-<import-id>.json`. Both contain identical canonical
bytes. A pending record authorizes retirement but is not exposed as completed
history; the final basename denotes privacy-complete terminalization.

### Closed terminal schema

`TerminalHistoryRecord` is canonical JSON, at most 1048576 UTF-8 bytes, with
exactly these keys:

| Field | Exact rule |
| --- | --- |
| `terminal_schema_version` | String `1.0` |
| `import_id` | Canonical UUID and terminal transaction identifier |
| `final_phase` | `SUCCEEDED`, `ROLLED_BACK`, or `CANCELLED` |
| `result` | Matching `ImportResult` value |
| `transaction_created_at`, `completed_at` | Normalized UTC RFC 3339; completion is not earlier |
| `package_sha256`, `package_version`, `package_basename` | Immutable sanitized package provenance; version `1.0`, safe basename only |
| `proposed_count`, `imported_count`, `skipped_count` | Integers 0–100 agreeing with the audit and outcome |
| `collection_proof` | Closed `TerminalCollectionProof` |
| `managed_image_proof` | Closed `TerminalManagedImageProof` |
| `cleanup_summaries` | Ordered array of 1–3 `TerminalCleanupSummary` values |
| `outcome_payload_sha256` | SHA-256 of canonical JSON containing exactly every terminal field except `outcome_payload_sha256` and `operational_chain_proof`; this must equal H's commitment |
| `operational_chain_proof` | Closed `OperationalChainProof` |
| `audit` | Closed path-free `SanitizedTerminalAudit` schema 1.0 |
| `error_category` | Sanitized schema-2 category or null; no raw message |

Nested terminal objects are closed:

| Object | Exact keys and rules |
| --- | --- |
| `TerminalCollectionProof` | Exactly `outcome` (`PUBLISHED` or `UNCHANGED`), `baseline_sha256_or_sentinel`, `baseline_byte_length`, `final_sha256_or_sentinel`, `final_byte_length`, `committed_item_count`, `committed_item_ids_sha256`; missing baseline/final uses `MISSING_COLLECTION_V1` with zero bytes; ID digest hashes the canonical ordered ID array, including empty |
| `TerminalManagedImageProof` | `outcome` (`RETAINED`, `REMOVED`, or `NONE`), `image_count`, `aggregate_sha256`; the aggregate hashes canonical ordered role/length/content-digest tuples without paths |
| `TerminalCleanupSummary` | `category` (`BASELINE_BACKUP`, `SUCCESS_SNAPSHOT`, or `ROLLBACK_ALL`), `result` (`COMPLETED`), `target_count`, `receipt_count`, `intent_generation`, `completed_generation`, `aggregate_sha256`; the aggregate hashes canonical root-kind-length-content-digest and removal-identity-hash tuples with every path and raw identity omitted |
| `OperationalChainProof` | Exactly `manifest_generation_count` (integer 1–4095), `manifest_head_sha256` (G), `compaction_commit_generation` (H=G+1, integer 1–4095), `compaction_commit_transition_id` (UUIDv4), `compaction_commit_byte_length` (integer 1–1048576), `compaction_commit_sha256` (exact H bytes), `compaction_commit_object_identity_sha256`, `owner_record_sha256`, `owner_token_sha256`, `operational_directory_identity_sha256`, `terminal_object_identity_sha256`, `retirement_manifest_identity_sha256`, `retirement_manifest_byte_length` (integer 1–1048576), `retirement_manifest_sha256`; every digest is lowercase SHA-256 and no field is nullable |
| `SanitizedTerminalAudit` | Exactly `audit_schema_version` (`2.0`), `import_id`, `started_at`, `completed_at`, `package_filename_basename`, `package_sha256`, `schema`, `package_version`, `created_by`, `created_with`, `exported_at`, `session_id`, `session_name`, `session_description`, `session_date`, `session_created_at`, `session_updated_at`, `coin_provenance`, `proposed_count`, `imported_count`, `skipped_count`, `phase`, `final_status`, `error_category`; values retain AuditSession 1.0 validation except the path-free coin type, and phase/result match the terminal record |
| `SanitizedTerminalCoin` | Exactly `source_coin_id`, `desktop_item_id`, `decision`, `source_position`, `mint`, `composition`, `is_bullion`, `actual_silver_weight_oz`, `source_created_at`, `source_updated_at`, `source_quantity`, `image_role_hashes`; value rules equal `AuditCoin` 1.0 and no managed path key exists |

The terminal record never contains snapshot, temporary, backup, managed-image, or
operational recovery paths; raw ownership/lock tokens; hostnames; process IDs; raw
native identities; logs; exception strings; or serialized operational descriptors.
Opaque SHA-256 commitments, counts, phases, categories, and sanitized audit facts
are permitted. Cleanup summaries are derived only from complete operational
cleanup operations and are validated against their receipts before compaction.
The path-bearing operational `AuditSession` is transformed deterministically into
`SanitizedTerminalAudit`; validation rejects any nested `managed_image_paths` key
or unknown field.

There is no terminal cleanup-failure record. Cleanup or retirement failure remains
operational (`ROLLBACK_FAILED`, process-level blocked, or pending retirement) with
its detailed evidence until resolved. Consequently every terminal cleanup summary
has result `COMPLETED`; failure proof is never compacted into a misleading final
outcome.

`final_phase` and `result` must be identical enum values. `SUCCEEDED` requires a
null error category, published collection proof, and retained managed-image proof.
`ROLLED_BACK` requires unchanged collection proof and removed/none managed-image
proof; it may retain one sanitized initiating error category. `CANCELLED` requires
unchanged collection proof, removed/none managed-image proof, and null error.
`completed_at` is the canonical timestamp persisted in G and copied unchanged
through H and terminal bytes; compaction never calls a later independent clock.

### Terminal-compaction eligibility

Success is eligible only after exact collection publication, managed-image
verification, baseline-backup cleanup when applicable, snapshot cleanup, complete
pending audit, and zero unresolved recovery artifact. Rollback/cancellation is
eligible only after exact baseline/collection proof, complete `ROLLBACK_ALL`, no
managed image or snapshot artifact, and complete pending audit. The active
directory must contain exactly `owner.json` and the contiguous generation chain;
no temp, backup, unexplained, or partial candidate may remain.

`RECOVERY_REQUIRED` and `ROLLBACK_FAILED` are never compacted. A valid chain must
first reach the uniquely proven success/rollback path and satisfy eligibility.

### Compaction state machine

```text
Eligible operational outcome
    -> COMPACTING / PLANNING_MANIFEST generation G durable
    -> retirement manifest durable and verified
    -> sanitized outcome payload canonicalized and hashed
    -> COMPACTING / READY_FOR_TERMINAL generation H durable
    -> sanitized terminal temp containing exact H proof created, written, synced, and verified
    -> pending terminal record published, directory-synced, and verified
    -> active directory renamed no-overwrite to deterministic retirement name
    -> operational generations, owner, and manifest retired idempotently
    -> retirement directory removal durably confirmed
    -> pending terminal record renamed no-overwrite to final history name
    -> final record directory-synced and verified
    -> privacy-complete terminal state
```

The first `COMPACTING` generation G contains a non-null token for its one planned
successor H, null snapshot and collection artifact descriptors, complete
operational cleanup operations, pending terminal audit, and the
`PLANNING_MANIFEST` compaction object. H is the final operational generation,
contains the `READY_FOR_TERMINAL` object and `next_generation_token = null`, and
commits the exact manifest and sanitized outcome payload. Compaction names are exactly:

```text
terminal_pending_name = .pending-<import-id>.json
terminal_temporary_name = .pending-<import-id>-<terminal-token>.tmp
retirement_directory_name = .retire-<import-id>
retirement_manifest_name = retirement-manifest.json
retirement_manifest_temporary_name = .retirement-manifest-<retirement-token>.tmp
```

`TerminalCompaction` also records the verified history/journal parent identities,
active operational-directory identity, owner-record hash, manifest generation
range `0..G`, exact count, and planned H generation/transition/filename. G's hash
is computed after it is durable and committed by the manifest and terminal record.
H commits the exact path-free outcome payload. The later terminal record commits
H's exact bytes/identity and repeats that payload, avoiding a self-hash cycle.
Tokens are UUIDv4 values unique
from every journal token. Names are ASCII, fixed-root-relative basenames, and never
accepted from enumeration alone.

### Retirement manifest

The retirement manifest is canonical JSON schema `1.0`, at most 1048576 bytes,
with exactly `schema_version`, `import_id`, `random_ownership_token_sha256`,
`operational_directory_identity`, `owner_record`, `generations`, and
`compaction_commit`. Its nested schemas are closed:

| Object | Exact keys and rules |
| --- | --- |
| `owner_record` | `basename` (exact `owner.json`), `byte_length` (integer 1–1048576), `sha256` (lowercase SHA-256), `object_identity` (`ObjectIdentity`) |
| `generations[]` | Ordered array of 1–4095 objects, each exactly `generation` (integer 0–4094), `transition_id` (UUIDv4), `basename` (exact derived generation filename), `byte_length` (integer 1–1048576), `sha256`, `object_identity`; entries are contiguous 0 through G |
| `compaction_commit` | Exactly `generation` (H=G+1, integer 1–4095), `transition_id` (UUIDv4), `basename` (exact planned H filename); it has no H length/hash/identity because H does not yet exist when the immutable manifest is published |

No field is nullable. The import ID and ownership-token hash equal G; directory
identity equals the held active directory; all listed bytes and identities are
reverified before publication. The manifest lists no object outside that directory
and does not list itself. Its temporary target is authorized by G. Partial temp
bytes are cleanup-only; one complete manifest
must equal a fresh exact inventory before no-overwrite publication and directory
sync. Extra members, a conflicting manifest, or identity drift blocks compaction.

### Sanitized record publication

After manifest verification, the implementation deterministically constructs the
closed outcome payload from G, audit, cleanup receipts, collection proof, and
managed-image proof. G authorizes H; H matches the manifest's planned generation,
transition, and filename and commits the manifest triple plus exact outcome-payload
hash. After H is durable, the implementation reopens H by held active-directory
identity, verifies its exact bytes, link to G, transition, and native identity, and
constructs `OperationalChainProof` from that evidence. It exclusively creates the
H-authorized terminal temp, captures its held identity, constructs canonical
terminal bytes containing the outcome payload and exact H proof, writes and syncs
them, and verifies both its self-identity commitment and canonical content. It then
publishes the same terminal object no-overwrite to the
pending name, syncs the history directory according to the platform contract, and
reopens/verifies the pending object. A partial temp is cleanup-only; a complete
matching temp may be promoted; a conflict or multiple candidate blocks.

The verified pending record becomes replay authority before any operational
generation is removed. No separate log or in-memory flag has authority.

### Generation-chain retirement

While holding the global lock, recovery verifies the pending record, manifest,
owner/token hash, active directory identity, and complete chain commitment. It
renames the complete active directory no-overwrite from `<import-id>` to
`.retire-<import-id>` in the same journal parent, makes that namespace step durable,
and reopens the retirement directory by identity. A pre-existing retirement name,
both names present, or identity mismatch blocks retirement.

Retirement deletes by held parent-relative identity in this fixed order:

1. H, verified as G's unique legal successor and against the exact H
   byte-length/SHA-256/object-identity proof in the pending record;
2. manifest-listed generation files from G down to zero;
3. `owner.json`;
4. `retirement-manifest.json` last;
5. the verified empty retirement directory;
6. durable sync of the journal parent.

The pending record authorizes deletion of exact H; the manifest authorizes each
generation 0..G and owner deletion. The manifest remains until all its listed
artifacts are absent. After a crash with partial retirement, the pending record's
exact H proof establishes whether H is the one permitted first absence, and its
manifest digest plus the still-present manifest authorize deletion of the
remaining exact suffix; already absent entries are accepted only in the prescribed
order. An unexpected member, out-of-order absence, replaced identity, undeletable
object, missing manifest before all listed files are gone, or changed parent blocks
and preserves evidence. If only an empty verified retirement directory remains
after manifest deletion, the pending record's hashed directory identity and the
empty inventory authorize its removal. Repeating any completed step is a no-op.

After durable retirement, the pending history record is renamed no-overwrite to
`<import-id>.json`, the history directory is synced, and the final object is
reopened and verified. The pending and final names may never coexist. Only then is
the result visible as `SUCCEEDED`, `ROLLED_BACK`, or `CANCELLED` history.

### Replay authority precedence

| Durable evidence | Authority and action |
| --- | --- |
| No pending/final record; valid active chain before `COMPACTING` | Active head; resume operational recovery |
| No pending/final record; G and manifest temp/record | G is authority; reconcile exact manifest and publish the uniquely authorized H; a terminal temp at G is unexplained and blocks |
| H; terminal temp absent | H is authority; reconstruct its committed outcome payload, create the exact authorized terminal temp, and bind the temp to exact H proof |
| H; partial terminal temp | H is authority; delete only the identity-bound authorized partial, recreate, sync, and verify it |
| H; complete terminal temp | H is authority; require canonical payload, exact H proof, self-identity, and bounded bytes, then publish pending no-overwrite |
| Exact pending record; complete active directory | Pending record; verify chain/manifest, then rename to retirement |
| Exact pending record; exact retirement directory | Pending record plus manifest; resume ordered retirement |
| Exact pending record; empty verified retirement directory, manifest already retired last | Pending record plus directory-identity hash; remove directory and sync parent |
| Exact pending record; neither active nor retirement directory | Pending record; finalize no-overwrite to terminal history |
| Exact final record; no active/pending/retirement artifact | Final record; privacy-complete, no mutation |
| Exact final record plus a reappeared exact active or retirement directory after a Windows crash | Final record; imports stay disabled while the matching manifest/chain is identity-bound and retirement is repeated, then final remains authoritative |
| Pending and final both present; terminal conflict; multiple candidates; active and retirement names both present; orphan retirement without matching pending/final record | Ambiguous; preserve all evidence and block for operator intervention |

### Journal and history enumeration

Enumeration occurs only under the global lock through held, verified journal and
history parent handles. The journal parent accepts only active canonical UUID
directory names and deterministic `.retire-<uuid>` directories. The history parent
accepts only final `<uuid>.json`, pending `.pending-<uuid>.json`, and a terminal
temp whose exact name/token is committed by that import's final H. Any other member,
duplicate canonical UUID, normalization/case collision, link/reparse object,
unexpected file type, or count beyond `MAX_IMPORT_STATE_MEMBERS`
blocks the entire recovery pass.

The index is built for every import ID before mutation. Final, pending, active,
retirement, and terminal-temp members are grouped, then evaluated only by the
precedence table. Retirement names are not orphans eligible for generic cleanup;
without one exact matching pending/final record they are preserved and block.
Likewise, a terminal temp without the exact active H intent is preserved and blocks.
Logs and exception records never participate in enumeration or authority.

Inside an active directory, normal phases permit only `owner.json`, contiguous
generation files, and at most the one predecessor-authorized next-generation temp.
G additionally permits its one manifest temp or published manifest and its one
terminal temp. H permits the published manifest and exact terminal temp until that
object becomes pending. A retirement directory permits H, manifest-listed
generations/owner, and the manifest in only the prescribed retirement suffix.
Every other member or phase/member combination blocks.

A final record conflicting with a surviving active chain is never reconciled by
timestamp. If it exactly matches that chain's compaction commitment, it has
precedence only after its publication and parent-durability protocol is verified;
otherwise the process-level blocked result applies.

### Terminal privacy rules

Operational paths may exist only in an active or retirement directory while
recovery is incomplete. They must never be copied into terminal JSON, user-visible
logs, error records, or exception text. Terminal cleanup proof uses aggregate
commitments only. Crash remnants outside the exact active, retirement, snapshot,
managed-image, collection-parent, and history roots are never adopted.

A prohibited path or raw token found in a pending/final terminal candidate is a
privacy violation: preserve the candidate, do not publish or expose it, emit a
sanitized process-level blocked diagnostic, and require operator intervention.
A final history file is accepted only when no prohibited operational artifact
remains, except the explicitly recoverable Windows reappearance case above.

## Snapshot lifecycle

### Creation and verification

The snapshot service creates a random-token directory exclusively beneath the
trusted snapshot root after validating every existing ancestor. It creates the
owner record and package file with no-follow, no-overwrite semantics. Source and
snapshot are consumed through bounded streams; size, exact length, and SHA-256
must agree with the accepted package. The package file is flushed and synced,
then its directory entry is made durable according to the platform protocol.

Before package bytes are copied, the service durably creates an immutable owner
record containing the preparation ID, random token, exact package target basename,
accepted source length/SHA-256, and `creation_state = COPYING`. The package target
is then created exclusively. If copying is interrupted, that exact regular file
and owner record form a cleanup-authorized incomplete candidate: cleanup requires
the original parent handle, matching token, matching target name, matching held
identity, and an inventory containing no unexpected object. After complete byte
verification and syncing, a new immutable completion receipt is exclusively
published with `creation_state = COMPLETE` and the verified package identity.
Only that receipt upgrades the package to a complete owned artifact. Unknown
tokens, partial owner records, unexpected objects, or substituted identities are
preserved and block cleanup.

### Ownership and lease

Ownership requires all of:

- canonical containment beneath the configured snapshot root;
- an exact schema-valid owner record;
- matching import or preparation ID and cryptographically random token;
- matching parent and object native identities captured from open no-follow handles;
- exact package length and SHA-256;
- a successfully acquired advisory lease on the package object.

The lease revalidates root, parent, owner, lease, and package identity before
yield, before every sensitive use, on exceptional exit, and before close. A path
or parent replacement never transfers ownership to the replacement.

### Cleanup

Cleanup uses held identities and parent-relative operations. It removes only the
objects in the verified ownership inventory. Before terminal success or rollback:

1. persist complete terminal material and a cleanup intent;
2. acquire and verify the snapshot lease and every owned identity;
3. remove owned children and snapshot directory without following replacements;
4. make the parent namespace removal durable;
5. persist a cleanup receipt that no longer depends on the removed snapshot;
6. enter `COMPACTING` only after every required cleanup operation is complete.

A crash after cleanup intent but before removal repeats verified cleanup. A crash
after durable removal but before its receipt may infer completion only from the
specific cleanup intent plus absence under the same verified parent identity and
complete pre-persisted terminal material. Any parent change or replacement is
ambiguous and remains nonterminal.

### Orphans

Startup enumerates journals and snapshots from one view while holding the global
lock. Journal-referenced snapshots are never classified as orphans. An unreferenced
snapshot may be removed only after its owner schema, containment, token, identities,
exact bytes, and exclusive lease are proven. PID liveness neither grants nor
denies ownership. Apparently live or otherwise uncertain ownership raises
`SnapshotRecoveryRequired`; no deletion, adoption, or silent skip occurs.

## Managed-image lifecycle

Before copying, the journal durably records the complete expected inventory. Each
file is created exclusively in the import-owned root, copied through a bounded
stream, flushed and synced, reopened or rewound through its held identity, and
verified for exact length, SHA-256, format, dimensions, and decode. Its verified
identity and content facts are recorded in a later journal generation before the
next file begins.

`FILES_READY` requires every expected image and no unexpected object. Immediately
before collection persistence, all opened managed-image handles are compared with
the identities captured during inventory and their exact bytes are reverified.
Replacement, addition, removal, or ambiguity fails closed. Rollback removes only
the verified import-owned root after recording rollback intent and durably confirms
the removal before entering compaction for `ROLLED_BACK` or `CANCELLED` history.

## Collection durable-write protocol

### Preconditions

The transaction holds the import lock, reloads the exact collection bytes, and
requires their length and SHA-256 to match the preview baseline. It serializes the
complete prospective collection once into canonical bytes. Before writing those
bytes, a `COMMITTING_COLLECTION` generation durably records:

- baseline sentinel or exact byte length and SHA-256;
- prospective exact byte length and SHA-256;
- complete reserved desktop IDs;
- verified managed-image inventory;
- transition ID and write token.

### Temporary write and publication

1. Verify and hold the collection parent-directory identity.
2. Create a random, owner-qualified temporary regular file in that same directory
   with exclusive, no-follow semantics.
3. Write the bounded prospective bytes completely; handle short writes.
4. Flush the language/runtime buffer and sync the file (`fsync` or
   `FlushFileBuffers`).
5. Read through the held handle and verify exact length, SHA-256, and canonical
   bytes. Do not accept parsed-object equality.
6. Reverify the parent, destination, journal head, lock, baseline, and temp identity.
7. Atomically exchange or replace the destination while retaining a verified
   displaced baseline object until the new destination is proven.
8. Open or retain the published object without following links; verify identity
   and exact bytes against the prospective commitment.
9. Make the containing-directory namespace update durable.
10. Persist a `COLLECTION_COMMITTED` generation containing the verified outcome.
11. Only then remove the displaced baseline object, and durably sync that namespace
    cleanup. If removal fails, preserve it as owned recovery evidence.

The collection object is never deleted before the prospective replacement is
durable. Replacement and cleanup operate on verified identities, not unresolved
pathnames. A pre-existing temporary or backup name is a collision, never reusable.

### Crash interpretation

`D`, `T`, and `B` mean destination, prospective temporary object, and displaced
baseline/backup. Every “exact” value includes bytes and the identity committed by
the write intent. “Absent” must be observed under the same verified parent handle.
The table is exhaustive; any unlisted combination is blocked.

| Baseline | Durable head | D | T | B | Required action |
| --- | --- | --- | --- | --- | --- |
| Existing exact bytes | Before `INTENT` | Baseline | Absent | Absent | No publication recovery; normal execution may begin |
| Existing exact bytes | `INTENT` | Baseline | Absent or cleanup-authorized incomplete candidate | Absent | Publication did not occur; durably remove candidate if present, then roll back |
| Existing exact bytes | `INTENT` | Baseline | Complete prospective | Absent | Publication not attempted; policy is rollback, not retry, after a crash |
| Existing exact bytes | `INTENT` | Baseline | Absent or cleanup-authorized incomplete candidate | Exact baseline backup | Windows backup publication started; verify backup, durably clean candidate then backup, and roll back |
| Existing exact bytes | `INTENT` | Baseline | Complete prospective | Exact baseline backup | Windows backup is verified but replacement did not occur; durably clean temp then backup and roll back |
| Existing exact bytes | `INTENT` with temp `VERIFIED`, backup `PLANNED` | Prospective | Exact displaced baseline | Absent | Linux/macOS exchange occurred; verify both identities/bytes and parent, persist both descriptors as `EXCHANGED`, then make namespace durable |
| Existing exact bytes | `INTENT` | Prospective | Absent | Exact baseline backup | Windows replacement occurred; verify both, persist `VERIFIED`, continue commit |
| Existing exact bytes | `INTENT` with both descriptors `EXCHANGED` | Prospective | Exact displaced baseline | Absent | Reverify exchanged identities, sync namespace, then persist `COLLECTION_COMMITTED` with temp `PUBLISHED` and backup `RETAINED` |
| Existing exact bytes | `VERIFIED` | Prospective | Exact displaced baseline or absent with cleanup receipt | Absent | Continue or confirm backup-cleanup protocol |
| Existing exact bytes | `VERIFIED` | Prospective | Absent | Exact baseline backup or absent with cleanup receipt | Continue or confirm backup-cleanup protocol |
| Existing exact bytes | Any | Missing, baseline, or third-party bytes in any other combination | Any | Any | Preserve evidence and block |
| Missing sentinel | Before `INTENT` | Absent | Absent | Absent | No publication recovery; normal execution may begin |
| Missing sentinel | `INTENT` | Absent | Absent or cleanup-authorized incomplete candidate | Absent | Publication did not occur; durably remove candidate if present, then roll back |
| Missing sentinel | `INTENT` | Absent | Complete prospective | Absent | Publication not attempted; policy is rollback after a crash |
| Missing sentinel | `INTENT` | Prospective | Absent | Absent | No-overwrite publication occurred; verify exact destination, persist `VERIFIED`, continue commit |
| Missing sentinel | `VERIFIED` | Prospective | Absent | Absent | Continue committed recovery |
| Missing sentinel | Any | Baseline-impossible or third-party bytes | Any | Any | Preserve evidence and block |

For an existing baseline, the displaced object remains until a
`BASELINE_BACKUP` cleanup-intent generation is durable. Recovery then verifies
the prospective destination and displaced baseline again, removes exactly the
intent target, durably syncs the namespace, and writes its cleanup receipt. A
crash before the intent preserves the backup; after the intent it repeats the
same verified deletion; after the receipt it requires the target to be absent
under the same parent identity. Success compaction is forbidden until this receipt
and the snapshot cleanup receipt are complete.

On Windows, backup creation is itself an intent-governed substep of
`COMMITTING_COLLECTION`. The commit-intent generation names the exact backup
target before `CreateHardLinkW`. After the call, the implementation reopens the
backup, requires baseline identity and bytes, and completes the platform namespace
step before replacement. A crash before backup creation observes `B = absent`; a
crash during publication observes either absent or the exact baseline backup; a
third-party or partial object is blocked. If destination still equals baseline,
recovery first persists the legal `COMMITTING_COLLECTION -> ROLLING_BACK`
transition while retaining the exact temp/backup descriptors. Only then does it
append one `ROLLBACK_ALL` cleanup operation whose ordered targets are the verified
temp candidate, verified backup, managed artifacts, and snapshot artifacts in the
schema-defined order. It removes and receipts each target under `ROLLING_BACK`,
then enters compaction for final `ROLLED_BACK` history. It never creates a cleanup operation while still in
`COMMITTING_COLLECTION` and never retries `ReplaceFileW` after restart.

Reserved IDs are supporting evidence only. They never substitute for exact-byte
verification and never authorize treating an unrelated record as this import.

## General durable-write protocol

The collection protocol also governs mutable control records where replacement is
unavoidable. Immutable journal generations prefer exclusive publication and do
not overwrite an existing generation.

### Required guarantees

- Temporary and destination files reside on the same supported filesystem.
- Every write is bounded and checked for complete consumption.
- File content is synced before namespace publication.
- Publication is atomic with respect to observers on the supported filesystem.
- The destination is verified by exact bytes and held identity after publication.
- Namespace changes are durably synchronized before their result is journalled.
- The displaced object remains available until the replacement is proven.
- Cleanup of temp/backup objects is ownership-bound and itself durably recorded.

An implementation may use a stronger primitive than specified. It may not silently
downgrade to copy-and-delete, pathname-only `os.replace`, or a best-effort flush.

## Temporary-file reconciliation

Startup examines reserved temporary and displaced names only while holding the
global lock and verified directory handles. It validates the name, owner token,
native identity, exact bytes, and journal transition commitment.

- A partial or malformed temp with an unchanged destination may be deleted only
  when it satisfies the cleanup-authorized incomplete-candidate proof and the
  deletion is durably synced.
- One complete temp matching the uniquely expected next action may be published or
  retained for the deterministic recovery action.
- A prospective destination with the verified baseline displaced object means
  publication occurred and can be finalized after exact verification.
- Multiple candidates, an unexpected destination, an unknown token, a missing
  required displaced object, or identity substitution is ambiguous.

Ambiguous objects are preserved. Recovery records a sanitized category and blocks
new imports; it never chooses by modification time or deletes unknown files.

## Recovery model

### Startup recovery

Before import is enabled, the coordinator acquires the global import lock. While
holding it, recovery:

1. binds history, journal, snapshot, managed-image, and collection parent directories;
2. enumerates final terminal records, pending terminal records, active transaction
   directories, and retirement directories into one import-ID-indexed view;
3. applies the replay-authority precedence table and fails on every conflict;
4. validates every authoritative active chain or sanitized terminal record;
5. reconciles only intent-authorized generation, manifest, terminal, collection,
   and backup temporary artifacts;
6. resumes operational recovery or compaction in deterministic import-ID order;
7. builds the complete set of authoritative journal-referenced snapshots;
8. reconciles orphan snapshots from that same lock-protected view;
9. accepts final terminal history only after privacy-complete artifact checks;
10. releases the lock only after a safe privacy-complete result or explicit blocked result.

Enumeration before lock acquisition is forbidden.

### Phase recovery

- `PREPARED`, `COPYING_IMAGES`, and `FILES_READY`: verify the snapshot and owned
  image inventory, then roll back unless a later durable intent uniquely proves
  that progress must continue.
- `COMMITTING_COLLECTION`: compare exact collection bytes with baseline and
  prospective commitments. Baseline permits rollback; prospective requires
  commit finalization; any other bytes require recovery.
- `COLLECTION_COMMITTED`: verify prospective collection bytes, exact managed
  images, terminal material, and cleanup evidence; complete snapshot cleanup and
  enter compaction.
- `ROLLING_BACK`: repeat verified compensating deletion and persist its receipts.
- `RECOVERY_REQUIRED` or `ROLLBACK_FAILED`: continue only after the original
  ambiguity or cleanup failure is demonstrably resolved.
- `COMPACTING`: reconcile the exact manifest and pending terminal publication; once
  pending is authoritative, resume retirement according to its manifest.
- Final terminal history: perform no mutation unless an exact Windows namespace
  reappearance is present, in which case disable imports and finish only the
  identity-bound retirement authorized by the final record.

### Interrupted and repeated recovery

Recovery uses the same write-ahead transitions as normal execution. A crash at
any recovery boundary leaves a prior durable generation or a uniquely reconcilable
next generation. Attempt counters advance in new generations. After pending
terminal publication, recovery advances retirement without creating generations.
Repeating recovery from unchanged evidence yields the same action and, once
privacy-complete, byte-stable final history with no further writes.

### Failure semantics

`RECOVERY_REQUIRED` is a journal phase only when the owner record and complete
generation chain through the current head are valid and a new generation can be
published safely. It records ambiguity in external evidence such as collection,
snapshot, or managed-image state. `ROLLBACK_FAILED` is likewise valid only on a
trusted chain when verified owned cleanup fails.

A corrupt owner record, corrupt generation zero, broken/forked chain, replaced
journal directory, or inability to publish the next generation produces a
process-level **blocked recovery result**, not a manufactured journal phase. The
implementation preserves every byte, emits only a sanitized non-journal diagnostic,
disables imports, and performs no recovery mutation. Unsupported filesystem,
uncertain object identity, replacement, third-party collection bytes, incomplete
durable sync, or conflicting candidates follow the same blocked behavior unless a
valid chain can safely record `RECOVERY_REQUIRED`.

## Locking and cancellation model

### Ownership

One service-level `PackageImportCoordinator` owns the execution and recovery
lease. Lower services accept that verified lease; they do not reacquire it. All
application collection writers use the same global `PackageImportLock`.

### Lock order

The only permitted acquisition order is:

```text
in-process coordinator gate
    -> global package-import lock
    -> verified parent-directory handles
    -> journal generation handles
    -> snapshot lease
    -> managed-image handles
    -> collection/temp/backup handles
```

Handles are released in reverse order. No callback, UI action, recovery routine,
or collection saver may acquire an earlier lock while holding a later one.

### Timeouts

Lock wait values are finite, non-negative, and no greater than the documented
maximum. Deadline calculation uses a monotonic clock. `NaN`, infinities, negative
values, overflow, and one-past-maximum values are rejected. Timeout returns the
sanitized `IMPORT_LOCKED` category and does not alter the existing lock.

### Stale locks

PID or hostname evidence alone never authorizes removal. Automatic stale-lock
clearing is prohibited. Deliberate recovery requires the approved ownership,
advisory-lock, identity, containment, and user-confirmation procedure.

### Cancellation

Cancellation is immediate only before the first durable transaction generation.
After `PREPARED`, cancellation is a cooperative request observed at documented
safe boundaries. It transitions through `ROLLING_BACK`; it never interrupts a
file write, publication, sync, or journal transition. Cancellation is disabled
during collection publication and is reported only after durable compensation.

## Persistence invariants

1. No managed image or collection mutation occurs before `PREPARED` is durable.
2. No `FILES_READY` state exists without a complete exact verified image inventory.
3. No collection publication occurs before its baseline and prospective exact-byte
   commitments are durable.
4. A collection commit is recognized by exact prospective bytes, not parsed JSON
   equality, reserved IDs, timestamps, or path existence.
5. No pending terminal record is published before required snapshot, backup, and
   rollback cleanup is durably confirmed.
6. Irreversible cleanup occurs only after recovery no longer depends on the artifact,
   or after complete replacement evidence is durably preserved elsewhere.
7. Every mutation remains bound to verified object and parent-directory identities.
8. A pathname replacement never inherits ownership from the replaced object.
9. Recovery decisions are deterministic and idempotent.
10. Ambiguous ownership, state, order, bytes, or platform guarantees fail closed.
11. Journal generations are immutable, contiguous, hash-linked, and uniquely headed.
12. A durable intent precedes every external side effect; a later generation records
    its verified outcome.
13. Pending and final terminal history contain no private source, snapshot,
    temporary, backup, managed-image, recovery, or absolute path.
14. Final terminal history is immutable; repeated recovery performs no work except
    identity-bound cleanup of a platform namespace reappearance it already proves.
15. Journal and snapshot enumeration occur under the same global lock-protected view.
16. Journal-referenced snapshots are never orphan candidates.
17. PID liveness is neither ownership proof nor permission to skip reconciliation.
18. Cleanup deletes only a complete verified ownership inventory and never broadens
    its target after an error.
19. File data is synced before publication; namespace publication is durably synced
    before the outcome is journalled.
20. Temporary, backup, and displaced objects are never silently reused or discarded.
21. All reads, writes, decoding, serialization, and recovery enumeration are bounded.
22. Raw path-bearing or hostile exception text is never persisted or shown.
23. The same lock serializes startup recovery, imports, and all application collection
    writers.
24. Unsupported filesystem semantics block mutation rather than reducing guarantees.
25. Every generation temporary is named and authorized by a token durably committed
    in its predecessor or immutable genesis owner record.
26. Native object identity is null for a planned artifact, becomes mandatory only
    after creation, and is never inferred from its planned pathname.
27. A pending sanitized terminal record becomes retirement authority before any
    operational generation is deleted.
28. The retirement manifest remains until every listed operational artifact is
    absent in the prescribed order.
29. A transaction is not privacy-complete while a pending record, active chain,
    retirement directory, or prohibited operational artifact remains.
30. Cleanup details are transformed into path-free aggregate terminal proofs;
    operational descriptors are never copied into sanitized history.
31. A POSIX displaced-baseline descriptor has no identity before exchange; the
    prospective and baseline relationships advance to `EXCHANGED` together only
    after both post-exchange objects are exactly verified.
32. H is never deleted until an exact pending terminal record durably commits H's
    byte length, SHA-256, and object-identity hash and reproduces H's committed
    sanitized outcome payload.

## Platform guarantees and fail-closed policy

### Windows

The initial supported target is a local NTFS volume. SMB, ReFS, FAT-family media,
cloud placeholders, and reparse-containing roots are unsupported until qualified.
At startup the implementation obtains the volume filesystem name and flags, opens
every root with `CreateFileW(FILE_FLAG_BACKUP_SEMANTICS |
FILE_FLAG_OPEN_REPARSE_POINT)`, rejects reparse attributes, and captures volume
serial number plus 128-bit file ID with `GetFileInformationByHandleEx`.

Files are opened with `FILE_FLAG_OPEN_REPARSE_POINT`, compatible sharing limited
to the operation, and identities captured from held handles. File bytes are
synced with `FlushFileBuffers` before publication.

- **Exclusive immutable publication or missing collection:** call
  `MoveFileExW(temp, destination, MOVEFILE_WRITE_THROUGH)` without
  `MOVEFILE_REPLACE_EXISTING`. A concurrent destination causes failure. Reopen and
  verify destination identity and exact bytes.
- **Existing collection:** create a token-qualified baseline backup with
  `CreateHardLinkW`, reopen it and require the same volume/file ID as the held
  baseline, then call `ReplaceFileW(destination, temp, null, 0, null, null)`.
  Reopen and verify exact prospective destination bytes and require the hard-link
  backup still identifies the baseline. The backup is removed only by the durable
  cleanup-intent protocol.
- **Deletion:** require `SetFileInformationByHandle(FileDispositionInfoEx)` with
  `FILE_DISPOSITION_FLAG_DELETE | FILE_DISPOSITION_FLAG_POSIX_SEMANTICS |
  FILE_DISPOSITION_FLAG_IGNORE_READONLY_ATTRIBUTE` on the verified held target.
  Close it and verify absence plus unchanged parent identity. If the API or flags
  are unavailable, deletion requiring a receipt is unsupported and mutation fails
  closed; there is no pathname-based fallback. `MoveFileExW(...,
  MOVEFILE_WRITE_THROUGH)` is used for namespace publication, not as evidence of
  content correctness.

Windows provides no portable directory-`fsync` equivalent for these user-mode
operations, and `ReplaceFileW`'s write-through flag is unsupported. Therefore the
v0.2 Windows guarantee is atomicity and deterministic recovery after application
or operating-system crash once the documented APIs return; it does **not** claim
survival of sudden power loss for the final namespace operation. NTFS journal
replay may restore either pre- or post-operation namespace after power loss. On
startup, exact journal/temp/backup evidence must reconcile either state; if it
cannot, imports remain blocked. The product and tests must label this narrower
guarantee. Claiming power-loss durability on Windows requires a later approved
volume-flush design and fault-injection evidence.

### Linux

The supported target is a local filesystem for which regular-file and directory
`fsync` plus same-directory `renameat2` semantics pass the startup capability test.
Roots are opened parent-relatively with `openat2` resolution constraints where
available, otherwise component-by-component `openat` using `O_NOFOLLOW |
O_DIRECTORY`; device/inode identity is captured from held descriptors.

- Write and `fsync` the temp file.
- For no-overwrite publication call `renameat2(..., RENAME_NOREPLACE)`, reopen and
  verify exact destination bytes, then `fsync` the parent directory.
- For an existing collection call `renameat2(temp, destination, RENAME_EXCHANGE)`.
  Before the call, the temporary descriptor is `VERIFIED` and the backup descriptor
  is `PLANNED` with null identity. Verify prospective destination and displaced
  baseline now at the temp name, capture both post-exchange identities, and persist
  one generation containing both `EXCHANGED` descriptors. Then `fsync` the parent,
  reverify, and publish the collection outcome. Keep the displaced object through
  the verified-outcome generation.
- For deletion call `unlinkat` relative to the held parent after identity
  verification, then `fsync` the parent before writing a cleanup receipt.

Failure or absence of `renameat2`, required flags, regular-file `fsync`, directory
`fsync`, same-device identity, or the startup capability test blocks mutation.
Mount points, cross-device replacement, network filesystems, and externally
synchronized roots are unsupported.

### macOS

The supported target is local APFS after the capability test below succeeds. Open
ancestors and targets parent-relatively with `O_NOFOLLOW`; bind device/inode from
held descriptors and reject mount crossings.

- Write the temp file, call `fsync`, then `fcntl(F_FULLFSYNC)`. Failure of
  `F_FULLFSYNC` means the power-loss contract is unavailable and blocks mutation.
- For no-overwrite publication call `renameatx_np(..., RENAME_EXCL)`.
- For an existing collection call `renameatx_np(temp, destination, RENAME_SWAP)`
  so the displaced baseline remains at the temp name. Before the call, only the
  prospective descriptor is `VERIFIED`; the backup is `PLANNED` with null identity.
- Reopen and verify exact identities/bytes, persist both post-swap descriptors as
  `EXCHANGED`, then `fsync` the parent directory, reverify, and publish the outcome.
- Delete only by parent-relative `unlinkat` after identity verification and `fsync`
  the parent before writing its cleanup receipt.

Absence or failure of `renameatx_np`, `RENAME_EXCL`, `RENAME_SWAP`, `F_FULLFSYNC`,
directory `fsync`, or same-volume behavior blocks mutation. These paths must run
in macOS CI and real APFS tests before macOS execution support is enabled.

### Capability test

Before enabling mutation, a versioned capability probe runs once per data-root
volume in a dedicated, exclusively created probe directory while holding the
global import lock. It verifies no-overwrite publication, existing-file exchange
or replacement with displaced-byte retention, exact-byte reopening, identity
stability, required file sync, required directory sync, deletion, and cleanup.
The probe stores only a version, volume identity, filesystem type, platform build,
and pass/fail category; it contains no user data. Probe failure, an unknown volume,
or a changed platform/filesystem invalidates the cached result and disables
mutation. The probe cannot prove sudden power-loss behavior; that claim additionally
requires the explicit platform guarantee and CI/hardware fault testing above.

### Common unsupported conditions

FAT-family/removable media without proven guarantees, network shares, cloud-synced
active data roots, cross-volume publication, filesystems with unstable object IDs,
and environments that prohibit required handles or syncing are outside the supported
mutation contract. Read-only preview may remain available, but import execution is
disabled with a sanitized `UNSUPPORTED_DURABILITY_ENVIRONMENT` diagnostic. This
category must be added in the separately authorized implementation/schema phase.

### Compaction and retirement primitives

The active-to-retirement rename is always within the journal parent. Terminal
temp-to-pending and pending-to-final publication are always within the history
parent. Cross-volume moves are forbidden.

- **Windows/NTFS:** use `MoveFileExW` without replace and with
  `MOVEFILE_WRITE_THROUGH` for all three no-overwrite renames. Open roots and
  candidates with reparse-point protection and verify volume/file IDs before and
  after. Retirement deletion requires the handle-based disposition contract
  already specified. Open or delete-pending handles that prevent rename/deletion
  leave the pending record authoritative and recovery blocked/retryable; no
  pathname fallback exists. The narrower Windows sudden-power-loss limitation
  applies: startup may observe pre- or post-rename namespace and must select only
  an exact precedence-table state.
- **Linux:** use `renameat2(RENAME_NOREPLACE)` relative to held parent descriptors,
  followed by parent `fsync`; retire with `unlinkat`/`rmdir` and parent-directory
  `fsync` after each prescribed boundary. Device/inode verification is mandatory.
- **macOS/APFS:** use `renameatx_np(RENAME_EXCL)`, required file sync/
  `F_FULLFSYNC`, directory `fsync`, and parent-relative unlink/rmdir. The complete
  compaction path must execute in macOS CI and real APFS validation before support
  is enabled.

Failure of a rename, required sync, identity check, or capability probe preserves
the current authority artifact and blocks. No platform may emulate no-overwrite
publication with delete-then-rename.

## Recovery matrix mapping

The detailed executable scenarios live in
[DESKTOP_PACKAGE_IMPORT_RECOVERY_MATRIX.md](../DESKTOP_PACKAGE_IMPORT_RECOVERY_MATRIX.md).
The mapping below assigns every current scenario to a durable phase and invariant.
“Blocked” is intentionally nonterminal.

| ID | Transaction phase | Injected failure | Recovery action | Expected terminal state | Invariants |
| --- | --- | --- | --- | --- | --- |
| RM-01 | Before `PREPARED` | Journal creation interrupted | Reconcile only a proven owned temp | No journal; no terminal state | 1, 10, 20 |
| RM-02 | `PREPARED` | Crash after generation zero | Verify snapshot and compensate | `ROLLED_BACK` | 5, 9, 12 |
| RM-03 | Any operational transition | Predecessor-authorized next-generation temp interrupted | Reconcile exact token/name: delete partial, publish one complete legal successor, accept published successor, or block conflict | Phase-dependent compaction/final outcome or blocked | 9–12, 20, 25 |
| RM-04 | `COPYING_IMAGES` | Crash after transition publication | Verify zero/partial inventory and compensate | `ROLLED_BACK` | 7, 9, 12, 18 |
| RM-05 | Preparation | Snapshot source rejected before creation | Perform no recovery mutation | No transaction or terminal state | 1, 21 |
| RM-06 | Preparation | Snapshot copy interrupted | Remove only proven partial owned state | No transaction or terminal state | 7, 18, 21 |
| RM-07 | Preparation | Crash after verified snapshot creation | Retain valid workspace or clean it through orphan rules | No transaction; workspace reconciled | 7, 16–18 |
| RM-08 | Before `PREPARED` | Under-lock snapshot revalidation fails | Abort and reconcile owned snapshot | No terminal transaction state | 1, 7, 10 |
| RM-09 | Before `PREPARED` | Package changes during held lease | Preserve ambiguous evidence and block | Blocked | 7, 8, 10 |
| RM-10 | Before `PREPARED` | Collection baseline changed | Abort without transaction mutation | No terminal transaction state | 1, 3, 10 |
| RM-11 | `COPYING_IMAGES` | Persisted image bytes corrupt | Reject `FILES_READY`, verify ownership, compensate | `ROLLED_BACK` or blocked | 2, 7, 10 |
| RM-12 | `COPYING_IMAGES` | Crash after first image receipt | Verify journalled identity and compensate | `ROLLED_BACK` | 7, 9, 18 |
| RM-13 | `COPYING_IMAGES` | Crash after complete inventory, before phase change | Verify all images and compensate under current policy | `ROLLED_BACK` | 2, 9, 12 |
| RM-14 | `COPYING_IMAGES` | Crash before `FILES_READY` | Use durable inventory; compensate | `ROLLED_BACK` | 2, 9, 18 |
| RM-15 | `FILES_READY` | Crash before metadata intent | Verify images, then compensate | `ROLLED_BACK` | 2, 6, 9 |
| RM-16 | `COMMITTING_COLLECTION` | Prospective temp verified; Windows backup may be verified, POSIX backup remains planned; destination remains baseline | Exact descriptors prove publication absent; enter `ROLLING_BACK`, receipt only artifacts that exist, then compact | Final `ROLLED_BACK` history | 3, 4, 12, 26–31 |
| RM-17 | `COMMITTING_COLLECTION` | Publication returns ambiguously before outcome generation | Apply exhaustive D/T/B bytes, identity, and descriptor table; exact POSIX exchange advances both descriptors together, baseline rolls back, other state blocks | Final `SUCCEEDED`, `ROLLED_BACK`, or blocked | 3, 4, 9, 20, 26, 31 |
| RM-18 | `COMMITTING_COLLECTION` | Destination is exact prospective; Windows retained backup or POSIX `EXCHANGED` pair; outcome generation absent | Verify destination, displaced baseline, images, parent durability, and exact bytes; advance once to committed cleanup/compaction | Final `SUCCEEDED` history | 2–5, 9, 26–31 |
| RM-19 | `COLLECTION_COMMITTED` | Crash before cleanup intent | Use exact intact snapshot/backup and append required cleanup operation(s) | Pending then final `SUCCEEDED` after compaction | 5, 6, 12, 27–32 |
| RM-20 | `COLLECTION_COMMITTED` or `ROLLING_BACK` | Crash during cleanup receipts | Resume only the final operation's next exact target; ambiguity blocks | Final success/rollback only after all receipts and compaction | 5–10, 18, 27–32 |
| RM-21 | Cleanup complete | Crash at any G, manifest, H, terminal-temp, or pending publication boundary | Active chain remains authority until exact pending record with H proof is verified | Pending then final outcome, or blocked | 5, 6, 9, 12, 27–32 |
| RM-22 | `ROLLING_BACK` | Crash after cleanup complete but before terminal audit history | Build path-free rollback proof, enter compaction, retire chain | Final `ROLLED_BACK` history | 5, 6, 18, 27–32 |
| RM-23 | Pending/final success history | Crash during retirement or rerun after finalization | Pending resumes ordered retirement using exact H proof and manifest; final with no remnants is inert | Final `SUCCEEDED` | 9, 14, 27–32 |
| RM-24 | Pending/final rollback history | Repeat recovery during/after retirement | Resume exact remaining suffix; final history is byte-stable | Final `ROLLED_BACK` | 9, 14, 27–32 |
| RM-25 | `ROLLING_BACK` or pending retirement | Recovery interrupted | Resume from unique active head or pending authority and exact manifest progress | Final `ROLLED_BACK` or blocked | 9, 11, 12, 27–32 |
| RM-26 | Any recoverable operational/compaction boundary | Recovery interrupted repeatedly | Consume generations before pending; afterward repeat manifest-governed retirement | Deterministic final outcome or blocked | 9, 11, 12, 25–32 |
| RM-27 | Final success history | Startup after privacy-complete success | Verify sanitized record and absence of prohibited remnants | Unchanged `SUCCEEDED` | 9, 14, 29, 30, 32 |
| RM-28 | Final rollback history | Startup after privacy-complete rollback | Verify sanitized record and absence of prohibited remnants | Unchanged `ROLLED_BACK` | 9, 14, 29, 30, 32 |
| RM-29 | Before `PREPARED` or recovery | Unrelated record uses a reserved desktop ID | Use exact-byte commitments; preserve unrelated record | No false success; rollback or blocked | 4, 10 |
| RM-30 | Snapshot cleanup | Owner record corrupt | Preserve snapshot and block deletion | Blocked | 7, 10, 18 |
| RM-31 | Any snapshot-required phase | Referenced snapshot missing | Require a matching cleanup intent/receipt; otherwise preserve journal | Blocked unless intended absence is uniquely proven | 5, 6, 10 |
| RM-32 | Startup orphan pass | Proven unreferenced snapshot | Acquire lease, verify full ownership, remove durably | No transaction terminal state | 7, 15–18 |
| RM-33 | Snapshot lease | Journal/snapshot bytes disagree | Preserve evidence and block | Blocked | 7, 10, 16 |
| RM-34 | `COPYING_IMAGES` or later | Managed image replaced after inventory | Preserve replacement and block | Blocked | 2, 7, 8, 10 |
| RM-35 | Any cleanup/publication | Destination pathname replaced | Continue only with held original identity; preserve replacement | Blocked unless original operation can be safely completed | 7, 8, 10 |
| RM-36 | Lock acquisition | Another owner holds a valid live lock | Wait boundedly, then refuse | No transaction state change | 17, 23 |
| RM-37 | Import start | Valid lock already exists | Do not enter transaction | No transaction state change | 1, 23 |
| RM-38 | Lock release/recovery | Metadata, token, or identity uncertain | Preserve lock evidence and block | Blocked | 10, 17, 23 |
| RM-39 | Recovery start | Import owner holds lock | Bounded refusal; do not enumerate or mutate | No recovery state change | 15, 23 |
| RM-40 | Windows identity check | Reparse substitution attempted | Reject the substitution; an uncreatable fixture is an explicit platform skip, never a pass | Blocked on actual substitution | 7, 8, 24 |
| RM-41 | POSIX/macOS journal publication | Destination substituted before exchange | Restore or preserve the unexpected object; accept only exact unique evidence | Blocked unless safely restored | 7–12, 20, 24 |

### Amended crash-contract details

| RM | Durable precondition and candidate artifacts | Injected interruption | Authoritative evidence and verification | Recovery, retained artifacts, and privacy result |
| --- | --- | --- | --- | --- |
| RM-03 | Valid predecessor commits exact next token/name; candidate absent, partial, complete, or already published | Any next-generation temp write/sync/publish/directory-sync boundary | Predecessor, held parent identity, exact candidate bytes/identity, successor link | Partial is deleted only as authorized; complete legal successor is published; published successor wins; conflicts block. Final history contains no candidate name. |
| RM-16 | `COMMITTING_COLLECTION` intent; exact baseline destination; temporary verified; Windows backup planned/created/verified or POSIX backup still planned | Crash before collection publication | Active head, exact D/T/B table, descriptor tokens, bytes, identities, and parent | Enter `ROLLING_BACK`; one `ROLLBACK_ALL` receipts every object that actually exists, images, and snapshot. Compact to sanitized rollback; no operational artifact retained. |
| RM-17 | Windows required artifacts verified, or POSIX prospective verified plus baseline held and backup planned; collection intent durable | Crash during platform replace/exchange or before directory durability | Active head plus exact destination/temp/backup layout; return code is non-authoritative | Baseline layout rolls back; exact prospective/displaced layout advances both POSIX descriptors atomically to `EXCHANGED`; third state blocks. Subsequent compaction retains only aggregate proofs. |
| RM-18 | Destination exactly prospective; Windows backup verified or POSIX pair `EXCHANGED`; outcome generation absent | Crash before `COLLECTION_COMMITTED` generation | Prospective exact bytes/identity, exact retained baseline identity, parent durability, image inventory | Reverify/sync, persist `COLLECTION_COMMITTED` once with `PUBLISHED`/`RETAINED`, then clean and compact. No duplicate IDs or operational paths. |
| RM-19 | `COLLECTION_COMMITTED`; complete pending audit; intact verified cleanup targets | Crash before first cleanup intent | Active head and exact target identities | Append next cleanup operation, receipt targets, enter compaction, publish final success. Only sanitized summaries remain. |
| RM-20 | Cleanup operation `INTENT` with an ordered receipt prefix | Crash before/after one target deletion or namespace sync | Active head, held parent identity, target descriptor, receipt prefix, exact presence/absence | Resume only next target. Intended absence after verified sync may receive the next receipt; replacement/ordering ambiguity blocks. |
| RM-21 | All cleanup complete; active chain eligible for compaction | Crash during final compaction generation, manifest temp/publication, or terminal temp/publication | Active head until exact pending terminal record is verified | Reconcile authorized generation/manifest/terminal candidate. Once pending is verified, it becomes retirement authority. Prohibited paths remain only operationally. |
| RM-22 | `ROLLING_BACK`; `ROLLBACK_ALL` complete; collection equals exact baseline/sentinel | Crash before pending rollback history | Active chain, complete cleanup receipts, exact collection proof, pending audit | Construct path-free rollback record, publish pending, retire chain, finalize. No operational path survives. |
| RM-23 | Exact pending success record with active or retirement directory, or exact final success record | Crash during any retirement/finalization step | Pending record, manifest, owner-token hash, directory-identity hash; final record only after retirement | Resume ordered retirement or accept inert final. Retain final record and managed images referenced by collection only. |
| RM-24 | Exact pending rollback record with partial retirement, or exact final rollback | Repeat startup recovery | Same pending/manifest precedence and ordered absence proof | Delete only remaining exact retirement suffix, finalize once, then byte-stable no-op. No managed/snapshot artifact remains. |
| RM-25 | Operational rollback head or pending record; recovery progress durable | Crash after any recovery generation or retirement deletion | Active chain before pending; pending+manifest afterward | Resume the one next transition/deletion. Final rollback or process-level blocked result; evidence preserved on ambiguity. |
| RM-26 | Same evidence replayed across multiple interruptions | Repeated crashes at successive boundaries | Generation number/token uniqueness, then immutable pending authority and manifest progress | Identical evidence yields identical action; no duplicate collection/image/history effect; generation exhaustion blocks explicitly. |
| RM-27 | Exact final success record; no pending, active, or retirement artifact | Startup | Final canonical bytes and fixed-root absence checks | No mutation; final success remains authoritative and privacy-complete. A proved Windows reappearance temporarily blocks and resumes retirement. |
| RM-28 | Exact final rollback/cancel record; no pending, active, or retirement artifact | Startup | Final canonical bytes and fixed-root absence checks | No mutation; final rollback/cancel remains authoritative and privacy-complete. |

#### RM-19 through RM-28 durability-boundary expansion

Each subcase below is a distinct mandatory crash-injection scenario. `0..G,H`
means the complete active chain with exact H present; `0..G` means H's permitted
first absence is proven by the pending record. `P` and `F` mean exact pending and
final terminal records. `M` means the verified manifest; `R[k]` means the
retirement directory with the prescribed first `k` deletion steps durably
complete. Every row starts under the global lock with verified parent identities.

| Subcase | Exact durable artifacts before restart | Interrupted boundary | Replay authority and deterministic action | Required final/artifact/privacy assertion |
| --- | --- | --- | --- | --- |
| RM-19.a | Active `0..head=COLLECTION_COMMITTED`; no cleanup intent; no terminal/M | Before first cleanup-intent generation | Active head; append exactly the required first intent | Final success; only collection/managed images/sanitized F remain |
| RM-19.b | Active head with cleanup `INTENT`, zero receipts | After intent publication | Active head and target identities; execute only target zero | Same final result; no unjournalled deletion |
| RM-20.a | Active intent; next exact target present | Before held-identity deletion | Active head; reverify then delete | Advance one receipt only after namespace durability |
| RM-20.b | Active intent; target absent; parent sync not proven | After unlink/delete call, before parent durability | Active head; platform outcome table; prove absence/durability or block | Never infer a receipt from pathname absence alone |
| RM-20.c | Active intent; target absence durable; receipt not published | After parent sync, before receipt generation | Active head plus verified absence; publish exactly one receipt | No duplicate receipt or out-of-order target |
| RM-20.d | Active intent with strict receipt prefix | Between targets | Active head; resume the unique next target | Final receipt count equals target count |
| RM-20.e | Fully receipted `INTENT`; `completed_generation` is null | After the final receipt generation and before the distinct completion generation | Active head; perform no deletion or target/receipt mutation; publish only `status = COMPLETE` with `completed_generation` equal to the current successor generation | Cleanup summary later matches the exact unchanged target/receipt aggregate |
| RM-21.a | Cleanup complete; no G candidate, no M/terminal | Before G temp creation | Active cleanup head; create G through predecessor token | Active chain remains sole authority |
| RM-21.b | Cleanup head; partial or complete authorized G temp | G write/sync/publish boundary | Predecessor; delete partial or publish one exact G | One G only; conflict blocks |
| RM-21.c | Active `0..G`; no manifest candidate | After G durable | G; create exact manifest temp | No terminal artifact is legal yet |
| RM-21.d | Active `0..G`; partial/complete manifest temp | Manifest write/file-sync boundary | G; delete partial or verify/publish complete candidate | M exact or no M; ambiguity blocks |
| RM-21.e | Active `0..G`; M visible, parent sync uncertain | Manifest rename/directory-sync boundary | G plus exact M identity/bytes; establish durability or block | M must match fresh inventory 0..G |
| RM-21.f | Active `0..G`; verified M; authorized H temp absent/partial/complete | H generation boundary | G token and M; reconcile H by normal generation rules | Exact active `0..G,H`; H commits payload hash |
| RM-21.g | Active `0..G,H`; no terminal temp | Before terminal-temp creation | H; create exact named temp and bind its identity | Terminal bytes include exact H proof |
| RM-21.h | Active `0..G,H`; partial terminal temp | Terminal write/file-sync boundary | H; delete only authorized partial and recreate | No partial terminal candidate accepted |
| RM-21.i | Active `0..G,H`; complete verified terminal temp; no P | Before terminal no-overwrite publication | H; reverify payload/H/self-identity and publish | P bytes exactly equal verified temp |
| RM-21.j | Active `0..G,H`; terminal temp renamed to P; history sync uncertain | Pending rename/directory-sync boundary | H plus exact candidate; establish P durability or block | Active authority does not retire yet |
| RM-21.k | Active `0..G,H`; verified P and M | After pending verification | P becomes authority; begin retirement | Operational paths remain only until retirement completes |
| RM-22.a | Rollback cleanup complete; no G | Before rollback G | Rollback active head; execute RM-21.a through RM-21.k with rollback payload | P/F result `ROLLED_BACK`; no managed/snapshot artifact |
| RM-22.b | Cancellation cleanup complete; no G | Before cancellation G | Cancellation active head; execute RM-21.a through RM-21.k with cancel payload | P/F result `CANCELLED`; null error category |
| RM-23.a | Success P + active `0..G,H` + M | Before active-to-retirement rename | P; verify full chain and rename no-overwrite | Exactly one active/retirement name |
| RM-23.b | Success P + exact active or retirement name; namespace sync uncertain | Rename/directory-sync boundary | P and directory identity; establish one exact retirement directory or block | No inferred rename result |
| RM-23.c | Success P + `R[0]` containing `0..G,H`, owner, M | Before H deletion | P exact H proof; delete H first | `R[1]` has `0..G`, owner, M |
| RM-23.d | Success P + `R[1]` | After H deletion | P proves H's one legal absence; M authorizes G | Delete G next, never another member |
| RM-23.e | Success P + `R[k]` during G..0 reverse deletion | Any generation deletion/sync boundary | P+M and ordered absence prefix | Resume exactly next descending generation |
| RM-23.f | Success P + retirement containing owner and M only | Before/after owner deletion | P+M; verify owner hash/identity, delete and sync | M remains last authority inside directory |
| RM-23.g | Success P + retirement containing M only | Before/after manifest deletion | P+M; verify all prior permitted absences, delete/sync M | Retirement directory must then be empty |
| RM-23.h | Success P + empty verified retirement directory | Before/after directory removal and parent sync | P plus committed directory-identity hash | Remove/sync directory; no operational artifact remains |
| RM-23.i | Success P, no operational artifact; F absent | Before pending-to-final rename | P; publish final no-overwrite | P or F, never both |
| RM-23.j | Final basename visible; history sync/verification uncertain | Final rename/directory-sync boundary | Exact terminal bytes; establish durable F or block | Final success is privacy-complete only after verification |
| RM-24.a | Rollback/cancel P + active or `R[k]` | Any RM-23.a through RM-23.j boundary | Same P/manifest/H-proof precedence | Final rollback/cancel; no collection/image side effect |
| RM-24.b | Exact rollback/cancel F only | Repeated startup | F | Byte-stable no-op and fixed-root absence proof |
| RM-25.a | Operational recovery generation candidate before P | Recovery interrupted at generation boundary | Current predecessor | Reconcile one successor; evidence preserved on ambiguity |
| RM-25.b | P plus `R[k]` | Recovery interrupted at retirement boundary | P plus M/H proof | Resume one prescribed deletion; no new generation |
| RM-26.a | Same pre-P evidence replayed repeatedly | Repeated process interruption | Unique active head/token | Identical one-next action; no duplicated collection/image effect |
| RM-26.b | Same post-P evidence replayed repeatedly | Repeated process interruption | Immutable P and ordered retirement prefix | Identical deletion/finalization; no duplicate history |
| RM-26.c | Head 4094 without legal closure reserve use, or malformed H at 4095 | Generation exhaustion boundary | Valid head plus numeric limit | Block with `JOURNAL_GENERATION_EXHAUSTED`; delete nothing |
| RM-27.a | Exact success F; no P/active/retirement | Normal startup | F | No mutation; privacy-complete success |
| RM-27.b | Exact success F plus provably matching Windows reappearance | Power-loss namespace replay | F temporarily blocks completion; exact P-equivalent proof resumes retirement | Return to F-only or block; never expose operational path as terminal data |
| RM-28.a | Exact rollback/cancel F; no P/active/retirement | Normal/repeated startup | F | No mutation; privacy-complete rollback/cancel |
| RM-28.b | Exact rollback/cancel F plus any conflicting remnant | Unexpected enumeration | Conflict is not adopted | Preserve evidence and require operator intervention |

For RM-19 through RM-28, a test must assert the exact active generations present,
pending/final terminal artifacts, retirement directory/manifest progress,
authoritative artifact, retained collection/images, prohibited-path absence, and
idempotent second recovery pass. RM-03 and RM-16 through RM-18 additionally assert
the planned-versus-created-versus-verified nullability rules.

Every matrix test must additionally assert collection-ID uniqueness, no deletion
outside verified roots, sanitized errors, expected artifact retention/removal, and
idempotent repeated recovery. The implementation phase shall expand the matrix when
this architecture introduces a new durable boundary; a boundary without a crash
test is incomplete.

### Matrix contract migration

The current recovery-matrix document predates journal schema 2.0. Until a separate
documentation/test phase revises it, it is a scenario inventory rather than an
executable acceptance contract for the target durability implementation. This
document supersedes the expected action and state for:

- RM-01 through RM-04 (immutable generation and temp reconciliation);
- RM-08 through RM-10 (under-lock pre-journal evidence);
- RM-11 through RM-15 (exact managed-image inventory generations);
- RM-16 through RM-18 and RM-29 (exact-byte collection intent/outcome rather than
  reserved-ID inference);
- RM-19 through RM-22 and RM-31 (cleanup intent/receipt semantics);
- RM-25, RM-26, and RM-30 through RM-35 (valid-chain versus process-level blocked
  recovery and identity evidence);
- RM-36 through RM-41 (service-level locking and platform-specific primitives).

Before implementation validation, those rows and their referenced tests must be
updated. New rows are required for every owner/genesis write, temp sync, generation
publication, directory sync, collection exchange/replacement, outcome generation,
backup cleanup intent/unlink/sync/receipt, snapshot cleanup boundary, capability
failure, and legacy-version case. Existing test names do not constitute evidence
for the new semantics until the tests assert those boundaries.

## Legacy journal policy

Schema 1 durable bytes are never reinterpreted as schema 2:

- A strictly valid schema 1 terminal `SUCCEEDED`, `ROLLED_BACK`, or `CANCELLED`
  journal is retained and exposed as read-only history. Schema 2 recovery performs
  no mutation on it.
- Any schema 1 nonterminal phase, including `RECOVERY_REQUIRED` or
  `ROLLBACK_FAILED`, blocks schema 2 import execution. Its fields do not contain the
  prospective exact-byte, generation, and cleanup-receipt evidence needed by this
  architecture, so automatic migration or recovery is forbidden.
- A corrupt or unknown-version record produces the process-level blocked result.
- A mixed root may enable schema 2 imports only when every schema 1 record is valid
  read-only terminal history and every schema 2 import ID has either one
  privacy-complete final record or a valid operational/pending state that startup
  successfully reconciles to one.
- No in-place or automatic migration is permitted. A future deliberately authorized
  legacy-recovery tool must preserve original bytes, operate under the global lock,
  and produce a separate audit record rather than rewriting history.

Startup enumerates and classifies all versions under the lock before temporary or
orphan reconciliation. A blocking legacy record prevents cleanup that could depend
on its missing evidence.

## Implementation and review gates

Production implementation may begin only under separate authorization. It shall:

1. version the journal schema rather than reinterpret existing durable bytes;
2. implement the legacy policy above without automatic active-journal migration;
3. implement one durable primitive at a time with injected crash boundaries;
4. run Windows and Linux full-suite CI plus macOS primitive tests;
5. prove all recovery-matrix paths execute on their relevant platform;
6. obtain independent review before any commit or push.

The design is implemented only when every persistence invariant is executable as a
test and no supported crash boundary relies on timing, pathname existence, PID
liveness, parsed-object equality, or undocumented filesystem behavior.
