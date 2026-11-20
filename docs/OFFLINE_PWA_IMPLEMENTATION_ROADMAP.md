# Proposed offline PWA implementation PR sequence

Status: **ROADMAP ONLY; no implementation or publication authorization**.
[Authority](OFFLINE_PWA_SECURITY_PACKAGE_2026-10-21.md),
[security contract](architecture/OFFLINE_PWA_SECURITY_CONTRACT.md),
[threat model](architecture/OFFLINE_PWA_THREAT_MODEL.md),
[acceptance packet](OFFLINE_PWA_SYNTHETIC_ACCEPTANCE_PACKET.md).

This refines sequencing for the next review cycle. It does not adopt the complete
older offline architecture, open a PR, change CI or advance any phase. Every slice
needs a new six-field contract, exact verified base and explicit action authority.
The identifiers below are proposed review units, not current branches or approved
schemas. Complexity is relative, not a delivery-time promise.

## Common regression, rollback and review rules

For every code slice: focused deterministic tests first, then affected integration,
relevant static checks, independent exact-revision review, and authoritative
current-head Windows/Ubuntu unittest, Ruff syntax, Gitleaks and bounded Pyright.
Root regression command remains `python -m unittest discover -s . -p "test_*.py"`.
Browser suites are additional; emulation/desktop WebKit never replaces the device.
Docs-only slices use whitespace/link/content checks, not full product regression.
No test weakening, protected images, broad artifacts or real records. Browser CI
must retain TESTING.md checkout/artifact/privacy rules, with credentials disabled.

Rollback means a separately authorized forward fix/revert and feature kept disabled,
never destructive Git history or IDB downgrade/reset. Existing primary/frozen
baselines stay untouched. After a durable-format change, old code is safe only if
its reader supports that exact state; otherwise stop writes and preserve state for
compatible recovery. Do not roll back by deleting evidence or retrying an ambiguous
Save. Every enabling/deployment step remains distinct owner authority.

## Separately reviewable slices

