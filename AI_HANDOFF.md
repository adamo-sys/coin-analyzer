# AI Handoff

## Snapshot

- Date: 2026-06-23
- Branch: `main`
- Current project state file reports release version: `v7.2`
- Current active task: v7.3 Acquisition Strategy

## Official v2.7-to-v3.0 Roadmap

1. `v2.7` Workflow Integration
2. `v2.8` Collector Home Dashboard
3. `v2.9` Collector Companion Release Candidate
4. `v3.0` Collector Companion

Clarification: `v2.9` is not a new feature engine. It is a release-candidate polish milestone focused on consistency, workflow quality, usability, documentation, and readiness validation before v3.0.

## Official v7.3 Roadmap

1. `v7.3` Acquisition Strategy
2. `v7.4` Collection Assistant
3. `v7.5` Numista Intelligence
4. `v8.0` Smart Phone Cataloguer
5. `v8.1` Batch Processing
6. `v8.2` AI Grading Assistant
7. `v8.3` Collector Workspace
8. `v8.4` Connected Data
9. `v9.0` Collector Ecosystem

Roadmap rationale: v7.0 established the platform architecture with service registry, plugin system, command framework, event bus, unified models, UI patterns, configuration, and state management. v7.1 added platform analytics for monitoring and insights, measuring every major subsystem using deterministic local data without AI, forecasting, or external APIs. v7.2 added Collection Insights that transform deterministic analytics into explainable, evidence-based observations about the collection, portfolio, workflow, and acquisition strategy. v7.3 adds Acquisition Strategy that orchestrates existing collection intelligence, insights, analytics, opportunity scoring, and market intelligence into strategic acquisition plans with phased priorities, portfolio balance guidance, and risk-adjusted recommendations without AI reasoning, forecasting, machine learning, or external APIs.

Post-v3.8 rationale: the platform can now evaluate opportunities, rank opportunities, explain opportunities, and calibrate recommendations. The next objective is understanding portfolio progress and collection development over time.

v4.0 rationale: v3.x established Collection Intelligence, Deal Hunter, Opportunity Engine, Ranking Engine, Listing Connectors, Calibration, Live Readiness, Market Intelligence, and Portfolio Performance. v4.0 introduces controlled, user-triggered live opportunity discovery while preserving no-purchase, no-bidding, no-background-job, and no-collection-mutation safety rules.

v4.1 rationale: v4.0 introduced live opportunity discovery. v4.1 focuses on trust, validation, reliability, and source quality before live listings enter Deal Hunter, Opportunity Engine, Ranking Engine, or Market Intelligence.

v4.2 rationale: v4.0 introduced live opportunity discovery and v4.1 hardened live source validation. v4.2 automates the connection between live/imported candidates and local Market Intelligence so collectors can understand deal quality faster and with greater consistency.


## Release Prompt Archive

Release prompts are project documentation and architecture history. Store them under `project_docs/release_prompts/`, preserve historical prompts, and version new prompts by release number such as `v5.1.txt`, `v5.2.txt`, `v5.3.txt`, `v5.4.txt`, `v6.0.txt`, `v6.1.txt`, `v6.2.txt`, and `v6.3.txt`.

Before each release, verify the current release prompt exists, previous archived prompts remain available, and release notes document whether the prompt was archived and where it lives.

## What Changed

- Added `platform_analytics.py` with `PlatformAnalyticsEngine`, `AnalyticsMetric`, `AnalyticsTrend`, `ModuleMetrics`, `AnalyticsSnapshot`, `AnalyticsSummary`, `PlatformHealthScore`, and `AnalyticsDashboard` for deterministic platform analytics.
- Platform Analytics Engine generates metrics for all major subsystems: Collection Intelligence, Portfolio Performance, Workflow Integration, Deal Hunter, Opportunity Engine, Market Intelligence, Watchlists & Alerts, Collector Cloud, Sync & Backup, Multi-Device Workspace, and Device Linking.
- Collection metrics: total items, unique countries, unique denominations, graded items, grade coverage, year coverage.
- Portfolio metrics: total estimated value, acquisition cost, unrealized gain/loss percentage, silver exposure percentage.
- Workflow metrics: photos captured, OCR sessions, identification success rate, entry completion rate, workflow completion rate.
- Deal Hunter metrics: listings processed, buy/pass recommendation rates, risk flags.
- Opportunity Engine metrics: opportunities generated, high-priority rate.
- Market Intelligence metrics: market records, comparable sales.
- Watchlist metrics: watchlists, watchlist items, alerts generated.
- Cloud metrics: snapshots created, sync plans generated.
- Sync & Backup metrics: backup archives, last backup age, sync simulations, backup readiness.
- Workspace metrics: registered devices, workspace snapshots.
- Device Linking metrics: linked devices, unresolved conflicts.
- PlatformHealthScore with component scores: module coverage, backup readiness, workflow completeness, metadata quality, collection completeness.
- AnalyticsDashboard with snapshot, summary, health score, and trends.
- Export support: Markdown and CSV export for snapshots and health scores.
- GUI integration: Tools -> Platform Analytics dialog with Dashboard, Health Score, Module Metrics, and Trends tabs.
- Added `test_platform_analytics.py`; platform analytics tests passed 18 OK; full `run_tests.bat` passed 786 OK (up from 768).
- v7.1 implementation commit: `51be4f3`.
- v7.1 release tag: `v7.1`.
- Archived the v7.1 release prompt at `project_docs/release_prompts/v7.1.txt`.
- v7.1 roadmap rationale: v7.0 established the platform architecture with service registry, plugin system, command framework, event bus, unified models, UI patterns, configuration, and state management. v7.1 adds platform analytics for monitoring and insights, measuring every major subsystem using deterministic local data without AI, forecasting, or external APIs.

- Added `platform_core.py`, `plugin_system.py`, `command_framework.py`, `event_bus.py`, `unified_models.py`, `ui_patterns.py`, `platform_config.py`, `platform_state.py`, and `platform_integration.py` establishing the Collector Platform architecture.
- Service Registry for registering, managing, and querying platform services with dependency tracking and health checks.
- Plugin System for dynamic plugin loading, validation, dependency management, and lifecycle control.
- Command Framework for structured command execution with validation, history tracking, rollback support, and statistics.
- Event Bus for publish/subscribe communication with priority handling, filtering, history tracking, and statistics.
- Unified Data Models for standardizing data structures across collection, market, portfolio, workspace, cloud, and device domains.
- UI Patterns for consistent dialogs, reports, workflows, and forms with standardized styling and state management.
- Platform Configuration for centralized configuration management with validation, persistence, backup, and migration support.
- Platform State Management for state persistence, snapshots, restoration, and migration.
- Platform Integration layer for connecting existing collector services as platform services.
- Platform Management GUI tool (Tools -> Platform Management) with tabs for Services, Plugins, Event Bus, Commands, and Configuration.
- Added `test_platform_core.py`, `test_plugin_system.py`, `test_command_framework.py`, and `test_event_bus.py`; platform tests passed 37 OK; full `run_tests.bat` passed 768 OK.
- v7.0 implementation commit: `9674de5`.
- v7.0 release tag: `v7.0`.
- Archived the v6.3 release prompt at `project_docs/release_prompts/v6.3.txt`.
- v6.3 roadmap rationale: v6.0 established cloud architecture, v6.1 established backup and sync planning, and v6.2 established multi-device workspaces; v6.3 links devices and resolves cross-device conflicts safely while keeping collector review mandatory.

- Added `multi_device_workspace.py` with `MultiDeviceWorkspaceEngine`, `CollectorWorkspace`, `DeviceProfile`, `WorkspaceSnapshot`, `WorkspaceActivity`, and `WorkspaceHealthReport`.
- Multi-Device Collector Workspace models desktop, laptop, phone, and tablet use entirely offline with device profiles, capability coverage, workspace snapshots, drift analysis, activities, health reports, and scenario simulations.
- Workspace snapshots reuse Collector Cloud snapshots and Sync & Backup archives so collection, portfolio, workflow, watchlist, cloud snapshot, and backup state stay aligned with v6.0/v6.1 architecture.
- Tools -> Multi-Device Workspace displays workspaces, devices, snapshots, capability reports, activity summaries, health reports, Desktop -> Phone -> Laptop simulation, Phone -> Tablet -> Desktop simulation, and CSV/Markdown export.
- Added `test_multi_device_workspace.py`; focused Multi-Device tests passed 10 OK; adjacent v6.2 slice passed 62 OK; full `run_tests.bat` passed 704 OK.
- v6.2 implementation commit: `735c4bf`.

- Locked the v6.2 roadmap: v6.2 Multi-Device Collector Workspace, v6.3 Device Linking & Conflict Resolution, and v7.0 Collector Platform.
- Archived the v6.2 release prompt at `project_docs/release_prompts/v6.2.txt`.
- v6.2 roadmap rationale: v6.0 established cloud architecture; v6.1 established backup archives, restore planning, snapshot history, sync simulation, rollback planning, and conflict reporting; v6.2 models offline collector work across desktop, laptop, phone, and tablet.

