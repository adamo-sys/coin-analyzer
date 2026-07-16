# Engineering Playbook

This handbook defines the normal contribution workflow for Coin Analyzer. Scale the ceremony to the risk, but do not skip verification.

## Sprint Workflow

1. Inspect the repository, relevant architecture, persistence paths, tests, and current worktree.
2. Search for existing concepts before adding fields, models, engines, or UI patterns.
3. Write a concise plan naming affected files, compatibility strategy, risks, and test approach.
4. Obtain approval when scope or architecture is material, or when the requested workflow establishes an approval gate.
5. Implement the smallest coherent change and preserve unrelated worktree changes.
6. Run focused tests, relevant integration or GUI tests, the complete suite, and `git diff --check`.
7. Review the final diff and stop at any required pre-commit gate.
8. Commit with a focused message only after approval; push or publish only when explicitly authorized.

## Approval Gates

Stop for human review before:

- materially changing persistence or public data formats;
- deleting or migrating user data or repository fixtures;
- introducing a new service, dependency, engine, or storage layer;
- broadening scope beyond approved acceptance criteria;
- committing when the requested workflow requires staged-diff approval;
- pushing, tagging, or publishing a release.

Report the proposed choice, evidence, tradeoffs, affected files, and rollback or compatibility strategy.

## Code Review Checklist

- Does the change solve the stated problem without unrelated features?
- Were existing names, models, and behaviors reused where appropriate?
- Is business logic kept out of the GUI and thin orchestration layers?
- Are failure modes safe and errors actionable?
- Are collection data, local paths, credentials, and generated artifacts excluded?
- Is old persisted or imported data still accepted?
- Are tests deterministic and isolated from live data?
- Does the diff contain only the intended files?

## Testing Requirements

Every behavior change needs focused regression coverage. Include normal, blank, boundary, and invalid cases appropriate to the risk. Persistence changes also require old-record and save/reload coverage.

Run:

```bash
python -m unittest discover -s . -p "test_*.py"
git diff --check
```

Also run targeted modules during development and `git diff --cached --check` before an approved commit. Tests use temporary directories and must never read or mutate live `data/collection.json`. See [`../TESTING.md`](../TESTING.md).

## Documentation Expectations

Update documentation when a change affects installation, user workflows, persistence, public APIs, architecture, or roadmap status. Keep durable principles in `docs/`; keep active work in issues or short implementation plans; keep release history in `docs/releases/`.

Documentation must distinguish:

- implemented behavior;
- approved but unimplemented work;
- exploratory ideas.

Do not commit personal career plans, private collection records, local paths, or transient AI handoff prose as project guidance.

## Architecture Decision Records

Create an ADR in [`adr/`](adr/) for a decision that is costly to reverse, affects multiple features, or establishes a lasting constraint.

Use this structure:

- status and date;
- context;
- decision;
- consequences and tradeoffs;
- conditions that would justify reconsideration.

ADRs record decisions, not sprint plans. Supersede an ADR with a new ADR rather than silently rewriting history.

## Commit Messages

Use an imperative, scoped summary. Conventional prefixes are encouraged:

- `feat:` user-facing capability;
- `fix:` defect or regression;
- `test:` test-only change;
- `docs:` documentation-only change;
- `refactor:` behavior-preserving restructuring;
- `chore:` maintenance or repository hygiene.

Keep commits focused. Do not mix generated artifacts, personal runtime data, cleanup, and feature implementation.

## Release Checklist

Before a release:

- confirm the intended commits and version scope;
- run focused, integration, GUI, and complete regression tests as applicable;
- complete manual acceptance checks that automation cannot cover;
- update user, architecture, roadmap, and release documentation as needed;
- run both worktree and staged diff checks;
- verify no local data or unrelated changes are included;
- create and verify the release tag only after explicit approval;
- push only when authorized.

The detailed existing process remains in [`../RELEASE_CHECKLIST.md`](../RELEASE_CHECKLIST.md). Coding conventions remain in [`../DEVELOPMENT_GUIDELINES.md`](../DEVELOPMENT_GUIDELINES.md).
