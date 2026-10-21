# Offline PWA deterministic synthetic acceptance packet

Status: **SPECIFICATIONS ONLY; every T execution UNVERIFIED / NOT RUN here**.
No device, host listener, certificate, product test or fault injection is executed
by preparing this file. [Authority/baseline](OFFLINE_PWA_SECURITY_PACKAGE_2026-10-21.md),
[S requirements/O choices](architecture/OFFLINE_PWA_SECURITY_CONTRACT.md),
[threats](architecture/OFFLINE_PWA_THREAT_MODEL.md).

## Execution contract, fixtures and evidence

Future execution requires its own exact base/build, bounded authorization,
approved dependent O decisions and disposal scope. Browser automation uses an
ephemeral loopback synthetic origin only; it cannot qualify the production host.
TLS integration uses a separate disposable synthetic trust store under separately
authorized tooling. Never disable certificate validation. Device procedures T16
and device parts of T11/T14-T18 remain blocked until private provisioning/security
gates pass and owner separately authorizes that exact device/operation.

Fixture classes (all **SYNTHETIC / PUBLIC-SAFE**, generated without protected inputs):

| Fixture | Deterministic setup |
| --- | --- |
| F1 identity/clock | Independent fake server clock starts at epoch `1800000000`; advance exact milliseconds, no sleeps. CSPRNG dependency replaced only in test process by an indexed deterministic byte sequence; production randomness must remain cryptographic. Fixed entry IDs `00000000-0000-4000-8000-000000000001` and `...0002`, revision 1; wrong/replay tokens enumerated in fixture manifest. Do not record real credentials |
| F2 server state | Empty temporary grant/session/counter store, trusted desktop test-control seam unavailable over HTTP, two independent clients, configured synthetic origin. Fault seam throws at read/check/update/commit; concurrent operations synchronized by barriers, not scheduling luck |
| F3 builds | Build A from exact authorized source; build B changes only a public display string in a temporary source copy. Retain exact asset MIME/length/SHA-256/version inventories, including worker. Explicit corrupt/partial/redirect variants derived from B. Do not edit checkout or import extra files |
| F4 storage | Ten v1 entries with fixed valid UUIDs/revisions, two deterministic 4x4 RGBA PNGs with known pixel arrays, explicit roles/references and hashes computed when fixture is generated. Store a sorted full before/after inventory including Blob bytes, version/stores/meta. v2 fixture is same records plus documented state/meta |
| F5 media/privacy | Deterministic synthetic JPEG and PNG with visible grid and fake markers `SYNTHETIC_GPS`, `SYNTHETIC_NOTE`, fake EXIF/XMP/IPTC/GPS tags, PNG text/eXIf chunks, filename `synthetic-private-name.jpg`. Record exact input/normalized hash manifests per tested engine; no cross-engine encoder-byte assumption |
| F6 collection/files | Temporary synthetic desktop collection/media sentinel and empty staging root, hashed before/after; future closed recovery bundles containing only F4/F5 with fixed IDs/revisions/binding. Malformed variants include duplicate IDs, wrong hashes/lengths, future version, divergent revision and truncated payload; archive forms additionally traversal/link/expansion cases |

Every run records T subcase, tester, authorization reference, UTC timestamps,
source/build SHA/inventory, harness versions, actual environment/context, fixture
generator/revision/hash inventory, exact injections/clock events, expected and
observed result, sanitized evidence path, disposition and cleanup receipt.
Credential bytes/cookies/CSRF are redacted in retained evidence. Record flags,
token equality/hash relations and store schema instead. With deterministic fake
tokens, assertions may inspect values in isolated memory; exported reports keep
only booleans/correlations. No raw browser profile, full HAR/body/cookie dump,
screenshots containing codes or arbitrary artifact directory upload.

