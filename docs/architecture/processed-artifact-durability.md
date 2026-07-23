# Processed-Artifact Durability Specification

## Status and authority

This document is the normative Unit 7A successor contract for imports that make
Sprint 8 processed media durable. It extends, but never rewrites or reinterprets,
the legacy [Durable Persistence Architecture](durable-persistence.md), whose exact
bytes remain frozen at SHA-256
`A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4`.

Normative terms **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are used as
defined by RFC 2119. If this document does not explicitly replace a legacy rule,
that legacy rule remains normative. Schema 1 and Schema 2 bytes MUST NOT be
parsed as, migrated to, or recovered by the successor schemas.

This specification governs architecture only. It does not authorize production
code, tests, staging, commits, pushes, tags, or Unit 7B work.

## Scope and invariants

The processed-artifact snapshot is immutable coordinator-owned derived evidence.
It is separate from:

- the original immutable package snapshot;
- the temporary workflow workspace;
- managed collection images and collection JSON;
- operational journals and sanitized terminal history.

The following invariants are absolute:

1. Original package SHA-256, byte length, basename, package version, manifest,
   replay identity, and audit authority MUST remain unchanged.
2. Durable state MUST NOT depend on a workflow path, handle, native identity, or
   workspace lifetime.
3. Stages and the adapter MUST NOT create, adopt, delete, or own durable
   snapshots.
4. The coordinator is the sole processed-snapshot creator and owner before the
   transaction journal exists.
5. A transaction or recovery operation MUST consume only verified immutable
   snapshots through held, no-follow identities.
6. Processed media MUST NOT silently fall back to raw package media.
7. Every external side effect MUST be preceded by durable intent and followed
   by durable verified outcome evidence.
8. Ownership loss, identity ambiguity, unsupported platform behavior, or corrupt
   evidence MUST preserve artifacts and fail closed.
9. A processed snapshot handle and prepared import are single-use. A second
   transaction attempt MUST fail before mutation.
10. Terminal history MUST NOT contain workflow paths, snapshot paths, raw native
    identities, ownership tokens, process IDs, hostnames, or exception text.

## Schema and compatibility table

| Contract | Identifier | Applies to | Compatibility rule |
| --- | --- | --- | --- |
| Legacy operational journal | `2.0` | Imports without processed media | Exact legacy behavior; this specification does not alter it |
| Processed operational journal | `3.0` | Imports with a processed snapshot | Closed successor schema; never accepted by Schema 2 code |
| Legacy journal owner | `1.0` | Journal `2.0` | Unchanged |
| Processed journal owner | `2.0` | Journal `3.0` | Closed successor schema committing a Schema 3 genesis |
| Processed snapshot owner | `1.0` | Snapshot creation intent | Closed immutable schema |
| Processed snapshot manifest | `1.0` | Sealed artifact inventory | Closed canonical schema |
| Processed snapshot completion | `1.0` | Ownership and sealing receipt | Closed immutable schema |
| Processed-media commitment | `1.0` | Schema 3 operational proof plan | Closed immutable schema retained through compaction |
| Legacy terminal history | `1.0` | Journal `2.0` | Unchanged |
| Processed terminal history | `2.0` | Journal `3.0` | Adds path-free processed-media proof |
| Collection photo provenance | `1.0` | Imported `ItemPhoto` records | Additive optional field; mandatory for Schema 3 imports |

Unknown versions and unknown fields MUST be rejected. A mixed repository MAY
contain legacy terminal history, valid Schema 2 state, and valid Schema 3 state.
Startup MUST enumerate every version under the same global lock before mutation.
A nonterminal Schema 1 record, invalid Schema 2/3 record, or version conflict
blocks all import and recovery mutation.

## Canonical JSON

Every JSON object defined here MUST be serialized as:

- UTF-8 without BOM;
- NFC-normalized Unicode strings;
- non-ASCII Unicode scalar values emitted literally as UTF-8, never as
  `\uXXXX` surrogate pairs or escapes;
- `"` and `\` escaped as `\"` and `\\`; `/` is never escaped;
- U+0008, U+0009, U+000A, U+000C, and U+000D escaped as `\b`, `\t`, `\n`,
  `\f`, and `\r`; every other U+0000 through U+001F scalar escaped as
  `\u00xx` with lowercase hexadecimal digits;
- U+2028 and U+2029 emitted literally; unpaired surrogate code points are
  forbidden;
- object keys in ascending Unicode code-point order;
- arrays in the explicitly defined order;
- `,` and `:` separators without surrounding whitespace;
- no leading or trailing whitespace and no terminal newline;
- JSON `true`, `false`, and `null` for booleans and null;
- base-10 integers without leading plus signs or leading zeros, except `0`;
- no floating-point, exponent, `NaN`, or infinity values.

Duplicate JSON keys are invalid. Every object is closed. Unless a smaller bound
is stated, the legacy limits apply: nesting at most 8, at most 64 keys per
object, strings at most 16384 Unicode scalar values, aggregate string content at
most 262144 characters, and each canonical control object at most 1048576 bytes.

## Snapshot identity and layout

The processed-snapshot root is a trusted sibling of the raw snapshot root:

