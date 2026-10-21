# Offline coin-show assistance and queued collection entry

Status: PROPOSED, for owner review; no implementation or architecture adoption.
Date: 2026-10-20. Verified main and task planning base:
e350644539c062ff1700fa58875ff26b02a89258.
Branch: codex/offline-coin-show-design.
Worktree: C:\Users\adamo\.codex\worktrees\offline-coin-show-design\coin-analyzer.

## 1. Contract and agreed outcome

GOAL: Reviewable offline coin-show design, smallest architecture amendment,
acceptance criteria, and incremental implementation slices.
IN SCOPE: This document and [amendment proposal](OFFLINE_COIN_SHOW_AMENDMENT_PROPOSAL.md);
bounded authentication/offline-startup correction and focused documentation checks.
Fresh independent review must pass without blocking findings before the owner-authorized
commit of these two files and documentation-only PR.
OUT OF SCOPE: Production implementation, dependencies, deployment, live collection
or photo access, migration, governance/baseline edits and merges.
PROTECTED BOUNDARIES: Local-first operation; collector-owned identity; explicit
desktop Save; provenance; frozen persistence; private/local data; unrelated work.
ACCEPTANCE GATES: Source-backed design review, whitespace/link checks, independent
review, then owner approval. Future device and behavior tests are unrun.
STOP CONDITIONS: Authority/base mismatch, architecture/privacy contradiction,
blocking review finding, scope expansion, and AGENTS.md context-budget stops.

The owner specified iPhone 13, iOS 27.0.1, Safari, installed home-screen PWA,
mandatory offline operation. This is the acceptance device, not a device tested
during this design task. Do not infer capabilities from the version string.

Away from home with the PC off, the collector takes one or more photos,
reviews/corrects identity, and compares with an offline collection reference and
collecting targets. A purchased candidate reuses the same photos/details and
becomes Pending sync. Pending purchases participate visibly in later checks.
Desktop review and a separate explicit Save remain the only collection entry
authority. Phase 2 HOLD remains unchanged.

## 2. Evidence and the smallest change

| Inspected seam | Finding and design consequence |
| --- | --- |
| [First demo](../PHONE_ENTRY_FIRST_DEMO.md), [host contract](PHONE_ENTRY_LOCAL_HOST.md), [template](../../templates/phone_entry.html) | Current pages post to a running PC over approved private-LAN HTTP. There is no offline app lifecycle in this flow. Add a separate offline companion. |
| [Reviewed-save contract](PHONE_ENTRY_REVIEWED_SAVE_SERVICE.md), [service](../../phone_entry_service.py) | create_draft requires front/reverse; verify and save require separate trusted approvals. save failures become recovery, and reconcile never invokes persistence. Reuse this boundary after desktop review. |
| [PhoneIntake](../../phone_intake.py), reserve and _saved_record | Reservation durably binds pair, item ID, collection, final identity and time. Completion checks actual collection and exactly two canonical role-bound images. One-photo entries cannot silently use this bridge. |
| [Collection intelligence](../../collection_intelligence.py), detect_missing_years_for_years and _identity_key | Missing-year suggestions use the observed min/max interval; identity omits type_design. Neither is an authoritative tracked-gap contract. |
| [Companion](../../mobile_collector_companion.py), collection_context; [watchlists](../../watchlist_engine.py) | Current context truncates active targets and includes preset priorities; watch queries are largely free text. Export explicit reviewed targets and coverage instead of treating these summaries as complete. |
| [CoinItem](../../coin_collection.py) | Has country, denomination, year, type_design, catalog references, grade, identification status, quantity and acquisition fields. Missing structured distinctions stay unknown; do not parse notes to invent them. |
| [Ordinary baseline](ORDINARY_COLLECTION_BASELINE.md), [frozen persistence](durable-persistence.md) | Stale baseline rejects writes; no automatic merge/reload/retry. Importer durability is a separate authority and is not a browser-storage guarantee. |

The frozen persistence file's Git/LF SHA-256 matches
A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4.
Its worktree CRLF bytes have a different hash; line-ending normalization explains
the difference. No existing baseline is edited.

Inspected tests include [service tests](../../tests/test_phone_entry_service.py)
for separate confirmations, stale collection, persistence failure, and failed
audit finalization followed by reconciliation; [host tests](../../tests/test_phone_entry_host.py)
cover request/media boundaries; [intake tests](../../tests/test_phone_intake.py)
cover reservations and ambiguous outcomes. These are source-inspection findings,
not a claim that tests ran.

## 3. Proposed architecture and transfer choice

| Approach | Trade-off | Recommendation |
| --- | --- | --- |
| Private file bundles, explicit import and receipt return | More user steps; no phone-to-PC network connection or background task needed at transfer time. Files can be carried by owner-selected local transfer. | First milestone. |
| Foreground paired LAN transfer over trusted HTTPS | Smoother repeated transfers; requires new TLS, session, Origin/CSRF and stable-host work. Internet connectivity alone does not reach the desktop. | Later transport using the same payload/receipt contract. |

Use a stable, owner-controlled private HTTPS origin with authenticated access
to provision/update the PWA at home; HTTPS alone does not authenticate a device. The PC may host it while running; at the show startup uses the installed
service worker and cached shell. No public host, tunnel, cloud account, CDN,
external font, analytics or runtime provider is required. A self-signed warning
page is not an installation strategy. Local certificate trust and stable
hostname/port provisioning require an owner-approved packet and real-device test.
The phone's localhost is the phone, not the PC.

