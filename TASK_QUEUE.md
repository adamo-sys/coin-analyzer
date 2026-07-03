# Task Queue

## v8.5 Collector Advisor

Status: Complete — v8.5 Released

### Phase 0 — Roadmap Lock
- [x] Create docs/releases/v8.5.md
- [x] Create project_docs/release_prompts/v8.5.txt
- [x] Create v8.5_implementation_plan.md
- [x] Update PROJECT_STATE.md
- [x] Update AI_HANDOFF.md
- [x] Update TASK_QUEUE.md (this file)
- [x] Update RELEASE_HISTORY.md
- [x] Commit Phase 0
- [x] Push Phase 0
- [x] Pass RELEASE GATE

### Phase 1 — Core Engine
- [x] Design collector_advisor.py public API
- [x] Implement CollectorAdvisor
- [x] Implement AdvisorRecommendation, AdvisorReport, AdvisorCategory
- [x] Unit tests for public API (43 tests)

### Phase 2 — Workspace Integration
- [x] Integrate AdvisorReport into CollectorWorkspace
- [x] Implement get_advisor() with lazy engine initialization
- [x] Integration tests (11 new tests)

### Phase 3 — GUI Integration
- [x] Add Advisor tab to coin_collection_gui.py
- [x] Implement advisor display and controls
- [x] GUI tests (3 new tests)

### Phase 4 — Signal Quality Fixes
- [x] Freeze recommendation categories (BUY_NOW, BUY_IF_PRICE_RIGHT, WATCH, NEGOTIATE, PASS, REVIEW)
- [x] Implement deterministic ordering
- [x] Upstream signal hardening

### Phase 5 — Infrastructure
- [x] Add requirements.txt (core dependencies)
- [x] Add requirements-dev.txt (development tools)
- [x] Add requirements-ocr.txt (optional OCR)
- [x] Add requirements-gui.txt (GUI support)
- [x] Add setup_dev.ps1 bootstrap script
- [x] Add DEPENDENCIES.md documentation
- [x] Update .gitignore with comprehensive exclusions
- [x] Update GitHub Actions workflow (Python 3.12)
- [x] Fix CI test brittleness (3 tests)
- [x] Clean-install verification (1261 tests pass)

### Phase 6 — Release
- [x] Final regression (1261 tests)
- [x] Metadata updates (PROJECT_STATE.md, AI_HANDOFF.md, TASK_QUEUE.md)
- [x] Finalize docs/releases/v8.5.md
- [x] Update RELEASE_HISTORY.md
- [x] Tag v8.5
- [x] Commit and push
- [x] Publish

## v8.1 Batch Processing

Status: Complete — v8.1 Released

### Phase 0 — Roadmap Lock
- [x] Create docs/releases/v8.1.md
- [x] Create project_docs/release_prompts/v8.1.txt
- [x] Create v8.1_implementation_plan.md
- [x] Update PROJECT_STATE.md
- [x] Update AI_HANDOFF.md
- [x] Update TASK_QUEUE.md (this file)
- [x] Update RELEASE_HISTORY.md
- [x] Commit Phase 0
- [x] Push Phase 0
- [x] Pass RELEASE GATE

### Phase 1 — Core Engine
- [x] Design batch_processing.py public API
- [x] Implement BatchProcessingEngine
- [x] Implement BatchSource, BatchCandidate, BatchReport, BatchResult
- [x] Unit tests for public API

### Phase 2 — Integration (Photo Capture + OCR)
- [x] Integrate PhotoCaptureWorkflow for batch sessions
- [x] Integrate OCRIdentificationEngine for batch identification
- [x] Handle per-image failures gracefully

### Phase 3 — Integration (Collection Intelligence)
- [x] Integrate Collection Intelligence for batch analysis
- [x] Consolidated duplicate/upgrade/gap reports

### Phase 4 — Workflow
- [x] Batch reporting and export (CSV/Markdown)
- [x] Dashboard integration

### Phase 5 — GUI
- [x] Tools → Batch Processing menu item
- [x] Folder selection dialog
- [x] Progress dialog
- [x] Results review dialog

### Phase 6 — Release
- [x] Final regression (1015 tests)
- [x] Metadata updates
- [x] Tag v8.1
- [x] Commit and push
- [x] Publish

---

## v8.2 AI Grading Assistant

Status: Complete — v8.2 Released

### Phase 0 — Roadmap Lock
- [x] Create docs/releases/v8.2.md
- [x] Create project_docs/release_prompts/v8.2.txt
- [x] Create v8.2_implementation_plan.md
- [x] Update PROJECT_STATE.md
- [x] Update AI_HANDOFF.md
- [x] Update TASK_QUEUE.md (this file)
- [x] Update RELEASE_HISTORY.md
- [x] Commit Phase 0
- [x] Push Phase 0
- [x] Pass RELEASE GATE

### Phase 1 — Core Engine
- [x] Design ai_grading_assistant.py public API
- [x] Implement AIGradingAssistant
- [x] Implement GradingCandidate, GradingAssessment, GradePattern, BatchGradingReport
- [x] Unit tests for public API

### Phase 2 — Integration (Photo Vault + OCR)
- [x] Integrate Photo Vault metadata for grading candidates
- [x] Integrate OCR Identification evidence (optional)
- [x] Handle missing/weak evidence gracefully

### Phase 3 — Integration (Collection Intelligence)
- [x] Integrate Collection Intelligence for grade pattern analysis
- [x] Collection context: duplicate risk, upgrade opportunities, series completion
- [x] Flag candidates outside typical grade range

### Phase 4 — Workflow
- [x] Assessment reporting and export (CSV/Markdown)
- [x] Batch assessment for multiple candidates
- [x] Review flagging and escalation

### Phase 5 — GUI
- [x] Tools → AI Grading Assistant menu item
- [x] Single assessment dialog (form fields, photo reference, evidence display)
- [x] Batch assessment dialog (multi-candidate input, summary, per-candidate results)
- [x] Export buttons (single/batch Markdown and CSV)

### Phase 6 — Release
- [x] Final regression (1047 tests)
- [x] Metadata updates
- [x] Tag v8.2
- [x] Commit and push
- [x] Publish

---

## v8.3 Collector Workspace

Status: Complete — v8.3 Released

### Phase 0 — Roadmap Lock
- [x] Create docs/releases/v8.3.md
- [x] Create project_docs/release_prompts/v8.3.txt
- [x] Create v8.3_implementation_plan.md
- [x] Update PROJECT_STATE.md
- [x] Update AI_HANDOFF.md
- [x] Update TASK_QUEUE.md (this file)
- [x] Update RELEASE_HISTORY.md
- [x] Commit Phase 0
- [x] Push Phase 0
- [x] Pass RELEASE GATE

### Phase 1 — Core Engine
- [x] Design collector_workspace.py public API
- [x] Implement CollectorWorkspace thin aggregation engine
- [x] Implement WorkspacePanel, WorkspaceReport, DashboardReport dataclasses
- [x] Unit tests for public API (19 tests)

### Phase 2 — Panel Aggregation
- [x] Implement get_dashboard() using CollectorHomeDashboard + CollectorOperatingSystem
- [x] Implement get_inbox() using CollectionAssistant + BatchProcessing + AIGradingAssistant
- [x] Implement get_collection_overview() using CollectionIntelligence + CollectionDashboard + CollectionSnapshot
- [x] Implement get_want_list() using CollectionIntelligence + WatchlistEngine + OpportunityEngine
- [x] Implement get_opportunities() using SmartShoppingAssistant + OpportunityEngine + DealHunter
- [x] Implement get_ai_queue() using AIGradingAssistant
- [x] Implement get_batch_queue() using BatchProcessingEngine
- [x] Implement get_photo_vault() using PhotoVault + PhotoVaultIntegrityAudit
- [x] Implement get_workflow_status() using CollectorWorkflowEngine
- [x] Implement get_data_safety() using PersistenceManager + CollectionIntegrityAudit
- [x] Unit tests for each panel (17 tests)

### Phase 3 — Reports Panel
- [x] Implement get_reports() menu/aggregator
- [x] Wire each report to existing engine
- [x] Export support
- [x] Unit tests (24 tests)

### Phase 4 — Refresh & Lifecycle
- [x] Implement refresh() that re-queries all engines
- [x] Implement lazy loading (panels query when activated)
- [x] Implement error handling (panel warning, not crash)
- [x] Unit tests (13 tests)

### Phase 5 — GUI
- [x] Add Collector Workspace menu item
- [x] Implement notebook/tabbed panel layout
- [x] Implement each panel's read-only display
- [x] Implement "Open in [Tool]..." buttons for mutation
- [x] Export buttons for each panel
- [x] Unit tests for GUI wiring (4 tests)

### Phase 6 — Release
- [x] Final regression (1124 tests)
- [x] Metadata updates
- [x] Tag v8.3
- [x] Commit and push
- [x] Publish

---

## v8.4 Connected Data

Status: Phase 0 — Roadmap Lock

### Phase 0 — Roadmap Lock
- [x] Create docs/releases/v8.4.md
- [x] Create project_docs/release_prompts/v8.4.txt
- [x] Create v8.4_implementation_plan.md
- [x] Update PROJECT_STATE.md
- [x] Update AI_HANDOFF.md
- [x] Update TASK_QUEUE.md (this file)
- [x] Update RELEASE_HISTORY.md
- [ ] Commit Phase 0
- [ ] Push Phase 0
- [ ] Pass RELEASE GATE

### Phase 1 — Connected Data Core Engine
- [ ] Design ConnectedContext dataclass
- [ ] Implement ConnectedDataEngine thin facade
- [ ] Implement link_*() methods (photos→grading, OCR→grading, intelligence→shopping, market→acquisition, watchlist→deals, batch→grading)
- [ ] Implement generate_cross_reference_report()
- [ ] Unit tests for core engine

