# Offline coin-show foundation

Phase 1 implements a separate static application shell and local **drafts**.
There is no collection writer, purchase queue, comparison, import, transfer,
reconciliation, recovery bundle format or production provisioning listener.
Use synthetic practice data until the acceptance gates below are completed.

Authority: owner-authorized bounded slice of
[offline design](../docs/architecture/OFFLINE_COIN_SHOW_DESIGN.md) and
[amendment](../docs/architecture/OFFLINE_COIN_SHOW_AMENDMENT_PROPOSAL.md).
Existing desktop Save and filesystem Phase 1 behavior are unchanged.

## Build and private provisioning boundary

From the repository root, using the configured project Python:

```text
python tools/build_offline_pwa.py NEW_OUTPUT_DIRECTORY
```

The builder accepts a new output directory and copies only enumerated shell
assets. It generates icons and a worker with asset MIME types, SHA-256 hashes and
a content-addressed version (including worker code). `shell.json` is build
inventory, not a credential, authorization decision or trust signature.
There is no build-time network requirement or runtime CDN/dependency.

The fixed application path is `/offline-coin-show/`; manifest identity, start URL
and worker scope agree. Do not relocate the path/origin/port as an ordinary update.
Only an owner-approved stable **private trusted HTTPS** origin may provision these
assets on a phone. Do not serve this directory through the existing HTTP demo or
expose it publicly. Loopback HTTP in browser tests is only a synthetic test origin.

