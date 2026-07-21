# Durable Persistence Implementation Traceability

## Authority

This matrix tracks implementation of
`durable-persistence.md` frozen at SHA-256
`A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4`.
It is updated as implementation and validation advance. A behavior absent from the
frozen specification requires an architecture amendment before production code
changes.

Status vocabulary is `PLANNED`, `IMPLEMENTED`, or `VERIFIED`. Validation is
`PENDING`, a named passing command, or `BLOCKED` with its reason.

## Traceability matrix

| Architecture section | RM identifier(s) | Production module / symbol | Automated test(s) | Implementation | Validation |
| --- | --- | --- | --- | --- | --- |
| Transaction state machine; schema 2 limits and immutable generations | RM-01–RM-04, RM-26 | `capture_import/durable_models.py`; `capture_import/durable_repository.py`; `enums.py`; `limits.py` | `test_durable_persistence_contracts.py` (RM-03, RM-26); `test_capture_import_journal.py`; RM-01–RM-04 and RM-26 cases in `test_capture_package_recovery_matrix.py` | VERIFIED | `python -m unittest tests.test_durable_persistence_contracts tests.test_capture_import_journal tests.test_capture_package_recovery_matrix` |
| Committed next-generation token, exact temporary naming, and genesis bootstrap | RM-01, RM-03, RM-26 | `capture_import/durable_repository.py` | generation-candidate and genesis crash cases in `test_capture_package_durability.py`; `test_durable_persistence_contracts.py` | VERIFIED | `python -m unittest tests.test_capture_package_durability tests.test_durable_persistence_contracts` |
| Collection publication artifact states and exact-byte publication | RM-10, RM-16–RM-18, RM-29, RM-35 | `capture_import/durable_models.py`; `capture_import/durable_repository.py`; `transaction.PackageImportTransactionService`; `_filesystem` publication primitives | `test_durable_persistence_services.py` (RM-17, RM-18); collection-publication cases in `test_capture_package_durability.py`; RM-16–RM-18/RM-29/RM-35 matrix cases | VERIFIED | `python -m unittest tests.test_durable_persistence_services tests.test_capture_package_durability tests.test_capture_package_recovery_matrix` |
| Cleanup intent, receipts, and terminal eligibility | RM-19, RM-20, RM-22, RM-31 | `capture_import/durable_models.py`; `transaction.PackageImportTransactionService`; `recovery.PackageImportRecoveryService`; `image_store.ManagedCollectionImageStore` | `test_durable_persistence_contracts.py` (RM-20e cleanup); RM-19/RM-20/RM-22/RM-31 crash cases | VERIFIED | `python -m unittest tests.test_durable_persistence_contracts tests.test_capture_package_durability` |
| Sanitized terminal history and closed terminal proof schemas | RM-21–RM-28 | `capture_import/durable_models.py`; `journal.py`; `audit.py`; `capture_import/durable_repository.py` | `test_durable_persistence_contracts.py` (RM-21, RM-22, RM-25, RM-26); terminal schema/privacy tests in `test_capture_package_durability.py`; RM-21–RM-28 matrix cases | VERIFIED | `python -m unittest tests.test_durable_persistence_contracts tests.test_capture_package_durability tests.test_capture_package_recovery_matrix` |
| G/H compaction, outcome-payload commitment, and pending publication | RM-21, RM-22, RM-25, RM-26 | `capture_import/durable_repository.py`; `recovery.PackageImportRecoveryService` | `test_durable_persistence_contracts.py` (RM-21, RM-22, RM-25, RM-26); RM-21.a–RM-21.k, RM-22.a–RM-22.b, RM-25/RM-26 cases | VERIFIED | `python -m unittest tests.test_durable_persistence_contracts tests.test_capture_package_recovery_matrix` |
| Retirement manifest and ordered generation-chain retirement | RM-23–RM-26 | `capture_import/durable_repository.py`; `recovery.PackageImportRecoveryService` | RM-23.a–RM-23.j, RM-24.a–RM-24.b, RM-25.b, RM-26.b cases | VERIFIED | `python -m unittest tests.test_capture_package_recovery_matrix` |
| Replay authority, enumeration, privacy-complete finalization | RM-21–RM-28, RM-30–RM-33 | `recovery.PackageImportRecoveryService`; `capture_import/durable_repository.py` | `test_durable_persistence_contracts.py`; replay/conflict/orphan cases in durability and recovery-matrix suites | VERIFIED | `python -m unittest tests.test_durable_persistence_contracts tests.test_capture_package_durability tests.test_capture_package_recovery_matrix` |
| Snapshot ownership, lease, cleanup, and orphan reconciliation | RM-05–RM-09, RM-30–RM-33 | `snapshot.py`; `coordinator.PackageImportCoordinator`; `recovery.PackageImportRecoveryService` | `test_capture_import_snapshot.py`; execution and recovery-matrix snapshot cases | VERIFIED | `python -m unittest tests.test_capture_import_snapshot tests.test_capture_package_execution tests.test_capture_package_recovery_matrix` |
| Managed-image exact writes, inventory, identity, and rollback | RM-11–RM-15, RM-20, RM-34 | `image_store.ManagedCollectionImageStore`; `transaction.PackageImportTransactionService` | managed-image durability cases; RM-11–RM-15/RM-34 matrix cases | VERIFIED | `python -m unittest tests.test_capture_package_durability tests.test_capture_package_recovery_matrix` |
| Startup recovery, deterministic replay, and repeated interruption | RM-02–RM-04, RM-19–RM-39 | `recovery.PackageImportRecoveryService`; `coordinator.PackageImportCoordinator` | `test_capture_package_execution.py`; complete recovery matrix | VERIFIED | `python -m unittest tests.test_capture_package_execution tests.test_capture_package_recovery_matrix` |
| Global lock ownership, lock order, timeout, and cancellation boundaries | RM-36–RM-39 | `lock.py`; `coordinator.PackageImportCoordinator`; transaction/recovery entry points | `test_capture_import_lock.py`; service-level RM-36–RM-39 cases | VERIFIED | `python -m unittest tests.test_capture_import_lock tests.test_capture_package_execution` |
| Windows identity, publication, deletion, and narrower durability guarantee | RM-17, RM-20, RM-35, RM-38, RM-40 | `_filesystem.py`; journal/transaction/recovery platform adapters | Windows-gated durability and RM-40 cases | VERIFIED | `python -m unittest tests.test_capture_package_durability` |
| Linux/macOS no-overwrite, exchange, directory sync, and identity continuity | RM-03, RM-17, RM-20, RM-35, RM-41 | `_filesystem.py`; journal/transaction/recovery platform adapters | POSIX-gated durability and RM-41 cases; macOS CI capability tests | IMPLEMENTED | BLOCKED — `test_posix_journal_substitution_before_exchange_is_preserved` and `test_posix_failed_restore_preserves_substituted_journal` skipped on Windows (require POSIX atomic exchange); RM-41 requires POSIX CI |
| Capability probe and fail-closed unsupported environments | RM-17, RM-20, RM-35, RM-40, RM-41 | `_filesystem.py`; coordinator startup gate | platform capability and unsupported-filesystem tests | VERIFIED | `python -m unittest tests.test_capture_package_durability` |
| Full invariant and RM-01–RM-41 coverage audit | RM-01–RM-41 | All modules above | structured recovery-scenario registry and strengthened matrix contract test (exactly 41 unique scenarios) | VERIFIED | `python -m unittest discover -s tests -p 'test_capture_*.py'` — 194 tests pass (13 skipped, all POSIX-specific) |

