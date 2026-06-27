# DEVELOPMENT_GUIDELINES.md

# Coin Analyzer – Development Guidelines

## Purpose

This document defines the coding standards and development practices for Coin Analyzer.

The goal is to keep the codebase maintainable, reusable, deterministic, and easy to extend.

---

# Core Rule

Prefer extending existing code over creating new code.

Every new module increases long-term maintenance.

Only create new modules when the responsibility is clearly distinct.

---

# Code Style

Code should be:

* readable
* deterministic
* modular
* testable
* well named

Prefer clarity over cleverness.

Future contributors should be able to understand a module without reading unrelated files.

---

# Naming

Use descriptive names.

Examples:

Good:

```python
CollectionIntelligenceEngine
NumistaIntelligenceEngine
AcquisitionStrategyEngine
```

Avoid vague names:

```python
Helper
Utils
Manager
Processor
Thing
Stuff
```

Classes should describe responsibilities.

Methods should describe actions.

---

# Module Responsibilities

Each module should have one primary responsibility.

Examples:

Importers

* parse files
* normalize data

Engines

* analyze
* score
* compare
* classify

Workflow modules

* coordinate engines
* guide users

GUI modules

* collect input
* display output

Export modules

* write CSV
* write Markdown
* generate reports

Do not mix these responsibilities.

---

# Business Logic

Business rules belong inside engines.

Business rules should never be duplicated.

GUI code should never own:

* acquisition scoring
* duplicate detection
* collection intelligence
* Numista matching
* grading rules

---

# Deterministic Behaviour

Prefer deterministic algorithms.

Avoid hidden randomness.

Avoid behavior that changes between runs without explanation.

If confidence scoring is used, the scoring rules should be visible and explainable.

---

# Reuse Before Rewrite

Before writing new code ask:

1. Does this already exist?
2. Can an existing engine be extended?
3. Can this be reused?

Avoid rewriting working systems.

---

# Imports

Only import what is required.

Avoid circular dependencies.

Large dependency chains should be simplified whenever practical.

---

# Testing

Every new engine requires tests.

Test:

* normal cases
* edge cases
* invalid input
* empty input

Regression count should grow over time.

---

# Documentation

Every new feature updates:

* README.md
* PROJECT_STATE.md
* TASK_QUEUE.md
* AI_HANDOFF.md

Major releases also update:

* RELEASE_HISTORY.md
* docs/releases/
* release prompts

Documentation is part of development.

---

# Commits

Commit logical units of work.

Examples:

* implementation
* tests
* GUI integration
* documentation

Avoid mixing unrelated work into one commit.

Write clear commit messages.

---

# Error Handling

Fail safely.

Return useful error messages.

Never silently ignore unexpected failures.

---

# Performance

Optimize only when necessary.

Correctness is more important than speed.

Readability is more important than micro-optimizations.

---

# AI Development

AI contributors should:

* inspect existing architecture first
* reuse existing engines
* avoid duplicate business logic
* keep implementations deterministic
* explain architectural decisions when introducing new modules

When uncertain:

Stop.

Inspect the repository.

Do not guess.

---

# Definition of Good Code

Good code is:

* understandable
* reusable
* testable
* deterministic
* documented
* maintainable

Good code makes the next release easier than the previous one.

Every release should improve both the software and the architecture.