| Slice | Minimal scope and dependencies | Complexity / required regression | Rollback strategy | Stop/go gate |
| --- | --- | --- | --- | --- |
| P1 Browser CI | Separate Node/Playwright job using existing locked package and loopback synthetic fixtures. Explicit privacy-safe checkout, no traces/screenshots/profile/artifact upload by default. Pin setup/browser inputs, close listeners, set job timeout; expose failure as visible gate. Independent of host implementation | Medium; existing browser suite/build tests, JS syntax, repository privacy-policy suite and workflow validation; verify runner cleanup and failing-test job failure | Disable/revert only new job under authority; do not weaken existing merge gates or imply devices qualified | GO only after exact workflow/privacy review and reproducible synthetic run. NO-GO on protected-image materialization policy violation, artifact leakage or silently skipped tests; making it blocking is an explicit owner/repository setting decision |
| P2 Authentication/session model | Pure model/store and desktop-control interface, no listener. S4-S6/S7 denial model; O2 adoption, explicit pending/delivery state, fake clock/RNG seams, persistent grant/counter integrity, fail-closed restart. No collection/service adapter | High; T01-T04/T12, concurrency/reservation/approval/delivery races, secret schema/log checks, focused static checks then common gates | Keep disabled/unreferenced; invalidate pending contexts/sessions on version mismatch; retain hashed grant evidence, no automatic permissive recreation | GO only with atomic one-use and revocation proof, exact expiry equality, no raw bearer persistence and independent review. NO-GO for unadopted O2 or unresolved storage/time semantics |
| P3 Private HTTPS shell host | Dedicated stopped-by-default process, S1-S3/S6-S8, exact inventory route table and immutable build, no collection roots/adapters. Depends P2; O1/O2 selected. Certificate *procedure* documented; actual issuance, trust, binding/listening still separately authorized | High; T05-T10/T12/T17 raw requests versus worker/cache; parser limits/framing, bind/SNI/Host and credential-isolation tests. Browser update regression plus existing demo separation/Save tests and common gates | Stop listener, revoke/invalidate online sessions, restore prior valid immutable build/TLS config only; retain cached shell/IDB. Invalid/expired TLS denies, no HTTP fallback | GO for later provisioning consideration only after complete synthetic security evidence and least-privilege review. NO-GO on any unauthorized body/304, arbitrary path/collection access, host ambiguity, weak trust or parser disagreement |
| P4 Device-provisioning test packet | Exact device/context/origin, trust fingerprint/renewal/removal steps, install/pair/observe/cleanup and rollback checklist. Depends qualified P2/P3 and O1-O3; document timing budget before execution. Preparation can start sooner. No physical execution in code/docs PR | Medium documentation; link/authority checks and independent review. Later separately authorized execution: T07/T11/T16/T17, authenticated manifest/icon/worker retrieval, cookie/session-independent cold launch; 24h/8d observations as scheduled evidence | Stop qualification and listener; revoke sessions; remove only owner-approved dedicated test app/trust/data after evidence. Do not reset phone/Safari or expose assets to bypass behavior | GO only for synthetic execution on named approved device after explicit operation authority. NO-GO if authenticated installed retrieval and offline startup cannot coexist; seek smallest design revision |
| P5 Verified recovery export | First approve a closed recovery schema, confidentiality/custody policy O4 and export semantics O5. Export a consistent committed snapshot with UUID/revision/media inventory; explicit local destination and reselect/verify before marking verified. No desktop Save/import or presumed cloud destination. Browser implementation can proceed without host against synthetic local fixtures | High; T09/T15/T18 export cancellation/low memory/partial file/reselection/hash/secret exclusions; format limits and credential prohibition, common gates. Device Files path later needs P4-qualified environment | Disable export action on failure; prior verified file and local DB retained; never mark share callback as verification. Schema changes preserve earlier files/readers | GO after owner-reviewed exact schema/confidentiality and verified reselected copy. NO-GO for implicit plaintext/cloud policy, credentials/private undeclared fields or fabricated backup success |
| P6 Atomic restore and quarantine | Depends approved P5 format and O4/O5; stage/validate entirely before atomic activation, exact duplicate idempotence, divergent revisions quarantined read-only, preserve originals and unknown schemas; compatible read-only salvage scope separately specified. No new collection writer | Very high; T13/T14/T17/T18 with boundary injection, malformed archive/path/size/count/expansion, restart/reopen and exact before/after snapshots; common gates | Stop writes on uncertainty, retain previous active dataset and quarantined/staged evidence; compatible recovery only, no downgrade/reset/automatic merge | GO only with executable activation/quarantine state machine and complete crash-boundary evidence. NO-GO on partial activation, re-created server grants or destructive salvage |
| P7 Storage and lifecycle hardening | Depends P1 and version compatibility with P5/P6; expand missing-store/corruption/concurrency, uncertain readback, navigation/foreground/dirty edit handling, supported media and quota/lifecycle failure modes. Design retention observations with P4; no promise every keystroke retained | High; T10-T16, existing migration/browser/build tests and common gates. Physical full-process/reboot/pressure/24h/8d acceptance separately authorized and recorded | Retain compatible old shell plus complete active data, disable unsafe writes, explicit uncertainty/recovery. No automatic photo eviction or quota compression | GO when measured behavior, write acknowledgment and recovery remain truthful; O5 accepts actual unsaved/loss limits. NO-GO on acknowledged data loss in required ordinary lifecycle or incompatibility without recovery |
| P8 Retention/deletion | Depends P5/P6 recovery and P7; O3-O5 approved. Explicit entry/local-copy/export/phone distinction, no automatic expiry for unsynced work; transferred operations retain reviewed minimal outcome/ID tombstones. Define tombstone fields/retention and future P10 interface before code | High; deletion interruption/concurrent use, pending/awaiting outcome, export coverage, restore-after-delete and re-import dedup tests; T16-T19 refinements plus common gates | Disable destructive actions; never silently reconstruct deleted user content or cascade to desktop. Partial/uncertain deletion keeps recovery evidence and reports state | GO only with explicit ownership/deletion acceptance and no second Save path after restore/re-import. NO-GO for unreviewed retention period, removal of unresolved outcome evidence or claimed secure erasure of external copies |
| P9 Offline coin-show workflows | O6 adopts only needed workflow clauses; depends P5-P8 and accepted snapshot/target/entry/outbox schemas. Start pure projection/matcher fixtures earlier; then local capture/review/purchase/pending overlay and freshness/coverage. File-mediated flow only, recognition optional/deferred | Very high; design A08-A12/A14-A17/A20/A23 per-case specs before code, T19 refinement; unknown identity, stale/partial coverage, pending collisions, receipt overlay and privacy tests; common gates | Disable purchase/comparison surfaces retaining entries/photos/operations; never downgrade evidence or infer collection completion. Keep prior compatible readers | GO only for synthetic workflow acceptance; real operational qualification also needs P10 and owner loss/device acceptance. NO-GO for invented gaps/confidence/provenance or purchase implying collection Save |
| P10 Desktop staging and separate Save reconciliation | Depends approved P5/P6/P8/P9 formats/interfaces and O6; first sub-PR inbox/ingress registry (no writes), second existing service/pair association plus separate desktop Verify/Save, third original-operation reconciliation and receipts. Specify locking, unique binding, prospective publication/recovery boundaries before enabling Save. No direct JSON/media writer | Very high; A13/A16-A23, T17-T19 refined, existing PhoneEntryService/PhoneIntake/guarded persistence suites; duplicate/concurrent import, vanished ledger, stale baseline, one-side/extra photos, crash before/after collection/audit/receipt. Common gates, frozen recovery invariants unchanged | Stop new staging/Save; preserve ingress/pair/reservation/receipts and all media. Reconcile exact original operation against actual disk evidence, never resave/rebuild missing mapping | GO only after separately approved ingress durability contract and exact-byte recovery evidence. NO-GO for browser booleans as approval, one-photo pair fabrication, ambiguous repeated Save, changed baseline or missing association |