- Added `sync_backup_engine.py` with `SyncBackupEngine`, `BackupArchive`, `RestorePlan`, `BackupHistory`, `SyncSimulation`, `SyncConflictReport`, and `RollbackPlan`.
- Sync & Backup creates offline backup archives, restore plans, backup history, sync simulations, conflict reports, and rollback plans on top of Collector Cloud snapshots.
- Backup archives track version, timestamp, source snapshot, checksum, metadata, and backup scope for collection, portfolio, watchlists, workflow, and settings.
- Restore plans preview affected modules/records, warnings, conflicts, validation results, and rollback options without overwriting data.
- Sync simulations compare local Device A and Device B snapshots and generate proposals, conflict analysis, and merge previews without synchronization.
- Tools -> Sync & Backup displays backup archives, restore plans, backup history, sync simulations, conflict reports, rollback plans, and CSV/Markdown export.
- Added `test_sync_backup_engine.py`; focused Sync & Backup tests passed 9 OK; adjacent v6.1 slice passed 44 OK; full `run_tests.bat` passed 694 OK.
- v6.1 implementation commit: `b884755`.

- Locked the v6.1 roadmap: v6.1 Sync & Backup, v6.2 Multi-Device Collector Workspace, v6.3 Device Linking & Conflict Resolution, and v7.0 Collector Platform.
- Archived the v6.1 release prompt at `project_docs/release_prompts/v6.1.txt`.
- v6.1 roadmap rationale: v6.0 established the cloud architecture layer; the next step is offline backup, restore planning, snapshot history, rollback planning, and synchronization simulation.

- Added `collector_cloud.py` with `CollectorCloud`, `CloudRecord`, `CloudCollectionSnapshot`, `CloudSyncPlan`, `CloudBackupPackage`, `CloudConflict`, and `CloudReadinessReport`.
- Collector Cloud Foundation models future cloud state entirely offline: collection records, snapshot history, sync plans, backup packages, conflicts, and readiness reports.
- Snapshot creation tracks collection metrics, portfolio metrics, workflow metrics, module counts, stable content hashes, and no-upload metadata.
- Sync plans generate proposed changes, merge candidates, collection/workflow/settings/record conflicts, and manual-review recommendations without executing synchronization.
- Backup packages include package metadata, validation findings, and restore previews without cloud storage or restore execution.
- Tools -> Collector Cloud Foundation displays snapshots, sync plans, backup packages, readiness reports, conflict previews, and CSV/Markdown export.
- Mobile Collector Companion reports can include Collector Cloud readiness summaries.
- Added `test_collector_cloud.py`; focused Collector Cloud tests passed 8 OK; adjacent v6.0 slice passed 47 OK; full `run_tests.bat` passed 685 OK.
- v6.0 implementation commit: `a35528b`.

- Locked the v6 roadmap: v6.0 Collector Cloud Foundation, v6.1 Sync & Backup, v6.2 Multi-Device Collector Workspace, v6.3 Device Linking & Conflict Resolution, and v7.0 Collector Platform.
- Archived the v6.0 release prompt at `project_docs/release_prompts/v6.0.txt`.
- v6 roadmap rationale: v5.x completed Mobile Companion, Phone Photo Capture, OCR-Assisted Identification, Mobile Collection Entry, and Collector Workflow Integration; the next stage prepares for future sync and multi-device operation.

- Added `collector_workflow_integration.py` with `CollectorWorkflowIntegrationEngine`, `WorkflowStage`, `WorkflowSession`, `WorkflowCompletionReport`, and `WorkflowHealthReport`.
- Collector Workflow Integration coordinates Phone Photo Capture, OCR-Assisted Identification, evidence review, collection context, Mobile Collection Entry, Portfolio Performance preview, and final review without mutating collection records.
- Workflow sessions track photos, OCR candidates, evidence, collection context, entry candidates, portfolio previews, review decisions, timestamps, and resume/reopen state.
- Review checkpoints support APPROVE, REJECT, and REVIEW at OCR review, evidence review, collection context, entry review, portfolio preview, and final review stages.
- Workflow health reporting tracks completed workflows, abandoned workflows, review escalations, confidence distribution, and stage completion rates.
- Added Tools -> Collector Workflow Integration with Markdown/CSV export for completion and health reports.
- Mobile Collector Companion reports can include Collector Workflow Integration summaries.
- Added `test_collector_workflow_integration.py` and expanded Mobile Collector Companion tests.
- v5.4 implementation commit: `f86d8ca`.
- v5.4 acceptance audit: 677 tests OK via `run_tests.bat`.

- Locked the v5.4 roadmap: Collector Workflow Integration, followed by v6.0 Collector Cloud Foundation, v6.1 Sync & Backup, v6.2 Multi-Device Collector Workspace, v6.3 Device Linking & Conflict Resolution, and v7.0 Collector Platform.
- Archived the v5.4 release prompt at `project_docs/release_prompts/v5.4.txt`.

- Added `mobile_collection_entry.py` with `MobileCollectionEntryEngine`, `CollectionEntryCandidate`, `CollectionEntryReview`, and `CollectionEntryReport`.
- Mobile Collection Entry converts OCR identification output into review-only proposed collection-entry records with country, year, denomination, series, monarch, variety, grade estimate, certification number, notes, acquisition source, and per-field confidence.
- The workflow preserves manual control: APPROVE prepares an approved-entry preview, REJECT rejects the candidate, REVIEW keeps it in manual review, and no collection record is inserted automatically.
- Collection context covers already owned, duplicate, possible upgrade, collection gap, WANT_LIST/watchlist matches, and review-required states.
- Portfolio impact previews summarize collection size, priority, collection gap, and value-impact implications without valuation automation or mutation.
- Added Tools -> Mobile Collection Entry with OCR text/latest-OCR report intake, field workflow selection, review controls, and CSV/Markdown export.
- Mobile Collector Companion reports can include Mobile Collection Entry summaries.
- Added `test_mobile_collection_entry.py` and expanded Mobile Collector Companion tests.
- Archived the v5.3 release prompt at `project_docs/release_prompts/v5.3.txt`.
- v5.3 implementation commit: `9b5be99`.
- v5.3 acceptance audit: 669 tests OK via `run_tests.bat`.

- Added `ocr_assisted_identification.py` with `OCRIdentificationEngine`, `OCRIdentificationCandidate`, `OCRIdentificationReport`, and `IdentificationEvidence`.
- OCR-Assisted Identification turns captured photos or pasted OCR text into review-only identification candidates.
- The candidate model includes year, denomination, country, monarch, banknote prefix, certification number, series/type, silver indicator, possible variety keywords, confidence, evidence, collection relevance, watchlist matches, warnings, and mandatory review status.
- The evidence model records OCR text used, validation score, trust level, supporting keywords, conflicts detected, and missing evidence.
- OCR identification reuses OCR Experiment, OCR Validation, Phone Photo Capture, Focused Collection Intelligence, and Watchlists instead of mutating collection records or duplicating decision engines.
- Added Tools -> OCR-Assisted Identification with Markdown/CSV export.
- Mobile Collector Companion reports can include OCR-Assisted Identification summaries.
- Added `test_ocr_assisted_identification.py` and expanded Mobile Collector Companion tests.
- Archived the v5.2 release prompt at `project_docs/release_prompts/v5.2.txt`.

- Added `mobile_collector_companion.py` with `MobileCollectorCompanion`, `MobileSession`, `MobileWorkflow`, `QuickDecisionSummary`, `MobileCollectionContext`, `MobileDashboard`, `FieldWorkMode`, and `MobileCompanionReport`.
- Added mobile-oriented workflows for coin shows, dealer visits, antique markets, coin shops, and auction previews.
- Quick Decision Mode summarizes BUY/WATCH/PASS/REVIEW, confidence, top reasons, key risks, watchlist matches, collection relevance, and market intelligence summary.
- Mobile Collection Context surfaces active watchlists, high-priority targets, collection priorities, recent opportunities, and portfolio highlights useful away from the desktop.
- Field Work Mode provides short-form summaries optimized for simulated on-the-go review.
- Added Tools -> Mobile Collector Companion with manual candidate rows and CSV/Markdown export.
- Mobile Collector Companion reuses Deal Hunter Ranking, Market Intelligence Automation, Watchlists, Alerts, Portfolio Performance, and Field Test Framework instead of duplicating intelligence logic.
- Added `test_mobile_collector_companion.py` covering sessions, workflows, quick decisions, collection context, dashboard, field work mode, report export, and field-test integration.

- Added `field_test_framework.py` with `FieldTestScenario`, `FieldTestResult`, `FieldTestReport`, `ScenarioRunner`, `OpportunityQualityReport`, `PipelineHealthReport`, and `FalsePositiveAudit`.
- Added deterministic field-test scenarios for Newfoundland upgrade, Newfoundland duplicate, 1859 variety candidate, 1926 Near 6 candidate, Canadian silver lot, banknote opportunity, high shipping trap, non-CAD listing, weak title listing, duplicate URL listing, false positive watchlist match, and strong watchlist match.
- Field tests run local scenario batches through Live Source Validation, Live Deal Hunter, Deal Hunter Ranking, Market Intelligence Automation, Watchlists, and Alerts without fetching live sources.
- Added Tools -> Field Test & Tuning with scenario results, pipeline health, opportunity quality, false positive audit, CSV export, and Markdown export.
- Tuned watchlist confidence downward when candidate text contains souvenir/token/copy/replica wording so likely false-positive collector targets are easier to review.
- Added `test_field_test_framework.py` covering scenario execution, pipeline health, alert tuning, opportunity quality, false-positive audit, report exports, and full scenario library execution.