### Phase 2 — Engine Context Enhancements
- [ ] Add keyword-only context params to AIGradingAssistant
- [ ] Add keyword-only context params to SmartShoppingAssistant
- [ ] Add keyword-only context params to AcquisitionWorkflow
- [ ] Add keyword-only context params to DealHunter
- [ ] Add keyword-only context params to BatchProcessingEngine
- [ ] Add keyword-only context params to CollectionAssistant
- [ ] Regression tests for all engine enhancements

### Phase 3 — Workspace Connection Methods
- [ ] Implement get_connected_photos() in CollectorWorkspace
- [ ] Implement get_connected_grading() in CollectorWorkspace
- [ ] Implement get_connected_acquisition() in CollectorWorkspace
- [ ] Implement get_connected_shopping() in CollectorWorkspace
- [ ] Implement get_connected_batch() in CollectorWorkspace
- [ ] Implement get_connected_entry() in CollectorWorkspace
- [ ] Integration tests with real engines

### Phase 4 — Auto-Population & Session Context
- [ ] Auto-load SessionContext on app startup
- [ ] Auto-propagate session context to all engines via ConnectedContext
- [ ] Add "Use Last OCR" / "Use Last Photo" / "Use Last Grading" buttons
- [ ] Add "Import from Want List / Deal Hunter / Intelligence" buttons
- [ ] Add "Link to Grading / Entry" buttons to Batch Processing
- [ ] GUI smoke tests

### Phase 5 — GUI Integration (Connected Panels)
- [ ] Add "Connected Photos" tab to workspace notebook
- [ ] Add "Connected Acquisition" tab to workspace notebook
- [ ] Add "Connected Batch" tab to workspace notebook
- [ ] Implement "Open in Tool..." buttons for connected views
- [ ] Implement connected export buttons (Markdown/CSV)
- [ ] GUI tests for new tabs

### Phase 6 — Release
- [ ] Final regression (1124+ tests)
- [ ] Metadata updates
- [ ] Tag v8.4
- [ ] Commit and push
- [ ] Publish

---

Work through this queue in priority order. Handle only one task at a time.

## Status Legend

- `[ ]` Not Started
- `[-]` In Progress
- `[x]` Complete
- `[!]` Blocked

## Working Rules

1. Work on only one task at a time.
2. After each task, run tests if possible.
3. Summarize changed files after each task.
4. Stop for approval before continuing to the next task.
5. Do not add unrelated features while completing a queued task.
6. When a task is blocked, explain why in the queue or changelog.
7. `TASK_QUEUE.md` and `PROJECT_STATE.md` are the source of truth for project status.
8. Whenever a task is completed:
   - Update `PROJECT_STATE.md`.
   - Update `TASK_QUEUE.md`.
   - Run tests if available.
   - Commit changes.
   - Include the commit hash in `PROJECT_STATE.md` Recent Changes.
9. Every completed version must end with implementation, acceptance audit, tag creation, and push verification.
10. A version is not complete until its release tag exists locally and remotely and both tag targets are verified.
11. Never leave a completed version untagged.

## Queue

1. `[x]` Harden test infrastructure
2. `[x]` Add `run_tests.bat`
3. `[x]` Add `TESTING.md`
4. `[x]` Add GitHub Actions workflow
5. `[x]` Ensure tests use isolated test data
6. `[x]` Implement Collection Gap Report
7. `[x]` Add Markdown export for gap report
8. `[x]` Implement Want List Generator MVP
9. `[ ]` Improve Buy Advisor validation messages
10. `[ ]` Add autocomplete for country/denomination
11. `[x]` Add Auction Evaluator draft spec
12. `[x]` Add legacy portfolio import spec
13. `[x]` Add portfolio integration roadmap
14. `[x]` Implement legacy portfolio staging importer
15. `[x]` Add Portfolio Import Preview GUI
16. `[x]` Build Melt Value Engine
17. `[x]` Build Upgrade Advisor
18. `[x]` Recreate dashboard metrics in app
19. `[x]` Refine Collection Gap Report MVP CSV export
20. `[x]` Perform v0.3 release audit
21. `[x]` Finalize v0.3 release and plan WANT_LIST integration
22. `[x]` Implement legacy WANT_LIST staging integration
23. `[x]` Add WANT_LIST Preview GUI
24. `[x]` Connect staged WANT_LIST intent to Want List Generator
25. `[x]` Connect staged WANT_LIST intent to Buy Advisor
26. `[x]` Perform v0.4 integration audit
27. `[x]` Fix low-priority world base metal Buy Advisor guardrail
28. `[x]` Perform v0.6 release audit
29. `[x]` Perform complete v0.5 release audit rerun
30. `[x]` Build focused Collection Intelligence Engine
31. `[x]` Consolidate advisor decisions on Collection Intelligence Engine
32. `[x]` Integrate WANT_LIST context into Collection Intelligence Engine and Do I Own This
33. `[x]` Build Acquisition Workflow on Collection Intelligence Engine
34. `[x]` Perform v1.0 release-readiness audit
35. `[x]` Complete post-v1.0 release packaging documentation
36. `[x]` Build Shared Session Context
37. `[x]` Build Listing Analyzer
38. `[x]` Perform v1.2 post-release usability documentation audit
39. `[x]` Build v1.3 Collection Dashboard release line
40. `[x]` Build v1.4 Collection Quality Engine
41. `[x]` Build v1.5 Smarter Acquisition Intelligence
42. `[x]` Build v1.6 Series Tracker
43. `[x]` Build v1.7 Photo Vault
44. `[x]` Build v1.8 Market Awareness Layer
45. `[ ]` Improve Buy Advisor validation messages
46. `[ ]` Add autocomplete for country/denomination
47. `[x]` Build v1.9 Smart Shopping Assistant
48. `[x]` Build v2.0 Collector Operating System
49. `[x]` Build v2.1 Persistence Layer
50. `[x]` Build v2.2 Data Safety and Backup Hardening
51. `[x]` Build v2.3 Mobile Readiness
52. `[x]` Build v2.4 Mobile Companion Prototype
53. `[x]` Build v2.4.1 Critical Collection Backup Hardening
54. `[x]` Build v2.4.2 Collection Integrity Audit
55. `[x]` Build v2.4.3 Collection Snapshot System
56. `[x]` Build v2.5 Photo-Assisted Entry
57. `[x]` Build v2.5.1 Photo Vault Hardening
58. `[x]` Build v2.5.2 Shopping Explainability
59. `[x]` Build v2.6 OCR Experiments
60. `[x]` Build v2.6.1 OCR Validation Layer
61. `[x]` Build v2.7 Workflow Integration
62. `[x]` Build v2.8 Collector Home Dashboard
63. `[x]` Build v2.9 Collector Companion Release Candidate
64. `[x]` Build v3.0 Collector Companion
65. `[ ]` Improve Buy Advisor validation messages
66. `[ ]` Add autocomplete for country/denomination
67. `[ ]` Consider storage/file-picker/photo URI adapters before mobile implementation
68. `[x]` Build v3.1 eBay.ca Coin Deal Hunter MVP
69. `[x]` Build v3.2 Deal Hunter Workflow Refinement
70. `[x]` Build v3.3 Opportunity Engine
71. `[x]` Build v3.4 Deal Hunter Ranking Engine
72. `[x]` Build v3.5 External Listing Connectors
73. `[x]` Build v3.6 Deal Hunter Calibration
74. `[x]` Build v3.7 Live Deal Hunter Readiness
75. `[x]` Build v3.8 Market Intelligence
76. `[x]` Build v3.9 Portfolio Performance
77. `[x]` Build v4.0 Live Deal Hunter (Controlled Beta)
78. `[x]` Build v4.1 Live Source Validation
79. `[x]` Build v4.2 Market Intelligence Automation
80. `[x]` Build v4.3 Watchlists & Alerts
81. `[x]` Build v4.4 Live Deal Hunter Field Test & Tuning
82. `[x]` Build v5.0 Mobile Collector Companion
83. `[x]` Build v5.1 Phone Photo Capture
84. `[x]` Build v5.2 OCR-Assisted Identification
85. `[x]` Build v5.3 Mobile Collection Entry
86. `[x]` Build v5.4 Collector Workflow Integration
87. `[x]` Build v6.0 Collector Cloud Foundation
88. `[x]` Build v6.1 Sync & Backup
89. `[x]` Build v6.2 Multi-Device Collector Workspace
90. `[-]` Build v6.3 Device Linking & Conflict Resolution
91. `[x]` Build v7.0 Collector Platform
92. `[x]` Build v7.1 Platform Analytics
93. `[x]` Build v7.2 Collection Insights
94. `[x]` Build v7.3 Acquisition Strategy
95. `[x]` Build v7.4 Collection Assistant
96. `[x]` Build v7.5 Numista Intelligence

## Official v7.4 Roadmap

1. `v7.4` Collection Assistant
2. `[x]` `v7.5` Numista Intelligence
3. `[x]` `v8.0` Smart Phone Cataloguer
4. `[x]` `v8.1` Batch Processing
5. `[x]` `v8.2` AI Grading Assistant
6. `[x]` `v8.3` Collector Workspace (released)
7. `[-]` `v8.4` Connected Data (active planning)
8. `v9.0` Collector Ecosystem

Roadmap rationale: v7.0 established the platform architecture with service registry, plugin system, command framework, event bus, unified models, UI patterns, configuration, and state management. v7.1 added platform analytics for monitoring and insights, measuring every major subsystem using deterministic local data without AI, forecasting, or external APIs. v7.2 added Collection Insights that transform deterministic analytics into explainable, evidence-based observations about the collection, portfolio, workflow, and acquisition strategy. v7.3 added Acquisition Strategy that orchestrates existing collection intelligence, insights, analytics, opportunity scoring, and market intelligence into strategic acquisition plans with phased priorities, portfolio balance guidance, and risk-adjusted recommendations without AI reasoning, forecasting, machine learning, or external APIs. v7.4 adds Collection Assistant that orchestrates existing Photo Capture, OCR Identification, Collection Intelligence, Collection Insights, and Acquisition Strategy engines into a single guided review experience for dramatically reducing manual cataloguing work while preserving user review and approval for every collection change.

