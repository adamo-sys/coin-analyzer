# Coin Analyzer

Current version: `v1.3`

Latest tagged release: `v1.3`

Coin Analyzer is a local desktop application for managing a coin and banknote collection, evaluating possible acquisitions, and keeping collection priorities grounded in the actual holdings on disk.

The project is focused on practical collector decisions. A collector can enter a candidate coin or banknote and receive ownership status, duplicate detection, upgrade analysis, WANT_LIST status, an acquisition recommendation, and max rational price guidance without web scraping, live pricing APIs, OCR expansion, or automatic image recognition decisions.

## Project Overview

Coin Analyzer stores collection data locally in JSON and provides a Tkinter desktop GUI for collection management, analysis, and read-only acquisition guidance. Its current stable release centers on a deterministic Collection Intelligence Engine and Acquisition Workflow that help answer:

- Do I already own this?
- Is this a duplicate, downgrade, or better-grade upgrade?
- Is this an explicit WANT_LIST target?
- Does this fill a collection gap?
- Should I buy, pass, watch, negotiate, or review?

## What Problem It Solves

Collectors often compare possible purchases against incomplete date runs, duplicate holdings, upgrade opportunities, want-list notes, and budget constraints by hand. Coin Analyzer consolidates those checks into repeatable local workflows so a candidate can be reviewed consistently before money is spent.

The app is especially tuned for Adam-specific priorities:

- Newfoundland coinage
- 1859 Canadian Large Cents and varieties
- Canadian silver coinage
- Date-run completion
- Upgrade-over-duplicate strategy
- Budget-conscious acquisition decisions

## Core Features

- Collection manager: add, edit, delete, view, and search local collection records.
- Numista Excel import: import Numista `.xlsx` exports with field mapping and duplicate detection.
- CSV import and export: import simple collection CSV files and export collection data.
- Collection Intelligence Engine: classify manual candidates as owned, duplicate, upgrade, want-list match, collection gap, not relevant, or needs review.
- Shared Session Context: load a legacy collection workbook and WANT_LIST context once per app session for reuse across collector tools.
- Listing Analyzer: paste listing title, URL, price, shipping, notes, and description to get offline ownership, duplicate, upgrade, WANT_LIST, and acquisition guidance.
- Collection Dashboard: actionable overview of collection size, priorities, WANT_LIST opportunities, upgrade opportunities, collection gaps, and series completion.
- Do I Own This?: lightweight GUI workflow for manual candidate analysis with optional WANT_LIST context and asking-price guidance.
- Acquisition Workflow: deterministic BUY/PASS/WATCH/NEGOTIATE/REVIEW guidance with max rational price output.
- Buy Advisor: rule-based purchase recommendation support with collection-intelligence context while preserving duplicate and price-analysis behavior.
- Upgrade Advisor: compare candidates against existing holdings for upgrade, duplicate, downgrade, and priority scenarios.
- Collection Gap Report: analyze missing dates and completion percentages by country and denomination.
- Want List Generator: rank acquisition targets using gaps, priorities, and staged WANT_LIST intent.
- Legacy Portfolio Preview: safely stage `CORE_RAW`, `SLABS`, and `WANT_LIST` workbook data without modifying `data/collection.json`.
- Melt Value Engine: support silver melt-value calculations from internal ASW reference data.
- Portfolio Dashboard: summarize collection health, gaps, upgrades, duplicates, and WANT_LIST progress.

## Example Collector Workflow

1. Launch Coin Analyzer.
2. Load or review the local collection.
3. Use Tools -> Load Collection Context to select the legacy workbook once for the session.
4. Open Tools -> Listing Analyzer.
5. Paste listing title, optional URL, asking price, shipping, seller notes, and description.
6. Review ownership status, duplicate risk, upgrade status, WANT_LIST status, collection impact, max rational price, recommendation, confidence, reasons, and warnings.
7. If the listing needs manual confirmation, compare it with Do I Own This, Buy Advisor, or Upgrade Advisor before purchasing.
8. Reuse the same shared context in Want List Generator, Portfolio Import Preview, and related tools without repeatedly selecting the workbook.
9. Open Tools -> Collection Dashboard to review what to focus on next without manually running every report.
10. Export reports when needed for collection planning or records.

