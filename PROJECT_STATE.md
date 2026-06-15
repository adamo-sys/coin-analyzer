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

1. Implement Collection Gap Report
2. Add Markdown export for gap report
3. Improve Buy Advisor validation messages
4. Add autocomplete for country/denomination
5. Add Auction Evaluator draft spec
6. Add image preview in collection list
7. Add batch editing
8. Add undo/redo
9. Add backup/restore
10. Evaluate SQLite storage for larger collections

## Adam-Specific Collection Priorities

1. Newfoundland coinage: date runs, key dates, higher-grade examples, and 5 cent, 10 cent, 20 cent, and 50 cent focus.
2. 1859 Canadian Large Cents: variety attribution, Narrow 9 / Wide 9, 8 over 9 varieties, date and die variety analysis, and upgrade opportunities.
3. Canadian silver coinage: dimes, quarters, half dollars, and dollars.
4. Date run completion: identify missing years, prioritize easiest completions, and calculate completion percentages.
5. Upgrade-over-duplicate strategy: prefer quality upgrades, minimize duplicate purchases, and identify replacement candidates.
6. Budget-conscious acquisitions: maximize value per dollar spent, focus on high-ROI purchases, and highlight underpriced opportunities.
7. Collection gap reduction: generate want lists, rank acquisition targets, and recommend highest-impact purchases.

## Next Priority Task

Implement Collection Gap Report.

## Project Architecture

* Main application entry point: `coin_collection_gui.py` launches the primary Tkinter collection manager. `main.py` launches the older `gui.py` entry point.
* Collection management system: `coin_collection.py` defines `CoinItem`, `CoinCollection`, and `CoinCollectionApp`; it handles JSON persistence, CRUD, search, CSV import/export, and collection summaries.
* Buy Advisor system: `buy_advisor.py` contains rule-based recommendation logic for duplicates, upgrades, collection gaps, value data, priority, liquidity, landed cost, and purchase verdicts.
* CSV import system: `CoinCollection.import_from_csv()` imports simple CSV files; `numista_importer.py` imports Numista Excel exports; `csv_exporter.py` exports analyzer results with Numista search URLs.
* Testing framework: Python standard-library `unittest` discovery via `python -m unittest discover -s . -p "test_*.py"`, with fixture files in `test_data/` and Windows runner `run_tests.bat`.

## Development Notes

* Python 3.8+ is expected.
* Runtime dependencies are pinned in `requirements.txt`: `pytesseract`, `Pillow`, `opencv-python`, and `pandas`.
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