Post-v3.8 rationale: the platform can now evaluate opportunities, rank opportunities, explain opportunities, and calibrate recommendations. The next objective is understanding portfolio progress and collection development over time.

v4.0 rationale: v3.x established Collection Intelligence, Deal Hunter, Opportunity Engine, Ranking Engine, Listing Connectors, Calibration, Live Readiness, Market Intelligence, and Portfolio Performance. v4.0 introduces controlled, user-triggered live opportunity discovery while preserving no-purchase, no-bidding, no-background-job, and no-collection-mutation safety rules.

v4.1 rationale: v4.0 introduced live opportunity discovery. v4.1 focuses on trust, validation, reliability, and source quality before live listings enter Deal Hunter, Opportunity Engine, Ranking Engine, or Market Intelligence.

v4.2 rationale: v4.0 introduced live opportunity discovery and v4.1 hardened live source validation. v4.2 automates the connection between live/imported candidates and local Market Intelligence so collectors can understand deal quality faster and with greater consistency.

Clarification: `v3.4` is offline and deterministic. It does not scrape, use browser automation, call eBay APIs, fetch live listings, claim live market-pricing accuracy, predict markets, purchase automatically, recognize images, or mutate collection data.

## Adam-Specific Collection Priorities

Use these priorities when designing gap reports, Buy Advisor changes, acquisition ranking, and evaluator specs.

1. Newfoundland Coinage
   - Date runs
   - Key dates
   - Higher-grade examples
   - 5 cent, 10 cent, 20 cent, and 50 cent focus
2. 1859 Canadian Large Cents
   - Variety attribution
   - Narrow 9 / Wide 9
   - 8 over 9 varieties
   - Date and die variety analysis
   - Upgrade opportunities
3. Canadian Silver Coinage
   - Dimes
   - Quarters
   - Half dollars
   - Dollars
4. Date Run Completion
   - Identify missing years
   - Prioritize easiest completions
   - Calculate completion percentages
5. Upgrade Over Duplicate Strategy
   - Prefer quality upgrades
   - Minimize duplicate purchases
   - Identify replacement candidates
6. Budget-Conscious Acquisitions
   - Maximize value per dollar spent
   - Focus on high-ROI purchases
   - Highlight underpriced opportunities
7. Collection Gap Reduction
   - Generate want lists
   - Rank acquisition targets
   - Recommend highest-impact purchases

## Project Changelog

### 2026-06-23

#### `[x]` Implement v7.0 Collector Platform

- Date started: 2026-06-23
- Date completed: 2026-06-23
- Release commit: `9674de5`.
- Release tag: `v7.0`.
- Features implemented:
  - Service Registry for platform service management
  - Plugin System for extensible architecture
  - Command Framework for structured command execution
  - Event Bus for publish/subscribe communication
  - Unified Data Models for standardized data structures
  - UI Patterns for consistent UI components
  - Platform Configuration for centralized configuration
  - Platform State Management for state persistence
  - Platform Integration for service integration
  - Platform Management GUI tool
- Test results: 768 tests OK.
- Release prompt archived: `project_docs/release_prompts/v7.0.txt`.
- Release documentation: `docs/releases/v7.0.md`.

### 2026-06-23

#### `[x]` Implement v7.1 Platform Analytics

- Date started: 2026-06-23
- Date completed: 2026-06-23
- Release commit: `51be4f3`.
- Release tag: `v7.1`.
- Features implemented:
  - Platform Analytics Engine with deterministic metrics for all major subsystems
  - AnalyticsMetric, AnalyticsTrend, ModuleMetrics, AnalyticsSnapshot dataclasses
  - AnalyticsSummary and PlatformHealthScore with component scores
  - AnalyticsDashboard with snapshot, summary, health score, and trends
  - Collection metrics: total items, countries, denominations, grades, coverage
  - Portfolio metrics: value, cost, gain/loss, silver exposure
  - Workflow metrics: photos, OCR, success rates, completion rates
  - Deal Hunter metrics: listings processed, recommendation rates, risk flags
  - Opportunity Engine metrics: opportunities, high-priority rate
  - Market Intelligence metrics: records, comparable sales
  - Watchlist metrics: watchlists, items, alerts
  - Cloud metrics: snapshots, sync plans
  - Sync & Backup metrics: backups, last backup age, readiness
  - Workspace metrics: devices, snapshots
  - Device Linking metrics: linked devices, conflicts
  - GUI integration: Tools -> Platform Analytics dialog with 4 tabs
  - Export support: Markdown and CSV for snapshots and health scores
- Test results: 786 tests OK (up from 768).
- Release prompt archived: `project_docs/release_prompts/v7.1.txt`.
- Release documentation: `docs/releases/v7.1.md`.

### 2026-06-25

#### `[x]` Implement v7.4 Collection Assistant

- Date started: 2026-06-25
- Date completed: 2026-06-25
- Roadmap lock commit: `fab9527`.
- Implementation commit: `2e5c56b`.
- Release metadata commit: pending.
- Release tag: `v7.4`.
- Features implemented:
  - Collection Assistant Engine with guided cataloguing workflow
  - CollectionAssistantEngine, CollectionAssistantCandidate, AssistantReviewQueue
  - AssistantSummary, ProductivityMetrics, SideBySideComparison
  - PhotoInfo with side detection, quality assessment, auto-pairing
  - OCRCandidate with confidence scoring, trust levels, evidence
  - CollectionMatch with exact/similar matching and duplicate risk
  - CollectionGapInfo for series/date/denomination gap detection
  - AcquisitionPriorityInfo for WANT_LIST and strategy priority matching
  - Photo workflow: multi-photo import, auto-pairing, quality checks
  - OCR workflow: text parsing, confidence scoring, evidence collection
  - Side-by-side review with candidate, match, evidence, recommendations
  - Batch review with queue filtering, sorting, progress tracking
  - Productivity metrics: photos, OCR success, reviews, time saved
  - GUI integration: Tools -> Collection Assistant dialog with 3 tabs
  - Export support: Markdown and CSV for session, queue, productivity
- Test results: 880 tests OK (up from 842).
- Release prompt archived: `project_docs/release_prompts/v7.4.txt`.
- Release documentation: `docs/releases/v7.4.md`.

### 2026-06-25

#### `[x]` Implement v7.2 Collection Insights

- Date started: 2026-06-25
- Date completed: 2026-06-25
- Release commit: `9c856c3`.
- Release tag: `v7.2`.
- Features implemented:
  - Collection Insights Engine with deterministic, explainable observations
  - InsightCategory, InsightPriority, InsightEvidence dataclasses
  - CollectionInsight with category, priority, evidence, confidence, actionability
  - CollectorHealthReport with overall score and component scores
  - CollectionInsightReport with categorized insights and health report
  - InsightsDashboard with summary, priority counts, category breakdown
  - Collection insights: size, diversity, grade coverage, year span, empty collection
  - Portfolio insights: value, unrealized gain/loss, silver exposure
  - Acquisition insights: watchlist progress, duplicate concentration
  - Workflow insights: completion rate, photo coverage, OCR utilization
  - Health report: metadata, photo, OCR, grading, documentation, workflow scores
  - Insight prioritization by priority and confidence
  - GUI integration: Tools -> Collection Insights dialog with 7 tabs
  - Export support: Markdown and CSV for reports and health reports
- Test results: 806 tests OK (up from 786).
- Release prompt archived: `project_docs/release_prompts/v7.2.txt`.
- Release documentation: `docs/releases/v7.2.md`.

### 2026-06-22

#### `[x]` Lock v6.3 roadmap

- Date started: 2026-06-22
- Date completed: 2026-06-22
- Roadmap lock commit: `6a78771`.
- Roadmap locked:
  - `v6.3` Device Linking & Conflict Resolution
  - `v7.0` Collector Platform
- Rationale: v6.0 established cloud architecture. v6.1 established backup and sync planning. v6.2 established multi-device workspaces. The final v6 milestone is linking devices and resolving cross-device conflicts safely while keeping collector review mandatory.
- Release prompt archive verified:
  - `project_docs/release_prompts/v5.4.txt`
  - `project_docs/release_prompts/v6.0.txt`
  - `project_docs/release_prompts/v6.1.txt`
  - `project_docs/release_prompts/v6.2.txt`
  - `project_docs/release_prompts/v6.3.txt`
- Files checked:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `README.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v6.0.md`
  - `docs/releases/v6.1.md`
  - `docs/releases/v6.2.md`

#### `[-]` Build v6.3 Device Linking & Conflict Resolution

- Date started: 2026-06-22
- Implementation status: locally implemented; full-suite audit passed.
- Implementation commit: pending commit creation.
- Added `device_linking.py` with `DeviceLinkingEngine`, `LinkedDevice`, `DeviceRelationship`, `DeviceLinkReport`, `WorkspaceLinkMap`, `ConflictResolutionEngine`, `ConflictCase`, `ConflictAnalysis`, `ConflictRecommendation`, `ConflictResolutionReport`, and `DeviceLinkReadinessReport`.
- Device relationships cover Primary Device, Secondary Device, Mobile Device, Tablet Device, and Backup Device.
- Conflict detection covers collection, workflow, portfolio, watchlist, settings, and snapshot conflicts.
- Conflict classification covers LOW, MEDIUM, and HIGH.
- Recommendations cover MERGE, KEEP_PRIMARY, KEEP_SECONDARY, REVIEW_REQUIRED, and REJECT without automatic application.
- Workspace link maps display linked devices, relationships, capability overlap, conflict exposure, and sync readiness.
- Readiness reports track linked devices, unresolved conflicts, merge exposure, backup coverage, workspace health, and recommendations.
- Integration: Multi-Device Workspace snapshots, Collector Cloud, and Sync & Backup are reused.
- GUI: Tools -> Device Linking & Conflict Resolution with link reports, conflicts, workspace maps, readiness, full review, and export actions.
- Release prompt archived: `project_docs/release_prompts/v6.3.txt`.
- Release notes: `docs/releases/v6.3.md`.
- Tests passed: `python -m unittest test_device_linking.py` -> 11 tests OK; adjacent v6.3 slice -> 73 tests OK; `run_tests.bat` -> 715 tests OK.
- Full-suite audit status: PASS.
- Limitation: offline planning only; no internet sync, real cloud providers, user accounts, authentication services, automatic conflict resolution, background sync, or collection mutation.

