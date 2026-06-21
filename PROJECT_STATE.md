# Project State

## Current Version

* Current release version: `v3.9`
* Current Git branch: `main`
* Last updated date: 2026-06-21

## Last Release Tag

* Most recent Git tag: `v3.9`
* Summary of what was included: Portfolio Performance with deterministic collection growth analysis, acquisition performance, series progress, budget allocation, health score, snapshot comparison, Tools -> Portfolio Performance, CSV/Markdown export, and 579-test regression pass.
* `v0.3` release audit passed on 2026-06-15.
* `v0.4` integration audit passed on 2026-06-15; no defects required code fixes.
* `v0.4` release tests passed on 2026-06-15: 47 OK.
* `v0.5` release audit passed on 2026-06-15; no release-blocking defects found.
* `v0.5` release audit rerun passed on 2026-06-16; no release-blocking defects found.
* `v0.6` release audit passed on 2026-06-15; no release-blocking defects found.
* `v0.7` acceptance audit passed on 2026-06-16; tag `v0.7` points to `3cf26ff6b07e7d0d39b4ff62a410bf753dece5c0`.
* `v0.8` acceptance audit passed on 2026-06-16; tag `v0.8` points to `f3acc605024712a867046be24e3c32db3f18d854`.
* `v0.9` acceptance audit passed on 2026-06-16; tag `v0.9` points to `af09668dd9b735479a0885445a7198302d6432f3`.
* `v1.0` release-readiness audit passed on 2026-06-16; tag `v1.0` points to `2c3d68bc65fcb2f3787f9a3d7624bd49675684c7`.
* `v1.1` acceptance audit passed on 2026-06-16; tag `v1.1` points to `0fd5e1fbe5807cf8889cee3ea94d5752acfdf06e`.
* `v1.2` acceptance audit passed on 2026-06-16; tag `v1.2` points to `db001da4187af5a2bd2350bd956b2876007f7587`.
* `v1.3` acceptance audit passed on 2026-06-16; tag `v1.3` points to `dfbea9bd93e617e3b3a0067d56e15b3d14c69c1e`.
* `v1.4` acceptance audit passed on 2026-06-16; tag `v1.4` points to `7cc5a7cc4b0e99a01e7515b89d11089461ea097d`.
* `v1.5` acceptance audit passed on 2026-06-16; tag `v1.5` points to `080b70b106e19de0739fab172993846999edb2bd`.
* `v1.6` acceptance audit passed on 2026-06-17; tag `v1.6` points to `09b201cb0a5f394c957af48081e10e7f200b8533`.
* `v1.7` acceptance audit passed on 2026-06-17; tag `v1.7` points to `b650a141e1061979506f19402360239d69f68073`.
* `v1.8` acceptance audit passed on 2026-06-17; tag `v1.8` points to `425fb2597b95e410e4c9c49465dd8b12e080ace3`.
* `v1.9` acceptance audit passed on 2026-06-18; tag `v1.9` points to `bf7e33648e6d150ffa7193cdddbbe493cb50c7fb`.
* `v2.0` acceptance audit passed on 2026-06-18; tag `v2.0` points to `a661b06c846bdd0d5342ce892c350832c8907974`.
* `v2.1` acceptance audit passed on 2026-06-18; tag `v2.1` points to `bd4897fbee4f8306b69fb369a2e81768631fb865`.
* `v2.2` acceptance audit passed on 2026-06-18; tag `v2.2` points to `d84aa40334a6c3f859a996006bfe8005074ea6a4`.
* `v2.3` acceptance audit passed on 2026-06-18; tag `v2.3` verified during release.
* `v2.4` acceptance audit passed on 2026-06-18; tag `v2.4` verified during release.
* `v2.4.1` acceptance audit passed on 2026-06-18; tag `v2.4.1` verified during release.
* `v2.4.2` acceptance audit passed on 2026-06-18; tag `v2.4.2` verified during release.
* `v2.4.3` acceptance audit passed on 2026-06-18; tag `v2.4.3` verified during release.
* `v2.5` acceptance audit passed on 2026-06-18; tag `v2.5` verified during release.
* `v2.5.1` acceptance audit passed on 2026-06-18; tag `v2.5.1` verified during release.
* `v2.5.2` acceptance audit passed on 2026-06-19; tag `v2.5.2` verified during release.
* `v2.6` acceptance audit passed on 2026-06-19; tag `v2.6` verified during release.
* `v2.6.1` acceptance audit passed on 2026-06-19; tag `v2.6.1` verified during release.
* `v2.7` acceptance audit passed on 2026-06-19; tag `v2.7` verified during release.
* `v2.8` acceptance audit passed on 2026-06-19; tag `v2.8` verified during release.
* `v2.9` acceptance audit passed on 2026-06-19; tag `v2.9` verified during release.
* `v3.0` acceptance audit passed on 2026-06-19; tag `v3.0` verified during release.
* `v3.1` acceptance audit passed on 2026-06-20; tag `v3.1` verified during release.
* `v3.2` acceptance audit passed on 2026-06-21; tag `v3.2` verified during release.
* `v3.3` acceptance audit passed on 2026-06-21; tag `v3.3` verified during release.
* `v3.4` acceptance audit passed on 2026-06-21; tag `v3.4` verified during release.
* `v3.5` acceptance audit passed on 2026-06-21; tag `v3.5` verified during release.
* `v3.6` acceptance audit passed on 2026-06-21; tag `v3.6` verified during release.
* `v3.7` acceptance audit passed on 2026-06-21; tag `v3.7` verified during release.
* `v3.8` acceptance audit passed on 2026-06-21; tag `v3.8` verified during release.
* `v3.9` acceptance audit passed on 2026-06-21; tag `v3.9` verified during release.

## Completed Features