- Added `watchlist_engine.py` with `WatchlistEngine`, `Watchlist`, `WatchlistItem`, `WatchlistMatch`, `AlertEngine`, `AlertRecord`, `AlertScore`, `WatchlistReport`, and `AlertReport`.
- Watchlists support series, specific coin, keyword, and custom watches with `CRITICAL`, `HIGH`, `NORMAL`, and `LOW` priorities.
- Added Adam starter presets for Newfoundland Coins, Newfoundland Silver, Canadian Silver, Canadian Banknotes, 1859 Large Cent Varieties, 1926 Near 6 Nickel, and 1973 Large Bust Quarter; presets are editable.
- Watchlists scan existing Deal Hunter, Ranking, Live Deal Hunter, listing connector, and Market Intelligence Automation candidate outputs without duplicating recommendation logic.
- Alerts are generated on demand only for watchlist matches, upgrade opportunities, collection-gap opportunities, high-priority opportunities, and rare target opportunities.
- Added Tools -> Watchlists & Alerts with editable watch rows, candidate rows, scan/report display, and CSV/Markdown export.
- Added `test_watchlist_engine.py` covering watch creation/removal, keyword watches, specific coin watches, series watches, priority ordering, presets, alert scoring, exports, and enriched-candidate pipeline integration.