## Dependency and parallel-work boundaries

P1 and pure P2 model work are independent after their own authorization. P3 design
and P4 document drafting can proceed alongside them; host integration waits for P2,
and device execution waits for P3 security qualification plus explicit permission.
P5 format/privacy design and P9 pure matcher/snapshot fixtures can be reviewed in
parallel with authentication/host work, using synthetic temporary data only.
Neither requires a listener, physical phone or live collection.

P6 cannot finalize without P5's immutable format; P7 compatible-reader/upgrade
work must coordinate with both. P8 needs recovery and a jointly agreed P10
tombstone/operation interface before deletion semantics freeze. P9 implementation
needs the storage/recovery/retention contracts. P10 staging-schema design may run
in parallel after the bundle/outcome interfaces freeze; Save wiring waits for its
own persistence and human-approval gates. Shared schema/store/worker changes must
use sequential integration and independent review, not uncoordinated parallel edits.

The numeric order expresses review slices, not a requirement to finish a physical
retention duration before designing an unrelated pure module. Parallel *planning*
does not grant code, device or publication authority.

## Cumulative stop/go decisions

| Boundary | Evidence needed / decision |
| --- | --- |
| Documentation -> implementation | Owner adopts exact necessary clauses/O choices and authorizes one bounded slice. Package review alone is not this decision |
| Model -> enabled private host | Qualified P2/P3, exact-SHA CI/review, chosen origin/trust/ACL plan and explicit listener/certificate authority. No production config action bundled with implementation |
| Host -> synthetic phone execution | P4 packet approved, actual device/version/context and operations named; synthetic-only. Trust/device cleanup reviewed first |
| Foundation -> usable recovery | P5/P6 independent verified private copy, atomic restore/quarantine and device Files evidence. Current C5 remains FAIL until observed capability exists |
| Synthetic -> real data/show use | All applicable existing A01-A29 and PR #429 gates resolved with evidence, complete workflow P9/P10, measured lifecycle/retention, recovery/custody/privacy acceptance and explicit owner operational authority. No automatic promotion |
| Any PR -> merge | Separately authorized publication, current passing blocking CI for exact head, independent review and explicit human authorization for that PR merge |

Next recommended owner decision: review this proposed package and authorize only
P1 Browser CI preparation/implementation on a fresh verified base, with synthetic
fixtures and existing privacy contracts, followed by local validation/independent
review. Push/PR, settings changes, host/auth implementation, certificates, device
execution and product readiness would remain outside that next slice unless
separately and explicitly authorized.