**PASS:** all named assertions for that environment/subcase observed with retained
evidence and no relevant contradiction. **FAIL:** observed assertion violation,
including a demonstrably absent required capability. **UNVERIFIED:** not executed,
missing prerequisite, unsupported/missing environment or insufficient evidence.
An absent authentication implementation is FAIL for capability B2, but an unrun
proposed expiry test is UNVERIFIED, not an invented observed failure. Aggregate
PASS requires every required subcase; any FAIL controls, otherwise missing subcases
keep aggregate UNVERIFIED. Documentation review never promotes a T/device gate.

Default cleanup **C0:** close owned browser/test clients and fixture listeners,
remove only exact temporary directories/profiles/DBs created by that run, remove
disposable trust within its authorized store, restore test-only hooks, and record
disposal. Do not delete a failed-state fixture before preserving a sanitized
synthetic inventory needed for diagnosis. No primary/private/other-origin cleanup.
For device tests **CD:** owner-approved removal only of identified synthetic app
data/files and dedicated trust artifacts, after evidence retained; no reset of
phone, personal Safari storage or user trust store. Each case below requires C0
or CD plus its listed specifics.

## T01 Pairing time, approval and consumption (S4-S6; B2 / A24-A25)

- Setup: F1/F2, fresh issued secret per independent subcase; matching pre-auth
  context; desktop approval seam and two-client barrier.
- Steps: submit and approve before expiry, then explicitly `POST /auth/complete`
  at 299999 ms; independent fresh subcases complete at 300000 and 300001 ms.
  Also submit or approve at those boundaries, and submit before/approve after
  expiry. Attempt early/unapproved, wrong-context and wrong-CSRF completion;
  reject/cancel; submit twice simultaneously, approve twice and synchronize two
  completions after one valid approval. Try approval over HTTP and wrong attempt
  ID. Drop the response after committed completion, retry completion, then request
  fresh owner pairing. Test independently expired pre-auth context with otherwise
  unexpired pairing code, and the reverse; neither extends the other lifetime.
- Expected: only approved matching unexpired attempt yields one fresh session.
  Reservation binds one context; second submit cannot reserve/consume again.
  Late/rejected/cancelled/consumed attempts yield no grant/session. Approval alone
  sets no cookie/session; valid completion creates exactly one committed grant/
  session and at most one cookie-bearing response under the concurrency barrier.
  At exactly five minutes either expiry controls. Lost delivery after commit burns
  attempt; retry cannot redeliver that token or create another session. The stranded
  session is revoked or expires; fresh owner pairing creates a distinct session.
- Evidence: ordered fake-time transition/store assertions and cookie-issued count,
  not raw secrets. PASS iff every transition/counter assertion holds; FAIL on any
  duplicate/unapproved/late grant; UNVERIFIED without implemented seam. Cleanup C0.

## T02 Replay, revocation and session fixation (S4-S6; B2/B4 / A25/A28)

- Setup: F1/F2, approved grants A/B with independent sessions; saved previous token.
- Steps: replay consumed code, use arbitrary grant ID/boolean/fixed token, replay
  prior rotated session, logout A, revoke A, revoke-all, restart server; race a
  revocation with an authorization transaction at explicit ordering barriers.
- Expected: no code/fixed/old-token authority; logout/revoke denies next protected
  request; B survives A-only revocation, not revoke-all; restart invalidates all
  sessions/pending contexts. Requests authorized before revocation may complete;
  those ordered after it cannot. Offline copies are not erased. Stolen *current*
  bearer may work within its lifetime: record the limitation, not false replay immunity.
- Evidence: transition order, grant/session hashed-state and response matrix;
  PASS iff those boundaries hold; FAIL on unauthorized/new grant or post-revocation
  authorization; UNVERIFIED without actual model. Cleanup C0.

## T03 Idle/absolute expiry and clock anomalies (S5; B2 / A25)

- Setup: independent F1/F2 sessions per row; server time seam only.
- Steps: idle request at 1799999 ms passes, one at 1800000/1800001 fails in fresh
  rows. Keep another session active every 60 seconds through 28799999 ms; request
  at 28800000/28800001 fails. Send denied/public/status/CSRF-failed traffic before
  idle limit, alter browser time, roll server wall time backwards, restart process.