```text
data/imports/processed-snapshots/<processed-snapshot-id>/
    owner.json
    lease.lock
    artifacts/
        000-<sha256>.jpg
        ...
    manifest.json
    complete.json
```

`processed_snapshot_id`, `workflow_execution_id`, and `ownership_token` are
distinct canonical random UUIDv4 strings. The snapshot ID is operational and
not content-derived. `created_at` is a normalized UTC RFC 3339 timestamp produced
once by the injected coordinator clock; it is operational and MUST NOT drive
ordering, replay, duplicate detection, or recovery.

The root, owner, lease, artifacts directory, each artifact, manifest, and
completion receipt MUST have verified native identities captured from open
no-follow handles. Pathnames alone never establish ownership.

### Path and resource rules

- At most `MAX_COINS_PER_PACKAGE * MAX_IMAGES_PER_COIN` (currently 300)
  artifacts are permitted.
- Each artifact MUST be 1 through `MAX_IMAGE_SIZE` bytes (currently 41943040).
- Aggregate artifact bytes MUST be at most `MAX_TOTAL_UNCOMPRESSED_SIZE`
  (currently 268435456).
- Width and height MUST each be 1 through `MAX_IMAGE_DIMENSION` (currently
  12000), and their product MUST not exceed `MAX_IMAGE_PIXELS` (currently
  80000000).
- Snapshot-relative paths MUST be 1 through 1024 Unicode scalar values, use `/`,
  and contain no empty, `.`, or `..` component, control character, drive prefix,
  UNC prefix, alternate separator, trailing dot, or trailing space.
- The Windows-safe key is NFC followed by Unicode casefold and per-component
  trailing-dot/space rejection. Duplicate keys are invalid on every platform.
- Version 1.0 processed artifacts MUST be baseline, non-progressive
  `image/jpeg`. Any other content type, extension, magic, or decoded format is
  unsupported and fails before snapshot creation.
- Links, reparse points, mount crossings, sparse/placeholder files, devices,
  FIFOs, sockets, and non-regular files are forbidden.

No retry loop based on pathname availability is allowed. Exclusive creation
collisions fail closed.

## Processed artifact descriptor

`ProcessedArtifactDescriptor` contains exactly these keys:

| Field | Type and exact rule |
| --- | --- |
| `artifact_key` | NFC string, 1–255 characters; unique by Windows-safe key |
| `source_coin_id` | NFC string, 1–16384 characters; MUST identify one selected package coin |
| `role` | `front`, `reverse`, or `edge` |
| `variant` | `NORMALIZED` or `CROPPED` |
| `relative_path` | Exact `artifacts/<index-as-three-decimal-digits>-<sha256>.jpg` |
| `content_type` | String `image/jpeg` |
| `byte_length` | Integer 1–41943040 |
| `sha256` | Lowercase SHA-256 of exact artifact bytes |
| `width`, `height` | Integers 1–12000 whose product is at most 80000000 |
| `source_artifact` | Non-null closed `SourceArtifactLink` |

`SourceArtifactLink` contains exactly:

| Field | Type and exact rule |
| --- | --- |
| `package_media_relative_path` | Strict package-relative path already validated by the package contract |
| `package_media_sha256` | Lowercase SHA-256 committed by the validated original package media descriptor |

Descriptors MUST be sorted by:

```text
(source_coin_id NFC code-point order,
 role order front < reverse < edge,
 variant order CROPPED < NORMALIZED,
 artifact_key NFC code-point order)
```

The zero-based descriptor index determines `relative_path`. `artifact_key`,
`relative_path`, and `(source_coin_id, role)` MUST each be unique by their
canonical keys. Duplicate byte digests across distinct items are permitted
because duplicate policy remains a collector decision. A descriptor that does
not map to exactly one selected package-media item is invalid.

### Normative durable variant selection

The adapter supplies both normalization artifacts and the closed crop record for
each selected `(source_coin_id, role)`. The crop record contains exactly the
existing Unit 3 keys: `coin_id`, `role`, `x`, `y`, `width`, `height`,
`crop_confidence`, `crop_applied`, `source_normalized_key`, `source_width`, and
`source_height`. The durable selector MUST:

1. require exactly one normalized artifact, one cropped artifact, and one crop
   record for every selected package-media item;
2. require `crop_applied` to be a JSON boolean and `crop_confidence` to be a
   finite JSON number in `[0.0, 1.0]`;
3. require `crop_applied is true` if and only if
   `crop_confidence >= 0.65`, select `CROPPED` exactly in that case, and select
   `NORMALIZED` otherwise;
4. require `crop_applied is false` to have `crop_confidence == 0.0`, the
   full-normalized-image rectangle, and a cropped fallback whose exact bytes,
   dimensions, media type, and digest equal the normalized artifact;
5. take `artifact_key` verbatim from the selected `StageResult.artifacts` key,
   never derive it from a pathname; and
6. reject a missing, duplicate, unknown, inconsistent, non-JPEG, or replaced
   candidate before coordinator ownership transfer.

The comparison is inclusive at `0.65`, matching `MIN_CROP_CONFIDENCE`. The crop
stage always produces a cropped artifact; “fallback” describes a byte-identical
full-frame copy, not an absent artifact. This rule is the sole permitted Unit 7
variant-selection policy.

