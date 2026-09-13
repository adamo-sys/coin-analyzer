# Coin Analyzer Agent Harness v1

## Start and scope

- Before substantive work, record and compare actual branch, exact HEAD, and
  intended task-authorized base/ref against task expectations; stop on mismatch or
  unresolved base expectations. Do not fetch or mutate the checkout to satisfy
  this gate without authority. Inspect tracked state using
  `git status --short --untracked-files=no` when unrelated local artifacts exist;
  check only intended new paths separately. Do not enumerate protected data.
- Read only guidance/source needed for the task. Verify the handoff against current
  evidence; do not rediscover the whole repository.
- Before editing, state the file boundary and six-field task contract in
  [CONTRACT.md](docs/agent-ops/CONTRACT.md#bounded-task-contract). Reuse a complete
  user contract. No unrelated cleanup or speculative refactors.
- Use [RUNBOOK.md](docs/agent-ops/RUNBOOK.md) for checkpoints and independent review;
  consult [STANDARDS.md](docs/agent-ops/STANDARDS.md) for detailed standards.

## Codex context budget

These are repository operating thresholds, not model capacity claims. K = 1,000
tokens of accumulated thread context/work; compaction does not reset this budget.
Use available session accounting; label estimates. If accounting is unavailable,
report that limitation rather than invent a count. Checkpoint at each bounded
work-package boundary and rotate before another substantive package; genuinely
nearly-complete current work may finish only under the exception below.
Check at task start, work-package boundaries, and before substantive new steps.

| Threshold | Required action |
| --- | --- |
| 50K | Warn the user; report current state and remaining work. |
| 65K | Prepare a durable checkpoint/handoff now; stop beginning new substantive steps. |
| 75K | Normal hard rotation cap: stop work and rotate with the handoff; no substantive new work. |
| 100K | Emergency ceiling only, never a planned working budget; stop by this limit. |

Exception: finish a genuinely nearly-complete step only if stopping would create
more work. Record the specific step, reason, and bounded exit; no new scope or
extension past 100K. Then checkpoint and rotate. These are agent-enforced rules,
not an installed token monitor. A stricter task-specific stop rule takes priority.

## Architecture and protected boundaries

- Production behavior must follow applicable frozen architecture/contracts.
  If absent or contradictory, stop and propose the smallest architecture amendment.
  Docs, tests, CI, tooling, and hygiene need no unrelated production amendment.
- Preserve local-first behavior and optional network/AI features. Recognition and
  evaluation are advisory; they do not own persistence or collector decisions.
- Never inspect, commit, upload, or migrate collection backups, exports, live
  records, notes, credentials, or private photos without authorization for the
  exact material and operation. Backups/exports remain outside source control.
- Preserve unrelated local/untracked files and ignored private benchmark artifacts.
  Do not investigate `data/imports/` permission warnings unless required by scope.
- The ten JPEGs in `test_coins/` are **UNCERTAIN / LOCAL-ONLY**: existing local
  test use only; no CI artifacts, external providers, redistribution, or public
  benchmark manifests. Secret scanning does not authorize sensitive publication.
- Tests use sanitized synthetic fixtures and temporary directories. Evaluation
  inputs require sanitized relative references and explicit privacy classification;
  private/uncertain inputs stay out of cloud CI and provider comparisons.
- Ground truth must be provenance-backed; otherwise report it as unavailable.
  Do not manufacture ground truth, provenance, or evidence. Do not turn heuristic
  or source-specific scores into probability confidence; report unavailable
  confidence when semantics are indefensible.

## Validation, review, and authority

- Validate narrowly first: focused checks, affected integration, then applicable
  static checks. Docs-only tasks use lightweight checks, not expensive regression
  solely for docs. Preserve [TESTING.md](TESTING.md) and executable CI contracts.
- Root regression: `python -m unittest discover -s . -p "test_*.py"`.
  Authoritative merge gates remain GitHub Actions: Windows/Ubuntu unittest,
  Ruff syntax, Gitleaks, and ratcheted bounded Pyright; whole-repo Pyright is advisory.
- Do not weaken behavior/tests for a pass. Report exact evidence and unrun checks;
  update status/traceability claims only after underlying evidence is verified.
- For significant closure, use an independent verifier when practical, with
  **PASS**, **PASS WITH NOTES**, or **FAIL**; see the runbook. CI outranks confidence.
- Use a dedicated non-default branch. Branches, commits, pushes, PRs, comments,
  and CI changes require authorization covering the bounded action. Stage exact
  paths only. Task-specific restrictions override default workflow suggestions.
  Implementation alone does not authorize commit, push, or PR creation; see
  [action authority](docs/agent-ops/CONTRACT.md#default-authority).
- The owner retains architecture, privacy/evidence decisions, and final merge
  authority. Require explicit human authorization for each PR merge and current
  passing blocking gates; never merge stale, incomplete, cancelled, or failed gates.
  Use the current PR head SHA when possible. No force-push, destructive history
  rewrite, release, or tag without explicit authorization.

## Stop and report

Stop for architecture contradiction, security/privacy/provenance risk, scope
expansion, validation failure not safely resolvable in scope, blocking review
finding, exceeded authority, or the budget rules above. Report the blocker and
smallest next decision; do not improvise around it.

At closure, report scope/files, checks and results, CI status, review findings,
risks/deferred work, commit/PR state, and remaining manual acceptance. Do not
hard-code a repository-wide test total; use the latest authoritative CI evidence.

## Task-specific references (load only when relevant)

- [Frozen persistence spec](docs/architecture/durable-persistence.md), SHA-256
  `A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4`
- [Recovery matrix](docs/DESKTOP_PACKAGE_IMPORT_RECOVERY_MATRIX.md)
- [Recovery invariants](docs/DESKTOP_PACKAGE_IMPORT_RECOVERY_INVARIANTS.md)
- [Traceability](docs/architecture/durable-persistence-traceability.md)
- [Tool evaluation](docs/AI_TOOL_EVALUATION.md)