* Desktop collection manager: Tkinter GUI for adding, editing, deleting, viewing, and searching coin records.
* JSON collection storage: stores collection data in `data/collection.json`.
* Numista Excel import: imports Numista `.xlsx` exports with field mapping and duplicate detection.
* CSV import: imports simple collection CSV files with quantity expansion.
* CSV export: exports collection records with core and Numista fields.
* Collection analysis: summarizes countries, years, denominations, and Numista coverage.
* Buy Advisor: provides rule-based purchase recommendations, price checks, priority scoring, liquidity scoring, and collection-intelligence impact scoring.
* Manual entry support: allows manually entered collection items and basic autocomplete suggestions from Numista-backed data.
* Experimental image detection: CV/OCR-based identification exists but is suggestion-only and not treated as truth.
* Test infrastructure: root-level `unittest` discovery, isolated `test_data` fixtures, `run_tests.bat`, `TESTING.md`, and GitHub Actions workflow.
* Task queue: `TASK_QUEUE.md` tracks prioritized work, status, and changelog entries.
* Collection Intelligence Engine: reusable analysis for country, denomination, series, missing years, completion percentages, duplicates, upgrade candidates, and acquisition priorities.
* Focused Collection Intelligence Engine: deterministic manual candidate evaluation that classifies owned matches, upgrades, duplicates, want-list matches, collection gaps, unrelated items, and review-needed cases without modifying collection data.
* Collection Gap Report MVP: Tools menu report grouped by country/denomination, with missing dates, completion percentages, priority tiers, suggested next acquisitions, duplicate/upgrade context, and Markdown/CSV export.
* Want List Generator MVP: ranked acquisition targets with estimated impact, explainable recommendation reasons, Markdown/CSV export, and optional staged `WANT_LIST` intent input.
* Auction Evaluator draft spec: documents how the future evaluator should consume the Collection Intelligence Engine.
* Legacy portfolio import spec: documents how `Adam_Collection_Portfolio_PRO_LEVEL.xlsx` should be staged, mapped, and consumed by future app systems.
* Portfolio integration roadmap: phases the legacy workbook migration from safe inventory staging through dashboard replacement.
* Legacy portfolio staging importer: safely previews `CORE_RAW` and `SLABS` workbook rows, detects likely duplicates, reports skipped rows and warnings, and does not modify `data/collection.json`.
* Portfolio Import Preview GUI: Tools menu workflow for selecting a legacy workbook, reviewing staged items and duplicates, seeing import summary counts, and exporting the preview report to CSV without importing data.
* WANT_LIST integration plan: documents the v0.4 Phase 2 approach for staging workbook acquisition intent without importing owned holdings.
* Legacy WANT_LIST staging parser: safely parses workbook `WANT_LIST` rows into acquisition-intent records without creating owned `CoinItem` records or modifying `data/collection.json`.
* WANT_LIST Preview GUI: Tools menu workflow for selecting a legacy workbook, reviewing staged acquisition-intent rows, skipped rows, warnings, and exporting the preview to CSV without modifying collection data.
* WANT_LIST-backed generator ranking: Tools -> Want List Generator can load staged workbook `WANT_LIST` intent and blend it with collection gaps and upgrade candidates without modifying collection data.
* Buy Advisor collection-intelligence integration: Buy Advisor can use collection gaps, generated want-list targets, and staged `WANT_LIST` intent as explainable Adam Priority boosts without changing duplicate or price analysis.
* Advisor decision-source consolidation: Buy Advisor duplicate/upgrade flags and Upgrade Advisor match/upgrade decisions now route through the focused Collection Intelligence Engine while preserving existing scoring, pricing, melt-value, and user-visible verdict behavior.
* Buy Advisor low-priority world guardrail: prevents low-priority world base-metal coins with negative Adam Priority, no collection impact, and no liquidity support from becoming `BUY NOW` solely because price is good.
* Upgrade Advisor: evaluates candidate coins against existing collection for upgrade potential, with grade improvement, value improvement, and Adam-specific priority scoring (Newfoundland, Canadian silver, 1859 Large Cents). Provides verdicts (Strong Upgrade, Upgrade, Hold Existing, Duplicate, Pass) with human-readable explanations. Read-only analysis with GUI integration (Tools → Upgrade Advisor) and CSV export.
* Melt Value Engine: calculates silver coin melt values using ASW (Actual Silver Weight) reference data from legacy workbook. Supports manual spot price input with optional API-based spot price provider with 24-hour caching and fallback logic. Integrated into Buy Advisor and Upgrade Advisor as supporting factor for silver coin analysis.
* Portfolio Dashboard: high-level collection health overview showing total items, countries, estimated value, melt value, Newfoundland progress, Canadian silver progress, 1859 Large Cent progress, top gap-fill targets, top upgrade targets, duplicate-heavy areas, and WANT_LIST progress. GUI integration (Tools → Portfolio Dashboard) with CSV and Markdown export.
* Do I Own This lookup: Tools menu entry for read-only manual candidate analysis using the focused Collection Intelligence Engine.
* Do I Own This WANT_LIST awareness: the lookup can load staged workbook `WANT_LIST` context, report whether a candidate is on the want list, not on the want list, or a collection gap not explicitly targeted, and keep analysis read-only.
* Acquisition Workflow: reusable deterministic purchase guidance service built on the focused Collection Intelligence Engine. It provides max rational price, BUY/PASS/WATCH/NEGOTIATE/REVIEW recommendations, confidence, reasons, and warnings without live pricing, scraping, OCR, image recognition, or Numista expansion.
* Shared Session Context: per-session workbook and WANT_LIST context layer that lets Do I Own This, Acquisition Workflow, Buy Advisor, Want List Generator, Portfolio Import Preview, and related tools reuse one loaded context while preserving manual file-selection fallbacks.
* Listing Analyzer: offline pasted-listing workflow that stores URL reference data, parses basic listing text into a candidate, and reuses Shared Session Context, Collection Intelligence, WANT_LIST context, and Acquisition Workflow to answer ownership, duplicate, upgrade, want-list, and buy/pass questions.
* Collection Dashboard: actionable read-only overview that combines collection snapshot counts, WANT_LIST opportunities, upgrade opportunities, collection gaps, series completion, and basic collection evolution into CSV/Markdown-exportable planning data.
* Collection Quality Engine: deterministic scoring engine that explains overall quality, completeness, upgrade pressure, WANT_LIST progress, diversity, certification, strengths, weaknesses, and recommended actions using only available collection data.
* Smarter Acquisition Intelligence: deterministic impact simulation that measures collection impact, quality score delta, completion delta, WANT_LIST impact, and upgrade impact for candidate purchases without modifying collection data.
* Series Tracker: deterministic supported-series progress reports for owned dates, missing dates, completion percentage, WANT_LIST targets, upgrade counts, priority score, CSV/Markdown export, Dashboard Top Series panel, and Acquisition Impact series metrics.
* Photo Vault: metadata-only photo record engine for collection, candidate, reference, auction, and sold photos with collection-item linking, candidate linking, certification-number lookup, deterministic search, coverage metrics, and CSV/Markdown export.
* Market Awareness Layer: local-only tracking for observed prices, purchases, sales, and auction outcomes with dashboard market summary, acquisition historical context, photo-reference links, and CSV/Markdown export.
* Smart Shopping Assistant: ranked purchasing recommendation workflow that combines listing/manual opportunities, WANT_LIST targets, acquisition workflow, acquisition impact, quality deltas, series completion, upgrade impact, local market context, and photo references into STRONG BUY/BUY/NEGOTIATE/WATCH/PASS/REVIEW guidance.
* Collector Operating System: unified Collector Home and Collection Health Report that consolidate collection snapshot, best next purchase, highest-impact opportunity, top WANT_LIST target, closest supported series, quality score, market activity, photo coverage, strengths, weaknesses, priorities, recommended actions, persistence findings, and CSV/Markdown exports.
* Persistence Layer: local JSON app-state manager that saves, loads, clears, validates, backs up, imports, and exports Shared Session Context metadata, workbook/WANT_LIST paths, Market Awareness records, Photo Vault records, Smart Shopping candidates, and app preferences.
* Data Safety and Backup Hardening: local backup packages with JSON/Markdown manifests, checksum verification, backup listing, safe restore with pre-restore backup, Data Safety reports, and Collector Export Bundles.
* Critical Collection Backup Hardening: backup packages now include `data/collection.json` by default, copy the persisted workbook path when available, expose recovery coverage flags in manifests, generate Collection Recovery Reports, and validate whether core ownership records are recoverable.
* Collection Integrity Audit: read-only integrity engine and Tools menu report for duplicate ownership records, missing/invalid ownership data, orphan photo references, orphan market records, certification issues, invalid persisted paths, backup readiness, integrity score, recommendations, and CSV/Markdown export.
* Collection Snapshot System: point-in-time snapshot engine and Tools menu workflows for measuring collection growth, quality score change, integrity score change, photo coverage change, supported-series completion progress, market record counts, shopping candidate counts, and CSV/Markdown export.
* Mobile Readiness: deterministic readiness audit layer that documents desktop dependency blockers, service boundaries, mobile input friction, future endpoint mappings, dealer-table phone workflow steps, mobile readiness scoring, and CSV/Markdown export without building a mobile app or API.
* Mobile Companion Prototype: local desktop prototype for minimal candidate entry, quick recommendation output, phone workflow simulation, provider abstraction points, dashboard mobile summary, persistence of recent mobile candidates/recommendations, and CSV/Markdown export without building a mobile app.
* Photo-Assisted Entry: metadata-only photo reference workflow for front, reverse, and reference photos attached to manually reviewed candidates, with Photo Vault linking, Mobile Companion recommendation reuse, persistence, backup-compatible metadata, Tools -> Photo-Assisted Entry, and CSV/Markdown export.
* Photo Vault Hardening: read-only Photo Vault integrity audit for missing files, duplicate references, unlinked metadata, invalid extensions, unsupported paths, collection/candidate/certified-item coverage, backup/recovery photo metadata messaging, Tools -> Photo Vault Audit, and CSV/Markdown export.
* Shopping Explainability: report-only explanation layer that translates existing shopping, listing, acquisition, and impact outputs into primary reasons, supporting reasons, confidence labels, impact summaries, warnings, collector notes, and CSV/Markdown exports without changing recommendation outcomes.
* OCR Experiments: advisory-only OCR workflow for image paths and pasted OCR text, with raw OCR output, possible years, denominations, countries, note prefixes, certification numbers, deterministic confidence, warnings, manual-review requirement, app-state persistence, Tools -> OCR Experiment, and CSV/Markdown export without modifying collection records or recommendation logic.
* OCR Validation Layer: deterministic trust layer for OCR output, with HIGH/MEDIUM/LOW trust levels, validation score, year/denomination/country/certification checks, findings, warnings, explanations, review recommendations, Tools -> OCR Experiment display integration, and CSV/Markdown export without changing OCR suggestions or collection/recommendation behavior.
* Workflow Integration: orchestration layer that coordinates existing Photo-Assisted Entry, OCR Experiments, OCR Validation, Smart Shopping, Shopping Explainability, Collection Dashboard, Collection Quality, Collection Integrity, Collection Snapshot, and Photo Vault Audit systems into guided acquisition, collection review, photo review, and daily summary workflows.
* Collector Home Dashboard: unified daily dashboard that surfaces Collection Health, Acquisition Focus, Review Queue, Data Safety, Progress, ranked Daily Collector Actions, top opportunities, warnings, workflow status, persistence, and CSV/Markdown export while reusing existing engines.
* Collector Companion Readiness and Status: v3.0 product audit system with menu grouping, V3 readiness checklist, export consistency report, report consistency report, end-to-end workflow audit, product status, persistence, and CSV/Markdown export.
* Deal Hunter: eBay.ca-style offline listing evaluator with manual/CSV input, deterministic title/description parsing, slab/banknote/keyword/grade-word detection, lot/problem-listing risk flags, collection-aware scoring, Adam buying rules, counterarguments before BUY, CSV import warnings, persistence, and CSV/Markdown export.
* Opportunity Engine: deterministic decision-support engine that answers "What should I buy next?" with top opportunities, budget recommendations, opportunity scores, reasoning, risks, counterarguments, Deal Hunter input support, and CSV/Markdown export.
* Deal Hunter Ranking and Import Framework: offline candidate-pool system that merges manual/CSV listings, validates import profiles, detects duplicate URLs/listings, ranks opportunities with Deal Hunter and Opportunity Engine context, produces budget/category views, and exports CSV/Markdown reports.
* External Listing Connectors: offline connector framework that normalizes eBay CSV, Auction CSV, Dealer Inventory CSV, and Generic CSV files into a common listing model with source tracking, validation reports, duplicate-opportunity detection, multi-source CandidatePool ranking compatibility, GUI import workflow, and CSV/Markdown export.
* Deal Hunter Calibration: offline calibration framework that compares expected collector judgment against Deal Hunter and Ranking output, detects false BUY/PASS/REVIEW outcomes, ranking misses, missing risk flags, and explanation gaps, and exports calibration reports without live-source ingestion.
* Live Deal Hunter Readiness: readiness and safety layer for future live listing ingestion with contract models, source validation reports, staleness flags, rate-limit policy models, failure models, no-fetch guardrails, GUI report workflow, and CSV/Markdown export.
* Market Intelligence: deterministic local fair-value and deal-quality analysis that reuses Deal Hunter, Opportunity Engine, Collection Intelligence, WANT_LIST context, and local Market Awareness records to explain value confidence, risks, counterarguments, and buy rationale without scraping, APIs, live pricing, purchasing, or collection mutation.
* Portfolio Performance: deterministic portfolio-level reporting that reuses snapshots, Collection Intelligence, Opportunity Engine, Market Intelligence context, Series Tracker, Quality, Integrity, and local Market Awareness records to explain growth, acquisition performance, series progress, budget allocation, collection health, risks, and focus areas without investment advice, live pricing, forecasting, or collection mutation.

