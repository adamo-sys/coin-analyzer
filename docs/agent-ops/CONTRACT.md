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

**Package 0 — single historical checkpoint acceptance amendment**

**1. Effect and authority**

This amendment is ineffective until explicitly approved by the owner and adopted through CONTRACT.md’s normal repository-review process. Draft preparation, the earlier append authorization, and the owner’s reported execution do not constitute adoption.

This is a narrowly scoped qualification of Core Principle 3 solely for the historical evidence requirements identified below. It changes the acceptance basis for one historical checkpoint append. It does not certify compliance with the original procedure, retroactively authorize an execution context, or relax operational safeguards for future work.

**2. Exact scope**

This amendment applies only to:

- Worktree: `C:\Users\adamo\.codex\worktrees\first-save-filesystem-phase1\coin-analyzer`
- Branch: `feature/first-save-filesystem-phase1`
- HEAD/base: `8a2258614ac774e4578d1b75046fe0bc0c6a3f11`
- Target: `docs/agent-ops/checkpoint-first-save-filesystem-phase1.md`
- Evidence root: `C:\CoinAnalyzerPhase1Temp\package0-checkpoint-20261017-01a14841`
- Reviewed `checkpoint-write-packet.md`, SHA-256 `FD921C4B24D39544DDB74067809C0D1B392148386DA3392E57A6570BB9E5040B`.

**3. Acceptance clauses being amended**

For acceptance of this historical event only, the alternative criteria below supersede the requirement to establish complete historical compliance with:

- Write-packet pre-write steps 3–4, lines 35–36: contemporaneous raw-index capture, index fingerprint, and historical safeguard checks.
- Pre-write step 5, line 50: complete writer receipt, including argv, timestamps, writer identity, approval reference, and measured hashes.
- Write/post-write requirements, lines 54 and 58: proof of the prescribed execution and paired preservation comparisons.
- Independent verification requirement, line 60: verification of the complete write receipt and actual authorized writer scope.
- The retained owner authorization of `2026-10-17T12:16:57.363Z`, execution requirements 2, 6, and 7 and its final requirement that every mandatory acceptance condition be satisfied, solely insofar as they require the missing historical proof.

These original requirements and their unmet status remain preserved. No historical packet, approval, receipt, or review verdict shall be rewritten.

**4. Permanent historical evidence limitations**

The acceptance record shall permanently state **UNAVAILABLE HISTORICAL EVIDENCE — ORIGINAL REQUIREMENT NOT SATISFIED** for:

1. A complete actual writer execution receipt.
2. A contemporaneous pre-write raw-index identity, size, and hash capture.
3. A paired writer pre-write/post-write raw-index comparison.
4. Independent corroboration of the actual sanctioned, ordinary non-elevated writer context.
5. Proof that every required safeguard executed successfully.

“Unavailable” describes the authorized retained record; it is not proof that no record exists anywhere. Neither this amendment nor new observations may be presented as supplying those historical observations.

**5. Alternative acceptance criteria**

Acceptance under this amendment requires one bounded independent verification confirming:

a. The exact identity above and preservation of the scoped repository state against retained evidence.

b. The following checkpoint relationship, using raw bytes:

- Retained rollback image: 104,367 bytes; SHA-256 `D84CFCA591D31CAF634D1E5BE5B5B17D423D37B86C25EE7C22DB2455C7F7C8D1`.
- Reviewed payload: 8,455 bytes; SHA-256 `9189D54981A099D134A433BC3392CB31EEA4614271DCC0A5FDB8C6949444D568`.
- Resulting checkpoint: 112,822 bytes; SHA-256 `03DC6D882818D819DEF9966F816ABF28C0F8E9B8A1F59FAAB33AD34F876A76AD`.
- The checkpoint equals the entire retained rollback image followed by exactly the reviewed payload, without additional or changed bytes.

c. Integrity and accurate characterization of the retained approval, owner execution report, command-history excerpt, rollback image, and independent post-write findings.

