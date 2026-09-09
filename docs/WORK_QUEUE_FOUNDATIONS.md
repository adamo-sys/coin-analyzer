# Work Queue prerequisite contract

This bounded slice adds typed record and safe edit foundations to main's existing
array-format collection store. It retains exact-byte baseline checks, import locks,
atomic publication receipts, and fail-closed persistence. It does not replay the
older versioned-envelope migration or publish Work Queue.

Records expose closed `ItemType` (COIN/BANKNOTE) and `IdentificationStatus`
(IDENTIFIED/PARTIAL/UNIDENTIFIED). Legacy records default to COIN. Missing status
is derived once at the record boundary; explicit status round-trips unchanged.
Manual entry and edits derive status from reliable identity fields: a reference,
or country/issuer plus denomination plus year, establishes IDENTIFIED; some
reliable fields establish PARTIAL; otherwise UNIDENTIFIED. Blank and placeholder
text does not establish identity. Work Queue must consume this explicit status,
never derive it itself. Title alone is display text, not identification evidence.
Loading does not rewrite stored bytes. Unsupported explicit enum values fail.

Incomplete manual records need neither a photo nor fabricated identity. Stable
nonblank IDs must be unique for authoritative ordinary writes. An item's ID and
type cannot be changed by an ordinary edit.

Deferred actions capture a runtime reference bound to both the collection instance
and the exact item object. Resolution requires the same valid collection and a
single matching item that is still that object. Reload, collection replacement,
deletion/replacement with a reused ID, and ambiguous duplicate IDs invalidate the
reference. References retain object ownership for their lifetime, are not persisted,
and are not reconstructed from an ID at activation time. Work Queue reconstruction
must capture these references when deriving/displaying tasks and resolve them
before navigation. The existing editor captures at dialog opening and checks again
at save, including after media ingestion.

New photos selected in an existing-item edit are copied exclusively to collection
managed storage and verified before persistence. Existing photo paths/provenance
are preserved, including unavailable existing files; ordinary edit cannot fabricate
capture-import provenance. Failure rolls back only unchanged attempt-owned files;
removed photos and sources are never deleted. Submitted photo normalization must
not mutate authoritative metadata before commit. Media storage is bound to the
current collection, not a formerly active collection.

Validation uses synthetic records/media: enum and legacy round trips, incomplete
entry, reused-ID/reference rejection, guarded editor saves, media copy/rollback and
provenance, plus affected persistence/integration regression. Native Tk acceptance,
Work Queue projection/GUI integration, Command Center, Sprint wording, schema
migration, banknote-specific UI, and unrelated cleanup are out of scope.

## Reconciliation and validation

Reconstructed on main `df29e35a8abcedb05d9db67b959855bc19b894ae` with fresh
metadata. The older record/entry/editor implementations informed this slice;
no original Work Queue commit or unrelated ancestor was replayed.

Focused validation: 42 tests across `test_confirmed_observations`,
`test_phase2b2_photo_inbox_create`, and `tests.test_work_queue_foundations`.
Negative purchase price retains genuine validation-failure coverage; explicit
incomplete-entry success tests cover observation recording and inbox attachment.
Windows Python 3.14.6 was used locally; normal PR CI supplies broader validation.

Ruff 0.16.5 E9 and `git diff --check` passed. Targeted Pyright 1.1.411
reported no diagnostics in the two new modules. Across the collection/editor
surfaces, 74 existing diagnostics remain versus 81 on main; comparison by file,
rule, and message found no added diagnostics. This is not a claim of a clean
whole-editor or whole-repository type check.

The earlier full run's nine Doctor failure entries reproduced on main inside the
sandbox and passed on this foundation outside it. Its Hypothesis input-generation
health-check error also passed outside the sandbox. No Doctor behavior or
Hypothesis health check was weakened. Native GUI acceptance is not claimed.

Future Work Queue reconstruction must consume `CollectionItemReference` captured
when a task is displayed and resolve it before navigation. Merely using the new
editor service does not fix a stale task that already chose the wrong record.
Adapt to main's retained load-state names and array persistence; do not replay the
old patch unchanged. Merge this prerequisite before that separate work.
