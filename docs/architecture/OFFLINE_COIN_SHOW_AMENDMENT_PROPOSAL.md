# Proposed additive amendment: offline coin-show companion

Status: PROPOSED ONLY, not adopted and not implementation authority.
Date: 2026-10-20. Planning base:
e350644539c062ff1700fa58875ff26b02a89258.
Owner review package: [combined design](OFFLINE_COIN_SHOW_DESIGN.md).

## Purpose and limited effect

The owner-approved product milestone is offline coin-show lookup plus queued
collection entry on an iPhone 13, iOS 27.0.1, Safari home-screen PWA, including
operation with PC off. Existing [north-star planning](mobile-coin-entry-human-verification-north-star.md)
excludes PWA/offline sync from its first LAN demo; the
[local-host boundary](PHONE_ENTRY_LOCAL_HOST.md) specifies trusted-LAN HTTP and
the [reviewed-save service](PHONE_ENTRY_REVIEWED_SAVE_SERVICE.md) requires an
explicit front/reverse pair with separate verification and Save approvals.

If explicitly adopted through owner-approved repository review, this amendment
would add the bounded companion below. It would qualify those scope exclusions
only for this new milestone; the existing demo's authority and transport remain
unchanged. This proposal edits none of those documents, no governance file and no
frozen baseline. It supplies no execution, deployment or live-data authority.

## Proposed clauses

1. **Offline preparation and operation.** A separately installed companion may
   cache its complete application shell under a stable private trusted HTTPS
   origin and retain owner-selected collection/target projections, local entries
   and photos. After preparation, lookup, review, capture and purchase queuing
   require neither a running PC nor network/AI. Provisioning/trust must be tested
   and separately authorized; HTTP demo installation is not a substitute.
   HTTPS alone is not device authentication. Provisioning and every update fetch
   require the proposed local owner-approved single-use pairing and server-side
   short-lived session in design sections 3.1-3.2; no existing identity provider or
   implemented authentication is asserted. A five-minute random pairing secret
   plus desktop approval issues a host-only Secure/HttpOnly/SameSite=Strict cookie;
   server expiry is 30 minutes idle/eight hours absolute, with no refresh token.
   Each protected asset/manifest/worker request checks the session and device grant;
   absent/expired sessions and revoked grants disclose no protected bytes or 304.
   Provisioning grants shell retrieval only, never collection/desktop Save access.

   Credentials/tokens never enter source, PWA assets, URLs, logs, browser app stores
   or exported purchase/snapshot/receipt/recovery bundles. Only the browser cookie
   jar holds the client session; pairing input is transient. The server retains
   token hashes, enforces expiry/logout/revocation and denies on store failure.
   Only minimal enrollment endpoints are public; approval/revocation are trusted
   desktop actions. Authentication responses are network-only/no-store. HTTP caches
   must not bypass auth; explicit Cache Storage permits only the complete verified
   credential-free shell allowlist obtained after authorization, never auth/API/
   error/redirect responses. No cached flag or bundle conveys server authority.

   A previously authorized complete installation starts and uses local data without
   a live authentication request even with an expired/missing session, revoked
   grant, unavailable network or PC off. Revocation immediately denies future
   protected server retrieval, but cannot recall cached offline code/data or wipe
   the phone. First installation requires reachable trusted HTTPS and approved
   pairing in the installed context; unavailable/denied setup is not offline-ready.
   Reconnect never auto-transfers, Saves or silently re-enrolls. Expired sessions
   require new pairing and revoked devices a new explicit owner grant for online
   access. Update denial, TLS/server failures, timeout, partial/login content or
   network loss keep the previous complete compatible shell/database and pending
   evidence; no login wall, forced reset or data deletion. Browser update checks
   cannot block local startup or weaken server authorization. Device feasibility
   must prove authenticated retrieval and independent cached startup together.

2. **Queue ownership.** Browser records are private candidate/purchase evidence.
   An explicit Purchased/Pending sync action commits a reviewed local revision
   and media inventory. It neither creates nor updates a collection item. One or
   more explicitly assigned photos are permitted locally; missing information
   stays visible. The browser is not a new collection database or decision owner.

3. **Advisory comparison.** Results distinguish saved identity matches, potential
   explicit tracked gaps, possible variants/upgrades, outside targets and
   insufficient information. Relevant snapshot/target coverage and freshness are
   visible. Absence alone and observed year ranges do not establish a gap.
   Clearly labelled pending purchases participate in subsequent checks; uncertain
   identity cannot silently fulfill a target. No invented provenance/confidence.

