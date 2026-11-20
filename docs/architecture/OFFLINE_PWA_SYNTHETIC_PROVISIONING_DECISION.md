# Synthetic-only offline PWA provisioning decision

Date: 2026-10-25. Implementation baseline:
`9ac8f7fa988241937be8843865baf21d16ed569a`.
Authority: the owner's bounded synthetic-only implementation authorization.
Status: synthetic acceptance profile; runtime qualification **UNVERIFIED**.

## Decision and boundary

Supply a stock-Caddy HTTPS/Basic Authentication profile solely for disposable
synthetic shell-provisioning experiments. This is the narrowly authorized
synthetic exception to the future production pairing/session requirements in
[design sections 3.1–3.2](OFFLINE_COIN_SHOW_DESIGN.md#31-proposed-provisioning-authentication-and-authorization).
It does not amend or satisfy those production requirements, establish readiness
for real collecting data, or authorize deployment. Existing desktop persistence,
Save, collection/transfer behavior and the application shell are unchanged.
SEC-003 remains **OPEN**, outside this package. Physical-iPhone acceptance remains
**UNVERIFIED**; no device test is authorized by this change.

Only these files belong to the package:

- `offline_pwa/README.md`
- `docs/architecture/OFFLINE_PWA_SYNTHETIC_PROVISIONING_DECISION.md`
- `tools/offline_pwa_acceptance/Caddyfile.example`
- `tests/test_offline_pwa_provisioning.py`

The last file deliberately houses both the acceptance preflight/preparation CLI
and its tests so that no production host, custom middleware or extra tool file
is introduced. The README gives the commands and operator prerequisites.

## Trust and request processing

Caddy's ordered `route` establishes built-in Basic Authentication before method
checks, literal original-target matching, any rewrite or file handler. GET/HEAD
alone can retrieve assets. Missing/wrong credentials must disclose no asset bytes
or usable conditional 304. No public shell, favicon or metadata exception exists.
HTTP parser/TLS failures may reject requests before route execution without
serving assets. Authentication at the route layer cannot run before that parser.

The exact original `RequestURI` is matched by `{http.request.orig_uri}` rather
than a normalized path. Each accepted target selects a static filename and MIME
type. The start-URL alias alone selects `index.html`; all other targets must
name one of the ten enumerated assets beneath `/offline-coin-show/`. The profile
does not normalize suspicious spellings into accepted ones. Directory browsing,
extension fallback, public redirects, custom authentication, reverse proxies,
filesystem-derived routes, arbitrary root selection and client-controlled
rewrites are absent. The default authenticated response is a denial.

All routed responses carry no-store, nosniff, no-referrer, restrictive CSP and
Permissions-Policy headers; assets set no cookies and contain no account/session
information. Explicit MIME types cover the manifest, worker, scripts, styles,
HTML, icons and metadata. There are no state-changing methods or CORS grants.
Basic Authentication supplies neither short-lived sessions nor per-device
revocation. Stopping the listener blocks new retrieval, but cannot recall cached
shell/data or browser-cached credentials. A disposable browser profile and
synthetic password are mandatory operating limits.

Reference semantics: Caddy's [route ordering](https://caddyserver.com/docs/caddyfile/directives/route),
[built-in authentication](https://caddyserver.com/docs/caddyfile/directives/basic_auth),
and [original-URI implementation](https://github.com/caddyserver/caddy/blob/v2.10.2/modules/caddyhttp/replacer.go).
These references support the intended configuration; only execution against an
approved local binary can qualify its actual behavior.

## Artifact authentication and filesystem preflight

Trust is anchored to the owner's exact baseline Git commit, not to hashes
invented for this package or to a manifest accompanying an unverified build.
Reconstruction reads the pinned builder and seven enumerated source blobs from
Git with replacement objects disabled, executes only that pinned builder in
isolation and derives expected bytes. Generated icons, worker and `shell.json`
are included in exact byte comparison. There are no private-photo inputs,
network fetches or collection data dependencies. A baseline change requires new
owner authority; absent objects/build evidence deny preparation.

Preflight requires an absolute, unambiguous, local output root. It inspects each
ancestor, the root and every asset with `lstat`; it rejects links, Windows
reparse points, unexpected node types, unavailable device/inode identity,
multiple hard links, extra/missing entries and all directories in the inventory.
It compares opened-file identity with pathname identity and rechecks files,
inventory and ancestor identity after reading. Windows path/handle `ctime`
semantics differ, so cross-API comparison uses stable identity/size/mtime fields;
within one API the complete captured tuple is compared. Every byte must match
the reconstructed baseline, including metadata/worker files.

The verified bytes are copied into a NEW isolated runtime shell root. Caddy
serves that copy, never the candidate or checkout. Config/CA state is outside
the shell directory. The runtime parent must be under exclusive operator control
with restrictive OS permissions. ACL verification is an operator prerequisite,
not a claim made by this portable topology checker. The default Windows user
temporary path can lack sandbox-visible ancestor evidence; it is rejected. Tests
use a safe ignored build location with observable identities. The snapshot is
not a hostile-local-writer sandbox: another process with operator/admin authority
can replace serving files after preparation. Such a location is unauthorized;
do not run if stable exclusive control cannot be established.

Origin/port/bind values are validated before literal config generation. No
environment-variable expansion or arbitrary directives are accepted from those
inputs. Only explicit private HTTPS origins and private/loopback IP binds are
allowed, with canonical matching unprivileged ports. DNS and private certificate
trust remain separately qualified operator responsibilities. Configuration
disables admin, HTTP redirection, config persistence and trust installation;
HTTP/1.1 limits this acceptance profile's protocol surface.

## Evidence and remaining gates

The focused suite exercises baseline reconstruction and byte tampering of each
asset; extra/missing inventory; hard links; Windows junctions at an asset, root
and ancestor; unavailable identity; origin/bind/port rejection; isolated copy
preparation; and structural route/inventory checks. The existing builder test is
included. Structural checks do not execute CEL, adapt Caddyfile syntax or prove
HTTP behavior.

An optional real-Caddy runtime class covers GET/HEAD for all assets and the start
alias, credentials and conditional requests, denied methods, raw malformed and
ambiguous targets, outside/extra-file sentinels, exact types, headers and 304
behavior. It binds only loopback and isolates temporary PKI/configuration. No
binary was found on PATH or checked standard local install locations during
implementation; no download/install or listener run occurred. Those runtime
tests are skipped and all runtime criteria remain **UNVERIFIED**. No system
trust certificate was installed. No CI, phone, retention or production security
acceptance follows from local deterministic tests.

Exactly one independent High-reasoning security review follows implementation
and available checks. A material blocking finding stops this package; no
automatic remediation/re-review campaign is authorized. Commit/publication,
deployment, LAN use, physical-device testing and final merge each remain outside
the current authority. Review verdict and exact executed checks are reported in
the task closure, including any failed or unrun acceptance criteria.
