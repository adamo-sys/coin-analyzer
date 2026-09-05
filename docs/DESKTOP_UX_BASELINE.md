# Desktop UX Baseline

## Purpose

This document freezes a bounded desktop UX baseline for Coin Analyzer before the project moves toward maintenance mode.

The objective is not to redesign the application. The objective is to record the current desktop interaction model, preserve important navigation invariants, identify obvious keyboard/accessibility risks, and create a stable reference for future bug fixes.

## Scope

The baseline covers:

- the primary Tkinter desktop entry point in `coin_collection_gui.py`;
- top-level menu grouping and command discoverability;
- deterministic menu/navigation regression coverage;
- keyboard-access and focus behavior that can be inspected without broad GUI restructuring;
- current native Windows desktop expectations.

The baseline does not introduce:

- a new GUI framework;
- an Electron or web rewrite;
- broad visual redesign;
- automated screenshot-approval infrastructure;
- cloud services;
- analytics;
- design-system dependencies;
- new product features.

## Current desktop interaction model

Coin Analyzer remains a native Python/Tkinter desktop application.

The current Tools menu is organized into bounded functional groups.

### Session & Data

- Load Collection Context
- Clear Session Context
- Save Session State
- Load Session State
- Clear Session State
- Export Session State
- Import Session State
- Create Backup Package
- List Backups
- Restore Backup
- Create Snapshot

### Collection Intelligence

- Buy Advisor
- Upgrade Advisor
- Want List Generator
- Portfolio Import Preview
- Want List Preview
- Collection Insights
- Acquisition Strategy
- Ask My Collection
- Collection Assistant
- Portfolio Analytics
- Numista Intelligence

### OCR & AI

- OCR Experiment
- OCR-Assisted Identification
- AI Grading Assistant
- Smart Phone Cataloguer

### Mobile & Sync

- Mobile Collection Entry
- Collector Workflow Integration
- Collector Cloud Foundation
- Sync & Backup
- Multi-Device Workspace
- Device Linking & Conflict Resolution
- Mobile Collector Companion
- Phone Photo Capture

### Market & Deal Tools

- Deal Hunter Ranking
- Deal Hunter Calibration
- External Listing Connectors
- Live Deal Hunter
- Live Source Validation
- Live Deal Hunter Readiness
- Market Intelligence
- Market Intelligence Automation
- Watchlists & Alerts

### Platform & Diagnostics

- Platform Management
- Platform Analytics
- Field Test & Tuning
- Batch Processing

### Help

- Collector Companion Readiness

## Existing deterministic navigation coverage

`test_menu_navigation.py` already protects the important navigation structure.

It verifies:

- all six expected Tools submenu groups remain present;
- representative commands remain wired to their existing handlers;
- Collector Companion Readiness appears exactly once and remains under Help;
- existing top-level navigation entries remain present.

This existing coverage is preferred over adding redundant source-text assertions.

## UX invariants

Future desktop changes should preserve the following unless an explicit product decision supersedes them:

1. Top-level menu actions remain discoverable through stable functional groupings.
2. Collector Companion Readiness remains under Help and is not duplicated under Tools.
3. Session/data actions remain separated from analysis/intelligence actions.
4. OCR/AI actions remain visibly distinct from deterministic collection-management operations.
5. Optional live, cloud, or provider actions must not become prerequisites for core local collection management.
6. Menu changes remain covered by deterministic regression tests.
7. Native Windows/Tkinter smoke validation remains required for GUI-sensitive release work.
8. GUI changes must not weaken provenance, privacy, or explicit-review boundaries around OCR/AI output.

## Keyboard and accessibility baseline

Tkinter exposes fewer accessibility semantics than modern browser-native UI stacks, so Coin Analyzer uses a pragmatic desktop baseline rather than claiming formal WCAG compliance.

Future GUI work should preserve these expectations:

- important actions remain reachable through standard menu keyboard navigation;
- focus order is not intentionally broken;
- dialogs use clear labels and explicit confirmation or cancellation paths;
- destructive operations do not become unconfirmed single-keystroke actions;
- keyboard shortcuts do not conflict with common platform conventions;
- menu labels remain concise and distinguishable;
- accessibility claims remain limited to behavior actually tested.

## Visual-regression position

The project is not adding broad screenshot-diff infrastructure at this stage.

Tkinter rendering can vary with:

- Windows version;
- Tcl/Tk version;
- DPI scaling;
- system fonts;
- theme configuration.

Those differences can create visual-regression noise without stable rendering infrastructure.

For the current maintenance boundary, deterministic navigation/state tests provide better signal for the maintenance burden.

A screenshot fixture should be introduced only if a specific future GUI regression cannot be captured through deterministic state or navigation tests.

## Highest-value workflow for future UX work

If future user feedback justifies targeted UX work, the preferred candidate is the OCR-assisted import/review path.

That workflow combines:

- file selection;
- capture-package state;
- OCR-assisted interpretation;
- explicit human review;
- persistence boundaries;
- privacy and provenance constraints.

Any material redesign should begin with frozen acceptance criteria or a bounded mockup before implementation.

## Current findings

### Strengths

- menu grouping is explicit and regression-tested;
- representative commands are tested against their handlers;
- Collector Companion Readiness is protected against duplicate placement;
- local collection-management functionality remains distinct from optional provider/cloud behavior;
- OCR/AI functionality remains advisory;
- protected-branch and regression gates reduce accidental GUI churn;
- a repeatable native Windows validation path exists.

### Risks to watch

- large menus can still create discoverability friction;
- Tkinter provides limited accessibility semantics;
- future feature additions could reintroduce duplicate or poorly grouped actions;
- keyboard/focus behavior can regress without deliberate validation;
- screenshot comparison would remain noisy unless rendering conditions are tightly controlled.

## Maintenance-mode rule

After this baseline is merged and final release-quality validation is green, Coin Analyzer should enter maintenance mode.

New GUI work should require at least one of:

- a reproducible bug;
- observed user friction;
- useful external feedback;
- a security or privacy issue;
- a clearly justified feature with a concrete use case.

Tool adoption, framework experimentation, or visual redesign by itself is not sufficient justification.

## Definition of done

This baseline slice is complete when:

- this document is merged;
- existing menu/navigation regression tests remain green;
- bounded Pyright remains clean;
- the full regression suite passes;
- no production architecture or product behavior changes;
- the repository is ready for a final maintenance-release decision.