- Added `focused_collection_intelligence.py` with reusable deterministic candidate classification.
- Added Tools -> Do I Own This in `coin_collection_gui.py`.
- Added `test_focused_collection_intelligence.py` with focused unit coverage.
- Refactored `buy_advisor.py` duplicate/upgrade flags to use `FocusedCollectionIntelligenceEngine`.
- Refactored `upgrade_advisor.py` match/upgrade decisions to use `FocusedCollectionIntelligenceEngine`.
- Added regression tests proving both advisors route through the focused engine while preserving existing verdict behavior.
- Added WANT_LIST context status to focused candidate analysis: `ON_WANT_LIST`, `NOT_ON_WANT_LIST`, `GAP_NOT_EXPLICITLY_TARGETED`, and `WANT_LIST_UNAVAILABLE`.
- Added a lightweight Load WANT_LIST Context button to Tools -> Do I Own This.
- Added `acquisition_workflow.py`, a deterministic purchase-guidance service using the focused Collection Intelligence Engine as its decision source.
- Buy Advisor now stores the acquisition workflow result as supporting structured context while preserving existing user-visible behavior.
- Do I Own This shows acquisition guidance when asking price is provided.
- Completed v1.0 release-readiness audit with app/tool smoke checks, export smoke checks, tag metadata verification, and full regression suite.
- Tagged v1.0 at `2c3d68bc65fcb2f3787f9a3d7624bd49675684c7`.
- Added post-v1.0 packaging docs: README refresh, release notes, release history, screenshot guide, and backup guide.
- Added `session_context.py` with shared per-session workbook and WANT_LIST context models.
- Added Tools -> Load Collection Context and Tools -> Clear Session Context, plus a lightweight session status line in `coin_collection_gui.py`.
- Do I Own This, Acquisition Workflow guidance, Buy Advisor, Want List Generator, Portfolio Import Preview, and Want List Preview can now reuse loaded shared WANT_LIST/workbook context while preserving manual load fallbacks.
- Added `test_session_context.py` for empty context, successful loads, missing/invalid workbook handling, shared consumer behavior, clearing state, and manual workflow preservation.
- Added `listing_analyzer.py` with `ListingCandidate`, URL validation, total-cost calculation, basic candidate parsing, and offline analysis through Acquisition Workflow.
- Added Tools -> Listing Analyzer in `coin_collection_gui.py`.
- Added `test_listing_analyzer.py` covering listing creation, URL validation, total cost, WANT_LIST, duplicate, upgrade, gap, missing inputs, and Shared Session Context integration.
- Tagged and pushed `v1.2` at `db001da4187af5a2bd2350bd956b2876007f7587`.
- Clarified README guidance for which acquisition tool to use, report/export support, and Listing Analyzer limitations.
- Added `collection_dashboard.py` with structured dashboard data, snapshot counts, actionable priorities, upgrade opportunities, WANT_LIST priorities, collection gaps, series completion, basic collection evolution, and CSV/Markdown export.
- Added Tools -> Collection Dashboard in `coin_collection_gui.py`.
- Added `test_collection_dashboard.py` for empty collection, small collection summary, WANT_LIST integration, upgrade reporting, gap reporting, series completion, exports, and Shared Session Context integration.
- Added `collection_quality.py` with deterministic quality reports, category scores, strengths, weaknesses, recommended actions, supporting metrics, and CSV/Markdown export.
- Integrated Collection Quality output into Collection Dashboard markdown and CSV exports.
- Added `test_collection_quality.py` covering empty, small, and larger collections; completeness, upgrade, WANT_LIST, diversity, certification scores; strengths, weaknesses, recommended actions, dashboard integration, and exports.
- Added `acquisition_impact.py` with deterministic candidate add/replace simulation, quality deltas, completion deltas, WANT_LIST impact, upgrade impact, impact score, and recommendation reasoning.
- Listing Analyzer results now include acquisition impact score, quality impact, completion impact, and recommendation reasoning.
- Tools -> Listing Analyzer displays acquisition impact output in its existing text report.
- Collection Dashboard now exposes Top Potential Collection Improvements from the quality report.
- Added `test_acquisition_impact.py` covering duplicates, upgrades, WANT_LIST targets, gap fillers, major Newfoundland targets, random world base-metal, quality/completion deltas, dashboard integration, and Listing Analyzer integration.
- Added `series_definitions.py` with extendable definitions for supported Newfoundland and Canadian series.
- Added `series_tracker.py` with series reports, owned/missing dates, completion percentages, WANT_LIST counts, upgrade counts, priority scores, top missing dates, and CSV/Markdown export.
- Collection Dashboard now exposes Top Series using Series Tracker output.
- Acquisition Impact now exposes series name and series priority before/after/delta.
- Added `test_series_tracker.py` covering definitions, completion, missing dates, WANT_LIST, upgrades, priority, dashboard integration, acquisition impact integration, and exports.
- Added `photo_vault.py` with metadata-only `PhotoRecord`, collection/candidate/reference linking, certification-number lookup, deterministic search, expected folder mapping, coverage metrics, and CSV/Markdown export.
- Collection Dashboard now accepts optional photo records and displays photo coverage metrics.
- Added `test_photo_vault.py` covering record creation, collection linking, candidate linking, reference linking, certification lookup, dashboard integration, search, and exports.
- Added `market_awareness.py` with local-only observed price, purchase, sale, and auction records plus market summaries, historical observed-price context, and CSV/Markdown export.
- Collection Dashboard now accepts an optional Market Awareness engine and displays purchases, sales, observations, auctions, averages, and recent market activity.
- Acquisition Impact can now expose local historical observed-price context for a candidate without changing recommendation thresholds or using live pricing.
- Market records can preserve linked Photo Vault reference identifiers without moving files.
- Added `test_market_awareness.py` covering record creation, auction tracking, dashboard integration, acquisition context, export support, and photo-reference IDs.
- Added `smart_shopping_assistant.py` with `ShoppingCandidate`, `ShoppingRecommendation`, `ShoppingRecommendationReport`, and `SmartShoppingAssistant`.
- Smart Shopping Assistant ranks manual opportunities, Listing Analyzer candidates, staged WANT_LIST targets, and local Market Awareness observations using Acquisition Workflow and Acquisition Impact outputs.
- Collection Dashboard now accepts optional shopping candidates and displays Best Next Purchase and Top Opportunities.
- Added Tools -> Smart Shopping Assistant in `coin_collection_gui.py` with multiline manual opportunity entry and CSV/Markdown export.
- Added `test_smart_shopping_assistant.py` covering candidate ranking, STRONG BUY/BUY/NEGOTIATE/WATCH/PASS/REVIEW paths, WANT_LIST and upgrade prioritization, market context, dashboard integration, exports, Shared Session Context, listing conversion, and photo-reference IDs.
- Added `collector_operating_system.py` with Collector Home and Collection Health Report consolidation.
- Collector Home composes existing dashboard, quality, series, smart shopping, market, and photo coverage output into a unified starting point.
- Collection Health Report combines dashboard summary, quality summary, series summary, Smart Shopping priorities, market summary, strengths, weaknesses, recommended actions, and persistence findings.
- Added Tools -> Collector Home and Tools -> Collection Health Report in `coin_collection_gui.py`.
- Added `test_collector_operating_system.py` covering summary generation, shopping integration, end-to-end workflow guidance, export consistency, persistence findings, empty collection behavior, and photo/market context.
- Added `persistence_manager.py` with JSON-backed app state save, load, clear, validate, backup, import, and export.
- Added Tools -> Save Session State, Load Session State, Clear Session State, Export Session State, and Import Session State.
- Persistence covers Shared Session Context metadata, last workbook path, WANT_LIST path/source, Market Awareness records, Photo Vault records, Smart Shopping candidates, app preferences, warnings, and errors.
- Saving over existing state and clearing saved state create timestamped backups under `collection_data/app_state/backups/`.
- Added `test_persistence_manager.py` covering empty state, session context, market/photo/shopping round-trips, corrupt JSON, missing workbook warnings, clear, backup, import/export, and invalid schema.
- Added `backup_manager.py` with BackupManager, BackupManifest, DataSafetyValidator, DataSafetyReport, backup package creation/verification/listing/restore, safe pre-restore backup behavior, and Collector Export Bundle generation.
- Added Tools -> Data Safety Check, Create Backup Package, List Backups, and Restore Backup.
- Backup packages include app state when available, release metadata, release notes, and JSON/Markdown manifests with checksums.
- Data Safety Check validates app-state existence/schema, workbook/WANT_LIST paths, loadable market/photo/shopping records, missing photo references, and backup directory availability.
- Added `test_backup_manager.py` covering backup creation, manifest creation, verification, listing, restore validation, pre-restore backup creation, partial restore, corrupt backup handling, missing app state/workbook/photo references, PASS/WARNING/FAIL reports, and export bundle generation.
- Added `mobile_readiness.py` with MobileReadinessAuditor, MobileReadinessReport, MobileReadinessScore, desktop dependency findings, service boundary findings, mobile input findings, documentation-only API mappings, dealer-table phone workflow steps, and CSV/Markdown export.
- Added `test_mobile_readiness.py` covering report generation, score calculation, desktop blockers, service boundary review, mobile input readiness, future endpoint mapping, phone workflow audit, serialization, and export support.
- Documented v2.3 Mobile Readiness in README, PROJECT_STATE, TASK_QUEUE, RELEASE_HISTORY, and release notes.
- Locked the official post-v2.2 roadmap in PROJECT_STATE, TASK_QUEUE, AI_HANDOFF, and README: v2.3 Mobile Readiness, v2.4 Mobile Companion Prototype, v2.5 Photo-Assisted Entry, v2.6 OCR Experiments, and v3.0 Collector Companion.
- Added `mobile_companion.py` with MobileCandidateEntry, MobileAnalysisReport, MobileCompanionWorkflow, desktop StorageProvider/PhotoProvider/ExportProvider abstractions, PhoneWorkflowSimulation, PhoneWorkflowReport, and CSV/Markdown export.
- Mobile Companion reuses Listing Analyzer, Acquisition Workflow, Acquisition Impact, Smart Shopping Assistant, Photo Vault metadata, and Persistence Manager instead of duplicating recommendation logic.
- Collection Dashboard can optionally surface the last mobile recommendation, last mobile candidate, and top mobile opportunity.
- Persistence Manager now stores recent mobile candidates and recent mobile recommendations in the existing local JSON app-state model.
- Added `test_mobile_companion.py` covering minimal entry, concise reports, workflow scenarios, provider abstractions, phone simulation, persistence, dashboard integration, and exports.
- Updated `PROJECT_STATE.md` and `TASK_QUEUE.md` as source-of-truth files.
- Enhanced `backup_manager.py` so backup packages include `data/collection.json` by default and copy the persisted collection workbook path when available.
- Added explicit manifest recovery flags: `collection_json_backed_up`, `workbook_backed_up`, and `app_state_backed_up`.
- Added `CollectionRecoveryReport` and Tools -> Collection Recovery Report to show recoverable ownership records, workbook copies, app state, market records, photo metadata, and shopping candidates.
- Enhanced Data Safety validation for collection JSON existence, latest verified backup coverage, persisted workbook existence, and workbook backup availability.
- Expanded `test_backup_manager.py` coverage for collection JSON backup, missing collection JSON, workbook backup success, missing workbook warnings, manifest flags, recovery reports, and validator coverage.
- Added `collection_integrity.py` with CollectionIntegrityAudit, CollectionIntegrityReport, CollectionIntegrityScore, PhotoIntegritySummary, MarketIntegritySummary, and CertificationIntegritySummary.
- Added Tools -> Collection Integrity Audit with read-only report display and Markdown/CSV export.
- Collection Integrity Audit checks duplicate ownership records, missing dates, missing grades, invalid countries, invalid denominations, invalid years, orphan photo references, orphan market records, duplicate market observations, certification issues, shopping photo references, persistence paths, and backup readiness.
- Added `test_collection_integrity.py` covering integrity report generation, duplicate detection, missing fields, invalid values, orphan photos, orphan market records, certification issues, scoring, exports, and backup readiness integration.
- Added `collection_snapshot.py` with CollectionSnapshot, CollectionSnapshotManager, CollectionSnapshotReport, GrowthSummary, and SeriesProgressDelta.
- Added Tools -> Create Snapshot and Tools -> Snapshot Report with Markdown/CSV export.
- Snapshot storage uses `collection_data/app_state/collection_snapshots.json`; backup packages include that file when present.
- Collection snapshots capture collection size, quality score, integrity score, photo coverage, supported-series completion metrics, market record count, and shopping candidate count.
- Added `test_collection_snapshot.py` covering creation, persistence, comparison, growth, quality/integrity/photo/series deltas, exports, and backup eligibility.
- Added `photo_assisted_entry.py` with PhotoCandidate, PhotoAssistedEntry, and PhotoReviewReport.
- Added Tools -> Photo-Assisted Entry for metadata-only front/reverse/reference photo candidate review.
- Photo-Assisted Entry links candidate photos through Photo Vault metadata, converts candidates into Mobile Companion/Smart Shopping inputs, and reuses existing recommendation engines.
- Persistence Manager now stores photo candidate metadata in local app state.
- Added `test_photo_assisted_entry.py` covering candidate creation, photo linking, Photo Vault integration, Mobile Companion integration, persistence, backup metadata behavior, and exports.
- Added PhotoVaultIntegrityAudit, PhotoCoverageReport, and PhotoVaultIssue to `photo_vault.py`.
- Added Tools -> Photo Vault Audit for read-only coverage and trust reporting with CSV/Markdown export.
- Photo Vault Audit detects missing photo files, duplicate references, unlinked records, invalid extensions, unsupported paths, collection items without photos, candidates without photos, and certified/slabbed items without photos.
- Data Safety validation now surfaces Photo Vault audit warnings for duplicate, unlinked, invalid, unsupported, and candidate-missing-photo metadata.
- Collection Recovery Report now states that app-state backups preserve photo metadata, while photo files themselves are not copied automatically.
- Added `shopping_explainability.py` with RecommendationConfidence, RecommendationExplanation, ExplainableRecommendationReport, and ShoppingExplanationEngine.
- Shopping Explainability explains existing BUY/PASS/WATCH/NEGOTIATE/REVIEW outputs without changing recommendation outcomes.
- Smart Shopping Assistant markdown now includes compact "Why" blocks.
- Listing Analyzer GUI output now shows confidence, primary reasons, and supporting reasons.
- Added `test_shopping_explainability.py` covering BUY, PASS, WATCH, confidence, impact, ownership, WANT_LIST, exports, Listing Analyzer explanations, Smart Shopping markdown, and behavior preservation.
- Added `ocr_experiment.py` with OCRResult, OCRConfidence, OCRSuggestionReport, and OCRExperiment.
- Added Tools -> OCR Experiment for advisory-only OCR text extraction, suggestion display, and CSV/Markdown export.
- OCR Experiments extract possible years, denominations, countries, note prefixes, and certification numbers from OCR text while always requiring manual review.
- Persistence Manager now stores OCR results and OCR reports in local app state.
- Added `test_ocr_experiment.py` covering OCR result creation, deterministic confidence, suggestion extraction, missing-image warnings, persistence, exports, Photo-Assisted Entry/Photo Vault/Mobile Companion integration helpers, and no collection mutation.
- Added `ocr_validation.py` with OCRValidationEngine, OCRValidationReport, OCRTrustLevel, OCRValidationScore, and OCRValidationExplanation.
- OCR Validation Layer evaluates OCR output quality, trust level, validation score, findings, warnings, review recommendations, and explanations without changing OCR suggestions or collection/recommendation behavior.
- Tools -> OCR Experiment now displays the OCR suggestion report plus validation trust level, score, findings, warnings, explanation, and manual-review recommendations.
- Added `test_ocr_validation.py` covering trust levels, year/denomination/country/certification validation, warning generation, scoring, explanation, exports, and OCR behavior preservation.
- Added `collector_workflows.py` with CollectorWorkflowEngine, guided Acquisition Workflow, Collection Review Workflow, Photo Review Workflow, CollectorDailySummary, WorkflowStatus, and WorkflowSummary.
- Workflow Integration orchestrates existing Photo-Assisted Entry, OCR Experiment, OCR Validation, Smart Shopping, Shopping Explainability, Collection Dashboard, Collection Quality, Collection Integrity, Collection Snapshot, and Photo Vault Audit systems without replacing them.
- Added Tools -> Acquisition Workflow, Tools -> Collection Review Workflow, and Tools -> Daily Collector Summary.
- Persistence Manager now stores workflow statuses and workflow summaries in local app state.
- Added `test_collector_workflows.py` covering acquisition workflow, collection review workflow, photo workflow, daily summary, status tracking, persistence, and exports.
- Added `collector_home_dashboard.py` with CollectorHomeDashboard, CollectorHomeReport, HomeStatusCard, DailyCollectorAction, and HomeStatusSeverity.
- Collector Home Dashboard aggregates Collection Health, Acquisition Focus, Review Queue, Data Safety, Progress, ranked daily actions, top opportunities, warnings, workflow statuses, persistence, and CSV/Markdown export by reusing existing engines.
- Added Tools -> Collector Home Dashboard in `coin_collection_gui.py`.
- Persistence Manager now stores generated home reports and acknowledged home action identifiers in local app state.
- Added `test_collector_home_dashboard.py` covering report generation, daily action ranking, severity, backup status, integrity status, OCR review status, photo coverage, snapshot trend, top opportunities, exports, persistence compatibility, and fallback behavior.
- Added `collector_companion_readiness.py` with CollectorCompanionReadinessAuditor, CollectorCompanionReadinessReport, ExportConsistencyReport, ReportConsistencyReport, WorkflowAuditReport, and V3ReadinessChecklistItem.
- Added `CollectorCompanionStatus` as the v3.0 READY/NEEDS_WORK product status derived from the existing readiness auditor.
- Added `deal_hunter.py` with DealListing, ParsedDealCandidate, DealHunterResult, DealHunterReport, and DealHunter for offline eBay.ca-style listing evaluation.
- Deal Hunter supports manual rows, CSV import, deterministic parsing, slab/banknote/keyword detection, collection-aware scoring, Adam buying rules, counterarguments before BUY, Workflows -> Deal Hunter, persistence of recent listings/reports, and CSV/Markdown export.
- Refined Deal Hunter for v3.2 with grade-word parsing, key variety signals, banknote/slab detection hardening, lot/problem-coin risk flags, CSV alias handling, malformed price warnings, skipped-row reporting, GUI import summaries, and richer CSV/Markdown exports.
- Added `opportunity_engine.py` with OpportunityEngine, OpportunityScore, OpportunityReport, and TopOpportunitiesReport for budget-aware "What should I buy next?" guidance.
- Opportunity Engine reuses Collection Intelligence, Smart Shopping Assistant, Acquisition Impact, Collection Quality, Series Tracker, WANT_LIST, Deal Hunter, and local Market Awareness context.
- Added Workflows -> Opportunity Engine with optional manual candidates, top opportunities, budget recommendations, CSV export, and Markdown export.
- Added `deal_hunter_ranking.py` with `CandidatePool`, `ImportProfile`, `DealHunterRankingEngine`, `RankingScore`, `RankedDeal`, `BudgetOpportunityReport`, and `DealHunterRankingReport`.
- Deal Hunter Ranking merges manual/CSV candidate pools, validates eBay/Auction/Dealer/Custom import profiles, detects duplicate URLs/listings, and suppresses repeated recommendations.
- Deal Hunter Ranking reuses Deal Hunter and Opportunity Engine outputs to score candidates by collection fit, upgrade value, gap value, WANT_LIST relevance, liquidity, risk, and budget fit.
- Added Tools -> Deal Hunter Ranking with manual pool entry, local CSV import, source summary/ranking display, CSV export, and Markdown export.
- Added `test_deal_hunter_ranking.py` covering candidate pools, duplicate detection/import handling, import profiles, malformed imports, ranking score generation, budget views, Newfoundland/banknote/upgrade/gap categories, and exports.
- Added `listing_connectors.py` with `ListingConnector`, `ConnectorRegistry`, `NormalizedListing`, `eBayCSVConnector`, `AuctionCSVConnector`, `DealerInventoryConnector`, `GenericCSVConnector`, `ConnectorValidationReport`, `ConnectorImportReport`, `SourceSummaryReport`, and `DuplicateOpportunityDetector`.
- External Listing Connectors normalize user-supplied local CSV files into Deal Hunter-compatible listings, preserve source/connector/import metadata, validate required fields/prices/URLs/unsupported columns, and detect duplicate opportunities across sources.
- Added Tools -> External Listing Connectors for connector selection, local file import, validation/source/duplicate summary, multi-source ranking handoff, Markdown import export, and ranking CSV export.
- Added `test_listing_connectors.py` covering eBay/Auction/Dealer/Generic connectors, malformed imports, validation warnings, source tracking, duplicate detection, multi-source ranking, and report exports.
- Added `deal_hunter_calibration.py` with `CalibrationCase`, `CalibrationCaseResult`, `DealHunterCalibrationEngine`, and `DealHunterCalibrationReport` for offline collector-judgment calibration.
- Added `test_data/deal_hunter/calibration_cases.csv` with realistic fake cases for obvious BUY/PASS, high shipping, irrelevant items, Newfoundland upgrades, banknotes, same/lower-grade duplicates, raw overgraded claims, damaged/problem coins, estate/bulk lots, unclear currency, and explicit WANT_LIST matches.
- Added `test_deal_hunter_calibration.py` covering case creation, report generation, false BUY/PASS detection, ranking misses, missing risk flags, Newfoundland, banknote, high shipping, duplicate calibration, and exports.
- Added Tools -> Deal Hunter Calibration with default fixture loading, CSV loading, summary display, failed case display, and CSV/Markdown export.
- Tuned Deal Hunter raw high-grade risk detection so raw AU/MS-style titles are flagged as `RAW_OVERGRADED` and routed to manual review when collection-relevant.
- Added `live_deal_hunter_readiness.py` with `LiveDealHunterReadinessAudit`, `LiveDealHunterReadinessReport`, `LiveListingSource`, `LiveListingBatch`, `LiveListingFetchResult`, `LiveSourceValidationReport`, `RateLimitPolicy`, and `LiveSourceFailure`.
- Live Deal Hunter Readiness validates future live-source output contracts for missing title, missing price, missing shipping, non-CAD currency, malformed URL, missing seller, suspicious metadata, duplicate URLs, and stale listing timestamps.
- Added deterministic staleness flags: `FRESH`, `STALE`, and `UNKNOWN`.
- Added Tools -> Live Deal Hunter Readiness with report display and CSV/Markdown export.
- Added `test_live_deal_hunter_readiness.py` covering readiness report generation, contract models, validation reports, staleness, rate-limit policy, failure model, no-fetch behavior, and exports.
- Added `market_intelligence.py` with `MarketIntelligenceEngine`, `MarketIntelligenceReport`, `FairValueEstimate`, `ComparableSale`, `DealQuality`, `OpportunityConfidence`, and `RiskSummary`.
- Market Intelligence evaluates supplied/manual listing data with local comparable sales, local Market Awareness observations, Deal Hunter output, Opportunity Engine integration, Collection Intelligence context, WANT_LIST context, risk flags, confidence scoring, deal quality, buy rationale, and counterarguments.
- Added Tools -> Market Intelligence with manual listing entry, report display, CSV export, and Markdown export.
- Added `test_market_intelligence.py` covering fair-value generation, confidence scoring, deal quality, comparable sales, risk analysis, counterarguments, duplicate handling, upgrade handling, fallback valuation, and exports.
- Added `portfolio_performance.py` with `PortfolioPerformanceEngine`, `PortfolioPerformanceReport`, `CollectionGrowthReport`, `AcquisitionPerformanceReport`, `SeriesProgressReport`, `BudgetAllocationReport`, and `CollectionHealthScore`.
- Portfolio Performance reuses Collection Snapshot, Collection Intelligence, Opportunity Engine, Market Intelligence context, Series Tracker, Quality, Integrity, and local Market Awareness records.
- Added Tools -> Portfolio Performance with report display and CSV/Markdown export.
- Added `test_portfolio_performance.py` covering growth analysis, acquisition analysis, series progress, budget allocation, health score, snapshot comparison, executive dashboard, and exports.
- Added `live_deal_hunter.py` with `LiveDealHunter`, `LiveListing`, `LiveListingBatch`, `LiveDealHunterReport`, `LiveListingSource`, and `RSSListingConnector`.
- Live Deal Hunter fetches public RSS/XML only when explicitly triggered by the user, validates and normalizes listing data, rejects missing/invalid/duplicate URLs, converts accepted listings into CandidatePool inputs, reuses Deal Hunter Ranking and Market Intelligence, and exports CSV/Markdown reports.
- Added Tools -> Live Deal Hunter with RSS URL input, timeout input, explicit Analyze Live Feed action, report display, CSV export, and Markdown export.
- Added `test_data/deal_hunter/sample_live_rss.xml` and `test_live_deal_hunter.py` covering RSS parsing, source validation, listing normalization, CandidatePool integration, ranking integration, Market Intelligence integration, duplicate detection, reports/exports, source failures, and malformed feeds.
- v4.0 full suite passed: 589 tests OK. Coverage increased from 579 to 589, and existing regression suites remained green.
- v4.0 guardrails: no purchases, no bids, no background polling, no scheduled execution, no page scraping, no browser automation, no logins, no collection mutation, and no live-pricing accuracy claims.
- Added `live_source_validation.py` with `LiveSourceValidator`, `ValidationResult`, `ValidationWarning`, `ValidationSummary`, `SourceHealthReport`, `LiveSourceValidationReport`, and `ListingFreshness`.
- Live Source Validation checks required listing fields, CAD/USD/unknown currency, stale/unknown freshness, duplicate URLs, malformed/unsupported URLs, high shipping, vague titles, missing descriptions, and suspicious metadata.
- Live Deal Hunter now gates CandidatePool/ranking/Market Intelligence entry through `LiveSourceValidator`, preferring REVIEW or rejection over false confidence.
- Added Tools -> Live Source Validation with explicit user-triggered RSS validation, source health display, report display, CSV export, and Markdown export.
- Added `test_live_source_validation.py` covering missing title/price/seller/URL, CAD/non-CAD/unknown currency, stale listings, duplicate URLs, malformed URLs, source health scoring, validation reports, exports, and Live Deal Hunter fixture validation.
- v4.1 full suite passed: 602 tests OK. Coverage increased from 589 to 602, and existing regression suites remained green.
- v4.1 guardrails: validation is deterministic and conservative; it does not repair listings, convert currencies, fetch exchange rates, guarantee source truth, scrape pages, automate browsers, purchase, bid, poll in the background, or mutate collection data.
- Added `market_intelligence_automation.py` with `MarketIntelligenceAutomationEngine`, `MarketEnrichedCandidate`, `MarketEnrichmentBatchReport`, `FairValueEvidenceSummary`, and `CollectionRelevanceSummary`.
- Market Intelligence Automation reuses `MarketIntelligenceEngine` for all valuation guidance; it does not create a second valuation engine.
- Automation supports single candidates, candidate pools, ranked lists, live listing batches, and Live Deal Hunter reports.
- Live Deal Hunter reports now include automated Market Intelligence enrichment summaries after validation, CandidatePool creation, and ranking.
- Added Tools -> Market Intelligence Automation for manual batch enrichment with CSV/Markdown export.
- Added `test_market_intelligence_automation.py` covering single enrichment, candidate-pool enrichment, batch enrichment, upgrade/WANT_LIST/gap/duplicate classifications, low-confidence REVIEW escalation, fair-value evidence summaries, ranking integration, Live Deal Hunter integration, export generation, original recommendation preservation, and no live price retrieval.
- v4.2 full suite passed: 615 tests OK. Coverage increased from 602 to 615, and existing regression suites remained green.
- v4.2 guardrails: deterministic local enrichment only; no scraping, APIs, live pricing, exchange-rate lookup, market forecasting, automatic purchasing, bidding, investment advice, or collection mutation.
- Reorganized the GUI menu bar into Collector Home, Workflows, Reports, Tools, and Help groupings while preserving existing commands.
- Added Tools -> Collector Companion Readiness and Help -> Collector Companion Readiness.
- Persistence Manager now stores readiness reports and audit summaries in local app state.
- Added `test_collector_companion_readiness.py` covering readiness generation, checklist generation, export consistency, report consistency, workflow audit, persistence compatibility, export generation, and menu grouping.