This slice deliberately supplies **no production authentication implementation**.
The separate [synthetic-only Caddy profile](#synthetic-only-caddy-provisioning)
below is authorized only for disposable synthetic practice; it does not satisfy
the production pairing/session requirements in this paragraph.
Before enabling provisioning, the private host must implement design sections
3.1–3.2: local one-use pairing plus desktop approval, short-lived host-only secure
HttpOnly sessions, grant revocation, deny-on-store-failure and authorization on
every shell/manifest/worker/icon/metadata request (GET/HEAD/conditional included).
Every response must use `Cache-Control: no-store`; shell responses must contain no
credentials, user/session data or `Set-Cookie`. Auth/API/error/redirect responses
must never enter Cache Storage. Production security and iPhone retrieval remain
unverified. Do not substitute a client flag, URL token or public static server.

The explicit **Prepare / check shell update** action registers/updates the worker.
Installation verifies the entire shell before publication. A denied, redirected,
wrong-type, wrong-hash, missing, timed-out or partial candidate cannot replace the
prior shell. No forced `skipWaiting` or reload occurs. Updates are deferred while
the current form is dirty/writing; an installed update waits for all app windows
to close. Browser-initiated worker checks may still occur.

Previously provisioned navigation to the start page or `/entry/<UUID>` resolves
immediately to the local shell without a live authentication request. Unknown
routes, authentication/API paths, query URLs and non-GET methods are never an
offline proxy. Expiry/revocation denies new server access; it cannot recall local
code/data. Reconnect does not transfer, authenticate or save anything.

## Local persistence and schema

Database `coin-show-local`, version **2**, contains `entries`, `photos` and `meta`.
A draft is `{id, revision, label, state: "draft", photoIds}`. A photo is
`{id, entryId, blob, size, sha256, width, height, role}`. IDs are random UUIDv4;
photo roles are explicit `unassigned`, `obverse`, `reverse`, or `detail`.
`meta` records `{key: "schema", value: 2}`. Version 1 is the fixture/legacy
entry/photo layout with exactly the same required fields except entry `state`;
the transactional v2 upgrade adds `state: "draft"` and `meta`. Existing state
values or invalid revisions/references cannot be silently reinterpreted.
This is a browser database migration, never a collection/filesystem migration.

Photos are byte-sniffed JPEG/PNG, checked for dimensions before decoding, decoded,
and normalized to PNG without resizing. Canvas normalization removes embedded
metadata. HEIC/HEIF, animated PNG, malformed/oversize or undecodable input is
rejected explicitly. Original upload bytes and browser filenames are not retained.
Normalization/hash work happens before opening a short write transaction.

Entry revision, photo references and photo Blobs commit in one transaction with
an expected-revision check across windows. Strict durability is requested where
supported; it is a browser hint, not a filesystem/power-loss guarantee. Success is
acknowledged only after transaction completion and validated committed readback.
Startup and foreground reopen validate references, byte lengths and photo hashes.
Interrupted writes preserve the prior committed revision; no unload/background
task is a commit point. New photos are appended; no automatic deletion is present.

Limits: 200 entries; 8 photos per entry; 16 MiB per input/normalized photo;
30 MP and 8,000 pixels per edge; 128 MiB normalized photo bytes per database.
Quota estimates reserve 32 MiB of advisory headroom for temporary recovery/update
work. Actual transaction/quota failures still control. Persistent-storage status
is displayed and requested only through the explicit button. No denied/unavailable
grant implies a successful write. Shell storage permits current + previous + one
candidate version; prior caches are pruned only after compatible local startup,
retaining a previous shell. No photo or entry is evicted to recover quota.

Blocked/closed/newer/incompatible/corrupt databases stop writes and report recovery
requirements. Failed upgrades abort; no delete/reset/downgrade is implemented.
The v1 upgrade validates the complete entry/photo snapshot, including references,
ownership, limits, byte lengths and hashes, within the exclusive upgrade transaction
before adding draft states and schema metadata. Pending IDB requests keep that
transaction alive during asynchronous hashing. The five-second open deadline aborts
an unfinished upgrade; a deadline delivered after native commit defers to the open
result instead of reporting a cancelled migration that actually committed.
Readback failure after commit is **outcome uncertain**, requiring inspection of
the same draft before retry. Compatible read-only salvage/export tooling and
private verified recovery bundles are deferred; the UI does not claim they exist.
If storage is empty, the UI cannot distinguish first install from complete loss
or know how many records are missing. Origin storage is not a backup.

## Tests and static checks

### Review retained photos offline

After preparing the complete shell, reopen this origin offline and choose
**Review / add photos** on a retained draft. The viewer shows one saved photo,
its retained role and position. Use **Previous photo** and **Next photo** to
inspect the saved order; a draft without photos reports that explicitly.
Choosing a draft or **New draft** still asks before discarding dirty form edits.
Review does not retain edits or change draft IDs, revisions, photo references,
roles, order, Blobs, hashes or the database schema. Temporary display URLs are
released when the photo, draft or view changes. A late read cannot replace a
newer selection. Foreground reopen revalidates local evidence before display.
This browser-tested viewer does not establish physical-iPhone acceptance;
SEC-003 remains OPEN and independent of this slice.

### Unretained edits and leaving the form

Retain remains explicit; form edits are not automatically saved. A changed coin
description (after trimming surrounding whitespace) or selected new photos count
as unretained edits. Reverting the description and clearing selected photos
removes that warning; changing the role without selected photos or reviewing
retained photos does not create an unsaved edit. Acknowledged Retain success
sets the new baseline and clears the photo selection.

Choosing another draft or **New draft** asks before discarding unretained edits.
Cancel preserves the description, selected photos, role and current photo view.
Navigation is blocked during a write. Failed writes keep unretained input;
an uncertain post-commit outcome keeps departure protection and recovery guidance,
including after a failed retry. Reopen and inspect the same draft before retrying;
a warning does not mean that an uncertain write rolled back. Explicitly discarding
the form never deletes retained evidence.

While meaningful edits or an unacknowledged write remain, a `beforeunload` handler
requests the browser's native warning on reload, closure or document departure.
The handler is removed when no longer needed. Browsers control whether the prompt
appears and its wording, and generally require prior user interaction. This cannot
guarantee protection against forced mobile browser termination. No unload-time
persistence is attempted. Foreground reopening still validates retained evidence
without saving or clearing the current form; shell updates remain deferred while
edits or unacknowledged writes require protection. Physical-iPhone acceptance
remains **UNVERIFIED**.

```text
python -m unittest tests.test_offline_pwa_build -v
python -m ruff check tools/build_offline_pwa.py tests/test_offline_pwa_build.py
cd offline_pwa
npm ci --ignore-scripts --no-audit --no-fund
node node_modules/playwright/cli.js install chromium
npm run check
npm test
```

`PWA_PYTHON` selects the project interpreter; `PWA_BROWSER_CHANNEL=msedge` uses an
installed Edge instead of downloaded Chromium. The browser tests build a fresh
artifact in a temporary directory, bind only to `127.0.0.1`, use synthetic photos
and a synthetic request-denial fixture, and close/delete their own temporary
resources. The fixture is **not** production pairing/session security evidence.
Default repository unittest discovers the Python build test. Browser tests require
the separate Node development dependency/browser. The existing Tests workflow now
runs them in its `offline-pwa-browser` job on push, pull request and manual dispatch.
See [CI commands and failure behavior](../TESTING.md#offline-pwa-browser-ci).

Migration regressions compare the database version, store names, complete legacy
records and photo bytes after missing/duplicate references, wrong ownership,
orphaned/corrupt photos, timeout during hashing or after writes, explicit abort,
and page termination. Clean retry, delayed hashing, a deadline after native commit,
and post-commit readback uncertainty are exercised separately.

## Remaining acceptance gates

No screen claims coin-show readiness. Required follow-up includes:

- Private HTTPS trust/origin packet and actual pairing/session/CSRF/throttle/
  logout/revocation/store-failure enforcement, including A24–A29 security tests.
- iPhone 13 / owner-specified iOS/Safari installed-context manifest/icon/worker
  authentication, offline cold start with PC off and expired/deleted/revoked
  session, camera format/normalization and low-memory/quota interruptions.
- Lock/close/restart and 24-hour/8-day entry/photo hash retention observations.
- Verified private Files recovery export/restore, complete-origin-loss behavior,
  selected snapshot/targets and the later authorized product workflows.
- Owner acceptance of storage-loss limits before real data or show use.

Desktop browser automation proves only the exercised foundation behavior; it
does not certify phone lifecycle, production authentication, trust or recovery.

## Synthetic-only Caddy provisioning

This bounded acceptance profile uses Caddy's built-in HTTPS and Basic
Authentication, with a disposable `synthetic` account. Its authority and limits
are recorded in the [synthetic provisioning decision](../docs/architecture/OFFLINE_PWA_SYNTHETIC_PROVISIONING_DECISION.md).
It grants shell retrieval only. Use a fresh browser profile containing only
synthetic drafts/photos. Do not use collection records, private photos or real
credentials. Production pairing, expiry/revocation and physical-iPhone acceptance
remain unimplemented/unverified; SEC-003 remains OPEN.

The example is a **template**, not a runnable configuration. The acceptance
utility in `tests/test_offline_pwa_provisioning.py` prepares a separate, new
runtime directory only after byte authentication and filesystem preflight.
Do not manually replace tokens, point Caddy at a checkout, or serve a candidate
directory directly. No listener starts during preparation. Do not change the
generated configuration or serving files between preparation and shutdown.

Expected bytes come from the owner-authorized Git commit
`9ac8f7fa988241937be8843865baf21d16ed569a`: the utility reads only the pinned builder
and seven enumerated source blobs with Git replacement objects disabled, rebuilds
in a temporary directory, and compares all ten output files byte for byte.
The candidate's `shell.json` supplies no trust. Missing Git objects/build evidence,
an extra directory/file, changed worker/metadata/icon bytes, links/reparse points,
multiple hard links or ambiguous path identity deny preparation. Ordinary working
tree builds with different line endings are intentionally rejected. A different
source revision needs a separately approved baseline change.

Use an explicitly private directory whose ancestors expose filesystem identity.
All relevant paths must remain controlled by the operator for the whole run.
On Windows, verify the runtime parent has an ACL restricted to the operator and
trusted administrators; Python's `0700` creation mode does not establish that ACL.
On POSIX, world-writable non-sticky ancestors are rejected; a shared/untrusted
group-writable parent is not an authorized runtime location. This utility checks
path topology and artifact identity; it does not certify ACLs or protect against
another process acting as the same OS user or an administrator. Stop if exclusive
runtime control cannot be established. Caddy's file root is not an OS sandbox.

Example preparation, from the isolated worktree (PowerShell; paths are examples
for NEW directories inside ignored `build`, never overwrite existing state):

```powershell
python -B tests/test_offline_pwa_provisioning.py --write-baseline C:/Projects/coin-analyzer/build/pwa-synthetic-candidate
# With an already approved local Caddy binary, generate a disposable password hash
# using its interactive prompt; never commit the hash or put the password in a URL.
$env:PWA_SYNTHETIC_PASSWORD_HASH = (caddy hash-password).Trim()
python -B tests/test_offline_pwa_provisioning.py --prepare C:/Projects/coin-analyzer/build/pwa-synthetic-candidate --runtime C:/Projects/coin-analyzer/build/pwa-synthetic-runtime --origin https://localhost:8443 --bind 127.0.0.1 --port 8443
Remove-Item Env:PWA_SYNTHETIC_PASSWORD_HASH
```

Only canonical HTTPS origins with an explicit unprivileged port (1024–65535)
are accepted. Hosts are `localhost`, a name below `home.arpa`, or an IP literal
equal to the bind address. Bind must be canonical loopback, RFC1918 IPv4 or ULA
IPv6; wildcards, public IPs, scoped/link-local addresses, paths, userinfo, queries,
fragments and mismatched ports fail. Private DNS, hostname-to-address mapping,
certificate identity and OS permissions still require owner verification before
any separately authorized non-loopback use. A stable origin/port must not be
changed for an existing installation. This package starts no LAN listener.

Before any separately authorized listener run, validate the generated config
with the exact approved Caddy binary. Use its generated `Caddyfile` only inside
the new private runtime directory. The configuration disables the admin endpoint,
HTTP redirects, config persistence and automatic trust installation, and keeps
its local CA state outside the serving root. Do not install its CA into system
trust as part of these tests. No access logging is configured. Basic credentials
can be retained by the browser; dispose of the synthetic browser profile afterward.

Authentication precedes method checks, target interpretation, rewriting and
conditional file handling within the ordered route. Only GET/HEAD and exact
case-sensitive original request targets for the ten assets are accepted. The
single start-URL alias `/offline-coin-show/` rewrites to `index.html`; there is no
network SPA fallback for `/entry/...`. Queries (even empty `?`), escapes, doubled
slashes, traversal, backslashes, alternate data-stream syntax and other spellings
do not match. All asset branches rewrite to literal filenames under the isolated
root, with explicit MIME types, no-store and security headers. Rejections never
rewrite to assets; no auth/API/enrollment endpoint is added. HTTP syntax rejected
by Caddy/Go before routing may return 400 before authentication or these headers.

Run the bounded evidence checks:

```text
python -B -m unittest tests.test_offline_pwa_provisioning tests.test_offline_pwa_build -v
python -m ruff check tests/test_offline_pwa_provisioning.py
```

The runtime class uses an already available `caddy` on PATH, or the explicitly
approved binary path in `PWA_CADDY`. It never downloads software. When available,
it validates and runs the generated profile on IPv4 loopback with a temporary
CA, a client that trusts only that CA, and raw HTTP targets; it terminates its
process and deletes its configuration/certificates in cleanup. Preparation and
runtime fixtures live in ignored `build`; baseline reconstruction uses temporary
storage. Missing Caddy skips the runtime tests and means **runtime qualification
UNVERIFIED**, including config adaptation, TLS, auth precedence, raw-target
interpretation, HTTP methods, MIME/headers and conditional-response behavior.
Passing structural source checks is not runtime acceptance. Physical-iPhone
acceptance remains **UNVERIFIED** and requires separate authorization.