## Installation

Prerequisites:

- Python 3.8 or newer
- Windows is the primary tested desktop environment
- Tkinter available in the Python installation

Clone and install:

```powershell
git clone https://github.com/adamo-sys/coin-analyzer.git
cd coin-analyzer
py -m pip install -r requirements.txt
```

If the repository is already cloned, install dependencies from the project root:

```powershell
py -m pip install -r requirements.txt
```

## Running the Application

From the project root:

```powershell
py coin_collection_gui.py
```

The main data file is `data/collection.json`. Analysis and preview workflows are designed to be read-only unless the user explicitly performs a collection-management action.

## Running Tests

Use the project test runner:

```powershell
.\run_tests.bat
```

The v1.3 collection-dashboard development suite passed with `238 tests OK`.

The test suite uses isolated fixtures in `test_data/` and must not mutate production collection data in `data/collection.json`.

## Release History

| Version | Release Hash | Summary |
| --- | --- | --- |
| `v0.5` | `f90541b3622aeb0d846dc787437762f7600a6d35` | Stable Upgrade Advisor release with CI dependency compatibility fix. |
| `v0.6` | `d976f9ec3d0e95124013db5f10cffd503b1acb03` | Focused Collection Intelligence Engine and Do I Own This foundation. |
| `v0.7` | `3cf26ff6b07e7d0d39b4ff62a410bf753dece5c0` | Advisor decision-source consolidation on Collection Intelligence. |
| `v0.8` | `f3acc605024712a867046be24e3c32db3f18d854` | WANT_LIST context integration in candidate analysis. |
| `v0.9` | `af09668dd9b735479a0885445a7198302d6432f3` | Acquisition Workflow with deterministic max rational price guidance. |
| `v1.0` | `2c3d68bc65fcb2f3787f9a3d7624bd49675684c7` | Stable release candidate audit passed; production-ready v1.0 baseline. |
| `v1.1` | `0fd5e1fbe5807cf8889cee3ea94d5752acfdf06e` | Shared Session Context for load-once workbook and WANT_LIST reuse. |
| `v1.2` | `db001da4187af5a2bd2350bd956b2876007f7587` | Listing Analyzer for offline pasted listing evaluation. |
| `v1.3` | Pending tag verification | Collection Dashboard for actionable collection priorities, gaps, upgrades, WANT_LIST opportunities, and exports. |

See [RELEASE_HISTORY.md](RELEASE_HISTORY.md) and [docs/releases/v1.0.md](docs/releases/v1.0.md) for release documentation.

## Which Tool To Use

- Use Listing Analyzer when starting from a real listing title, asking price, shipping cost, seller notes, or URL.
- Use Do I Own This? when manually checking a candidate coin or banknote without listing context.
- Use Buy Advisor when you already know the candidate details and want the legacy buy report format with pricing, priority, liquidity, and collection-intelligence factors.
- Use Collection Dashboard when you want the fastest overview of collection size, strengths, gaps, upgrade opportunities, WANT_LIST priorities, and next focus areas.
- Use Want List Generator when planning what to look for next, not when evaluating one specific listing.
- Use Collection Gap Report when reviewing missing dates and completion percentages by country and denomination.

These tools overlap intentionally. Listing Analyzer is the fastest entry point for pasted listings; it reuses the same underlying Collection Intelligence and Acquisition Workflow instead of replacing them.

## Screenshot Placeholders

Screenshots are not committed yet. Recommended screenshot slots:

- Main application
- Collector Decision Center
- Do I Own This?
- Buy Advisor
- Upgrade Advisor
- Collection Gap Report
- WANT_LIST workflow

See [docs/screenshots/README.md](docs/screenshots/README.md) for suggested filenames and capture notes.

## Roadmap

Near-term maintenance candidates:

- Begin v1.4 Collection Scoring Engine planning.
- Improve Buy Advisor validation messages.
- Add GUI autocomplete for country and denomination entry.
- Decide whether Acquisition Workflow guidance should become more visible in Buy Advisor reports.
- Expand normalization fixtures for country, denomination, and variety edge cases.

