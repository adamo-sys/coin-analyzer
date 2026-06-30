# Release Governance

**Status:** Permanent  
**Scope:** All future releases (v8.2+)  
**Last Updated:** 2026-06-29

---

# Purpose

This document defines the standard release engineering workflow for the Coin Analyzer project.

The objective is to ensure that every release is:

- reproducible
- auditable
- deterministic
- recoverable
- fully verified before publication

This workflow should be followed exactly unless explicitly superseded.

---

# Core Principles

## GitHub is the Source of Truth

The Git repository is the authoritative source for the project.

Temporary AI workspaces are disposable.

No work is considered durable until it has been:

1. committed
2. pushed
3. verified on GitHub

---

## Favor Reuse Over Invention

Extend existing engines before introducing new modules.

New orchestration layers should remain thin.

Avoid duplicating business logic already implemented elsewhere.

---

## Thin Orchestration

Workflow modules coordinate existing engines.

They should not reimplement:

- OCR
- Collection Intelligence
- Deal Hunter
- Photo Capture
- Review workflows

---

# Repository Authority & HOLD Policy

The Git repository is the **sole source of truth**.

A HOLD report is **informational only**.

It must never become the authoritative source for repository contents.

If tool access is lost before commit or push:

- do **not** reconstruct repository files from memory
- do **not** recreate repository files from HOLD reports
- do **not** synthesize documentation

Instead:

1. restore a clean repository checkout
2. re-read the actual repository files
3. apply changes directly to those files

---

## Released Versions

Released versions must always reference:

- actual release commit
- actual release tag

Never use placeholder values such as:

```
PENDING
TBD
UNKNOWN
```

for released versions.

If the correct commit or tag cannot be verified from the repository:

**STOP with a HOLD report.**

Wait until repository access is restored.

---

# Standard Release Lifecycle

```
Phase 0 — Roadmap Lock
        ↓
RELEASE GATE
        ↓
Phase 1 — Core Engine
        ↓
Phase 2 — Integration
        ↓
Phase 3 — Integration
        ↓
Phase 4 — Workflow
        ↓
Phase 5 — GUI
        ↓
Phase 6 — Release
        ↓
Publish
```

---

# RELEASE GATE

Implementation may not begin until all checks pass.

Required:

- Phase 0 committed
- Phase 0 pushed
- Working tree clean
- Remote verified
- Governance documents synchronized

Only then may Phase 1 begin.

---

# Phase 0 Required Files

Every release must update or create:

- PROJECT_STATE.md
- AI_HANDOFF.md
- TASK_QUEUE.md
- RELEASE_HISTORY.md
- docs/releases/vX.Y.md
- project_docs/release_prompts/vX.Y.txt
- vX.Y_implementation_plan.md

Optional:

- README.md

---

# Version Convention

During development:

| Field | Example |
|------|---------|
| Current Release | v8.1 |
| Next Planned Release | v8.2 |
| Active Development Target | v8.2 |

After release:

| Field | Example |
|------|---------|
| Current Release | v8.2 |
| Next Planned Release | v8.3 |
| Active Development Target | v8.3 |

---

# Recovery Protocol

Recovery priority is fixed.

## 1. Preferred

Modify the repository directly.

Run tests.

Commit.

Push.

Verify.

---

## 2. Patch Recovery

Generate:

```bash
git format-patch BASE..HEAD --stdout > release.patch
```

Apply with:

```bash
git am < release.patch
```

---

## 3. ZIP Recovery

If a patch cannot be generated or applied:

Provide a ZIP containing **only the changed files**.

---

## 4. HOLD

If neither repository edits, patch generation, nor ZIP generation are possible:

STOP.

Produce a HOLD report.

Do not continue implementation.

---

# Manual Editing Policy

Do **not** ask the user to manually edit repository files.

Manual editing is an emergency recovery option only.

It must never be recommended unless the user explicitly requests it.

---

# Release Verification

Every release must end with:

```bash
git status
git log --oneline -3
git ls-remote origin refs/heads/main
git ls-remote origin refs/tags/vX.Y
git ls-remote origin "refs/tags/vX.Y^{}"
```

The release is complete only when:

- local repository matches remote
- release tag exists remotely
- working tree is clean

---

# Design Philosophy

The project favors:

- deterministic behaviour
- explainable outputs
- reproducible builds
- comprehensive testing
- minimal architectural change
- small commits
- reusable engines

Every release should improve capability while preserving stability.

---

# Amendment Policy

This document is intended to be stable.

Changes should be:

- rare
- intentional
- justified by a demonstrated process failure

Do not modify this workflow during an active release unless explicitly instructed.

When in doubt:

**Follow this document.**