The existing HTTP demo is retained for its existing bounded purpose. Do not add
a service worker to that HTTP origin and claim offline readiness. Do not connect
an HTTPS companion to its HTTP endpoints. File-mediated transfer keeps the first
milestone independent of that transport.

Component responsibilities:

    Desktop snapshot exporter -> private snapshot file -> installed PWA
    Cached app shell -> IndexedDB snapshots + entries + photos + outbox
    Reviewed identity + snapshot + pending overlay -> advisory comparison
    Explicit purchased action -> immutable pending operation
    Explicit private export -> desktop staging inbox -> desktop review
    Separate desktop Verify + Save -> existing guarded persistence
    Verified desktop receipt -> explicit import on phone -> pending reconciliation

The staging inbox, export files and browser queue are not collection records.
Transport completion never means collection Save.

### 3.1 Proposed provisioning authentication and authorization

These are proposed requirements, not verified capabilities. No identity provider,
pairing service, session store or authenticated PWA provisioning is claimed to
exist. The existing HTTP demo supplies none of this authority. The proposed first
milestone uses local owner-approved pairing, without an external identity provider:

1. The owner enables enrollment from the trusted desktop UI. The server generates
   a cryptographically random, single-use secret with at least 128 bits of entropy,
   valid for five minutes, and displays it only there. The owner enters it into a
   minimal same-origin HTTPS enrollment form on the intended installed app/device.
   Submission uses a POST body, never a URL/QR link. Before issuing access, the
   desktop owner explicitly approves that pending attempt against a matching
   displayed attempt identifier on both screens. Rate-limit attempts and return
   generic denials; expired, consumed, rejected or unapproved attempts grant nothing.
2. Successful pairing creates a server-side device grant and a fresh random opaque
   bearer session with at least 128 bits of entropy. Store only secret/token hashes
   and grant/session metadata server-side under desktop-user access controls.
   Deliver the token only in a host-only `__Host-` cookie with `Secure`, `HttpOnly`,
   `SameSite=Strict`, `Path=/` and no Domain. Rotate on new authentication; reject
   client-selected/fixed tokens. Server-enforced limits: 30 minutes idle and eight
   hours absolute, without automatic renewal or a refresh token. Missing browser
   cookies require pairing again; no persistent device credential is stored in JS.
3. On every protected request, the server checks the session, both expiries and
   current device grant. Deny by default, including direct asset paths, GET/HEAD,
   conditional requests and worker/update fetches. A valid session grants only
   retrieval of the versioned companion shell, manifest, worker, icons and update
   metadata/assets. It grants no collection, photos, snapshot API, inbox upload,
   desktop administration, enrollment approval, Verify or Save capability. These
   remain outside the provisioning listener; transfer stays file-mediated.
4. Only the minimal enrollment/status endpoints may be reached before pairing;
   they expose no app assets, collection data or grant inventory. Network requests
   for protected resources return 401 for absent/expired sessions or 403 for a
   revoked grant, with no protected body, redirect-to-login content, or usable 304.
   State-changing authentication requests require same-origin Origin/CSRF checks;
   reject cross-origin access. Enrollment approval and revocation are desktop-only.
   A server/store failure also denies protected resources rather than bypassing auth.
5. The owner can revoke a device grant or all grants from the trusted desktop UI;
   invalidate associated sessions immediately and check revocation on each request.
   Logout invalidates the current session and expires its cookie. Expiry/logout
   require a new owner-approved pairing for online access. A revoked device requires
   an explicit new owner grant, never silent re-enrollment. Lost grant/session
   state denies access and requires owner recovery; it is not recreated from a
   client ID, receipt or bundle. A device label/ID alone is not authentication.

This authenticates possession of a short-lived approved session, not hardware
identity or the person currently holding the phone. A stolen cookie can act until
expiry/revocation. Physical phone access can expose cached app/data; use the phone's
OS lock. Revocation cannot recall already delivered code/data or enforce remote
wipe/offline lockout. Do not claim either property. Owner adoption of this proposal
must accept that boundary; future implementation still needs security/device gates.

### 3.2 Secret handling and cache boundary

Pairing secrets and session tokens must never be embedded in the PWA bundle,
source code, configuration committed to Git, manifest/start URL, query/fragment,
logs, purchase/snapshot/receipt exports or recovery bundles. Do not store them in
IndexedDB, localStorage, sessionStorage or Cache Storage. Clear the pairing form
and transient memory after submission/failure/expiry; never persist the entered
secret. The browser cookie jar is the only client session store, inaccessible to
app JavaScript; cookie expiry never controls local data retention. Session/CSRF
responses stay network-only with `Cache-Control: no-store`; suppress secret values
in server diagnostics. CSRF values, if used, are transient and never exported.

All server responses use `Cache-Control: no-store` to prevent intermediary/HTTP
cache reuse bypassing authorization. The sole deliberate Cache Storage exception
is a complete, versioned allowlist of credential-free shell assets fetched after
successful authorization. Asset responses must not set cookies or contain tokens,
user/session metadata or collection payloads. Authentication responses, errors,
redirects, protected APIs and POSTs are never put in that cache. Verify response
status, expected type, version and asset hashes before publishing a replacement;
login/error HTML cannot become an app asset. No cached session-valid response,
local enrollment flag or restored bundle can authorize a server request.

