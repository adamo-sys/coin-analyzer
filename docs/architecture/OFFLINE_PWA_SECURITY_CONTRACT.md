# Proposed private HTTPS shell provisioning security contract

Status: **PROPOSED**, not adopted or implemented. Authority and evidence:
[package](../OFFLINE_PWA_SECURITY_PACKAGE_2026-10-21.md).
Companions: [threat model](OFFLINE_PWA_THREAT_MODEL.md),
[test packet](../OFFLINE_PWA_SYNTHETIC_ACCEPTANCE_PACKET.md),
[roadmap](../OFFLINE_PWA_IMPLEMENTATION_ROADMAP.md).

## Requirement status

**R (retained requirement):** local-first behavior, protected-data isolation,
collector authority, separate desktop Verify/Save, no automatic collection mutation,
frozen persistence, synthetic-only foundation use and existing acceptance holds.
These already govern; they are not new choices granted by this document.

**P (proposed decision):** every numbered S clause below, including security timings
requested for this package. A future owner adoption must identify its exact scope;
document review alone does not implement or approve these clauses.
**O (owner choice):** explicit decisions in the final table. An unresolved choice
blocks only the slices that depend on it, never silently selects a weaker default.

The recommended option is a dedicated private HTTPS origin serving only an
immutable shell plus minimal authentication. File-mediated recovery/transfer remains
separate. Extending the existing HTTP demo would mix cookie, Save and transport
authority; public hosting/tunnels would enlarge exposure. Neither is selected.

## S1. Process, network and origin boundary (P; preserves R)

Start stopped. Only a trusted local desktop owner action may enable provisioning.
Bind an explicitly selected private interface/address and fixed port; reject
wildcard IPv4/IPv6, public interfaces, automatic interface fallback and router
forwarding. Firewall permits only the owner-selected private subnet; any IPv6 or
multiple-interface support needs an explicit tested policy. Private LAN is untrusted.
No discovery, public DNS routing, proxy tunnel, external identity service or CDN.

Pin one configured `https://hostname:port` origin, separate from the demo/desktop
application. Validate TLS SNI and HTTP authority/Host against it; do not infer it
from incoming Host, forwarding headers or DNS results. Reject mismatches before
enrollment or asset processing. Disable proxy-header trust, redirects to aliases,
directory listings, filesystem-root serving and development/debug endpoints.
Host rebinding does not bypass TLS/Host checks. Network binding is a prerequisite,
not authentication. Origin/port/path changes require a reviewed migration packet.

Use a dedicated host data directory under desktop-user permissions for server
grants/sessions; never collection roots. The provisioner must not load collection,
inbox, intake or Save adapters. No generic file or upload route. If deployed under
the desktop OS user, filesystem separation is defense in depth, not containment
against that user/host compromise; O1 must address least-privilege execution.

## S2. Trusted TLS lifecycle (P)

O1 must select a maintained TLS server/library and private trust method; no custom
TLS implementation. A dedicated local CA with narrowly controlled issuance is a
candidate, not a certificate installation authorization. Before any phone setup,
owner verifies CA fingerprint out of band, leaf SAN/hostname/chain and actual
device trust; never bypass browser warnings or offer HTTP downgrade. TLS 1.2/1.3
only is proposed; private keys remain on the host under restricted ACLs, never
in source/assets/backups/phone export. Root signing key should be kept off the
listener host where practical. Installing a CA adds trust beyond this application;
owner accepts that cost or selects an alternative trusted private method.

Proposed operational packet: 90-day leaf validity, renewal review 30 days before
expiry, same origin and SAN, validated chain/key match before atomic configuration
activation, and retained last valid configuration. Failed renewal never activates
invalid material; expired/not-yet-valid/mismatched/untrusted TLS denies new retrieval.
Clock anomalies require owner correction, not validation bypass. Key compromise
requires stop, trusted reissuance/rotation and device trust review. Root replacement
is a separately approved trust operation; do not promise mobile revocation checking
or remote cached-code removal. No certificate is provisioned by writing this plan.

## S3. Closed routing and service-worker boundary (P)

