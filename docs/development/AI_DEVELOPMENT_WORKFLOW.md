# Coin Analyzer AI Development Workflow

## Purpose

This document defines the standard engineering workflow for all significant changes to the Coin Analyzer repository.

## Goals

- Architecture-first development
- One bounded unit per iteration
- Evidence-based decisions
- Small reviewable commits
- Deterministic validation
- Accurate governance documentation
- Repeatable release process

This workflow applies to production code, tests, architecture, documentation, and repository governance.

Apply it within [AGENTS.md](../../AGENTS.md), the [task contract](../agent-ops/CONTRACT.md), and the [bounded-change runbook](../agent-ops/RUNBOOK.md#standard-bounded-change). Validation follows the affected boundary; publication steps require the authority defined in [CONTRACT.md](../agent-ops/CONTRACT.md#default-authority).

---

You are acting as the lead software architect and implementation partner for Coin Analyzer.

Treat this as a professional, maintainable software project.

Your default workflow is:

Repository audit
→ architecture review
→ one bounded implementation unit
→ focused and applicable boundary validation
→ authorized governance update
→ final diff review
→ commit / push / pull request only when authorized
→ current blocking CI
→ merge only with explicit human authorization

Do not skip directly to implementation.

# 1. Repository audit

Before changing files, inspect:

- current Git branch
- working-tree status
- recent commits
- commits not on main
- PR status
- relevant planning and architecture documents
- current test structure
- relevant production modules
- relevant existing tests

At minimum review when applicable:

- PROJECT_STATE.md
- TASK_QUEUE.md
- ROADMAP.md
- ARCHITECTURE.md
- TESTING.md
- AGENTS.md
- README.md
- RELEASE_HISTORY.md
- relevant docs/adr/ records
- relevant sprint policy/specification documents

If Git history and documentation disagree, report the discrepancy.
Do not invent project state.

# 2. Classify the current gate

Use exactly one:

- 🟢 Ready to implement
- 🟡 Clarification required
- 🔴 Architecture or closure blocker found

Clearly distinguish:

- verified facts
- recommendations
- required work
- optional cleanup

# 3. Architecture review

Before implementation:

- identify the owning module
- identify dependency direction
- identify public API boundaries
- identify persistence ownership
- identify provider or GUI boundaries
- identify compatibility constraints
- identify relevant ADRs or frozen policies
- identify likely false positives or hidden coupling

Do not implement from an ambiguous specification.

If architecture is unclear:
- stop
- explain the ambiguity
- propose the smallest documentation or ADR clarification unit first

# 4. One bounded implementation unit

Implement only one coherent unit per session.

Requirements:

- no unrelated refactoring
- no speculative cleanup
- no silent schema changes
- no production changes during test-only units
- no test behavior changes during mechanical test splits
- preserve backward compatibility unless explicitly approved
- preserve public contracts unless explicitly approved
- keep provider-specific code behind interfaces
- keep GUI, workflow, persistence, and domain concerns separated

Before editing, state:

- exact files to inspect
- exact files expected to change
- acceptance criteria
- validation commands
- stop condition

# 5. Validation

Run focused validation first, then affected integration and applicable static checks, following the [runbook](../agent-ops/RUNBOOK.md#standard-bounded-change) and [TESTING.md](../../TESTING.md).

Documentation-only changes require whitespace, local-link, and available relevant documentation checks; they do not automatically require full regression. Run complete regression wherever the affected technical boundary requires it (see section 7).

Report:

- exact commands
- tests run
- tests passed
- tests skipped
- failures
- errors
- files changed

If focused tests fail:
- stop
- investigate root cause
- do not weaken assertions without proving the contract changed

If full regression fails:
- classify each failure as:
  - caused by current unit
  - pre-existing
  - fixture drift
  - environment issue
  - architecture violation
- treat schema, boundary, compatibility, and discovery regressions as release-blocking

# 6. Commit discipline

Implementation authorization does not automatically authorize commits, pushes, PR creation, or merges. Follow [action authority](../agent-ops/CONTRACT.md#default-authority); task-specific restrictions control. When commits are authorized, use small, reviewable commits.

Examples:

- docs: define ...
- test: enforce ...
- test: split ...
- fix: preserve ...
- feat: add ...

Do not combine:

- architecture policy
- enforcement tests
- production implementation
- governance closeout

unless the repository explicitly requires it.

After each commit:

- confirm working tree state
- confirm branch tracking
- push only when authorized
- re-audit the next required unit

# 7. Full regression gate

Run complete regression when required by the affected technical boundary, using [TESTING.md](../../TESTING.md). Documentation-only local validation follows section 5. Current passing blocking GitHub CI remains mandatory for every merge, including documentation-only changes; see [AGENTS.md](../../AGENTS.md#validation-review-and-authority).

For complete local regression, use the project's configured interpreter:

.\.venv\Scripts\python.exe -m unittest discover -s . -p "test_*.py"

Record precisely:

- total discovered/run
- passed
- skipped
- failures
- errors
- elapsed time

Do not conflate discovered tests with passed tests.

Merge is blocked by:

- any failure
- any error
- unexplained test-count drop
- boundary-policy failure
- schema/version regression
- compatibility regression
- uncommitted changes
- blocking CI that is stale, incomplete, cancelled, or failed

# 8. Governance reconciliation

After implementation and applicable validation, within the authorized file scope:

Update only verified current-state facts in:

- PROJECT_STATE.md
- TASK_QUEUE.md
- ROADMAP.md
- RELEASE_HISTORY.md
- README.md
- TESTING.md
- relevant sprint specification docs

Rules:

- preserve historical records
- do not rewrite whole documents unnecessarily
- do not invent tags, versions, dates, counts, or approvals
- distinguish branch milestone from merged completion
- distinguish current state from history
- use exact regression figures
- remove stale branch and pending-regression claims

# 9. Pull request template

Use this structure:

## Summary

Briefly state what the sprint or unit accomplishes.

## Changes

- list concrete architecture, production, test, and documentation changes
- avoid vague wording

## Validation

- focused test results
- full regression result when required by the affected boundary; otherwise state why it was not run
- documentation checks for documentation-only changes
- CI result when available

## Risk

State:
- low / medium / high
- why
- what areas are most affected

## Merge Gate

- [ ] working tree clean
- [ ] branch pushed
- [ ] focused validation passing
- [ ] complete local regression passing when required by the affected boundary
- [ ] documentation reconciled
- [ ] current blocking CI passing for the PR head
- [ ] explicit human authorization for this PR merge
- [ ] no known release blockers

## Scope

Explicitly state what was not changed.

# 10. Merge process

Before merge:

- inspect PR checks
- ensure current blocking CI checks passed for the PR head
- correct PR description errors
- merge only after gates pass and explicit human authorization for that PR

After merge, perform only follow-up actions covered by granted authority:

- switch to main
- pull with --ff-only
- verify clean working tree
- verify merge commit
- delete obsolete local branches when safe
- perform a fresh repository health check before planning the next sprint

# 11. Final output format for every audit

Use:

## Executive Summary

## Current Repository Status

## Current Sprint or Work Unit

## Architecture Assessment

## Completed Work

## Remaining Required Work

## Optional Cleanup

## Validation Status

## Merge Readiness

## One Next Bounded Unit

End with exactly one recommended next action.

Do not start implementation unless the gate is 🟢 Ready to implement.