The installed worker serves this previously authorized shell locally; it never
uses cached content as a fallback for a protected API/authentication request.
Private snapshots, entries, media and queue stay only in the explicit IndexedDB
and private file workflows already defined below. Export/import restores evidence,
never cookies, grants or server authority. Do not add a general offline proxy.

## 4. Snapshot and collecting-target contract

Desktop export is an explicit owner action selecting the collection and target
scope. It reads a successfully loaded baseline without mutation, detects changes
during preparation, and labels the resulting point-in-time reference. Replacing
a snapshot on the phone is atomic and never replaces pending entries.

A versioned snapshot carries:
- Snapshot UUID, export time/timezone, schema and matching-rule versions, digest,
  opaque target-collection binding, source revision fingerprint, and coverage.
- Minimal item projection: real item ID, item type/status, country, denomination,
  year, type_design, available structured catalog identifiers, quantity, and
  optional collector-recorded grade. Unknown remains unknown.
- Explicit active target records with stable IDs, provenance to the selected
  target/source revision, human-reviewed structured predicates, required identity
  dimensions, and whether each predicate is machine-evaluable or text-only.
- Coverage records describing included/omitted items and targets. No silent
  truncation. An incomplete export cannot support a global absence claim.

Exclude photos, private notes/comments, prices, seller details, paths and secrets
by default. Additional fields need separately reviewed user purpose. The
collection binding is issued and durably retained by the desktop ingress registry
for one selected collection lineage; it is not a pathname or a changing file hash.
No new collection schema field is proposed. A rename, copied collection, restored
older collection or missing registry requires owner reconciliation of the binding.

Import validates schema, lengths/counts, digest and binding before activation.
Reject unsupported versions and incomplete payloads; retain the last valid
snapshot. Digests detect corruption, not trusted provenance or authorization.
The owner explicitly selects/imports a private snapshot; do not auto-trust a file
from its extension. No live records were exported for this task.

Always show "Collection snapshot: [export time], [coverage]" and "Targets:
[revision/time]" plus pending count. Snapshot age is informational, never a
freshness guarantee. A 7-day age warning is a proposed UI default; unknown/future
clock values show freshness unavailable. Old snapshots remain usable with visible
warnings, and comparisons say "in this snapshot." Desktop always checks the live
baseline later. Empty, unavailable or partial snapshot is distinct from no match.

## 5. Identity review and comparison

Manual entry works fully offline; optional OCR/recognition is absent in the first
slice. Display source/proposal separately from collector values. Offline
confirmation records what the collector checked; it is not desktop Save approval.
Changes to fields or photo roles invalidate that revision's confirmation.

Use a versioned conservative comparison over explicit country, denomination,
year, type/design and available catalog/variant distinctions. Normalize safe
whitespace/case only; preserve raw values and meaningful variants. No free-text
notes parsing, fuzzy score as probability, or invented catalog provenance.
Photo hashes indicate identical bytes, not the same physical coin.

Evaluate in this order, retaining all relevant evidence tags:

| Result | Required basis |
| --- | --- |
| Insufficient information | No valid reference, missing required identity dimensions, unknown item identity/status, incomplete relevant coverage, or ambiguous/non-evaluable target. Name what is missing. |
| Already recorded | Identity dimensions required by the comparison are known and equal to saved snapshot item(s). Means an identity match, not proof this is the same physical specimen. Show item IDs/quantity and snapshot date. |
| Possible variant/upgrade | Related saved/pending identity exists but a distinguishing field differs/is unresolved, or collector explicitly requests a condition comparison. Show evidence; never claim an upgrade from a heuristic grade rank. |
| Potential tracked gap | A specific explicit evaluable target matches, relevant snapshot coverage is complete, identity is sufficient, and neither saved items nor pending overlay fulfill the target. Cite target and matching dimensions. |
| Outside targets | Sufficient identity and complete target coverage show no applicable target. "Not found in snapshot" can accompany this; absence alone is never a gap. |

A text-only desire can be shown as a possible target requiring review, not a
verified gap. Do not invent minted-year universes from min/max dates.

Compute against saved snapshot plus all active Pending sync purchases, imported
pending purchases and recovery/awaiting-receipt entries. Label each pending match
"Pending purchase: [entry ID]" and block a second gap claim for that exact target.
A fuzzy/partial pending identity produces a possible collision warning and
insufficient-information result, not an assumed fulfilled target. Draft sightings
do not count as purchases.

Receipt-confirmed saves remain as a "Saved since snapshot" overlay until a new
snapshot demonstrably includes the exact item ID and matching identity. When it
does, de-duplicate by receipt/item identity; do not count both. If a refreshed
snapshot omits/changes it, flag a conflict and preserve the receipt/overlay.
Cancelled purchases stop satisfying targets only after explicit local action;
a transferred/saving entry needs desktop outcome reconciliation first.

## 6. Photo capture, local writes and retention

An entry can hold 1+ photos with explicit roles: unassigned, obverse, reverse,
detail. Never infer roles from sequence or duplicate an image to fill a side.
One photo suffices for offline review and Pending sync. Existing reviewed-save
requires two distinct explicitly selected sides; a one-photo purchase syncs to
the desktop inbox as needs-more-media. Extra photos stay attached to the private
inbox/archive and phone until explicitly retained or deleted; the existing pair
bridge saves only the selected pair. No extra media is silently dropped or
attached using a new collection persistence path.