#### `[x]` Build v6.2 Multi-Device Collector Workspace

- Date started: 2026-06-22
- Date completed: 2026-06-22
- Implementation status: complete; release metadata prepared for tag and push verification.
- Implementation commit: `735c4bf`.
- Added `multi_device_workspace.py` with `MultiDeviceWorkspaceEngine`, `CollectorWorkspace`, `DeviceProfile`, `WorkspaceSnapshot`, `WorkspaceActivity`, and `WorkspaceHealthReport`.
- Device profiles cover Desktop, Laptop, Phone, and Tablet with capability and module coverage.
- Workspaces track registered devices, snapshots, sync readiness, backup readiness, and activities.
- Workspace snapshots track device, collection, portfolio, workflow, watchlist, cloud snapshot, and backup archive state with comparison and drift analysis.
- Capability reports cover Photo Capture, OCR Identification, Collection Entry, Workflow Integration, Deal Hunter, Portfolio Analysis, and Backup Operations.
- Activity summaries track device, workflow, backup, and collection activity.
- Health reports track device coverage, backup coverage, sync readiness, snapshot freshness, conflict exposure, workflow coverage, and recommendations.
- Scenario simulations cover Desktop -> Phone -> Laptop and Phone -> Tablet -> Desktop without synchronization.
- Integration: Collector Cloud snapshots and Sync & Backup archives are reused for workspace snapshots.
- GUI: Tools -> Multi-Device Workspace with workspace, device, snapshot, capability, activity, health, scenario, and export actions.
- Release prompt archived: `project_docs/release_prompts/v6.2.txt`.
- Release notes: `docs/releases/v6.2.md`.
- Tests passed: `python -m unittest test_multi_device_workspace.py` -> 10 tests OK; adjacent v6.2 slice -> 62 tests OK; `run_tests.bat` -> 704 tests OK.
- Full-suite audit status: PASS.
- Limitation: offline planning only; no real synchronization, device linking, accounts, authentication, internet services, cloud providers, automatic restore, automatic conflict resolution, background sync, or collection mutation.

#### `[x]` Lock v6.2 roadmap

- Date started: 2026-06-22
- Date completed: 2026-06-22
- Roadmap lock commit: `11d7dc7`.
- Roadmap locked:
  - `v6.2` Multi-Device Collector Workspace
  - `v6.3` Device Linking & Conflict Resolution
  - `v7.0` Collector Platform
- Rationale: v6.0 established the cloud architecture layer. v6.1 established backup archives, restore planning, snapshot history, sync simulation, rollback planning, and conflict reporting. The next step is modeling how collectors work across desktop, laptop, phone, and tablet while remaining completely offline.
- Release prompt archive verified:
  - `project_docs/release_prompts/v5.4.txt`
  - `project_docs/release_prompts/v6.0.txt`
  - `project_docs/release_prompts/v6.1.txt`
  - `project_docs/release_prompts/v6.2.txt`
- Files checked:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `README.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v6.0.md`
  - `docs/releases/v6.1.md`

#### `[x]` Lock v6.1 roadmap

- Date started: 2026-06-22
- Date completed: 2026-06-22
- Roadmap lock commit: `3e35f3c`.
- Roadmap locked:
  - `v6.1` Sync & Backup
  - `v6.2` Multi-Device Collector Workspace
  - `v6.3` Device Linking & Conflict Resolution
  - `v7.0` Collector Platform
- Rationale: v6.0 established the cloud architecture layer with CollectorCloud, CloudCollectionSnapshot, CloudSyncPlan, CloudBackupPackage, and CloudReadinessReport. The next step is implementing backup, restore planning, snapshot history, rollback planning, and synchronization simulation.
- Release prompt archive verified:
  - `project_docs/release_prompts/v5.4.txt`
  - `project_docs/release_prompts/v6.0.txt`
  - `project_docs/release_prompts/v6.1.txt`
- Files checked:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `README.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v5.4.md`
  - `docs/releases/v6.0.md`

#### `[x]` Lock v6 roadmap

- Date started: 2026-06-22
- Date completed: 2026-06-22
- Roadmap lock commit: `761a296`.
- Roadmap locked:
  - `v6.0` Collector Cloud Foundation
  - `v6.1` Sync & Backup
  - `v6.2` Multi-Device Collector Workspace
  - `v6.3` Device Linking & Conflict Resolution
  - `v7.0` Collector Platform
- Rationale: v5.x completed Mobile Companion, Phone Photo Capture, OCR-Assisted Identification, Mobile Collection Entry, and Collector Workflow Integration. The collector workflow is now complete; the next stage is preparing the platform for future synchronization and multi-device operation.
- Release prompt archive verified:
  - `project_docs/release_prompts/v5.1.txt`
  - `project_docs/release_prompts/v5.2.txt`
  - `project_docs/release_prompts/v5.3.txt`
  - `project_docs/release_prompts/v5.4.txt`
  - `project_docs/release_prompts/v6.0.txt`
- Files checked:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `README.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v5.0.md`
  - `docs/releases/v5.1.md`
  - `docs/releases/v5.2.md`
  - `docs/releases/v5.3.md`
  - `docs/releases/v5.4.md`

#### `[x]` Build v6.1 Sync & Backup

- Date started: 2026-06-22
- Date completed: 2026-06-22
- Implementation status: complete; metadata commit, tag, push, and remote verification completed.
- Implementation commit: `b884755`.
- Added `sync_backup_engine.py` with `SyncBackupEngine`, `BackupArchive`, `RestorePlan`, `BackupHistory`, `SyncSimulation`, `SyncConflictReport`, and `RollbackPlan`.
- Backup archives cover collection, portfolio, watchlist, workflow, and settings scope with timestamps, version, source snapshot, checksum, metadata, and warnings.
- Restore plans report affected modules, affected records, warnings, conflicts, validation results, and rollback options without overwriting existing data.
- Backup history provides timeline, snapshot comparisons, collection delta, portfolio delta, and workflow delta.
- Sync simulations compare two local snapshots, generate sync proposals, conflict analysis, and merge previews without synchronization.
- Conflict reports detect duplicate entries, collection/workflow/settings mismatches, snapshot divergence, backup incompatibilities, and MERGE/REVIEW/REJECT recommendations.
- Rollback plans cover backup, restore, and sync rollback targets, scope, risks, and recommendations.
- GUI: Tools -> Sync & Backup with backup archives, restore plans, backup history, sync simulations, conflict reports, rollback plans, and CSV/Markdown export.
- Release prompt archived: `project_docs/release_prompts/v6.1.txt`.
- Release notes: `docs/releases/v6.1.md`.
- Tests passed: `python -m unittest test_sync_backup_engine.py` -> 9 tests OK; adjacent v6.1 slice -> 44 tests OK; `run_tests.bat` -> 694 tests OK.
- Limitation: offline planning only; no internet synchronization, cloud providers, user accounts, authentication, automatic conflict resolution, automatic restore, background sync, or collection mutation.

#### `[x]` Build v6.0 Collector Cloud Foundation

- Date started: 2026-06-22
- Date completed: 2026-06-22
- Implementation status: complete; metadata commit, tag, push, and remote verification completed.
- Implementation commit: `a35528b`.
- Added `collector_cloud.py` with `CollectorCloud`, `CloudRecord`, `CloudCollectionSnapshot`, `CloudSyncPlan`, `CloudBackupPackage`, `CloudConflict`, and `CloudReadinessReport`.
- Snapshot model tracks collection metrics, portfolio metrics, workflow metrics, module counts, content hashes, metadata, and snapshot history.
- Sync planning generates proposed changes, merge candidates, and manual-review conflicts without executing synchronization.
- Backup package model provides package metadata, validation findings, and restore previews without cloud storage or restore execution.
- Readiness reporting tracks syncable modules, non-syncable modules, migration requirements, risks, and conflict exposure.
- GUI: Tools -> Collector Cloud Foundation with snapshots, sync plans, backup packages, readiness reports, conflict previews, and CSV/Markdown export.
- Mobile Companion integration: companion reports can include latest Collector Cloud readiness summary.
- Release prompt archived: `project_docs/release_prompts/v6.0.txt`.
- Release notes: `docs/releases/v6.0.md`.
- Tests passed: `python -m unittest test_collector_cloud.py` -> 8 tests OK; adjacent v6.0 slice -> 47 tests OK; `run_tests.bat` -> 685 tests OK.
- Limitation: offline architecture only; no real cloud hosting, accounts, authentication, internet connectivity, cloud providers, background sync, automatic restore, or collection mutation.

#### `[x]` Lock v5.4 roadmap

- Date started: 2026-06-22
- Date completed: 2026-06-22
- Roadmap lock commit: `0760cc0`.
- Roadmap locked:
  - `v5.4` Collector Workflow Integration
  - `v6.0` Collector Cloud Foundation
  - `v6.1` Sync & Backup
  - `v6.2` Multi-Device Collector Workspace
  - `v6.3` Device Linking & Conflict Resolution
  - `v7.0` Collector Platform