## Known Bugs

* Direct multi-module `py -m unittest ...` commands can be flaky in this environment due to the Windows Python launcher; use `run_tests.bat` as the reliable suite command.
* GUI autocomplete currently prints suggestions to the console instead of showing a dropdown.
* Experimental detection and template matching are incomplete and should remain manual-verification-only.
* Numista API integration is not implemented and is blocked by API key, terms, pricing, and access review.
* JSON storage is simple and may not scale well for large collections.
* Many collection rows have no `Estimate (CAD)`, limiting Buy Advisor max-bid accuracy.
* No automated GUI tests currently cover Tkinter workflows.

## Active Roadmap

Official post-v3.8 roadmap:

1. `v3.8` Market Intelligence
2. `v3.9` Portfolio Performance
3. `v4.0` Live Deal Hunter
4. `v4.1` Live Source Validation
5. `v4.2` Market Intelligence Automation
6. `v5.0` Mobile Collector Companion

Roadmap rationale: the platform now contains Collection Intelligence, Deal Hunter, Opportunity Engine, Ranking Engine, Listing Connectors, and Calibration Framework. Before live listings are introduced, the system should better explain value, confidence, risk, and deal quality.

Post-v3.8 rationale: the platform can now evaluate opportunities, rank opportunities, explain opportunities, and calibrate recommendations. The next objective is understanding portfolio progress and collection development over time.

Clarification: `v3.4` remains offline and deterministic. It adds no scraping, browser automation, eBay API usage, live listing fetches, live market-pricing claims, market prediction, automatic purchasing, image recognition, or collection mutation.

Near-term maintenance candidates:

1. Improve Buy Advisor validation messages
2. Add autocomplete for country/denomination
3. Consider storage-provider, file-picker, export-destination, and photo URI adapters before mobile implementation
4. Consider a compact dealer-table candidate workflow after mobile storage abstractions exist
5. Decide whether acquisition workflow guidance should become visible in Buy Advisor reports
6. Expand normalization fixtures for country, denomination, and variety edge cases
7. Build Auction Evaluator implementation from `AUCTION_EVALUATOR_SPEC.md`
8. Add image preview in collection list
9. Add batch editing
10. Add undo/redo
11. Evaluate SQLite storage for larger collections

## Adam-Specific Collection Priorities

1. Newfoundland coinage: date runs, key dates, higher-grade examples, and 5 cent, 10 cent, 20 cent, and 50 cent focus.
2. 1859 Canadian Large Cents: variety attribution, Narrow 9 / Wide 9, 8 over 9 varieties, date and die variety analysis, and upgrade opportunities.
3. Canadian silver coinage: dimes, quarters, half dollars, and dollars.
4. Date run completion: identify missing years, prioritize easiest completions, and calculate completion percentages.
5. Upgrade-over-duplicate strategy: prefer quality upgrades, minimize duplicate purchases, and identify replacement candidates.
6. Budget-conscious acquisitions: maximize value per dollar spent, focus on high-ROI purchases, and highlight underpriced opportunities.
7. Collection gap reduction: generate want lists, rank acquisition targets, and recommend highest-impact purchases.

## Next Priority Task

Prepare v4.0 Live Deal Hunter planning unless a release-blocking defect is found.

## Project Architecture

