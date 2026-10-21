# Offline PWA security architecture and synthetic acceptance package

Date: 2026-10-21. Status: **PROPOSED; documentation preparation only**.
No architecture adoption, product acceptance, implementation, listener, certificate,
physical-device execution or publication authority follows from this package.

## Bounded task contract

GOAL: Prepare the next reviewable security contract, threat model, synthetic
acceptance packet and implementation roadmap from merged foundation and PR #429 evidence.
IN SCOPE: This file, [security contract](architecture/OFFLINE_PWA_SECURITY_CONTRACT.md),
[threat model](architecture/OFFLINE_PWA_THREAT_MODEL.md),
[acceptance packet](OFFLINE_PWA_SYNTHETIC_ACCEPTANCE_PACKET.md), and
[roadmap](OFFLINE_PWA_IMPLEMENTATION_ROADMAP.md); read-only authority checks,
documentation validation, independent review and a local commit after those gates.
OUT OF SCOPE: Product/test/CI/configuration edits, deployment, listeners, trust or
certificate provisioning, device tests, private records/photos, push, PR and merge.
PROTECTED BOUNDARIES: Primary checkout and existing modifications; frozen
persistence/baselines; local-first operation; separate trusted desktop Verify/Save;
private/uncertain images and evidence; Package 0/Phase 1/Phase 2 dispositions.
ACCEPTANCE GATES: Verified main and PR identities, source traceability, whitespace
and local-link checks, exact-snapshot independent PASS or PASS WITH NOTES without
blocking findings, protected-checkout preservation, exact-path local commit.
STOP CONDITIONS: Unresolved base/authority or architecture contradiction, privacy
or provenance risk, scope expansion, blocking review/validation and AGENTS budgets.

## Verified starting authority

