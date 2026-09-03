# Agent Workflow: Guarded Architecture-First Development

## Purpose

This document defines the operating procedure for AI-assisted development in
`coin-analyzer`. It keeps production changes architecture-first while allowing
larger, bounded implementation work packages when the scope, invariants, tests,
and stop conditions are explicit.

Typical invocation:

> "Continue the current Coin Analyzer work. Inspect the repository, follow
> AGENTS.md, complete the next bounded work package, validate it, and report
> changed files, tests, risks, and stop conditions."

## Operating Model

### Roles

- **User / repository owner**: owns product direction, architecture decisions,
  privacy/evidence decisions, and merge authority unless explicit scoped
  authorization is given for a specific PR or bounded task.
- **Primary implementation agent (normally Codex)**: implements bounded vertical
  slices, runs focused validation, and reports scope/test/risk evidence.
- **Independent reviewer (when used)**: reviews against the frozen architecture,
  invariants, tests, and diff without silently broadening scope.
- **GitHub Actions**: authoritative automated gate for repository CI.

The implementation agent and independent reviewer should be separated where
practical. CI evidence outranks agent confidence.

## Core Principles

### 1. Architecture-First Production Changes

Production behavior changes must be supported by the applicable architecture or
contract documentation. If the requested behavior is absent from, or contradicts,
the frozen architecture, the agent must stop and propose the smallest necessary
architecture amendment before changing production behavior.

Documentation, CI, tests, developer tooling, and repository-hygiene changes do
not require an unrelated production architecture amendment, but they must still
preserve project invariants.

### 2. Bounded Vertical Slices, Not Artificially Tiny Prompts

Prefer one substantial, reviewable work package over many microscopic prompts.
A work package may span multiple related files when they form one coherent
vertical slice.

Each work package must define:

- objective and acceptance criteria;
- files/components expected to change;
- explicit invariants and out-of-scope items;
- focused validation plus the required regression/CI gates;
- risks and stop conditions.

Do not mix unrelated cleanup, speculative refactors, or opportunistic feature
work into the same package.

### 3. Inspect Before Editing

Before changing code, the implementation agent should inspect the relevant
repository state and source rather than rely on memory. In a local checkout this
includes `git status`; through remote tooling it includes the current branch/head,
relevant files, PR state, and current CI evidence.

Preserve unrelated local or untracked files. Never infer that an untracked file
is disposable or publishable.

### 4. Validation Ladder

Use the narrowest meaningful validation first, then escalate:

1. focused tests/checks for the changed behavior;
2. affected module/integration tests where applicable;
3. compilation/static checks where applicable;
4. authoritative GitHub Actions regression before merge.

Current blocking repository gates include the Windows/Ubuntu unittest matrix,
Ruff syntax checks, and Gitleaks. Advisory experiments such as Pyright remain
non-blocking until explicitly ratcheted into a bounded blocking gate.

Do not weaken production semantics merely to make a test pass.

### 5. Independent Review Before Significant Closure

Before a significant feature/sprint is considered complete, perform an
independent review when practical. Review should verify:

- architecture/contract alignment;
- state-transition and invariant correctness;
- edge cases and fail-closed behavior;
- privacy, provenance, licensing, and evidence boundaries;
- test coverage and whether the selected tests actually prove the claim;
- unnecessary churn or scope expansion.

Review conclusion: **PASS**, **PASS WITH NOTES**, or **FAIL**.

### 6. Documentation Follows Verified Reality

Update traceability, project state, recovery matrices, portfolio claims, and
other status documents only after the underlying implementation or CI evidence
is verified.

Do not overstate benchmark completion, confidence semantics, corpus readiness,
or test results. Prefer exact evidence over promotional wording.

### 7. Repository Mutation and Authority

Default rule: the user retains merge authority.

The agent may create branches, commits, pushes, PRs, comments, and CI-supporting
changes only when the user has authorized that bounded work. Authorization can
be explicit for one action or can cover a clearly scoped work package.

For merges:

- do not merge a PR with failing, cancelled, stale, or incomplete blocking gates;
- use the current PR head SHA when possible to prevent stale merges;
- merge only when the user has explicitly authorized that PR or has clearly
  granted standing merge authority for that specific bounded task;
- never infer indefinite authority for unrelated future PRs from an earlier
  approval.