* Main application entry point: `coin_collection_gui.py` launches the primary Tkinter collection manager. `main.py` launches the older `gui.py` entry point.
* Collection management system: `coin_collection.py` defines `CoinItem`, `CoinCollection`, and `CoinCollectionApp`; it handles JSON persistence, CRUD, search, CSV import/export, and collection summaries.
* Upgrade Advisor system: `upgrade_advisor.py` evaluates candidate coins against existing collection for upgrade potential, with grade improvement, value improvement, and Adam-specific priority scoring (Newfoundland, Canadian silver, 1859 Large Cents). Provides verdicts (Strong Upgrade, Upgrade, Hold Existing, Duplicate, Pass) with human-readable explanations. Read-only analysis with GUI integration (Tools → Upgrade Advisor) and CSV export.
* Collection Intelligence system: `collection_intelligence.py` powers gap reports, want lists, duplicate/upgrade detection, Adam-specific priority scoring, staged `WANT_LIST` ranking boosts, and future evaluator inputs.
* Focused Collection Intelligence system: `focused_collection_intelligence.py` provides reusable manual candidate classification for the Do I Own This workflow, staged WANT_LIST context awareness, Buy Advisor duplicate/upgrade detection, and Upgrade Advisor match/upgrade decisions, including fuzzy matching, grade comparison, duplicate/upgrade detection, want-list matching, gap detection, recommendation, confidence, reasons, and warning flags.
* Acquisition Workflow system: `acquisition_workflow.py` consumes focused Collection Intelligence results and asking price to produce deterministic acquisition guidance. Buy Advisor stores the workflow result as supporting structured context while preserving existing user-visible verdict behavior; Do I Own This shows acquisition guidance only when asking price is entered.
* Shared Session Context system: `session_context.py` stores the session workbook path, staged collection preview counts, staged WANT_LIST intents, load timestamp, warnings, and errors for reuse by GUI tools while keeping fallbacks intact.
* Persistence Layer system: `persistence_manager.py` stores local app state as JSON under `collection_data/app_state/`, validates schema, creates timestamped backups before overwrite/clear, handles corrupt JSON and missing referenced files gracefully, and restores session metadata, market records, photo records, shopping candidates, OCR experiment metadata, and app preferences.
* Data Safety and Backup system: `backup_manager.py` creates and verifies local backup packages, writes human-readable manifests, includes `data/collection.json` and persisted workbook copies when available, lists backups, restores known safe app-state and collection JSON files with pre-restore backup, validates app-state, backup coverage, collection JSON, workbook paths, and referenced paths, generates Collection Recovery Reports, and creates Collector Export Bundles.
* Collection Integrity system: `collection_integrity.py` audits collection data quality without modifying records, including duplicate ownership detection, missing and invalid fields, photo integrity, market record integrity, certification integrity, shopping candidate references, persistence paths, backup readiness, integrity scoring, and CSV/Markdown exports.
* Collection Snapshot system: `collection_snapshot.py` creates persistent point-in-time snapshots under `collection_data/app_state/collection_snapshots.json`, compares current and previous snapshots, reports growth, quality, integrity, photo coverage, series completion, market, and shopping deltas, and exports CSV/Markdown reports. Backup packages include the snapshot file when present.
* Mobile Readiness system: `mobile_readiness.py` generates a deterministic Mobile Readiness Report, Mobile Readiness Score, desktop dependency audit, service boundary review, mobile input readiness findings, documentation-only API mapping, dealer-table phone workflow audit, and CSV/Markdown exports.
* Mobile Companion system: `mobile_companion.py` provides `MobileCandidateEntry`, `MobileAnalysisReport`, `MobileCompanionWorkflow`, desktop `StorageProvider`/`PhotoProvider`/`ExportProvider` abstractions, `PhoneWorkflowSimulation`, `PhoneWorkflowReport`, and CSV/Markdown exports while reusing Listing Analyzer, Acquisition Workflow, Acquisition Impact, Smart Shopping Assistant, Photo Vault metadata, and Persistence Manager.
* Photo-Assisted Entry system: `photo_assisted_entry.py` provides `PhotoCandidate`, `PhotoAssistedEntry`, and `PhotoReviewReport` for metadata-only front/reverse/reference photo candidate workflows. It links photo paths through Photo Vault metadata, routes recommendations through Mobile Companion and existing acquisition engines, stores candidate metadata in app state, and exports review reports without copying, moving, reading, OCRing, classifying, or grading images.
* OCR Experiment system: `ocr_experiment.py` provides `OCRResult`, `OCRConfidence`, `OCRSuggestionReport`, and `OCRExperiment` for advisory-only OCR text extraction and deterministic suggestion parsing. It can report possible years, denominations, countries, note prefixes, and certification numbers, persists OCR metadata through app state, exports CSV/Markdown reports, and always requires manual review.
* OCR Validation system: `ocr_validation.py` provides `OCRValidationEngine`, `OCRValidationReport`, `OCRTrustLevel`, `OCRValidationScore`, and `OCRValidationExplanation` for deterministic OCR trust assessment. It validates year, denomination, country, certification, confidence, source warnings, and ambiguity, then exports CSV/Markdown validation reports.
* Workflow Integration system: `collector_workflows.py` provides `CollectorWorkflowEngine`, guided `AcquisitionWorkflow`, `CollectionReviewWorkflow`, `PhotoReviewWorkflow`, `CollectorDailySummary`, `WorkflowStatus`, and `WorkflowSummary`. It orchestrates existing engines, persists lightweight workflow state, exposes Tools -> Acquisition Workflow, Tools -> Collection Review Workflow, and Tools -> Daily Collector Summary, and exports workflow Markdown/CSV summaries.
* Collector Home Dashboard system: `collector_home_dashboard.py` provides `CollectorHomeDashboard`, `CollectorHomeReport`, `HomeStatusCard`, `DailyCollectorAction`, and `HomeStatusSeverity`. It aggregates existing workflow, dashboard, shopping, OCR validation, photo audit, integrity, backup, snapshot, series, and persistence signals into one daily report without adding recommendation logic or mutating collection data.
* Collector Companion Readiness system: `collector_companion_readiness.py` provides `CollectorCompanionReadinessAuditor`, `CollectorCompanionReadinessReport`, `CollectorCompanionStatus`, `ExportConsistencyReport`, `ReportConsistencyReport`, `WorkflowAuditReport`, and `V3ReadinessChecklistItem`. It audits readiness, product status, workflow cohesion, report/export consistency, and v3.0 blockers without modifying collection data or decision logic.
* Deal Hunter system: `deal_hunter.py` provides `DealListing`, `ParsedDealCandidate`, `DealHunterCSVImportResult`, `DealHunterResult`, `DealHunterReport`, and `DealHunter`. It imports manual/CSV eBay.ca-style listing rows, parses deterministic candidate signals, flags high shipping, unclear grade, raw-overgraded language, lot listings, possible damage, unclear currency, non-collection relevance, and manual-review needs, reuses Listing Analyzer, Acquisition Workflow, Acquisition Impact, Smart Shopping, Market Awareness, and WANT_LIST context, then exports CSV/Markdown reports without scraping or live pricing.
* Deal Hunter Ranking system: `deal_hunter_ranking.py` provides `CandidatePool`, `ImportProfile`, `DealHunterRankingEngine`, `RankingScore`, `RankedDeal`, `BudgetOpportunityReport`, and `DealHunterRankingReport`. It reuses Deal Hunter and Opportunity Engine outputs to rank large local candidate pools by collection fit, upgrade value, gap value, WANT_LIST relevance, liquidity, risk, and budget fit, then exports budget/category reports without scraping, APIs, live pricing, automatic purchasing, or collection mutation.
* External Listing Connector system: `listing_connectors.py` provides `ListingConnector`, `ConnectorRegistry`, `NormalizedListing`, `eBayCSVConnector`, `AuctionCSVConnector`, `DealerInventoryConnector`, `GenericCSVConnector`, `ConnectorValidationReport`, `ConnectorImportReport`, `SourceSummaryReport`, and `DuplicateOpportunityDetector`. It normalizes user-supplied local CSV files into Deal Hunter-compatible listings and CandidatePools without scraping, APIs, live listing retrieval, browser automation, or collection mutation.
* Deal Hunter Calibration system: `deal_hunter_calibration.py` provides `CalibrationCase`, `CalibrationCaseResult`, `DealHunterCalibrationEngine`, and `DealHunterCalibrationReport`. It runs offline calibration fixtures through Deal Hunter and Ranking output to surface false recommendations, ranking misses, missing risk flags, over/under-penalized cases, and explanation gaps before any live-source work.
* Live Deal Hunter Readiness system: `live_deal_hunter_readiness.py` provides `LiveDealHunterReadinessAudit`, `LiveDealHunterReadinessReport`, `LiveListingSource`, `LiveListingBatch`, `LiveListingFetchResult`, `LiveSourceValidationReport`, `RateLimitPolicy`, and `LiveSourceFailure`. It documents future live-source boundaries and validates supplied batch data without performing live fetching.
* Market Intelligence system: `market_intelligence.py` provides `MarketIntelligenceEngine`, `MarketIntelligenceReport`, `FairValueEstimate`, `DealQuality`, `OpportunityConfidence`, `ComparableSale`, and `RiskSummary`. It reuses Deal Hunter, Opportunity Engine, Collection Intelligence, WANT_LIST context, and local Market Awareness data for deterministic fair-value guidance without external fetching or collection mutation.
* Portfolio Performance system: `portfolio_performance.py` provides `PortfolioPerformanceEngine`, `PortfolioPerformanceReport`, `CollectionGrowthReport`, `AcquisitionPerformanceReport`, `SeriesProgressReport`, `BudgetAllocationReport`, and `CollectionHealthScore`. It reuses Collection Snapshot, Collection Intelligence, Opportunity Engine, Market Intelligence context, Series Tracker, Quality, Integrity, and Market Awareness records for local portfolio-development reporting.
* Opportunity Engine system: `opportunity_engine.py` provides `OpportunityEngine`, `OpportunityScore`, `OpportunityReport`, and `TopOpportunitiesReport`. It reuses Collection Intelligence, Smart Shopping Assistant, Acquisition Impact, Collection Quality, Series Tracker, WANT_LIST, Deal Hunter, and local Market Awareness context to identify budget-aware collection opportunities without scraping, APIs, live pricing, market prediction, automatic purchasing, image recognition, or collection mutation.
* Listing Analyzer system: `listing_analyzer.py` defines `ListingCandidate` and `ListingAnalyzer`, validates stored-only URLs, computes total cost, parses basic candidate fields from listing text, and routes recommendations through `AcquisitionWorkflow`.
* Acquisition Impact system: `acquisition_impact.py` simulates candidate acquisition impact using `AcquisitionWorkflow`, `CollectionQualityEngine`, and `CollectionIntelligenceEngine` to report quality, completion, WANT_LIST, upgrade, and impact-score deltas.
* Series Tracker system: `series_definitions.py` stores extendable supported-series definitions; `series_tracker.py` reports owned dates, missing dates, completion, WANT_LIST counts, upgrade counts, priority scores, top missing dates, and exports.
* Photo Vault system: `photo_vault.py` stores metadata-only `PhotoRecord` objects, links photos to collection items and candidates, supports reference/auction/sold photo types, certification-number lookup, deterministic search, coverage metrics, expected folder mapping, CSV/Markdown exports, and `PhotoVaultIntegrityAudit` for report-only trust checks across missing, duplicate, unlinked, invalid, unsupported, collection, candidate, and certified-item photo metadata.
* Market Awareness system: `market_awareness.py` stores local-only observed price, purchase, sale, and auction records, generates summaries, exposes historical observed-price context for acquisition impact, supports photo-reference identifiers, and exports CSV/Markdown reports.
* Smart Shopping Assistant system: `smart_shopping_assistant.py` ranks shopping opportunities by reusing Listing Analyzer parsing, Acquisition Workflow decisions, Acquisition Impact scoring, staged WANT_LIST context, local Market Awareness observations, and optional photo-reference identifiers. It displays compact "Why" explanations generated by `shopping_explainability.py`.
* Shopping Explainability system: `shopping_explainability.py` provides `RecommendationConfidence`, `RecommendationExplanation`, `ExplainableRecommendationReport`, and `ShoppingExplanationEngine` to explain existing BUY/PASS/WATCH/NEGOTIATE/REVIEW outputs without changing recommendation decisions.
* Collector Operating System system: `collector_operating_system.py` composes Collection Dashboard, Collection Quality, Series Tracker, Smart Shopping Assistant, Market Awareness, and Photo Vault context into Collector Home and Collection Health Report outputs without duplicating decision logic.
* Collection Dashboard system: `collection_dashboard.py` generates actionable dashboard data, snapshot counts, top priorities, upgrade opportunities, WANT_LIST priorities, collection gaps, series completion, basic collection evolution, and CSV/Markdown exports.
* Collection Quality system: `collection_quality.py` generates explainable quality reports, category scores, strengths, weaknesses, recommended actions, supporting metrics, and CSV/Markdown exports. Collection Dashboard displays its top-level quality output.
* CSV import system: `CoinCollection.import_from_csv()` imports simple CSV files; `numista_importer.py` imports Numista Excel exports; `csv_exporter.py` exports analyzer results with Numista search URLs.
* Legacy portfolio staging system: `legacy_portfolio_importer.py` parses `CORE_RAW` and `SLABS` from the legacy workbook into reviewable staged `CoinItem` records, future metadata, duplicate buckets, skipped rows, summary text, and CSV preview reports without saving collection data.
* Legacy WANT_LIST staging: `legacy_portfolio_importer.py` also exposes read-only `WANT_LIST` acquisition intent previews for Want List Generator input and Buy Advisor context.
* Portfolio preview GUI: `coin_collection_gui.py` exposes Tools -> Portfolio Import Preview and displays importable staged rows, duplicate rows, skipped rows, warnings, and summary counts.
* WANT_LIST preview GUI: `coin_collection_gui.py` exposes Tools -> Want List Preview and displays staged workbook acquisition intent without modifying collection data.
* Want List Generator GUI: `coin_collection_gui.py` exposes Tools -> Want List Generator and can combine current collection analysis with staged workbook `WANT_LIST` intent for read-only acquisition recommendations.
* WANT_LIST integration plan: `WANT_LIST_INTEGRATION_PLAN.md` defines the Phase 2 design for staged acquisition intent and future Buy Advisor/Want List Generator integration.
* Legacy portfolio import design: `LEGACY_PORTFOLIO_IMPORT_SPEC.md` maps the external workbook sheets into future staging/import, melt-value, upgrade, want-list, and advisor workflows.
* Portfolio integration roadmap: `PORTFOLIO_INTEGRATION_ROADMAP.md` defines phased migration work for workbook-backed portfolio features.
* Testing framework: Python standard-library `unittest` discovery via `python -m unittest discover -s . -p "test_*.py"`, with fixture files in `test_data/` and Windows runner `run_tests.bat`.