d. Current semantic index emptiness and current raw-index/protected-file comparisons against the retained observations. These establish current consistency only; they shall not be described as historical pre-write preservation.

e. Continued applicability of the other Package 0 requirements and retained dispositions, without repeating selector, cleanup, or checkpoint-chain investigations. The historical `5EB442…4347B` assertion remains UNVERIFIED and NON-AUTHORITATIVE.

f. Explicit owner acceptance of the residual uncertainty in section 6.

**6. Accepted uncertainty**

Matching resulting bytes do not establish the actual writer process, execution context, complete command sequence, or execution of every safeguard. They cannot exclude transient index changes later restored, an unrecorded failed attempt, another execution context, or omitted checks. These are unresolved possibilities, not findings that such events occurred.

**7. Independent review and finite exit**

The reviewer must be separate from the writer and amendment preparer, remain read-only, and assess the exact approved amendment, its governing authority, named retained evidence, current scoped state, and alternative criteria.

The review shall return PASS, PASS WITH NOTES containing only non-blocking findings, or FAIL. It shall identify the reviewer, exact snapshot, findings, evidence, and limitations. The original FAIL-for-closure verdict remains intact.

The owner shall explicitly approve or reject this amendment, including whether approval conditionally authorizes the disposition “Package 0 ACCEPTED UNDER AMENDED CRITERIA — PERMANENT HISTORICAL EVIDENCE GAPS.”

Rejection ends this proposal with Package 0 BLOCKED. Approval permits only the agreed bounded verification after valid adoption. Missing authority, a discrepancy, denied access, or a blocking finding ends verification with Package 0 BLOCKED. No automatic recovery or re-review campaign follows.

Only valid adoption, explicit conditional disposition authority, satisfaction of all alternative and unchanged requirements, and the required independent verdict permit that labelled disposition. It shall never be shortened to a claim that the original historical requirements were satisfied.

**8. Exclusions**

This amendment authorizes no checkpoint append, rollback, index/repository mutation, permission change, test, CI action, commit, publication, Package 1 work, or Phase 2 work. Any separately required adoption action needs its own authority.

Phase 1 remains NO-GO and Phase 2 HOLD until their applicable gates are independently satisfied and the required owner authorization is given.

**Package 0 — prospective exception for one known governance-file preservation discrepancy**

**1. Effect, authority, and limited purpose**

This supplemental amendment is ineffective until explicitly approved by the
owner and adopted through CONTRACT.md’s normal repository-review process.
Preparation, implementation, publication, or the presence of amendment text in
the protected checkout does not establish adoption or Package 0 acceptance.

This is an additional, narrowly scoped qualification of Core Principle 3 and
of the preceding “Package 0 — single historical checkpoint acceptance
amendment.” It permits prospective consideration of acceptance despite the
single governance-file preservation discrepancy identified below. It does
not establish compliance with the original preservation requirements,
retrospective propagation authorization, or permission for any further
protected-checkout change.

The checkpoint packet’s independent restrictions require the additional
explicit owner decision in section 4. Upstream adoption alone does not
satisfy that requirement.

**2. Exact protected scope and attributed fingerprints**

This exception applies only to:

- Repository: adamo-sys/coin-analyzer.
- Protected worktree:
  C:\Users\adamo\.codex\worktrees\first-save-filesystem-phase1\coin-analyzer
- Protected branch: feature/first-save-filesystem-phase1.
- Protected HEAD/base: 8a2258614ac774e4578d1b75046fe0bc0c6a3f11.
- Governance file: docs/agent-ops/CONTRACT.md.
- Historical checkpoint target:
  docs/agent-ops/checkpoint-first-save-filesystem-phase1.md.
- Retained checkpoint packet:
  C:\CoinAnalyzerPhase1Temp\package0-checkpoint-20261017-01a14841\checkpoint-write-packet.md
