# Desktop Capture Package Import Recovery Invariants

These invariants govern every importer transaction, recovery implementation,
and future review.

1. **Terminal states are idempotent.** A retained `SUCCEEDED`, `ROLLED_BACK`, or
   `CANCELLED` journal is history. Startup recovery does not repeat its effects.
2. **Recovery is deterministic.** The same durable evidence produces the same
   recovery decision and final state on every attempt.
3. **Uncertain identity fails closed.** Recovery never adopts, overwrites, or
   deletes an object whose ownership, containment, bytes, or native identity
   cannot be established.
4. **Cleanup precedes terminal history.** No terminal journal or audit is
   persisted while successful recovery still depends on a sensitive snapshot.
5. **Durable transitions are reconstructible.** Every phase records enough
   validated evidence to resume, compensate, or explicitly require recovery
   after process termination or power loss.
6. **Collection commits are all-or-nothing.** Recovery never creates a second
   record for a reserved desktop ID and never treats an unrelated collision as
   a successful import.
7. **Persisted media is exact.** Managed images must match the declared length,
   digest, decoded format, dimensions, inventory, and captured native identity
   before collection mutation is permitted.
8. **Owned cleanup is narrow.** Cleanup removes only objects whose ownership and
   identity match the active journal. Replacement evidence is preserved.
9. **Recovery is serialized.** Startup recovery and normal import use the same
   bounded exclusive lock and cannot reconcile concurrently.
10. **Every durable boundary has a crash test.** The recovery matrix maps each
    supported failure point to a permanent automated regression test.

The normative scenario-to-test mapping is maintained in
`DESKTOP_PACKAGE_IMPORT_RECOVERY_MATRIX.md`.