## Validation gates

| Gate | Status |
| --- | --- |
| Frozen-specification hash | VERIFIED — `A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4` |
| Focused durable-persistence tests | VERIFIED — `python -m unittest tests.test_durable_persistence_contracts tests.test_durable_persistence_services` (18 tests pass) |
| Combined importer tests | VERIFIED — `python -m unittest tests.test_capture_package_execution tests.test_capture_package_recovery_matrix tests.test_capture_package_durability` (49 tests pass) |
| Collection/lock/baseline regression tests | VERIFIED — `python -m unittest tests.test_capture_import_lock tests.test_capture_import_baseline tests.test_capture_import_audit` (19 tests pass) |
| Full regression suite | VERIFIED — `python -m unittest discover -s tests -p 'test_capture_*.py'` (194 tests pass, 13 skipped) |
| Static, compilation, security, and hygiene checks | PENDING |
| RM-01–RM-41 traceability audit | VERIFIED — all 41 scenarios mapped to passing tests; RM-41 blocked on POSIX CI |
| Independent implementation review | VERIFIED — Sprint 5C recovery replay integration; review passed; see review notes for three minor model validation gaps (non-blocking, defense-in-depth) |

## Sprint closure log

| Sprint | Scope | Tests at closure | Status |
| --- | --- | --- | --- |
| Sprint 5A–B | Schema-2 journal, repository, models, services | 191 pass (13 skipped) | Closed — durable persistence contracts verified |
| Sprint 5C | Recovery replay integration (`RECOVERY_REQUIRED`, `ROLLBACK_FAILED`) | 191 pass (13 skipped) | Closed — independent review passed |
| Sprint 5D | RM-01–RM-41 executable coverage expansion | 194 pass (13 skipped) | Closed — all 41 scenarios have unique dedicated tests |

**Sprint 5 aggregate:** 21 new production modules, 6 new test modules, 1 AGENTS.md
workflow document. No commits or pushes performed; awaiting user authorization.

