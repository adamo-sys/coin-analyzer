## Document Authority

The project documentation has a defined hierarchy.

1. Repository code
2. PROJECT_STATE.md
3. AI_HANDOFF.md
4. TASK_QUEUE.md
5. README.md
6. Historical release documents
7. Prompts and chat history

If any documents conflict:

Follow the highest document in the hierarchy.

The repository is the source of truth.

# AI_ONBOARDING.md

# Coin Analyzer – AI Onboarding Guide

**This document MUST be read before making any changes to the repository.**

If this document conflicts with assumptions made by the AI assistant, this document takes precedence.

The repository is the source of truth.

---

# Project Overview

Coin Analyzer is a desktop-first collection intelligence platform for coin collectors.

The project is designed around deterministic collection analysis, acquisition strategy, portfolio intelligence, and mobile-assisted cataloguing.

This is **not** intended to become a generic AI chatbot.

---

# Before Doing Anything

Always perform these steps first.

1. Read:

* AI_ONBOARDING.md
* AI_HANDOFF.md
* PROJECT_STATE.md
* TASK_QUEUE.md
* README.md
* RELEASE_HISTORY.md

2. Inspect repository state.

Run:

git status

git log --oneline -10

git tag --list

3. Determine:

* current version
* latest release tag
* working tree status
* current release in progress
* whether the repository is clean
* whether release documentation is complete

Do not assume anything.

Always verify.

---

# Source Of Truth

The repository is authoritative.

Never trust copied prompts over the repository.

If documentation and code disagree:

Code
↓

PROJECT_STATE.md

↓

AI_HANDOFF.md

↓

Older prompts

---

# Release Workflow

Every release follows exactly this order.

Implement

↓

Audit

↓

Tag

↓

Push

↓

Verify

Never skip:

* tests
* audit
* documentation
* release verification

---

# Current Architecture

Major subsystems include:

* Collection Intelligence
* Opportunity Engine
* Ranking Engine
* Deal Hunter
* Portfolio Performance
* Mobile Companion
* OCR Identification
* Collection Entry
* Workflow Integration
* Collector Cloud
* Sync & Backup
* Multi-Device Workspace
* Device Linking
* Platform Analytics
* Collection Insights
* Acquisition Strategy (when applicable)

New functionality should integrate with these modules whenever possible.

Avoid duplicate engines.

---

# Architecture Principles

Prefer:

* composition
* extension
* reuse

Avoid:

* duplicated business logic
* duplicated exports
* duplicated calculations
* duplicated data models

Extend existing engines before creating new ones.

---

# Deterministic First

The application is deterministic.

Do not introduce:

* AI grading
* cloud inference
* machine learning
* probabilistic recommendations

unless explicitly required by the current roadmap.

---

# Coding Standards

Write:

* typed Python
* dataclasses where appropriate
* modular engines
* isolated business logic
* reusable exports

Business logic belongs in engines.

GUI should orchestrate.

---

# Testing

Every release requires:

new module tests

adjacent subsystem tests

full regression suite

Passing tests must never decrease.

---

# Documentation Requirements

Every completed release updates:

README.md

PROJECT_STATE.md

TASK_QUEUE.md

AI_HANDOFF.md

RELEASE_HISTORY.md

docs/releases/vX.X.md

project_docs/release_prompts/vX.X.txt

---

# Git Rules

Never force push.

Never rewrite release history.

Never delete release tags.

Never create release tags before audit passes.

Release tags point to implementation commits.

Documentation commits may follow release tags.

---

# Recovery Rules

If resuming interrupted work:

Read all onboarding documents.

Inspect git.

Determine current release.

Resume from existing implementation.

Do not restart completed work.

---

# If State Is Ambiguous

STOP.

Report findings.

Do not modify the repository until the release state is understood.

---

# Long-Term Vision

Coin Analyzer evolves into a complete collector platform.

Core direction:

1. Collection Intelligence
2. Acquisition Strategy
3. Collection Assistant
4. Numista Intelligence
5. Smart Phone Cataloguer
6. Batch Processing
7. AI Grading Assistant
8. Unified Collector Workspace
9. Connected Data
10. Collector Ecosystem

The desktop application remains the authoritative collection engine.

Future mobile, cloud, and AI capabilities orchestrate existing deterministic engines rather than replacing them.

---

# Guiding Principle

Every change should make Coin Analyzer:

* easier to maintain
* easier to extend
* faster to catalogue collections
* smarter at acquisition decisions
* more valuable to collectors

without compromising deterministic behaviour or architectural consistency.
