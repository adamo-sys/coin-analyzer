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
- an Electron/web rewrite;
- broad visual redesign;
- automated screenshot approval infrastructure;
- cloud services;
- analytics;
- design-system dependencies;
- new product features.

## Current desktop interaction model

Coin Analyzer remains a native Python/Tkinter desktop application.

The current menu hierarchy is organized into bounded functional groups:

### Tools

#### Session & Data

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

#### Collection Intelligence

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

#### OCR & AI

- OCR Experiment
- OCR-Assisted Identification
- AI Grading Assistant
- Smart Phone Cataloguer

#### Mobile & Sync

- Mobile Collection Entry
- Collector Workflow Integration
- Collector Cloud Foundation
- Sync & Backup
- Multi-Device Workspace
- Device Linking & Conflict Resolution
- Mobile Collector Companion
- Phone Photo Capture

#### Market & Deal Tools

- Deal Hunter Ranking
- Deal Hunter Calibration
- External Listing Connectors
- Live Deal Hunter
- Live Source Validation
- Live Deal Hunter Readiness
- Market Intelligence
- Market Intelligence Automation
- Watchlists & Alerts

#### Platform & Diagnostics

- Platform Management
- Platform Analytics
- Field Test & Tuning
- Batch Processing

### Help

- Collector Companion Readiness

## UX invariants

Future desktop changes should preserve the following unless an explicit product decision supersedes them:

1. Top-level menu actions remain discoverable through stable functional groupings.
2. Collector Companion Readiness appears only under Help.
3. Session/data actions remain separated from analysis/intelligence actions.
4. OCR/AI actions remain visibly distinct from deterministic collection-management operations.
5. Optional live/cloud/provider actions must not become prerequisites for core local collection management.
6. Menu changes must remain covered by deterministic regression tests.
7. Native Windows/Tkinter smoke validation remains required for GUI-sensitive release work.
8. GUI changes must not weaken provenance, privacy, or explicit-review boundaries around OCR/AI output.

## Keyboard and accessibility baseline

Tkinter accessibility support is limited compared with modern browser-native accessibility stacks, so the project uses a pragmatic desktop baseline rather than claiming formal WCAG compliance.

For future GUI work:

- important actions should remain reachable through standard menu keyboard navigation;
- focus order should not be intentionally broken;
- dialogs should retain clear labels and explicit confirmation/cancellation paths;
- destructive operations should not become single-keystroke actions without confirmation;
- keyboard shortcuts should not conflict with common platform conventions;
- menu labels should remain concise and distinguishable;
- accessibility claims should remain limited to behavior actually tested.

## Visual-regression position

The project is not adding screenshot-diff infrastructure at this stage.

Reasons:

- Tkinter rendering can vary across Windows/Tcl/Tk versions and DPI settings;
- screenshot baselines can become noisy without stable rendering infrastructure;
- current deterministic navigation tests provide higher signal for the maintenance burden.

If a future GUI regression cannot be captured through deterministic state/navigation tests, a small screenshot fixture may be introduced for that specific workflow only.

## Highest-value workflow for future UX work

The preferred workflow for any future targeted UX improvement is the OCR-assisted import/review path because it combines:

- file selection;
- imported capture-package state;
- OCR-assisted interpretation;
- explicit human review;
- persistence boundaries;
- privacy/provenance constraints.

Any redesign of that workflow should begin with a bounded mockup or acceptance-criteria document before implementation.

## Current findings

### Strengths

- menu grouping is now explicit and regression-tested;
- local collection-management functionality remains distinct from optional provider/cloud behavior;
- OCR/AI functionality remains advisory;
- protected-branch and regression gates reduce accidental GUI churn;
- the project already has a repeatable native Windows validation path.

### Risks to watch

- Tkinter exposes fewer built-in accessibility semantics than browser-native UI frameworks;
- very large menus can still create discoverability friction;
- future feature additions could reintroduce duplicate or poorly grouped menu actions;
- keyboard behavior can regress without deliberate focus/binding tests;
- screenshot comparison would be noisy unless rendering conditions are tightly controlled.

## Maintenance-mode rule

After this baseline is merged and release-quality validation is green, Coin Analyzer should enter maintenance mode.

New GUI work should require one of:

- a reproducible bug;
- observed user friction;
- useful external feedback;
- a security/privacy issue;
- a clearly justified feature with a concrete use case.

Tool adoption, framework experimentation, or visual redesign by itself is not sufficient justification.

## Definition of done

This baseline slice is complete when:

- this document is merged;
- existing menu/navigation regression tests remain green;
- any added focused navigation invariant is deterministic;
- bounded Pyright remains clean;
- the full regression suite passes;
- no production architecture or product behavior is changed;
- the repository is ready for a final maintenance release decision.