- Expected: successful protected authorization refreshes idle only; absolute
  never renews. Denials/public traffic and browser time do not prolong it. Time
  uncertainty/restart invalidates sessions; store failure cannot refresh idle.
- Evidence: exact fake clock and stored times, no wall-clock waiting. PASS iff
  every equality/refresh/anomaly row matches; FAIL on late access or extension;
  UNVERIFIED without fake-clock coverage. Cleanup C0.

## T04 Cookie, pre-auth CSRF and bounded attempts (S4/S6; B2/B5 / A24-A26)

- Setup: F1/F2 clients and a separate hostile synthetic origin; approved O2 caps.
- Steps: inspect cookie flags/host-only scope/JS invisibility; send missing/null/
  foreign/multiple Origin, absent/wrong/cross-context token, GET mutation, method
  override and preflight. Cross-client claim of approved pending attempt must fail.
  Send five invalid code submissions then sixth; ten source submissions then
  eleventh; fifty global then fifty-first, distinct contexts where needed. Advance
  rolling clock to 300000 ms with precise earlier timestamps; test pending cap.
  Independently allocate twenty fresh-client pre-auth contexts across sufficient
  test-transport source addresses to avoid confounding source limits; request
  twenty-first. Repeated enrollment GET/status/completion traffic must consume
  source/global budgets before allocation. At context age 299999 ms retain it;
  at 300000/300001 ms reject its use and reclaim expired capacity. Reuse an existing
  context without extending deadline; inject context-store/read/allocation errors.
- Expected: exact-origin POST plus correct context-bound CSRF required; no CORS;
  no session fixation or cross-context delivery. Limits reject request over cap,
  with no state issuance; expired window counts drop only as specified. Public
  form cannot create protected authority. Cap+1/floods issue no new context/cookie;
  no other active attempt is evicted to make space. Expired contexts reclaim
  deterministically, never silently renew. Counter/context-store failure denies.
- Evidence: sanitized header/JS-access booleans, per-limit isolated state traces;
  PASS iff all rows hold; FAIL on bypass or wrong flags; UNVERIFIED if a cap is not
  adopted or engine visibility unmeasured. Cleanup C0, including hostile origin.

## T05 GET/HEAD/conditional/direct-path authorization (S1/S3/S7; B2 / A24)

- Setup: F2/F3, raw HTTP client with no worker/HTTP cache and a fresh browser.
- Steps: Cartesian matrix of all ten asset paths plus root/deep-link, GET/HEAD,
  no session/valid/idle-expired/absolute-expired/revoked/store-error, with no
  conditionals, `If-None-Match`, `If-Modified-Since`, combined and Range headers.
  Probe unknown paths, traversal/encoded separators/query assets and symlink escape.
  Probe collection/inbox/Verify/Save routes using valid session.
- Expected: only valid session/exact allowed path returns approved MIME/bytes
  (HEAD empty); authenticated conditional GET returns full 200, never 304 under
  proposed policy. All invalid states deny before asset/validator lookup; generic
  errors only, no protected validators/length. Unknown paths do not map to index.
  Collection/admin capabilities absent, collection fixture unchanged.
- Evidence: complete matrix keyed by path/state/method/header, body hash or
  zero-byte count and validator absence. PASS iff no row leaks/bypasses; FAIL on
  any leak or unbounded mapping; UNVERIFIED for missing cells. Cleanup C0.

## T06 Unauthorized 304 and warmed-cache behavior (S7/S8; B3/B4 / A24/A27)

- Setup: F2/F3 with authorized cached shell A; separate raw client and HTTP cache
  test fixture with worker explicitly bypassed, then a controlled app window.
- Steps: prime authorized GET/HEAD/validators, invalidate session, request direct
  assets conditionally and via back/reload; attempt worker update and `/auth/*`/
  fake API fetch with cold and warm caches. Inspect server origin response apart
  from service-worker-supplied response.