- Rationale: The v5.x series introduced Mobile Collector Companion, Phone Photo Capture, OCR-Assisted Identification, and Mobile Collection Entry. Before introducing cloud architecture, these capabilities should be unified into a complete collector workflow.
- Release prompt archive verified:
  - `project_docs/release_prompts/v5.1.txt`
  - `project_docs/release_prompts/v5.2.txt`
  - `project_docs/release_prompts/v5.3.txt`
  - `project_docs/release_prompts/v5.4.txt`
- Files checked:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `README.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v5.0.md`
  - `docs/releases/v5.1.md`
  - `docs/releases/v5.2.md`
  - `docs/releases/v5.3.md`

#### `[x]` Build v5.4 Collector Workflow Integration

- Date started: 2026-06-22
- Date completed: 2026-06-22
- Implementation status: complete; metadata commit, tag, push, and remote verification completed.
- Implementation commit: `f86d8ca`.
- Added `collector_workflow_integration.py` with `CollectorWorkflowIntegrationEngine`, `WorkflowStage`, `WorkflowSession`, `WorkflowCompletionReport`, and `WorkflowHealthReport`.
- End-to-end workflow implemented: Photo Capture -> OCR Identification -> Evidence Review -> Collection Context -> Collection Entry Candidate -> Portfolio Impact Preview -> Final Review.
- Review checkpoints support APPROVE, REJECT, and REVIEW.
- Workflow sessions support resume/reopen from serialized session data.
- Workflow health reporting tracks completed workflows, abandoned workflows, review escalations, confidence distribution, and stage completion rates.
- Portfolio preview integration reuses Mobile Collection Entry and Portfolio Performance preview data.
- Mobile Companion integration: companion reports can include Collector Workflow Integration summaries.
- GUI: Tools -> Collector Workflow Integration with workflow generation, final review controls, completion export, and health export.
- Release prompt archived: `project_docs/release_prompts/v5.4.txt`.
- Release notes: `docs/releases/v5.4.md`.
- Tests passed: v5.4 focused/adjacent slice -> 44 tests OK; `run_tests.bat` -> 677 tests OK.
- GUI smoke blocked by local Tcl/Tk `init.tcl` installation issue.

#### `[x]` Lock v5.3 roadmap

- Date started: 2026-06-22
- Date completed: 2026-06-22
- Roadmap lock commit: `bf294c1`.
- Roadmap locked:
  - `v5.3` Mobile Collection Entry
  - `v6.0` Collector Cloud
  - `v6.1` Sync & Backup
  - `v6.2` Multi-Device Collector Workspace
- Release prompt archive verified:
  - `project_docs/release_prompts/v5.1.txt`
  - `project_docs/release_prompts/v5.2.txt`
  - `project_docs/release_prompts/v5.3.txt`
- Files checked:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `README.md`


#### `[x]` Build v5.3 Mobile Collection Entry

- Date started: 2026-06-22
- Date completed: 2026-06-22
- Implementation status: complete; metadata commit, tag, push, and remote verification completed.
- Implementation commit: `9b5be99`.
- Added `mobile_collection_entry.py` with `MobileCollectionEntryEngine`, `CollectionEntryCandidate`, `CollectionEntryReview`, and `CollectionEntryReport`.
- Pipeline implemented: Photo/OCR text -> OCR Candidate -> Collection Entry Candidate -> Review -> Approved Entry Record preview.
- Review decisions: APPROVE, REJECT, REVIEW; approval prepares a preview record only and never inserts it automatically.
- Context checks: already owned, duplicate, possible upgrade, collection gap, WANT_LIST/watchlist match, review required.
- Portfolio integration: preview-only collection size, priority, collection gap, and value-impact notes through Portfolio Performance.
- Field workflows: Coin Show, Dealer Visit, Coin Shop, Auction Preview, Antique Market.
- GUI: Tools -> Mobile Collection Entry with candidate generation, first-candidate review controls, confidence/evidence/context/impact display, and CSV/Markdown export.
- Mobile Companion integration: companion reports can include latest Mobile Collection Entry summary.
- Release prompt archived: `project_docs/release_prompts/v5.3.txt`.
- Release notes: `docs/releases/v5.3.md`.
- Tests passed: `python -m unittest test_mobile_collection_entry` -> 8 tests OK; adjacent v5.3 slice -> 48 tests OK; `python -m unittest test_melt_value_engine` -> 29 tests OK; `run_tests.bat` -> 669 tests OK.

#### `[x]` Lock v5.2 roadmap

- Date started: 2026-06-22
- Date completed: 2026-06-22
- Roadmap locked:
  - `v5.2` OCR-Assisted Identification
  - `v5.3` Mobile Collection Entry
  - `v6.0` Collector Cloud
  - `v6.1` Sync & Backup
  - `v6.2` Multi-Device Collector Workspace
- Release prompt archive verified:
  - `project_docs/release_prompts/v5.1.txt`
  - `project_docs/release_prompts/v5.2.txt`
- Files checked:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `README.md`
- Commit hash: `08c5cf2`

#### `[x]` Build v5.2 OCR-Assisted Identification

- Date started: 2026-06-22
- Date completed: 2026-06-22
- Files modified:
  - `ocr_assisted_identification.py` (new file)
  - `test_ocr_assisted_identification.py` (new file)
  - `coin_collection_gui.py`
  - `mobile_collector_companion.py`
  - `test_mobile_collector_companion.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v5.2.md` (new file)
- Roadmap lock commit hash: `08c5cf2`
- Implementation commit hash: `96b65b9`
- Test coverage: total passing tests increased from 650 to 660; full suite passed.
- Release prompt archived: `project_docs/release_prompts/v5.2.txt`.
- Limitation: OCR-assisted identification is advisory only; no computer vision attribution, AI grading, automatic collection entry, automatic ownership decisions, automatic purchases, or collection mutation.

### 2026-06-21

#### `[x]` Lock v5 roadmap

- Date started: 2026-06-22
- Date completed: 2026-06-22
- Roadmap locked:
  - `v5.0` Mobile Collector Companion
  - `v5.1` Phone Photo Capture
  - `v5.2` OCR-Assisted Identification
  - `v5.3` Mobile Collection Entry
  - `v6.0` Collector Cloud
  - `v6.1` Sync & Backup
  - `v6.2` Multi-Device Collector Workspace
- Rationale: v4.x completed Live Deal Hunter, Live Source Validation, Market Intelligence Automation, Watchlists & Alerts, and Field Testing & Tuning; the intelligence stack is mature enough for a mobile-focused workflow.
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `README.md`
- Commit hash: `0e9e37f`

#### `[x]` Build v5.0 Mobile Collector Companion

- Date started: 2026-06-22
- Date completed: 2026-06-22
- Files modified:
  - `mobile_collector_companion.py` (new file)
  - `test_mobile_collector_companion.py` (new file)
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v5.0.md` (new file)
- Roadmap lock commit hash: `0e9e37f`
- Implementation commit hash: `814ca99`
- Test coverage: total passing tests increased from 633 to 641; existing regression suites remained green.
- Limitation: desktop/local mobile workflow simulation only; no Android/iOS app, cloud sync, phone-camera integration, OCR identification, live fetching, purchasing, or collection mutation.

#### `[x]` Lock v4.4 roadmap

- Date started: 2026-06-21
- Date completed: 2026-06-21
- Roadmap locked:
  - `v4.4` Live Deal Hunter Field Test & Tuning
  - `v5.0` Mobile Collector Companion
  - `v5.1` Phone Photo Capture
  - `v5.2` OCR-Assisted Identification
  - `v6.0` Collector Cloud
- Rationale: `v4.0` introduced live opportunity discovery, `v4.1` introduced source validation, `v4.2` introduced automated market intelligence enrichment, and `v4.3` introduced watchlists and alerts; before mobile expansion, the live pipeline should be tuned using realistic field-test scenarios.
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `README.md`
- Commit hash: `e21abe3`

#### `[x]` Build v4.4 Live Deal Hunter Field Test & Tuning

- Date started: 2026-06-21
- Date completed: 2026-06-21
- Files modified:
  - `field_test_framework.py` (new file)
  - `test_field_test_framework.py` (new file)
  - `coin_collection_gui.py`
  - `watchlist_engine.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v4.4.md` (new file)
- Roadmap lock commit hash: `e21abe3`
- Implementation commit hash: `1b5bfce`
- Test coverage: total passing tests increased from 625 to 633; existing regression suites remained green.
- Limitation: deterministic local field testing only; no new live sources, scraping, browser automation, API integrations, automatic purchasing, collection mutation, push notifications, or cloud sync.

#### `[x]` Lock v4.3 roadmap

- Date started: 2026-06-21
- Date completed: 2026-06-21
- Roadmap locked:
  - `v4.3` Watchlists & Alerts
  - `v5.0` Mobile Collector Companion
  - `v5.1` Phone Photo Capture
  - `v5.2` OCR-Assisted Identification
  - `v6.0` Collector Cloud
- Rationale: `v4.2` completed automated market intelligence enrichment; `v4.3` lets collectors define what they care about and identify matching opportunities.
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `README.md`
  - `project_docs/release_prompts/v4.3.txt`
- Commit hash: `14f09d6`

#### `[x]` Build v4.3 Watchlists & Alerts

- Date started: 2026-06-21
- Date completed: 2026-06-21
- Files modified:
  - `watchlist_engine.py` (new file)
  - `test_watchlist_engine.py` (new file)
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v4.3.md` (new file)
- Roadmap lock commit hash: `14f09d6`
- Implementation commit hash: `c793569`
- Test coverage: total passing tests increased from 615 to 625; existing regression suites remained green.
- Limitation: report-driven, user-triggered alerts only; no push/email/SMS notifications, background polling, scheduled jobs, automatic purchasing, bidding, live pricing, or collection mutation.

#### `[x]` Lock v4.2 roadmap

