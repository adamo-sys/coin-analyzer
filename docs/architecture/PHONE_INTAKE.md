# Phone Intake MVP

Status: local implementation; scoped review and complete collector acceptance pending.
Canonical base: origin/main 1857e3372b7a6ba24c529eec2cac6c31e93260dc.

## Ownership and pairing

Import Phone Photos creates application-owned staging copies without modifying
originals. Byte-identical renamed imports are detected by SHA-256, not perceptual
similarity. Imports are serialized and publish a completed, hash-checked copy.
HEIC/HEIF remain unsupported; paired visual review requires JPEG/PNG.

Photo Inbox scan groups remain suggestions. Pair and Review Phone Photos confirms
exactly two distinct images and collector-assigned Front/Reverse roles. Filename,
time and adjacency never establish a pair. Retakes/orphans remain unpaired. Swap
is permitted before saving; changing roles during review invalidates that save.
An image hash cannot silently belong to two pairs. Later imports/scans do not
change confirmed membership. Explicit pairs use data/phone_intake.json with the
existing atomic JSON writer and exclusive filesystem lock. Invalid state is not
reset. Legacy group handoff refuses paired images; fully paired legacy groups
are omitted from its pending list.

## Review and save authority

Review Pair reuses the two-image capture adapter, existing provider disclosure,
visual review, collector corrections and separate save confirmation. It does not
start batch inference or change provider contracts. AI proposal values/coverage
remain independent of edits. Cancel/reject/defer/save decline retain the READY
pair and staging copies without creating a collection record.

After confirmation, the existing managed-media transaction saves the corrected
coin and both photos. Inbox owns unsaved work; Work Queue remains derived only
from saved records under existing rules. No collection model/status rule changes.

Before persistence, a durable intent changes READY to SAVING and records the
absolute target collection path, reserved UUID, date, confirmed identity and
existing role-specific image hashes. The UUID/date are passed to persistence.
After success, completion checks the actual on-disk record and both managed photo
hashes, then marks only that pair SAVED. Relative media references resolve against
the application media base recorded at reservation.

Collection success remains authoritative if Inbox completion fails. The UI says
'Coin Saved - Inbox Reconciliation Required'. SAVING prevents resaving after a
restart. Reconcile Save verifies that record and completes Inbox metadata only;
it never writes the collection, creates a coin, or calls a provider. Wrong
collection, changed record/media, missing target or unreadable state stay blocked.
A crash after reservation but before persistence requires operator investigation;
an absent target is not automatic permission to retry. A caught, proven clean
persistence failure can return to READY only after checking that its reserved
record is absent on disk. Recovery-required errors remain blocked. Existing stale
save refusal and managed-media rollback are preserved.

## Boundaries and acceptance

Refresh/Next Pending updates the pair list; neither dispatches a provider request.
Staging copies are not automatically removed. Pair regrouping/unpairing is not
provided in this MVP; inspect the previews before confirmation.

No mobile code, sync, watcher, conversion, auto-pairing, perceptual deduplication,
batch AI, type/design search, new Work Queue rule or evaluation export is added.
Collector evidence is not automatically benchmark truth. Any future evaluation
selection remains separate from collection identity and requires its own review.

Focused synthetic tests cover grouping-independent pairs, role assignment/swap,
restart, duplicates, cancellations, save/rollback and completion failure recovery.
Native widget tests do not establish a full first-run or real-phone acceptance.
The remaining manual journey must use a transferred iPhone JPEG batch, inspect
orientation/large-photo layout and pairing, correct/cancel/review/save, restart,
verify identity/photos/Work Queue, and advance to the next pending coin.