- Expected: network never returns protected bytes or usable 304 after denial;
  HTTP cache/no-store cannot bypass server. Previously authorized local shell may
  return 200 offline by design; that is not an authentication failure. Auth/API
  gets no cached fallback. Denied update cannot replace A or reset F4 data.
- Evidence: source-of-response/server traces plus Cache Storage key/MIME inventories;
  PASS iff these separate boundaries hold; FAIL on unauthorized network reuse/API
  fallback; UNVERIFIED if response source is unknown. Cleanup C0.

## T07 TLS, authority, binding and renewal (S1/S2; B1 / A24/A29)

- Setup: F2/F3 disposable TLS trust and authorized synthetic interface environment;
  never personal certificates. Exact origin tuple recorded; O1 selected first.
- Steps: valid chain/SAN versus unknown root, wrong SAN, expired/not-yet-valid,
  protocol downgrade, wrong SNI/Host/port/forwarded authority; inspect enabled
  interfaces/firewall and attempt outside allowed subnet. Stage valid renewal,
  wrong key/chain, expired renewal and interrupted configuration activation.
- Expected: valid trusted private origin only; no warning bypass/HTTP fallback,
  wildcard/public/IPv6 exposure outside approved policy. Renewal keeps origin and
  uses whole valid old or new configuration, never partially activated secrets;
  expired service denies while cached local shell/data survive.
- Evidence: sanitized chain fingerprints/times/SAN, bind/firewall and handshake
  results, no private keys. PASS only for observed topology/trust store; FAIL on
  exposed/downgraded/invalid accepted transport; UNVERIFIED on unmeasured phone
  trust/network. Cleanup C0; device portion requires separate CD authority.

## T08 Malformed HTTP and resource bounds (S3/S4/S6; B2/B5 / A24-A26)

- Setup: future actual HTTP stack in isolated F2 integration harness, F6 sentinel;
  proposed sixteen-connection limit is adopted with O1/O2 before this subcase.
- Steps: body/header/target sizes at cap and cap+1, slow headers/body at deadline,
  unsupported methods/content types, duplicate Host/Origin/session cookies,
  conflicting framing/CL-TE and encoded traversal; saturate pending/connections.
  Use fresh-client enrollment GET floods, context cap+1, precise context expiry/
  reclamation and context-store faults independently of POST/pending-attempt caps.
- Expected: deterministic bounded 4xx/429/connection close as appropriate, no
  grant/state/asset read or reflected private values; over-budget requests allocate
  no pre-auth state and never displace a live attempt; parsing disagreement stops
  the slice. No debug/stack trace; sentinel untouched. Valid bounded control works.
- Evidence: parser outcome and bounded time/resource metrics, sanitized request
  case IDs; PASS iff all specified caps/invariants hold; FAIL on bypass/hang;
  UNVERIFIED if stack/cap undecided. Cleanup C0; no shared LAN fuzzing.

## T09 Credential and private-payload isolation (S3/S6-S8; B3/B5 / A23/A26)

- Setup: F2-F6 sentinel markers with test-only secrets, approved event schema.
- Steps: install/pair/fail/logout/update/export/restore where implemented; inspect
  enumerated built assets, URLs/history, app stores/cache, sanitized host logs and
  explicit export schemas. Scan local diagnostic hooks *before* redaction to assert
  bodies/cookies/tokens are never recorded; retain boolean findings only.
- Expected: no pairing/session/CSRF material outside transient form/memory/cookie
  handling; no Set-Cookie/private metadata in shell; no photos/notes/paths in build
  or provisioner. Auth/error/redirect responses absent from Cache Storage. Bundle
  restore grants no online access. Inspect destinations; no telemetry/cloud upload.
- Evidence: allowlisted field/key inventories and sentinel-absence assertions;
  PASS only for inspected surfaces/stages; FAIL on prohibited occurrence;
  UNVERIFIED for absent future export/restore stages. Cleanup C0; never upload raw logs.