## Development Notes

* Python 3.8+ is expected.
* Runtime dependencies are pinned in `requirements.txt`: `pytesseract`, `Pillow`, `opencv-python`, `pandas`, and `openpyxl`.
* Tests must not mutate `data/collection.json`; copy fixtures from `test_data/` into temporary directories instead.
* Keep app data as UTF-8 JSON.
* Detection features are experimental suggestions only; user verification is required before saving.
* Work one task at a time from `TASK_QUEUE.md`, run tests if possible, summarize changed files, then stop for approval.
* Update this file whenever a major feature is completed.
* `PROJECT_STATE.md` and `TASK_QUEUE.md` are the source of truth for project status.
* Whenever a task is completed:
  1. Update `PROJECT_STATE.md`.
  2. Update `TASK_QUEUE.md`.
  3. Run tests if available.
  4. Commit changes.
  5. Include the commit hash in this file's Recent Changes section.
* Every completed version must end with implementation, acceptance audit, tag creation, and push verification.
* A version is not complete until its release tag exists locally and remotely and both tag targets are verified.
* Never leave a completed version untagged.

## Recent Changes

### 2026-06-21

* Implemented v3.9 Portfolio Performance: `PortfolioPerformanceEngine`, `CollectionGrowthReport`, `AcquisitionPerformanceReport`, `SeriesProgressReport`, `BudgetAllocationReport`, `CollectionHealthScore`, executive `PortfolioPerformanceReport`, Tools -> Portfolio Performance, snapshot comparison support, CSV/Markdown export, and explicit no-investment-advice/no-live-pricing guardrails.
* Roadmap lock commit: `a65a9ce`
* Implementation commit: `e52083d`
* Full test suite passed: 579 tests OK.
* Coverage note: total passing tests increased from 571 to 579; existing regression suites remained green.
* Limitation: deterministic local portfolio-development reporting only; no investment advice, scraping, APIs, live pricing, market forecasting, automatic purchasing, or collection mutation.

* Implemented v3.8 Market Intelligence: `MarketIntelligenceEngine`, `FairValueEstimate`, `ComparableSale`, `DealQuality`, `OpportunityConfidence`, `RiskSummary`, collector-facing counterarguments, Tools -> Market Intelligence, CSV/Markdown export, and explicit no-scraping/no-live-pricing guardrails.
* Roadmap lock commit: `b9915d4`
* Implementation commit: `92864f6`
* Full test suite passed: 571 tests OK.
* Coverage note: total passing tests increased from 560 to 571; existing regression suites remained green.
* Limitation: deterministic local guidance only from supplied/local comparable records and internal deal guidance; no scraping, browser automation, APIs, live pricing, automatic purchasing, image recognition, or collection mutation.

* Implemented v3.7 Live Deal Hunter Readiness: `LiveDealHunterReadinessAudit`, live-source contract models, `LiveSourceValidationReport`, deterministic staleness flags, `RateLimitPolicy`, `LiveSourceFailure`, Tools -> Live Deal Hunter Readiness, CSV/Markdown export, and explicit no-fetch safety behavior.
* Implementation commit: `ca87a8a`
* Full test suite passed: 560 tests OK.
* Coverage note: total passing tests increased from 550 to 560; existing regression suites remained green.
* Limitation: readiness contracts and validation only; no scraping, browser automation, eBay/dealer/auction APIs, live listing retrieval, automatic purchasing, live pricing claims, image recognition, or collection mutation.

* Implemented v3.6 Deal Hunter Calibration: `CalibrationCase`, `DealHunterCalibrationEngine`, `DealHunterCalibrationReport`, offline collector-judgment fixture CSV, false BUY/PASS/REVIEW detection, ranking-miss detection, missing risk-flag detection, explanation checks, Tools -> Deal Hunter Calibration, CSV/Markdown export, and raw high-grade listing risk calibration.
* Implementation commit: `87bf575`
* Full test suite passed: 550 tests OK.
* Coverage note: total passing tests increased from 538 to 550; existing regression suites remained green.
* Limitation: deterministic offline calibration only; no scraping, browser automation, eBay/dealer/auction APIs, live listing retrieval, live pricing, automatic purchasing, image recognition, or collection mutation.

* Implemented v3.5 External Listing Connectors: `ListingConnector`, `ConnectorRegistry`, `NormalizedListing`, eBay/Auction/Dealer/Generic CSV connectors, validation reports, source summaries, duplicate-opportunity detection, multi-source CandidatePool/ranking compatibility, Tools -> External Listing Connectors, CSV/Markdown export, and release documentation.
* Roadmap lock commit: `e4a2245`
* Implementation commit: `27aca0c`
* Full test suite passed: 538 tests OK.
* Coverage note: total passing tests increased from 527 to 538; existing regression suites remained green.
* Limitation note: connectors normalize user-supplied local files only. They do not scrape, fetch URLs, use browser automation, call eBay/dealer/auction APIs, retrieve live listings, claim live market-pricing accuracy, purchase automatically, recognize images, or mutate collection data.

* Implemented v3.4 Deal Hunter Ranking and Import Framework: candidate pools, eBay/Auction/Dealer/Custom import profiles, required-field/URL/malformed-price warnings, duplicate URL/listing suppression, Opportunity Engine-backed ranking scores, $50/$100/$250/$500 budget optimization, Newfoundland/Canadian silver/banknote/upgrade/gap/WANT_LIST category views, Tools -> Deal Hunter Ranking, CSV/Markdown export, and release documentation.
* Implementation commit: `47d34fe`
* Full test suite passed: 527 tests OK.
* Coverage note: total passing tests increased from 515 to 527; existing regression suites remained green.
* Limitation note: Deal Hunter Ranking is deterministic local guidance only. It does not scrape, fetch live listings, use browser automation, call APIs, claim live market-pricing accuracy, purchase automatically, recognize images, or mutate collection data.

* Implemented v3.3 Opportunity Engine: budget-aware top opportunities, $50/$100/$250/$500 recommendations, supported opportunity types, opportunity score components, reasoning, risks, counterarguments, Deal Hunter result input support, Workflows -> Opportunity Engine GUI, CSV/Markdown export, and release documentation.
* Roadmap lock commit: `7d53acc`
* Implementation commit: `3871611`
* Full test suite passed: 515 tests OK.
* Coverage note: total passing tests increased from 505 to 515; existing regression suites remained green.
* Limitation note: Opportunity Engine is deterministic local guidance only. It does not scrape, fetch live listings, use browser automation, call APIs, predict markets, purchase automatically, recognize images, or mutate collection data.

