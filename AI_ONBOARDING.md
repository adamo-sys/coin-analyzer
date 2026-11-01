## Document Authority — governance versus factual evidence

Applicable higher-level safety restrictions, authorized task instructions, `AGENTS.md`, `docs/agent-ops/CONTRACT.md`, adopted amendments and stricter project safety rules govern permissions, protected boundaries, stop conditions, validation and publication. A lower-priority task instruction, source code, project-state record or historical handoff cannot grant authority or waive a governing requirement. Apply the stricter compatible boundary; stop the affected action and report any unresolved contradiction for authorized disposition.

For factual claims about implemented behavior or project status, verify the claim against current authenticated source code, commit identity, applicable test evidence and relevant records. Historical handoffs and release documents establish only their dated observations; prompts and chat summaries do not substitute for primary evidence.

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

At task start, read `AGENTS.md`, this onboarding guide, and the applicable mandatory contract and runbook entry points. Determine the task class and load additional original evidence and documents required by that task or governing contract; context packs are navigation aids, not waivers. A release task must still inspect the complete applicable release documentation and perform all mandatory release checks.

Before substantive work, verify repository identity, actual branch, exact HEAD, task-authorized base and relevant tracked state by permitted read-only methods. For release tasks, also verify current version, latest release tag, release in progress, clean/dirty state and documentation completeness using appropriate current evidence. Do not broaden discovery into protected or unrelated data. If a required observation is unavailable or mismatched, report it and stop the dependent action. Do not assume; verify.

This selective-loading procedure becomes effective only after explicit approval and adoption; until then the existing startup requirements remain controlling. This paragraph grants no new execution, editing, publication or merge authority.

---

# Source Of Truth — factual claims only

The repository supplies evidence about implementation and recorded project state, not authorization. Authenticate the relevant source and revision, assess test coverage and freshness, and report unresolved factual discrepancies. Do not treat copied prompts, project-state summaries or historical handoffs as substitutes for original evidence. Governance conflicts are resolved under the Document Authority rule above, not by a factual-source ranking.

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

1. Verify the current branch, exact HEAD, task-authorized base,
   tracked working-tree state, and relevant handoff against the
   current repository evidence.

2. Read the governing instructions and task-relevant source documents.
   Apply the selective startup procedure in "Before Doing Anything".
   Do not require unrelated onboarding or release documents solely
   because work is being resumed.

3. For release-related recovery, inspect the applicable release state,
   release documentation, tags, audit status, and mandatory release
   checks. Do not relax any release safeguard.

4. Resume from existing verified implementation and evidence.
   Do not restart completed work without a documented reason.

If required state is ambiguous or inconsistent, STOP and report
the smallest unresolved prerequisite. Do not modify the repository
until the relevant state is understood.

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