- Date completed: 2026-06-21
- Roadmap locked:
  - `v4.2` Market Intelligence Automation
  - `v4.3` Watchlists & Alerts
  - `v5.0` Mobile Collector Companion
- Rationale: v4.0 introduced live opportunity discovery; v4.1 hardened live source validation; v4.2 connects live/imported candidates to local Market Intelligence faster and more consistently.
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `README.md`
  - `project_docs/release_prompts/v4.2.txt`
- Commit hash: `473ffee`

#### `[x]` Build v4.2 Market Intelligence Automation

- Date started: 2026-06-21
- Date completed: 2026-06-21
- Files modified:
  - `market_intelligence_automation.py` (new file)
  - `test_market_intelligence_automation.py` (new file)
  - `live_deal_hunter.py`
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v4.2.md` (new file)
- Roadmap lock commit hash: `473ffee`
- Implementation commit hash: `17d7fe5`
- Test coverage: total passing tests increased from 602 to 615; existing regression suites remained green.
- Limitation: deterministic local enrichment only; no scraping, APIs, live pricing, exchange-rate lookup, market forecasting, automatic purchasing, bidding, investment advice, or collection mutation.

#### `[x]` Lock v4.1 roadmap

- Date completed: 2026-06-21
- Roadmap locked:
  - `v4.1` Live Source Validation
  - `v4.2` Market Intelligence Automation
  - `v5.0` Mobile Collector Companion
- Rationale: v4.0 introduced live opportunity discovery; v4.1 focuses on trust, validation, reliability, and source quality.
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `README.md`
  - `project_docs/release_prompts/v4.1.txt`
- Commit hash: `fcc715d`

#### `[x]` Build v4.1 Live Source Validation

- Date started: 2026-06-21
- Date completed: 2026-06-21
- Files modified:
  - `live_source_validation.py` (new file)
  - `test_live_source_validation.py` (new file)
  - `live_deal_hunter.py`
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v4.1.md` (new file)
- Roadmap lock commit hash: `fcc715d`
- Implementation commit hash: `639d794`
- Test coverage: total passing tests increased from 589 to 602; existing regression suites remained green.
- Limitation: deterministic validation only; no listing repair, currency conversion, exchange-rate lookup, source truth guarantee, scraping, browser automation, purchases, bids, background polling, or collection mutation.

#### `[x]` Lock v4.0 roadmap

- Date completed: 2026-06-21
- Roadmap locked:
  - `v4.0` Live Deal Hunter (Controlled Beta)
  - `v4.1` Live Source Validation
  - `v4.2` Market Intelligence Automation
  - `v5.0` Mobile Collector Companion
- Rationale: v3.x established Collection Intelligence, Deal Hunter, Opportunity Engine, Ranking Engine, Listing Connectors, Calibration, Live Readiness, Market Intelligence, and Portfolio Performance; v4.0 introduces controlled live opportunity discovery.
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `README.md`
- Commit hash: `3dd8830`

#### `[x]` Build v4.0 Live Deal Hunter (Controlled Beta)

- Date started: 2026-06-21
- Date completed: 2026-06-21
- Files modified:
  - `live_deal_hunter.py` (new file)
  - `test_live_deal_hunter.py` (new file)
  - `test_data/deal_hunter/sample_live_rss.xml` (new fixture)
  - `coin_collection_gui.py`
  - `project_docs/release_prompts/v4.0.txt` (release prompt archive)
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v4.0.md` (new file)
- Roadmap lock commit hash: `3dd8830`
- Implementation commit hash: `1d8c1bc`
- Test coverage: total passing tests increased from 579 to 589; existing regression suites remained green.
- Limitation: controlled-beta public RSS/XML ingestion only; no scraping, browser automation, logins, eBay API integration, purchases, bids, background polling, collection mutation, or live-pricing accuracy claims.

#### `[x]` Lock post-v3.8 roadmap

- Date completed: 2026-06-21
- Roadmap locked:
  - `v3.8` Market Intelligence
  - `v3.9` Portfolio Performance
  - `v4.0` Live Deal Hunter
  - `v4.1` Live Source Validation
  - `v4.2` Market Intelligence Automation
  - `v5.0` Mobile Collector Companion
- Rationale: the platform can now evaluate, rank, explain, and calibrate opportunities; the next objective is understanding portfolio progress and collection development over time.
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `README.md`
- Commit hash: `a65a9ce`

#### `[x]` Build v3.9 Portfolio Performance

- Date started: 2026-06-21
- Date completed: 2026-06-21
- Files modified:
  - `portfolio_performance.py` (new file)
  - `test_portfolio_performance.py` (new file)
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v3.9.md` (new file)
- Roadmap lock commit hash: `a65a9ce`
- Implementation commit hash: `e52083d`
- Test coverage: total passing tests increased from 571 to 579; existing regression suites remained green.
- Limitation: deterministic local portfolio-development reporting only; no investment advice, scraping, APIs, live pricing, market forecasting, automatic purchasing, or collection mutation.

#### `[x]` Build v3.8 Market Intelligence

- Date started: 2026-06-21
- Date completed: 2026-06-21
- Files modified:
  - `market_intelligence.py` (new file)
  - `test_market_intelligence.py` (new file)
  - `coin_collection_gui.py`
  - `project_docs/release_prompts/v3.8.txt` (new file)
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v3.8.md` (new file)
- Roadmap lock commit hash: `b9915d4`
- Implementation commit hash: `92864f6`
- Test coverage: total passing tests increased from 560 to 571; existing regression suites remained green.
- Limitation: deterministic local market guidance only; no scraping, browser automation, APIs, live pricing, automatic purchasing, image recognition, or collection mutation.

#### `[x]` Lock post-v3.4 roadmap

- Date completed: 2026-06-21
- Historical note: this roadmap lock was later superseded by the post-v3.7 roadmap recorded above, which moves Market Intelligence to `v3.8` and keeps `v4.2` for Portfolio Performance.
- Original rationale: the platform then contained Collection Intelligence, Deal Hunter, Opportunity Engine, and Ranking Engine; the next bottleneck was candidate acquisition, so future development prioritized listing ingestion, source normalization, connector reliability, and candidate volume before live APIs and scraping.
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `README.md`
- Commit hash: `e4a2245`

#### `[x]` Build v3.6 Deal Hunter Calibration

- Date started: 2026-06-21
- Date completed: 2026-06-21
- Files modified:
  - `deal_hunter_calibration.py` (new file)
  - `test_deal_hunter_calibration.py` (new file)
  - `test_data/deal_hunter/calibration_cases.csv` (new file)
  - `deal_hunter.py`
  - `coin_collection_gui.py`
  - `project_docs/release_prompts/v3.6.txt` (new file)
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v3.6.md` (new file)
- Implementation commit hash: `87bf575`
- Test coverage: total passing tests increased from 538 to 550; existing regression suites remained green.
- Limitation: deterministic offline calibration only; no scraping, browser automation, eBay/dealer/auction APIs, live listing retrieval, live pricing, automatic purchasing, image recognition, or collection mutation.

#### `[x]` Build v3.7 Live Deal Hunter Readiness

- Date started: 2026-06-21
- Date completed: 2026-06-21
- Files modified:
  - `live_deal_hunter_readiness.py` (new file)
  - `test_live_deal_hunter_readiness.py` (new file)
  - `coin_collection_gui.py`
  - `project_docs/release_prompts/v3.7.txt` (new file)
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v3.7.md` (new file)
- Implementation commit hash: `ca87a8a`
- Test coverage: total passing tests increased from 550 to 560; existing regression suites remained green.
- Limitation: readiness contracts and validation only; no scraping, browser automation, eBay/dealer/auction APIs, live listing retrieval, automatic purchasing, live pricing claims, image recognition, or collection mutation.

#### `[x]` Build v3.5 External Listing Connectors

- Date started: 2026-06-21
- Date completed: 2026-06-21
- Files modified:
  - `listing_connectors.py` (new file)
  - `test_listing_connectors.py` (new file)
  - `coin_collection_gui.py`
  - `project_docs/release_prompts/v3.5.txt` (new file)
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v3.5.md` (new file)
- Roadmap lock commit hash: `e4a2245`
- Implementation commit hash: `27aca0c`
- Test coverage: total passing tests increased from 527 to 538; existing regression suites remained green.
- Limitation: deterministic local connector framework only; no scraping, browser automation, eBay/dealer/auction APIs, live listing retrieval, live pricing, automatic purchasing, image recognition, or collection mutation.

#### `[x]` Build v3.4 Deal Hunter Ranking Engine

- Date started: 2026-06-21
- Date completed: 2026-06-21
- Files modified:
  - `deal_hunter_ranking.py` (new file)
  - `test_deal_hunter_ranking.py` (new file)
  - `coin_collection_gui.py`
  - `project_docs/release_prompts/v3.4.txt` (new file)
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v3.4.md` (new file)
- Implementation commit hash: `47d34fe`
- Test coverage: total passing tests increased from 515 to 527; existing regression suites remained green.
- Limitation: deterministic local ranking only; no scraping, browser automation, eBay APIs, live listing retrieval, live pricing, automatic purchasing, image recognition, or collection mutation.

#### `[x]` Build v3.3 Opportunity Engine

- Date started: 2026-06-21
- Date completed: 2026-06-21
- Roadmap lock:
  - `v3.3` Opportunity Engine
  - `v3.4` Deal Hunter Ranking Engine
  - `v3.5` External Listing Imports
  - `v4.0` Live Deal Hunter
  - `v5.0` Mobile Collector Companion
- Rationale: future work should prioritize opportunity identification, upgrade prioritization, budget allocation, candidate ranking, and decision quality over additional parser complexity.
- Files modified:
  - `opportunity_engine.py` (new file)
  - `test_opportunity_engine.py` (new file)
  - `coin_collection_gui.py`
  - `project_docs/release_prompts/v3.3.txt` (new file)
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v3.3.md` (new file)
- Roadmap lock commit hash: `7d53acc`
- Implementation commit hash: `3871611`
- Test coverage: total passing tests increased from 505 to 515; existing regression suites remained green.
- Limitation: deterministic local guidance only; no scraping, browser automation, APIs, live pricing, market prediction, image recognition, automatic purchasing, or collection mutation.

