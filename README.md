# Coin Analyzer

Current version: `v1.0`

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
3. Open Tools -> Do I Own This?
4. Enter a candidate item: country, denomination, year, type or series, variety, grade, certification details, asking price, and notes.
5. Optionally load the legacy workbook WANT_LIST context for the session.
6. Review ownership status, duplicate risk, upgrade status, WANT_LIST status, collection impact, max rational price, recommendation, confidence, reasons, and warnings.
7. If the item looks promising, compare it with Buy Advisor or Upgrade Advisor before purchasing.
8. Export reports when needed for collection planning or records.

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

The v1.0 release-readiness audit passed with `203 tests OK`.

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

See [RELEASE_HISTORY.md](RELEASE_HISTORY.md) and [docs/releases/v1.0.md](docs/releases/v1.0.md) for release documentation.

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

- Improve Buy Advisor validation messages.
- Add GUI autocomplete for country and denomination entry.
- Decide whether Acquisition Workflow guidance should become more visible in Buy Advisor reports.
- Share session-loaded WANT_LIST context across Buy Advisor, Want List Generator, and Do I Own This.
- Expand normalization fixtures for country, denomination, and variety edge cases.

Future candidates:

- Build Auction Evaluator from `AUCTION_EVALUATOR_SPEC.md`.
- Add image preview in the collection list.
- Add batch editing, undo/redo, and backup/restore workflows.
- Evaluate SQLite storage for larger collections.

## Known Limitations

- Acquisition price guidance is deterministic internal guidance, not live market pricing.
- Experimental image/OCR modules exist in the repository but remain suggestion-only and manual-verification-only.
- WANT_LIST context loaded in Do I Own This is session-local and not persisted as app state.
- JSON storage is simple and may not scale well for very large collections.
- GUI workflows currently rely mostly on smoke testing rather than full automated UI coverage.

## Data Safety

- Production collection data lives in `data/collection.json`.
- Tests use `test_data/` fixtures and temporary files.
- Legacy portfolio import workflows stage previews first and do not overwrite collection data.
- Keep regular backups of the repository, collection JSON, and legacy workbook. See [docs/BACKUP.md](docs/BACKUP.md).
