# Offline PWA provisioning and local-evidence threat model

Status: **PROPOSED / needs_validation**, 2026-10-21. This is a design threat model,
not a penetration test or a list of confirmed vulnerabilities. See the
[contract](OFFLINE_PWA_SECURITY_CONTRACT.md) for S clauses/O decisions and the
[packet](../OFFLINE_PWA_SYNTHETIC_ACCEPTANCE_PACKET.md) for T evidence IDs.

## Assets, actors and boundaries

Assets: pairing/session/CSRF secrets; server grants and counters; trusted TLS keys;
immutable shell/build; private local drafts/photo bytes; eventual recovery files;
desktop collection and its existing Save authority. Session possession proves
only temporary approved access, not hardware identity or current human identity.

Actors: trusted desktop owner; intended phone user; unauthorized private-LAN client;
origin on a hostile website; thief with code/cookie/file/unlocked phone; malformed
HTTP client; compromised host/build/browser. The LAN and incoming files are untrusted.

| Boundary | Meaning |
| --- | --- |
| B1 LAN -> provisioner | TLS, configured authority, parser and authentication; private address alone is no authorization |
| B2 desktop owner -> grants | Local-only pairing approval/revocation; no HTTP admin authority |
| B3 server -> browser/worker | Only authorized credential-free shell; cache never grants server permission |
| B4 shell -> IndexedDB / lifecycle | Commit/readback, schema/integrity and loss limits; no desktop durability inheritance |
| B5 browser -> private recovery file | Explicit destination, verification and custody; bytes/hashes are not provenance |
| B6 PWA/staging -> desktop collection | No route in this host; later distinct review, Verify, Save and original-operation recovery |

## Structured threat register

All attack hypotheses below are **needs_validation**. A test specification is not
observed exploitation. Known absent authentication/recovery are acceptance gaps
from PR #429, not confirmed reachable vulnerabilities in an enabled provisioner.
Residual-risk decisions must be recorded by the owner, not inferred from PASS.

