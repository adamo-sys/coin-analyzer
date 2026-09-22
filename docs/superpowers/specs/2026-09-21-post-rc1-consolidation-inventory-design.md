# Post-RC1 consolidation inventory design

## Status and objective

This design defines one bounded, local-only foundation improvement for the
post-RC1 consolidation pass: a deterministic worktree inventory in the existing
`tools/task-state.py` preflight utility. Its purpose is to make future repository
archaeology and branch-selection safer without performing consolidation.

The verified implementation base is `main` at
`d388542fda7e034a2edc946cd1f9b5017c067d1e`. The RC1 evidence-extraction repair
is preserved remotely by open PR #288 at
`520d5d888b6b27d451abcf49db196ce7eb4b1308`; this slice neither alters that
branch nor its pull request.

## Decision

Extend the existing read-only task-state utility instead of building a separate
Command Center feature or adopting another repository-management platform.
The command will observe each registered worktree relative to a caller-supplied
base revision and return stable structured data suitable for a human-written
consolidation report.

It will not decide whether a worktree, branch, or stash is disposable. Human
review remains required for every disposition and any later mutation.

## Interface

Add an `inventory` subcommand to `tools/task-state.py`:

```text
python -B tools/task-state.py inventory --repo . --base main --format json
```

Supported formats are the utility's existing JSON and Markdown outputs. The
command accepts a repository path and a base revision. It obtains data only via
bounded Git inspection commands. A bad repository, unresolved base, malformed
Git output, or failed inspection is an error; it must not guess at state.

Each worktree record contains only:

- registered path;
- HEAD object ID;
- local branch name or a detached marker;
- tracked-change presence (untracked files are intentionally excluded);
- relationship to the selected base, expressed as whether HEAD is already
  contained by the base and the count of commits reachable from HEAD but not the
  base.

The report labels these as observations, never as authority to remove or retain
anything. Stashes and remote PR state remain outside this command because their
disposition and network evidence require separate explicit review.

## Data flow and safety

1. Validate the supplied repository and base with the same fail-closed command
   runner used by preflight.
2. Read `git worktree list --porcelain` and parse only its documented records.
3. For each registered worktree, read tracked status with
   `git status --porcelain --untracked-files=no`, determine base containment,
   and count unique commits.
4. Emit ordered, deterministic JSON or Markdown.

No command receives mutation arguments. The implementation must not invoke
`worktree remove`, `branch -d`, `stash drop`, cleanup, fetch, or network access.
Paths are reported as Git returned them; no untrusted path is opened or copied.

## Tests and validation

Synthetic temporary repositories will prove normal branch/detached records,
tracked-dirty detection, merged-versus-ahead observations, stable output, and
fail-closed behavior for invalid input or malformed worktree metadata. Tests may
create and remove their own temporary Git repositories only; they must not touch
registered project worktrees.

The implementation validation is limited to focused task-state tests, applicable
Ruff and bounded Pyright checks, and `git diff --check`. A final independent,
read-only review assesses scope, correctness, and the no-mutation boundary.

## Reversibility and exclusions

The slice adds an optional developer command and documentation only. Removing
the command later does not alter repository or user data. It introduces no
runtime dependency, CI requirement, remote service, collection behavior, or
Command Center integration.
