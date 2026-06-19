# AI Handoff

## Snapshot

- Date: 2026-06-19
- Branch: `main`
- Current project state file reports release version: `v2.8`
- Current active task completed: v2.8 Collector Home Dashboard

## Official v2.7-to-v3.0 Roadmap

1. `v2.7` Workflow Integration
2. `v2.8` Collector Home Dashboard
3. `v2.9` Collector Companion Release Candidate
4. `v3.0` Collector Companion

Clarification: `v2.8` is not a new recommendation engine. It is a workflow-surfacing milestone focused on showing existing collector status, actions, safety, review, progress, and opportunities in one place.

## What Changed

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
- Keep Buy Advisor, Upgrade Advisor, Want List Generator, Collection Gap Report, and import previews stable unless the active task explicitly targets them.
- Every completed version must end with implementation, acceptance audit, tag creation, and push verification.
- A version is not complete until its release tag exists locally and remotely and both tag targets are verified.
- Never leave a completed version untagged.

## Test Status

- `.\run_tests.bat`: 463 tests OK for the v2.8 Collector Home Dashboard release line.
- Coverage note: total passing tests increased from 451 to 463; existing regression suites remained green.
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
- Market Awareness is local recordkeeping only. It does not scrape, fetch URLs, call pricing APIs, predict market values, or estimate prices from external data.
- Smart Shopping Assistant ranks opportunities from supplied local/manual inputs and existing staged context only; it does not scrape, fetch listings, forecast prices, or create market estimates.
- Collector Home, Collector Home Dashboard, and Collection Health Report are consolidation/reporting layers only; they do not modify collection records.
- Persistence stores local JSON state only; no cloud sync, database server, credentials, scraping, APIs, or workbook mutation.
- Backup packages are local zip files only; keep off-machine backups separately and continue storing collection workbooks in known backed-up locations.
- Workbook copy coverage depends on the persisted workbook path saved in app state. If the workbook path is missing or stale, backup continues and reports a warning.
- GUI workflows still have limited automated coverage.

## Recommended Next Steps

1. Prepare v3.0 Collector Companion planning.
2. Improve photo URI/file-picker abstractions before a true companion UI.
3. Improve Buy Advisor validation messages.
4. Add GUI autocomplete for country and denomination.
5. Keep OCR advisory-only unless a future release explicitly expands the reviewed workflow.