## Canonical manifest and aggregate identity

`ProcessedSnapshotManifest` contains exactly these keys:

| Field | Type and exact rule |
| --- | --- |
| `manifest_schema_version` | String `1.0` |
| `processed_snapshot_id` | Canonical UUIDv4 |
| `workflow_execution_id` | Canonical UUIDv4 |
| `ownership_token_sha256` | SHA-256 of UTF-8 canonical ownership-token text |
| `created_at` | Normalized UTC RFC 3339 |
| `source_package_sha256` | Exact original package SHA-256 |
| `source_package_byte_length` | Exact original package length, 1–268435456 |
| `source_package_version` | String `1.0` |
| `artifact_count` | Integer 1–300, equal to `artifacts` length |
| `aggregate_byte_length` | Integer 1–268435456, equal to descriptor-length sum |
| `artifact_inventory_sha256` | Inventory digest defined below |
| `artifacts` | Ordered descriptor array defined above |

The artifact inventory digest is:

```text
SHA256(
    UTF8("coin-analyzer.processed-artifact-inventory.v1") ||
    0x00 ||
    canonical_json(artifacts)
)
```

Artifact bytes are committed through each descriptor's SHA-256, not concatenated
directly into the aggregate. Verification MUST nevertheless stream and hash every
artifact byte. `manifest_sha256` is SHA-256 over the exact canonical manifest
bytes and therefore covers operational IDs/timestamp, original package linkage,
all descriptors, and the inventory digest.

## Owner and completion schemas

`ProcessedSnapshotOwner` is written before any artifact and contains exactly:

| Field | Type and exact rule |
| --- | --- |
| `owner_schema_version` | String `1.0` |
| `processed_snapshot_id`, `workflow_execution_id`, `ownership_token` | Distinct canonical UUIDv4 strings |
| `root_identity` | Non-null legacy `ObjectIdentity` captured from the held no-follow root handle before owner publication |
| `created_at` | Same timestamp as the planned manifest |
| `creation_state` | String `COPYING` |
| `manifest_name`, `completion_name`, `lease_name` | Exactly `manifest.json`, `complete.json`, `lease.lock` |
| `source_package_sha256`, `source_package_byte_length`, `source_package_version` | Exact original package evidence |
| `planned_manifest_byte_length`, `planned_manifest_sha256` | Exact precomputed canonical manifest commitment |
| `artifact_count`, `aggregate_byte_length`, `artifact_inventory_sha256` | Exact manifest values |
| `planned_artifacts` | Exact ordered manifest descriptor array |

The owner is immutable. It authorizes cleanup of only its exact predictable
inventory; it does not prove sealing.

`ProcessedSnapshotCompletion` contains exactly:

| Field | Type and exact rule |
| --- | --- |
| `completion_schema_version` | String `1.0` |
| `processed_snapshot_id`, `workflow_execution_id` | Exact owner values |
| `ownership_token_sha256` | SHA-256 of UTF-8 canonical ownership-token text |
| `root_identity`, `owner_identity`, `lease_identity`, `artifacts_directory_identity`, `manifest_identity` | Non-null legacy `ObjectIdentity` values |
| `owner_byte_length`, `owner_sha256` | Exact immutable owner-record length and SHA-256 |
| `manifest_byte_length`, `manifest_sha256` | Exact canonical manifest commitment |
| `artifact_count`, `aggregate_byte_length`, `artifact_inventory_sha256` | Exact manifest values |
| `artifact_objects` | Ordered `ProcessedArtifactObject` array |
| `sealed_at` | Normalized UTC RFC 3339 from the injected clock, not used for ordering |

`ProcessedArtifactObject` contains exactly `relative_path`, `byte_length`,
`sha256`, `parent_identity`, and `object_identity`; both identity fields are
non-null legacy `ObjectIdentity` values. Its ordered facts MUST equal
the corresponding manifest descriptors. The completion receipt excludes its own
identity and digest to avoid a self-reference. Those facts are captured in the
coordinator handle and Schema 3 journal reference.

`lease.lock` is an immutable zero-byte regular file. The coordinator creates it
no-follow, exclusively, and without overwrite after durable owner publication;
syncs it and the root directory; captures its identity through the held handle;
and acquires the platform advisory lock before creating `artifacts/`. Its bytes,
identity, and pathname binding MUST NOT change for the snapshot lifetime. No PID,
hostname, timestamp, token, or other diagnostic metadata is written to it.
Recovery accepts only an absent lease authorized by an owner-only cleanup state,
or the exact zero-byte lease bound to the owner/root and completion identities.
A partial, non-empty, replaced, multiply named, or un-lockable lease is ambiguous,
is preserved, and blocks mutation.

## Ephemeral handoff contract

The workflow's non-serializable `PreparedArtifactSet` consists of:

- an immutable tuple of closed `PreparedArtifactDescriptor` values;
- one verified workflow-root directory lease;
- open read-only no-follow handles for every selected artifact;
- captured root, parent, and file native identities;
- single-use ownership state.