| Evidence | Observed identity / consequence |
| --- | --- |
| Live GitHub `main`, checked 2026-10-21 | `9e9281fe528abe3861630183a7efa4660be58557`; protected branch |
| [PR #428](https://github.com/adamo-sys/coin-analyzer/pull/428) | MERGED at `2026-10-21T19:13:00Z`; merge is main above; foundation head `d9b39f303864a15c70fb46ae539174ef70698602` has identical tree |
| [PR #429](https://github.com/adamo-sys/coin-analyzer/pull/429) | OPEN, unmerged; head `d70ddb343902f9b40ede02ba14875e68a9eef142`; no discussion comments returned at inspection |
| [Exact PR #429 acceptance register](https://github.com/adamo-sys/coin-analyzer/blob/d70ddb343902f9b40ede02ba14875e68a9eef142/docs/OFFLINE_PWA_POST_MERGE_ACCEPTANCE_2026-10-21.md) | Authoritative task input, not merged policy: **4 PASS, 2 FAIL, 18 UNVERIFIED** across its 24 A/B/C/D gates; do not confuse its separate audit-finding rows with those gates |
| [Frozen persistence](architecture/durable-persistence.md) | Canonical Git/LF SHA-256 `A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4` verified; worktree CRLF hash `22D881DBD666163961E5CDAC8F620FF40D6729A70CA47670875C25CC8E5C0997` is a different byte representation |
| New isolated branch / base | `docs/offline-pwa-security-package`, exact base/main above; initially clean |
| New worktree | `C:/Projects/coin-analyzer/build/worktrees/offline-pwa-security-package`; existing ignored `build/` used; no ignore-rule change |
| Protected primary checkout | `C:/Projects/coin-analyzer`, branch `docs/deferred-mass-research-candidate`, HEAD `cb54d10dd19b2c023c1f73344234358df5d802b7` |

Main and PR state were read live using GitHub API; the local main ref was not used
as a substitute. The exact main object already existed, so no fetch was needed.
GitKraken created the isolated worktree from the new branch at that object.
Creating branch/worktree metadata did not switch or edit primary tracked files.

Protected modified-path SHA-256 observations (contents not reviewed):

| Path | Initial fingerprint |
| --- | --- |
| `ROADMAP.md` | `AB3B8FDC22C8780C97B402DAE938FD914D03CBC7AF718AF35C79BF5676F59E34` |
| `benchmarks/bakeoff-v1/RUNBOOK.md` | `21BC140C24D1964F0275261F4BB99CFD34CD5C3A91825476BAC3DDF4BEE448F4` |
| `capture_import/desktop_import_pipeline_selection.py` | `A20B379F6F5E1935AF8BFA7E1D7CEE5DF2FBD176E7322367A3927CE27B506349` |
| `docs/AI_TOOL_EVALUATION.md` | `4925A32B6AAA3360D825B894FC26FCC49274CE2A0683E6BB43FD1460ECD4A1AE` |

## Precedence and conflicts

1. The current user contract authorizes documentation and a reviewed local commit
   only. Historical design/foundation/publication instructions to push or open PRs
   do not carry forward. PR #429's body separately authorizes its publication;
   its retained document contains earlier restrictions. Neither authorizes this push.
2. [AGENTS](../AGENTS.md), [CONTRACT](agent-ops/CONTRACT.md),
   [RUNBOOK](agent-ops/RUNBOOK.md), [STANDARDS](agent-ops/STANDARDS.md) and
   [TESTING](../TESTING.md) govern this task. Current-main CONTRACT additions are
   exact historical Package 0 exceptions, not a general permission or phase release.
3. [Offline design](architecture/OFFLINE_COIN_SHOW_DESIGN.md) and
   [amendment](architecture/OFFLINE_COIN_SHOW_AMENDMENT_PROPOSAL.md) remain PROPOSED.
   [Foundation plan](superpowers/plans/2026-10-21-offline-pwa-foundation.md) and
   [README](../offline_pwa/README.md) establish only the bounded implemented slice.
   Merging it did not adopt every snapshot, purchase, recovery or ingress decision.
4. The approved [HTTP demo](architecture/PHONE_ENTRY_LOCAL_HOST.md) has 120-second
   pairing and an intentionally non-Secure HTTP cookie. Those are its own contract,
   not defaults for the new HTTPS provisioner. This proposal uses five minutes and
   Secure cookies, a separate listener/origin and no demo route reuse.
5. [Reviewed Save](architecture/PHONE_ENTRY_REVIEWED_SAVE_SERVICE.md), frozen
   importer persistence and the approved portion of
   [ordinary baseline](architecture/ORDINARY_COLLECTION_BASELINE.md) retain authority.
   Proposed Option B text is not blanket adoption. IndexedDB transactions do not
   inherit filesystem power-loss or importer recovery guarantees.

## Evidence coverage and present readiness

Inspected: runtime `offline_pwa/{app.js,index.html,manifest.webmanifest,media.js,
storage.js,worker.js}`, README, package scripts, browser tests,
`tools/build_offline_pwa.py`, `tests/test_offline_pwa_build.py`, relevant Tests CI,
the documents above and exact PR #429 register. This is source inspection; no
product/browser suite was rerun for this documentation task. No private corpus,
collection records, exports, photographs or unrelated protected worktrees inspected.

Main's exact-SHA check runs were completed/successful for Windows/Ubuntu unittest,
Ruff, Gitleaks, bounded Pyright, dependency smoke and advisory/security jobs at
inspection. [Tests baseline run](https://github.com/adamo-sys/coin-analyzer/actions/runs/39659673476)
is historical baseline evidence. PR #429's exact-head checks likewise reported
success, including [Tests run](https://github.com/adamo-sys/coin-analyzer/actions/runs/39664195030).
These runs do not execute production authentication or physical-device acceptance.
This unpublished branch has no new-head GitHub CI; no merge readiness is claimed.

PR #429 gates B2 (production security) and C5 (verified recovery) remain **FAIL**
because the capabilities are absent, not because an exploit was demonstrated.
Its bounded browser/storage PASS evidence is retained, not broadened. All new
packet executions are **UNVERIFIED / NOT RUN**. No physical acceptance status changes.

**GO:** review this proposed package and separately scope a future slice.
**NO-GO:** listeners, certificates/trust, device execution, real data, operational
coin-show use, production enablement and phase advancement. Independent document
review cannot close any product gate or grant implementation authority.

## Documentation validation and independent review

Independent read-only reviewer: `/root/security_package_verifier`. Initial verdict
**FAIL**, with two medium blocking documentation omissions: T01 did not explicitly
exercise the separate completion transition; pre-auth enrollment GET allocation
lacked explicit expiry/caps and allocation-request budgets. These were design/test
specification omissions, not confirmed deployed vulnerabilities. Corrections add
S4/S6 fixed context lifetime/caps/budgets and T01/T04/T08 completion/GET-allocation
boundary, race, retry and fault cases. Final exact-byte confirmation is required;
the initial FAIL remains part of the record rather than being relabelled.

Final commands, exact snapshot fingerprints, independent re-review verdict,
resolution evidence and local commit identity are supplied in task closure.
Do not interpret this preparation record as a predeclared passing review.
Any blocking finding must be corrected and independently confirmed against the
final five-file snapshot before commit. No push, PR, merge or deployment is permitted.