| ID / threat | Boundary and potential impact | Proposed mitigation | Testable evidence | Residual risk / owner decision |
| --- | --- | --- | --- | --- |
| M01 Unauthorized LAN client, host rebinding or alternate interface | B1; unauthorized shell retrieval or broadened exposure | S1/S3/S7: exact bind/firewall/origin, SNI/Host validation, no wildcard/proxy fallback, auth before every asset | T05-T08: wrong Host/SNI/port/interface, direct assets and network matrix deny; no protected bytes/validators | LAN can deny service; actual network posture unmeasured. O1 selects subnet/IPv6 policy; stop if isolation cannot be proved |
| M02 Stolen or guessed pairing code / racing approval | B1/B2; thief acquires session or burns enrollment | S4: >=128-bit secret, five minutes, one reservation/consumption, match pending attempt on both screens, bounded attempts, desktop-only approval | T01/T02/T04/T08: stolen-code concurrent submits, wrong attempt, boundary times, locks and no HTTP approval | Theft plus mistaken owner approval may succeed; secret alone is insufficient. O2 accepts human matching and denial-of-service trade-off |
| M03 Session theft, fixation and replay | B1/B3; attacker retrieves future shell as approved session | S5/S6: random hashed opaque token, no client choice, cookie security, idle/absolute expiry, logout and grant revocation | T02-T04/T09: old/fixed/duplicate token, logout/revoke, fake-clock deadlines and allowed cookie surface | Current bearer replay before expiry/revocation cannot be distinguished from user; no hardware binding. O2/O3 accept limit; no claim of universal replay prevention |
| M04 CSRF, login CSRF and cross-origin fetch | B1/B2; unintended enrollment/logout or unauthorized browser action | S6: exact Origin, per-context synchronizer CSRF, Strict cookies, no CORS, POST-only mutations; HTTP cannot approve grants | T04/T08: null/foreign/missing Origin, cross-context tokens, form/fetch/OPTIONS; no state transition | Same-origin script compromise bypasses CSRF; browser behavior must be measured. O2 and independent host review required |
| M05 Malformed/slow/oversized requests, traversal and framing ambiguity | B1; parser bypass, arbitrary reads or resource exhaustion | S3/S4/S6: maintained stack, bounded target/headers/body/time/connections, exact normalized allowlist, no symlink roots/debug | T05/T08: traversal/encoding/symlink, duplicate authority/cookie/header, CL/TE conflicts, size/time limits | Resource exhaustion remains possible; reverse proxy adds another parser/trust boundary and requires new review. O1/O2 fix supported topology |
| M06 Service-worker cache poisoning or unauthorized 304 reuse | B3; malicious/login content executes, or online denial is bypassed | S3/S7: no-store HTTP, auth before validators, closed verified shell, no auth/API caching, exact scope, CSP/no-sniff | T05/T06/T09/T10: warm/cold cache, missing/revoked tokens, wrong MIME/hash/redirect, private sentinel absence | Digests protect against corruption, not malicious host/build or same-origin script. O1 trusts host/build; no code-signature claim |
| M07 Interrupted shell update and incompatible schema | B3/B4; no offline startup, partial version or data loss | S7/S8: stage complete candidate, old shell retained, no forced activation/reset, compatibility check before pruning | T10/T11/T13/T14: fail each fetch/publication boundary and reopen same IDs/blob hashes | Physical process/power interruption remains device-specific; compatibility rollback may need forward-compatible reader. O5; stop on unreadable old/new state |
| M08 Host, CA key or trusted build compromise | B1-B3/B6; malicious authorized shell, token theft, possible desktop-data exposure | S1/S2: restricted keys, dedicated immutable asset directory/process, no collection adapters, least privilege, stop/reissue on compromise | T07/T09/T17 plus deployment ACL/import review; synthetic unreadable collection sentinel and build provenance record | Same-user/admin compromise defeats ACL/log assumptions; this contract cannot secure a compromised desktop or revoke offline malicious code. O1 accepts trust root and execution isolation |
| M09 Lost/unlocked/shared phone | B3/B4; local photo/entry disclosure or modification | S8: dedicated owner context, OS lock, explicit disclosure, server revocation; no false wipe/offline-lock guarantee | T16/T17: revoke then launch offline; record what remains visible, replacement pairing and no silent identity switch | Cached data remains accessible to unlocked holder; app encryption/biometrics not selected. O3 explicitly accepts or requires separate design |
| M10 IDB corruption, loss, browser eviction or app removal | B4; partial/missing evidence or false empty/success claim | Transactional commits/readback, fail-closed schema validation, no automatic reset, verified independent recovery; loss count unknown if all markers disappear | T13-T16/T18: exact snapshots, corrupt references, origin clear versus actual eviction labelled separately, restore coverage | Persist permission and same-origin copies do not prevent full loss; actual eviction may remain unobserved. O5 accepts measured limits; recovery absent remains FAIL |
| M11 Recovery-file disclosure or malicious replacement | B5; entry/photo/snapshot disclosure, false restored evidence | Explicit local destination/reselection, closed versioned schema, bounds/digests, no credentials, quarantine divergence; O4 confidentiality decision first | T09/T18: synthetic sensitive markers, cancelled/truncated/tampered files, wrong version, exact inventory; verify no server authority | Hashes are not authenticity; plaintext/file-provider/cloud/backup access may disclose contents. O4 chooses encryption/key custody or explicit risk acceptance; no silent cloud target |
| M12 Unauthorized desktop collection access or Save escalation | B1/B6; read private records or mutate collection | S1/S3/S8: no collection routes/adapters/roots; provisioning token shell-only; later inbox never Save authority | T05/T17/T19: route probes and synthetic collection/media hashes unchanged; verify separate desktop approvals/reconcile-only ambiguity | Compromised desktop user remains outside boundary; future ingress needs its own durability contract. O6; no phone-supplied approval accepted |
| M13 Accidental private photographs, EXIF/GPS, paths or note leakage | B3-B5/B6; metadata or visual disclosure through build/log/export/CI | Enumerated shell only; no photo uploads; normalize synthetic media; strip metadata/filenames; schema excludes private fields by default; diagnostic/artifact allowlists | T09/T15/T18/T19: synthetic EXIF/XMP/GPS/text/filename markers absent from stores/build/logs/exports; destination trace | Re-encoding cannot remove identity/location visible in pixels; sanitized derivative provenance still matters. O4/O6 approve exact future export fields |
| M14 Server-store/time failure or stale positive authorization | B1/B2; fail-open grants, expired session accepted, replay after restart | S4/S5/S7: serialized current-state checks, monotonic/time-anomaly policy, invalidate pending/sessions on restart, 503 denial on failure | T01-T04/T12: injected read/write/commit/counter/time errors, restart and no reconstructed grants | Last in-flight authorized bytes cannot be recalled; unavailable store blocks new online access, not offline local use. O2 accepts fail-closed availability cost |
| M15 Cross-tab/context ownership confusion and stolen pre-auth status | B2-B4; approval delivered to wrong context or data exposed to second user | Bind pending attempt to pre-auth cookie/token; one-use final delivery, no label authentication; independently set up installed context; no multi-user claim | T01/T02/T04/T16: second context cannot claim approved attempt or session, contexts inventoried separately | Browser storage sharing/isolation differs by platform; use dedicated origin/user. O2/O3; unsupported install behavior stops feasibility |

## Review coverage and evidence limits

Inspected source and governing documents are enumerated in the
[package coverage](../OFFLINE_PWA_SECURITY_PACKAGE_2026-10-21.md#evidence-coverage-and-present-readiness).
The foundation has no implemented production TLS/pairing/session service to audit.
No physical device, private data, host ACL deployment, actual recovery file,
certificate installation, HTTP fuzzing or exploit execution was reviewed here.
Future confirmed findings must retain preconditions, reachable behavior, impact
and sanitized reproduction under STANDARDS; otherwise keep needs_validation.

No mitigation reduces R authority boundaries. A proposed safer capability needing
code/configuration or broader data access requires a new task. An owner accepting
a residual risk does not make the threat test PASS or authorize device use.