Initial candidate envelope: up to 8 retained photos per entry, each <=16 MiB,
<=30 MP and <=8,000 pixels per edge; a selected saved pair <=32 MiB.
A session/total storage cap is checked separately. Limits are product proposals
to validate on the iPhone, not guarantees of available quota.
The offline app validates bytes/decoded type and image limits, normalizes JPEG/PNG
to strip embedded metadata, and preserves the actual normalized evidence bytes
and SHA-256. Original upload bytes are not part of the retained/exported contract.
No silent downscaling or re-compression for quota recovery. HEIC/HEIF and undecodable
photos show unsupported with a JPEG/PNG retake/select action; verify actual camera
output on the acceptance device. No browser filename, EXIF or claimed MIME drives
a path. Desktop independently validates and canonicalizes its selected pair,
recording its own hashes separately from normalized phone hashes.

Use IndexedDB for entries, normalized image Blobs, snapshots, immutable outbox
operations, receipts, and local metadata. A single database allows atomic
transactions across these stores. Cache Storage holds rebuildable shell assets
only; localStorage/sessionStorage and object URLs are not durable photo storage.
OPFS adds a second commit protocol and has the same origin-loss boundary, so is
deferred.

Persist each captured photo before showing "Retained on this phone." Perform
decode/hash/normalization before opening the short write transaction. Atomically
publish photo bytes, role/reference, entry revision and reference count; wait for
transaction completion and verify committed readback. Show "Writing..." until
then. Field edits persist in short transactions; show an unsaved marker until
commit. Pending sync requires an explicit tap and a committed transaction binding
the reviewed revision, all referenced media hashes, purchase flag and outbox
operation. No unload handler, debounce timer or in-memory preview is the final
commit point. Startup reopens the database and validates references/hashes before
showing a resumable entry. A previous committed revision survives an interrupted
replacement; incomplete work is visibly incomplete.

Request persistent storage and display granted/denied/unavailable status. Use
storage estimates as advisory headroom, reserve temporary export/update space,
and handle actual transaction/quota errors. Ask for strict durability where
supported; a hint is not a filesystem/power-loss guarantee. Failure to write
leaves the previous committed state, an explicit not-retained error and retake
or recovery/export guidance. Never evict unsynced photos or pending operations
to make room. Rebuildable caches may be reclaimed first.

Use IndexedDB transactions with expected revision checks to serialize competing
PWA windows. Immutable operation IDs and desktop locking also protect re-imports.
A stale editor must reload/review instead of overwriting another revision.
No service-worker message or network callback creates purchase/Save intent.

## 7. Offline startup, updates and iOS lifecycle

Provision while online at home, then launch the installed PWA and perform setup
there. Complete pairing in the installed app if its cookie/session is absent;
do not assume a Safari tab's storage or authentication transferred into it.
A stable manifest ID, standalone display, start URL, HTTPS origin/port and service
worker scope remain fixed; hostname changes are a migration, not an update.

Cache a complete versioned app shell: start/navigation fallback, HTML, JavaScript,
CSS, icons, local validation/matching data and restore screen. Installation fails
without all required assets; keep the previous complete shell. Navigations within
scope resolve to the cached shell immediately, without awaiting network or a live
authentication request, even after session expiry, logout or server revocation.
Dynamic snapshot/entry data comes from IndexedDB. Only the credential-free shell
allowlist in section 3.2 may be cached after authentication; pairing/session
responses, collection endpoints and POST/Save requests must never be cached.
Deep links require the same offline navigation fallback. Local startup must not
wait for a session-status fetch, DNS, redirect or timeout.

"Ready for offline use" requires controlling worker, complete verified shell,
database/photo write-read test, valid selected snapshot/targets and a successful
cold start with PC off and connectivity disabled. Show degraded modes separately.
No first-ever installation or recovery of an evicted shell is promised offline.

Updates are user-deferred while dirty/recovery work exists. Do not force
skipWaiting/client reload or erase old caches before replacement is verified.
Database upgrades preserve unknown/newer versions without resetting, stop on
blocked/version conflicts and permit export with compatible code. Keep a
compatible old shell until the new shell/database pairing has passed checks.
No timer-based background work, push or Background Sync is required.

Authentication controls new server retrieval, not use of an already provisioned
local copy. Local capture, comparison, queuing, recovery export and file-mediated
transfer remain available without a current server session; none authorizes a
protected server request. Disable navigation preload/network-first startup.
Browser-initiated worker update checks may still occur when connected, but cannot
block local startup, fetch an unauthorized replacement or activate login content.
Do not implement background session polling or automatic protected fetches from
application code; offer an explicit foreground provisioning/update action.

| State/event | Required behavior |
| --- | --- |
| First installation, no complete shell | At home with reachable trusted HTTPS, complete pairing and authorize every required fetch; prepare/test in installed context. Without network or approval, explain setup required and do not report offline-ready. A minimal enrollment form is not the offline app. |
| Previously authorized installation; expired/missing session, PC off or network unavailable | Start the last complete cached shell immediately and use committed local data. Show online authorization unavailable/required only for a requested online action; no login wall or redirect on local startup. |
| Revoked grant | Server denies all further protected retrieval immediately. Existing local app/data remain usable, including offline; once a foreground request reports revocation, show access revoked and require explicit owner reauthorization for server access. Do not erase entries, photos or shell. |
| Reconnect | Recompute local state without auto-transfer, Save or re-login. An explicit foreground update action checks server authorization; a cached local flag never bypasses it. Expired sessions require new pairing; revoked grants require a new owner grant. |
| Update receives 401/403, server/store error, TLS failure, timeout, partial assets, login HTML or no network | Reject the candidate update; keep the last complete compatible shell/database and pending work. Distinguish denied access from unavailable network without claiming unknown revocation status. Offer later explicit retry after authorization/connectivity is restored; no forced reload/reset. |
| Shell evicted or origin changed | No offline reinstall is promised; return to trusted home provisioning, authenticate again and explicitly restore a verified private bundle. A bundle never restores server access. |