`PreparedArtifactDescriptor` is the ephemeral handoff type and contains exactly
`artifact_key`, `source_coin_id`, `role`, `variant`, `content_type`,
`expected_byte_length`, `expected_sha256`, `workspace_relative_path`,
`root_identity`, `parent_identity`, and `file_identity`. It uses the descriptor
bounds above, except its relative path is workspace-relative and never durable.
Values are ordered by `(source_coin_id, role order, variant, artifact_key)` and
each descriptor corresponds one-to-one with its held file handle.
`ProcessedArtifactDescriptor` is reserved exclusively for the durable manifest
schema. The coordinator deterministically transforms each prepared descriptor
into it by assigning the canonical snapshot-relative index path, revalidating
exact bytes/dimensions/source linkage, and omitting every workspace/native fact.

Stage output identifies the normalized artifact key, cropped artifact key, and
closed crop record for each source/role. Assembly MUST hash through held handles,
validate both candidates and decoded JPEG facts, apply the inclusive `0.65`
selection rule, verify fallback equivalence, and create the one selected
`PreparedArtifactDescriptor`. Neither the crop stage nor adapter selects durable
bytes. The adapter MUST pass the resulting object unchanged and MUST NOT inspect
bytes or paths.

Before ownership transfer, the workflow driver owns closing every handle on
success cancellation or failure. `coordinator.prepare(...,
processed_artifacts=...)` atomically accepts ownership exactly once. On rejection,
ownership remains with the caller. After acceptance, the coordinator owns closing
the lease on every path. Repeated transfer or consumption MUST fail explicitly.
No ephemeral fact may be serialized.

## Sealing procedure

The coordinator MUST implement behavior equivalent to:

```text
require global preparation gate
validate original package snapshot and package evidence
accept PreparedArtifactSet ownership exactly once
reverify workflow root, parent chain, held file identities, lengths, and digests
build sorted descriptors and exact manifest bytes in memory
enforce every count, size, dimension, path, and content-type bound
exclusively create trusted processed root and capture identity
durably publish immutable owner.json containing the complete plan
exclusively create immutable zero-byte lease.lock and capture identity
sync lease and root; acquire the advisory lease through the held handle
exclusively create artifacts/ and capture identity
for each descriptor in canonical order:
    create exact target no-follow and no-overwrite
    bounded-copy only from its held workflow handle
    flush and platform-sync target
    hash/decode/verify through held target identity
    reverify workflow handle identity, length, digest, root, parent, and path binding
create, sync, verify, and no-overwrite publish exact manifest.json
sync/reverify processed root and fresh exact inventory
construct completion receipt from held identities
create, sync, verify, and no-overwrite publish exact complete.json
sync/reverify processed root and complete inventory again
return one ProcessedSnapshotHandle; close all workflow handles
```

The snapshot is usable only after `complete.json` is durable and verified. A
crash before completion leaves cleanup-only preparation evidence. It MUST NOT be
adopted into a transaction journal.

## Verification procedure and lease

Before cleanup intent is durable, every sensitive use MUST:

```text
acquire the processed lease with a finite monotonic wait <= MAX_LOCK_WAIT_SECONDS
bind trusted root and snapshot root through no-follow handles
verify owner, completion, manifest, and complete directory inventory
verify snapshot/workflow/package IDs and all cross-commitments
verify root, parent, owner, lease, manifest, completion, artifacts directory,
    and every artifact native identity
stream every artifact with bounded reads; verify exact length, SHA-256, JPEG
    structure, dimensions, and end-of-file consumption
recompute canonical descriptor ordering, inventory digest, and manifest digest
reverify every held identity and directory inventory before yield
reverify again before each durable mutation, on exceptional exit, and before close
```

The advisory lock is held continuously through verification and use. Lease
creation has three durable cases: absent after owner publication, exact zero-byte
object with uncertain root sync, or exact zero-byte object with durable root
sync. The first two are cleanup-only and never transaction authority; conflicting
bytes or identity block. No lease metadata replacement exists.

Wait values MUST be finite, non-negative, and at most 30 seconds. `NaN`,
infinities, overflow, wall-clock deadlines, PID liveness, and automatic stale
lease clearing are forbidden. Uncertain ownership produces a recovery-required
or process-level blocked result; it never permits deletion or adoption.

## Coordinator API and ownership

The conceptual additive API is:

```python
prepare(
    source_path,
    *,
    processed_artifacts: PreparedArtifactSet | None = None,
) -> PreparedPackageImport
```

`processed_artifacts=None` MUST execute the existing Schema 2 preparation path
unchanged. A non-null set selects Schema 3, seals the processed snapshot before
workspace cleanup, and returns a `PreparedPackageImport` owning both snapshot
handles as one single-use preparation lease.

The coordinator MUST create and validate the original package snapshot first.
It MUST reject package evidence that differs from the artifact set's source
linkage. It MUST either return both verified handles or clean/preserve only
objects whose ownership it proves. `cancel()` before journal creation MUST clean
both proven snapshots in deterministic processed-then-original order. Ambiguous
evidence is preserved for startup reconciliation.

Commit transfers both handles to the Schema 3 transaction exactly once. After
`PREPARED` is durable, only transaction/recovery code may release or clean them.

