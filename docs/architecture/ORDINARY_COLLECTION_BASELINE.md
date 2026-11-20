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

## Proposed Option B amendment — not adopted

Status: PROPOSED — ordinary-media Phase 1 new-item first saves only.

This section records proposed replacements and additions to the approved
contract above, using source revision
`ccaf7e8d1b3eced4f19cbf899e3e3ae2a53ad8a8`. It does not adopt those changes.
The existing approved clauses remain governing until explicit owner adoption.
Documentation preparation, PR submission, or review provides no implementation
authority or technical acceptance.

Package 0 remains BLOCKED; Phase 1 remains NO-GO; Phase 2 remains HOLD; the
execution allowlist remains EMPTY. No historical Package 0 evidence is repaired
or reclassified by this proposal.

### Proposed replacement: stale-baseline rejection

Upon adoption only, replace the opening passage beginning "A mismatch writes
nothing" through "Existing CRUD rollback remains intact" with the following.
The preceding exact-byte comparison and locking requirements and the following
publication-receipt requirements remain unchanged.

On a baseline mismatch, ordinary save must not publish collection JSON or
persist the attempted record change. It must report that storage changed
elsewhere, that the attempted change was not saved, and that explicit collector
reload is required. No merge, retry, silent reload, or override is authorized.
Media staging and retained artifacts are governed by the Option B first-save
exception below; this exception does not permit collection JSON publication on
a stale baseline. Existing CRUD rollback remains mandatory except for the
expressly permitted retention of attempt-created managed media during an
eligible new-item first save.

### Proposed replacement: bounded write-path map

Upon adoption only, replace the first bullet of "Bounded write-path map" with:

- Add/update/delete, photo migration, CSV, and reviewed visual/OCR persistence
  use ordinary save and retain their existing rollback or managed-image cleanup
  behavior. The sole exception is retention of attempt-created managed media
  for eligible ordinary-media Phase 1 new-item first saves, as defined below.
  This exception does not extend to existing-item edits or other write paths
  merely because they create media.

Leave the unrelated `type_design`/CSV compatibility paragraph unchanged.
Upon adoption only, replace the concluding exclusions paragraph of "Bounded
write-path map" with:

No new storage format, recovery/journal redesign, backup behavior, cloud
behavior, or visual cancellation changes are introduced. Image transaction
authority remains unchanged except for the eligible ordinary-media Phase 1
first-save cleanup exception expressly defined below. Tests use synthetic files
and deterministic intervening writes only.

### Proposed addition: Option B first-save exception

The following addition is proposed immediately before "Material saved identity
correction". It is not current execution authority.

**Scope and creation/edit boundary.** This exception applies only to a
collector-initiated ordinary-media Phase 1 operation that proposes adding a new
collection item. It applies whether the collection JSON already exists or has
an explicitly missing baseline. It does not authorize first-save behavior for
other workflows.

Editing, replacing or attaching media to an already published item remains an
existing-item operation, including when that item has incomplete identity or
unavailable photos. A caller flag, stale in-memory absence, reused ID or previous
uncertain result does not establish that an operation is new-item creation.
Publication must retain authoritative ID validation and ordinary freshness
protection; this exception never authorizes an upsert or overwrite of an
existing item.

**No persistent interruption guard.** Eligible first saves must not create or
depend on a persistent first-save interruption guard, pending-attempt record or
restart-resumption journal. This prohibition does not remove ordinary
collection locking, exact-byte baseline checks, failed-load protection,
publication receipts or transient bookkeeping needed to perform a bounded
attempt.

**Permitted media staging.** An eligible attempt may create exclusively new
managed-media destinations before the final ordinary-save baseline comparison.
It must not overwrite, adopt or reuse existing managed files, or delete or
modify source files. A staged artifact is not a saved collection item and
supplies no authority to publish collection JSON.

**Definite failure, including stale-baseline rejection.** If collection JSON was
definitely not published, the attempted item must not remain an authoritative
saved item in memory. Existing record rollback remains mandatory. Unreferenced
managed media created by the attempt may remain, including incomplete artifacts
left by interruption. Such files must not be referenced by a successful
collection record unless the successful save's media verification requirements
were satisfied.

On stale-baseline rejection, the current collection JSON must remain untouched
by the rejected save, the instance baseline must not advance, and explicit
collector reload is required. Previously staged attempt-created media may
remain. This permission applies to eligible media artifacts only; it does not
change the ordinary JSON writer's temporary-file, replacement or cleanup
contract.

**No orphan lifecycle authority.** Retained artifacts do not authorize automatic
adoption, deletion, reuse, recovery or retry. A later attempt must not discover
and attach them, select them by name or hash, or use them to reconstruct an
interrupted operation. No retention expiry, background cleanup or startup
recovery is introduced. Any future orphan-management operation requires
separate owner authority.

**Uncertain publication.** If JSON publication cannot be determined reliably,
the application must report uncertainty and must not claim either successful
creation or definite non-creation. It must not compensate by rewriting
collection JSON or deleting potentially referenced media. Automatic retry and
replay of the uncertain attempt are prohibited.

The collector must explicitly reload through the ordinary collection load path
before any further save arising from that attempt. Only a successful load
resolves authoritative collection contents and supplies the ordinary baseline;
media presence, cached memory and later destination observations must not
manufacture a publication receipt or baseline.

Reload establishes current collection contents only. It does not prove whether
the earlier attempt published, whether an observed item was created by that
attempt, or whether a currently absent item was never published.

If reload reveals the item, subsequent changes follow existing-item rules.
Reload invalidates pre-reload item references. Any subsequent edit must capture
and validate a fresh reference to the currently selected item; the attempted ID
alone does not establish continuity or item ownership.

If reload confirms its absence, a deliberate fresh creation may be offered as
a separate attempt, subject to ordinary validation and resource limits, without
reusing retained artifacts. Failed reload does not authorize another save. No
cross-restart resumption or replay of the earlier attempt is provided.

The fresh-creation permission after reload is a separate proposed policy detail
requiring owner acceptance; it is distinct from resuming or retrying the
interrupted operation.

**Existing safeguards.** Existing-item reference checks, rollback of unchanged
attempt-owned files, preservation of removed photos and sources, provenance
protection, and authoritative-metadata isolation remain unchanged. Ordinary
collection locking, exact-byte freshness checks, atomic JSON publication,
failure-state protection and receipt-based baseline advancement remain
mandatory for all saves.

**Resources and retention.** Before execution authorization, the owner must
approve finite limits for per-attempt media count and bytes, aggregate
managed-storage consumption including retained artifacts, and minimum available
storage. The resource policy must specify its accounting and concurrency
assumptions. Repeated failures must not bypass the aggregate limit. Exhaustion
must reject further staging without automatically reclaiming retained
artifacts.

Retained media has no automatic expiry under this exception. No claim of bounded
aggregate consumption is accepted until enforcement under repeated failures,
interruption and cooperating concurrent writers is demonstrated. Resource-cap
values and enforcement remain unresolved execution prerequisites.

**Unverified feasibility.** Windows NTFS destination exclusivity, interruption
behavior, publication-result classification, resource enforcement and source
coherence remain unverified. Successful creation must demonstrate that
referenced managed media contains verified bytes from a coherent source
observation. A destination hash alone does not establish source coherence.
This amendment grants no Windows feasibility or crash-durability assurance.
Source coherence and Windows NTFS feasibility remain unresolved execution
prerequisites.

The proposed acceptance and independent-review requirements are recorded in
[Work Queue foundations](../WORK_QUEUE_FOUNDATIONS.md#proposed-option-b-amendment--not-adopted).

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