Protected asset paths under `/offline-coin-show/` are exactly `index.html`, `app.js`,
`storage.js`, `media.js`, `style.css`, `manifest.webmanifest`, `icon-192.png`,
`icon-512.png`, `sw.js` and `shell.json`. Root navigation and validated entry UUID
deep links map only to index bytes after authorization on the server. Built
inventory specifies MIME/digest/version; it is integrity metadata, not a signature.
No arbitrary version/path lookup. Deploy only one explicitly approved immutable
build directory, reject symlinks/reparse escapes and verify complete inventory
before enablement. Unknown paths, dot segments, encoded separators, query-bearing
asset requests and alternate encodings do not expand the allowlist.

Worker URL, manifest ID/start URL and scope remain `/offline-coin-show/`; no
`Service-Worker-Allowed` broadening. Worker never intercepts authentication,
collection, inbox, Verify, Save, unknown paths, cross-origin or non-GET requests as
an offline proxy. Enrollment lives outside that scope at proposed `/enroll` and
`/auth/*`; it is a tiny self-contained page with no protected app dependencies.
Exact route spellings are proposed interfaces for later review, not new endpoints.

## S4. Pairing protocol and one-use credentials (P)

Desktop-only Enable pairing creates a CSPRNG secret of at least 128 bits, pending
server record and expiry `issued_at + 300 seconds`. Display secret only on that
trusted desktop screen; owner enters it into same-origin HTTPS enrollment POST
body. No URL, fragment, QR link, clipboard automation or printed/exported secret.
Pairing never approves itself: pending attempt has a random identifier shown on
both screens, and owner must approve that exact attempt from the trusted desktop.
No HTTP approval/revocation administration route exists on the provisioner.

Recommended state machine: `issued -> pending-attempt -> consumed` with terminal
`expired/rejected/revoked`. First valid submission atomically reserves the secret
to one attempt and transient pre-auth context, rejecting every subsequent submit.
Approval records only that exact pending attempt as approved, before expiry;
it creates no session. The same pre-auth context completes a CSRF-protected
`POST /auth/complete`; one store transaction rechecks approval/context/expiry,
consumes the attempt and creates the session. A context-bound status POST may
report pending/approved/denied only, never secrets or grant inventory. All these
responses are network-only/no-store; status cannot extend any deadline.
Completion must occur strictly before expiry; approval or completion at 300
seconds fails. Rejection/cancellation/timeout burns
the code; a new attempt requires a new desktop-issued code. Competing submissions
or completions can yield at most one session. Lost response after committed
completion cannot redeliver/recreate a token: fresh desktop pairing is required,
and the stranded session is revoked or expires normally. Secret remains display-only in desktop
memory until attempt/expiry; clear transient input and DOM on all terminal paths.

Proposed bounded limits: 4 KiB auth body, 16 KiB aggregate request headers, 2 KiB
request target; five failed submissions per issued code/pre-auth context, ten
public enrollment/auth requests per source address per five minutes, fifty globally
per five minutes (GET form, status and completion included, not just submissions);
at most five pending attempts and sixteen concurrent connections, 10-second
header/body deadline. Apply source/global budgets before any pre-auth allocation
or expensive work; they are independent of failed-code counters. Next request over
the applicable limit returns generic 429 without creating state. Counts use a
fake-clock-testable rolling window; limits apply before expensive work. Persist
security counters for code lifetime, fail closed on failure; restart invalidates
all pending codes/contexts and sessions. Shared-address denial of service remains
possible; desktop may explicitly cancel/reissue, never auto-unlock a consumed code.
O2 approves these proposed limits and enrollment accessibility trade-offs.

## S5. Session state and expiry (P)

Successful approved pairing creates a device grant and new CSPRNG opaque token
of at least 128 bits; ignore/reject client-selected tokens, grant IDs and approval
booleans. Retain only domain-separated cryptographic hashes of pairing/session
secrets plus minimal grant/session metadata (opaque IDs, issuance, last activity,
absolute deadline, status, bounded attempt counters), under host ACLs. Compare
tokens without timing-dependent equality. No JWT, refresh token, JS device secret
or durable bearer on the phone. Raw session token exists only during generation
and delivery; CSRF/pre-auth secrets follow the same no-log/no-export policy.

