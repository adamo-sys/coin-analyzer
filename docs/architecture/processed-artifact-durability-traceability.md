# Processed-Artifact Durability Traceability

## Authority

This matrix tracks the separately versioned
[processed-artifact durability specification](processed-artifact-durability.md).
The authoritative bundle digest is recorded outside the hashed bundle in
ADR-008, `IMPORT_WORKFLOW.md`, and `SPRINT_08_PLAN.md`.

Status vocabulary is `PLANNED`, `IMPLEMENTED`, `VERIFIED`, or `BLOCKED`.
Unit 7A is documentation-only; every production and test row remains `PLANNED`.

## Architecture-to-implementation matrix

| Requirement / architecture section | PA-RM IDs | Planned unit | Planned production module / symbol | Planned automated tests | Status | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| Versioned closed schemas and compatibility | PA-RM-34, PA-RM-35 | 7D | `durable_models.py`; `durable_repository.py`; `limits.py` | `test_processed_artifact_durable_contracts.py`; version conflict cases | PLANNED | PENDING |
| Canonical manifest and descriptors | PA-RM-06–PA-RM-11, PA-RM-38 | 7B | `processed_snapshot.ProcessedSnapshotManifest`; `ProcessedArtifactDescriptor` | `test_processed_artifact_snapshot.py` canonical/unknown/duplicate/bound tests | PLANNED | PENDING |
| Exact durable variant selection | PA-RM-01, PA-RM-07, PA-RM-17, PA-RM-20 | 7B/7E | workflow typed selection; `PreparedArtifactDescriptor`; `PreparedArtifactSet`; adapter routing | threshold boundary, fallback equivalence, missing/duplicate/inconsistent crop record tests | PLANNED | PENDING |
| Aggregate and exact-byte verification | PA-RM-06–PA-RM-11, PA-RM-16–PA-RM-17, PA-RM-39 | 7B/7D | `processed_snapshot`; transaction verification seam | digest, trailing-byte, corruption, replacement, and terminal-proof cases | PLANNED | PENDING |
| Identity-bound ephemeral handoff | PA-RM-01, PA-RM-02, PA-RM-07 | 7B | `workflow_models.PreparedArtifactSet`; `PreparedWorkspaceLease`; `workflow_execution.assemble_prepared_import` | handoff transfer, replacement, mutation, cancellation, and handle-leak tests | PLANNED | PENDING |
| Snapshot owner, sealing, completion, and immutable lease | PA-RM-03–PA-RM-12, PA-RM-37–PA-RM-38, PA-RM-41 | 7B | `processed_snapshot.ProcessedArtifactSnapshotService`; `ProcessedSnapshotHandle` | owner/root binding, zero-byte lease publication, sync, advisory acquisition, crash, and inventory suite | PLANNED | PENDING |
| Coordinator additive API and dual ownership | PA-RM-02, PA-RM-12–PA-RM-15 | 7C | `coordinator.PackageImportCoordinator.prepare`; `PreparedPackageImport` | source-only compatibility, transfer, dual cancel, pre-journal crash tests | PLANNED | PENDING |
| Schema 3 genesis, immutable commitment, and processed reference lifecycle | PA-RM-14–PA-RM-16, PA-RM-34–PA-RM-35, PA-RM-42 | 7D | `durable_models.OperationalJournalGenerationV3`; `ProcessedMediaCommitment`; Schema 3 repository | closed schema, proof retention, exact mapping, nullability, genesis boundary, chain, and version-selection tests | PLANNED | PENDING |
| Processed image planning and source selection | PA-RM-17–PA-RM-20 | 7D | `image_store.ManagedCollectionImageStore`; Schema 3 transaction service | processed source, mismatch, no-fallback, and partial-copy tests | PLANNED | PENDING |
| Collection photo provenance | PA-RM-20, PA-RM-21, PA-RM-39 | 7D | `coin_collection.ItemPhoto`; transaction record builder | serialization, legacy absence, malformed provenance, exact mapping tests | PLANNED | PENDING |
| Success and rollback cleanup ordering and prefix verification | PA-RM-21–PA-RM-26, PA-RM-29, PA-RM-43 | 7D | cleanup schemas/executor; processed cleanup-prefix verifier; Schema 3 transaction/recovery | full pre-intent verification, every intent/delete/sync/receipt/completion/release boundary, absent prefix and remaining suffix | PLANNED | PENDING |
| Startup enumeration and orphan reconciliation | PA-RM-12, PA-RM-27–PA-RM-28, PA-RM-34–PA-RM-38 | 7D | `recovery.PackageImportRecoveryService`; coordinator startup gate | one-view reference/orphan/version/platform cases | PLANNED | PENDING |
| Terminal processed proof and privacy | PA-RM-29–PA-RM-33, PA-RM-39–PA-RM-40 | 7D | immutable processed commitment; terminal models/persistence; retirement and recovery services | success/rollback/cancel proof equivalence, exact mapping, G/H, pending, retirement, privacy, idempotence tests | PLANNED | PENDING |
| Deterministic image pipeline and thin adapter | PA-RM-01, PA-RM-02, PA-RM-13–PA-RM-14 | 7E | `workflow_stages.build_image_processing_pipeline`; `workflow_adapter.commit_prepared_import` | seven-stage order, unchanged descriptors, one invocation, legacy builder tests | PLANNED | PENDING |
| Platform fail-closed guarantees | PA-RM-22–PA-RM-28, PA-RM-36–PA-RM-38 | 7B/7D | `_filesystem.py`; processed snapshot/cleanup adapters | Windows, Linux, macOS identity/sync/deletion/capability cases | PLANNED | PENDING |
| Complete recovery contract | PA-RM-01–PA-RM-43 | 7D | all versioned services above | structured registry proving exactly 43 unique PA-RM scenarios | PLANNED | PENDING |

