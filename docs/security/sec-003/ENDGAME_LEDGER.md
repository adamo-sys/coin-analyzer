# SEC-003 endgame ledger

Assessment: 2026-11-06 UTC. **SEC-003 OPEN; Stage 1B NO-GO; R2 UNCHANGED;
PRs #451/#452 HOLD.** This is the consolidated current blocker index. Existing
contracts, historical evidence and rejected attempts retain their authority and
identities; this index does not replace them or grant execution authority.

This first bounded package reconciles the supplied starting state, closes the
verified obsolete draft, and corrects embedded scanner-report publication.
It is **not Outcome A or Outcome B**: further authorized engineering work remains,
including the full-history scanner-wrapper remedy described below. A repository
work-package/context checkpoint must not be represented as external-only closure.

Status vocabulary: PASS means the named predicate has inspected supporting
evidence; FAIL means an established unmet predicate; BLOCKED means acceptance
cannot proceed without the listed prerequisite; NOT RUN means no qualifying
execution evidence; NOT APPLICABLE requires a justified scope exclusion.
Source/synthetic PASS never means native/runtime qualification. No binding
requirement below has been waived as NOT APPLICABLE.

## Contract and exact state

GOAL: Remove safely actionable SEC-003 blockers and retain one independently
reviewable requirement/evidence index; seek formal closure only after all gates.

IN SCOPE: `.github/workflows/tests.yml`,
`tests/test_repository_privacy_boundaries.py`, and this file only in the isolated
package; existing offline checks, read-only security evidence/CI reconciliation,
verified #458 closure, independent technical review, reviewed commit/push/draft PR.

OUT OF SCOPE: Suppression-policy changes, restricted native scanner qualification,
exhausted allowances, protected originals/reports, merges, releases, policy waivers,
production/dependency changes and any implication of historical acceptance.

PROTECTED BOUNDARIES: Original checkout, five retained tracked modifications and
raw index; private/local-only data; complete R2; native/platform and human/custody
requirements; existing holds and finite accounting.

ACCEPTANCE GATES: Exact base/scope/source identity, meaningful offline regression,
affected privacy integration, Ruff/whitespace/docs checks, independent final-diff
review and current GitHub blocking gates before any separately authorized merge.

STOP CONDITIONS: Credential exposure, identity/evidence conflict, protected-data
access, architecture contradiction, unsafe validation failure, authority expansion,
blocking review, exhausted allowances and AGENTS context/work-package boundaries.


### Required SEC-003 / EDR preflight additions — owner-directed 2026-11-11

The following two checks are mandatory inputs to the existing independent
final-diff review gate for later agent-assisted SEC-003 packages. They add no
execution, merge, release, remediation or evidence-access authority. They do not
change any current verdict and are **NOT RUN** for existing packages unless an
exact review record says otherwise.

1. **Agent-configuration secret provenance.** On the exact reviewed repository
   snapshot, the reviewer SHALL determine whether agent permission/configuration
   files, including applicable `.claude/settings.json` and
   `.claude/settings.local.json` paths, are present, tracked, ignored only by a
   machine-local rule, or present in reachable repository history. The check
   SHALL also determine whether an applicable permission rule contains a literal
   credential, token, connection string or secret-bearing command. Evidence
   SHALL identify only path, Git state, rule category and sanitized finding
   identity; secret values SHALL NOT be printed, copied into review artifacts or
   exposed to an LLM. A detected or potentially exposed secret is a STOP
   condition requiring rotation/custody disposition outside this documentation
   amendment. An exact-tree-and-history ABSENT result may satisfy the check only
   when its bounded scope and method are recorded.

2. **Authenticated safeguard-bearing review context.** Before the independent
   reviewer may issue PASS, the review packet SHALL identify the security
   safeguard or policy relevant to each security-sensitive change, authenticate
   its exact repository path and snapshot/blob identity, and state why it is
   controlling evidence. The reviewer SHALL construct or verify this context
   independently of the implementer's conclusion. Functionally similar,
   legacy, vulnerable or otherwise unauthenticated exemplars SHALL be labeled
   untrusted and cannot substitute for the controlling safeguard. If the
   governing safeguard cannot be located and authenticated within authorized
   scope, the dependent review result is BLOCKED rather than inferred from
   nearby code.

The final EDR report SHALL record each check as PASS, FAIL or BLOCKED, the exact
snapshot reviewed, sanitized evidence and remaining limitations. Reviewer/model
diversity or agreement cannot substitute for either check. These additions do
not revise historical EDR receipts, retroactively fail completed packages or
supply any missing F/R/G/C07/R2 evidence.