- Packet SHA-256:
  FD921C4B24D39544DDB74067809C0D1B392148386DA3392E57A6570BB9E5040B.

The owner supplied these raw-byte fingerprints:

- Historical protected CONTRACT.md: 5,923 bytes; SHA-256
  D0CCA7E9C77A8B4D72B2E8375B3409A0AE6E4969BE5D3657CBFDD8B5C7AE3A07.
- Current retained protected CONTRACT.md: 12,602 bytes; SHA-256
  CE2F03D374585FDAFFBF0A80BC9CDEECBC3001E44DC9E13C60863E6C25F8141C.
- Upstream CONTRACT.md merged through PR #415 at commit
  f76a22405c4e0f4c77a1d3576e02ecec8ec7af86: SHA-256
  5832001C38C06C1835B388A05E87D5EBE7EC53804CB8A5331146AC69E8A8D71A.

The owner reports that the original 5,923-byte prefix remains intact, that
the current protected file contains the appended amendment, and that removing
146 CR bytes in memory produces the 12,456-byte merged amendment version.

These are attributed findings until independently verified within separately
authorized scope. Content correspondence does not establish raw-byte
preservation or historical propagation authorization. No normalization,
replacement, or restoration of the protected file is authorized.

The current fingerprint identifies the exact retained discrepancy. It does
not replace the historical fingerprint or become evidence that the original
preservation requirement was satisfied.

**3. Permanent disclosure and exact acceptance qualification**

Every acceptance record relying on this exception shall permanently include:

KNOWN GOVERNANCE PRESERVATION DISCREPANCY — ORIGINAL REQUIREMENT NOT SATISFIED; HISTORICAL PROPAGATION AUTHORIZATION UNVERIFIED.

The historical and current raw-byte fingerprints differ. Original
CONTRACT.md preservation was not satisfied. Retention of the current bytes
does not authorize their historical propagation or establish who propagated
them, when, or under what authority.

For this exact discrepancy only, this supplement qualifies the prospective
acceptance application of:

- The preceding amendment’s section 1 limitation to the previously enumerated
  historical evidence requirements and section 3 enumeration of those
  requirements.
- Its section 5(a) scoped-state preservation requirement, section 5(d)
  protected-file comparisons, and section 5(e) continued Package 0
  requirements.
- Its section 7 discrepancy-stop consequence, independent verification,
  owner acceptance, and labelled disposition requirements.
- The checkpoint packet’s line 29 sole-change restriction; line 36 unchanged
  governance hashes; line 58 governance-hash equality and checkpoint-only
  difference; line 60 preservation verification; and lines 64–66 discrepancy
  stop consequences, solely as acceptance barriers arising from this one
  identified CONTRACT.md difference.

This qualification changes only whether future acceptance may proceed under
express amended criteria. It does not alter the original writer scope,
convert the governance change into an authorized historical operation, or
erase any original violation, stop condition, or review finding.

Every other acceptance requirement remains applicable, including the
preceding amendment’s exact checkpoint byte relationship, retained evidence
integrity, index requirements, all other protected-file and governance-file
comparisons, independence requirements, and permanent historical evidence
limitations. No unrelated discrepancy is excused.

**4. Independent checkpoint-packet restriction**

The retained packet is a separate governing constraint. This CONTRACT.md
amendment shall not be treated as automatically overriding it.

Before this exception may be used, the owner must separately and explicitly
approve a prospective qualification of the acceptance consequences of the
packet provisions identified in section 3, limited to the exact historical
and current CONTRACT.md fingerprints in section 2.

That decision must identify the packet by path and SHA-256, identify the
adopted upstream revision containing this supplement, and expressly
acknowledge both that original preservation was not satisfied and that
historical propagation authorization remains unverified.

The decision must be retained in a separately authorized adoption or
acceptance record outside the protected checkout and original evidence
artifacts. The packet itself, historical approvals, receipts, fingerprints,
and review verdicts shall remain unchanged.