#### `[x]` Build v3.2 Deal Hunter Workflow Refinement

- Date completed: 2026-06-21
- Files modified:
  - `deal_hunter.py`
  - `coin_collection_gui.py`
  - `test_deal_hunter.py`
  - `test_data/deal_hunter/sample_ebay_ca_listings.csv`
  - `project_docs/release_prompts/3.2.txt` (new file)
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v3.2.md` (new file)
- Implementation commit hash: `0a80eff`
- Test coverage: total passing tests increased from 494 to 505; existing regression suites remained green.
- Limitation: deterministic local guidance only; no scraping, browser automation, eBay API usage, live listing fetches, or live market-pricing claims.

### 2026-06-20

#### `[x]` Build v3.1 eBay.ca Coin Deal Hunter MVP

- Date completed: 2026-06-20
- Files modified:
  - `deal_hunter.py` (new file)
  - `test_deal_hunter.py` (new file)
  - `test_data/deal_hunter/sample_ebay_ca_listings.csv` (new file)
  - `project_docs/release_prompts/3.1.txt` (new file)
  - `coin_collection_gui.py`
  - `persistence_manager.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v3.1.md` (new file)
- Implementation commit hash: `fb20988`
- Test coverage: total passing tests increased from 475 to 494; existing regression suites remained green.
- Limitation: deterministic local guidance only; no scraping, browser automation, eBay API usage, live listing fetches, or live market-pricing claims.

### 2026-06-19

#### `[x]` Build v3.0 Collector Companion

- Date completed: 2026-06-19
- Files modified:
  - `collector_companion_readiness.py`
  - `test_collector_companion_readiness.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v3.0.md` (new file)
- Implementation commit hash: `935e3c7`
- Test coverage: total passing tests increased from 471 to 475; existing regression suites remained green.

#### `[x]` Build v2.9 Collector Companion Release Candidate

- Date completed: 2026-06-19
- Files modified:
  - `collector_companion_readiness.py` (new file)
  - `test_collector_companion_readiness.py` (new file)
  - `coin_collection_gui.py`
  - `persistence_manager.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.9.md` (new file)
- Implementation commit hash: `379715f`
- Test coverage: total passing tests increased from 463 to 471; existing regression suites remained green.

#### `[x]` Build v2.8 Collector Home Dashboard

- Date completed: 2026-06-19
- Files modified:
  - `collector_home_dashboard.py` (new file)
  - `test_collector_home_dashboard.py` (new file)
  - `coin_collection_gui.py`
  - `persistence_manager.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.8.md` (new file)
- Implementation commit hash: `632a922`
- Test coverage: total passing tests increased from 451 to 463; existing regression suites remained green.

#### `[x]` Build v2.6 OCR Experiments

- Date completed: 2026-06-19
- Files modified:
  - `ocr_experiment.py` (new file)
  - `test_ocr_experiment.py` (new file)
  - `coin_collection_gui.py`
  - `persistence_manager.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.6.md` (new file)
- Implementation commit hash: `f569393`
- Test coverage: total passing tests increased from 422 to 433; existing regression suites remained green.

#### `[x]` Build v2.6.1 OCR Validation Layer

- Date completed: 2026-06-19
- Files modified:
  - `ocr_validation.py` (new file)
  - `test_ocr_validation.py` (new file)
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.6.1.md` (new file)
- Implementation commit hash: `22645a0`
- Test coverage: total passing tests increased from 433 to 444; existing regression suites remained green.

#### `[x]` Build v2.7 Workflow Integration

- Date completed: 2026-06-19
- Files modified:
  - `collector_workflows.py` (new file)
  - `test_collector_workflows.py` (new file)
  - `coin_collection_gui.py`
  - `persistence_manager.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.7.md` (new file)
- Implementation commit hash: `599cb4a`
- Test coverage: total passing tests increased from 444 to 451; existing regression suites remained green.

#### `[x]` Build v2.5.2 Shopping Explainability

- Date completed: 2026-06-19
- Files modified:
  - `shopping_explainability.py` (new file)
  - `test_shopping_explainability.py` (new file)
  - `smart_shopping_assistant.py`
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.5.2.md` (new file)
- Implementation commit hash: `17821de`
- Test coverage: total passing tests increased from 410 to 422; existing regression suites remained green.

### 2026-06-18

#### `[x]` Build v2.5.1 Photo Vault Hardening

- Date completed: 2026-06-18
- Files modified:
  - `photo_vault.py`
  - `test_photo_vault.py`
  - `backup_manager.py`
  - `test_backup_manager.py`
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.5.1.md` (new file)
- Implementation commit hash: `749182f`
- Test coverage: total passing tests increased from 399 to 410; existing regression suites remained green.

#### `[x]` Build v2.5 Photo-Assisted Entry

- Date completed: 2026-06-18
- Files modified:
  - `photo_assisted_entry.py` (new file)
  - `test_photo_assisted_entry.py` (new file)
  - `coin_collection_gui.py`
  - `persistence_manager.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.5.md` (new file)
- Implementation commit hash: `fd817b6`
- Test coverage: total passing tests increased from 391 to 399; existing regression suites remained green.

#### `[x]` Build v2.4.3 Collection Snapshot System

- Date completed: 2026-06-18
- Files modified:
  - `collection_snapshot.py` (new file)
  - `test_collection_snapshot.py` (new file)
  - `coin_collection_gui.py`
  - `backup_manager.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.4.3.md` (new file)
- Implementation commit hash: `044dd50`
- Test coverage: total passing tests increased from 382 to 391; existing regression suites remained green.

#### `[x]` Build v2.4.2 Collection Integrity Audit

- Date completed: 2026-06-18
- Files modified:
  - `collection_integrity.py` (new file)
  - `test_collection_integrity.py` (new file)
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.4.2.md` (new file)
- Implementation commit hash: `bbb7314`
- Test coverage: total passing tests increased from 368 to 382; existing regression suites remained green.

#### `[x]` Build v2.4.1 Critical Collection Backup Hardening

- Date completed: 2026-06-18
- Files modified:
  - `backup_manager.py`
  - `coin_collection_gui.py`
  - `test_backup_manager.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/BACKUP.md`
  - `docs/releases/v2.4.1.md` (new file)
- Implementation commit hash: `a9ca10c`
- Test coverage: total passing tests increased from 361 to 368; existing regression suites remained green.

#### `[x]` Build v2.4 Mobile Companion Prototype

- Date completed: 2026-06-18
- Files modified:
  - `mobile_companion.py` (new file)
  - `test_mobile_companion.py` (new file)
  - `collection_dashboard.py`
  - `persistence_manager.py`
  - `backup_manager.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.4.md` (new file)
- Implementation commit hash: `8de41c7`
- Test coverage: total passing tests increased from 344 to 361; existing regression suites remained green.

#### `[x]` Build v2.3 Mobile Readiness

- Date completed: 2026-06-18
- Files modified:
  - `mobile_readiness.py` (new file)
  - `test_mobile_readiness.py` (new file)
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.2.md`
  - `docs/releases/v2.3.md` (new file)
- Implementation commit hash: `539472b`

#### `[x]` Lock post-v2.2 roadmap

- Date completed: 2026-06-18
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `README.md`
- Roadmap locked:
  - `v2.3` Mobile Readiness
  - `v2.4` Mobile Companion Prototype
  - `v2.5` Photo-Assisted Entry
  - `v2.6` OCR Experiments
  - `v3.0` Collector Companion
- Clarification: `v2.3` is a readiness and architecture milestone only, not a mobile app.

#### `[x]` Build v2.2 Data Safety and Backup Hardening

- Date completed: 2026-06-18
- Files modified:
  - `backup_manager.py` (new file)
  - `test_backup_manager.py` (new file)
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/BACKUP.md`
  - `docs/releases/v2.2.md` (new file)
- Implementation commit hash: `e70fc4c`

#### `[x]` Build v2.1 Persistence Layer

- Date completed: 2026-06-18
- Files modified:
  - `persistence_manager.py` (new file)
  - `test_persistence_manager.py` (new file)
  - `collection_data/app_state/README.md` (new file)
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/BACKUP.md`
  - `docs/releases/v2.1.md` (new file)
- Implementation commit hash: `95ef0c0`

#### `[x]` Build v2.0 Collector Operating System

- Date completed: 2026-06-18
- Files modified:
  - `collector_operating_system.py` (new file)
  - `test_collector_operating_system.py` (new file)
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.0.md` (new file)
  - `project_docs/release_prompts/v2.0.txt`
- Implementation commit hash: `11b4f6e`

#### `[x]` Build v1.9 Smart Shopping Assistant

- Date completed: 2026-06-18
- Files modified:
  - `smart_shopping_assistant.py` (new file)
  - `test_smart_shopping_assistant.py` (new file)
  - `collection_dashboard.py`
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Implementation commit hash: `efe7a1b`

### 2026-06-17

#### `[x]` Build v1.8 Market Awareness Layer

- Date completed: 2026-06-17
- Files modified:
  - `market_awareness.py` (new file)
  - `test_market_awareness.py` (new file)
  - `collection_dashboard.py`
  - `acquisition_impact.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Implementation commit hash: `5a73332`

#### `[x]` Build v1.7 Photo Vault

- Date completed: 2026-06-17
- Files modified:
  - `photo_vault.py` (new file)
  - `test_photo_vault.py` (new file)
  - `collection_dashboard.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Implementation commit hash: `0b961d9`

#### `[x]` Build v1.6 Series Tracker

- Date completed: 2026-06-17
- Files modified:
  - `series_definitions.py` (new file)
  - `series_tracker.py` (new file)
  - `test_series_tracker.py` (new file)
  - `collection_dashboard.py`
  - `acquisition_impact.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Implementation commit hash: `8c4b58b`