* Implemented v3.2 Deal Hunter Workflow Refinement: expanded deterministic parsing for key Canadian/Newfoundland targets, banknotes, slab companies, grade words, lots, problem-coin language, CSV aliases, malformed price warnings, skipped-row reporting, risk flags, GUI import summaries, and richer CSV/Markdown exports.
* Implementation commit: `0a80eff`
* Full test suite passed: 505 tests OK.
* Coverage note: total passing tests increased from 494 to 505; existing regression suites remained green.
* Limitation note: Deal Hunter remains deterministic local guidance only. It does not scrape, fetch live listings, use browser automation, call eBay APIs, or claim live market-pricing accuracy.

### 2026-06-20

* Implemented v3.1 eBay.ca Coin Deal Hunter MVP: DealListing input model, CSV import, deterministic title/description parser, slab and banknote detection, collection-aware deal scoring, Adam buying rules, counterargument-before-BUY logic, Workflows -> Deal Hunter GUI, app-state persistence, test fixture CSV, CSV/Markdown export, and release documentation.
* Implementation commit: `fb20988`
* Full test suite passed: 494 tests OK.
* Coverage note: total passing tests increased from 475 to 494; existing regression suites remained green.
* Limitation note: Deal Hunter is deterministic local guidance only. It does not scrape, fetch live listings, use browser automation, call eBay APIs, or claim live market-pricing accuracy.

### 2026-06-19

* Finalized v3.0 Collector Companion milestone: added Collector Companion Status derived from the existing readiness auditor, verified full system imports, verified end-to-end workflow readiness, created v3.0 release notes, and refreshed source-of-truth release metadata.
* Implementation commit: `935e3c7`
* Full test suite passed: 475 tests OK.
* Coverage note: total passing tests increased from 471 to 475; existing regression suites remained green.
* GUI smoke note: local Tcl/Tk install may remain environment-sensitive; v3.0 imports, readiness/status generation, exports, persistence compatibility, targeted tests, and full non-GUI regression suite passed.

* Implemented v2.9 Collector Companion Release Candidate: menu grouping into Collector Home, Workflows, Reports, Tools, and Help; Collector Companion Readiness report; export consistency audit; report consistency audit; end-to-end workflow audit; V3 readiness checklist; app-state persistence for readiness reports/audit summaries; Tools/Help readiness entry; CSV/Markdown export; and focused tests.
* Implementation commit: `379715f`
* Full test suite passed: 471 tests OK.
* Coverage note: total passing tests increased from 463 to 471; existing regression suites remained green.
* GUI smoke note: local Tcl/Tk install may remain environment-sensitive; v2.9 imports, readiness generation, menu source validation, exports, persistence, targeted tests, and full non-GUI regression suite passed.

* Implemented v2.8 Collector Home Dashboard: CollectorHomeDashboard, CollectorHomeReport, HomeStatusCard, DailyCollectorAction, HomeStatusSeverity, Tools -> Collector Home Dashboard, app-state persistence for home reports/action acknowledgements, status cards, daily actions, top opportunities, review queues, data safety, progress, CSV/Markdown export, and focused tests.
* Implementation commit: `632a922`
* Full test suite passed: 463 tests OK.
* Coverage note: total passing tests increased from 451 to 463; existing regression suites remained green.
* GUI smoke note: local Tcl/Tk install may remain environment-sensitive; v2.8 imports, report generation, exports, persistence, targeted tests, and full non-GUI regression suite passed.

* Implemented v2.7 Workflow Integration: CollectorWorkflowEngine, guided Acquisition Workflow, Collection Review Workflow, Photo Review Workflow, Daily Collector Summary, WorkflowStatus, WorkflowSummary, app-state persistence for workflow statuses/summaries, Tools menu entries, CSV/Markdown export, and orchestration tests.
* Implementation commit: `599cb4a`
* Full test suite passed: 451 tests OK.
* Coverage note: total passing tests increased from 444 to 451; existing regression suites remained green.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v2.7 imports, workflow generation, exports, persistence, targeted tests, and full non-GUI regression suite passed.

* Implemented v2.6.1 OCR Validation Layer: OCRValidationEngine, OCRValidationReport, OCRTrustLevel, OCRValidationScore, OCRValidationExplanation, year/denomination/country/certification validation, warning generation, trust scoring, explanations, Tools -> OCR Experiment validation display, and CSV/Markdown export.
* Implementation commit: `22645a0`
* Full test suite passed: 444 tests OK.
* Coverage note: total passing tests increased from 433 to 444; existing regression suites remained green.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v2.6.1 imports, validation generation, exports, OCR behavior preservation, targeted tests, and full non-GUI regression suite passed.

* Implemented v2.6 OCR Experiments: OCRResult, OCRConfidence, OCRSuggestionReport, OCRExperiment, advisory-only suggestion extraction, deterministic confidence labels, Photo-Assisted Entry/Photo Vault/Mobile Companion helper integrations, app-state persistence for OCR reports, Tools -> OCR Experiment, CSV/Markdown export, and manual-review guardrails.
* Implementation commit: `f569393`
* Full test suite passed: 433 tests OK.
* Coverage note: total passing tests increased from 422 to 433; existing regression suites remained green.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v2.6 imports, OCR report generation, exports, persistence, targeted tests, and full non-GUI regression suite passed.

* Implemented v2.5.2 Shopping Explainability: RecommendationConfidence, RecommendationExplanation, ExplainableRecommendationReport, ShoppingExplanationEngine, BUY/PASS/WATCH/NEGOTIATE/REVIEW explanations, deterministic confidence labels, impact summaries, Listing Analyzer "Why" output, Smart Shopping "Why" markdown, CSV/Markdown export, and behavior-preservation tests.
* Implementation commit: `17821de`
* Full test suite passed: 422 tests OK.
* Coverage note: total passing tests increased from 410 to 422; existing regression suites remained green.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v2.5.2 imports, explanation generation, exports, behavior preservation, targeted tests, and full non-GUI regression suite passed.

### 2026-06-18

* Implemented v2.5.1 Photo Vault Hardening: PhotoVaultIntegrityAudit, PhotoCoverageReport, PhotoVaultIssue, missing/duplicate/unlinked/invalid/unsupported photo findings, collection/candidate/certified-item coverage metrics, Tools -> Photo Vault Audit, Data Safety photo findings, recovery report photo-file backup warning, and CSV/Markdown export.
* Implementation commit: `749182f`
* Full test suite passed: 410 tests OK.
* Coverage note: total passing tests increased from 399 to 410; existing regression suites remained green.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v2.5.1 imports, Photo Vault audit generation, Data Safety integration, backup/recovery messaging, exports, targeted tests, and full non-GUI regression suite passed.

* Implemented v2.5 Photo-Assisted Entry: PhotoCandidate, PhotoAssistedEntry, PhotoReviewReport, Tools -> Photo-Assisted Entry, Photo Vault candidate/reference linking, Mobile Companion recommendation reuse, persisted photo candidate metadata, backup-compatible metadata-only behavior, and CSV/Markdown export.
* Implementation commit: `fd817b6`
* Full test suite passed: 399 tests OK.
* Coverage note: total passing tests increased from 391 to 399; existing regression suites remained green.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v2.5 imports, photo candidate creation, Photo Vault linking, Mobile Companion integration, persistence, backup compatibility, exports, targeted tests, and full non-GUI regression suite passed.

* Implemented v2.4.3 Collection Snapshot System: CollectionSnapshot, CollectionSnapshotManager, CollectionSnapshotReport, GrowthSummary, series progress deltas, persistent snapshot storage, Tools -> Create Snapshot, Tools -> Snapshot Report, backup eligibility, and CSV/Markdown export.
* Implementation commit: `044dd50`
* Full test suite passed: 391 tests OK.
* Coverage note: total passing tests increased from 382 to 391; existing regression suites remained green.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v2.4.3 imports, snapshot creation, persistence, comparisons, exports, backup eligibility, targeted tests, and full non-GUI regression suite passed.

* Implemented v2.4.2 Collection Integrity Audit: CollectionIntegrityAudit, CollectionIntegrityReport, integrity score, duplicate/missing/invalid ownership checks, photo/market/certification summaries, backup readiness integration, Tools -> Collection Integrity Audit, and CSV/Markdown export.
* Implementation commit: `bbb7314`
* Full test suite passed: 382 tests OK.
* Coverage note: total passing tests increased from 368 to 382; existing regression suites remained green.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v2.4.2 imports, integrity report generation, exports, backup readiness checks, targeted tests, and full non-GUI regression suite passed.

* Implemented v2.4.1 Critical Collection Backup Hardening: default `data/collection.json` backup coverage, persisted workbook copy support, explicit manifest recovery flags, Collection Recovery Report, Data Safety backup-coverage validation, Tools -> Collection Recovery Report, and recovery documentation.
* Implementation commit: `a9ca10c`
* Full test suite passed: 368 tests OK.
* Coverage note: total passing tests increased from 361 to 368; existing regression suites remained green.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v2.4.1 imports, backup/recovery reports, manifests, validator checks, targeted tests, and full non-GUI regression suite passed.