No force-pushes, destructive history rewrites, releases, or tags without explicit
user authorization.

### 8. Private Data and Protected Local Files

- Never inspect, commit, upload, or migrate collection backups, exports, live
  collection records, collector notes, credentials, or private photographs
  unless the user explicitly authorizes the exact material and operation.
- Collection backups and exports remain outside source control. Tests use
  sanitized synthetic fixtures and temporary directories.
- The ten JPEGs under `test_coins/` are **UNCERTAIN / LOCAL-ONLY**. They may
  support their existing local test role but must not be uploaded to CI artifacts
  or external providers, redistributed, or promoted into public benchmark
  manifests.
- Secret scanning is defense in depth, not permission to commit sensitive data.

### 9. Recognition and Evaluation Boundaries

- Recognition and evaluation outputs are advisory; they do not own collection
  persistence, confirmed observations, or collector decisions.
- Do not convert heuristic or source-specific scores into generic probability
  confidence. Use unavailable confidence when semantics are not defensible.
- Ground truth must be provenance-backed. Never manufacture labels to satisfy a
  schema, benchmark, or test.
- Evaluation inputs use sanitized relative references and explicit privacy
  classification. Private or uncertain inputs do not enter cloud CI or provider
  comparisons.

### 10. Reporting Discipline

Every completed implementation work package should report, as applicable:

- objective and scope completed;
- changed files and why;
- focused tests/checks and results;
- authoritative CI/regression status;
- review findings;
- known risks and deferred work;
- commit/PR status;
- whether any manual validation remains (for example native Tk acceptance).

Avoid hard-coding a repository-wide expected test total in this file. The latest
successful authoritative CI run is the source of truth because the suite grows
as work is merged.

## Stop Conditions

Stop and report rather than improvising when any of the following occurs:

1. **Architecture contradiction** — implementation requires behavior outside or
   inconsistent with the frozen specification.
2. **Security/privacy/provenance issue** — a change risks secrets, private data,
   unauthorized evidence, or a fail-open boundary.
3. **Scope expansion** — a prerequisite or unrelated change would broaden the
   approved work package.
4. **Failed validation** — focused or authoritative blocking checks fail and the
   cause cannot be safely resolved within the bounded task.
5. **Blocking review finding** — review discovers a substantive correctness,
   architecture, or evidence-boundary discrepancy.
6. **Authority boundary** — the next mutation would exceed the user's explicit
   or clearly scoped authorization.

## Validation Commands

### Focused examples

```bash
python -m unittest tests.test_durable_persistence_contracts
python -m unittest tests.test_durable_persistence_services
python -m unittest tests.test_capture_package_recovery_matrix
python -m unittest tests.test_capture_package_execution
python -m unittest tests.test_capture_package_durability
python -m unittest tests.test_capture_import_lock
python -m unittest tests.test_capture_import_snapshot
python -m unittest tests.test_workflow_models
python -m unittest tests.test_workflow_pipeline
python -m unittest tests.test_workflow_execution
python -m unittest tests.test_workflow_workspace
python -m unittest tests.test_workflow_integration
python -m unittest tests.test_workflow_reference_stages
```

### Full regression

```bash
python -m unittest discover -s . -p "test_*.py"
```

Root discovery remains the authoritative Python regression command. GitHub
Actions additionally supplies the cross-platform and repository-quality gates.
See `TESTING.md` and `.github/workflows/` for the current executable CI contract.

## Project-Specific Invariants

- Frozen spec: `docs/architecture/durable-persistence.md` at SHA-256
  `A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4`
- Recovery matrix: `docs/DESKTOP_PACKAGE_IMPORT_RECOVERY_MATRIX.md`
- Recovery invariants: `docs/DESKTOP_PACKAGE_IMPORT_RECOVERY_INVARIANTS.md`
- Traceability: `docs/architecture/durable-persistence-traceability.md`
- Tool evaluation: `docs/AI_TOOL_EVALUATION.md`

## Practical Default

For normal Coin Analyzer work, use this sequence:

1. inspect current state;
2. define one bounded vertical slice and acceptance criteria;
3. implement the slice;
4. run focused validation;
5. run/await authoritative CI;
6. perform independent review when the change is significant;
7. report changed files, tests, risks, and deferred work;
8. merge only within the user's explicit scoped authority.