4. **Browser persistence boundary.** Acknowledged writes require committed
   IndexedDB entries and photo bytes; ordinary closure, locking and connectivity
   loss are acceptance cases. The service worker caches rebuildable shell assets,
   never Save requests or authority. Browser quota, clearing, eviction, lifecycle
   and device-loss limitations are explicit. Private verified export/restore is
   required; origin storage is not a backup. Failure never justifies silent reset,
   pending-photo eviction, fabricated success or background-save dependence.

5. **Transfer authority.** Explicit private bundle export/import may stage phone
   purchases into a desktop inbox. The first milestone is file-mediated; later
   authenticated foreground private HTTPS transfer must use the same contract.
   Connectivity, receipt import, offline review, purchase flags and imported
   booleans do not authorize collection persistence. No remote/public listener,
   cloud state or cached credential for unattended writes is introduced.

6. **Stable identity and duplicate suppression.** A durable desktop ingress
   registry binds one selected collection lineage and stable mobile entry UUID to
   one accepted revision/digest and one existing service/pair association. Repeat
   import preserves that association and never offers another Save. A conflicting
   revision, missing mapping, changed collection binding or ambiguous outcome
   blocks for owner reconciliation. The registry correlates staging and outcome;
   it does not replace PhoneIntake reservation or actual collection/media proof.

7. **Existing desktop Save boundary.** Before collection mutation, the owner must
   review current collection evidence and explicitly verify identity, then
   separately confirm Save through the existing trusted desktop application
   boundary. The selected distinct obverse/reverse pair uses PhoneEntryService,
   PhoneIntake and the existing guarded reviewed-save bridge. One-photo entries
   wait in the inbox for missing media. Extra photos/details remain recoverable;
   mapping omissions cannot be reported as saved. No duplicated side, direct
   collection JSON write, new media transaction, automatic quantity increment or
   browser-derived approval is permitted.

8. **Interrupted outcome and receipts.** An interrupted/ambiguous Save reconciles
   the original service/pair/reservation against actual disk records and canonical
   media. It never starts another Save. Collection success plus audit/receipt
   failure remains recovery-only. A saved receipt is emitted only after existing
   completion/finalization evidence agrees. The phone correlates the exact entry,
   binding, accepted digest and final desktop result, keeps unresolved purchases
   pending and never deletes media merely because transport succeeded.

9. **Unchanged contracts.** The frozen durable-persistence/importer schema,
   locks, journal, recovery rules and ordinary stale-baseline protection retain
   their current meaning. No collection schema change, migration, automatic
   reload/merge/retry, backup redesign, evaluation/provenance policy change,
   recognition authority or Phase 2 release is adopted by this amendment.

## Adoption and implementation gates

Owner adoption must explicitly accept these clauses and the design's technical
decisions/limits. Written adoption is distinct from authorizing implementation.
Each future slice requires its own bounded task and approved base/authority.

Before enabling the capability, prove:
- Design A24-A29: unapproved/expired/revoked requests (including direct assets,
  HEAD/conditional and worker fetches) deny access; pairing/CSRF/rate limits and
  session expiry/logout/revocation hold; provisioning cannot access collection or
  desktop authority; credential and cache/export boundaries survive inspection.
- Cold-start/deep-link with expired/deleted sessions, server revocation, PC off,
  unavailable or hanging network/auth: cached local capture/comparison/queue/recovery
  work without live authentication. Restored bundles never grant server access.
- First-install denial/offline is not-ready; installed-context pairing and all
  manifest/icon/worker fetches are authenticated; reconnect and failed updates
  preserve exact pending IDs/media and the last complete shell without automatic
  transfer, Save, re-enrollment or erase. Test on the named iPhone, not only emulation.
- Offline cold startup and committed photo/entry retention on the named iPhone
  through closure, locking and disconnected operation.
- Verified private export/restore and truthful complete-storage-loss behavior.
- Coverage-aware matching and pending/saved-since-snapshot overlays.
- Re-import/concurrency/crash duplicate suppression and original-operation
  recovery, including missing ledger, stale collection, changed records/media
  and interrupted audit/receipt.
- Separate desktop Verify/Save approvals, existing persistence gates, privacy
  controls and current blocking CI for the implementation head.

The detailed acceptance matrix and incremental slices are in the
[combined design](OFFLINE_COIN_SHOW_DESIGN.md). No production or device tests
have been run by preparing this amendment. The bounded correction authorization
permits committing only these two documents and opening a documentation-only PR
only after fresh independent review passes without blocking findings. Final merge,
adoption, implementation and deployment remain subject to separate owner authority.
