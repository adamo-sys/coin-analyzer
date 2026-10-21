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

```text
python -m unittest tests.test_offline_pwa_build -v
python -m ruff check tools/build_offline_pwa.py tests/test_offline_pwa_build.py
cd offline_pwa
npm ci --ignore-scripts --no-audit --no-fund
npx playwright install chromium
npm run check
npm test
```

`PWA_PYTHON` selects the project interpreter; `PWA_BROWSER_CHANNEL=msedge` uses an
installed Edge instead of downloaded Chromium. The browser tests build a fresh
artifact in a temporary directory, bind only to `127.0.0.1`, use synthetic photos
and a synthetic request-denial fixture, and close/delete their own temporary
resources. The fixture is **not** production pairing/session security evidence.
Default repository unittest discovers the Python build test. Browser tests are
explicit and require the separate Node development dependency/browser; existing
CI configuration is unchanged and does not run this browser suite.

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