## T10 MIME/hash/TLS/timeout and interrupted shell updates (S7; B3 / A29)

- Setup: F3 A complete, F4 committed, B candidate and fresh-install profile.
- Steps: parameterize each B asset with missing/401/403/503, redirect/login HTML,
  opaque/wrong MIME, correct MIME wrong hash, truncation, >3 MiB, TLS failure,
  eight-second fetch deadline, disconnect before/after each cache write and before
  completeness publication. Repeat first-install cases; no wall sleep for timeout
  branch, separately measure actual bounded integration timeout when authorized.
- Expected: no failed candidate activates; A and exact F4 inventory survive.
  First install has no complete worker/ready claim. Later clean B install waits
  for all app windows to close, then complete compatible startup. No forced reload
  while dirty/writing; partial cache is never represented as complete.
- Evidence: worker state, per-asset injections, cache inventory/completeness and
  before/after IDB hashes. PASS iff all boundary cases hold; FAIL on partial publish,
  forced activation or data loss; UNVERIFIED for unexercised interruption. Cleanup C0.

## T11 Offline cold startup, host unavailable and session invalid (S8; B4 / A27)

- Setup: A provisioned, F4 committed, record worker control; fresh windows and
  independent no-shell negative control.
- Steps: remove/expire cookie/revoke grant, close all app pages, cold-launch root
  and valid deep link with host stopped, offline network, reachable 401/403, and
  hanging host. Reconnect while form dirty; record incidental browser updates.
- Expected: local shell/F4 usable without auth/DNS/status wait, no automatic
  transfer/Save/re-enrollment/erase. Harness local-start deadline proposed 2 seconds
  after navigation dispatch; physical device timing recorded under T16, not inferred
  from desktop speed. Auth/API paths never resolve to shell. No-shell control is
  setup-required; no claim of offline first installation.
- Evidence: timings, application-versus-browser request initiator trace, control
  worker and F4 equality. PASS only within tested environment/deadline; FAIL on
  startup blocked by online auth or authority expansion; UNVERIFIED for device
  portion. Cleanup C0 or separately authorized CD.

## T12 Server storage failure (S4/S5/S7; B2/B4 / A24-A25/A29)

- Setup: F1/F2 approved session and pending attempt; A/F4 on independent client.
- Steps: inject store missing/corrupt/unreadable, read/write/counter/commit failure
  at reservation, approval, delivery, authorization/activity, logout/revocation;
  restart after failure. Explicit barriers exercise races with expiry/revocation.
- Expected: no protected bytes, 304 or new session when state cannot be proved;
  generic 503 denial. Failed revocation/logout is reported as unconfirmed, never
  falsely acknowledged; fail-closed store health prevents subsequent online use
  until explicit recovery. Recovery never reconstructs old sessions. Existing
  offline A/F4 persists; no permissive fallback to memory/client IDs.
- Evidence: fault/transaction trace, post-restart state, response/body/validator
  assertions; PASS iff every injection fails closed; FAIL on grant/leak/false
  revocation acknowledgment; UNVERIFIED for missing fault seams. Cleanup C0.

## T13 IndexedDB migration interruption and reopen (B/D; A04/A11)

- Setup: F4 v1 exact full inventory; use documented five-second open deadline seam.
- Steps: abort before validation/during async hashing/after first write/before meta
  publication; blocked open, page close, deadline delivered after native commit.
  Independently inject wrong-owner/orphan/missing/duplicate reference, size/hash,
  invalid revision/state, missing store and future version. Reopen without implicit
  version upgrade to inspect; then explicit clean retry where valid.
- Expected: abort leaves exact v1 version/stores/records/bytes, never partial v2;
  native-committed deadline yields complete valid v2. Clean retry preserves IDs,
  photos and adds only draft state/meta. Invalid/unknown state blocks writes and
  preserves evidence, no reset/downgrade. Page close is not OS-process evidence.