Authoritative server time, not browser time, enforces `now - last_activity < 1800s`
and `now - created_at < 28800s`; equality expires. Only a fully authenticated and
authorized protected request refreshes idle activity; denied requests, public
status, CSRF failures, client timestamps and validation failures do not. Absolute
deadline never slides. Serialized store transaction checks current grant/revocation
and expiry, advances activity, then authorizes the response. Wall-clock rollback
or unprovable store/time state invalidates sessions; restart invalidates them and
requires pairing again. Stable device grants may persist but grant ID is no login.

Logout invalidates the current server session before expiring its cookie. Device
revocation invalidates all that grant's sessions; revoke-all invalidates every
grant/session and pending attempt. Future requests check current state each time;
no cached positive authorization. Revocation does not promise cancellation of
bytes already authorized/in flight. Missing/corrupt/lost state denies access;
never rebuild grants from a bundle, browser flag, receipt or device label.

## S6. Cookies, CSRF and input handling (P)

Only the browser cookie jar holds the client session:
`__Host-coin-show-session; Secure; HttpOnly; SameSite=Strict; Path=/`, no Domain.
Use a session cookie (no persistent refresh); server deadlines remain authoritative.
Rotate on authentication and reject old token replay. Cookie set/clear occurs only
on authentication responses, never shell responses. Reject ambiguous duplicate
session cookies. No CORS access or credentials, permissive OPTIONS or JSONP.

Every state-changing browser authentication request is POST-only, exact configured
HTTPS Origin required (missing/null/multiple/foreign fails), plus an unpredictable
server-bound synchronizer CSRF token carried in body/header, never URL. Enrollment
GET creates a CSPRNG pre-auth context/cookie and transient form token, each at
least 128 bits, subject to S4 request budgets before allocation. Pre-auth context
expires at `created_at + 300 seconds`, with equality expired and no renewal from
GET, status or POST traffic. At most twenty live pre-auth contexts exist globally;
reuse an existing valid context without extending its deadline, reject cap+1 with
429 and no allocation, and reclaim expired contexts deterministically. Never evict
another active context/attempt to make room. Context-store/time failure gives 503
denial, not an untracked context. Its Secure/HttpOnly/Strict host-only cookie and
form token grant no asset access. Pairing issuance expiry and this context expiry
are independent: completion requires both still valid. Session logout uses its own
session-bound token. Tokens must not cross pre-auth/session contexts or survive
logout; token mismatch grants nothing. Fetch Metadata checks are additional
defense, never a substitute for Origin/token validation. SameSite alone is
insufficient. POST redirects, credential-bearing URLs and method override fail.

A maintained HTTP stack rejects malformed framing, conflicting Content-Length /
Transfer-Encoding, invalid Host/Origin, duplicate security headers, oversized/
slow requests and unsupported methods/content types with bounded generic errors.
No reflection of inputs, traces, filenames or secrets. Rate-limiter/store errors
deny. Resource caps, parser policy and connection limits need synthetic evidence
before a listener can be enabled; unexpected parser behavior is a stop condition.

## S7. Authorization and caches (P)

Every protected network GET/HEAD, conditional, direct asset, manifest/icon/worker
and update metadata request authenticates before file access or validator logic.
Missing/expired session: 401; identified revoked grant: 403; unavailable auth/time/
store: 503 denial. Authenticated unknown path: 404; unsupported method: 405;
all reveal no protected bytes. Unauthorized HEAD has no body; denied GET has only
a fixed generic error. Never issue a usable 304, protected ETag, Last-Modified,
asset length or redirect-to-login response before authorization. Proposed host
ignores conditionals after auth and emits full 200 for valid GET / empty-body 200
for HEAD, simplifying the no-304 rule. Range is not supported.

Every response uses `Cache-Control: no-store`; no reverse-proxy/CDN/HTTP cache may
reuse an authorized response. Set `X-Content-Type-Options: nosniff`, no-referrer
and restrictive CSP; enrollment additionally disallows framing, external form
targets and external script/style. Shell assets contain no cookie, credential,
user/session metadata or collection payload. A future header profile must retain
the existing shell's script/style/connect/worker restrictions.

