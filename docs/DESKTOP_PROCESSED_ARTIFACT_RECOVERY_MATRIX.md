# Desktop Processed-Artifact Recovery Matrix

## Authority

This matrix is the planned executable crash contract for
[processed-artifact durability](architecture/processed-artifact-durability.md).
It supplements, and does not renumber or reinterpret, legacy RM-01 through
RM-41. `PA-RM` means processed-artifact recovery matrix.

Every scenario MUST run with a verified global lock and fixed-root identities.
Every terminal-producing test MUST repeat recovery and prove byte-stable,
idempotent results.

## Scenarios

| ID | Durable boundary or fault | Authoritative evidence | Required recovery action | Required assertion | Planned test |
| --- | --- | --- | --- | --- | --- |
| PA-RM-01 | Artifact changes after workflow assembly, before coordinator acceptance | Held workflow handles and assembly identities | Reject transfer; workflow closes lease | No snapshot or journal; replacement preserved | `test_pa_rm01_handoff_source_replacement_fails_closed` |
| PA-RM-02 | Coordinator accepts the artifact set, then cancellation occurs before processed-root creation | Coordinator-owned single-use lease | Close handles; clean raw snapshot if proven | No processed root; no double close or journal | `test_pa_rm02_cancel_after_transfer_before_root` |
| PA-RM-03 | Crash after processed root creation, before complete owner bytes | Root identity only; owner unprovable | Preserve and block automatic deletion | No adoption or broad cleanup | `test_pa_rm03_partial_owner_preserved_and_blocks` |
| PA-RM-04 | Owner durable; lease and artifact targets absent | Exact owner plan and root identity | Delete owner/root narrowly as incomplete orphan | No journal, lease, or managed image | `test_pa_rm04_owner_only_orphan_cleanup` |
| PA-RM-05 | Crash during one artifact copy | Owner plan, held target identity, partial bytes | Delete only the exact incomplete candidate; clean snapshot | No partial target reused | `test_pa_rm05_partial_artifact_cleanup` |
| PA-RM-06 | Artifact bytes complete but target sync/outcome uncertain | Owner plan, exact target identity/bytes | Reverify; cleanup-only because completion is absent | Snapshot is never adopted | `test_pa_rm06_complete_unsealed_artifact_is_cleanup_only` |
| PA-RM-07 | Source handle changes during bounded copy | Pre/post source identity, length, digest | Abort sealing; preserve replacement; clean only owned targets | `PROCESSED_SOURCE_MUTATION`; no journal | `test_pa_rm07_source_mutation_during_seal` |
| PA-RM-08 | Crash with all artifacts complete, before manifest temp | Owner plan and exact inventory | Cleanup incomplete snapshot | No reconstructed transaction authority | `test_pa_rm08_artifacts_without_manifest_cleanup` |
| PA-RM-09 | Crash during manifest write/sync/publication | Owner manifest commitment and candidate identity | Delete partial or accept exact complete candidate for cleanup only | Conflicting/multiple candidate blocks | `test_pa_rm09_manifest_candidate_reconciliation` |
| PA-RM-10 | Manifest durable, completion absent | Owner, exact manifest, exact artifact inventory | Cleanup incomplete snapshot; do not adopt | Completion receipt is mandatory authority | `test_pa_rm10_manifest_without_completion_not_adopted` |
| PA-RM-11 | Crash during completion write/sync/publication | Owner, manifest, exact inventory, candidate identity | Delete partial; accept exact complete receipt as sealed orphan | No ambiguous completion accepted | `test_pa_rm11_completion_candidate_reconciliation` |
| PA-RM-12 | Complete processed snapshot exists before coordinator returns | Complete receipt and held snapshot identity | Startup classifies as complete orphan and removes narrowly | No journal; all owned members absent | `test_pa_rm12_complete_prejournal_orphan_cleanup` |
| PA-RM-13 | Cancel after both snapshots are prepared, before `PREPARED` | Both verified preparation handles | Clean processed snapshot, then raw snapshot | No durable transaction state | `test_pa_rm13_prejournal_cancel_cleans_both_snapshots` |
| PA-RM-14 | Under-lock revalidation fails before Schema 3 genesis | Both snapshot handles and original preview baseline | Abort before journal creation; clean/preserve by ownership proof | No managed or collection mutation | `test_pa_rm14_prepared_snapshot_revalidation_failure` |
| PA-RM-15 | Crash after Schema 3 `PREPARED` | Valid chain references both complete snapshots | Verify both; enter deterministic rollback | Final rollback after both cleanup receipts | `test_pa_rm15_prepared_crash_rolls_back_both_snapshots` |
| PA-RM-16 | Processed reference disagrees with owner, completion, manifest, or package hash | Valid Schema 3 chain plus conflicting snapshot evidence | Record recovery-required only if safe; otherwise process block | No artifact read or cleanup | `test_pa_rm16_processed_reference_mismatch_blocks` |
| PA-RM-17 | Processed artifact missing/replaced before managed-image copy | Valid chain, manifest, completion, held identities | Fail closed and roll back only if exact cleanup remains provable | No raw-media fallback | `test_pa_rm17_processed_artifact_missing_or_replaced` |
| PA-RM-18 | Crash after one managed image copied from processed snapshot | Schema 3 expected/verified inventory prefix | Verify exact source and destination; compensate | No duplicate or orphan managed image | `test_pa_rm18_partial_processed_copy_recovery` |
| PA-RM-19 | Crash after all managed images, before `FILES_READY` | Complete Schema 3 verified inventory | Follow legacy policy using processed source evidence | Stable rollback; both snapshots cleaned | `test_pa_rm19_complete_inventory_before_files_ready` |
| PA-RM-20 | Collection photo provenance differs from manifest mapping | Prospective exact collection bytes and Schema 3 mapping | Reject publication or block recovery if already external | No false commit | `test_pa_rm20_collection_provenance_mismatch` |
| PA-RM-21 | Crash after collection publication, before processed cleanup intent | Exact prospective collection, managed images, both snapshots | Append required cleanup operations in fixed order | Final success only after all receipts | `test_pa_rm21_committed_before_processed_cleanup_intent` |
| PA-RM-22 | Crash during processed-artifact deletion | Cleanup intent, strict receipt prefix, held parent identity | Resume only next target | No out-of-order or pathname-only deletion | `test_pa_rm22_processed_cleanup_receipt_prefix` |
| PA-RM-23 | Final processed target absent after durable namespace sync, before receipt | Intent and verified absence under same parent identity | Publish exactly one receipt | Repeated recovery does not duplicate receipt | `test_pa_rm23_absence_before_cleanup_receipt` |
| PA-RM-24 | Fully receipted processed cleanup `INTENT`, before completion generation | Exact unchanged targets/receipts | Publish only `COMPLETE` successor | No further deletion or receipt mutation | `test_pa_rm24_processed_cleanup_completion_only` |
| PA-RM-25 | Crash after durable cleanup-release successor, raw snapshot still present | Null processed reference, immutable commitment, completed processed operation, and raw reference | Execute legacy raw snapshot cleanup next | Raw cleanup never begins from the pre-release generation; terminal history remains forbidden | `test_pa_rm25_processed_then_raw_cleanup_order` |
| PA-RM-26 | Rollback during processed cleanup | `ROLLBACK_ALL` ordered inventory | Resume managed, processed, then raw target suffix | Exact baseline; no owned artifacts | `test_pa_rm26_rollback_dual_snapshot_cleanup` |
| PA-RM-27 | Startup sees journal-backed processed snapshot during orphan enumeration | One lock-protected journal/snapshot index | Exclude it from orphan candidates | Referenced snapshot never deleted | `test_pa_rm27_referenced_processed_snapshot_not_orphaned` |
| PA-RM-28 | Unreferenced processed snapshot has uncertain lease or object identity | Owner evidence plus acquired/failed lease proof | Preserve and raise recovery-required/block | No deletion, adoption, PID inference, or silent skip | `test_pa_rm28_uncertain_processed_orphan_preserved` |
| PA-RM-29 | Terminal compaction starts before both snapshot cleanups complete | Active Schema 3 head and incomplete cleanup ledger | Reject transition | No pending/final terminal record | `test_pa_rm29_compaction_requires_dual_cleanup` |
| PA-RM-30 | Crash during Schema 3 G/H/pending publication | Legacy compaction authority plus processed proof | Resume exact candidate/manifest/H path | Terminal proof matches processed commitments | `test_pa_rm30_processed_terminal_compaction_replay` |
| PA-RM-31 | Crash during retirement of Schema 3 chain | Pending history and retirement manifest | Resume ordered retirement | Final record contains no operational path | `test_pa_rm31_processed_chain_retirement` |
| PA-RM-32 | Repeated startup after processed success | Exact terminal history 2.0; no operational remnants | Verify and perform no mutation | Byte-stable success; managed media retained | `test_pa_rm32_processed_success_is_inert` |
| PA-RM-33 | Repeated startup after processed rollback/cancel | Exact terminal history 2.0; no operational remnants | Verify and perform no mutation | Byte-stable outcome; no managed media | `test_pa_rm33_processed_rollback_is_inert` |
| PA-RM-34 | Schema 2 record contains processed fields or Schema 3 omits them | Closed-schema bytes | Preserve and block | No reinterpretation or migration | `test_pa_rm34_version_field_conflict_blocks` |
| PA-RM-35 | Same import ID appears in conflicting Schema 2 and Schema 3 state | Lock-protected complete version index | Preserve both and block | No timestamp/version preference | `test_pa_rm35_mixed_version_identity_conflict` |
| PA-RM-36 | Unsupported filesystem or processed root on another volume | Capability and volume identities | Disable mutation | Read-only preview MAY remain; no state change | `test_pa_rm36_processed_root_capability_failure` |
| PA-RM-37 | Processed lease wait is invalid, times out, or ownership is uncertain | Exact immutable zero-byte lease identity | Reject boundedly and preserve | No rewrite, stale clearing, or PID inference | `test_pa_rm37_processed_lease_is_bounded` |
| PA-RM-38 | Extra member, duplicate canonical path, or reparse object appears in snapshot | Owner plan and actual held inventory | Preserve evidence and block | No unknown object deleted | `test_pa_rm38_processed_inventory_conflict` |
| PA-RM-39 | Terminal processed proof mismatches journal/manifest/mapping | H, pending/final candidate, processed commitments | Reject terminal candidate and preserve operational authority | Privacy-incomplete blocked state | `test_pa_rm39_terminal_processed_proof_mismatch` |
| PA-RM-40 | Recovery is interrupted repeatedly before and after cleanup | Active generation before pending; pending authority afterward | Resume unique next generation/deletion | No duplicate collection/image/history effect | `test_pa_rm40_repeated_processed_recovery_is_idempotent` |
| PA-RM-41 | Crash after owner publication during immutable lease creation, lease sync, root sync, or advisory acquisition | Exact owner/root plus absent or exact zero-byte lease candidate | Reconcile only the authorized lease candidate; cleanup-only before durable root sync; preserve conflicting identity/bytes | No lease metadata exists; no partial lease becomes transaction authority | `test_pa_rm41_immutable_lease_creation_boundaries` |
| PA-RM-42 | Crash during journal owner 2.0 or Schema 3 genesis temporary write, file sync, no-overwrite publication, or parent sync | Verified global lock, both snapshots, exact owner/genesis commitments and bounded candidates | Apply predecessor-authorized candidate reconciliation; publish exactly one genesis or remove only proven partial candidate | No external mutation before durable Schema 3 `PREPARED`; conflicting candidates block | `test_pa_rm42_schema3_genesis_publication_boundaries` |
| PA-RM-43 | Crash during cleanup-release temporary write, file sync, no-overwrite publication, or parent sync after processed cleanup is `COMPLETE` | Exact predecessor with non-null reference, immutable commitment, and completed cleanup | Reconcile and publish exactly one successor that nulls only the processed reference | Raw snapshot cleanup cannot begin until the release successor is durable; replay is byte-stable | `test_pa_rm43_processed_cleanup_release_publication` |

## Matrix-wide assertions

Every PA-RM test MUST assert:

- original package evidence is byte-for-byte unchanged;
- no workflow path or ephemeral native identity is serialized;
- collection IDs remain unique;
- every managed image equals the selected processed descriptor;
- Schema 3 never falls back to raw archive media;
- no deletion occurs outside verified roots or without held identity;
- error text is sanitized and path-free;
- retained/removed raw and processed snapshots match the current durable phase;
- the second recovery pass performs no additional mutation;
- terminal history is impossible before all cleanup receipts are complete.

Platform-specific tests MAY skip only when their required primitive cannot be
created on the current runner. The corresponding Windows, Linux, or macOS CI job
MUST execute it before the relevant platform is considered verified.