- Evidence: full sorted inventories/byte comparisons, transaction events and
  version; PASS iff every named row holds; FAIL on partial schema/data change;
  UNVERIFIED for unrun rows/physical kill. Cleanup C0.

## T14 Quota, write abort and uncertain acknowledgment (A4-A6/C1/D4-D5)

- Setup: F4 v2, two windows at same expected revision, controlled IDB fault seams.
- Steps: deny/unavailable persist/estimate; exhaust estimated headroom; throw quota
  on each write boundary; abort/close/versionchange; race two edits; fail readback
  after commit. Separately authorized process termination before/after commit is
  device extension, not simulated by page close.
- Expected: one revision wins concurrent race; failures before commit leave exact
  prior records/media; no eviction/false retained message. Post-commit readback
  failure is outcome-uncertain, blocks blind retry, reopening inspects same UUID
  and finds exactly old or complete new state, never automatic duplicate.
- Evidence: full inventory and ack/transaction ordering; PASS for all browser
  injections observed, FAIL on partial write/false ack; physical power-loss remains
  UNVERIFIED absent device evidence. Cleanup C0/CD as separately authorized.

## T15 Synthetic metadata removal and image limits (A3/A6/B5 / A05/A23)

- Setup: F5; independently parse original/normalized container metadata and decoded
  pixel dimensions, not just byte substring search. F4 prior state retained.
- Steps: normalize JPEG/PNG, orientation sample, malformed/truncated/animated PNG,
  unsupported HEIC/HEIF synthetic bytes, 16 MiB and cap+1, 30 MP/8000-edge boundaries;
  spoof filename/MIME. Enumerate retained object keys and outbound requests.
- Expected: supported still media re-encodes to PNG without inbound EXIF/XMP/IPTC/
  GPS/text/filename/original bytes; declared dimensions/roles and actual bytes
  agree. Unsupported/oversize failures preserve prior F4, no upload or silent
  resizing. Visible synthetic marker pixels may remain: no anonymity claim.
- Evidence: parser results, pixel/dimension checks, per-engine normalized hashes,
  store/network inventory. PASS iff asserted metadata absent and errors atomic;
  FAIL on retained metadata/unsupported success; actual camera behavior UNVERIFIED
  until separately authorized. Cleanup C0 or CD for device extension.

## T16 Tab versus installed app, restart and retention (A1-A7/C2-C4/D5)

- Setup: **future physical test only**, named owner target iPhone 13 / owner-stated
  iOS 27.0.1 / Safari; record actual versions, dedicated synthetic origin/profile,
  O1-O3 accepted and authenticated provisioner already qualified. Do not infer
  installed cookies/IDB from a Safari tab. Inventory both contexts independently.
- Steps: authorize every manifest/icon/worker request in tab and installed context;
  if context lacks session, pair there. Commit F4, close/lock/camera handoff/terminate
  app/restart phone, launch offline with PC off and cookie expired/revoked. Compare
  at baseline, 24 elapsed hours and 8 elapsed days. Test unretained edit loss without
  claiming it was committed; separately clear only synthetic origin/remove app if
  explicitly authorized. Record actual eviction only if observed; deliberate clear
  is not proof of eviction behavior.
- Expected: committed IDs/revisions/bytes survive ordinary lifecycle on tested
  device; no auth dependency. Empty/lost origin says unavailable/new installation,
  unknown missing count, not successful recovery. No installed-asset public bypass.
  If authenticated installed retrieval and offline startup cannot both work, stop
  and seek minimal architecture revision. No readiness label from partial tests.
- Evidence: context-by-context authenticated request and storage inventory, elapsed
  duration/version, lifecycle action/timing, before/after hashes. PASS only for
  completed subcases/durations; FAIL on demonstrated loss/false claim/unsafe bypass;
  incomplete duration/context remains UNVERIFIED. Cleanup CD; no physical execution here.

## T17 Lost-device, replacement and desktop isolation (B6/C3/D6 / A25-A28)

