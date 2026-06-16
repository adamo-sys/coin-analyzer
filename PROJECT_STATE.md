# Project State

## Current Version

* Current release version: `v1.2-dev`
* Current Git branch: `main`
* Last updated date: 2026-06-16

## Last Release Tag

* Most recent Git tag: `v1.1`
* Summary of what was included: Shared Session Context for load-once workbook and WANT_LIST reuse across collector tools.
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

## Known Bugs

* Direct multi-module `py -m unittest ...` commands can be flaky in this environment due to the Windows Python launcher; use `run_tests.bat` as the reliable suite command.
* GUI autocomplete currently prints suggestions to the console instead of showing a dropdown.
* Experimental detection and template matching are incomplete and should remain manual-verification-only.
* Numista API integration is not implemented and is blocked by API key, terms, pricing, and access review.
* JSON storage is simple and may not scale well for large collections.
* Many collection rows have no `Estimate (CAD)`, limiting Buy Advisor max-bid accuracy.
* No automated GUI tests currently cover Tkinter workflows.

## Active Roadmap

1. Improve Buy Advisor validation messages
2. Add autocomplete for country/denomination
3. Decide whether acquisition workflow guidance should become visible in Buy Advisor reports
4. Build v1.3 Collection Dashboard release line
5. Expand normalization fixtures for country, denomination, and variety edge cases
6. Build Auction Evaluator implementation from `AUCTION_EVALUATOR_SPEC.md`
7. Add image preview in collection list
8. Add batch editing
9. Add undo/redo
10. Add backup/restore
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

Perform a focused v1.2 acceptance audit for Listing Analyzer, then tag v1.2 if it passes.

## Project Architecture

* Main application entry point: `coin_collection_gui.py` launches the primary Tkinter collection manager. `main.py` launches the older `gui.py` entry point.
* Collection management system: `coin_collection.py` defines `CoinItem`, `CoinCollection`, and `CoinCollectionApp`; it handles JSON persistence, CRUD, search, CSV import/export, and collection summaries.
* Upgrade Advisor system: `upgrade_advisor.py` evaluates candidate coins against existing collection for upgrade potential, with grade improvement, value improvement, and Adam-specific priority scoring (Newfoundland, Canadian silver, 1859 Large Cents). Provides verdicts (Strong Upgrade, Upgrade, Hold Existing, Duplicate, Pass) with human-readable explanations. Read-only analysis with GUI integration (Tools → Upgrade Advisor) and CSV export.
* Collection Intelligence system: `collection_intelligence.py` powers gap reports, want lists, duplicate/upgrade detection, Adam-specific priority scoring, staged `WANT_LIST` ranking boosts, and future evaluator inputs.
* Focused Collection Intelligence system: `focused_collection_intelligence.py` provides reusable manual candidate classification for the Do I Own This workflow, staged WANT_LIST context awareness, Buy Advisor duplicate/upgrade detection, and Upgrade Advisor match/upgrade decisions, including fuzzy matching, grade comparison, duplicate/upgrade detection, want-list matching, gap detection, recommendation, confidence, reasons, and warning flags.
* Acquisition Workflow system: `acquisition_workflow.py` consumes focused Collection Intelligence results and asking price to produce deterministic acquisition guidance. Buy Advisor stores the workflow result as supporting structured context while preserving existing user-visible verdict behavior; Do I Own This shows acquisition guidance only when asking price is entered.
* Shared Session Context system: `session_context.py` stores the session workbook path, staged collection preview counts, staged WANT_LIST intents, load timestamp, warnings, and errors for reuse by GUI tools while keeping fallbacks intact.
* Listing Analyzer system: `listing_analyzer.py` defines `ListingCandidate` and `ListingAnalyzer`, validates stored-only URLs, computes total cost, parses basic candidate fields from listing text, and routes recommendations through `AcquisitionWorkflow`.
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

## Recent Changes

### 2026-06-16

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
