# Phone-Entry Reviewed-Save Service

Status: approved implementation boundary for Mobile Coin Entry Packets 1–2.

`phone_entry_service.PhoneEntryService` is a Tk-independent application service.
It does not create a collection model, invoke recognition, or accept a request,
provider, or proposal as persistence authority.

## Required sequence

```text
explicit front/reverse paths
  -> PhoneIntake.confirm_pair
  -> PhoneEntryDraft (DRAFT)
  -> explicit human verification with final fields (VERIFIED)
  -> separate save confirmation (SAVING)
  -> temporary capture package + validated manifest source ID
  -> ReviewedCoinDraft + persist_reviewed_coin
  -> PhoneIntake.complete
  -> phone-entry audit finalization (SAVED)
```

The service always uses the existing capture-package persistence bridge. It does
not replace it with ordinary-entry media ingestion. `persist_reviewed_coin`
retains snapshot validation, managed-image copy/hash validation, collection
baseline checks, atomic publication, cleanup, and rollback behavior.

## Authority and recovery

`verify(..., verification_approval=...)` requires an action-bound approval
validated by an injected trusted host verifier before the service will create a
save intent. `save(..., save_approval=...)` is a second independent, action-bound
approval. A raw client/model boolean is not accepted as either proof. Packet 2
will provide the host-owned verifier from its authenticated session/CSRF boundary.
The sidecar records workflow state but cannot independently authorize persistence:
the injected verifier supplies each approval, and `PhoneIntake` plus the reviewed
save bridge remain the persistence authorities.

`PhoneIntake` remains the durable pair/save authority. A persistence, completion,
or audit-finalization ambiguity changes the sidecar state to
`RECOVERY_REQUIRED`; the service does not retry collection persistence. The only
allowed continuation is `reconcile`, which calls `PhoneIntake.complete` to prove
the actual saved record before finalizing the audit. A recovery record cannot be
used to call `save` again.

## Local audit sidecar schema

`PhoneEntryAuditStore` writes version `1` JSON using the existing atomic writer
and exclusive lock. Each entry is keyed by an opaque UUID and contains only:

- opaque entry, pair, and optional saved-item IDs plus a one-way session
  correlation hash (never a session bearer value);
- creation/update/verification/save timestamps;
- front and reverse SHA-256 values;
- optional bounded proposal slot (currently always `null`);
- human-final `country`, `denomination`, `year`, and `type_design` values;
- per-field `proposal` to human-final change records;
- the `DRAFT`, `VERIFIED`, `SAVING`, `SAVED`, or `RECOVERY_REQUIRED` state and
  reconciliation status.

The sidecar intentionally excludes collection or staging paths, upload names,
IP/device information, cookies, pairing secrets, EXIF, credentials, raw provider
payloads, inferred ground truth, and confidence/probability claims. Its records
are provenance/presentation evidence only; they never authorize persistence.

## Future HTTP boundary

Packet 2 may pass server-owned staging paths into `create_draft` only after its
upload boundary validates those files. A later route can safely present
`PhoneEntryDraft.to_dict()` / `reopen()` because the representation omits the
session ID and every filesystem path. HTTP routes must still enforce session,
CSRF, Origin, Host, and explicit confirmation controls; this service does not
implement network authentication.
