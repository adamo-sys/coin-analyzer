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
