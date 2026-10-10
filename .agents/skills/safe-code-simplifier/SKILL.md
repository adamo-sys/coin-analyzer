---
name: safe-code-simplifier
description: Opt-in, bounded refactoring of task-scoped changes with strict behavioral equivalence and fail-closed project safeguards. Use only when explicitly requested.
---

# Safe Code Simplifier (opt-in)

## Invocation and scope
- Run ONLY when the operator explicitly asks for code simplification. Never automatically run after a PR, during an active authorized task, or as part of an unrelated review.
- Determine the exact target diff/files and baseline commit with the operator or current task context. If ambiguous, ask before editing.
- Work in a clean, isolated branch/worktree. Preserve existing dirty state; never reset, clean, stash, or overwrite operator changes.
- Keep edits small and local. Avoid broad rewrites, dependency additions, architectural changes, and speculative optimization.
- Use one agent by default. Do not spawn extra reviewers unless material correctness or security risk justifies escalation.

## Non-negotiable invariants
- Preserve public APIs, schemas, outputs, error semantics, determinism, and compatibility.
- Do not weaken provenance, immutable external oracle/ground truth, frozen corpus, train/eval separation, confidence routing, ABSTAIN, false-ACCEPT controls, fail-closed behavior, or approval/acceptance gates.
- Never let model-generated output, memory, compaction, or reflection become an authority or correctness oracle.
- No modifications to protected evaluation fixtures, historical oracle data, or frozen inputs as a shortcut to green tests.
- Do not silently delete defensive checks, audit events, validation, or evidence collection.

## Procedure
1. Identify baseline, changed files, tests, and invariant-bearing paths. Report scope.
2. Prefer obvious readability wins: remove genuine duplication, simplify nesting, improve naming, and eliminate dead code only when proven unreachable.
3. Produce minimal diff; avoid formatting churn and unrelated files.
4. Run targeted tests, lint/type checks as applicable, plus invariant-focused regression tests. Compare before/after behavior where possible.
5. If tests cannot run or equivalence is uncertain, STOP and report NOT_VERIFIED; do not claim success or propose merge.
6. Summarize changes, commands/results, residual risks, and any unverified behavior; present diff for human review.

## Acceptance
- PASS only with documented evidence that all relevant tests and safeguards hold.
- Otherwise return NEEDS_REVIEW or NOT_VERIFIED and leave the branch unmerged.
- Never push to main, merge, enable auto-merge, or change branch protection.