## Schema 3 journal

Schema 3 inherits every closed Schema 2 field, bound, transition, canonical
encoding, generation rule, platform rule, and compaction rule by normative
reference, with only the replacements below:

| Schema 2 contract | Schema 3 replacement |
| --- | --- |
| `journal_schema_version = 2.0` | Exactly `3.0` |
| journal owner `1.0` | Owner `2.0`, identical fields except it requires journal `3.0` |
| `snapshot_relative_path` | Renamed `package_snapshot_relative_path`; same lifecycle |
| no processed fields | Adds nullable `processed_snapshot_reference` and mandatory immutable `processed_media_commitment` |
| `ExpectedImage` | Replaced by `ExpectedImageV3` |
| `VerifiedImage` | Replaced by `VerifiedImageV3` |
| cleanup kinds/roots | Adds processed-snapshot kinds and root |
| terminal history `1.0` | Terminal history `2.0` with processed-media proof |
| Schema 2 error category set | Adds the processed failure categories below |

Every other key remains mandatory and retains its Schema 2 meaning. Schema 3
objects are closed; implementations MUST construct and validate the complete
effective key set rather than accepting a partial “extension” mapping.

### Processed snapshot reference

`ProcessedSnapshotReference` contains exactly:

| Field | Exact rule |
| --- | --- |
| `processed_snapshot_id`, `workflow_execution_id` | Canonical UUIDv4 |
| `root_relative_path` | Exact `processed-snapshots/<processed_snapshot_id>` beneath the fixed snapshots parent |
| `manifest_relative_path`, `completion_relative_path` | Exact root-relative manifest/completion names |
| `manifest_byte_length`, `completion_byte_length` | Integers 1–1048576 |
| `manifest_sha256`, `completion_sha256` | Lowercase SHA-256 of exact bytes |
| `artifact_count` | Integer 1–300 |
| `aggregate_byte_length` | Integer 1–268435456 |
| `artifact_inventory_sha256` | Exact manifest inventory commitment |

It is non-null from `PREPARED` through the `COMPLETE` successor for processed
snapshot cleanup. The next generation is a distinct cleanup-release successor:
it changes only `processed_snapshot_reference` to null and retains the completed
cleanup operation and immutable commitment. It is null in both compaction
generations and forbidden in terminal history.

`ProcessedMediaCommitment` is mandatory and immutable in every Schema 3
generation, including compaction generations, and contains exactly:

| Field | Exact rule |
| --- | --- |
| `commitment_schema_version` | String `1.0` |
| `processed_snapshot_id_sha256` | SHA-256 of canonical snapshot UUID text |
| `source_package_sha256` | Exact original package SHA-256 |
| `artifact_count`, `aggregate_byte_length` | Exact manifest values |
| `artifact_inventory_sha256`, `manifest_sha256` | Exact processed commitments |
| `ordered_mapping` | Closed ordered array defined below |
| `persisted_mapping_sha256` | Exact domain-separated digest defined below |

`ordered_mapping` is an array in manifest descriptor order. Every element is a
closed object with exactly `source_coin_id`, `role`, `artifact_key`,
`artifact_sha256`, and `variant`; each value exactly matches its descriptor.
The commitment is published in Schema 3 genesis before any external mutation.
No later generation may alter it.

`ExpectedImageV3` has every Schema 2 `ExpectedImage` key plus exactly
`source_kind`, `source_snapshot_id`, `source_coin_id`,
`source_artifact_key`, and `variant`.
`source_kind` is exactly `PROCESSED_SNAPSHOT`; snapshot ID matches the reference;
source coin ID, artifact key, and variant uniquely select a manifest descriptor
whose role, byte length, SHA-256, content type, width, and height equal the
expected managed image.
`VerifiedImageV3` adds the same native identities as Schema 2 and retains the
source fields unchanged.

The Schema 3 lifecycle is closed as follows:

| Durable state | Processed reference | Commitment | Processed cleanup |
| --- | --- | --- | --- |
| Genesis through collection publication | Non-null | Non-null, immutable | Absent or not started |
| Cleanup `INTENT`, including receipt prefixes | Non-null | Non-null, immutable | `INTENT` |
| Cleanup `COMPLETE` | Non-null | Non-null, immutable | `COMPLETE` |
| Cleanup-release successor | Null | Non-null, immutable | Same `COMPLETE` object |
| Later cleanup/rollback generations | Null iff processed cleanup is complete | Non-null, immutable | `COMPLETE` |
| G/H and pending compaction | Null | Non-null, immutable | Complete summaries |

No other nullability combination or field mutation is legal.

The processed-field mutation allowlist is exact:

| Transition | Permitted processed-field change |
| --- | --- |
| Schema 3 genesis | Create the non-null reference, immutable commitment, and complete `ExpectedImageV3` plan |
| Managed-image verification | Append only the next `VerifiedImageV3`; reference and commitment unchanged |
| Processed cleanup intent/receipt/completion | Append only the legal cleanup operation successor; reference and commitment unchanged |
| Cleanup-release successor | Set only `processed_snapshot_reference` from its exact value to null |
| Compaction G/H | Retain the generation-level `processed_media_commitment` byte-for-byte; `TerminalCompaction` gains no field and the reference remains null |
| Pending/final terminal publication | Derive only the defined `processed_media_proof` from the immutable commitment |

