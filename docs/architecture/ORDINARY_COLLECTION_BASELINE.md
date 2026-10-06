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

Collection JSON has an additive optional `type_design` string (empty when absent
in legacy records). Ordinary collection CSV supports the same optional column;
no value is inferred from notes, title or catalog references. Confirmed reviewed
drafts and the existing guarded item editor carry the collector-owned value.
Older application versions may ignore/drop this new field if they rewrite a
newer collection. No migration/backfill or transaction-authority change is made.

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

## Material saved identity correction

Ordinary `update_item` and raw `mutate_fields_conditionally` share one private
transition policy. A difference in country, denomination, year or type/design,
compared with collapsed whitespace and case folding only, is material. Stored
collector text is retained verbatim; presentation-only and unrelated edits do
not invalidate metadata or reconcile untouched legacy records.

One material transition appends a deterministic, labelled superseded-value JSON
snapshot to effective notes, preserving existing notes and initial-save review
summaries. It clears title, issuer, reference, Numista number, currency and face
value, resets detection metadata, and sets `from_numista=False`. Thus a corrected
specimen joins the existing manual-entry set preserved by Numista replacement.
The final identification status is derived from current identity after clearing
these dependencies. Type/design triggers invalidation but does not itself count
as factual identity in the existing status rules.

Requested and generated fields publish together. Ordinary save failure restores
all affected in-memory values, including notes and status, and retains existing
stale-baseline and media rollback safeguards. Conditional commands retain their
exact three-field external authority and raw comparisons; history includes only
actually present pre-transition keys. Verification covers the generated fields
as well as requested values. Already-applied commands generate no history and
write nothing. Post-publication verification failure reports uncertainty without
a compensating rewrite; explicit reload precedes retry. No load-time repair,
new persistence field or reconstructed provenance is introduced.