Approval to prepare or implement this supplement does not constitute that
packet decision. Without the explicit packet decision, Package 0 remains
BLOCKED.

**5. Upstream application without protected-checkout mutation**

The adopted upstream contract may govern a later, separately authorized
Package 0 assessment by explicit owner designation of its exact adopted
revision and applicability to the protected identity in section 2.

That designation applies governing criteria to the retained snapshot. It
does not require or authorize checkout, cherry-pick, pull, copying,
normalization, or any other propagation into the protected checkout.

The protected CONTRACT.md shall retain the current raw bytes identified in
section 2. The assessment must cite the adopted upstream revision and the
owner’s applicability and packet decisions separately from the protected
file’s fingerprint. Local presence of amendment text is not proof of valid
adoption.

**6. Independent verification and owner acceptance prerequisites**

Before any acceptance under this exception:

1. A read-only reviewer separate from the historical checkpoint writer and
   amendment preparer must verify the exact adopted amendment, its authority,
   the explicit packet qualification, and the owner’s applicability decision.

2. Within separately authorized access, the reviewer must independently check
   the protected identity, exact current raw-byte fingerprint, and reported
   prefix and content correspondence. New observations must be dated and
   distinguished from historical evidence. In-memory comparisons do not
   authorize on-disk normalization.

3. The reviewer must assess every alternative and unchanged requirement of
   the preceding amendment. This supplement supplies no missing historical
   writer receipt, index capture, safeguard proof, or propagation authority.
   The original FAIL-for-closure verdict and the historical
   5EB442…4347B assertion’s UNVERIFIED and NON-AUTHORITATIVE status remain
   intact.

4. The reviewer must return PASS, PASS WITH NOTES containing only
   non-blocking findings, or FAIL, identifying the reviewer, exact reviewed
   revisions and snapshot, evidence, findings, and limitations. Requested or
   pending review does not satisfy this gate.

5. The owner must explicitly accept the residual historical uncertainty and
   this known governance preservation discrepancy, and separately authorize
   any resulting acceptance disposition.

If eventually authorized and supported by all required evidence, the
preceding amendment’s disposition label shall be extended to:

Package 0 ACCEPTED UNDER AMENDED CRITERIA — PERMANENT HISTORICAL EVIDENCE GAPS — KNOWN GOVERNANCE PRESERVATION DISCREPANCY.

That label must accompany the permanent disclosure in section 3. It shall
never be shortened into a claim of original compliance or historical
propagation authorization.

Missing authority, denied access, a different fingerprint, any additional
discrepancy, or a blocking finding leaves Package 0 BLOCKED. The preceding
amendment’s finite-exit rule remains applicable; no automatic repair,
restoration, investigation expansion, or re-review campaign is authorized.

**7. Exclusions and retained status**

This supplement grants no filesystem or repository mutation, checkpoint
append, restoration, index change, permission change, test, CI execution,
branch creation, commit, push, PR, merge, publication, Package 1 work, or
phase advancement authority. Each separately required implementation,
adoption, verification, recording, or publication action needs its own
applicable authorization.

Proposal, implementation, adoption, and review do not themselves certify
acceptance or grant execution permission.

Until separately authorized acceptance and phase decisions satisfy their
applicable requirements:

- Package 0: BLOCKED.
- Phase 1: NO-GO.
- Phase 2: HOLD.
- Execution allowlist: EMPTY.

## SEC-003 Assurance-Tier Amendment

### Authority, applicability and incorporated R2

The owner previously approved the three-tier architecture reviewed under
`SEC003-EDR-DOC-20261027-01` for controlled governance adoption, subject to
the two nonblocking review notes below. The owner separately authorized
preparation of this one adapted target-main integration draft. Preparation
does not establish target-main adoption or approval of the integrated diff.
The prerequisite changes below become applicable on this target only after
explicit owner approval and normal repository-review adoption.