Any variant, mapping, digest, source coin, source key, expected-image,
commitment, or cleanup mutation outside this table is an illegal transition and
blocks recovery.

### Cleanup schema changes

Schema 3 `OwnershipDescriptor.root` additionally permits
`PROCESSED_SNAPSHOT`. `CleanupOperation.kind` additionally permits
`SUCCESS_PROCESSED_SNAPSHOT`; the maximum operation count is 4 and
`MAX_CLEANUP_TARGETS_V3` is exactly 1024. Exceeding either bound preserves
evidence and blocks mutation.

Success with an existing collection baseline orders:

```text
BASELINE_BACKUP
SUCCESS_PROCESSED_SNAPSHOT
SUCCESS_SNAPSHOT
```

Success with a missing baseline omits `BASELINE_BACKUP`. Within
`SUCCESS_PROCESSED_SNAPSHOT`, targets are artifacts in reverse descriptor order,
then `manifest.json`, the artifacts directory, `owner.json`, `complete.json`,
`lease.lock` last among files, and the verified empty processed root. Raw package
snapshot cleanup then follows the legacy `SUCCESS_SNAPSHOT` order.

`ROLLBACK_ALL` orders collection temp/backup, managed files and directories,
processed-snapshot targets in the order above, then raw package-snapshot targets.
Absent classes are omitted. Fully receipted `INTENT` and the distinct
completion-only successor retain the exact legacy rules.

Full snapshot verification is mandatory immediately before durable cleanup
intent. Once that intent is durable, cleanup uses an exact prefix verifier rather
than requiring the deleted inventory to reappear. At every next target it MUST:

1. validate the unchanged commitment, reference, cleanup intent, target order,
   and strict receipt prefix;
2. bind the held processed-root and target-parent identities to the identities
   committed before cleanup;
3. prove every receipted target absent under the same held parent identity after
   its recorded namespace sync;
4. verify every unreceipted target in the remaining suffix against its committed
   pathname, type, native identity, length, and digest before deleting only the
   next target; and
5. reject extra members, reordered targets, identity drift, missing unreceipted
   targets without an authorized absence boundary, or any mutation between the
   fully receipted `INTENT` and `COMPLETE`.

This cleanup-prefix authority is the only permitted degraded verification mode.
It authorizes deletion only, never artifact consumption, collection mutation, or
snapshot adoption.

### Error categories

Schema 3 adds these sanitized categories:

| Category | Classification |
| --- | --- |
| `PROCESSED_CONTRACT_VIOLATION` | Closed-schema, canonicalization, role, or mapping violation |
| `PROCESSED_CONTAINMENT_VIOLATION` | Unsafe path, link/reparse, mount, root, or parent substitution |
| `PROCESSED_DIGEST_MISMATCH` | Artifact, inventory, manifest, receipt, or aggregate digest mismatch |
| `PROCESSED_SIZE_MISMATCH` | Individual or aggregate size/shape mismatch |
| `UNSUPPORTED_PROCESSED_SNAPSHOT_VERSION` | Unknown owner, manifest, completion, journal, or terminal version |
| `DUPLICATE_PROCESSED_ARTIFACT` | Duplicate key, path, or source-coin/role identity |
| `PROCESSED_ARTIFACT_MISSING` | Required planned or sealed artifact absent |
| `PROCESSED_OWNERSHIP_LOST` | Token, lease, native object, or parent identity cannot be proven |
| `PROCESSED_SOURCE_MUTATION` | Ephemeral source changes during sealing |
| `PROCESSED_JOURNAL_INCONSISTENCY` | Journal reference disagrees with sealed evidence |
| `PROCESSED_CLEANUP_FAILED` | Authorized deletion or durable namespace confirmation failed |
| `PROCESSED_RECOVERY_REQUIRED` | Valid chain exists but external processed evidence is ambiguous |

Raw exceptions and paths MUST NOT be persisted or displayed.

## Transaction and image-store rules

Before creating Schema 3 generation zero, the transaction MUST hold and reverify
the global import lock, collection baseline, package snapshot, processed snapshot,
package/processed linkage, preview, decisions, and both preparation handles.

Image planning MUST select each expected image from the processed manifest.
The image store MUST:

- read only through the verified processed snapshot handle;
- match `source_artifact_key`, role, size, digest, media type, and dimensions;
- reverify snapshot and artifact identity before opening, after copying, on
  exception, and before close;
- persist exact processed bytes and record Schema 3 source evidence;
- reject missing, corrupt, replaced, extra, or mismapped artifacts;
- never inspect or use the workflow workspace;
- never fall back to archive media when `source_kind` is
  `PROCESSED_SNAPSHOT`.

Each imported `ItemPhoto` MUST contain a closed optional
`capture_import_media` object. For Schema 3 it is mandatory and contains exactly:

| Field | Exact rule |
| --- | --- |
| `schema_version` | String `1.0` |
| `import_id` | Schema 3 transaction UUID |
| `source_kind` | `PROCESSED_SNAPSHOT` |
| `package_sha256` | Original package SHA-256 |
| `processed_snapshot_id` | Processed snapshot UUID |
| `artifact_key` | Matching manifest key |
| `artifact_sha256` | Exact managed-image source digest |
| `variant` | `NORMALIZED` or `CROPPED` |

Legacy and user-created photos MAY omit the field. Deserialization MUST retain a
valid field and reject malformed importer-generated provenance. Collection
publication remains exact-byte atomic under the legacy platform protocol.

## Recovery and cleanup

Startup MUST acquire and verify the global lock before enumerating history,
journals, raw snapshots, processed snapshots, managed images, or collection
state. It MUST build one import-ID-indexed view and then:

1. classify Schema 1, 2, and 3 authority without reinterpretation;
2. validate every Schema 3 chain and processed reference;
3. reconcile only predecessor-authorized journal candidates;
4. resume transaction, rollback, cleanup, compaction, or retirement from the
   unique durable authority;
5. build complete referenced sets for both snapshot roots;
6. reconcile raw and processed orphans from the same lock-protected view;
7. accept final history only after every prohibited operational artifact is
   absent.

A complete processed snapshot referenced by a valid Schema 3 head MUST be opened
and verified before recovery reads an artifact or mutates state. Missing evidence
without an exact cleanup intent/receipt is blocked. A digest, identity, inventory,
or package-link mismatch is blocked or recorded as
`PROCESSED_RECOVERY_REQUIRED` only when a valid chain can safely publish that
generation.

An unreferenced processed directory is cleanup-eligible only when its owner plan,
token, root identity, complete inventory, and exclusive lease are proven:

- incomplete creation with no completion receipt is cleanup-only and MUST NOT be
  adopted;
- a complete verified orphan is removed narrowly;
- partial/invalid owner data, unexpected members, identity drift, uncertain
  lease ownership, or apparently live PID evidence is preserved and blocked;
- PID/hostname/timestamp never authorizes deletion or a silent skip.

Rollback MUST preserve the exact collection baseline, remove only journal-owned
managed images and both snapshots, and durably receipt every target before
compaction. Success MUST verify prospective collection and managed images before
cleaning processed then raw snapshots. A terminal outcome is illegal until all
required receipts are complete.

## Terminal and audit semantics

Processed terminal history `2.0` inherits terminal history `1.0` and adds exactly
one mandatory, non-null `processed_media_proof` field containing a closed
`TerminalProcessedMediaProof`. Schema 2 imports continue to produce terminal
history `1.0`; there is no Schema 3 legacy-source variant.

`TerminalProcessedMediaProof` contains exactly:

| Field | Exact rule |
| --- | --- |
| `outcome` | `RETAINED` for success or `REMOVED` for rollback/cancellation |
| `processed_snapshot_id_sha256` | SHA-256 of canonical UUID text; raw ID omitted |
| `source_package_sha256` | Original package SHA-256 |
| `artifact_count`, `aggregate_byte_length` | Manifest counts |
| `artifact_inventory_sha256`, `manifest_sha256` | Exact processed commitments |
| `persisted_mapping_sha256` | Exact digest of the commitment's `ordered_mapping` |

The mapping digest is:

```text
SHA256(
    UTF8("coin-analyzer.processed-media-mapping.v1") ||
    0x00 ||
    canonical_json(ordered_mapping)
)
```

Here `ordered_mapping` is exactly the closed object array defined by
`ProcessedMediaCommitment`, in manifest descriptor order. JSON arrays are used;
there is no language-specific tuple representation. Terminal proof is derived
from the immutable commitment, not from a deleted snapshot or collection
record, so success, rollback, and cancellation remain equally reproducible.

Terminal cleanup summaries add `SUCCESS_PROCESSED_SNAPSHOT` and the processed
targets within `ROLLBACK_ALL`, but remain path-free. The pending terminal audit
continues to describe the original package. Processed evidence supplements it;
it never replaces `package_sha256`.

## Failure and cancellation ordering

| Boundary | Required behavior |
| --- | --- |
| Before coordinator accepts the artifact set | Workflow owns and closes handles; no durable processed state |
| During sealing before `complete.json` | Coordinator cleans only proven incomplete candidates or preserves ambiguity; no journal |
| After sealing before coordinator return | Complete orphan is recoverable through startup reconciliation |
| After preparation before `PREPARED` | Cancel cleans processed then raw snapshot; crash leaves independently owned orphans |
| After `PREPARED` | Cancellation is cooperative and transitions through Schema 3 rollback |
| During managed-image copy | Exact journal prefix controls compensation; no raw-media fallback |
| After collection publication | Commit-or-recovery only; both snapshot references remain until cleanup receipts |
| During cleanup | Resume only the next identity-bound target; fully receipted `INTENT` has only the completion successor |
| Cleanup failure | Persist sanitized category only when the chain is valid; otherwise process-level block |
| After pending terminal publication | Pending record and retirement manifest govern ordered retirement |

## Platform guarantees