## Engine Scope

The focused engine accepts manual candidate input and returns structured output:

- Match status
- Best existing match
- Grade comparison
- Collection impact
- Recommendation
- Confidence score
- Priority reasons
- Warning flags
- WANT_LIST status
- Shared session context status

The acquisition workflow adds:

- Asking price
- Max rational price
- BUY/PASS/WATCH/NEGOTIATE/REVIEW recommendation
- Owned/current match summary
- Upgrade status

The listing analyzer adds:

- Listing title, URL, seller/source notes, price, shipping, and total cost
- Parsed candidate fields from pasted text
- Ownership, duplicate, upgrade, WANT_LIST, collection impact, priority score, max rational price, and listing recommendation
- Offline URL storage only; no scraping or network requests

The collection dashboard adds:

- Collection snapshot counts
- Top collection priorities
- Best upgrade opportunities
- WANT_LIST priorities
- Collection gaps
- Series completion percentages from actual collection data
- Basic collection evolution from available `date_added` values
- CSV and Markdown export

The collection quality engine adds:

- Overall Quality Score
- Completeness, Upgrade, WANT_LIST Progress, Diversity, and Certification scores
- Data-driven strengths and weaknesses
- Ranked recommended actions with why they matter and expected impact
- Supporting metrics for future acquisition-impact work
- CSV and Markdown export

