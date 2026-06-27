# RELEASE_CHECKLIST.md

# Coin Analyzer Release Checklist

This document defines the required workflow for every official Coin Analyzer release.

No release should skip any step.

---

# Phase 0 — Repository Verification

Before writing any code, verify repository state.

Run:

```
git status
git log --oneline -10
git tag --list
git branch -vv
git fetch --tags
```

Verify:

* correct repository
* correct branch
* current HEAD
* latest release tag
* clean working tree
* local main matches origin/main

If repository state is unclear:

STOP.

Resolve repository state before implementation.

---

# Phase 1 — Roadmap Lock

Update project planning documents.

Required:

* PROJECT_STATE.md
* TASK_QUEUE.md
* AI_HANDOFF.md

Mark:

* current release
* active task
* roadmap status

Commit roadmap changes when appropriate.

---

# Phase 2 — Implementation

Implement the release.

Rules:

* extend existing engines whenever possible
* avoid duplicate business logic
* preserve backwards compatibility
* maintain deterministic behaviour
* keep GUI changes minimal

Commit completed implementation phases.

---

# Phase 3 — Testing

Every release requires:

* unit tests
* edge case tests
* integration tests where appropriate
* full regression suite

Regression count should never decrease without explanation.

No release proceeds with failing tests.

---

# Phase 4 — GUI Integration

If GUI changes are required:

* reuse existing patterns
* avoid duplicate workflows
* avoid business logic in GUI
* call existing engines

Skip this phase if no GUI work is required.

---

# Phase 5 — Documentation

Update:

* README.md
* PROJECT_STATE.md
* TASK_QUEUE.md
* AI_HANDOFF.md
* RELEASE_HISTORY.md
* docs/releases/vX.X.md
* project_docs/release_prompts/vX.X.txt

Documentation is part of the release.

---

# Phase 6 — Release Audit

Verify:

* implementation complete
* tests passing
* documentation updated
* no duplicated logic
* architecture respected
* GUI working
* exports working
* backwards compatibility preserved

If any item fails:

Return to implementation.

---

# Phase 7 — Git Verification

Before tagging:

```
git status
git log --oneline -5
git tag --list
```

Verify:

* clean working tree
* expected commits present
* correct branch

---

# Phase 8 — Tag Release

Create annotated tag.

Example:

```
git tag -a v8.0 -m "Release v8.0"
```

Never use lightweight tags.

---

# Phase 9 — Push

Push branch.

```
git push origin main
```

Push tag.

```
git push origin v8.0
```

---

# Phase 10 — Verify Remote

Verify:

```
git ls-remote origin refs/heads/main
git ls-remote origin refs/tags/v8.0
git ls-remote origin "refs/tags/v8.0^{}"
```

Confirm:

* branch updated
* tag exists
* annotated tag points to expected commit

---

# HOLD Procedure

If work cannot continue because of:

* tool limits
* authentication
* missing repository
* ambiguous project state

STOP.

Produce a HOLD report containing:

* completed phases
* current commit
* working tree status
* tests completed
* remaining work
* exact next action

Resume only after repository state has been verified.

---

# Definition of Done

A release is complete only when it has been:

* planned
* implemented
* tested
* documented
* audited
* tagged
* pushed
* verified
