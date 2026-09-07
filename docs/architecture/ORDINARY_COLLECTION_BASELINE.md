# Ordinary collection baseline ownership

Status: APPROVED — stale-write and persistence-state hardening

Each `CoinCollection` owns a baseline of the exact bytes decoded by its last
successful load, or an explicit missing state. Failed loads retain `FAILED`
protection. Ordinary saves compare current bytes with that baseline under the
existing package-import lock before atomic replacement. A mismatch writes
nothing and reports that storage changed elsewhere, the attempted change was
not saved, and explicit reload is required. No merge, retry, silent reload, or
override is authorized. Existing CRUD rollback remains intact.

The atomic JSON writer returns the SHA-256 and byte length of the exact
same-directory temporary file it publishes. This receipt is computed before
replacement, not from a later observation of the destination. Successful own
writes advance the instance baseline from that receipt; failures do not. Loads
hash the same raw bytes they decode. JSON format and atomic publication remain
unchanged. The guarantee covers cooperating locked writers, not an arbitrary
external writer racing after freshness validation.

## Bounded write-path map

- Add/update/delete, photo migration, CSV, and reviewed visual/OCR persistence
  use ordinary save and retain rollback or managed-image cleanup behavior.
- `replace_items_for_import` retains its caller-supplied importer baseline and
  verification authority. When it adopts prospective items, it also adopts the
  exact publication receipt and clears failed-load state.
- `mutate_fields_conditionally` retains its fresh raw-record compare/update
  authority. Successful verified writes adopt both prospective items and the
  receipt. No-op/conflict/failed verification does not advance the baseline.
- Durable importer/recovery publishers retain their own journals and authority.
  Desktop import success already reloads. A writer leaving memory unchanged
  also leaves its prior baseline unchanged; ordinary writes then fail closed
  until reload if disk changed.
- CSV exposes save/read failure via `last_save_error`; its GUI does not show
  success on failure.
- Numista replacement builds the existing intended replacement set in memory,
  saves once through the ordinary guard, and restores prior memory on failure.
  Mapping and duplicate policy are unchanged.

No new storage format, recovery/journal redesign, backup behavior, image
transaction authority, cloud behavior, or visual cancellation changes are
introduced. Tests use synthetic files and deterministic intervening writes only.