Cookie delivery for initial/installed contexts, manifest/icon downloads and browser
worker-update requests must be measured on the named iPhone. They must satisfy
both authenticated retrieval and nonblocking cached startup; do not make assets
public to work around a browser limitation. If either requirement cannot be met,
stop the future feasibility slice and seek the smallest revised design. This is
an unrun implementation gate, not a claim of verified platform support.

Treat phone locking, camera handoff, OS termination, PWA closure and connectivity
loss as ordinary interruptions. Resume from committed database state; reopen
connections on foreground/pageshow, recompute comparisons and validate current
outbox/receipt state. Visibility events can prompt flushing but are not relied on
for correctness. A photo still in the native camera or a not-yet-committed edit
can be lost; it must never have been labelled retained.

## 8. Transfer, duplicate prevention and desktop authority

Proposed closed version-1 bundle: format/schema, opaque collection binding,
bundle ID, snapshot reference, and entries containing stable random entry UUID,
revision, normalized final/proposal/absence values, explicit offline-review and
purchase intent, role-bound media inventory, byte lengths and SHA-256 values.
Include only enumerated bounded acquisition fields; validate values through the
existing backend normalizers. The current phone service does not carry all
acquisition fields: retain them in staging and require a separately tested
mapping through the existing guarded save seam. Never report those fields saved
merely because staging succeeded.

Export a frozen committed revision. Editing after transfer creates a proposed
replacement revision, not another purchased entry. Exported duplicates keep the
same entry UUID and digest, including after database restore/new installation.
Do not mint new IDs during import or use timestamps, filenames, identity strings,
photo hashes or device installation IDs as uniqueness keys.

A private bundle contains a manifest and bounded ZIP media inventory. Validate
allowlisted names, per-entry/aggregate counts, compression ratio, uncompressed
sizes, media types and digests before extraction; reject traversal, symlinks,
duplicates, unknown required fields and mixed bindings. No executable paths or
credentials are accepted. A digest is not a signature.
Proposed limits: <=50 entries and <=256 MiB uncompressed per transfer, no nesting;
split larger exports on entry boundaries. Larger single entries require reducing
the retained set explicitly, with originals preserved until owner decision.
Limits require the memory/export device gate before adoption.

Desktop processing:

1. Owner selects target collection and explicitly imports the private bundle.
   Validate the binding and immutable payload; intake/staging writes no collection.
2. Under a dedicated ingress lock, durably associate (collection binding, entry
   UUID) with one accepted revision/digest, staging inventory and service entry/pair
   mapping. Publish the mapping before exposing a saveable inbox entry.
3. An identical replay returns the existing staging state or current proven
   receipt; it never creates another save opportunity. A differing revision/digest
   is a conflict, not a last-write-wins update. An explicit desktop replacement
   before any save intent may supersede the old revision with retained history.
4. The owner reviews current collection duplicates, target changes, acquisition
   details and selected photos, then performs desktop identity verification and
   separate Save using new trusted action-bound approvals. Offline flags,
   imported JSON, receipts and file signatures cannot authorize these actions.
5. Before Save is enabled, durably bind exactly one existing PhoneEntryService
   entry and PhoneIntake pair to the ingress entry. Creation that crashes before
   this association leaves unassociated preparation quarantined and unsaveable.
   Association conflicts block. Do not recreate a service entry after SAVING.
6. Delegate persistence to the existing reviewed-save/media/baseline bridge.
   Existing reservation and actual record/media evidence decide outcome.
   The ingress ledger records correlation and receipts, not a second collection
   transaction protocol. Lock ordering must be specified/tested without holding
   the ingress lock across calls acquiring existing persistence locks.
7. Return a versioned receipt only after actual saved record, canonical pair
   evidence, intake completion and audit finalization agree. Receipt binds
   collection, entry UUID, accepted input revision/digest, final desktop field/media
   digest, existing service/pair/item IDs and outcome. Desktop edits are explicitly
   visible in that receipt and require phone acknowledgement of the result.
8. Import the receipt explicitly on the phone; validate trusted collection binding
   and correlate exact operation, revision/digest and item. Conflicting or unknown
   receipts are quarantined. For file transfer, the owner confirms the expected
   desktop source and displayed identifiers; integrity checks alone do not prove
   origin. A forged JSON file must never trigger collection mutation or deletion.
   Receipt replay is idempotent.

State boundaries:

| Phone/desktop observation | Allowed continuation |
| --- | --- |
| Local draft / Pending sync | Edit locally; explicit frozen export. A purchase is still not in the collection. |
| Exported / desktop staged / awaiting receipt | Keep pending overlay and all photos. Re-import the same payload to query/recover staging. |
| Desktop needs review/media or conflict | Preserve evidence; obtain missing sides or owner disposition. No collection write. |
| SAVING, recovery, disconnected or unknown outcome | Reconcile the same existing service/pair/reservation. No new save or blind replay. |
| Proven SAVED and matching receipt | Mark Saved since snapshot; retain photos until explicit cleanup after verified recovery copy. |
| Proven clean pre-save rejection | Show not saved; explicit desktop reload/review required. Existing service recovery restrictions still apply. |