This section grants no execution, acquisition, installation, CI, dependency-change,
spending, branch/worktree creation, commit, push, PR, merge, publication,
independent review or follow-up authority. The current drafting package's
branch/worktree and sole-file editing authority comes only from its bounded
owner authorization. Independent review of this integrated diff remains pending.

Repository: `adamo-sys/coin-analyzer`.
Target-main HEAD/base: `7374c234a5e985d654cc9a87dda32dc7e88e8dbf`.
Draft branch: `docs/sec-003-target-main-integration`; isolated worktree:
`C:/Projects/coin-analyzer/build/worktrees/sec-003-target-main-integration`.
The entire pre-amendment target contract is retained as an unchanged LF prefix:
22,435 bytes, SHA-256
`483E76F88B293437C1F9BAC2F114275CBFCE727EA9CEBBECC6269961B76FFCEB`.

The substantive source is the independently reviewed amendment at commit
`2f2fc58c59cef8df8ba63b671facc049e6161932`, whose complete committed LF
CONTRACT.md blob is 30,155 bytes, SHA-256
`F8F7B6CC26A4B825A55CF414EA2E078B8023874FF0B6507E00AFC25940B24845`.
Its historical implementation baseline was branch
`docs/deferred-mass-research-candidate`, HEAD/base
`cb54d10dd19b2c023c1f73344234358df5d802b7`; its pre-amendment contract
was 5,923 bytes, SHA-256
`D0CCA7E9C77A8B4D72B2E8375B3409A0AE6E4969BE5D3657CBFDD8B5C7AE3A07`.
Those historical identities are not the target-main baseline.

The operating contract, [runbook](RUNBOOK.md), [standards](STANDARDS.md),
[AGENTS.md](../../AGENTS.md) and [testing/privacy contract](../../TESTING.md)
continue to apply. Upon valid target-main adoption, only the expressly identified
SEC-003 sequencing/applicability provisions below are superseded for separately
authorized lower-tier work. All other protected boundaries and authority
restrictions remain controlling.

Both preceding Package 0 amendments remain unchanged: "single historical
checkpoint acceptance amendment" and "prospective exception for one known
governance-file preservation discrepancy." Their narrowly scoped qualifications
of Core Principle 3 and historical acceptance requirements, exact identities,
permanent disclosures, independent packet decision, upstream applicability
designation, protected-checkout non-mutation, independent verification, owner
acceptance and finite-exit requirements remain intact. SEC-003 prerequisite
supersession neither overrides those requirements nor broadens, revokes or
repurposes their scoped exceptions. This draft supplies no Package 0 adoption,
packet qualification, applicability designation or acceptance decision.
Package 0 BLOCKED, Phase 1 NO-GO, Phase 2 HOLD and execution allowlist EMPTY
remain as stated in the preceding supplement until their own gates and separate
owner decisions are satisfied. No protected Package 0 material is changed.

Retained SEC-003 sources are under the original checkout root
`C:/Projects/coin-analyzer`, at
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

The retained LPAC parking checkpoint under that same original checkout root at
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

The reviewed source identified the following SEC-003 provisions for supersession.
Upon valid target-main adoption, only these limited sequencing/applicability
changes apply. They do not supersede unrelated governance or either Package 0
amendment and its scoped exceptions. Historical authorizations are not revived
and no lower-tier operation is admitted without a new exact, bounded owner
authorization.

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

**Input reference:** the retained reconciliation Core profile at `1e4150df50815ba2f501a8d12d15acf6dd9abee4`. This selection must appear explicitly in any future pilot authorization. The pinned target-main checkout is a different baseline; their manifests must not be mixed.

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

These priority remediation candidates preserve the reviewed source's static
consistency findings. The target-specific pandas/Flask facts below are based on
the pinned target-main manifests and locks, not a dependency execution or audit.
Runtime consequences and exploitability remain `needs_validation`.
This amendment authorizes no investigation or correction:


| Finding | Confirmed static evidence | Still requiring validation |
|---|---|---|
| Different installation and audit inputs | [Tests](../../.github/workflows/tests.yml) installs `.txt` manifests; [Dependency Audit](../../.github/workflows/dependency-audit.yml) audits three `.lock` files | Actual selected/installed/audited set equality for a particular run |
| Flask/qrcode omissions | Both are declared in [core requirements](../../requirements.txt); neither appears in the three inspected locks | Complete target-specific closure and actual audit coverage/impact |
| Target-main pandas mismatch | At pinned target main, core requires pandas `3.0.6`; runtime, development and AI locks pin `3.0.5` | Complete target-specific closure and actual installation/audit consequences |
| AI floor mismatch | AI manifest requires OpenAI `>=3.13.0`; AI lock pins `3.8.0` | Current runtime/audit consequences |
| Incomplete independent reporting | Audit steps are sequential; a preceding failure can prevent later steps. Workflow does not request strict collection or prove closure | Selected scanner behavior and retained results under failures |
| Broader consumer drift | The reviewed source's inspected advisory workflows add tools after manifest installation, including unpinned hypothesis | Current target-specific consumer inventories and audit coverage; no refreshed broad consumer assessment is claimed |

These are **consistency findings**, not confirmed exploitability findings or approved remediation decisions.

Baseline distinction matters: the reviewed source's historical assessment core
declared pandas **3.0.5** and Flask `>=3.1,<4`; its warning against asserting
the historical pandas mismatch described that source baseline only. The retained
reconciliation profile declares pandas **3.0.6** and Flask `>=3.1.3,<4`.
At pinned target main `7374c234a5e985d654cc9a87dda32dc7e88e8dbf`, core
also declares pandas **3.0.6** and Flask `>=3.1.3,<4`; the three inspected
locks still pin pandas **3.0.5** and omit Flask/qrcode. The pandas manifest/lock
mismatch therefore applies to this target. Neither those matching direct
requirements nor this static comparison establishes complete dependency closure,
installation consistency, advisory coverage or qualification.

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

**Review statuses are distinct.** The design **PASS WITH NOTES** above applies
only to `SEC003-EDR-DOC-20261027-01`. The owner handoff identifies source
commit `2f2fc58c59cef8df8ba63b671facc049e6161932` as independently reviewed.
The committed source's "Independent final-diff EDR: NOT PERFORMED" and
"uncommitted and unpublished" statements describe its drafting-time state;
they are retained here as historical observations, not current source status.
The source is now a committed reference. No later original-final-diff reviewer
identity, verdict or review-report identity is supplied in this drafting handoff;
none is invented here. Source review does not cover this adapted integrated diff.

**Independent integrated-diff EDR: NOT PERFORMED / NOT AUTHORIZED in this
package.** No additional review resources are established for this integrated
file diff. This target-main draft remains uncommitted and unpublished pending
separately authorized integrated-diff review and owner disposition. Neither
prior design review nor original source review satisfies that pending gate.
No automatic review retry, investigation or correction cycle is authorized.

Remaining owner decisions are separate bounded authorization/resources for
integrated-diff review and any subsequent adoption/publication action; independent
Pillow reassessment; conservative runtime-budget reconciliation and feasible pilot
schedule; exact Tier 1 provisioning/install authority; and, only thereafter,
a separately authorized pilot. Tier 2 requires its own adopted containment
contract and native evidence. Native Windows and R2 qualification remain
outstanding. None of these actions begins automatically.

**Preserved status: SEC-003 OPEN; Stage 1B NO-GO; R2 UNCHANGED;
Windows protected-runtime recovery BLOCKED/PARKED;
Tier 1 pilot HOLD / NOT AUTHORIZED.**

## SEC-003 Tier 1 Linux provisioning: prospective adoption record

### Owner disposition and exact prospective scope