| Identity | Verified value |
| --- | --- |
| Repository | `adamo-sys/coin-analyzer`, origin `https://github.com/adamo-sys/coin-analyzer.git` |
| Preserved checkout | `C:/Projects/coin-analyzer` |
| Preserved branch / HEAD | `docs/deferred-mass-research-candidate` / `0a4a4bc8f9ae4eed0b3981d8fd1d25d4f83073e0` |
| Isolated worktree | `C:/Users/adamo/.codex/worktrees/sec003-endgame/coin-analyzer` |
| Package branch | `sec003/endgame-reconciliation` |
| Package parent / authorized base | `fbd945079b5db5643aa74d286d45828d47ddac8a` (#460 head) |
| Remote main at admission | `25ebd93f02b58a588445c697cda410475ddbe30e`, verified by HTTPS `git ls-remote` |
| Frozen R2 | 39,704 raw bytes; SHA-256 `4B0FF509AAA0AC511BA1905BAFAF38306AB7B5934E1FD8289E944AD069CF2778` |
| Frozen C07-P1 | 19,885 committed LF bytes; SHA-256 `B85ACAB6B686F63665947E546F54C1586D5DEE4BCCCD405CA6A53B03D61B14D8` |

The original checkout's modified CONTRACT was not used as adopted governance.
The governing contract is the committed file at the package base. Windows CRLF
checkout hashes differ from committed LF blobs; criterion verification used
`git show` bytes, not newline-normalized assertions of raw-byte equality.

Original preservation baseline, SHA-256 (hash-only access):

| Original path | Entry hash |
| --- | --- |
| `ROADMAP.md` | `AB3B8FDC22C8780C97B402DAE938FD914D03CBC7AF718AF35C79BF5676F59E34` |
| `benchmarks/bakeoff-v1/RUNBOOK.md` | `21BC140C24D1964F0275261F4BB99CFD34CD5C3A91825476BAC3DDF4BEE448F4` |
| `capture_import/desktop_import_pipeline_selection.py` | `A20B379F6F5E1935AF8BFA7E1D7CEE5DF2FBD176E7322367A3927CE27B506349` |
| `docs/AI_TOOL_EVALUATION.md` | `4925A32B6AAA3360D825B894FC26FCC49274CE2A0683E6BB43FD1460ECD4A1AE` |
| `docs/agent-ops/CONTRACT.md` | `84D196765C33F616D96EB2670DF9041302245E31C6C5B19D271E8DF7C32E52F2` |
| `.git/index` | `9349D001EE662D1F9DE5E4918CB3C6861A738CAF04004EC55890F0DCE87E77C7` |

## Starting facts and CI

| Item | Status | Current evidence / next action |
| --- | --- | --- |
| #455 merged | PASS | Merge `0deed892100b37b6611f37466ba535ea40c977e4`; published prospective package, did not alone adopt C07-P1 |
| #456 merged | PASS | Merge `961064caf43017d9816f691cf8dc06731abb635a`; records explicit prospective adoption, without backdating historical acceptance |
| #457 merged | PASS | Merge `c2833648c1aed392e05f816e7beeb25391c7807f`; P13 reconciler only |
| #459 merged | PASS | Merge `25ebd93f02b58a588445c697cda410475ddbe30e`; clean replacement of #458 |
| #460 exact head | PASS | Draft, open, `fbd945079b5db5643aa74d286d45828d47ddac8a` |
| #460 CI | PASS | All 20 returned check runs completed successfully on that exact head; no reruns requested |
| #460 merge | BLOCKED | Ready for explicit owner merge decision as offline engineering; no merge performed or qualification implied |
| #458 supersession | PASS | #459 generator bytes identical; normalized test AST identical after evaluating the single inert assertion; expected-value SHA-256 `e59e9d802cd96f32d74715f4c34e5efd0d10b564bb66deb699ed471207d2f4b8`; replacement commit is ancestor of observed main |
| #458 closure | PASS | Closed unmerged at `2026-11-06T15:23:05Z`; branch/commit/history retained; no deletion or history rewrite |
| #451 / #452 | BLOCKED | Both open draft, heads `2f0ed985df3a466ca04402eff0ef366b7ac1cde2` / `0b3c4954866c27a9a25d99201ce52e157d7e7d65`; holds unchanged; diagnostic one-shot not rerun |

Authoritative #460 Tests runs:
[PR 42240874019](https://github.com/adamo-sys/coin-analyzer/actions/runs/42240874019),
[push 42240783152](https://github.com/adamo-sys/coin-analyzer/actions/runs/42240783152).
Both Windows/Ubuntu tests, Ruff, Gitleaks, bounded Pyright, optional SDK smoke and
offline PWA jobs passed. Returned advisory checks also succeeded; their labels
do not establish that every advisory diagnostic passed.

The legacy branch-protection endpoint returned 404, but active
[ruleset 22232667](https://github.com/adamo-sys/coin-analyzer/rules/22232667)
protects the default branch. Its required contexts are `ruff`, `gitleaks`,
`test (ubuntu-latest)`, `test (windows-latest)`, `pyright-event-bus`, with Actions
integration ID 15368. No settings changed. The separate governance requirement
for explicit human merge authority remains binding.

## Actual security remediation and remaining wrapper defect

**Confirmed report-publication gap:** the pinned action defaults artifact upload
and summary to enabled and allows PR comments unless disabled. The existing
privacy validator inspected explicit upload actions only, so embedded action
uploads escaped that check. Upstream source at immutable action commit
`e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e`:
[index.js](https://github.com/gitleaks/gitleaks-action/blob/e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e/src/index.js),
[gitleaks.js](https://github.com/gitleaks/gitleaks-action/blob/e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e/src/gitleaks.js).
Source blob identities are `808a16e5c4447c1b7dc451d7ba237d66f30593be` and
`ee5e10a4e7fcc5e231f7d7dc489d0a2a134aa72c` respectively.
The independent technical reviewer also inspected deployed `dist/index.js` blob
`e98c6b0ba78e612d607cc7b826a647e51df4ebf2`, confirming these switches and preserved
scanner failure propagation; source/bundle correspondence was not merely assumed.

Actual run 42240874019 retained artifact ID `13513717732`,
`gitleaks-results.sarif`, 6,784 bytes, service-reported SHA-256
`c3a2256476a7143b3fab2b0876940ac73139f0c3742d8a468ccd0ed8068b31f7`.
This is metadata evidence of publication, not an independently computed content
digest or credential-exposure finding. Contents were not downloaded/inspected.
Existing artifact custody/retention disposition remains separate; no deletion
or assertion of secret-free content follows from successful CI.
The action still streams redacted verbose/debug CLI output into CI logs. This
fix does not establish absence of sensitive paths/metadata in those logs.

Correction: explicitly set `GITLEAKS_ENABLE_UPLOAD_ARTIFACT`,
`GITLEAKS_ENABLE_SUMMARY` and `GITLEAKS_ENABLE_COMMENTS` to string `"false"`.
The existing privacy gate now checks embedded Gitleaks publication switches.
Missing, enabled, mistyped, non-string, expression-valued and malformed settings
fail the offline gate. Scanner configuration, exceptions, action pin, invocation,
history selection, exit handling, permissions and existing coverage are unchanged.

Validation: new test first failed on 21 independently unsafe variants; after the
fix all 10 privacy tests passed. Scoped Ruff E9/F and whitespace checks passed.
This supports configuration enforcement only. Native action output suppression
and new-head CI still require their own evidence after publication.

**Remaining history-control FAIL:** full checkout hydration does not imply full
scan selection. The pinned action's push/PR invocation uses event ranges with
`--no-merges --first-parent` (and sometimes `-1`), whereas the offline recipe
declares `--all --full-history`. No successful #460 job qualifies P09/P14.
Next authorized engineering work is a separately bounded, independently reviewed
explicit scanner-wrapper correction and offline negative controls, retaining
all suppression/privacy/exit gates. Do not silently label this defect external,
change exceptions to force green, run the native matrix, or consume old allowances.
Actual native detection/history semantics still need separately admitted runs.

## Historical closure ledger and disposition request

The committed [CONTRACT](../../agent-ops/CONTRACT.md) preserves the following
unresolved states. The sanitized retained documents do not supply the missing
original finding-specific requirements. Absence from these inspected sources
is not proof that evidence does not exist elsewhere.

| Requirement | Status | Exact missing artifact / authority / verification |
| --- | --- | --- |
| F-01 historical attestation | BLOCKED | Original attributable finding and governing requirement, affected/reviewed snapshot, qualified reviewer evidence/verdict, and authorized disposition; qualified human verifies correspondence |
| F-02 historical attestation | BLOCKED | Same finding-specific packet for F-02; no equivalence inferred from aggregate unresolved status |
| F-03 historical attestation | BLOCKED | Same finding-specific packet for F-03 |
| F-04 historical attestation | BLOCKED | Same finding-specific packet for F-04 |
| G-02 historical decisions | BLOCKED | Both competing decisions, issuers/authority, dates/effectiveness and snapshots; qualified applicability/conflict crosswalk and explicit resolution |
| Historical C07 | FAIL; disposition BLOCKED | Authenticated original criterion/adoption and review packet unavailable; recovered hardening assessment does not identify/authenticate them |
| Historical C07 suppression | BLOCKED | Defaults-only A/B detection receipt does not exercise an exception, replacement history or differential B/C suppression |
| Protected-original recovery | BLOCKED | Exact-material access authority and appropriate human/custody process; this package did not search sessions, confidential originals or private finding index |

Disposition requested: the owner/qualified authority must either designate the
original sanitized attributable packets or authorize an explicit missing-evidence
disposition through applicable change control. That disposition must retain the
historical uncertainty/noncompliance and cannot be shortened to historical PASS.
C07-P1 prospective adoption supplies neither historical equivalence nor waiver.
This request does not assume the owner can waive technical/human requirements.

Measured retained sanitized source identities, relative to original checkout:

| Source | Bytes | Raw SHA-256 |
| --- | ---: | --- |
| `build/worktrees/sec003-c07-controlled-integration-01/docs/agent-ops/ci-security-hardening-assessment.md` | 26,128 | `7231A1F20E4338AFBBACDCCEAF67F37861AC200109E6C2E168D0F6A693CD9A1B` |
| `build/sec003-c07-integration-review-20261106/INTEGRATION_REVIEW.md` | 12,858 | `DD3DCE9DC536272E2681ECFCCC3AD8D26BBD921C529004733E9C7A5DC3803DF7` |
| `build/sec003-c07-integration-review-20261106/VERIFICATION.json` | 5,921 | `55075121315BD6A69FE14CA8E09EB7E93711B23DC73A3D5A0744DD3CF384F002` |
| `build/sec003-gitleaks-linux-12/RUN01_EXECUTION_REPORT.md` | 6,839 | `27295B84C6B1D9ABA91601E7B1E533ABDCD97F7986FE4333E221A238DDF1744D` |

RUN01 remains FAIL/STOPPED at staged whitespace, before commit/publication/Linux
runtime. No scanner/native credit. Historical assessment and integration reviews
are attributed bounded AI reviews; original reviewer inputs/custody/human assurance
were not authenticated here. Retained integration excludes confidential
attestation and F/R/G reconciliation. No historical failure was erased or rerun.

## C07-P1 acceptance ledger

Criterion/adoption source: [complete frozen criterion](C07_PROSPECTIVE_ACCEPTANCE_PROPOSAL.md)
and [prospective adoption record](C07_P1_PROSPECTIVE_ADOPTION_DECISION.md).
Their historical task-status wording is contextualized by the later adoption.

Catalog reconciliation PASS: P01 1; P02 9; P03 4; P04 4; P05 2; P06 18;
P07 54; P08 9; P09 8; P10 48; P11 10; P12 34; P13 28; P14 17 = **246**.
These are heterogeneous offline definitions, including 28 P13 test methods,
not 246 executed native matrix cells. The previously reported 53 focused tests
are engineering evidence; no local scanner was rerun in this package.

| Requirement | Status for technical acceptance | Required next evidence |
| --- | --- | --- |
| P01 clean | NOT RUN natively | Complete fresh B/C scans, both exit 0, no findings |
| P02 each exact fixture/context | BLOCKED | Independent non-secret evidence, each exact exception approval and pinned-B detectability before C |
| P03 separate/same-line controls | NOT RUN natively | B detects both; C preserves unrelated occurrence, including actual masking/overlap behavior |
| P04 independent same-location A/B | NOT RUN natively | Both histories/paths independently detected with native B/C evidence; prior defaults-only receipt insufficient |
| P05 replacement history | NOT RUN natively | Exact commits/occurrences retained; only approved fixture removed |
| P06 path/rule boundaries | NOT RUN natively | B-detectable wrong-path/wrong-rule controls retained |
| P07 exact-value boundaries | NOT RUN natively | Each mutation/replacement B-prevalidated and preserved in C |
| P08 built-in rules | NOT RUN natively | Effective default-rule identity and native detectability/overlap evidence |
| P09 history | FAIL in current wrapper; native matrix NOT RUN | Full required graph traversal including root/deleted/unmerged/merge-only controls; wrapper remedy above |
| P10 platform paths | NOT RUN natively | LF/CRLF/separators/case coexistence on each actual filesystem; unsupported topology remains unqualified |
| P11 weakened policies | NOT RUN natively | Native behavior rejects each forbidden mutation, with P03-P07 counterexamples |
| P12 operational failures | NOT RUN natively | Actual pinned-tool/error/timeout/report faults propagate to required check |
| P13 finding reconciliation | PASS offline only; native integration BLOCKED | Trusted predeclared plan, authenticated complete records, exact native field/column semantics and multiplicity |
| P14 wrapper bypass | FAIL for history; other native controls NOT RUN | Real control-flow/failure propagation, exact input/rules/ignore policy, publication/privacy and final review |
| Clauses 1-2 snapshot/B-C identity | BLOCKED | Per-platform binary provenance/digest, effective rules/config/invocation/harness/fixture snapshot; only exception differs |
| Clauses 3-5 E/specificity | BLOCKED | Independently non-secret finite E, explicit exception decisions, every B finding detected, C = B minus E by full identity |
| Clauses 6-7 controls/exits | BLOCKED | Effective defaults/full history, no bypass/unchecked failure; 0 clean, 2 valid detection, other failures rejected |
| Clause 8 final acceptance | BLOCKED | Every matrix cell/native lane reconciled and independently reviewed; separate owner technical acceptance |

Native Ubuntu x86-64 and native Windows x86-64 are both required for C07-P1.
SEC-003 Windows claims retain Windows 11 24H2 x64 and applicable full matrix.
Hosted Windows 2025, Windows 10, WSL, synthetic adapters and ordinary CI do not
substitute. The C07 harness has no authenticated raw-scanner-field adapter or
native materialization/driver package; inventing those results would be unsafe.

## R2 C1-C12 requirement status

R2 locator: original checkout
`build/worktrees/sec-003-1-reconciliation/.sec003-1-local/contracts/SEC0031_R2_APPROVED.txt`.
The complete text and mandatory prose control; summaries below are locating aids.
All original applicability, archive/link/preservation invariants and all 30 cases
remain intact. No lower-tier evidence promotes R2 acceptance.

| Control | Status | Evidence limit / artifact needed to advance |
| --- | --- | --- |
| C1 scope/trust | BLOCKED | Exact contract PASS by byte identity; actual enforced Windows/WSL TCB/principal/security boundary unqualified |
| C2 admission/accounting | BLOCKED | S must sample QPC before all run-specific work; integer D=T0+420*f, continuity/anomaly handling and complete charged intervals absent |
| C3 supervision | BLOCKED | Concrete S/W/C/E launch/principals/ACLs/jobs/handles/descendants and qualified IO/resource registry needed |
| C4 timing | BLOCKED | Qualified enforcement/observations for 300/330/390/405/420-second absolute limits, strict pre-D completion and real detection latency |
| C5 isolation/termination | BLOCKED | Exclusive registered-target lease, ownership/restart/quiescence controls and exact target-only termination authority/evidence |
| C6 states | BLOCKED | Independent complete host/guest/process/IO/core dimensions; preserve UNKNOWN, no inferred transitions |
| C7 rejection | BLOCKED | Durable irreversible whole-attempt rejection, accounting/replay protection; local source poisoning alone insufficient |
| C8 completion | BLOCKED | Sole-E publish/acknowledge/closed IO registry/normal exit, all non-S helpers gone, final conjunction and pre-D QPC sample, S-only attestation tail |
| C9 evidence | BLOCKED | Source ledger/host validator PASS WITH NOTES only; protected transport/acquisition, namespace, durable ownership and complete core pipeline missing |
| C10 races/preservation | BLOCKED | Pinned objects/ancestors/mounts/source-through-use, content/link/topology checks and complete preserved failure evidence needed |
| C11 remediation/lifecycle | BLOCKED | Corrected worker/host/binary coordinator source-only reviews; qualified nonblocking Ports/backend, durable failure retention and integrated lifecycle missing |
| C12 qualification | NOT RUN | All 30 cases plus actual native platform qualification required; no execution packet/receipts |

Selected retained source identities, relative to the same `.sec003-1-local/`:

| Source | Bytes | Raw SHA-256 |
| --- | ---: | --- |
| `source-preparation-r2-01/c9-01-correction-01-worker.py` | 38,371 | `CD180665FA86898A2532352DE36B2D568EAA33CEA7C191705EEC7263A7F81E42` |
| `source-preparation-r2-01/c9-host-01-candidate.py` | 31,926 | `94E35583349ADD109C0B38BC70D92ED281676DF1CC7056CA2A34024911089FE2` |
| `source-preparation-c11-01/c11-01-correction-01-candidate.py` | 24,464 | `13DA006F18D8EA5ACE45821554DADC88B0E7EAF234F338DC37292D7F441DCECF` |
| `source-preparation-c11-01/c11-01-checkpoint.md` | 37,863 | `FA50E54B3C502CC06CA0AB2E88D1AD89199363EF6D04F55D652A544749A83267` |

Historical rejected worker/C9/C11 snapshots remain rejected and preserved.
C11 source correction resolved delivered failed-READ payload loss at source
level only. Its correction allowance is **1/1 exhausted**; no further action
may be charged to that old package. A new exact source-preparation boundary and
review are required for concrete backend/supervisor/finalizer implementation.
No retained candidate was executed in this reconciliation.

## Every binding C12 case

Every row is **NOT RUN**. These abbreviations do not omit any subcase or mandatory
prose in the full contract. Case 22 specifically requires actual platform evidence.

| # | Required qualification case | Status |
| ---: | --- | --- |
| 1 | Admission QPC before every run-specific read/hash/acquisition/launch, including blocked preparation | NOT RUN |
| 2 | UTC/timer resets, sleep advancement, reboot/counter anomalies | NOT RUN |
| 3 | Final conjunction D-1 tick vs D/later; late rename/flush | NOT RUN |
| 4 | Freeze S across D with worker success claim; measured detection latency | NOT RUN |
| 5 | Independently blocked read/hash/flush/start/capture/WSL helpers | NOT RUN |
| 6 | Kill S in each phase; leaked job handles/breakaway; no Linux inference | NOT RUN |
| 7 | Successful kill with unsignaled handle, PID reuse/wrong process | NOT RUN |
| 8 | wsl.exe exit with guest/daemon/interop descendants alive | NOT RUN |
| 9 | Terminate returns zero with running/unknown target; ambiguous ownership/workload/restart | NOT RUN |
| 10 | Lease/restart/ownership-loss races throughout stages | NOT RUN |
| 11 | Acquire/start/stdin/drain/flush/dispose/readback/accounting faults, combined errors | NOT RUN |
| 12 | Descendant pipe writer, disk/sharing/oversize/UTF-8/NUL faults; exact raw retention | NOT RUN |
| 13 | Interrupted ledger/core write/flush/rename/ack; partial/duplicate/missing records or attestation | NOT RUN |
| 14 | Ancestor/object/hash-use swaps, concurrent/hash-restore writers, privileged-writer invalidation | NOT RUN |
| 15 | Spoof terminal/helper/receipt/nonce/timestamp/record/source/registration identities | NOT RUN |
| 16 | Byte/link/count/head/digest/namespace mutation, missing evidence/undeclared temp | NOT RUN |
| 17 | Late guest transfer/stop before finalization; no reconstruction rescue | NOT RUN |
| 18 | TERM/KILL delays/subordinate cutoffs cannot extend D | NOT RUN |
| 19 | Missing flush ack/crash loss/unsupported or cross-volume publication | NOT RUN |
| 20 | All pinned worker/archive invariants, fully evidenced good case and each prerequisite failure | NOT RUN |
| 21 | Attestation-only observer tail vs forbidden late task IO/cleanup/new predicates; lost attestation | NOT RUN |
| 22 | Actual principals/WSL/jobs/clock/filesystem/capabilities/registry/async IO/handles/lease semantics | NOT RUN |
| 23 | E alive during publication allowed, alive at final sample rejected | NOT RUN |
| 24 | Ack with open writer/pending IO/duplicated handle; exit alone insufficient | NOT RUN |
| 25 | Unclassified C/E descendants, post-seal delegation, job change/breakaway | NOT RUN |
| 26 | W claims C/E or spoofs/reuses helper identity; ancestry confers no trust | NOT RUN |
| 27 | E crash after publication before ack or after ack before normal exit | NOT RUN |
| 28 | Reordered/duplicate/lost/overflowed notifications/completions; bound conjunction before QPC | NOT RUN |
| 29 | Endpoint/writer/helper/required-handle cleanup/reconciliation after final sample | NOT RUN |
| 30 | No Linux/quiescence inference from helper exit, Windows jobs, command success or restarted query | NOT RUN |

## Dependency/native/release obligations beyond C07

| Binding requirement | Status | Artifact, authority and verification needed |
| --- | --- | --- |
| Tool/bootstrap/resolver/scanner closures before application solving | BLOCKED | Qualified exact interpreter/tool artifacts, inventories, metadata, strict audits, replay and independent review |
| Eight universal outputs | BLOCKED | Complete coherent reviewed locks for core/dev/OCR/AI and all approved unions; source inputs preserved; stop if universal representation impossible |
| Native matrix | BLOCKED | Ubuntu 24.04 and Windows 11 24H2 x64, CPython 3.12.15/3.13.17/3.14.9 release 20261021 conventional GIL non-stripped install_only builds; 8 profiles, 48 native environments plus 6 GUI/24 AI-floor aliases under original counting rules |
| L=I=A and audit coverage | BLOCKED | Native clean install/pip check, exact locked/installed/audited inventory equality, extras/markers/wheel eligibility, zero unapproved findings or gaps per lane |
| Determinism/replay | BLOCKED | Approved exact seeds/core constraints/cutoff, independent same-seed generations and unchanged-input accepted-output replay |
| Native synthetic features | NOT RUN for global acceptance | GUI/Tk/display, Excel/image/Flask/QR/OCR approved prerequisites, offline SDK/transport/floor/optional-absence evidence; no provider calls/private images |
| Pillow 12.3.0 / 13.0.0 | BLOCKED / UNQUALIFIED | Independent security/advisory reassessment and compatibility/coverage acceptance; historical zero-report candidate audits do not qualify either version |
| Tier 1 pilot | BLOCKED / HOLD | Contract prospectively adopted; actual platform/admission/custody/tool-closure/execution gates still required; no new allowance from adoption |
| Budget | BLOCKED | Reconcile all cumulative metered/unmetered intervals, counters and finite headroom before allocation; unchanged 36,000-machine-second ceiling; recorded 5,046.4083199 seconds plus later unmetered work is not a current total/remainder |
| SEC-003-2 consumer/CI alignment | BLOCKED | Accepted SEC-003-1 coherent outputs first; approved mappings and drift/failure controls, native checks and final review |
| Rollback/reproducibility/custody | BLOCKED | Reviewed coherent source/lock/consumer/toolchain rollback, fresh recreation, approved sanitized retention destinations/identities and independent custody; hash equality does not prove authorship/durability |
| SEC-003-3 stronger supply chain | NOT APPLICABLE as mandatory closure gate | Optional package under dependency contract; explicit scope/authority needed if chosen; cannot use its optionality to waive existing provenance/replay obligations |
| #451/#452 release | BLOCKED | Retain HOLD; qualified security/historical/finding reconciliation and current passing required gates plus separate explicit owner merge/release decisions |
| Formal SEC-003 / Stage 1B acceptance | BLOCKED | Every binding requirement evidenced and independent required reviews complete; separate formal approval; this ledger supplies none |

## Execution handoff and evidence custody

Safe repeatable read-only identity commands (use explicit working directory;
original checkout is not an execution fixture):

```powershell
git -C C:/Users/adamo/.codex/worktrees/sec003-endgame/coin-analyzer branch --show-current
git -C C:/Users/adamo/.codex/worktrees/sec003-endgame/coin-analyzer rev-parse HEAD
git -C C:/Users/adamo/.codex/worktrees/sec003-endgame/coin-analyzer status --short --untracked-files=no
Get-FileHash -Algorithm SHA256 -LiteralPath C:/Projects/coin-analyzer/build/worktrees/sec-003-1-reconciliation/.sec003-1-local/contracts/SEC0031_R2_APPROVED.txt
```

Expected: recorded package branch/current published package head, scoped state,
exact R2 digest above. A mismatch stops admission. Before/after original branch,
HEAD, five-file hashes and raw-index hash must match the preservation baseline.

Existing authorized offline commands, from the isolated worktree:

```powershell
& C:/Projects/coin-analyzer/.venv/Scripts/python.exe -B -m unittest tests.test_repository_privacy_boundaries -q
& C:/Projects/coin-analyzer/.venv/Scripts/python.exe -B -m ruff check --no-cache tests/test_repository_privacy_boundaries.py --select E9,F
git diff --check
```

Expected: 10 privacy tests pass, Ruff passes, no whitespace errors. Do not rerun
unchanged successful checks merely to extend a report; independent verification
or changed inputs may justify repetition. Full regression evidence comes from
applicable exact-head GitHub Actions; no full local regression solely for this
workflow/test/document package.

**Native C07 invocation: UNBOUND, NOT READY TO EXECUTE.** Missing reviewed
materializer/driver/raw-report adapter, per-platform scanner binary digest and
effective-rule snapshot, B-detectability/non-secret/exception approval, exact
platform/finite admission and retention policy. These are prerequisites, not
values an operator should guess. The offline constant `--all --full-history`
does not prove merge-only native semantics. Prepare those engineering artifacts
and a new reviewed command manifest before requesting an execution decision.

**Native R2 invocation: UNBOUND, NOT READY TO EXECUTE.** Missing qualified concrete
Ports/backend, S/C/E security boundary/finalizer and actual platform admission.
There is no truthful runnable end-to-end harness command in retained evidence.
Source candidates must not be executed as substitutes. A later command manifest
must bind exact sources/driver/config, target ownership/termination authority,
all C12 selectors and evidence paths. Native acceptance requires all case-specific
predicates, complete preserved failures, strict pre-D conjunction and valid
S-only attestation. Never extend D or rescue a rejected attempt.

Proposed evidence layout for a later separately admitted run:
`<approved-local-evidence-root>/<immutable-attempt-id>/<platform>/<case-id>/`
with input/output inventory, source/binary/config/rules digests, exact command,
environment and counters, predeclared expectations, per-B/C records/exits,
timing/timeout/skip and failure receipts, independent verification and preservation.
Destination, access, retention and transfer authority remain **UNBOUND**; do not
create/upload a bundle or publish raw scanner reports. Only reviewed sanitized
metadata may be incorporated here. No real secret or protected coin material is
needed. If real credential exposure is established, stop that workflow and seek
containment/revocation, preserving evidence under authorized custody.

## Independent review, remaining decisions and checkpoint

`/root/r2_audit`: separate read-only AI technical audit; R2 acceptance BLOCKED,
all 30 cases NOT RUN; selected source identities independently rehashed.
`/root/history_audit`: separate read-only AI audit; historical closure BLOCKED,
source locators/digests and missing original evidence independently checked.
Neither review is an independent human finding, native observation or custody
attestation. Their source/digest results are incorporated above; they do not
rerun or authenticate all prior reviews.

Final engineering-diff/ledger review: `/root/endgame_review`, separate read-only
AI reviewer, **PASS WITH NOTES**, no blocking findings. Independently ran 10
privacy tests and 29 additional adversarial fixtures, rejected the old workflow
and accepted the corrected one, inspected the deployed action bundle, and read
the complete R2/criterion and this ledger. Author documentation checks passed
UTF-8/EOF/conflict markers/local links and all 12 controls/30 case rows.
Workflow committed-LF identity: 7,447 bytes,
`65c6de0c78af368266dbec9bca6d4e75dd5609ad8c93c774ad146585ce6a0eea`;
test identity: 12,757 bytes,
`1608e833d3a96fa830cdb35d3819022b98a0d4297a647b9fbd1eea4c99cac0d9`.
Final changed-predicate/hash confirmation is required before commit; the
publication receipt must identify the exact final reviewed ledger digest.
Notes retain unchanged history limitations, CI-log/existing-artifact uncertainty,
unqualified native behavior and pending exact-new-head CI. A source-only or AI
review cannot satisfy independent human/custody/final native acceptance.

Smallest owner-controlled decisions, to batch after engineering preparation:

1. Explicit #460 merge decision on `fbd945079b5db5643aa74d286d45828d47ddac8a`,
   with current passing gates rechecked at merge. No security closure follows.
2. Designate original F-01-F-04/G-02/C07 attributable packets or commission the
   qualified missing-evidence/conflict disposition, preserving noncompliance.
3. After concrete command/input/evidence packages exist, approve exact platform,
   independent human/custody roles, finite reconciled allocation and native run
   scope; approve each evidenced exception and final technical acceptance only
   after their separate predicates. This is not approval of an UNBOUND recipe.

Next authorized engineering action: finish final review/publication of this
package, then in a fresh bounded package correct the actual history-wrapper gap
and prepare missing native-driver/adapter and concrete R2 source components where
approved interfaces/authority permit. No owner permission is needed for routine
offline edits/tests/reviewed draft preparation already covered by standing scope.
Stop before restricted native work, exhausted-allowance consumption or unresolved
platform/architecture/evidence decisions. Do not claim Outcome B while this
authorized engineering work remains.

Checkpoint publication state at assessment: uncommitted scoped package; #458
closed, #460 not merged, #451/#452 unchanged. Proposed commit set is exactly the
three paths in the contract. Final commit/PR/CI identities belong to the package
publication receipt and task closure message. Original preservation must be
remeasured before publication. Retain this worktree; do not reset or clean it.

Context accounting: exact session-wide count unavailable; tool/discovery volume
approached the repository warning threshold. Complete this bounded reviewable
package, checkpoint exact final state, and rotate before beginning the next
substantive work package. Compaction does not reset that rule.