* Implemented v2.4 Mobile Companion Prototype: MobileCandidateEntry, MobileAnalysisReport, MobileCompanionWorkflow, desktop provider abstractions, PhoneWorkflowSimulation, PhoneWorkflowReport, dashboard mobile summary, persistence of recent mobile candidates/recommendations, CSV/Markdown export, and v2.4 release documentation.
* Implementation commit: `8de41c7`
* Full test suite passed: 361 tests OK.
* Coverage note: total passing tests increased from 344 to 361; existing regression suites remained green.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v2.4 imports, workflow reports, persistence round-trips, dashboard integration, exports, targeted tests, and full non-GUI regression suite passed.

* Implemented v2.3 Mobile Readiness: MobileReadinessAuditor, MobileReadinessReport, MobileReadinessScore, desktop dependency audit, service boundary review, mobile input analysis, documentation-only future endpoint mapping, dealer-table phone workflow audit, CSV/Markdown export, and v2.3 release documentation.
* Implementation commit: `539472b`
* Full test suite passed: 344 tests OK.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v2.3 imports, readiness report generation, exports, targeted tests, and full non-GUI regression suite passed.

* Locked the official post-v2.2 roadmap: v2.3 Mobile Readiness, v2.4 Mobile Companion Prototype, v2.5 Photo-Assisted Entry, v2.6 OCR Experiments, and v3.0 Collector Companion. Clarified that v2.3 is a readiness and architecture milestone only, not a mobile app.

* Implemented v2.2 Data Safety and Backup Hardening: BackupManager, BackupManifest, DataSafetyValidator, DataSafetyReport, backup package creation/verification/listing/restore, pre-restore backups, collector export bundle, Tools menu entries, and data-safety documentation.
* Implementation commit: `e70fc4c`
* Full test suite passed: 335 tests OK.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v2.2 imports, backup package checks, restore checks, data-safety reports, export bundles, targeted integration tests, and full non-GUI regression suite passed.

* Implemented v2.0 Collector Operating System: Collector Home, Collection Health Report, consolidated workflow guidance, persistence audit findings, dashboard/quality/series/shopping/market/photo integration, Tools menu entries, and CSV/Markdown export.
* Implementation commit: `11b4f6e`
* Full test suite passed: 309 tests OK.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v2.0 imports, consolidated report generation, exports, targeted integration tests, and full non-GUI regression suite passed.

* Implemented v2.1 Persistence Layer: local JSON app state, save/load/clear/validate/backup/import/export operations, session metadata restoration, market/photo/shopping/app-preference round-tripping, Tools menu integration, and state folder documentation.
* Implementation commit: `95ef0c0`
* Full test suite passed: 321 tests OK.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v2.1 imports, persistence round-trips, validation, backups, targeted integration tests, and full non-GUI regression suite passed.

* Implemented v1.9 Smart Shopping Assistant: reusable ranked opportunity engine, shopping candidate model, best next purchase output, STRONG BUY/BUY/NEGOTIATE/WATCH/PASS/REVIEW recommendation statuses, local market context, WANT_LIST and upgrade prioritization, dashboard shopping panel, Tools -> Smart Shopping Assistant GUI workflow, and CSV/Markdown export.
* Implementation commit: `efe7a1b`
* Full test suite passed: 300 tests OK.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v1.9 imports, ranking checks, exports, dashboard integration, and full non-GUI regression suite passed.

### 2026-06-17

* Implemented v1.8 Market Awareness Layer: local observed price, purchase, sale, and auction records; market summary reporting; dashboard market metrics; acquisition historical observed-price context; photo-reference identifiers; and CSV/Markdown export.
* Implementation commit: `5a73332`
* Full test suite passed: 285 tests OK.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v1.8 imports, market context checks, exports, dashboard integration, and full non-GUI regression suite passed.

* Implemented v1.7 Photo Vault: metadata-only photo records, collection/candidate/reference linking, certification lookup, deterministic search, collection photo coverage metrics, dashboard photo coverage display, expected folder mapping, and CSV/Markdown export.
* Implementation commit: `0b961d9`
* Full test suite passed: 277 tests OK.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v1.7 imports, photo vault lookups, and non-GUI dashboard coverage checks passed.

* Implemented v1.6 Series Tracker: supported series definitions, owned/missing date reports, completion percentages, WANT_LIST and upgrade integration, priority scores, CSV/Markdown export, Dashboard Top Series panel, and Acquisition Impact series priority metrics.
* Implementation commit: `8c4b58b`
* Full test suite passed: 269 tests OK.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v1.6 imports, tracker reports, and non-GUI dashboard/impact checks passed.

### 2026-06-16

* Implemented v1.5 Smarter Acquisition Intelligence: Acquisition Impact Engine, deterministic add/replace simulation, quality/completion/WANT_LIST/upgrade deltas, impact score, recommendation reasoning, Listing Analyzer display integration, and Dashboard top potential collection improvements panel.
* Implementation commit: `549665a`
* Full test suite passed: 260 tests OK.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; v1.5 imports and non-GUI impact/listing/dashboard checks passed.

* Implemented v1.4 Collection Quality Engine: explainable overall quality score, category scores, strengths, weaknesses, recommended actions, supporting metrics, CSV/Markdown export, and Collection Dashboard integration.
* Implementation commit: `4df68f2`
* Full test suite passed: 251 tests OK.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; quality/dashboard/GUI module imports passed and full non-GUI regression suite passed.

* Implemented v1.3 Collection Dashboard: Tools -> Collection Dashboard, reusable structured dashboard data, snapshot counts, top priorities, upgrade opportunities, WANT_LIST priorities, collection gaps, series completion, basic collection evolution, and CSV/Markdown export.
* Implementation commit: `da1c37f`
* Full test suite passed: 238 tests OK.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; import smoke passed and full non-GUI regression suite passed.

* Completed v1.2 post-release usability documentation audit: clarified Listing Analyzer workflow positioning, Buy Advisor / Listing Analyzer / Want List overlap, export support, known limitations, release metadata, and next priorities.
* Commit: `d3eac79`
* Full test suite passed after documentation cleanup: 229 tests OK.

* Implemented v1.2 Listing Analyzer: offline pasted listing model, URL validation, total-cost calculation, basic candidate parsing, acquisition workflow integration, shared WANT_LIST context reuse, Tools -> Listing Analyzer GUI entry point, and listing regression tests.
* Commit: `7d12b54`
* Full test suite passed: 229 tests OK.

* Implemented v1.1 Shared Session Context: load-once workbook/WANT_LIST state, menu actions for loading and clearing context, status-line visibility, shared WANT_LIST reuse across Do I Own This, Acquisition Workflow, Buy Advisor, Want List Generator, and portfolio preview workflows, plus regression tests.
* Commit: `a63edb5`
* Full test suite passed: 213 tests OK.
* GUI smoke note: local Tcl/Tk install could not find `init.tcl`; full non-GUI regression suite passed.

* Completed post-v1.0 release packaging documentation: refreshed README for v1.0, added screenshot guidance, v1.0 release notes, release history, backup guide, and verified local/remote release tags from `v0.5` through `v1.0`.
* Commit: `2318550`
* Test status: documentation-only changes; full suite rerun after packaging.

* Completed v1.0 release-readiness audit: application launch, collection load, Do I Own This with and without WANT_LIST-capable workflow, Acquisition Workflow, Buy Advisor, Upgrade Advisor, Want List Generator, Collection Gap Report, Portfolio Import Preview, export smoke tests, tag metadata, and full regression suite passed. No source defects required fixes.
* Commit: `f20fd22`
* Full test suite passed: 203 tests OK.

* Implemented v0.9 Acquisition Workflow on top of the focused Collection Intelligence Engine. The workflow provides deterministic max rational price and BUY/PASS/WATCH/NEGOTIATE/REVIEW guidance using internal collection, WANT_LIST, priority, duplicate, upgrade, and review-risk signals only.
* Commit: `77771f6`
* Full test suite passed: 203 tests OK.

* Implemented v0.8 WANT_LIST context awareness for the focused Collection Intelligence Engine and Do I Own This workflow. Candidate analysis now reports `ON_WANT_LIST`, `NOT_ON_WANT_LIST`, `GAP_NOT_EXPLICITLY_TARGETED`, or `WANT_LIST_UNAVAILABLE` while preserving existing primary classifications and deterministic behavior.
* Commit: `76b4f11`
* Full test suite passed: 190 tests OK.

* Consolidated Buy Advisor and Upgrade Advisor decision sources around the focused Collection Intelligence Engine. Duplicate detection, owned-match lookup, and upgrade classification now reuse the focused engine while preserving existing scoring, price analysis, melt-value support, explanations, and verdict behavior.
* Commit: `fb96574`
* Full test suite passed: 184 tests OK.

* Implemented focused Collection Intelligence Engine for manual candidate analysis, including deterministic classifications, fuzzy matching, grade comparison, raw/certified handling, variety review flags, want-list context support, and read-only Tools -> Do I Own This GUI entry point.
* Commit: `831d363`
* Full test suite passed: 182 tests OK.