The owner's 2026-10-28 "Owner Authorization — SEC003-T1 Adoption
Documentation" records **SEC003-T1-LINUX-PROVISIONING-DRAFT-01: ADOPTED**
as a prospective governing contract. This record identifies the accepted
preserved representation below and carries forward its complete Sections 1–12,
subject to the narrow Section 8 disposition below. It does not authenticate
historical original bytes or convert documentation adoption into execution
permission. This documentation package remains uncommitted and unpublished;
publication requires a separate owner decision after final-diff review.

The authorized documentation baseline is branch `docs/sec003-t1-adoption`,
worktree `C:/Projects/coin-analyzer/build/worktrees/sec003-t1-adoption-docs`,
HEAD `9ebb14973646170e385e0cc95b6b2b33d2cfbfae`. The incorporated governance
baseline remains `27672e6820c3c92e2fc5a5036fcc815bde9b338f`.

The adopted scope is ordinary trusted Tier 1 Linux interpreter and tool
provisioning criteria only. The failed Windows-supervised WSL operation is not
reclassified, repaired or authorized. R2 remains unchanged wherever applicable,
including complete C1–C12, all 30 C12 cases and native platform qualification.
Tier 2 containment and Tier 3 qualification cannot be inferred from this adoption.
The preceding Package 0 amendments and their separate restrictions are unchanged.

### Preserved snapshot identity and provenance limitations

The owner accepts the eight-file preservation remedy with its documented
provenance and durability limitations. The snapshot is
`SEC003-T1-LINUX-PROVISIONING-DRAFT-01-local-preservation`, under
[`docs/security/sec-003/t1-linux-provisioning-draft-01/`](../security/sec-003/t1-linux-provisioning-draft-01/).
The exact adopted prospective contract representation is
[`draft.md`](../security/sec-003/t1-linux-provisioning-draft-01/draft.md).
The separate
[`preservation-manifest.json`](../security/sec-003/t1-linux-provisioning-draft-01/preservation-manifest.json)
identifies seven content files; its own identity is recorded externally here.
All identities below cover complete preserved raw bytes using SHA-256:

| Preserved file | Bytes | SHA-256 |
|---|---:|---|
| README.md | 1,043 | `3EB993E996E78ADCB385A43E8E3D97F02B3BF6EA6AD96BCA7BA2CCF699516FF5` |
| draft.md | 17,974 | `8FC0714B5A8C624861609CC9A7A6B707D264ED667733AF476199DA950D785ADD` |
| edr-report.md | 8,391 | `A9689584A0DCDD63E68B9927A1EA2FEB6A4FBEEF4FD9F82AA014B4136F781124` |
| evidence-matrix.md | 1,703 | `F727165D791216026E290666D18E83E96D18D25B2ABBAAAB76CCF5CA7B9782D0` |
| manifest.json | 1,308 | `EDD98EE87347E2B806D3C5745EE4441F1BC05BD087430DFDCC9E20E6DDBFBE72` |
| owner-disposition-supplement.md | 821 | `BE97DF92DB57D2C02DDC59162EF8E56B4D8E677E17B8F7FAA636EC7D69971C3C` |
| preservation-manifest.json | 5,583 | `9197F04A84F53B3E193738CDCF40C8E515A875D1D2E55DDDE256CBC02CCDC2AF` |
| section-8-static-verification.md | 9,811 | `AA7512E9181BACA2FD0939FAA04F0FD3C314AE63E50426F94F0713605A6EED82` |

The logical reviewed draft and this serialized preservation snapshot remain
distinct. The original logical draft has no authenticated whole-packet digest.
The recovery transcriptions are not certified original Codex file bytes. Current
byte correspondence establishes preservation relative to these identified files,
not retrospective authorship, complete approval provenance or historical fidelity.
The unchanged `manifest.json` is the recovery-candidate manifest; it is not
independent provenance authentication. No recursive or whole-packet digest is
claimed. Flush/readback observations do not establish physical durability,
power-loss persistence or resistance to privileged tampering.

