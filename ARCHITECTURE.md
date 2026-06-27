# ARCHITECTURE.md

# Coin Analyzer – Architecture

## Purpose

This document explains how Coin Analyzer is organized and how new features should fit into the existing system.

Coin Analyzer is a desktop-first collection intelligence platform. Its architecture is built around reusable engines, deterministic analysis, and clear separation between business logic, workflow orchestration, and user interface.

---

# Architectural Rule

Business logic belongs in engines.

The GUI should orchestrate engines and display results.

The GUI should not own collection logic, acquisition logic, grading logic, matching logic, export logic, or roadmap logic.

---

# System Overview

Coin Analyzer is organized into several layers:

1. Data Layer
2. Intelligence Engines
3. Workflow Engines
4. Integration Engines
5. Export Layer
6. GUI Layer
7. Documentation and Release Layer

Each layer should remain focused on its own responsibility.

---

# 1. Data Layer

The data layer stores and represents collection information.

Primary responsibilities:

* coin item records
* collection storage
* imported data
* Numista fields
* workbook and CSV compatibility
* persistent collection state

Typical modules may include:

* `coin_collection.py`
* collection workbook loaders
* Numista import utilities
* portfolio import utilities

Rules:

* Data models should remain stable whenever possible.
* New fields should be additive and backward-compatible.
* Data models should not contain large amounts of business logic.
* Importers should parse and normalize data, not make collection decisions.

---

# 2. Intelligence Engines

Intelligence engines analyze collection data and produce deterministic conclusions.

Examples:

* Collection Intelligence
* Focused Collection Intelligence
* Platform Analytics
* Collection Insights
* Acquisition Strategy
* Numista Intelligence
* Portfolio Performance
* Opportunity Engine
* Ranking Engine
* Deal Hunter

Responsibilities:

* ownership detection
* duplicate detection
* upgrade analysis
* collection gap analysis
* acquisition priority
* value and performance summaries
* Numista-backed matching
* deterministic recommendations

Rules:

* Engines own business logic.
* Engines should be reusable outside the GUI.
* Engines should be testable without launching the desktop app.
* Engines should return structured results, not raw GUI text.
* Engines should not mutate collection data unless explicitly designed to do so.
* Engines should prefer deterministic scoring over probabilistic output.

---

# 3. Workflow Engines

Workflow engines coordinate multi-step user tasks.

Examples:

* Collection Assistant
* Mobile Collector Companion
* Mobile Collection Entry
* Workflow Integration
* Smart Phone Cataloguer

Responsibilities:

* guide the user through a process
* combine outputs from multiple engines
* create review objects
* enforce confirmation before collection mutation
* preserve preview-only workflows when appropriate

Rules:

* Workflow engines orchestrate business engines.
* They should not duplicate the business logic of those engines.
* They should produce reviewable outputs.
* User confirmation is required before adding, editing, or deleting collection data.

---

# 4. Integration Engines

Integration engines connect separate subsystems.

Examples:

* Collector Cloud
* Sync and Backup
* Multi-Device Workspace
* Device Linking
* Numista integration
* future phone image ingestion
* future external data connectors

Responsibilities:

* move data between systems
* prepare data for existing engines
* manage local/offline synchronization concepts
* support future connected workflows

Rules:

* Integration engines should remain modular.
* They should not replace core collection logic.
* Connected features should extend the desktop collection engine.
* Offline deterministic behavior should remain available wherever practical.

---

# 5. Export Layer

Exports convert structured results into user-facing files.

Examples:

* CSV exports
* Markdown reports
* release reports
* analytics summaries
* acquisition reports
* Numista reports

Rules:

* Export logic should be reusable.
* Avoid duplicate CSV or Markdown formatting code.
* Engines should expose structured data that exporters can consume.
* GUI code should call exporters rather than formatting large reports inline where practical.

---

# 6. GUI Layer

The GUI is the desktop user interface.

Responsibilities:

* display collection data
* launch tools
* collect user inputs
* show reports
* offer export buttons
* guide review workflows

Rules:

* GUI code should be thin.
* GUI code should call engines.
* GUI code should not duplicate engine logic.
* GUI integration should be minimal and consistent with existing patterns.
* New tools should be added using existing menu/dialog patterns unless a larger UI redesign is explicitly planned.

Known technical debt:

* The engine architecture is more advanced than parts of the desktop GUI.
* A future Unified Collector Workspace should consolidate major tools into a cleaner interface.

---

# Core Data Flow

The long-term collection workflow is:

Photo or import

↓

OCR / import parser

↓

Collection Assistant

↓

Numista Intelligence

↓

Collection Intelligence

↓

Acquisition Strategy

↓

Review workflow

↓

User confirmation

↓

Collection update

No automatic collection mutation should occur without explicit user approval.

---

# v8.x Direction

The v8.x roadmap introduces mobile-assisted cataloguing.

The intended architecture is:

Phone image

↓

Desktop intake

↓

OCR identification

↓

Collection Assistant

↓

Numista Intelligence

↓

Collection Intelligence

↓

Acquisition Strategy

↓

Review screen

↓

One-click confirmed import

Existing v7.x engines should be reused wherever possible.

The phone workflow should sit on top of the desktop intelligence platform, not replace it.

---

# Module Responsibility Rules

Before creating a new module, ask:

1. Does an existing engine already do this?
2. Can the existing engine be extended cleanly?
3. Is this business logic, workflow logic, integration logic, export logic, or GUI logic?
4. Will this duplicate data models or calculations?
5. Can this be tested independently?

Create a new module only when:

* the responsibility is clearly distinct
* reuse would make the existing module less clear
* the new module has a narrow, testable purpose

---

# Importer Rules

Importers parse and normalize external data.

Importers should not:

* make acquisition decisions
* score collection priority
* determine upgrade strategy
* mutate the collection automatically
* own intelligence logic

For example:

* `NumistaImporter` imports Numista data.
* `NumistaIntelligence` analyzes Numista data.

---

# Engine Rules

Engines should:

* accept explicit inputs
* return structured outputs
* avoid hidden global state
* be unit-testable
* be deterministic by default
* avoid GUI dependencies
* avoid network dependencies unless explicitly required

Engines should not:

* show message boxes
* depend on Tkinter
* perform unrelated file writes
* silently mutate collection state
* duplicate another engine's scoring rules

---

# GUI Rules

GUI methods may:

* collect user choices
* call engines
* show summaries
* open dialogs
* save exported reports

GUI methods should not:

* implement scoring algorithms
* implement duplicate detection
* implement acquisition logic
* implement Numista matching
* implement portfolio calculations

If a GUI method starts becoming large, move the business logic into an engine.

---

# Testing Architecture

Each new engine requires:

* direct unit tests
* edge case tests
* export tests if applicable
* integration tests with adjacent engines where appropriate

Each release requires:

* targeted tests for new functionality
* adjacent subsystem tests
* full regression suite

Test count should not decrease without a documented reason.

---

# Release Architecture

Each release should follow this structure:

1. Planning / roadmap lock
2. Implementation
3. Tests
4. GUI integration if applicable
5. Documentation
6. Audit
7. Tag
8. Push
9. Verify remote refs

If interrupted, resume from the latest committed phase.

Do not restart completed work.

---

# Current Architectural Priorities

As of the transition into v8.0, the main priorities are:

1. Preserve deterministic desktop engines.
2. Add mobile-assisted workflows on top of existing engines.
3. Avoid duplicating collection intelligence.
4. Keep GUI changes minimal unless a UI modernization release is planned.
5. Improve documentation and release discipline.
6. Maintain explainable outputs.
7. Require user confirmation before collection mutation.

---

# Long-Term Architecture Goal

Coin Analyzer should become a modular collector platform where each major capability is independent, testable, and reusable.

The ideal structure is:

Data models

↓

Importers and OCR

↓

Intelligence engines

↓

Workflow engines

↓

GUI and exports

↓

User-confirmed collection updates

This architecture should allow future mobile, cloud, marketplace, and AI-assisted features to plug into the existing desktop intelligence platform without replacing it.