### 2026-06-16

#### `[x]` Build v1.5 Smarter Acquisition Intelligence

- Date completed: 2026-06-16
- Files modified:
  - `acquisition_impact.py` (new file)
  - `test_acquisition_impact.py` (new file)
  - `listing_analyzer.py`
  - `coin_collection_gui.py`
  - `collection_dashboard.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Implementation commit hash: `549665a`

#### `[x]` Build v1.4 Collection Quality Engine

- Date completed: 2026-06-16
- Files modified:
  - `collection_quality.py` (new file)
  - `test_collection_quality.py` (new file)
  - `collection_dashboard.py`
  - `test_collection_dashboard.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Implementation commit hash: `4df68f2`

#### `[x]` Build v1.3 Collection Dashboard release line

- Date completed: 2026-06-16
- Files modified:
  - `collection_dashboard.py` (new file)
  - `test_collection_dashboard.py` (new file)
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Implementation commit hash: `da1c37f`

#### `[x]` Perform v1.2 post-release usability documentation audit

- Date completed: 2026-06-16
- Files modified:
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Commit hash: `d3eac79`

#### `[x]` Build Listing Analyzer

- Date completed: 2026-06-16
- Files modified:
  - `listing_analyzer.py` (new file)
  - `test_listing_analyzer.py` (new file)
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Commit hash: `7d12b54`

#### `[x]` Build Shared Session Context

- Date completed: 2026-06-16
- Files modified:
  - `session_context.py` (new file)
  - `coin_collection_gui.py`
  - `test_session_context.py` (new file)
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Commit hash: `a63edb5`

#### `[x]` Complete post-v1.0 release packaging documentation

- Date completed: 2026-06-16
- Files modified:
  - `README.md`
  - `RELEASE_HISTORY.md` (new file)
  - `docs/BACKUP.md` (new file)
  - `docs/releases/v1.0.md` (new file)
  - `docs/screenshots/README.md` (new file)
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
- Commit hash: `2318550`

#### `[x]` Perform v1.0 release-readiness audit

- Date completed: 2026-06-16
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
- Commit hash: `f20fd22`

#### `[x]` Build Acquisition Workflow on Collection Intelligence Engine

- Date completed: 2026-06-16
- Files modified:
  - `acquisition_workflow.py` (new file)
  - `test_acquisition_workflow.py` (new file)
  - `focused_collection_intelligence.py`
  - `buy_advisor.py`
  - `coin_collection_gui.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
- Commit hash: `77771f6`

#### `[x]` Integrate WANT_LIST context into Collection Intelligence Engine and Do I Own This

- Date completed: 2026-06-16
- Files modified:
  - `focused_collection_intelligence.py`
  - `coin_collection_gui.py`
  - `test_focused_collection_intelligence.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
- Commit hash: `76b4f11`

#### `[x]` Consolidate advisor decisions on Collection Intelligence Engine

- Date completed: 2026-06-16
- Files modified:
  - `focused_collection_intelligence.py`
  - `buy_advisor.py`
  - `upgrade_advisor.py`
  - `test_buy_advisor_regression.py`
  - `test_upgrade_advisor.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
- Commit hash: `fb96574`

#### `[x]` Build focused Collection Intelligence Engine

- Date completed: 2026-06-16
- Files modified:
  - `focused_collection_intelligence.py` (new file)
  - `test_focused_collection_intelligence.py` (new file)
  - `coin_collection_gui.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md` (new file)
- Commit hash: `831d363`

#### `[x]` Perform complete v0.5 release audit rerun

- Date completed: 2026-06-16
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `36fc71b`

### 2026-06-15

#### `[x]` Build Upgrade Advisor

- Date completed: 2026-06-15
- Files modified:
  - `upgrade_advisor.py`
  - `coin_collection_gui.py`
  - `test_upgrade_advisor.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `4601863`

#### `[x]` Perform v0.7 release audit

- Date completed: 2026-06-15
- Files modified:
  - `test_v07_audit.py` (new file)
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `cabd83c`

#### `[x]` Recreate dashboard metrics in app

- Date completed: 2026-06-15
- Files modified:
  - `portfolio_dashboard.py` (new file)
  - `test_portfolio_dashboard.py` (new file)
  - `coin_collection_gui.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `714e875`

#### `[x]` Perform v0.6 release audit

- Date completed: 2026-06-15
- Files modified:
  - `test_v06_audit.py` (new file)
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `2aed7a0`

#### `[x]` Build Melt Value Engine

- Date completed: 2026-06-15
- Files modified:
  - `melt_value_engine.py` (new file)
  - `test_melt_value_engine.py` (new file)
  - `buy_advisor.py`
  - `upgrade_advisor.py`
  - `test_buy_advisor_regression.py`
  - `test_upgrade_advisor.py`
- Commit hash: `8f85073`

#### `[x]` Fix low-priority world base metal Buy Advisor guardrail

- Date completed: 2026-06-15
- Files modified:
  - `buy_advisor.py`
  - `test_buy_advisor_regression.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `2aec691`

#### `[x]` Perform v0.4 integration audit

- Date completed: 2026-06-15
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `7e17d42`

#### `[x]` Connect staged WANT_LIST intent to Buy Advisor

- Date completed: 2026-06-15
- Files modified:
  - `buy_advisor.py`
  - `coin_collection_gui.py`
  - `test_buy_advisor_regression.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `4c4b854`

#### `[x]` Connect staged WANT_LIST intent to Want List Generator

- Date completed: 2026-06-15
- Files modified:
  - `collection_intelligence.py`
  - `coin_collection_gui.py`
  - `test_collection_intelligence.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `8f11122`

#### `[x]` Add WANT_LIST Preview GUI

- Date completed: 2026-06-15
- Files modified:
  - `coin_collection_gui.py`
  - `legacy_portfolio_importer.py`
  - `test_legacy_portfolio_importer.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `eced7d9`

#### `[x]` Implement legacy WANT_LIST staging integration

- Date completed: 2026-06-15
- Files modified:
  - `legacy_portfolio_importer.py`
  - `test_legacy_portfolio_importer.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `b8fa9fa`

#### `[x]` Finalize v0.3 release and plan WANT_LIST integration

- Date completed: 2026-06-15
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `WANT_LIST_INTEGRATION_PLAN.md`
- Commit hash: `fab99b0`

#### `[x]` Perform v0.3 release audit

- Date completed: 2026-06-15
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `20513d9`

#### `[x]` Refine Collection Gap Report MVP CSV export

- Date completed: 2026-06-15
- Files modified:
  - `collection_intelligence.py`
  - `coin_collection_gui.py`
  - `test_collection_intelligence.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `701765a`

#### `[x]` Add Portfolio Import Preview GUI

- Date completed: 2026-06-15
- Files modified:
  - `coin_collection_gui.py`
  - `legacy_portfolio_importer.py`
  - `test_legacy_portfolio_importer.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `c50eb12`

#### `[x]` Implement legacy portfolio staging importer

- Date completed: 2026-06-15
- Files modified:
  - `legacy_portfolio_importer.py`
  - `test_legacy_portfolio_importer.py`
  - `requirements.txt`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `5e2732b`

#### `[x]` Add portfolio integration roadmap

- Date completed: 2026-06-15
- Files modified:
  - `PORTFOLIO_INTEGRATION_ROADMAP.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `b3d17bc`

#### `[x]` Add legacy portfolio import spec

- Date completed: 2026-06-15
- Files modified:
  - `LEGACY_PORTFOLIO_IMPORT_SPEC.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `217c467`

#### `[x]` Implement Collection Gap Report

- Date completed: 2026-06-15
- Files modified:
  - `collection_intelligence.py`
  - `coin_collection_gui.py`
  - `test_collection_intelligence.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `259ad42`

#### `[x]` Add Markdown export for gap report

- Date completed: 2026-06-15
- Files modified:
  - `collection_intelligence.py`
  - `coin_collection_gui.py`
  - `test_collection_intelligence.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `259ad42`

#### `[x]` Implement Want List Generator MVP

- Date completed: 2026-06-15
- Files modified:
  - `collection_intelligence.py`
  - `coin_collection_gui.py`
  - `test_collection_intelligence.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `259ad42`

#### `[x]` Add Auction Evaluator draft spec

- Date completed: 2026-06-15
- Files modified:
  - `AUCTION_EVALUATOR_SPEC.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `259ad42`

#### `[x]` Add Adam-specific collection priorities

- Date completed: 2026-06-15
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `f9014c3`

#### `[x]` Harden test infrastructure

- Date completed: 2026-06-15
- Files modified:
  - `test_accuracy.py`
  - `test_backend.py`
  - `test_buy_advisor_regression.py`
  - `test_collection_analysis.py`
  - `test_csv_import.py`
- Commit hash: `ac1d4e7`

#### `[x]` Add `run_tests.bat`

- Date completed: 2026-06-15
- Files modified:
  - `run_tests.bat`
- Commit hash: `ac1d4e7`

#### `[x]` Add `TESTING.md`

- Date completed: 2026-06-15
- Files modified:
  - `TESTING.md`
- Commit hash: `ac1d4e7`

#### `[x]` Add GitHub Actions workflow

- Date completed: 2026-06-15
- Files modified:
  - `.github/workflows/tests.yml`
- Commit hash: `ac1d4e7`

#### `[x]` Ensure tests use isolated test data

- Date completed: 2026-06-15
- Files modified:
  - `test_data/sample_collection.json`
  - `test_data/sample_import.csv`
  - `test_backend.py`
  - `test_buy_advisor_regression.py`
  - `test_collection_analysis.py`
  - `test_csv_import.py`
- Commit hash: `ac1d4e7`