Future candidates:

- Build Auction Evaluator from `AUCTION_EVALUATOR_SPEC.md`.
- Add image preview in the collection list.
- Add batch editing, undo/redo, and backup/restore workflows.
- Evaluate SQLite storage for larger collections.

## Known Limitations

- Acquisition price guidance is deterministic internal guidance, not live market pricing.
- Listing Analyzer stores URLs as reference data only; it does not scrape, fetch, or enrich listings.
- Experimental image/OCR modules exist in the repository but remain suggestion-only and manual-verification-only.
- Shared Session Context is per app session only; it is not persisted after closing the application.
- JSON storage is simple and may not scale well for very large collections.
- GUI workflows currently rely mostly on smoke testing rather than full automated UI coverage.

## Shared Session Context

Use Tools -> Load Collection Context to select a legacy workbook once per app session. The app stores the workbook path, previewed collection row counts, active WANT_LIST intent count, load timestamp, warnings, and errors in shared runtime state.

Tools that can reuse the shared WANT_LIST context include:

- Do I Own This?
- Acquisition Workflow guidance shown from Do I Own This
- Buy Advisor
- Want List Generator
- Portfolio Import Preview and Want List Preview where appropriate

If no context is loaded, tools fall back to their existing behavior and show unavailable or not-loaded status instead of failing.

## Listing Analyzer

Use Tools -> Listing Analyzer to evaluate a real-world listing without reconstructing the acquisition workflow by hand.

Supported inputs:

- Listing title
- URL, stored for reference only
- Asking price
- Shipping cost
- Seller
- Source
- Seller notes
- Description

The analyzer parses basic candidate details from pasted text, including country, denomination, year, grade, certifier, and simple variety terms. It then reuses Shared Session Context, WANT_LIST context, Collection Intelligence, and Acquisition Workflow to report ownership, duplicate, upgrade, want-list, collection impact, max rational price, and recommendation.

Known limitations:

- Fully offline and deterministic.
- No web scraping or URL fetching.
- No market-price API lookup.
- No OCR, image recognition, or AI grading.
- Listing parsing is intentionally basic and should be manually reviewed for ambiguous listings.

## Exports

Export support is intentionally report-specific:

- Collection data: CSV export.
- Collection Gap Report: CSV and Markdown export.
- Want List Generator: CSV and Markdown export.
- Portfolio Import Preview: CSV export.
- WANT_LIST Preview: CSV export.
- Upgrade Advisor: CSV export.

Listing Analyzer is currently a read-only on-screen workflow and does not export its result yet.

## Collection Dashboard

Use Tools -> Collection Dashboard for a read-only overview of the current collection and active WANT_LIST context.

Dashboard sections:

- Collection Snapshot: item count, WANT_LIST count, duplicates, upgrade opportunities, country count, denomination count, silver count, and certified count when available.
- Top Collection Priorities: closest completion targets, explicit WANT_LIST opportunities, and upgrade-focused next actions.
- Best Upgrade Opportunities: duplicate groups where the highest-grade item should guide replacement decisions.
- WANT_LIST Priorities: highest-priority staged workbook WANT_LIST targets and acquisition candidates.
- Collection Gaps: missing date runs and suggested next acquisitions using existing gap-report logic.
- Series Completion: deterministic completion percentages from actual owned years only.
- Collection Evolution: basic growth signal from available `date_added` values.

Exports:

- CSV
- Markdown

Known limitations:

- The dashboard does not estimate unknown values.
- Series completion uses existing collection years and known contiguous date spans; sparse or irregular series may need manual interpretation.
- Collection evolution depends on `date_added` being present in collection records.

## Data Safety

- Production collection data lives in `data/collection.json`.
- Tests use `test_data/` fixtures and temporary files.
- Legacy portfolio import workflows stage previews first and do not overwrite collection data.
- Keep regular backups of the repository, collection JSON, and legacy workbook. See [docs/BACKUP.md](docs/BACKUP.md).