The preserved files remain immutable. Their `PROPOSED / NOT ADOPTED` and similar
labels describe the retained earlier dispositions. The current owner's ADOPTED
disposition supersedes those labels only for prospective contract status. It does
not rewrite the reports, alter their review coverage, certify missing history or
supersede any execution, qualification, security or budget hold. Evidence and
review reports remain evidence records, not additional execution authority.

### Section 8: narrow static-interface condition satisfied

The owner accepts
[`section-8-static-verification.md`](../security/sec-003/t1-linux-provisioning-draft-01/section-8-static-verification.md)
as satisfying only the before-adoption requirement concerning selected-version
flags, exit semantics and machine-readable report schemas for uv 0.13.5,
pip 26.2.2 and pip-audit 2.10.1. The separate
[`owner-disposition-supplement.md`](../security/sec-003/t1-linux-provisioning-draft-01/owner-disposition-supplement.md)
records that narrow acceptance and remains a newly supplied decision, not a
recovered historical message. This adoption record does not independently repeat
or extend the static verification. The report's documented interface limits
remain controlling inputs to any later implementation design.

That acceptance does not qualify tool artifacts, complete dependency closures,
bundled/vendored components, bootstrap trust, native dependencies, actual flags
or schemas at runtime, reproducibility, installation, inventories, audits or
failure handling. The reported prior independent EDR PASS applies to prospective
contract design only; it is not a fidelity verdict on this preservation snapshot,
a runtime verdict or the final-diff EDR of this adoption documentation package.

### Outstanding gates and retained governing status

Adoption discharges only the prospective contract-adoption decision. All other
applicable prerequisites remain open, including:

- Exact approved platform/image/TCB, storage paths, privilege and credential
  controls, source/egress policy, independent verifier and complete admission
  schedule, finite limits, evidence retention and cancellation authority.
- Independent artifact authentication and custody; reviewed extraction
  implementation and native qualification; sealed-tree integrity and separate
  authority for interpreter execution. Retained artifact selections and archive
  policy are unchanged; neither the failed partial tree nor alternative builds
  are approved.
- Complete independent bootstrap/resolver/scanner qualification under Section 8,
  including closures, metadata, reviewed staged wheels, reproducibility/replay,
  inventories, strict complete audits and finite clean/negative controls before
  application solving. Static-interface acceptance is not tool qualification.
- Conservative cumulative budget reconciliation, certified finite headroom and
  separately authorized allocations. The 36,000-machine-second ceiling and all
  counters remain unchanged; exhausted allowances are not revived or transferred.
  Pilot maxima are not available allowance and their scheduling issue remains.
- Separate implementation, acquisition, installation, interpreter/tool execution,
  pilot and later application-work authorizations. Adoption grants none of them.
  All eight outputs, complete metadata closure, L = I = A, audits, replay,
  synthetic feature evidence and the full approved native matrix remain required
  for global SEC-003-1 acceptance and later consumer migration.
- Mandatory Windows 11 24H2 x64 qualification across the approved interpreter
  builds, profiles and applicable aliases; Linux, WSL or hosted Windows results
  do not substitute. SEC-003-2/3 ordering and local-first/privacy rules remain.
- **Pillow 12.3.0: UNQUALIFIED pending independent security/advisory reassessment.**
  No historical retention preference, static verification, EDR or adoption accepts it.

This package requires its own independent final-diff EDR covering scope,
provenance, internal consistency, security boundaries and byte/diff integrity.
Prior EDRs do not satisfy that gate. Review status must be reported against the
exact reviewed snapshot; this record supplies no new historical review receipt.
No commit, push, PR, merge, workflow change or publication is authorized here.

**Current governing status: prospective T1 contract ADOPTED; SEC-003 OPEN;
Stage 1B NO-GO; R2 UNCHANGED; Pillow 12.3.0 UNQUALIFIED;
Tier 1 pilot HOLD / NOT AUTHORIZED; implementation, provisioning and
qualification NOT AUTHORIZED.**