## Schema field traceability

| Schema | Defining section | Planned model | Required validation family |
| --- | --- | --- | --- |
| Processed snapshot owner `1.0` | Owner and completion schemas | `ProcessedSnapshotOwner` | closed fields, bounds, plan commitments, partial owner |
| Processed manifest `1.0` | Canonical manifest and aggregate identity | `ProcessedSnapshotManifest` | canonical bytes, ordering, digest, unknown fields |
| Processed completion `1.0` | Owner and completion schemas | `ProcessedSnapshotCompletion` | cross-identity, complete inventory, self-reference exclusion |
| Journal owner `2.0` | Schema 3 journal | `JournalOwnerRecordV2` | journal `3.0` commitment and genesis hash |
| Operational journal `3.0` | Schema 3 journal | `OperationalJournalGenerationV3` | effective closed key set, transitions, source evidence |
| Processed-media commitment `1.0` | Schema 3 journal | `ProcessedMediaCommitment` | closed mapping, canonical digest, immutability, cleanup/compaction retention |
| Terminal history `2.0` | Terminal and audit semantics | `TerminalHistoryRecordV2` | processed proof, cleanup summaries, privacy |
| Collection photo provenance `1.0` | Transaction and image-store rules | `CaptureImportMediaProvenance` | round trip, mandatory Schema 3 mapping, legacy omission |

## Unit gates

### Unit 7A

- Bundle schemas, transitions, matrix, invariants, and traceability agree.
- Legacy specification exact-byte hash remains unchanged.
- Bundle hash is independently reproduced twice and recorded outside the bundle.
- Fresh-context review returns
  `READY TO IMPLEMENT PROCESSED ARTIFACT DURABILITY`.

### Unit 7B

- Implement only handoff contracts, processed snapshot models, sealing,
  verification, lease, and preparation-orphan cleanup.
- PA-RM-01 through PA-RM-12 and PA-RM-37/38 MUST pass.
- Stop if a journal, transaction, collection, or managed-image mutation is
  required.

### Unit 7C

- Implement only coordinator additive API, dual preparation ownership, and
  pre-journal lifecycle.
- PA-RM-02 and PA-RM-12 through PA-RM-15 MUST pass.
- Stop on a breaking source-only API change or any durable journal mutation.

### Unit 7D

- Implement only the approved Schema 3 transaction, image-store, journal,
  recovery, cleanup, provenance, and terminal contracts.
- PA-RM-14 through PA-RM-43 MUST pass on applicable CI platforms.
- Stop on any unplanned state, field, transition, failure category, or platform
  downgrade.

### Unit 7E

- Implement only deterministic pipeline construction and thin adapter routing.
- Both pipeline builders, source-only preparation, single-use transfer,
  cancellation, and exactly-once transaction invocation MUST pass.
- Stop if the adapter must inspect bytes or create durable state.

## Validation ledger

| Gate | Status |
| --- | --- |
| Legacy exact-byte hash | PENDING |
| Bundle exact-byte hash, implementation 1 | PENDING |
| Bundle exact-byte hash, independent implementation 2 | PENDING |
| Closed-schema and terminology audit | PENDING |
| PA-RM-01–PA-RM-43 coverage audit | PENDING |
| Referenced paths and current symbols | PENDING |
| `git diff --check` | PENDING |
| Independent architecture review | PENDING |
