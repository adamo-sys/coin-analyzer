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
