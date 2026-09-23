# Codex Efficiency Foundation — Slice 1

Deterministic preflight answers task-start repository questions locally so an
operator can identify stale handoffs, unexpected edits, and already-merged work
before beginning an agent session. It does not measure or promise quota savings.

## Authority and scope

[AGENTS.md](../AGENTS.md), the [task contract](agent-ops/CONTRACT.md),
[runbook](agent-ops/RUNBOOK.md), [standards](agent-ops/STANDARDS.md), and
[testing guidance](../TESTING.md) remain authoritative. Preflight observations
grant no execution, branch, commit, publication, merge, or release authority.
Current blocking CI and explicit human approval still control merges.

Slice 1 provides configuration, repository inspection, Markdown output, and JSON
output. Validation execution/evidence storage, handoff persistence, model
selection, quota prediction, scheduling, automatic worktree creation, Git
mutation, and provider/API calls are deferred. The tool never installs anything,
fetches, runs tests, writes state, or makes a trust exception for a repository.

## Environment and dependency maintenance

Use an existing Python 3.12+ development interpreter with Git and PyYAML installed.
PyYAML is declared only in [requirements-dev.txt](../requirements-dev.txt) and
pinned in [requirements-dev.lock](../requirements-dev.lock). The application
runtime and optional AI dependency declarations are unchanged.

The existing lock mechanism is `uv pip compile`. Regenerate the development lock
with the following command when a dependency change is authorized:

```powershell
uv pip compile requirements-dev.txt -o requirements-dev.lock --no-python-downloads
```

The existing output lock supplies preferred pins; do not use upgrade flags.
Review the lock diff and verify every unrelated pin is unchanged. A dependency
snapshot is not evidence that an environment was installed or CI passed.

## Task definitions

[.ops/tasks.yml](../.ops/tasks.yml) contains policy/configuration, never mutable
execution state. Schema version 1 requires exactly `schema_version`, `guidance`,
`validation_profiles`, `task_classes`, and `protected_paths`. Mapping keys must
be unique strings. Classes reference named profiles with nonempty minimum
requirement lists. Unknown fields, invalid references, and malformed YAML fail.

| Class | Minimum validation plan (not executed by preflight) |
| --- | --- |
| documentation | Whitespace and relevant local links |
| tests | Changed unittest modules, affected regressions, applicable static checks |
| tooling | Synthetic tool tests, entry-point smoke checks, applicable Ruff E9 and bounded Pyright |
| production | Focused behavior, affected integration/regression, static checks and required CI |

Select a class explicitly. For a mixed task, inspect each applicable class and
combine requirements under the existing six-field contract. No class reduces
repository merge gates or authorizes an operation. Protected patterns add to a
fixed minimum boundary; a custom config cannot disable that minimum. Patterns
match path components and prefixes, case-insensitively. This is a conservative
guardrail, not a complete classifier of sensitive data: the operator must still
name only paths authorized for inspection.

## Invoke preflight

Run from the worktree you intend to inspect. Windows entry point:

```powershell
$env:COIN_TASK_PYTHON = 'C:\path\to\existing\development\python.exe'
.\tools\task-preflight.ps1 --task-class tooling --expect-branch codex/example --require-clean
```

Portable entry point, with exact expected HEAD supplied by your task handoff:

```text
python -B tools/task-state.py preflight --task-class tooling --expect-head FULL_COMMIT_SHA --format json
```

Add `--repo PATH` to inspect another explicitly selected repository. Defaults:
current directory for `--repo`, the tool's adjacent `.ops/tasks.yml` for config,
and Markdown for format. `--config PATH` explicitly selects another policy
configuration; it must be nonprotected and must not traverse links or junctions.
The wrapper forwards all arguments, stdout, stderr, and Python's exit code.

Optional literal-file checks:

```text
python -B tools/task-state.py preflight --task-class tooling --candidate-branch codex/example --expect-path tools/task-state.py --scope-path tools/task-state.py --scope-path tests/test_task_state.py --format json
```

- Repeat `--expect-path` for files which must exist. It does not authorize
  creation. Missing files produce a blocking mismatch.
- Repeat `--scope-path` for the exact allowed file set. Changes outside this set
  and expected filenames outside it produce blocking mismatches. If omitted,
  scope compliance is unavailable rather than assumed.
- Paths must be portable, literal, repository-relative file names. Traversal,
  wildcards, Git pathspec syntax, Windows alias/device names, protected paths,
  symlinks, and junctions are rejected. Directories are not recursively inspected.
- `--candidate-branch` observes an existing or proposed local branch. A missing
  candidate is reported without treating it as an error. No branch is created.
- `--require-clean` requires clean **tracked** state; it cannot certify a wholly
  empty untracked namespace.

## Inventory registered worktrees

Use the separate inventory command when a human needs factual consolidation
evidence for every worktree registered by the selected local repository:

```text
python -B tools/task-state.py inventory --repo . --base main --format json
```

The command reports registered path, branch or detached state, HEAD,
tracked-dirty presence, and local ancestry/count observations relative to the
selected base. It uses only local refs: it never fetches, reads a remote URL,
or establishes remote freshness. Dirty state excludes untracked files and never
prints changed filenames. In shallow repositories, base-relationship fields are
unavailable rather than guessed.

Inventory output is observation-only. It does not classify a worktree, branch,
or stash as preserveable, unfinished, merged, or disposable; does not assess
equivalence after squash/cherry-pick; and never authorizes deletion, cleanup,
branch changes, stash changes, or another Git mutation. A human must review the
reported evidence before making any disposition decision.

## Output and evidence semantics

Markdown presents labeled sections containing literal observations. JSON emits
one object with deterministic key ordering, no timestamps, and `schema_version: 1`.
Successful observations have `repository`, `relationships`, `working_tree`,
`paths`, `blocked_path_count`, `candidate`, `task`, `mismatches`, and `evidence`
fields in addition to the schema version and operation. A controlled failure
has `error` and `exit_code` instead. CLI syntax errors use argparse's stderr.

- Repository identity is the local worktree root. Remote URLs are not read or
  printed because they may contain credentials.
- HEAD, local `main`, and **recorded** `origin/main` are separate observations.
  No fetch occurs; remote freshness is always unverified by this command.
- Relationships count commits unique to the left (`ahead`) and right (`behind`).
  Missing refs or shallow history yield `null`, not fabricated zero counts.
- Candidate merged status is ancestry relative to local `main`. Squash/cherry-pick
  equivalence is not inferred. Unique commits do not prove unique functionality.
- `head_equals_main` compares the committed Git object and mode for an exact
  named path in HEAD versus local `main`. It does **not** compare unstaged content
  or certify task completion. Missing objects yield `null`.
- Staged/unstaged counts come from tracked status; a file may count in both.
  The tool neither prints those filenames nor reads their contents directly.
  Git's own tracked-status operation can refresh its in-memory stat information;
  optional Git index writes and filesystem-monitor hooks are disabled.
- Untracked counts cover only explicitly named, nonprotected, existing files.
  Unrelated untracked and ignored files are not enumerated. `untracked_total`
  stays `null`. Protected requests are counted but their names are omitted.
- Historical test reports remain reported/unverified evidence. This tool always
  reports validation `not_run`, CI `unverified`, and authority `observations_only`.
- Inspections comprise several read-only commands, not an atomic snapshot. Stop
  concurrent edits/ref updates when collecting task-start evidence. Recheck if
  the checkout changes before acting on the report.

## Stable exit codes

| Code | Meaning |
| --- | --- |
| 0 | Inspection completed with no requested-state mismatch |
| 2 | Invalid arguments, path syntax, or malformed/unavailable configuration |
| 3 | Missing prerequisite or failed/timed-out Git/filesystem inspection |
| 4 | Blocking expected-state, scope, or protected-path mismatch |

Zero means neither CI success nor permission to proceed. Detached HEAD is an
observation unless it conflicts with `--expect-branch`. Git ownership/trust
failures are reported without changing configuration or bypassing Git checks.

## Focused validation

From a configured development environment:

```powershell
python -B -m unittest tests.test_task_state
python -m ruff check tools/task-state.py tests/test_task_state.py --select E9
python -m pyright tools/task-state.py tests/test_task_state.py
.\tools\task-preflight.ps1 --task-class tooling --format json
git diff --check
```

Tests create synthetic temporary repositories. They do not use collection data,
photos, the operator's branch layout, or historical validation as ground truth.
Full regression and authoritative remote CI remain separate from this focused
Slice 1 verification. Future validate/handoff work needs its own bounded task.

## Task Packets and Outcome Packets

Task Packets and Outcome Packets are workflow contracts and evidence artifacts.
They are **not** autonomous execution authorization; repository governance and
explicit human authority still control implementation, commits, pushes, pull
requests, and merges.

Use the hand-authorable JSON templates in `.ops/task-packet.template.json` and
`.ops/outcome-packet.template.json`. Their corresponding JSON Schema artifacts
define the required shape. Validate a packet without network or model calls:

```text
python -B tools/task-packet.py validate --kind task --path path/to/task.json
python -B tools/task-packet.py validate --kind outcome --path path/to/outcome.json
```

The intended workflow is:

1. Decide and specify outside Codex where practical.
2. Classify the task before dispatch.
3. Send Codex a bounded Task Packet.
4. Use deterministic tooling and CI to prove the result.
5. Produce an Outcome Packet.
6. Review the outcome before authorizing additional agent work.
7. Future Better Harness experiments may compare workflows using these artifacts.

Outcome usage fields accept observed counts, useful local proxies, or an
explicit unavailable value. They must not be used to invent Codex telemetry.
