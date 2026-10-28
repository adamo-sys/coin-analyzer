# Coin Analyzer Agent Operations Contract

## Purpose

This file defines the default operating boundaries for AI agents working
on the Coin Analyzer repository.

These rules apply regardless of model, harness, scheduler, or vendor.
The concise entry point is [AGENTS.md](../../AGENTS.md); it owns the context-budget
thresholds and protected boundaries. This file defines task structure and authority.
Codex must apply the [context-budget and rotation rules](../../AGENTS.md#codex-context-budget)
as part of task execution discipline, within existing scope and authorization limits.

## Core Principles

1. Prefer bounded, reviewable changes over broad rewrites.
2. Preserve Coin Analyzer's local-first architecture.
3. Do not weaken existing safety, privacy, validation, or governance boundaries.
4. Treat repository evidence as authoritative over assumptions.
5. Do not claim work succeeded without evidence.
6. Keep durable project decisions in repository files rather than agent memory.

## Default Authority

Unless a task explicitly grants additional authority, an agent may:

- inspect repository files;
- navigate and analyze code;
- inspect issues and pull requests;
- propose implementation slices;
- edit files on a non-default branch when implementation is requested;
- add or update focused tests;
- run focused validation;
- prepare a proposed diff and exact commit file set.

Branches, commits, pushes, PRs, comments, and CI-supporting changes require
authorization expressly covering each applicable action or a named workflow that
explicitly includes them. Authorization to implement a bounded change does not by
itself authorize commit, push, or PR creation. An explicit task restriction (such as
no commit or push) controls even when implementation is authorized. Merge always
requires explicit human authorization for that PR and current passing blocking CI.

An agent must not assume authority to:

- push directly to `main`;
- bypass or weaken required CI;
- disable tests to obtain a passing result;
- publish a release;
- alter secrets or credentials;
- perform destructive repository operations;
- mutate a user's coin collection merely as a side effect of acquisition,
  import, analysis, or discovery;
- introduce cloud or remote dependencies that violate local-first behavior;
- silently expand the requested scope.

## Git Rules

- Work from a task-authorized, verified base. Before substantive work, record and
  compare actual branch, exact HEAD, and intended task-authorized base/ref against
  task expectations; stop on mismatch or unresolved base expectations. Do not fetch
  or mutate the checkout merely to satisfy this gate without authority.
- Never perform implementation directly on the default branch.
- Use a dedicated branch for each bounded change.
- Keep unrelated changes out of the branch.
- Prefer reviewable commits.
- Preserve git history and repository evidence.
- Do not force-push or rewrite shared history without explicit authorization.

## Validation

Before claiming completion:

1. Run the smallest relevant focused tests.
2. Run additional validation required by the affected boundary.
3. Report exactly what was run.
4. Distinguish passing evidence from tests that were not run.
5. Treat GitHub CI as authoritative for repository merge gates.

A prepared command, prompt, or test plan is not evidence that validation ran.

## Bounded-task contract

Before editing, state these six fields in the task. Reuse a complete user-provided
contract; fill only missing operational details. A separate repository task file
is unnecessary unless durable state is needed for rotation.

```text
GOAL: One objective and observable completion condition.
IN SCOPE: Exact proposed files/components and permitted actions.
OUT OF SCOPE: Excluded behavior, cleanup, tools, and follow-on work.
PROTECTED BOUNDARIES: Applicable architecture, invariants, private/local data, authority.
ACCEPTANCE GATES: Focused checks, applicable regression/CI, review, manual acceptance.
STOP CONDITIONS: Task-specific blockers and budget stops, plus root contract stops.
```

Name expected files before editing. Add a prerequisite only if it fits this
boundary; otherwise stop and propose the smallest scope amendment. Do not turn
a documentation-only task into production, dependency, or CI changes.

If accomplishing the task requires meaningful expansion beyond the declared
scope, stop and surface the expansion rather than silently implementing it.

## Evidence and State

Important agent activity should leave durable evidence where appropriate:

- commits;
- pull requests;
- issue comments;
- test results;
- release notes;
- repository documentation;
- machine-readable run ledgers for scheduled agents.

Do not rely on chat history or model memory as the sole record of an
important project decision.

## Scheduled and Autonomous Agents

Scheduled agents must:

- use explicit written instructions;
- maintain durable state between isolated runs when state is required;
- record whether each run completed, skipped, or failed;
- stop safely when assumptions, authentication, permissions, or environment
  conditions differ materially from expectations.

Autonomy should be granted incrementally:

read → analyze → propose → implement → validate → PR → merge → release

A capability being technically possible does not mean it is authorized.

## Conflict Rule

If an agent instruction conflicts with this contract, repository governance,
or a more specific project safety rule, follow the stricter boundary and
surface the conflict.

## Updating This Contract

Change this contract through normal repository review.

Agent behavior should adapt to this file; this file should not be silently
rewritten to accommodate agent behavior.

## SEC-003 Assurance-Tier Amendment

### Authority, applicability and incorporated R2

The owner approved the three-tier architecture reviewed under
`SEC003-EDR-DOC-20261027-01` for controlled governance adoption, subject to
the two nonblocking review notes below, and separately authorized this
append-only amendment. This section records that decision and the explicit
limited prerequisite changes. It grants no execution, acquisition, installation,
CI, dependency-change, spending, commit, publication or follow-up authority.
The final file diff remains subject to separate review; the prior design verdict
does not cover this newly drafted file diff.

Implementation baseline: branch `docs/deferred-mass-research-candidate`,
HEAD/base `cb54d10dd19b2c023c1f73344234358df5d802b7`.
The pre-amendment contract is 5,923 bytes, SHA-256
`D0CCA7E9C77A8B4D72B2E8375B3409A0AE6E4969BE5D3657CBFDD8B5C7AE3A07`.

The operating contract, [runbook](RUNBOOK.md), [standards](STANDARDS.md),
[AGENTS.md](../../AGENTS.md) and [testing/privacy contract](../../TESTING.md)
continue to apply. Only the expressly identified sequencing/applicability
provisions below are superseded for separately authorized lower-tier work.
All other protected boundaries and authority restrictions remain controlling.

Retained SEC-003 sources are under
`build/worktrees/sec-003-1-reconciliation`, recorded base
`1e4150df50815ba2f501a8d12d15acf6dd9abee4`:

- `docs/security/SEC-003_DEPENDENCY_CONTRACT.md`;
- `.sec003-1-local/authorization.txt`;
- `.sec003-1-local/ci-qualification-design-01.md`;
- `.sec003-1-local/owner-decision-record-01.md`;
- `.sec003-1-local/contracts/SEC0031_R2_APPROVED.txt` and its preservation manifest.

The complete **SEC-003.1 R2 — Integrated prospective security contract** is
incorporated by exact identity: **39,704 bytes**, SHA-256
`4B0FF509AAA0AC511BA1905BAFAF38306AB7B5934E1FD8289E944AD069CF2778`.
Its complete normative C1–C12 text, all mandatory prose and all 30 C12 cases
control Tier 3 and every operation within R2's original applicability.
The summaries and lower-tier mapping below neither replace nor modify that text.
Missing or mismatched retained R2 bytes block reliance on this incorporation;
no reconstructed or summarized substitute is permitted. Byte correspondence
does not create new provenance or approval; those remain attributed to the
retained record and manifest.

The retained LPAC parking checkpoint at
`build/worktrees/sec-003-lpac-feasibility/docs/security/SEC-003_LPAC_PARKED.md`
remains **UNVERIFIED / PARKED**. Profile creation and Job Object configuration
did not demonstrate worker isolation.

### Assurance tiers

| Tier | Permitted assurance claim | Required boundary |
|---|---|---|
| **1 — Ordinary development CI and dependency integrity** | A named profile/target has a reproducible, complete, consistently installed and audited dependency set, with bounded synthetic behavior evidence | Approved CI platform and toolchain are trusted infrastructure. No claim of containing deliberately hostile dependency execution |
| **2 — Isolated untrusted dependency execution** | A named operation ran within independently demonstrated restrictions on files, credentials, network, resources, descendants, and evidence production | A separately reviewed and adopted platform-specific containment contract |
| **3 — R2 high-assurance runtime qualification** | Only the result permitted by the complete original R2 contract | R2 C1–C12, all 30 C12 cases, actual platform qualification, and separate owner authority |

Classification follows the operation and threat model, not convenience. A suspicious artifact or deliberate hostile-execution experiment cannot be assigned Tier 1 merely because it runs in CI. Tier 2 does not automatically qualify an R2-governed operation.

### Explicit prerequisite amendment and limits

The reviewed proposal identified the following provisions for supersession.
The owner's controlled-governance adoption approves only these limited changes;
historical authorizations are not revived and no lower-tier operation is admitted
without a new exact, bounded owner authorization.

| Prior prerequisite provision | Tier 1 change | Tier 2 change and retained limit |
|---|---|---|
| Full R2 qualification treated as a prerequisite to dependency work following the blocked Windows/WSL extraction route; retained CI design section 5 step 3 and owner decision record section 10 P5 require R2 or an explicitly adopted distinct procedure | Full R2 is not a universal prerequisite for ordinary trusted development dependency assurance under a separately approved Tier 1 provisioning/install contract | A distinct, independently reviewed and adopted platform containment contract may govern a distinct operation. R2 still applies in full to the original Windows-supervised WSL extraction; relabeling that operation cannot waive it |
| Retained SEC-003-1 authorization's acceptance gates require the approved native matrix; owner decision record section 10 requires all eight universal outputs before later application solving | A separately authorized single profile/target pilot may produce limited Tier 1 evidence before the full native matrix and all eight outputs are complete | A separately authorized contained operation may produce only its scoped Tier 2 evidence before global qualification; it cannot accept shared locks, migrate consumers or credit absent lanes |
| Existing Windows/WSL provisioning and recovery route as the available route to interpreter/tool preflight | Ordinary Linux provisioning requires its own approved acquisition/install contract, exact artifact and trust assumptions | A distinct Linux containment/provisioning route requires its own adopted contract and native qualification; failed Windows/WSL extraction or exhausted allowances supply no authority |

These are changes to sequencing and applicability, not dependency-closure,
tool-qualification, audit, privacy, budget or acceptance waivers. The existing
requirement to qualify complete interpreter/bootstrap/resolver/scanner closures
before application solving remains. All eight outputs and the full approved native
matrix remain prerequisites to global SEC-003-1 acceptance and later consumer
migration; SEC-003-2/3 prerequisite ordering is unchanged. Limited lower-tier
evidence cannot satisfy them by implication.

No support promise is narrowed. Historical attempts and partial extraction trees
remain unqualified. R2's archive invariants, filtering/link policy,
descriptor-relative writes, preservation and prohibition on extracted
interpreter/module execution remain controlling wherever R2 applies.
If an operation straddles tiers or its applicability cannot be resolved, stop
before execution for the smallest explicit owner decision; use no implied waiver.

### Control-by-control requirements matrix

The Tier 3 column summarizes applicability; **the complete original R2 text controls without deletion or substitution**.

| R2 control | Tier 1 requirement | Tier 2 additional requirement | Tier 3 |
|---|---|---|---|
| **C1 — Scope and trust** | Declare platform, runner, actions, toolchain, publisher and advisory-service trust; exclude privileged-compromise resistance | Identify and qualify the enforcement boundary against the stated untrusted workload | Full original Windows/WSL TCB, exclusions and protected boundaries |
| **C2 — Admission/accounting** | Bind authorization, inputs, identities, counters and finite allocation before work; no budget reset | Charge setup, execution, containment and evidence work to the operation’s approved interval | First admitted QPC sample; integer `D=T0+420×frequency`; original accounting and observer-tail exception |
| **C3 — Supervision** | Separate application and audit environments; distinguish producer assertions from independent verification | Enforced workload/control/verifier separation, creation-bound identities, descendant and resource accounting; same-user processes alone insufficient | Complete S/W/C/E architecture, principals, ACLs, jobs, handles and qualified IO registry |
| **C4 — Timing** | Finite stage limits; late, cancelled or incomplete lanes cannot pass; no hard cessation claim | Independent deadline observation and demonstrated containment/cancellation behavior with recorded latency | Original 300/330/390/405/420-second limits and strict pre-D completion |
| **C5 — Isolation/termination** | Disposable approved runner; no access to private material or unrelated workloads | Demonstrate filesystem, credential, egress, process and restart restrictions; exact target-specific termination authority | Exclusive registered WSL target, retained lease/ownership rules and target-only control |
| **C6 — States** | Report generation, installation, closure, audit, behavior and evidence states separately | Also distinguish request, process exit, descendant cessation, IO completion and containment state | Complete orthogonal state model; no inferred transitions |
| **C7 — Failure** | Missing, unknown, failed, cancelled or unapproved-skipped required evidence prevents acceptance | Irreversible attempt rejection; cleanup cannot upgrade it | Original cumulative rejection lattice and no same-attempt rescue |
| **C8 — Completion** | Independent review of complete retained evidence; job exit alone insufficient | Trusted completion evidence outside workload control, including required cessation and IO closure | Original publish/acknowledge/helper-exit/final-QPC sequence and S-only attestation tail |
| **C9 — Evidence** | Exact input/output identities, inventories, commands, exits, raw diagnostics and audit coverage; disclose storage limits | Bounded strict schemas, replay/spoof rejection and protected verifier-owned evidence | Complete original ledger, capture, namespace, publication and attestation protocol |
| **C10 — Races/preservation** | Immutable scoped inputs, reviewed artifact identities, sterile configuration and preserved failures | Demonstrated object/ancestor identity protection and resistance to workload namespace substitution | All original handle, filesystem, archive, topology, link and preservation requirements |
| **C11 — Lifecycle** | Review applicable tooling; preserve primary and cleanup failures; no silent repair | Demonstrate partial-start, drain, flush, independent-close and pending-IO handling | Original remediation obligations, fresh source identities, independent review and runtime qualification |
| **C12 — Qualification** | Finite clean and negative controls for dependency integrity | Synthetic controls plus actual native containment tests; simulation alone insufficient | All 30 original cases plus actual platform qualification |

R2’s exact archive invariants, filtering/link policy, descriptor-relative writes, preservation rules and prohibition on extracted interpreter/module execution remain intact wherever that operation applies.

### Acceptance labels, failures and promotion

Every result must identify the tier, exact profile/target, input revision, toolchain, evidence snapshot and coverage. Labels:

| Label | Meaning |
|---|---|
| `PROPOSED / NOT RUN` | Design only |
| `BLOCKED` | Required authority, environment, budget or qualification unavailable |
| `REJECTED` | An admitted attempt violated a requirement or produced incomplete evidence |
| `T1 — ACCEPTABLE FOR OWNER REVIEW` | All declared Tier 1 predicates passed for that lane |
| `T2 — ACCEPTABLE FOR OWNER REVIEW` | Tier 1 predicates and the adopted containment contract passed for that operation |
| R2 `ACCEPTABLE_FOR_OWNER_REVIEW` | Only the original R2 eligibility result, with its observer-tail exclusion disclosed |

No label means “secure,” “SEC-003 closed,” or “Stage 1B approved.”

Acceptance requires complete applicable evidence, zero unapproved vulnerability findings or coverage gaps, and independent review without unresolved blockers. Missing advisory responses, unsupported packages, malformed reports, unexplained inventory differences and absent required lanes prevent acceptance.

Promotion requires a **new explicit authorization**, applicable stronger controls, independent final-snapshot review and native evidence. Tier 1 evidence can be reused only where its identities and predicates remain applicable; it cannot substitute for containment. Tier 2 evidence cannot substitute for any R2 requirement.

### Tier 1 pilot specification — HOLD / NOT AUTHORIZED

**Purpose:** demonstrate complete dependency accounting for one existing profile and target. It would not amend shared files or migrate consumers.

**Selected profile and target:** Core on Ubuntu 24.04 x86-64, conventional-GIL CPython 3.12.15, using the retained approved `20261021` non-stripped `install_only` build.

**Input reference:** the retained reconciliation Core profile at `1e4150df50815ba2f501a8d12d15acf6dd9abee4`. This selection must appear explicitly in any future pilot authorization. The current assessment checkout is a different baseline; their manifests must not be mixed.

The historical failed extraction and partial tree are excluded. Clean provisioning needs an adopted, reviewed Tier 1 Linux installation contract for the exact approved artifact. If unavailable, the pilot remains **BLOCKED**; no substitute build or repair route is selected here.

Required pilot evidence:

1. **Complete dependency closure.** Resolve every recursive direct requirement, extra, marker and transitive metadata edge. Retain approved candidate intent, including pandas 3.0.6, Flask 3.1.3 within `<4` and qrcode `[pil]` 8.2. **Pillow 12.3.0 is UNQUALIFIED pending independent security/advisory reassessment**; the historical retention preference is not qualification or permission to accept it into a qualified dependency set. That reassessment requires separate authorization and must precede acceptance. Preserve compatible reviewed pins; justify every delta. This amendment supplies no invented transitive versions.
2. **Set equality.** For this target, prove `L = I = A`: evaluated locked distributions, fresh installed distributions and distributions actually submitted for audit. Validate metadata edges separately; an inventory alone does not prove closure.
3. **Tool accounting.** Qualify the retained uv 0.13.5, pip 26.2.2 and pip-audit 2.10.1 selections and their complete bootstrap/tool closures. No open-ended bootstrap exemption or scanner installed into the application environment.
4. **Reproducibility.** Independently generate first/second candidates from the same explicit seed and configuration, then replay the accepted output. Compare canonical locks, allowing line-ending normalization only. Reinstall into a second clean application environment from the approved wheel set with dependency fetching disabled; require inventory equality and `pip check`.
5. **Independent audit coverage.** Audit the complete evaluated application set from the separate scanner environment. Independently verify requested versus returned package/version sets and collection status. Record scanner identity, advisory service, timestamp, exceptions and input digest. A scanner’s zero report cannot establish its own trust or closure completeness.
6. **Synthetic behavior.** Cover core imports, Excel round-trip, image processing, Flask request handling, QR generation and optional OCR/AI absence using synthetic fixtures and temporary paths. No provider calls. No GUI/OCR qualification credited.
7. **Artifact integrity.** Record origins, sizes and hashes of consumed interpreter/tool/wheel artifacts. Hashes establish correspondence, not publisher honesty or absence of malicious code. No SBOM or offline-replay claim without separate evidence.

The finite negative-control manifest must reject each of these independently:

- Missing Flask/qrcode direct coverage.
- Missing transitive edge or incorrect extra/platform marker.
- Manifest/lock version conflict.
- Unexpected installed package.
- Changed or unapproved artifact/source.
- Skipped package, partial audit, malformed response or advisory outage.
- Failed, cancelled or missing required sub-result.
- Stale, altered or producer-forged evidence.

Include one clean control. Preserve expected versus observed outcomes. Do not install malicious samples to test these bookkeeping failures.

**Proposed pilot ceilings:** six disposable application/tool environments; nine total first/second/replay generations across the application and two tool profiles; 180 seconds per generation; 600 seconds for the application lane; **1,800 cumulative machine-seconds**, including preparation, verification, concurrency and a 180-second failure-handling reserve. Every subordinate limit remains capped by the available total.

These are proposed maxima, **not available allowance**. They require reconciled headroom under the historical ceilings. First material failure ends the pilot; no automatic correction, alternate platform, retry or investigation cycle follows.

### Priority CI/audit consistency findings

These priority remediation candidates record static consistency findings at the implementation baseline; runtime consequences and exploitability remain `needs_validation`. This amendment authorizes no investigation or correction:


| Finding | Confirmed static evidence | Still requiring validation |
|---|---|---|
| Different installation and audit inputs | [Tests](../../.github/workflows/tests.yml) installs `.txt` manifests; [Dependency Audit](../../.github/workflows/dependency-audit.yml) audits three `.lock` files | Actual selected/installed/audited set equality for a particular run |
| Flask/qrcode omissions | Both are declared in [core requirements](../../requirements.txt); neither appears in the three inspected locks | Complete target-specific closure and actual audit coverage/impact |
| AI floor mismatch | AI manifest requires OpenAI `>=3.13.0`; AI lock pins `3.8.0` | Current runtime/audit consequences |
| Incomplete independent reporting | Audit steps are sequential; a preceding failure can prevent later steps. Workflow does not request strict collection or prove closure | Selected scanner behavior and retained results under failures |
| Broader consumer drift | Inspected advisory workflows add tools after manifest installation, including unpinned hypothesis | Complete application/tool inventories and audit coverage |

These are **consistency findings**, not confirmed exploitability findings or approved remediation decisions.

Baseline distinction matters: current core declares pandas **3.0.5** and Flask `>=3.1,<4`; the retained reconciliation profile declares pandas **3.0.6** and Flask `>=3.1.3,<4`. The historical pandas mismatch must not be asserted against the current checkout.

### Trust assumptions, residual risks and outstanding Windows evidence

Tier 1 would trust the approved CI provider, runner image, privileged platform services, approved toolchain and package publishers. Ordinary approved package installation/import may execute third-party code. Dependency auditing and hashes do not contain malicious publishers or detect every vulnerability.

Tier 2 must demonstrate its claimed restrictions on the actual platform. A container label, virtual environment, timeout, process group or second process does not establish that boundary.

Across tiers:

- Same-platform producer/verifier separation cannot defeat privileged platform compromise.
- A hosted runner label is not an immutable image identity.
- Version reproducibility does not freeze advisory databases.
- Flush/upload success does not prove physical durability.
- Artifact withdrawal can prevent replay without authorized retention.
- Public sources and TLS do not eliminate publisher or index compromise.
- Source export, console output, artifact retention and credentials require separate scoped controls.
- Protected records, photos, exports and local-only JPEGs remain excluded.

The retained **Windows 11 24H2 x64** requirement remains mandatory and unqualified: all three approved Windows interpreter builds, eight profiles, applicable GUI/AI-floor aliases, complete closure/audits/replay, and native synthetic feature evidence. Windows 10 host observations, hosted Windows 2025, Ubuntu and WSL do not substitute.

R2 additionally needs actual Windows/WSL principal and ACL separation, credential mapping/interop controls, process/job/handle accounting, QPC continuity, exclusive registered-distro lease, qualified IO completion and publication semantics, all 30 C12 cases, and complete finalization/attestation evidence.

Historical preflight/recovery allowances remain exhausted or non-reusable. The retained record reports **5,046.4083199 seconds plus subsequent unmetered work**; this is not a current total or spendable remainder. The 36,000-machine-second ceiling and existing counters remain unchanged. No current headroom is certified.

### Independent design review, mandatory notes and remaining decisions

Independent reviewer `/root/sec003_assurance_edr` returned **PASS WITH NOTES**
with no blocking findings for fixed logical snapshot
`SEC003-EDR-DOC-20261027-01`: the complete proposed amendment, controlling
owner dispositions, review/funding authorization and fixed source
manifest/selections. No whole-packet cryptographic digest is claimed.
All 38 named source fingerprints matched at entry, reviewer exit and the
preceding package's final preservation check.

Coverage comprised all eight review questions: full Tier 3 preservation and
native Windows requirements; explicit prerequisite changes; tier boundaries;
pilot closure/audits/reproducibility/negative controls; pilot accounting;
Flask/qrcode/OpenAI findings; Pillow qualification status; and fail-closed
labels/promotion. This design review did not execute or qualify any platform,
dependency set, advisory reassessment or pilot.

Both nonblocking notes remain mandatory:

1. **Pillow wording:** Every standalone amendment must explicitly retain
   **Pillow 12.3.0: UNQUALIFIED pending independent security/advisory reassessment**.
   The historical candidate/retention preference cannot accept that version.
2. **Pilot scheduling:** Nine generations at their 180-second maxima plus the
   180-second reserve consume all proposed 1,800 seconds. Preparation and
   verification require shorter actual durations or a separately approved
   allocation. The maxima establish neither feasible scheduling nor headroom.
   The pilot remains **HOLD** pending reconciled budget, feasible scheduling
   including preparation/verification/reserve, and separate execution authority.

The single design review used separate documentation-review allocation
`SEC003-DOC-EDR-20261027-01`; it is completed and supplies no further review
or runtime allowance. HIGH reasoning was requested; independent setting
telemetry and enforceable total-token limits were unavailable. Reported wall
intervals were 138 seconds for the reviewer and 376 seconds from preparation
through preservation verification; these are not CPU/cumulative machine-time
measurements. Estimated input exceeded its target; exact input, reasoning and
total-token consumption were unavailable. Unused allowance cannot transfer to
runtime execution.

**Independent final-diff EDR: NOT PERFORMED.** No separately authorized
additional review resources are established for this file diff. The prior
**PASS WITH NOTES** applies only to the named design snapshot and must not be
represented as a verdict on this implementation. The amendment remains
uncommitted and unpublished pending final-diff review and owner disposition.
No automatic review retry, investigation or correction cycle is authorized.

Remaining owner decisions are separate bounded authorization/resources for
final-diff review and any subsequent adoption/publication action; independent
Pillow reassessment; conservative runtime-budget reconciliation and feasible pilot
schedule; exact Tier 1 provisioning/install authority; and, only thereafter,
a separately authorized pilot. Tier 2 requires its own adopted containment
contract and native evidence. Native Windows and R2 qualification remain
outstanding. None of these actions begins automatically.

**Preserved status: SEC-003 OPEN; Stage 1B NO-GO; R2 UNCHANGED;
Windows protected-runtime recovery BLOCKED/PARKED;
Tier 1 pilot HOLD / NOT AUTHORIZED.**
