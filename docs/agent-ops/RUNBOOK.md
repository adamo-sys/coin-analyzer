# Agent Engineering Runbook

**PROPOSED / NOT ADOPTED.** Procedure draft for owner review; the authorized
baseline and independently applicable adopted rules govern until explicit adoption.
See the [authority and equivalence assessment](GOVERNANCE_SIMPLIFICATION_PROPOSAL.md).

## Standard bounded change

1. **Establish once.** Verify repository/worktree, branch, exact HEAD, task-authorized
   base and relevant tracked state against expectations. Use
   `git status --short --untracked-files=no`; inspect only intended new paths
   separately. Stop on mismatch/unresolved base. Record the six-field contract and
   paths once, reusing complete owner instructions. Identify applicable adopted
   rules and [engineering risk tier](CONTRACT.md#engineering-risk-tiers).
2. **Execute within authority.** Use relevant sources and valid prior evidence;
   implement only the bounded objective. Recheck affected entry facts when state
   or assumptions change, and apply root context-budget actions before substantive
   new steps. Preserve unrelated work. Any specialized checkpoint or preservation
   requirement remains mandatory; generic reuse is not a substitute.
3. **Validate proportionately.** Tier 1: relevant focused checks and self-review.
   Tier 2: acceptance tests, affected integration/static checks and independent
   technical review when practical. Tier 3: explicit risk assessment, applicable
   security controls/gates and appropriate independent verification, including
   qualified human review where required. More specific rules always control.
   Docs-only: whitespace, relevant links and available relevant doc checks; no
   full regression solely for docs. Follow [TESTING.md](../../TESTING.md).
4. **Resolve findings finitely.** Record failures, uncertainty and missing evidence.
   Resolve in scope, rerun affected checks and obtain required independent
   confirmation of blocking findings on the final snapshot. Otherwise write one
   [blocker-to-action record](CONTRACT.md#finite-investigation-and-blocker-handling)
   and stop dependent activity. No automatic investigation/review loop.
5. **Close once.** Inspect final diff, exact file set and scope/preservation.
   Report scope/files, exact checks/results and unrun checks, CI head/status,
   reviewer/verdict/findings/limits, risks/deferred work, commit/PR state and
   remaining manual acceptance. Reuse this same record as a handoff if needed.
   Do not assert a fixed repository test total or claim prepared commands ran.
6. **Publish only if authorized.** Revalidate state needed for that action.
   Branches, staging, commits, pushes, PRs, comments and CI changes stay within
   granted authority. Current blocking GitHub CI for the exact PR head is
   authoritative; every merge requires explicit human authorization and passing
   current gates. A review verdict supplies no new authority.

A current-state claim needs current evidence. A valid unchanged entry observation
need not be recollected at every procedural step. If a specific source requires
entry/exit hashes, full-source review, final-snapshot review or native evidence,
perform it; the general workflow cannot waive it.

## Checkpoint and thread rotation

When a task requires a **current-state handoff locator**, that locator must record
UTC observation time, repository identity, exact verified revision, observed
branch/worktree and authorized base (or unavailable status), original source
locators, claims actually verified, freshness/invalidation conditions, blockers
and owner decisions. This does not require a new locator for every routine
checkpoint. Preserve original historical evidence; a digest or summary alone
does not qualify primary bytes.

Apply the unchanged [root context-budget rules](../../AGENTS.md#codex-context-budget)
at task start, work-package boundaries and before substantive new steps. The
50K/65K/75K/100K thresholds, boundary rotation and narrow finish exception remain.
Compaction does not reset the budget. Prefer earlier checkpointing when uncertain.

Reuse one compact closure/decision record as the checkpoint. Persist only to a
named task-authorized non-sensitive Markdown path; never overwrite an unrelated
checkpoint or commit merely to checkpoint. If storage is unauthorized, provide the
complete handoff in-task and disclose that durable storage is pending. A checkpoint
grants neither extra editing nor publication authority.

```text
TASK / GOAL: Objective and six-field contract or durable reference.
STATE: Repository/worktree, branch, exact HEAD and authorized base, modified paths,
       exact proposed file set, staged/unstaged expectations.
PUBLICATION: Commit, push and PR status.
DONE / EVIDENCE: Exact checks, results, relevant CI head/run and review snapshot.
REMAINING: Next authorized action, ordered remaining work and manual acceptance.
BOUNDARIES / BLOCKERS: Dependencies, stops, exclusions and approvals still needed.
CONTEXT: Governing sources/revisions, decisions and material evidence limits.
BUDGET: Observed/estimated use, triggered threshold, any narrow exception/exit.
```

Retain original evidence and protected state without copying private material or
raw logs into the handoff. The next chat verifies recorded state, source authority
and next-action prerequisites; repeat other checks only when changed predicates,
staleness or findings justify it. Any independently binding complete receipt remains.

## Independent verifier / adversarial review

Use the [review requirements](CONTRACT.md#independent-technical-review). Supply a
read-only reviewer the bounded contract, applicable frozen/security requirements,
relevant actual source, exact base/head/diff or fixed uncommitted snapshot, and
validation evidence. A separate same-model session can qualify for technical
independence appropriate to risk; identify the model and separation actually used.
Do not supply protected material without specific access/transfer authority.

The reviewer challenges assumptions, unsafe transitions, fail-open behavior,
unsupported evidence/assurance claims, privacy/provenance/licensing violations,
missing tests and unnecessary churn. Identify actual coverage and omissions.

Return **PASS**, **PASS WITH NOTES** (nonblocking only), **FAIL** (blocking), or
**BLOCKED** (required evidence/access unavailable). Each finding records severity,
file/line, evidence or reproduction, violated requirement and smallest correction.
A BLOCKED verdict cannot satisfy acceptance; unavailable evidence is not a proven
failed behavior. Record reviewer/model, separation, snapshot, verdict and limits.

Resolve in scope, rerun affected validation and obtain independent confirmation
against the revised snapshot for blocking findings before acceptance. Reuse valid
unchanged coverage; do not repeat equivalent review without a material trigger or
binding refresh requirement. Self-review is not independent review. Review does
not establish inaccessible evidence, human/external isolation, CI success or merge
permission. Material security claims requiring a qualified human retain that gate.

## Evidence and scope expansion

Evidence supports only what was actually checked. Reference its source, identity,
claim, coverage and freshness; retain failures and original records. For unresolved
questions use the contract's finite investigation and blocker rule. Stop before a
prerequisite expands scope, exceeds authority or crosses a protected boundary.
