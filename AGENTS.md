# Coin Analyzer Agent Harness - governance simplification draft

**PROPOSED / NOT ADOPTED.** Owner review is pending. This working copy does not
replace governing policy. Until explicit adoption, the task-authorized baseline
and any independently applicable adopted requirements control; see the
[proposal and authority register](docs/agent-ops/GOVERNANCE_SIMPLIFICATION_PROPOSAL.md).
No execution, disclosure, historical acceptance or publication authority is added.

## Start and scope

- Use the [single workflow](docs/agent-ops/RUNBOOK.md#standard-bounded-change).
  Establish repository identity, branch, exact HEAD and task-authorized base before
  substantive work; stop on mismatch or unresolved expectations. Do not fetch or
  change checkout state to satisfy this gate without authority.
- Reuse a complete [six-field task contract](docs/agent-ops/CONTRACT.md#bounded-task-contract)
  and valid evidence. Read only relevant sources; never turn navigation aids,
  context packs, agent recommendations or an unadopted working copy into policy.
- Preserve unrelated changes. Use `git status --short --untracked-files=no` and
  check only intended new paths separately; never enumerate protected material.
- Use a dedicated non-default branch. Implementation alone does not authorize
  branch creation, commits, pushes, PRs, comments, CI changes or publication.
  Follow [action authority](docs/agent-ops/CONTRACT.md#default-authority).

## Codex context budget

These are repository operating thresholds, not model capacity claims. K = 1,000
tokens of accumulated thread context/work; compaction does not reset this budget.
Use available session accounting; label estimates. If exact session-wide accounting
is unavailable, state that limitation once per session; do not invent a count or
repeatedly restate the limitation. Use session length, tool-call volume, repository
discovery, accumulated history, and task complexity as proxies; prefer earlier
checkpointing when uncertain. When operator confirmation is useful, recommend
`/usage` where available or the visible session-status UI; do not assume it
provides exact session-wide context accounting.
Checkpoint at each bounded work-package boundary and rotate before another
substantive package; genuinely nearly-complete current work may finish only under
the exception below.
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

Before recommending a fresh Codex thread, provide a concise checkpoint containing
the task objective, branch, worktree, exact HEAD and task-authorized base, exact
modified paths, completed validation, unresolved blockers, next authorized action,
publication status, and relevant stop conditions. Use the
[runbook procedure](docs/agent-ops/RUNBOOK.md#checkpoint-and-thread-rotation) for
authorized durable storage or an in-task handoff when storage is not authorized;
checkpointing grants no additional file or publication authority.
After recommending rotation at or beyond the normal hard cap, do not begin a new
substantive subtask in that session.

## Architecture and protected boundaries

- Follow applicable frozen architecture. If production requirements are absent or
  contradictory, stop for the smallest amendment. Docs, tests, CI, tooling and
  hygiene need no unrelated production amendment. Preserve local-first behavior,
  optional network/AI features and advisory recognition/evaluation; collection
  changes require explicit collector intent.
- Never inspect, commit, upload or migrate backups, exports, live records, notes,
  credentials or private photos without authorization for the exact material and
  operation. Backups/exports remain outside source control. Preserve unrelated
  files and ignored private benchmarks; do not investigate `data/imports/`
  permission warnings outside scope. See [SECURITY.md](SECURITY.md).
- The ten `test_coins/` JPEGs remain **UNCERTAIN / LOCAL-ONLY**: existing local test
  use only, no CI artifacts, external providers, redistribution or public benchmark
  manifests. Secret scanning never authorizes sensitive publication.
- Use sanitized synthetic fixtures and temporary directories. Evaluation inputs
  need sanitized relative references and explicit privacy classification; private
  or uncertain inputs stay out of cloud CI and provider comparisons.
- Ground truth must be provenance-backed; otherwise report it as unavailable.
- Never invent ground truth, provenance, evidence or probability confidence from
  heuristic/source-specific scores. Report unavailable values truthfully.

## Validation, review, and authority

Use the [engineering risk tiers](docs/agent-ops/CONTRACT.md#engineering-risk-tiers)
and [review procedure](docs/agent-ops/RUNBOOK.md#independent-verifier--adversarial-review).
Validate narrowly; documentation alone needs lightweight checks. Preserve
[TESTING.md](TESTING.md), executable CI contracts and all applicable security gates.
Report failures, uncertainty and unrun checks; never weaken tests for a pass.
Current blocking GitHub CI and explicit human authorization for each PR control
merges. Never merge stale, failed, incomplete or cancelled gates. No force-push,
history rewrite, release or tag without explicit authority. Stage exact paths only.

## Stop and report

Stop the affected activity for architecture contradiction, security/privacy/
provenance risk, scope expansion, unresolved blocking review findings, validation
failure not safely resolvable in scope, exceeded authority or budget limits.
Apply any broader binding stop. Independent authorized work may proceed only when
its dependency separation is established; see [blocker handling](docs/agent-ops/CONTRACT.md#finite-investigation-and-blocker-handling).
Report the smallest next action and the [concise closure record](docs/agent-ops/RUNBOOK.md#standard-bounded-change).

## Task-specific references (load only when relevant)

[CONTRACT.md](docs/agent-ops/CONTRACT.md#specialized-contracts-and-references)
indexes frozen and specialized contracts. [STANDARDS.md](docs/agent-ops/STANDARDS.md)
retains detailed engineering and security-review standards.
