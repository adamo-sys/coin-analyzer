# Agent Engineering Runbook

## Standard bounded change

1. Before substantive work, record and compare actual branch, exact HEAD, and
   intended task-authorized base/ref against task expectations and the handoff.
   Stop on mismatch or unresolved base expectations. Do not fetch or mutate the
   checkout merely to satisfy this gate without authority.
2. Verify tracked state and the dedicated non-default branch. Inspect only relevant
   guidance/source; preserve unrelated, protected, and in-progress local work.
3. State the [six-field contract](CONTRACT.md#bounded-task-contract) and proposed
   file boundary before editing. Check for conflicting relevant guidance.
4. Implement only the bounded objective. Apply the budget actions in
   [AGENTS.md](../../AGENTS.md#codex-context-budget) before substantive new steps.
5. Run the smallest meaningful checks, then applicable gates from
   [TESTING.md](../../TESTING.md). Docs-only work: whitespace, local links, and
   available relevant documentation checks; no full regression solely for docs.
6. Review the final diff and exact proposed commit set. Report passing, failing,
   and unrun checks separately. Use independent review for significant closure
   when practical; disclose when it was unavailable.
7. Commit, push, and open a PR only within granted authority. GitHub CI for the
   exact current head is authoritative for merge gates. Merge only with explicit
   human authorization for that PR and passing current blocking gates.

## Checkpoint and thread rotation

Use the root budget thresholds without redefining them here. Keep one compact
checkpoint in a task-authorized, non-sensitive Markdown path (for example
`docs/agent-ops/checkpoint-<task>.md`); name the path before writing. Do not modify
an unrelated existing checkpoint. A checkpoint is not automatically publishable
or part of the commit set. If writing it is not authorized, provide the complete
handoff in the task and report that repository persistence remains pending.

```text
TASK / GOAL: One sentence; six-field contract or its durable reference.
STATE: Branch, exact HEAD, changed paths, proposed commit set, commit/PR status.
DONE / EVIDENCE: Verified results with commands, outcomes, relevant CI head/run.
REMAINING: Ordered next steps; identify the first safe action.
BOUNDARIES / BLOCKERS: Exclusions, protected data, unresolved findings, approvals needed.
CONTEXT: Relevant files/sections and decisions with brief reasons; no rediscovery log.
BUDGET: Reported/estimated usage or unavailable; triggered threshold; exception/exit if any.
```

Preserve uncommitted work; never commit merely to checkpoint. Include enough of
the contract to resume without the old chat. Do not copy secrets, private data,
raw logs, or large diffs into the handoff. In the new task, verify only the recorded
state and next-step prerequisites; do not repeat completed checks unless evidence
is stale, changes occurred, or a finding warrants it. Compaction within the same
thread is not rotation and does not reset the budget.

## Independent verifier / adversarial review

- For significant feature/sprint closure, use a reviewer separate from the
  implementer when practical. Supply only the bounded contract, relevant frozen
  specification/invariants, exact diff/base/head (or uncommitted snapshot), and
  validation evidence. Exclude private material and unrelated history.
- Reviewer remains read-only and does not silently broaden scope. Challenge the
  implementation: seek counterexamples, unsafe transitions, fail-open behavior,
  unsupported claims, privacy/provenance/licensing violations, and missing tests.
  Check whether validation proves acceptance and whether churn is necessary.
- Return **PASS**, **PASS WITH NOTES** (non-blocking only), or **FAIL** (blocking).
  Each finding names severity, file/line, evidence or reproduction, violated
  contract/invariant, and smallest correction. Disclose unverified areas.
- Implementer resolves findings only within scope, reruns affected checks, and
  requests re-review of blocking findings against the updated snapshot. Before
  closure, the independent reviewer must confirm resolution against that snapshot.
  Requested or pending re-review does not satisfy the gate; unresolved or
  unconfirmed blocking findings remain blocking. Review does not replace CI or
  grant merge authority.
- Record reviewer identity/role, reviewed revision or snapshot, verdict, findings,
  and remaining limits. Self-review must not be labeled independent review.

## Evidence and scope expansion

Prepared commands and agent confidence are not validation evidence. Report exact
results and relevant artifacts/CI links. Stop and surface any prerequisite that
expands scope, exceeds authority, or crosses a protected boundary.
