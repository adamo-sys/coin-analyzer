# Project State

## Current Version

* Current release version: `v0.2` latest tagged release; current working state includes post-`v0.2` test infrastructure and project documentation updates.
* Current Git branch: `main`
* Last updated date: 2026-06-15

## Last Release Tag

* Most recent Git tag: `v0.2`
* Summary of what was included: collection CSV import support, GUI import entry point, and CSV import tests.

## Completed Features

* Desktop collection manager: Tkinter GUI for adding, editing, deleting, viewing, and searching coin records.
* JSON collection storage: stores collection data in `data/collection.json`.
* Numista Excel import: imports Numista `.xlsx` exports with field mapping and duplicate detection.
* CSV import: imports simple collection CSV files with quantity expansion.
* CSV export: exports collection records with core and Numista fields.
* Collection analysis: summarizes countries, years, denominations, and Numista coverage.
* Buy Advisor: provides rule-based purchase recommendations, price checks, priority scoring, and liquidity scoring.
* Manual entry support: allows manually entered collection items and basic autocomplete suggestions from Numista-backed data.
* Experimental image detection: CV/OCR-based identification exists but is suggestion-only and not treated as truth.
* Test infrastructure: root-level `unittest` discovery, isolated `test_data` fixtures, `run_tests.bat`, `TESTING.md`, and GitHub Actions workflow.
* Task queue: `TASK_QUEUE.md` tracks prioritized work, status, and changelog entries.
* Collection Intelligence Engine: reusable analysis for country, denomination, series, missing years, completion percentages, duplicates, upgrade candidates, and acquisition priorities.
* Collection Gap Report MVP: Tools menu report with missing dates, completion percentages, upgrade opportunities, duplicate holdings, priority acquisition targets, and Markdown export.
* Want List Generator MVP: top acquisition targets with estimated impact and recommendation reasons, plus Markdown and CSV export.
* Auction Evaluator draft spec: documents how the future evaluator should consume the Collection Intelligence Engine.
* Legacy portfolio import spec: documents how `Adam_Collection_Portfolio_PRO_LEVEL.xlsx` should be staged, mapped, and consumed by future app systems.
* Portfolio integration roadmap: phases the legacy workbook migration from safe inventory staging through dashboard replacement.
* Legacy portfolio staging importer: safely previews `CORE_RAW` and `SLABS` workbook rows, detects likely duplicates, reports skipped rows and warnings, and does not modify `data/collection.json`.

## Known Bugs

* Local test execution depends on a working Python installation; the current Codex sandbox reports `No installed Python found!`.
* Some README text has encoding/mojibake artifacts in tree diagrams and symbols.
* `analyze_collection_gaps()` can divide by zero for an empty collection.
* GUI autocomplete currently prints suggestions to the console instead of showing a dropdown.
* Experimental detection and template matching are incomplete and should remain manual-verification-only.
* Numista API integration is not implemented and is blocked by API key, terms, pricing, and access review.
* JSON storage is simple and may not scale well for large collections.
* Many collection rows have no `Estimate (CAD)`, limiting Buy Advisor max-bid accuracy.
* No automated GUI tests currently cover Tkinter workflows.

## Active Roadmap

1. Improve Buy Advisor validation messages
2. Add autocomplete for country/denomination
3. Connect legacy `WANT_LIST` and `TARGETS` staging to Buy Advisor
4. Build Melt Value Engine using `ASW_REFERENCE` and workbook ASW fields
5. Build Upgrade Advisor using `UPGRADE_TARGETS`
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

Improve Buy Advisor validation messages.

## Project Architecture

* Main application entry point: `coin_collection_gui.py` launches the primary Tkinter collection manager. `main.py` launches the older `gui.py` entry point.
* Collection management system: `coin_collection.py` defines `CoinItem`, `CoinCollection`, and `CoinCollectionApp`; it handles JSON persistence, CRUD, search, CSV import/export, and collection summaries.
* Buy Advisor system: `buy_advisor.py` contains rule-based recommendation logic for duplicates, upgrades, collection gaps, value data, priority, liquidity, landed cost, and purchase verdicts.
* Collection Intelligence system: `collection_intelligence.py` powers gap reports, want lists, duplicate/upgrade detection, Adam-specific priority scoring, and future evaluator inputs.
* CSV import system: `CoinCollection.import_from_csv()` imports simple CSV files; `numista_importer.py` imports Numista Excel exports; `csv_exporter.py` exports analyzer results with Numista search URLs.
* Legacy portfolio staging system: `legacy_portfolio_importer.py` parses `CORE_RAW` and `SLABS` from the legacy workbook into reviewable staged `CoinItem` records, future metadata, duplicate buckets, skipped rows, and summary text without saving collection data.
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

### 2026-06-15

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
