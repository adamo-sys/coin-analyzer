# Desktop Capture Package Import Recovery Matrix

This matrix is the executable recovery contract for the desktop capture-package
importer. A terminal journal is retained history, not an orphan. Every test must
also preserve collection uniqueness, ownership boundaries, and fail-closed
behavior when exact recovery cannot be proven.

| ID | Scenario | Injected failure point | Expected recovery action | Expected final state | Automated test |
| --- | --- | --- | --- | --- | --- |
| RM-01 | Before journal creation | Journal create is interrupted before persistence | Perform no recovery work | No collection, image, or journal mutation | `tests/test_capture_package_recovery_matrix.py::test_before_journal_creation_has_no_durable_side_effects` |
| RM-02 | After journal creation | Crash after PREPARED is durable | Roll back the owned snapshot | Stable ROLLED_BACK history; no artifacts | `tests/test_capture_package_recovery_matrix.py::test_after_journal_creation_recovers_to_stable_rollback` |
| RM-03 | During journal persistence | First transition write fails | Compensate using the last durable journal | Stable ROLLED_BACK history | `tests/test_capture_package_recovery_matrix.py::test_during_journal_update_rolls_back_deterministically` |
| RM-04 | After journal persistence | Crash after COPYING_IMAGES transition | Resume from the persisted phase and roll back | Stable ROLLED_BACK history | `tests/test_capture_package_recovery_matrix.py::test_after_copying_images_transition_recovers_to_rollback` |
| RM-05 | Before snapshot creation | Missing, empty, or oversized source | Reject without creating owned state | No snapshot directory | `tests/test_capture_import_snapshot.py::test_missing_empty_and_oversized_sources_fail_without_snapshot` |
| RM-06 | During snapshot creation | Copy interruption | Remove only proven partial owned state | No reusable partial snapshot | `tests/test_capture_import_snapshot.py::test_copy_interruption_removes_only_partial_owned_snapshot` |
| RM-07 | After snapshot creation | Snapshot accepted and then cleaned | Validate exact identity and digest | Clean snapshot lifecycle | `tests/test_capture_import_snapshot.py::test_create_validate_and_cleanup_owned_snapshot` |
| RM-08 | Before snapshot verification | Under-lock revalidation fails | Abort before journal creation | No durable import state | `tests/test_capture_package_execution.py::test_snapshot_is_revalidated_under_lock_before_journal_creation` |
| RM-09 | After snapshot verification | Package changes during held lease | Fail closed and close the read handle | Evidence retained; no import mutation | `tests/test_capture_import_snapshot.py::test_open_snapshot_detects_package_mutation_during_lease` |
| RM-10 | Before first durable mutation | Collection baseline changes | Reject before PREPARED | Existing collection unchanged | `tests/test_capture_package_execution.py::test_stale_collection_baseline_fails_before_durable_import_state` |
| RM-11 | During managed-image persistence | Persisted bytes are corrupted | Block FILES_READY and compensate | No committed collection or corrupt image | `tests/test_capture_package_durability.py::test_same_length_persisted_corruption_blocks_files_ready` |
| RM-12 | After first managed image | Crash after first image path is journaled | Verify ownership and roll back | No managed-image orphan | `tests/test_capture_package_recovery_matrix.py::test_after_first_managed_image_recovers_without_orphans` |
| RM-13 | After all managed images | Crash after complete inventory is journaled | Verify and roll back | No image directory remains | `tests/test_capture_package_recovery_matrix.py::test_after_all_managed_images_before_files_ready_recovers` |
| RM-14 | Before FILES_READY | Crash before phase transition | Reconcile COPYING_IMAGES and compensate | Stable ROLLED_BACK history | `tests/test_capture_package_execution.py::test_restart_recovery_rolls_back_complete_uncommitted_images` |
| RM-15 | After FILES_READY | Crash after phase transition | Roll back verified images | No collection mutation | `tests/test_capture_package_recovery_matrix.py::test_after_files_ready_before_metadata_recovers_to_rollback` |
| RM-16 | Before metadata persistence | Crash after COMMITTING_COLLECTION | Prove reserved IDs absent and roll back | Empty collection; stable history | `tests/test_capture_package_recovery_matrix.py::test_after_committing_collection_before_metadata_recovers_to_rollback` |
| RM-17 | During metadata persistence | Collection write succeeds before caller returns | Detect exact reserved records and finalize | One collection record; no duplicate | `tests/test_capture_package_recovery_matrix.py::test_during_metadata_persistence_recovers_without_duplicates` |
| RM-18 | After metadata persistence | Crash before COLLECTION_COMMITTED is retained | Reconcile reserved records and finish | One collection record; SUCCEEDED | `tests/test_capture_package_execution.py::test_restart_recovery_finalizes_commit_without_duplicate_records` |
| RM-19 | Before cleanup | Crash before snapshot deletion | Resume using intact snapshot | SUCCEEDED after cleanup | `tests/test_capture_package_durability.py::test_success_crash_before_snapshot_cleanup_remains_preterminal` |
| RM-20 | During cleanup | Partial snapshot deletion | Fail closed because evidence is incomplete | Preterminal recovery-required state | `tests/test_capture_package_durability.py::test_success_crash_during_snapshot_cleanup_remains_preterminal` |
| RM-21 | After cleanup | Crash after deletion and before terminal update | Do not infer success without evidence | COLLECTION_COMMITTED remains nonterminal | `tests/test_capture_package_durability.py::test_success_crash_after_snapshot_cleanup_never_exposes_terminal_state` |
| RM-22 | Before rollback terminal state | Observe cleanup while ROLLING_BACK | Delete snapshot before retaining audit | ROLLED_BACK only after cleanup | `tests/test_capture_package_durability.py::test_rollback_snapshot_cleanup_precedes_terminal_state` |
| RM-23 | After terminal state | Re-run startup recovery | Perform no additional mutation | Stable SUCCEEDED history | `tests/test_capture_package_recovery_matrix.py::test_terminal_success_is_stable_under_repeated_recovery` |
| RM-24 | Repeated recovery | Run recovery twice after rollback | First reconciles; second is a no-op | Byte-stable terminal journal | `tests/test_capture_package_recovery_matrix.py::test_repeated_recovery_after_rollback_is_byte_stable` |
| RM-25 | Interrupted recovery | Crash after ROLLING_BACK is durable | Resume compensation on restart | Stable ROLLED_BACK history | `tests/test_capture_package_recovery_matrix.py::test_interrupted_recovery_resumes_idempotently` |
| RM-26 | Repeated interrupted recovery | Interrupt two recovery attempts | Preserve monotonic evidence and retry | Third attempt reaches ROLLED_BACK | `tests/test_capture_package_recovery_matrix.py::test_repeated_interrupted_recovery_has_stable_evidence` |
| RM-27 | Startup after success | Reconcile terminal success repeatedly | Skip retained history | Collection and journal unchanged | `tests/test_capture_package_recovery_matrix.py::test_startup_after_success_repeatedly_skips_retained_history` |
| RM-28 | Startup after rollback | Reconcile terminal rollback repeatedly | Skip retained history | No artifacts; journal unchanged | `tests/test_capture_package_recovery_matrix.py::test_startup_after_rollback_repeatedly_skips_retained_history` |
| RM-29 | Reserved desktop ID collision | Existing unrelated record uses reserved ID | Reject before durable import state | Unrelated record unchanged | `tests/test_capture_package_execution.py::test_reserved_desktop_id_collision_fails_before_durable_state` |
| RM-30 | Snapshot ownership mismatch | Owner record is corrupt | Preserve evidence and block cleanup | No unverified deletion | `tests/test_capture_import_snapshot.py::test_corrupt_owner_blocks_cleanup_without_broad_deletion` |
| RM-31 | Orphan journal | Preterminal journal references missing snapshot | Fail deterministically on every attempt | Journal retained; no guessed recovery | `tests/test_capture_package_durability.py::test_preterminal_missing_snapshot_fails_recovery_deterministically` |
| RM-32 | Proven orphan snapshot | Unreferenced snapshot has dead owner | Remove only proven owned snapshot | No orphan snapshot | `tests/test_capture_package_execution.py::test_startup_recovery_removes_only_proven_orphan_snapshot` |
| RM-33 | Journal/snapshot mismatch | Validated package changes under lease | Reject mismatched evidence | No terminal success | `tests/test_capture_import_snapshot.py::test_integrity_change_after_acceptance_is_detected_and_cleanup_is_safe` |
| RM-34 | Managed-image mismatch | Image object replaced after inventory | Fail closed and preserve replacement | No false FILES_READY or success | `tests/test_capture_package_durability.py::test_managed_image_replacement_after_inventory_is_rejected` |
| RM-35 | Object identity mismatch | Destination pathname is replaced | Reject cleanup and preserve replacement | No unrelated deletion | `tests/test_capture_package_durability.py::test_destination_pathname_replacement_is_detected` |
| RM-36 | Concurrent startup | Another owner holds the import lock | Refuse lock non-destructively | Existing lock remains | `tests/test_capture_import_lock.py::test_contention_is_non_destructive_and_never_clears_existing_lock` |
| RM-37 | Concurrent import attempt | Pre-existing valid lock is present | Do not enter transaction | No journal, image, or collection mutation | `tests/test_capture_import_lock.py::test_preexisting_uncertain_lock_is_preserved` |
| RM-38 | Lock acquisition failure | Metadata or ownership is uncertain | Fail closed | Lock evidence preserved | `tests/test_capture_import_lock.py::test_release_requires_exact_on_disk_token_and_preserves_mismatch` |
| RM-39 | Recovery while importer owns lock | Contended recovery acquisition | Wait only within bounded policy, then fail | Active importer state untouched | `tests/test_capture_import_lock.py::test_wait_arguments_are_bounded_and_typed` |
| RM-40 | Windows privilege boundary | Reparse swap cannot be created without privilege | Skip explicitly or reject the actual swap | Deterministic platform result | `tests/test_capture_package_durability.py::test_windows_reparse_swap_between_check_and_open_is_rejected` |
| RM-41 | Supported POSIX/Windows exchange | Destination changes immediately before journal swap | Restore or preserve unexpected object | No unverified journal deletion | `tests/test_capture_package_durability.py::test_posix_journal_substitution_before_exchange_is_preserved` |

## Matrix-wide assertions

Every terminal-producing test verifies, directly or through its shared assertion
helper, that recovery is idempotent, collection IDs remain unique, owned working
images and snapshots are absent, and a repeated recovery pass performs no work.
Ambiguous ownership or missing recovery evidence intentionally remains
nonterminal and fails closed.