The acquisition impact engine adds:

- Acquisition Impact Score from 0 to 100
- LOW/MEDIUM/HIGH/MAJOR collection impact categories
- Quality score before/after and delta
- Series completion before/after and delta
- WANT_LIST completion impact
- Upgrade opportunity impact
- Recommendation reasoning for Listing Analyzer output

The series tracker adds:

- Supported series definitions outside business logic
- Owned date and missing date tracking
- Completion percentage from actual observed collection data
- WANT_LIST target highlighting
- Upgrade count integration
- Series priority score
- Dashboard Top Series panel
- Acquisition Impact series priority metrics

The photo vault adds:

- Metadata-only photo records
- Collection, candidate, reference, auction, and sold photo types
- Collection item and candidate linking
- Optional ICCS, PCGS, and NGC certification numbers
- Deterministic search by cert number, file name, coin name, and notes
- Collection photo coverage metrics
- CSV and Markdown export

The market awareness layer adds:

- Observed price records
- Purchase records
- Sale records
- Auction records with Won/Lost/Passed status
- Local market summary averages and counts
- Historical observed-price context for acquisition impact
- Photo Vault reference identifiers on market records
- CSV and Markdown export

The smart shopping assistant adds:

- ShoppingCandidate inputs for manual opportunities, Listing Analyzer candidates, WANT_LIST targets, and Market Awareness observations
- Ranked ShoppingRecommendation output
- Best Next Purchase
- Highest Impact Candidate
- Highest Priority WANT_LIST Target
- STRONG BUY, BUY, NEGOTIATE, WATCH, PASS, and REVIEW statuses
- Local market-context reasoning without scraping or forecasting
- Dashboard shopping summary panel
- CSV and Markdown export

The collector operating system adds:

- CollectorHome for a unified collector-facing entry point
- CollectionHealthReportEngine for strengths, weaknesses, priorities, actions, series, shopping, market, and persistence reporting
- Deterministic persistence findings for collection JSON, Shared Session Context, Market Awareness, Photo Vault, Series Definitions, and Shopping Assistant candidates
- Tools -> Collector Home and Tools -> Collection Health Report
- CSV and Markdown export

The persistence layer adds:

- PersistenceManager for local JSON app-state storage
- AppState and PersistenceResult structured outputs
- Save, load, clear, validate, backup, import, and export operations
- Default state file at `collection_data/app_state/app_state.json`
- Timestamped backups under `collection_data/app_state/backups/`
- Round-tripping for SessionContext metadata, LegacyWantListIntent rows, Market Awareness records, PhotoRecord rows, ShoppingCandidate rows, and app preferences

The data safety and backup layer adds:

- BackupManager for local zip backup packages
- BackupManifest with collection JSON/workbook/app-state recovery flags, included, excluded, missing files, warnings, restore notes, sizes, and SHA-256 checksums
- DataSafetyValidator and DataSafetyReport for PASS/WARNING/FAIL validation
- CollectionRecoveryReport for recoverable and not-recoverable collection ownership data
- Safe restore of known app-state paths and `data/collection.json` with pre-restore backup
- Collector Export Bundle with health report, shopping recommendations, market summary, series summary, photo coverage summary, and manifest

The collection integrity layer adds:

- CollectionIntegrityAudit for read-only trust checks across collection records and related local metadata
- CollectionIntegrityReport with integrity score, findings, warnings, recommendations, and Markdown/CSV export
- Duplicate ownership detection by country, denomination, and year
- Missing/invalid ownership field checks
- Photo, market, certification, shopping-candidate, persistence, and backup-readiness checks
- Tools -> Collection Integrity Audit

The collection snapshot layer adds:

- CollectionSnapshot for point-in-time metrics
- CollectionSnapshotManager for create, save, load, and compare operations
- CollectionSnapshotReport for current/previous/first snapshot comparison
- GrowthSummary and SeriesProgressDelta outputs
- Persistent local snapshot storage under `collection_data/app_state/collection_snapshots.json`
- Tools -> Create Snapshot and Tools -> Snapshot Report
- CSV and Markdown export

The mobile readiness layer adds:

- MobileReadinessReport for future mobile planning without building a mobile app
- Desktop dependency audit for Tkinter, file dialogs, workbook loading, exports, photo workflows, and persistence workflows
- Service boundary review for Collection Intelligence, Listing Analyzer, Smart Shopping Assistant, Collection Dashboard, Collection Health Report, Persistence Layer, and Backup Manager
- Mobile input readiness findings for manual candidate entry, pasted listing text, pasted URLs, photo references, and persisted context
- Documentation-only API mapping for `analyze_candidate`, `collection_health`, `shopping_recommendations`, and `dashboard_summary`
- Dealer-table phone workflow audit for reaching BUY/PASS guidance from a candidate coin and asking price
- Mobile Readiness Score across architecture, workflow, persistence, exports, and inputs

The mobile companion layer adds:

- MobileCandidateEntry for title, asking price, shipping, notes, URL, photo reference ID, and source
- MobileAnalysisReport for concise recommendation, impact score, quality delta, series delta, WANT_LIST status, top reason, summary, warnings, and max rational price
- MobileCompanionWorkflow for candidate -> analysis -> recommendation using existing engines
- Desktop StorageProvider, PhotoProvider, and ExportProvider abstraction points
- PhoneWorkflowSimulation and PhoneWorkflowReport for coin-shop dealer-table workflow checks
- Dashboard mobile summary and app-state persistence for recent mobile activity

The photo-assisted entry layer adds:

- PhotoCandidate for title, front photo, reverse photo, reference photo paths, notes, asking price, source, timestamp, candidate ID, and workflow state
- PhotoAssistedEntry for creating candidates, linking photo paths through Photo Vault metadata, and routing analysis through Mobile Companion
- PhotoReviewReport for attached photos, candidate details, recommendation context, warnings, and CSV/Markdown export
- App-state persistence for photo candidate metadata
- Metadata-only backup compatibility through existing app-state backup packages

The photo vault hardening layer adds:

- PhotoVaultIntegrityAudit for report-only photo metadata trust checks
- PhotoCoverageReport for total records, valid references, missing references, duplicates, collection coverage, certified-item coverage, and candidate coverage
- PhotoVaultIssue for exportable issue rows with issue type, severity, reference, path, photo type, and recommendation
- Tools -> Photo Vault Audit with Markdown and CSV export
- Data Safety and Collection Recovery messaging for photo metadata backup limitations

The shopping explainability layer adds:

- RecommendationConfidence for deterministic High, Medium, and Low confidence labels
- RecommendationExplanation for primary reasons, supporting reasons, impact summary, warnings, and collector notes
- ExplainableRecommendationReport with Markdown and CSV export
- ShoppingExplanationEngine for existing Smart Shopping, Listing Analyzer, and Acquisition Workflow outputs
- Smart Shopping and Listing Analyzer display integration without changing recommendation outcomes

The OCR experiment layer adds:

- OCRResult for raw OCR text, image path, engine metadata, timestamp, and warnings
- OCRConfidence for deterministic High, Medium, and Low confidence labels
- OCRSuggestionReport for possible years, denominations, countries, note prefixes, certification numbers, warnings, manual-review status, and CSV/Markdown export
- OCRExperiment for optional local OCR execution, raw-text suggestion extraction, and helper integrations with PhotoCandidate, PhotoRecord, and MobileCandidateEntry
- Tools -> OCR Experiment for displaying raw OCR output, extracted suggestions, confidence, and warnings

The OCR validation layer adds:

- OCRValidationEngine for deterministic OCR trust assessment
- OCRValidationReport for findings, trust level, validation score, warnings, explanations, and review recommendations
- OCRTrustLevel values: HIGH, MEDIUM, and LOW
- OCRValidationScore with strengths, weaknesses, and recommended actions
- OCRValidationExplanation for why a trust level was assigned
- Year, denomination, country, certification, confidence, ambiguity, and source-warning checks

The workflow integration layer adds:

- CollectorWorkflowEngine as a facade for guided collector workflows
- AcquisitionWorkflow for Photo -> Photo-Assisted Entry -> OCR Experiment -> OCR Validation -> Smart Shopping -> Shopping Explainability -> Save Candidate review
- CollectionReviewWorkflow for Collection Dashboard -> Collection Quality -> Collection Integrity -> Snapshot Review -> Recommended Actions
- PhotoReviewWorkflow for Photo Vault -> Photo Vault Audit -> Coverage Review -> Missing Photo Actions
- CollectorDailySummary for a daily "what should I do today?" task list
- WorkflowStatus and WorkflowSummary for lightweight state tracking and persistence
- CSV and Markdown exports for workflow reports

Supported statuses:

- `ALREADY_OWNED`
- `BETTER_GRADE_UPGRADE`
- `SAME_GRADE_DUPLICATE`
- `LOWER_GRADE_DUPLICATE`
- `WANT_LIST_MATCH`
- `COLLECTION_GAP`
- `NOT_RELEVANT`
- `NEEDS_REVIEW`

## Guardrails

- Do not add OCR, image recognition, scraping, or market-price automation as part of this engine.
- Keep this engine deterministic and testable.
- Do not modify `data/collection.json` from analysis workflows.
- Do not treat Market Awareness as live pricing; it is local personal market memory only.
- Smart Shopping Assistant must reuse Acquisition Workflow and Acquisition Impact for decision source and scoring context; do not duplicate owned/duplicate/upgrade classification logic.
- Collector Operating System must compose existing engines and reports; do not create a second decision source for ownership, upgrades, acquisition impact, shopping, quality, series, market, or photo coverage.
- Persistence must not modify collection workbook contents or production `data/collection.json`; it stores app runtime state and paths only.
- Backup/restore must validate before restore, create pre-restore backups, include `data/collection.json` in backup packages when available, copy but never modify collection workbooks, and avoid silently overwriting collection workbooks or production collection ownership data.
- Collection Integrity Audit must remain report-only; it must not automatically edit, delete, normalize, or merge collection records.
- Collection Snapshot System must remain historical/reporting-only; it must not modify collection records, infer future trends, or change recommendation logic.
- Mobile Readiness must remain audit/documentation/scoring only; do not build a mobile app, web app, API server, OCR flow, scraper, live pricing, or Numista integration under this release line.
- Mobile Companion must remain a local desktop prototype; do not add native mobile code, web app code, API server code, OCR, image recognition, scraping, live pricing, cloud sync, or a new database.
- Mobile Companion must reuse existing acquisition and impact engines; do not create duplicate ownership, upgrade, duplicate, or recommendation logic.
- Photo-Assisted Entry must remain metadata-only. Do not move, copy, inspect, OCR, classify, or grade photo files.
- Photo-Assisted Entry must reuse Photo Vault, Mobile Companion, and existing acquisition engines; do not create a second recommendation source.
- Photo Vault Audit must remain report-only. Do not automatically move, delete, rename, repair, OCR, classify, inspect, or grade image files.
- Shopping Explainability must remain explanation-only. Do not change recommendation thresholds, rankings, prices, duplicate logic, ownership logic, or acquisition-impact calculations.
- OCR Experiments must remain advisory-only. Do not let OCR modify collection records, create ownership entries, update grades, change recommendations, auto-buy, alter shopping rankings, or bypass manual review.
- OCR Validation must remain a trust/reporting layer only. Do not let validation upgrade OCR suggestions into authoritative collection data or change recommendations.
- Workflow Integration must remain orchestration-only. Do not add new recommendation logic, new grading logic, scraping, APIs, live pricing, background jobs, or automatic collection updates.
- Deal Hunter must remain offline and deterministic. Do not scrape, use browser automation, fetch live listing pages, require eBay API credentials, claim live market-pricing accuracy, or mutate collection records. Risk flags and parser signals are manual-review guidance, not live market truth.
- Opportunity Engine must remain offline and deterministic. Do not use it to add scraping, browser automation, APIs, live pricing, market prediction, image recognition, automatic purchasing, or collection mutation.
- Deal Hunter Ranking must remain offline and deterministic. It may rank supplied local candidate pools and CSV imports, but it must not fetch listings, scrape websites, use eBay APIs, use browser automation, claim live market-pricing accuracy, purchase automatically, recognize images, or mutate collection records.
- External Listing Connectors must remain offline local-file adapters only. Do not add scraping, browser automation, eBay APIs, dealer APIs, auction APIs, live fetching, live pricing, automatic purchasing, image recognition, or collection mutation in this layer.
- Deal Hunter Calibration must remain an offline quality-control layer. Do not use it to fetch listings, scrape sites, call APIs, claim live market-pricing accuracy, purchase automatically, recognize images, or mutate collection records.
- Live Deal Hunter Readiness must remain contracts, validation, and reporting only. Do not add scraping, browser automation, APIs, live listing retrieval, background fetching, automatic purchasing, live pricing claims, image recognition, or collection mutation in this layer.
- Market Intelligence must remain deterministic local guidance only. Do not add scraping, browser automation, APIs, live listing retrieval, live market-price claims, automatic purchasing, image recognition, or collection mutation.
- Portfolio Performance must remain deterministic local collection-development reporting only. Do not add investment advice, scraping, APIs, live pricing, market forecasting, automatic purchasing, or collection mutation.
- Keep Buy Advisor, Upgrade Advisor, Want List Generator, Collection Gap Report, and import previews stable unless the active task explicitly targets them.
- Every completed version must end with implementation, acceptance audit, tag creation, and push verification.
- A version is not complete until its release tag exists locally and remotely and both tag targets are verified.
- Never leave a completed version untagged.

## Test Status

