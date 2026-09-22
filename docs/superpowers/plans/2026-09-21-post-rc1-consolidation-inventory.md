# Post-RC1 Consolidation Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic local-only task-state inventory command that reports registered-worktree facts without disposition decisions or Git mutation.

**Architecture:** Add an `inventory` command path to `tools/task-state.py`, reusing its bounded Git runner and generic report renderer. It parses `git worktree list --porcelain`, reports base relationships from local Git refs, and has no Command Center, runtime, network, or persistence integration.

**Tech Stack:** Python 3.12+, stdlib `argparse`, `subprocess`, and `unittest`; local Git.

**Spec:** `docs/superpowers/specs/2026-09-21-post-rc1-consolidation-inventory-design.md`

## Global Constraints

- Read-only, deterministic, local-only, factual.
- Never assign PRESERVE, UNFINISHED, DISPOSABLE, or another disposition.
- Never invoke Git mutation, network, fetch, cleanup, deletion, or Command Center code.
- Never emit untracked paths, remote URLs, private data, or Git stderr.
- Fail closed with `PreflightError` on malformed/unavailable Git observations.
- Do not add dependencies, CI, runtime, Recognition30, or collection behavior.
- Do not stage, commit, push, or create a pull request.

## Review Focus

- An ahead linked worktree reports only its factual relation, never value.
- A detached worktree remains visible with a null branch.
- Dirty state is a boolean and never reveals changed filenames.
- Missing base or malformed porcelain produces controlled error output.
- Git calls remain bounded read-only calls, plus `worktree list`.

## File Structure

- `tools/task-state.py`: inventory parser, inspection, and CLI dispatch.
- `tests/test_task_state.py`: synthetic repository acceptance and no-mutation tests.
- `docs/CODEX_WORKFLOW.md`: invocation and non-authority documentation.
- `docs/POST_RC1_CONSOLIDATION_POKEMON_REPORT_2026_09_21.md`: factual report and exactly one next package.

### Task 1: Write inventory acceptance tests

**Files:** Modify `tests/test_task_state.py`.

**Interfaces:** Produces tests for `task_state.main(['inventory', '--repo', REPO, '--base', BASE, '--format', 'json'])`.

- [ ] Add `invoke_inventory()` alongside the existing preflight helper.
- [ ] Create synthetic linked feature and detached worktrees. Commit one feature-only change and write one tracked dirty change in the feature worktree.
- [ ] Add `test_inventory_reports_sorted_factual_worktree_state` asserting operation `inventory`; paths sorted; the feature has `head_contained_by_base == False`, `unique_commits_vs_base == 1`, and `tracked_dirty == True`; and detached has `branch is None` and base HEAD.
- [ ] Run `.\.venv\Scripts\python.exe -m unittest tests.test_task_state.PreflightTests.test_inventory_reports_sorted_factual_worktree_state`; expect failure because inventory is absent.
- [ ] Add `test_inventory_rejects_missing_base` expecting controlled exit code 3 and JSON error.
- [ ] Add `test_inventory_uses_only_bounded_read_only_git_commands`. Snapshot synthetic files, wrap `task_state.subprocess.run`, run inventory, compare the snapshot, and accept only `rev-parse`, `worktree`, `status`, and `rev-list`; assert `GIT_OPTIONAL_LOCKS=0` and `GIT_NO_LAZY_FETCH=1` on every call.
- [ ] Run the two new tests; expect failure because inventory does not exist.

### Task 2: Implement the minimal inventory contract

**Files:** Modify `tools/task-state.py`; test `tests/test_task_state.py`.

**Interfaces:** Produces `worktree_records(raw: str) -> list[dict[str, str | None]]` and `inventory(args: argparse.Namespace) -> dict[str, Any]`.

- [ ] Implement `worktree_records()`. Parse blank-line-delimited porcelain records; require exactly one `worktree ` and `HEAD ` line; permit one `branch refs/heads/` line or `detached`; reject unknown/missing/duplicate required metadata with `PreflightError('Git returned invalid worktree metadata.', 3)`; normalize local branch names and sort by path.
- [ ] Resolve repository root and `--base` through `Git.ref()`. If absent, raise `PreflightError('Inventory base revision is unavailable.', 3)`.
- [ ] For each registered worktree, use `Git(Path(path))`; run only `status --porcelain=v1 -z --untracked-files=no --no-renames` and relationship inspection. Emit only `path`, `head`, `branch`, `tracked_dirty`, `head_contained_by_base`, and `unique_commits_vs_base`; relationship fields are null for shallow history.
- [ ] Return schema version 1 with operation `inventory`, repository root/identity/base/shallow fields, sorted worktrees, and evidence fields `remote_freshness: unverified_local_ref_only`, `validation: not_run`, `ci: unverified`, and `authority: observations_only`.
- [ ] Add parser arguments `inventory --repo . --base REQUIRED --format {markdown,json}`. Dispatch it without loading preflight configuration; preserve preflight behavior. Controlled errors retain the selected operation.
- [ ] Run `.\.venv\Scripts\python.exe -m unittest tests.test_task_state`; expect pass.

### Task 3: Document the interface and report the post-RC1 evidence

**Files:** Modify `docs/CODEX_WORKFLOW.md`; create `docs/POST_RC1_CONSOLIDATION_POKEMON_REPORT_2026_09_21.md`.

**Interfaces:** Consumes Task 2 stable report fields. Produces operator guidance and a durable evidence report that grants no authority.

- [ ] Document `python -B tools/task-state.py inventory --repo . --base main --format json`.
- [ ] State that relationships use local refs only, dirty status is tracked-only, shallow relationships are unavailable, and output cannot classify or authorize worktree/branch/stash removal.
- [ ] Write the report's four sections: consolidation map; dependency-ordered candidate backlog; tonight's implementation with actually-run validation evidence; and exactly one next package.
- [ ] Include RC1 preservation facts, all registered worktree/stash observations, a non-destructive sequence, deduplicated candidates, and human disposition authority.
- [ ] Run inventory against the canonical checkout and `git diff --check`; expect both to pass.

### Task 4: Validate and prepare independent review

**Files:** Verify `tools/task-state.py`, `tests/test_task_state.py`, `docs/CODEX_WORKFLOW.md`, and the post-RC1 report.

- [ ] Run `.\.venv\Scripts\python.exe -m unittest tests.test_task_state`.
- [ ] Run `.\.venv\Scripts\python.exe -m ruff check tools/task-state.py tests/test_task_state.py --select E9`.
- [ ] Run `.\.venv\Scripts\python.exe -m pyright tools/task-state.py tests/test_task_state.py`.
- [ ] Run `git diff --check`; stop and diagnose any failure without weakening tests or scope.
- [ ] Inspect `git status --short --untracked-files=no`, `git diff --stat`, and the bounded diff. Confirm only declared files plus the spec/plan changed.
- [ ] Request an independent read-only review of mutation resistance, factual semantics, porcelain parsing, deterministic output, test coverage, and scope. Record PASS, PASS WITH NOTES, or FAIL.
- [ ] Stop without staging, commit, push, PR, merge, release, deletion, or a second candidate.