* Completed v0.5 release audit rerun: main app launch, collection load, Upgrade Advisor dialog, manual candidate analysis, collection lookup, upgrade analysis, CSV export, Buy Advisor, Want List Generator, Collection Gap Report, Portfolio Import Preview, full test suite, targeted upgrade scenarios, WANT_LIST interaction, and random world base-metal non-upgrade all passed. No source defects required fixes.
* Commit: `36fc71b`
* Full test suite passed: 171 tests OK.
* Note: `AI_HANDOFF.md` was requested but is not present in this repository.

### 2026-06-15

* Completed v0.7 release audit: main app launch, Portfolio Dashboard opens, collection totals display correctly, estimated value calculation works, melt value subtotal works, Newfoundland progress displays correctly, Canadian silver progress displays correctly, 1859 Large Cent progress displays correctly, top gap-fill targets display correctly, top upgrade targets display correctly, duplicate-heavy report works, WANT_LIST progress displays correctly, CSV export works, Markdown export works, and full test suite passed. No release-blocking defects found.
* Commit: `cabd83c`
* Full test suite passed: 153 tests OK.
* Audit test suite passed: 22 tests OK.
* All targeted scenarios covered: collection with no silver, collection with silver, empty WANT_LIST, populated WANT_LIST, heavy duplicates, Newfoundland-focused collection, Canadian silver-focused collection, missing-value records, empty collection.

* Implemented v0.7 Portfolio Dashboard with high-level collection health overview showing total items, countries, estimated value, melt value, Newfoundland progress, Canadian silver progress, 1859 Large Cent progress, top gap-fill targets, top upgrade targets, duplicate-heavy areas, and WANT_LIST progress. GUI integration (Tools → Portfolio Dashboard) with CSV and Markdown export.
* Commit: `714e875`
* Full test suite passed: 131 tests OK.
* Portfolio dashboard unit tests passed: 15 tests OK.
* All targeted scenarios covered: collection with no silver, collection with silver, empty WANT_LIST, populated WANT_LIST, heavy duplicates, Newfoundland-focused collection, Canadian silver-focused collection, missing-value records, empty collection.

* Completed v0.6 release audit: main app launch, MeltValueEngine, ASWReferenceLoader, ManualSpotPriceProvider, ApiSpotPriceProvider, API failure fallback, 24-hour cache, Buy Advisor integration, Upgrade Advisor integration, melt value as supporting factor only, non-silver coins no false melt values, and full test suite passed. No release-blocking defects found.
* Commit: `2aed7a0`
* Full test suite passed: 99 tests OK.
* Audit test suite passed: 17 tests OK.
* All targeted scenarios covered: Canadian silver dime, Canadian silver quarter, Newfoundland silver, 1859 Large Cent non-silver, random world base metal non-silver, API failure fallback, manual spot price override.

* Implemented v0.6 Melt Value Engine with provider abstraction (ManualSpotPriceProvider, ApiSpotPriceProvider), 24-hour spot price caching, API failure fallback logic, and integration into Buy Advisor and Upgrade Advisor as supporting factor.
* Added MeltValueEngine core class, ASWReferenceLoader for parsing ASW_REFERENCE sheet, and dataclasses (MeltValueResult, ASWReferenceEntry).
* Integrated melt value into Buy Advisor and Upgrade Advisor reports with melt value fields in recommendation dataclasses and melt value analysis in explanations.
* Added comprehensive unit tests for MeltValueEngine, ASWReferenceLoader, and spot price providers (29 tests).
* Added regression tests for Buy Advisor and Upgrade Advisor to ensure melt value integration doesn't break existing functionality.
* Full test suite passed: 99 tests OK.

* Completed v0.5 release audit: main app launch, Upgrade Advisor GUI integration, manual candidate entry, collection lookup, upgrade analysis report, CSV export, Buy Advisor, Want List Generator, Collection Gap Report, Portfolio Import Preview, and full test suite passed. No release-blocking defects found. Only patchable cleanup items (pending commit hashes) were fixed.
* Commit: `f3eae0e`
* Full test suite passed: 60 tests OK.
* Upgrade Advisor unit tests passed: 13 tests OK.
* All targeted scenarios covered: better grade replacement, same-grade duplicate, lower-grade candidate, Newfoundland upgrade, Canadian silver upgrade, 1859 Large Cent upgrade, no-match scenario (random world base metal non-upgrade).

* Implemented v0.5 Upgrade Advisor with grade improvement, value improvement, and Adam-specific priority scoring (Newfoundland, Canadian silver, 1859 Large Cents). Provides verdicts (Strong Upgrade, Upgrade, Hold Existing, Duplicate, Pass) with human-readable explanations. Read-only analysis with GUI integration (Tools → Upgrade Advisor) and CSV export.
* Commit: `4601863`
* Added Upgrade Advisor backend engine with `UpgradeAdvisor` class and `UpgradeRecommendation` dataclass.
* Added GUI Tools → Upgrade Advisor menu with manual candidate entry form, collection lookup, upgrade analysis report display, and CSV export.
* Added comprehensive unit tests for Upgrade Advisor covering grade comparison scenarios, Adam priority tests, WANT_LIST integration tests, read-only behavior tests, and CSV export tests.
* Full test suite passed: 60 tests OK.

* Finalized `v0.4` release state after confirming the full test suite passed with 47 tests OK; release includes the world base-metal Buy Advisor guardrail.
* Commit: `af2e5c4`
* Added Buy Advisor guardrail for random world base-metal purchases so negative-priority, zero-impact, low-liquidity candidates downgrade to Neutral before purchase verdict calculation.
* Commit: `2aec691`
* Completed v0.4 integration audit: main app launch, Buy Advisor with and without staged `WANT_LIST` context, duplicate override behavior, price analysis, Collection Gap Report, Want List Generator, Portfolio Preview, and full test suite passed. No code fixes were required.
* Commit: `7e17d42`
* Integrated Collection Intelligence into Buy Advisor so collection gaps, generated want-list targets, Newfoundland/1859 priorities, and staged `WANT_LIST` intent add explainable Adam Priority boosts and collection impact scoring.
* Commit: `4c4b854`
* Connected staged workbook `WANT_LIST` intent to Want List Generator rankings, including explicit-target scoring, recommendation explanations, table display, and Markdown/CSV export.
* Commit: `8f11122`
* Added Tools -> Want List Preview for read-only workbook `WANT_LIST` review and CSV export; no Want List Generator or Buy Advisor integration was added.
* Commit: `eced7d9`
* Added legacy `WANT_LIST` staging parser for acquisition intent records, including empty sheet handling, invalid row skips, no-mutation checks, and deterministic priority ordering tests.
* Commit: `b8fa9fa`
* Finalized `v0.3`: created and pushed Git tag `v0.3`, confirmed release audit passed, and added the v0.4 WANT_LIST integration plan.
* Commit: `fab99b0`
* Completed v0.3 release audit: main app launch, CSV import, Portfolio Import Preview, Buy Advisor, Collection Gap Report, and full test suite passed. Updated project state to reflect v0.3 release-candidate status.
* Commit: `20513d9`
* Refined Collection Gap Report MVP with structured country/denomination series rows, Tier 1/Tier 2 prioritization, suggested next acquisitions, and CSV export.
* Commit: `701765a`
* Added Portfolio Import Preview GUI for legacy workbook staging review and CSV report export; no final import confirmation or collection writes were added.
* Commit: `c50eb12`
* Added Phase 1 legacy portfolio staging importer for safe `CORE_RAW` and `SLABS` workbook previews, duplicate detection, skipped-row reporting, and no-write collection safety tests.
* Commit: `5e2732b`
* Added portfolio integration roadmap for phased legacy workbook migration from inventory import through app dashboard metrics.
* Commit: `b3d17bc`
* Added legacy portfolio import spec for `Adam_Collection_Portfolio_PRO_LEVEL.xlsx`, including workbook sheet inspection, field mapping, importer design, and downstream system recommendations.
* Commit: `217c467`
* Added Collection Intelligence Engine, Collection Gap Report MVP, Want List Generator MVP, Markdown/CSV exports, Auction Evaluator spec, and engine tests.
* Commit: `259ad42`
* Added Adam-specific collection priorities to guide Collection Gap Report, Buy Advisor, and acquisition-planning work.
* Commit: `f9014c3`
* Added maintenance rule requiring completed tasks to update `PROJECT_STATE.md` and `TASK_QUEUE.md`, run tests when available, commit changes, and record commit hashes.
* Commit: `ba66958`
* Added test infrastructure hardening: converted script-style tests into `unittest` tests.
* Added isolated test fixtures in `test_data/`.
* Added `run_tests.bat`.
* Added `TESTING.md`.
* Added GitHub Actions workflow for push and pull-request test runs.
* Added `TASK_QUEUE.md` with task statuses and changelog.
* Added `PROJECT_STATE.md` as the concise project status snapshot.
* Commit: `ac1d4e7`