- `run_tests.bat`: 694 tests OK for the v6.1 Sync & Backup release line.
- Coverage note: total passing tests increased from 571 to 579; existing regression suites remained green.
- Targeted Portfolio Performance, Snapshot, Collection Intelligence, Opportunity Engine, and Market Intelligence block: 50 tests OK.
- Targeted Market Intelligence tests: 11 tests OK.
- Targeted Market Intelligence, Deal Hunter, Opportunity, Ranking, Connector, and Calibration regression block: 86 tests OK.
- Targeted Deal Hunter Calibration tests: 12 tests OK.
- Targeted Deal Hunter, Deal Hunter Ranking, Opportunity Engine, and Listing Connector regression block: 63 tests OK.
- Targeted External Listing Connectors, Deal Hunter Ranking, Deal Hunter, Opportunity Engine, Collection Intelligence, Focused Collection Intelligence, and Smart Shopping regression block: 125 tests OK.
- Targeted External Listing Connectors tests: 11 tests OK.
- Targeted Deal Hunter Ranking, Deal Hunter, Opportunity Engine, Collection Intelligence, Focused Collection Intelligence, and Smart Shopping regression block: 114 tests OK.
- Targeted Deal Hunter Ranking tests: 12 tests OK.
- Targeted Opportunity Engine, Deal Hunter, Smart Shopping, Acquisition Impact, Collection Intelligence, and Focused Collection Intelligence regression block: 111 tests OK.
- Targeted Opportunity Engine tests: 10 tests OK.
- Targeted Deal Hunter tests: 30 tests OK.
- Targeted Deal Hunter, Smart Shopping, Acquisition Impact, Collection Intelligence, and Market Awareness regression block: 109 tests OK.
- Targeted Collector Workflow tests: 7 tests OK.
- Targeted OCR Validation tests: 11 tests OK.
- Targeted OCR Experiment tests: 11 tests OK.
- Targeted Shopping Explainability tests: 12 tests OK.
- Targeted Photo Vault tests: 18 tests OK.
- Targeted Backup tests: 22 tests OK.
- Targeted Photo-Assisted Entry tests: 8 tests OK.
- Targeted Collection Snapshot tests: 9 tests OK.
- Targeted Collection Integrity tests: 14 tests OK.
- Targeted Backup/Persistence tests: 33 tests OK.
- Targeted Mobile Companion tests: 17 tests OK.
- Targeted Mobile Readiness tests: 9 tests OK.
- GUI smoke for Do I Own This, Buy Advisor, Upgrade Advisor, Want List Generator, Collection Gap Report, and Portfolio Import Preview passed.
- Export smoke for collection CSV, gap CSV, want-list CSV/Markdown, portfolio preview CSV, and WANT_LIST preview CSV passed.
- Tag metadata verified through `v1.2`; `v1.2` points to `db001da4187af5a2bd2350bd956b2876007f7587`.
- Local GUI smoke for v1.1 could not run because this Python/Tcl install cannot find `init.tcl`.
- Local GUI smoke for v1.3 also could not run because this Python/Tcl install cannot find `init.tcl`; dashboard and GUI module imports passed.
- Local GUI smoke for v1.4 also could not run because this Python/Tcl install cannot find `init.tcl`; quality/dashboard/GUI module imports passed.
- Local GUI smoke for v1.5 also could not run because this Python/Tcl install cannot find `init.tcl`; imports and non-GUI impact/listing/dashboard checks passed.
- Local GUI smoke for v1.6 also could not run because this Python/Tcl install cannot find `init.tcl`; imports, tracker reports, and non-GUI dashboard/impact checks passed.
- Local GUI smoke for v1.7 also could not run because this Python/Tcl install cannot find `init.tcl`; imports, photo vault lookups, and non-GUI dashboard coverage checks passed.
- Local GUI smoke for v1.8 also could not run because this Python/Tcl install cannot find `init.tcl`; imports, market context checks, exports, dashboard integration, and full non-GUI regression suite passed.
- Local GUI smoke for v1.9 also could not run because this Python/Tcl install cannot find `init.tcl`; imports, ranking checks, exports, dashboard integration, and full non-GUI regression suite passed.
- Local GUI smoke for v2.0 also could not run because this Python/Tcl install cannot find `init.tcl`; imports, consolidated report generation, exports, targeted integration tests, and full non-GUI regression suite passed.
- Local GUI smoke for v2.1 also could not run because this Python/Tcl install cannot find `init.tcl`; imports, persistence round-trips, schema validation, backups, targeted integration tests, and full non-GUI regression suite passed.
- Local GUI smoke for v2.2 also could not run because this Python/Tcl install cannot find `init.tcl`; imports, backup package checks, restore checks, data-safety reports, export bundles, targeted integration tests, and full non-GUI regression suite passed.
- Direct multi-module `py -m unittest ...` commands may still hit the intermittent Windows launcher issue; use `run_tests.bat` as the project runner.

## Known Limitations

- Fuzzy matching is deterministic and intentionally basic.
- Variety matching depends on existing text fields such as reference, title, notes, and comments.
- Shared Session Context metadata can be saved to local app state. Restoring workbook-backed previews still requires the referenced workbook to exist.
- Buy Advisor still keeps its legacy collection-intelligence boost scoring separate from duplicate/upgrade classification to preserve current user-visible behavior.
- Acquisition workflow max rational price is rule-based internal guidance only; it is not market pricing.
- Listing Analyzer parsing is intentionally basic and requires manual review for ambiguous listing titles.
- Listing URLs are stored as reference data only; no website fetches, scraping, enrichment, or market-price lookups occur.
- Collection Dashboard does not estimate unknown values and depends on available collection fields for certified counts and collection evolution.
- Collection Quality Engine uses deterministic internal scoring only; it does not use rarity guides, market pricing, population reports, OCR, scraping, or Numista expansion.
- Acquisition Impact Engine is deterministic planning guidance only; it does not modify collection data or use market pricing, rarity guides, scraping, OCR, or Numista expansion.
- Series Tracker definitions identify supported series; they do not contain fabricated master mintage checklists. Completion is based on actual owned dates and missing years inside observed owned spans.
- Photo Vault is metadata-only. It does not move files automatically and does not perform OCR, image recognition, AI grading, scraping, or Numista lookups.
- Photo-Assisted Entry stores photo paths and metadata only. It does not move files automatically and does not perform OCR, image recognition, AI grading, scraping, or Numista lookups.
- Photo Vault Audit stores and reports metadata only. Backup packages preserve photo metadata in app state but do not copy arbitrary photo folders.
- Shopping Explainability is a translation/reporting layer only; it does not modify recommendation outcomes or use AI confidence.
- OCR Experiments are advisory-only and manual-review-only. Local OCR runtime availability may vary; missing OCR runtime or missing images should produce warnings, not crashes.
- OCR Validation detects ambiguity and conflicts but does not resolve attribution; collector review is still required for all OCR-derived values.
- Workflow Integration coordinates existing systems and stores lightweight summaries/statuses only; it does not make final collector decisions or write collection ownership records.
- Collector Home Dashboard surfaces existing status/report outputs only; it does not add recommendation logic, mutate ownership data, run OCR, scrape, call APIs, grade images, create background jobs, or replace existing tools.
- Collector Companion Readiness and Status are audit/reporting layers only; they do not add recommendation logic, mutate ownership data, run OCR, scrape, call APIs, grade images, create background jobs, or replace existing tools.
- Deal Hunter recommendations are deterministic local guidance only. Max rational price is not live market pricing, appraisal, or a guarantee of value. CSV import warnings and risk flags reduce silent failure, but ambiguous listings still require collector review.
- Opportunity Engine scores supplied/generated opportunities only. Unpriced opportunities receive budget-fit review warnings, and all recommendations include counterarguments.
- Deal Hunter Ranking scores supplied/generated local candidate pools only. Import profiles are offline CSV mapping frameworks, not connectors, scrapers, or APIs.
- External Listing Connectors normalize supplied local CSV files only. Connector validation reports help review import quality, but ambiguous rows and likely duplicate opportunities still require collector review.
- Deal Hunter Calibration compares supplied offline expectations against deterministic recommendations/rankings only. Calibration fixtures are fake local test scenarios, not live market data.
- Live Deal Hunter Readiness defines future source contracts and validation reports only. `LiveListingSource.fetch_listings()` intentionally raises `NotImplementedError` in v3.7.
- Market Intelligence estimates fair-value bands from supplied/local comparable rows and existing internal deal guidance only. It does not appraise coins, retrieve live values, predict markets, or guarantee value.
- Portfolio Performance is not investment advice. It reports local collection growth, health, progress, and focus areas from existing records and snapshots only.
- Market Awareness is local recordkeeping only. It does not scrape, fetch URLs, call pricing APIs, predict market values, or estimate prices from external data.
- Smart Shopping Assistant ranks opportunities from supplied local/manual inputs and existing staged context only; it does not scrape, fetch listings, forecast prices, or create market estimates.
- Collector Home, Collector Home Dashboard, and Collection Health Report are consolidation/reporting layers only; they do not modify collection records.
- Persistence stores local JSON state only; no cloud sync, database server, credentials, scraping, APIs, or workbook mutation.
- Backup packages are local zip files only; keep off-machine backups separately and continue storing collection workbooks in known backed-up locations.
- Workbook copy coverage depends on the persisted workbook path saved in app state. If the workbook path is missing or stale, backup continues and reports a warning.
- GUI workflows still have limited automated coverage.

## Recommended Next Steps

1. Complete v4.0 Live Deal Hunter (Controlled Beta) with explicit user-triggered fetching, one public RSS source boundary, validation, ranking, reporting, and no purchase/bid/background/mutation behavior.
2. Improve Buy Advisor validation messages.
3. Add GUI autocomplete for country and denomination.
4. Improve photo URI/file-picker abstractions before a true companion UI.
5. Keep calibration fixtures current as new offline source formats or ranking behaviors are added.
