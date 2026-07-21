# Agent Workflow: Architecture-First Development

## Purpose

This document establishes the operating procedure for implementing features in the
coin-analyzer project. Future prompts may reference this file directly:

> "Continue Sprint N. Inspect the repository. Follow AGENTS.md. Complete the next
> implementation unit."

## Core Principles

### 1. Architecture-First Development

Every implementation begins with the frozen architecture specification.
No production code changes without a corresponding architecture section.
If the desired behavior is absent from the spec, the agent must:
- Halt implementation
- Propose an architecture amendment
- Await explicit authorization before proceeding

### 2. One Bounded Implementation Unit Per Prompt

Each turn addresses exactly one scoped unit of work:
- A single method or function
- A focused test suite addition
- A documentation update synchronized with verified code

The agent must state the unit's boundaries at the start and confirm completion
at the end. No scope creep within a single prompt.

### 3. Repository Inspection Before Coding

Before writing or modifying code, the agent must:
1. List the current working directory state (`git status`)
2. Identify which files are tracked, modified, or untracked
3. Read relevant existing source files, not infer from memory
4. Understand the current test baseline

### 4. Focused Validation After Each Unit

Every implementation unit must be validated with the narrowest possible test
command before proceeding:
- New code → run the new tests
- Bug fix → run the failing test, then the full module
- Refactor → run the affected module, then the integration suite

The agent reports test results explicitly: pass count, skip count, failure count.

### 5. Independent Implementation Review Before Sprint Closure

Before a sprint is considered complete, the agent performs an independent review:
- Review implementation against the frozen architecture
- Verify transition correctness, invariants, and edge cases
- Identify gaps between code and spec
- State review conclusion explicitly (pass / pass with notes / fail)

No sprint is closed without this review.

### 6. Documentation Synchronized After Verification

Traceability matrices, recovery matrices, and architecture docs are updated
only after code is verified:
- Status changes from `IMPLEMENTED` → `VERIFIED` only after passing tests
- Test counts and commands are updated to match reality
- Documentation edits are separate from code edits in the work log

### 7. No Commits, Pushes, or Releases Without Explicit Authorization

The agent never:
- Commits to the repository
- Pushes to a remote
- Creates release artifacts
- Merges pull requests
- Tags releases

The agent may prepare commit messages, tag suggestions, and release notes.
The user retains sole authority over repository mutations.

## Stop Conditions

The agent must halt and await direction when any of the following occur:

1. **Architecture Contradiction**
   - The implementation cannot satisfy the frozen spec without amendment.
   - The spec contains an internal inconsistency.

2. **Security Issue**
   - The proposed change weakens identity, ownership, or durability guarantees.
   - A test reveals a fail-open condition where the spec requires fail-closed.

3. **Scope Expansion**
   - The user request exceeds the current sprint's boundaries.
   - A prerequisite task is discovered mid-implementation.

4. **Failed Validation**
   - Tests fail after a code change.
   - The agent cannot determine why a test fails within reasonable effort.

5. **Blocking Review Finding**
   - The independent review identifies a substantive discrepancy.
   - A model validation gap or edge case is found that requires user judgment.

## Sprint Lifecycle

```
Sprint Start
    │
    ▼
┌─────────────────┐
│ Inspect repo    │ ◄── git status, read relevant files
│ Read AGENTS.md  │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Implement unit  │ ◄── One bounded change per prompt
│ Validate focused│ ◄── Run narrowest test command
└─────────────────┘
    │
    ▼
┌─────────────────┐     ┌─────────────────┐
│ More units?     │──Yes──► Repeat
│                 │
│                 │──No───► Independent review
└─────────────────┘     └─────────────────┘
                            │
                            ▼
                    ┌─────────────────┐
                    │ Review passed?  │──No──► Halt, report findings
                    │                 │
                    │                 │──Yes──► Update docs
                    └─────────────────┘     │
                                              ▼
                                    ┌─────────────────┐
                                    │ Update matrix   │
                                    │ Full regression │
                                    └─────────────────┘
                                          │
                                          ▼
                                    ┌─────────────────┐
                                    │ Release gate    │
                                    │ Await commit    │
                                    │ authorization   │
                                    └─────────────────┘
```

## Traceability Vocabulary

| Status | Meaning |
|--------|---------|
| `PLANNED` | Identified in architecture, no code exists yet |
| `IMPLEMENTED` | Code written, tests may not yet pass |
| `VERIFIED` | Code passes focused and regression tests |
| `PENDING` | Validation not yet run |
| `BLOCKED` | Cannot proceed; reason documented |

## Validation Commands

### Focused (per-module)
```bash
python -m unittest tests.test_durable_persistence_contracts
python -m unittest tests.test_durable_persistence_services
python -m unittest tests.test_capture_package_recovery_matrix
python -m unittest tests.test_capture_package_execution
python -m unittest tests.test_capture_package_durability
python -m unittest tests.test_capture_import_lock
python -m unittest tests.test_capture_import_snapshot
```

### Full Regression
```bash
python -m unittest discover -s tests -p 'test_capture_*.py'
```

Expected baseline: 194 tests pass, 13 skipped (POSIX-specific).

## Project-Specific Invariants

- Frozen spec: `docs/architecture/durable-persistence.md` at SHA-256
  `A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4`
- Recovery matrix: `docs/DESKTOP_PACKAGE_IMPORT_RECOVERY_MATRIX.md`
- Recovery invariants: `docs/DESKTOP_PACKAGE_IMPORT_RECOVERY_INVARIANTS.md`
- Traceability: `docs/architecture/durable-persistence-traceability.md`