Deliberate Cache Storage exception: only the complete credential-free shell
allowlist fetched with current server authorization. `sw.js` is browser-managed
worker code, not a dynamic API fallback; `shell.json` is optional inventory, not
an auth response. App worker validates 200, no redirect/opaque response, exact
MIME, version, byte limits and digest before publishing the complete candidate.
Auth/status/error/API/POST responses never enter it. HTTP no-store is not a claim
that explicit programmatic Cache Storage is disabled. Denied updates keep the old
compatible complete shell; no forced activation/reload or automatic data deletion.
Digest checks do not defend against a compromised trusted build/host replacing
both worker and inventory. No package signing trust anchor is claimed here.

## S8. Offline authority and data privacy (P; preserves R)

A complete previously authorized shell starts locally without online session,
DNS, status polling or auth timeout, including expired/deleted cookies, revoked
grants, PC off or hanging server. No online session is required for local access.
Incidental browser worker checks must deny unauthorized retrieval without blocking
startup. No first offline installation or offline reconstruction of an evicted
shell is promised. Tab and installed-context credentials/storage are measured
independently; never make assets public to bypass installation limitations.

Pairing/session/CSRF secrets never enter Git, URLs/history/referrers, access/error
logs, telemetry, shell, IDB, local/sessionStorage, Cache Storage or any recovery,
purchase, snapshot or receipt export. Only transient enrollment memory and the
cookie jar are allowed on the phone. Suppress request bodies/cookies/auth headers
in diagnostics; minimal event type/outcome and opaque non-secret correlation only.
No photo/metadata payload is accepted by this host. Synthetic media tests inspect
normalized bytes, not only MIME/filenames; visible pixels may still reveal secrets.

Physical access to an unlocked phone or compromised host/browser can expose or
alter cached data. Use device OS lock and a dedicated owner context. Server
revocation is not local encryption, user switching, remote wipe or offline lockout.
Origin loss/eviction is possible; persistence permission and transaction completion
are not backups. Recovery file is private evidence; same-phone copy cannot cover
phone loss. Replacement device needs fresh provisioning/pairing plus separately
verified recovery import, which never restores server authority. No collection,
inbox, Verify or Save capability is ever granted by a provisioning session.

## Owner decisions before dependent implementation

| ID | Required explicit choice / proposed default | Blocks |
| --- | --- | --- |
| O1 | Exact private interface/subnet, stable hostname/port, TLS stack, trust method, key custody, certificate renewal owner and least-privilege host execution | Host/provisioning slices; no actual values or certificates selected here |
| O2 | Adopt S4-S6 protocol/timings/cookie/CSRF/hash model, caps and restart invalidation; approve desktop-only attempt matching/revocation UX | Authentication and host slices |
| O3 | Accept offline cached access after revocation, unlocked-device exposure, dedicated-user/device policy and no remote wipe | Device packet execution and later real-data decisions |
| O4 | Recovery-file confidentiality policy: reviewed encryption/key recovery versus explicit plaintext risk acceptance; local destination, off-device custody and deletion | Recovery export/restore design and device recovery tests; no silent plaintext default |
| O5 | Accept measured lifecycle/eviction/unsaved-edit limits, retention observations, deletion/tombstone policy and export reminders | Storage/retention/product qualification |
| O6 | Adopt only needed additive workflow clauses, closed bundle/receipt schemas and ingress durability contract while preserving existing Save | Workflow/desktop slices; full older proposal remains unadopted |

Security rationale checked 2026-10-21: proposed opaque sessions/cookie/deadline
controls draw on [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html);
Origin and synchronizer tokens on [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
Offline lifecycle follows the [Service Workers draft](https://www.w3.org/TR/service-workers/);
storage risk is supported by [WebKit storage policy](https://webkit.org/blog/14403/updates-to-storage-policy/).
These sources inform proposals, not evidence that this app or the named phone
meets them. No inferred vulnerability is classified as confirmed by this contract.