A missing record, empty collection, timeout, expired session or missing ledger is
not proof a prior Save never happened. If ledger/mapping is lost, block this binding
until owner reconciliation against retained bundle, intake/audit and actual
collection/media evidence; no automatic registry recreation accepting old entries.
Re-import after successful Save must also detect a deleted/edited live item and
report a changed outcome instead of offering a new Save. Same identity under a
different entry UUID is a separate possible duplicate requiring human decision;
the ledger cannot prove physical identity.

Connectivity returning enables a foreground "Transfer pending purchases" action;
it never auto-saves. First milestone uses export/import and receipt return.
Optional paired HTTPS LAN transport later uses these same IDs/staging/receipt
rules, explicit foreground action, fresh authentication and private owner-enabled
listener. No pending credential is cached for a future unattended write.

## 9. Recovery and honest guarantees

After the app has acknowledged a committed local write, ordinary PWA closure,
phone locking and connectivity loss must preserve the entry and normalized photos
on the acceptance device. This is a tested product requirement, subject to the
platform limits below. It does not promise every keystroke or unsaved camera result.

Origin storage is not an independent backup. User clearing website data, removing
the app where data is removed, device loss/reset, browser defects, storage pressure
or a failed OS write may destroy the database and/or shell. Persistent mode reduces
eviction risk; it does not make copies outside the origin. No multi-store design
inside that origin solves full-origin loss.

Provide explicit private "Export recovery bundle" for committed entries/photos,
pending operations, selected snapshot and receipts. Use a user-selected local
Files destination, not an automatically selected cloud provider. A share-sheet
completion does not prove a file exists: reselect/reimport and verify its inventory
before marking a recovery copy verified. Feature-detect file sharing/download;
if no tested path works, mark recovery unavailable and block show-readiness.
Keep export errors, cancellation, low-memory and insufficient-disk outcomes visible.
A same-phone file helps with origin loss, not phone loss. Off-device copy is an
explicit later user action and remains private.

Show "Changes since verified recovery export" and prompt after purchases/before
leaving the show. Proposed policy: verify an initial recovery export and prompt
after each purchased entry; do not pretend a skipped prompt supplies a backup.
Recovery includes only what was exported; later entries/photos may be unrecoverable.

On database corruption, preserve data and offer read-only salvage/export; never
reset automatically. On complete loss with shell present, say "Local data
unavailable/new installation" and offer restore or a deliberately empty workspace.
If all local markers vanished, the app cannot distinguish loss from first install
or report the missing entry count. If shell is also gone, reinstall at home first,
then explicitly restore a verified bundle. Restore preserves entry UUIDs/digests,
merges exact duplicates and quarantines divergent revisions. Failed restore keeps
the previous valid database; no localStorage tombstone is offered as proof.

Delete/forget is explicit, per entry and clearly distinguishes sighting, unsynced
purchase, saved local copy, export and desktop record. Never cascade phone deletion
into collection deletion or revoke a potentially executed desktop Save. Retain
outcome/ID tombstones for transferred operations, and explain that deleting all
copies removes recovery evidence. No automatic retention expiry for unsynced work.

## 10. Platform evidence and limits

