# Desktop Processed-Artifact Recovery Invariants

These invariants supplement the legacy recovery invariants only for Schema 3
imports with processed media.

1. **Original evidence is immutable.** Package identity, bytes, manifest, audit,
   and replay authority never change because processed media exists.
2. **Derived evidence has separate identity.** A processed snapshot has its own
   ID, owner token, native identities, manifest, completion receipt, and digests.
3. **Workspace state is never durable.** No workflow path, handle, native
   identity, process fact, or lifetime is journal, recovery, or audit authority.
4. **Coordinator ownership is exclusive.** Stages and adapters cannot create,
   adopt, delete, or own a durable snapshot.
5. **Handoff is identity-bound and single-use.** The coordinator seals only the
   exact held objects verified by assembly; transfer or transaction reuse fails.
6. **Completion is explicit.** Owner intent or a manifest alone never makes a
   processed snapshot consumable. A verified completion receipt is mandatory.
7. **Reads require continuous verification.** Transaction and recovery rebind
   root, parent, file, manifest, completion, and lease identities before and
   after every sensitive read.
8. **Processed means processed.** Schema 3 image persistence reads the selected
   processed artifact and never silently substitutes original archive media.
9. **Source mapping is durable.** Expected images, managed images, collection
   photo provenance, journal evidence, and terminal proof agree on snapshot,
   artifact key, role, digest, and variant.
   The immutable processed-media commitment retains that mapping through
   cleanup, rollback, cancellation, and compaction.
10. **Both snapshots are recoverable.** Schema 3 retains raw and processed
    references until their independently ordered cleanup receipts are durable.
11. **Cleanup is narrow and ordered.** Success cleans baseline backup when
    applicable, processed snapshot, then raw snapshot. Rollback cleans collection
    candidates, managed images, processed snapshot, then raw snapshot.
    Full verification precedes cleanup intent; thereafter the strict durable
    receipt prefix and verified remaining suffix are the only deletion authority.
12. **Terminal state follows cleanup.** Pending or final history is forbidden
    until both snapshot cleanups and every other required operation are complete.
13. **Orphan classification uses one locked view.** Journal-backed processed
    snapshots are never orphans; incomplete or uncertain unreferenced state is
    never adopted.
14. **PID and time are not authority.** Liveness, hostname, timestamps, and path
    existence do not grant ownership, permit cleanup, or resolve ambiguity.
15. **Version boundaries are closed.** Schema 1/2 bytes are never interpreted as
    Schema 3, and conflicting versions for one import ID block all mutation.
16. **Recovery is deterministic and idempotent.** Equal durable evidence yields
    the same one-next action; replay cannot duplicate images, records, cleanup
    receipts, or history.
17. **Privacy completes retirement.** Terminal proof is path-free, token-free,
    identity-free, and cannot become final while operational remnants remain.
18. **Every new boundary has a test.** PA-RM-01 through PA-RM-43 are mandatory
    executable acceptance scenarios before Unit 7D can be verified.
19. **Lease bytes are immutable.** The processed lease is an exact zero-byte
    object created once, never rewritten, and used only through a verified held
    identity and platform advisory lock.
20. **Zero selection remains pre-journal.** If final decisions select no coins,
    the existing successful no-op result is returned only after processed-then-raw
    preparation cleanup. No Schema 3 owner, generation, managed image, collection
    mutation, or terminal history is created, and every actual Schema 3 genesis
    retains non-empty selected-source and expected-image inventories.

The normative scenario mapping is
`DESKTOP_PROCESSED_ARTIFACT_RECOVERY_MATRIX.md`.