The legacy Windows NTFS, Linux local-filesystem, macOS APFS, capability-probe,
sync, no-overwrite publication, identity, and deletion requirements apply to
the processed-snapshot root and artifacts without weakening. A processed root on
a different volume from the journal/managed-image roots is unsupported. Windows
retains the documented crash-consistency limitation and makes no new sudden
power-loss claim.

## Compatibility matrix

| State | Reader/recovery path | Mutation |
| --- | --- | --- |
| Valid legacy terminal Schema 1 | Legacy read-only history | None |
| Valid active/final Schema 2 without processed snapshot | Existing Schema 2 runtime | Exact existing behavior |
| Valid active/final Schema 3 with processed snapshot | Schema 3 runtime only | According to this specification |
| Schema 2 record with processed fields | Corrupt/unknown fields | Block |
| Schema 3 record without required processed evidence | Corrupt | Block |
| Unknown owner/journal/snapshot/terminal version | Unsupported | Preserve and block |
| Mixed valid Schema 2 and Schema 3 import IDs | Enumerate together under one lock | Recover each through its versioned runtime |
| Same import ID represented by conflicting versions | Ambiguous | Preserve and block |

## Specification bundle and freezing procedure

The authoritative Unit 7A specification bundle consists of the exact complete
repository-blob bytes, in this order:

1. `docs/architecture/processed-artifact-durability.md`
2. `docs/DESKTOP_PROCESSED_ARTIFACT_RECOVERY_MATRIX.md`
3. `docs/DESKTOP_PROCESSED_ARTIFACT_RECOVERY_INVARIANTS.md`
4. `docs/architecture/processed-artifact-durability-traceability.md`

No byte range is omitted. Git's existing `* text=auto` rule stores these Markdown
blobs with LF bytes. Every candidate bundle file MUST be LF-only before freezing,
so its exact pre-commit worktree bytes equal its prospective repository-blob
bytes. Future verification SHOULD read blob bytes from Git rather than a
platform-converted checkout. The recorded bundle digest is intentionally stored in
ADR-008, `IMPORT_WORKFLOW.md`, and `SPRINT_08_PLAN.md`, which are outside the
bundle, avoiding a self-referential hash.

The bundle byte stream is:

```text
UTF8("coin-analyzer.processed-artifact-durability-spec.v1") || 0x00 ||
for each ordered file:
    uint64_be(path_utf8_byte_length) ||
    path_utf8 ||
    uint64_be(file_byte_length) ||
    exact_file_bytes
```

The digest is SHA-256 of that stream. During the pre-commit freeze, LF-only
candidate files are hashed from the worktree as exact bytes. After commit, the
same calculation MUST consume the exact Git blob bytes. Markdown is never parsed,
newline-converted, or reserialized. The calculation MUST be repeated by an
independent implementation before the hash is frozen.

Reference PowerShell calculation:

```powershell
$files = @(
  'docs/architecture/processed-artifact-durability.md',
  'docs/DESKTOP_PROCESSED_ARTIFACT_RECOVERY_MATRIX.md',
  'docs/DESKTOP_PROCESSED_ARTIFACT_RECOVERY_INVARIANTS.md',
  'docs/architecture/processed-artifact-durability-traceability.md'
)
$sha = [Security.Cryptography.IncrementalHash]::CreateHash(
  [Security.Cryptography.HashAlgorithmName]::SHA256)
$sha.AppendData([Text.Encoding]::UTF8.GetBytes(
  "coin-analyzer.processed-artifact-durability-spec.v1`0"))
foreach ($path in $files) {
  $name = [Text.Encoding]::UTF8.GetBytes($path)
  $bytes = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $path))
  $n = [BitConverter]::GetBytes([uint64]$name.Length)
  $m = [BitConverter]::GetBytes([uint64]$bytes.Length)
  if ([BitConverter]::IsLittleEndian) {
    [Array]::Reverse($n)
    [Array]::Reverse($m)
  }
  $sha.AppendData($n)
  $sha.AppendData($name)
  $sha.AppendData($m)
  $sha.AppendData($bytes)
}
[Convert]::ToHexString($sha.GetHashAndReset())
```

## Implementation gates and stop conditions

Unit 7B MAY begin only after:

1. all four bundle files are internally consistent;
2. every durable boundary has a planned PA-RM scenario;
3. every requirement maps to a planned production symbol and test;
4. the legacy hash is independently reverified unchanged;
5. the bundle hash is independently verified twice;
6. fresh-context architecture review returns
   `READY TO IMPLEMENT PROCESSED ARTIFACT DURABILITY`;
7. the approved bundle hash is recorded outside the bundle.

Units 7B–7E MUST stop if implementation requires:

- a field, state, transition, ordering rule, source-selection rule, failure
  category, or recovery action absent from this bundle;
- reinterpretation or mutation of Schema 1/2 bytes;
- a stage- or adapter-owned durable snapshot;
- durable dependence on a workflow path or ephemeral identity;
- pathname-only ownership or deletion;
- unjournalled external mutation;
- raw-media fallback for a processed import;
- a new platform guarantee or weakening of fail-closed behavior;
- a crash boundary without a permanent test;
- a public breaking change not explicitly defined here.

Discovery of such a condition pauses implementation for a documentation-only
amendment, independent re-review, and a newly frozen bundle hash.