Research checked 2026-10-20; these support design choices, not device acceptance.
- [WebKit storage policy](https://webkit.org/blog/14403/updates-to-storage-policy/):
  quota estimates are not allocation promises; writes can fail, best-effort origins
  may be evicted, and persistent mode uses heuristics including home-screen use.
  Hence feature checks, actual error handling and recovery exports.
- [WebKit ITP home-screen note](https://webkit.org/blog/10218/full-third-party-cookie-blocking-and-more/):
  installed first-party apps have distinct use accounting; do not claim every PWA
  is erased after seven calendar days or promise immunity from data loss.
- [WebKit Safari 17.2](https://webkit.org/blog/14787/webkit-features-in-safari-17-2/):
  installation copies cookies, not other local storage. Prepare and test within
  the installed app.
- [IndexedDB transaction specification](https://www.w3.org/TR/IndexedDB/#transaction-concept):
  completion and durability hints inform the commit UI; strict remains a hint.
- [Service Workers specification](https://www.w3.org/TR/service-workers/):
  secure contexts and worker lifecycle govern offline provisioning/startup.
- [Web Share specification](https://www.w3.org/TR/web-share/):
  file sharing depends on capability and user action; it is not a file-verification
  or backup receipt.
- [WebKit Background Sync issue](https://bugs.webkit.org/show_bug.cgi?id=182565)
  and [Safari 27 beta overview](https://webkit.org/blog/17967/news-from-wwdc26-webkit-in-safari-27-beta/):
  do not make background execution or a new routing API a milestone dependency.
  Actual iOS 27.0.1 behavior remains a manual capability/interruptions gate.

Authentication correction reference: [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
informs proposed opaque sessions, cookie controls and server expiry/revocation.
It does not verify this application's implementation. Service-worker lifecycle
requirements above remain subject to the cited specification and real-device gates.

## 11. Acceptance matrix for future implementation

All fixtures synthetic, temporary and privacy-classified. No test_coins images,
live records, private exports, uncertain provenance or external providers.

| ID | Scenario and required evidence | Level |
| --- | --- | --- |
| A01 | Install/prepare in home-screen app; PC off, airplane mode, force-close/cold-launch, deep link; shell, snapshot, queue and restore controls usable. | iPhone |
| A02 | First install/incomplete cache, lost worker or cleared shell cannot falsely show ready; reinstall/restore instructions truthful. | Browser + iPhone |
| A03 | Capture 1, 2 and 8 photos; assign/swap roles; locked phone/camera cancellation/termination around each write. Acknowledged photos/fields reopen with identical normalized hashes. | Browser + iPhone |
| A04 | Interrupt before photo commit, after commit before UI update, and during replacement/purchase transaction; old or new complete revision, never partial Pending sync. | Browser fault injection + iPhone |
| A05 | Supported JPEG/PNG, actual iPhone camera output, HEIC, same bytes, malformed/animated/oversize images, EXIF/GPS, pixel limits. Explicit errors; no silently lost original/role. | Browser + backend + iPhone |
| A06 | Quota denial, persist denied/unavailable, low disk/memory, DB abort/closed connection; previous state preserved, no success copy, no unsynced eviction. | Browser fault injection + iPhone |
| A07 | Lock/close, foreground, phone restart, disconnected 24-hour and 8-day retention observations; compare entries and photo hashes. Record OS/browser, duration and limits. | iPhone |
| A08 | Complete/stale/partial/empty/missing/future-clock snapshots; target coverage and freshness visible; no unsupported absence claim. | Pure/browser |
| A09 | Saved identity, genuine explicit target, outside target, variant/unknown distinguishing field, unknown grade, free-text target, observed year hole without target. Five result semantics and explanations hold. | Pure/browser |
| A10 | Purchase suppresses subsequent exact target gap; partial pending gives collision warning; cancelled draft does not suppress; fresh snapshot + receipt overlay does not double-count. | Pure/browser |
| A11 | Upgrade/schema incompatibility, partial service-worker install and blocked DB upgrade; old complete app/data retained, no forced reload/reset or Save replay. | Browser + iPhone |
| A12 | Concurrent windows edit/purchase/export; revision conflict blocks stale update and stable UUID maps to one desktop inbox entry. | Browser + backend |
| A13 | One-side purchase stages but cannot invoke pair Save; extra photos/acquisition fields retained and mapping omissions disclosed. Two sides yield the existing bridge. | Integration |
| A14 | Export cancel/low memory/quota; reselect/reimport local Files recovery copy and verify hashes; full-origin loss and restore preserve UUIDs and pending state. | Browser + iPhone |
| A15 | Corrupt/truncated/unsupported/malicious ZIP, duplicate entries, traversal, symlink, expansion bombs, mixed binding, changed hashes; no partial activation/staging or paths trusted. | Backend/browser |
| A16 | Identical bundle imported twice, by two workers, after desktop restart and after phone restore; one mapping/pair/item, no second save capability. | Integration/fault injection |
| A17 | Same UUID changed payload/revision; different UUID same identity; desktop edits/target changes/wrong collection. Conflicts require explicit review, no automatic merge/quantity increment. | Integration |
| A18 | Kill before/after staging-map publication, service-pair association and reservation. Unassociated work unsaveable; existing association reused; no duplicate save path. | Backend fault injection |
| A19 | Kill/fail before collection publication, after publication before completion, and after completion before audit/receipt; read actual record/media, recover same pair, never resave. | Existing seam + integration |
| A20 | Lost/duplicate/late/wrong-binding/forged/mismatched receipt; remain pending until explicit correlation; no automatic media deletion. Saved receipt replay with later edited/deleted record surfaces conflict. | Integration/browser |
| A21 | Stale live collection, failed load, changed staged media or vanished ledger. Existing baseline/recovery rejection survives; no auto-reload/resave. | Existing seam + integration |
| A22 | Manual end-to-end: prepare, PC off at show, compare, buy, compare next coin, export, desktop review/Verify/Save, receipt, reopen and refresh snapshot. Demonstrate no collection write before desktop Save. | Owner/iPhone |
| A23 | Logs/bundles/cache contain only allowed fields; no credential/session/EXIF/path leaks, application-initiated network dependency at show, cloud/telemetry dependency or unintended collection write. Observe any browser-initiated worker checks separately under A27. | Integration + network observation |
| A24 | New/unapproved device: request shell, manifest, worker, icons, metadata and direct/versioned assets using GET, HEAD and conditional requests. Missing/expired session, revoked grant and unavailable session store disclose no protected bytes/304; no ready claim. Valid pairing requires desktop approval, one-use secret, five-minute expiry and attempt throttling. | Server security + iPhone |
| A25 | Verify cookie flags and host scope, session rotation, 30-minute idle/eight-hour absolute expiry, logout, device/all-device revocation and fresh owner reauthorization. Replayed pairing codes, fixed tokens, forged device IDs and cross-origin authentication attempts fail. Provisioning session cannot call collection, inbox, administration, Verify or Save. | Server security/integration |
| A26 | Inspect synthetic bundle/source/URLs/history/logs, browser stores, HTTP/Cache Storage and purchase/snapshot/receipt/recovery exports: no pairing/session/CSRF credentials outside allowed transient auth/cookie handling. Auth/error/redirect/API responses never cached; allowlisted shell has no cookies or private payload. Restoring/exporting bundles never restores server access. | Security + browser inspection |
| A27 | With a previously authorized complete installation, expire/delete cookie and revoke grant at server; force-close/cold-start and deep-link with PC off, no network, and reachable server returning 401/403 or hanging auth. Local shell, capture, comparison, queue and recovery remain usable without waiting for live auth. Record network traces: application startup makes no auth request; incidental browser worker checks cannot block startup or bypass server denial. | Browser fault injection + iPhone |
| A28 | First-install no network/denied enrollment stays not-ready; pair in installed context and prove authenticated manifest/icon/worker retrieval. Reconnect with valid, expired and revoked sessions; only explicit foreground update obtains assets after server authorization. No auto-transfer/Save, wipe or automatic re-enrollment. | Integration + iPhone |
| A29 | Interrupt update with 401/403, login HTML, corrupted/missing asset, timeout, server/store/TLS error or offline network. Old compatible shell/DB and exact pending IDs/photo hashes survive; candidate never activates, private resources never served from cache, explicit later retry succeeds only after authorization. | Server/browser fault injection + iPhone |

These are planned gates, not tests executed here. iPhone 13/iOS 27.0.1 manual
acceptance is mandatory; desktop WebKit emulation cannot certify phone lifecycle,
camera, storage eviction or Files behavior.

## 12. Incremental implementation plan for later authorization

Each slice needs a new bounded contract and explicit implementation authorization,
focused checks, affected integration, applicable static/CI gates and independent
review. This list grants no code, migration or publication authority.

1. **Contract fixtures and comparison:** closed snapshot/entry/receipt schemas,
   explicit target projection and pure matcher, synthetic A08-A10/A15/A17 tests.
   Exit: five results explained without inferred gaps or probabilities.
2. **Device feasibility and private provisioning:** minimal future PWA probe on
   the named iPhone; trusted local HTTPS, installed-app storage, photo commit,
   offline cold launch and verified local Files export/restore; proposed pairing,
   denial/revocation, credential/cache boundaries and session-independent startup.
   A01-A07/A14/A24-A29.
   Exit: owner accepts measured limits and provisioning procedure; stop/revise
   if offline-first or recovery cannot meet requirements. No real collection.
3. **Durable offline entry:** IndexedDB transactions, media retention, revision/
   purchase/outbox state and explicit local recovery with synthetic snapshots.
   A03-A06/A10/A12/A14; no desktop save adapter.
4. **Offline shell and snapshot UX:** versioned worker/cache update policy,
   readiness screen, freshness/coverage and comparison, resume/salvage paths.
   A01/A02/A07-A11; iPhone cold-start gate before show use.
5. **Private transfer and desktop inbox:** bounded bundles, stable binding,
   durable ingress uniqueness/association and receipt schema; no collection
   writes. A13-A18/A20/A23. Specify ingress publication/locking order and prove
   crash barriers before enabling the next slice.
6. **Desktop review/Save and outcome recovery:** desktop-only approvals, pair
   requirements, acquisition mapping, existing persistence/reconcile, receipt
   export/import and since-snapshot overlay. A13/A16-A23. No alternate writer.
7. **Owner acceptance and operating guide:** complete A22 on the named device,
   interruption/recovery demonstrations and current-head repository gates.
   Record limitations, verify a private recovery copy and obtain owner acceptance.

Foreground HTTPS LAN transfer is a separate optional follow-up; it is not needed
to complete this milestone. Recognition/AI, native app, public hosting, remote PC
access, collection editing/deleting from phone, schema migrations, background sync
and Phase 2 work remain deferred.

## 13. Owner decisions and validation record

Requested before implementation:
1. Approve the proposed additive amendment and file-mediated first milestone;
   confirm that a queued one-photo purchase may wait for a second side before
   desktop Save, and extra photos remain in the private queue/archive.
2. Approve the proposed local pairing/session requirements in sections 3.1-3.2
   and private HTTPS feasibility investigation, including the limit that revocation
   denies server access but cannot revoke cached offline use. This does not yet
   authorize certificate installation or exposure. Stable origin/trust/authentication
   and A24-A29 must pass slice 2 before production work.
3. Accept the explicit platform-loss limits and proposed private recovery workflow.
   Confirm proposed photo/export limits and recovery prompting after purchases.

No product decisions in section 1 are reopened. Failure of these technical gates
requires the smallest revised proposal, not an implicit native/cloud substitution.

### Bounded authentication correction: evidence status

The owner requested correction of an independent review FAIL concerning private
HTTPS provisioning authentication. The earlier design_verifier PASS concerned the
pre-correction candidate and does not close that finding. It is superseded for this
revision; no implemented security capability or device acceptance is asserted.

Correction base: GitHub main and isolated branch HEAD verified at
`e350644539c062ff1700fa58875ff26b02a89258` before editing; the two authorized
Markdown files were untracked. Primary checkout and its four tracked modifications
are protected. Only these two documents may be committed after a fresh independent
review of their exact revised bytes passes without blocking findings. Any fresh
FAIL or unresolved design decision stops publication. The correction authorization
permits that documentation-only PR; it grants no adoption, merge or implementation.

Focused documentation checks and the fresh independent verdict must be reported
with the reviewed SHA-256 snapshot and eventual commit/PR in the task/PR evidence;
this text does not predeclare their results. Behavior/device tests, full regression,
security execution and deployment are unrun. A24-A29 are future implementation
acceptance checks, not verified capabilities. Owner adoption and the implementation
feasibility/device gates above remain pending.