- Setup: two synthetic client profiles as lost/replacement plus F6; physical
  extension needs separate authority. No actual lost phone/private data involved.
- Steps: revoke lost grant; launch its cached shell offline; request new assets;
  copy F6 recovery bundle to replacement after independently provisioning it;
  request collection/inbox/Verify/Save/admin with provisioning session, device IDs,
  restored flags and fabricated receipts. Compare collection/media before/after.
- Expected: lost offline data remains readable to unlocked holder; new server
  retrieval denied. Replacement has no inherited session/grant, requires fresh
  pairing, and restores only verified included evidence after future restore exists.
  No collection read/write or Save authority; provisioning credentials authorize
  shell retrieval only. Origin change never silently accesses old IDB.
- Evidence: denied route matrix, store/cookie separation and unchanged sentinel;
  PASS only for implemented/tested boundaries; FAIL on inherited auth/collection
  access or false wipe promise; future restore/device portions UNVERIFIED. Cleanup C0/CD.

## T18 Verified recovery, restore/quarantine and confidentiality (C5/D3/D6 / A14-A15)

- Setup: future reviewed F6 format and O4/O5 decisions; no format invented by this
  packet. Exact committed F4 export, prior verified file and destination inventory.
- Steps: cancel export/share, truncate, low disk/memory, choose/reselect local file
  and verify complete hash inventory; restore into new and populated DB; duplicate,
  divergent/future/corrupt/oversize/traversal/link bundles; interrupt each activation
  boundary, reopen; inspect confidentiality controls/key-loss behavior selected by O4.
- Expected: only reselected verified file earns verified-copy status. Prior valid
  file/DB survives failure; no partial activation, unknown downgrade or silent
  merge; divergence quarantined read-only, exact duplicates idempotent. No tokens,
  original filenames/paths or unsolicited private fields in file. Same-phone copy
  does not claim lost-device recovery; encryption claims require actual evidence.
- Evidence: manifest/byte comparisons, quarantine inventory, cancellation/failure
  trace and no-auth-restoration assertions. PASS only for exact approved format/
  environment; FAIL on absent required recovery capability or corrupted activation;
  unexecuted new format tests remain UNVERIFIED; current C5 stays FAIL. Cleanup C0/CD,
  including only identified synthetic Files copies after evidence disposition.

## T19 Later workflow and separate Save contract gates (A08-A23)

- Setup: separately approved snapshot/targets/purchase/bundle/ingress schemas and
  F6 desktop fixture, existing service/intake approvals. This is a dependency gate,
  not authorization to build or run full workflows now.
- Steps: incomplete/stale snapshots, unknown identity, exact pending purchase,
  one-side/extra photos, repeated/conflicting import, lost ingress ledger, stale
  collection and ambiguous Save/audit/receipt; use original design A08-A23 as the
  per-case specification to refine in its slice before implementation.
- Expected: no invented gaps/provenance/confidence; no transfer/import/reconnect
  collection mutation; two separate desktop approvals, complete pair and actual
  persistence evidence required. Ambiguous outcome reconciles same operation,
  never offers another Save. Quarantined recovery cannot approve a Save.
- Evidence: reviewed per-case plan, exact staging/pair/reservation/collection/media
  inventories and existing persistence assertions. PASS requires those executable
  per-case specs and observations; FAIL on bypass; currently UNVERIFIED and blocks
  full show qualification. Cleanup C0; any private inputs remain prohibited.

## Register continuity and exit

This packet refines security A24-A29 and PR #429 B1-B6, plus lifecycle/storage/
recovery subsets; it does not replace the older register or waive unlisted gates.
PR #429's C1/D1/D2/D4 bounded browser PASS stays bounded; B2/C5 FAIL stays FAIL.
T01-T19 are fresh unrun specifications, not 19 new passed acceptance results.
T19 requires further bounded workflow specs; it is intentionally not an executable
implementation plan. Full workflow, loss-policy acceptance and current-head CI
remain prerequisites to any later operational decision.
