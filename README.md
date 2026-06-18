# Coin Analyzer

Current version: `v2.0`

Latest tagged release: `v2.0`

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
- Collection Quality Engine: deterministic quality scoring for completeness, upgrade pressure, WANT_LIST progress, diversity, certification, strengths, weaknesses, and recommended actions.
- Smarter Acquisition Intelligence: simulates candidate impact on quality score, series completion, WANT_LIST progress, and upgrade opportunities.
- Series Tracker: tracks supported collecting goals, owned dates, missing dates, WANT_LIST targets, upgrade counts, and series priority.
- Photo Vault: metadata-only photo organization, linking, certification lookup, search, coverage metrics, and exports.
- Market Awareness Layer: local-only observed price, purchase, sale, and auction records with dashboard summaries and acquisition historical context.
- Smart Shopping Assistant: ranked purchase-opportunity workflow that combines WANT_LIST, acquisition impact, collection quality, series completion, upgrade resolution, and local market context.
- Collector Operating System: unified Collector Home and Collection Health Report that consolidate dashboard, quality, series, shopping, market, photo, and persistence findings.
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
4. Open Tools -> Collector Home for the unified overview.
5. Review Best Next Purchase, Highest Impact Opportunity, Top WANT_LIST Target, Series Closest To Completion, quality score, market activity, and photo coverage.
6. Open Tools -> Smart Shopping Assistant to compare multiple opportunities at once.
7. Enter candidate listings or rely on loaded WANT_LIST context.
8. For a single pasted listing, use Tools -> Listing Analyzer.
9. If a listing needs manual confirmation, compare it with Do I Own This, Buy Advisor, or Upgrade Advisor before purchasing.
10. Reuse the same shared context in Want List Generator, Portfolio Import Preview, and related tools without repeatedly selecting the workbook.
11. Open Tools -> Collection Health Report when you want strengths, weaknesses, priorities, recommended actions, and persistence expectations in one report.
12. Export reports when needed for collection planning or records.

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

The v2.0 Collector Operating System development suite passed with `309 tests OK`.

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
| `v1.3` | `dfbea9bd93e617e3b3a0067d56e15b3d14c69c1e` | Collection Dashboard for actionable collection priorities, gaps, upgrades, WANT_LIST opportunities, and exports. |
| `v1.4` | `7cc5a7cc4b0e99a01e7515b89d11089461ea097d` | Collection Quality Engine for explainable strengths, weaknesses, category scores, and recommended actions. |
| `v1.5` | `080b70b106e19de0739fab172993846999edb2bd` | Smarter Acquisition Intelligence with deterministic acquisition impact simulation and listing/dashboard integration. |
| `v1.6` | `09b201cb0a5f394c957af48081e10e7f200b8533` | Series Tracker for supported collecting goals, completion, missing dates, WANT_LIST targets, upgrades, and priority rankings. |
| `v1.7` | `b650a141e1061979506f19402360239d69f68073` | Photo Vault for metadata-only photo organization, linking, certification lookup, coverage metrics, and exports. |
| `v1.8` | `425fb2597b95e410e4c9c49465dd8b12e080ace3` | Market Awareness Layer for local observed prices, purchases, sales, auction outcomes, dashboard summaries, acquisition context, and exports. |
| `v1.9` | `bf7e33648e6d150ffa7193cdddbbe493cb50c7fb` | Smart Shopping Assistant for ranked purchase opportunities, Best Next Purchase, impact-aware recommendation statuses, dashboard summaries, and exports. |
| `v2.0` | Pending tag verification | Collector Operating System with unified Collector Home, Collection Health Report, workflow guidance, persistence audit, dashboard/quality/series/shopping/market/photo consolidation, and exports. |

See [RELEASE_HISTORY.md](RELEASE_HISTORY.md) and [docs/releases/v1.0.md](docs/releases/v1.0.md) for release documentation.

## Which Tool To Use

- Use Collector Home when you want the unified starting point for what to focus on next.
- Use Collection Health Report when you want consolidated strengths, weaknesses, priorities, recommended actions, and persistence expectations.
- Use Listing Analyzer when starting from a real listing title, asking price, shipping cost, seller notes, or URL.
- Use Smart Shopping Assistant when comparing multiple opportunities and deciding what to buy next.
- Use Do I Own This? when manually checking a candidate coin or banknote without listing context.
- Use Buy Advisor when you already know the candidate details and want the legacy buy report format with pricing, priority, liquidity, and collection-intelligence factors.
- Use Collection Dashboard when you want the fastest overview of collection size, strengths, gaps, upgrade opportunities, WANT_LIST priorities, and next focus areas.
- Use Collection Quality Engine outputs inside Collection Dashboard when you want explainable quality scores, strengths, weaknesses, and ranked improvement actions.
- Use acquisition impact output from Listing Analyzer when you need to know how much a candidate improves the collection, not just whether it is buyable.
- Use Series Tracker output when you want to know which supported series are closest to completion and which dates matter next.
- Use Photo Vault output when you want to link and search photo metadata for collection items, candidates, references, auction wins, and sold items.
- Use Market Awareness output when you want to track what you observed, paid, sold, or bid locally without relying on live pricing.
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

- Perform post-v2.0 release packaging and backup verification.
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

The analyzer parses basic candidate details from pasted text, including country, denomination, year, grade, certifier, and simple variety terms. It then reuses Shared Session Context, WANT_LIST context, Collection Intelligence, Acquisition Workflow, and Acquisition Impact Engine to report ownership, duplicate, upgrade, want-list, collection impact, max rational price, acquisition impact score, quality impact, completion impact, recommendation reasoning, and recommendation.

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
- Collection Dashboard: CSV and Markdown export.
- Collection Quality Engine: CSV and Markdown export.
- Series Tracker: CSV and Markdown export.
- Photo Vault: CSV and Markdown export.
- Market Awareness Layer: CSV and Markdown export.
- Smart Shopping Assistant: CSV and Markdown export.
- Collector Home: CSV and Markdown export.
- Collection Health Report: CSV and Markdown export.

Listing Analyzer is currently a read-only on-screen workflow and does not export its result yet.

## Collector Operating System

Collector Operating System v2.0 consolidates the app's planning tools into a unified read-only workflow.

Tools:

- Collector Home: quick entry point for collection summary, best next purchase, highest-impact opportunity, top WANT_LIST target, closest supported series, quality score, recent market activity, photo coverage, and suggested workflow steps.
- Collection Health Report: consolidated report combining dashboard snapshot, quality report, series reports, Smart Shopping recommendations, market summary, strengths, weaknesses, priorities, recommended actions, and persistence findings.

Workflow intent:

1. Review Collector Home.
2. Evaluate specific opportunities in Listing Analyzer.
3. Compare opportunities in Smart Shopping Assistant.
4. Reference Photo Vault and Market Awareness context.
5. Use Dashboard and Collection Health Report for planning and recordkeeping.

Persistence expectations:

- Collection JSON and series definitions survive restart.
- Shared Session Context, market records, photo records, and shopping candidates are runtime/local supplied structures unless future persistence is added.
- No collection data is modified by Collector Home or Collection Health Report.

Known limitations:

- Collector Home and Collection Health Report are consolidation/reporting layers, not new decision engines.
- Market, photo, and shopping persistence remains intentionally lightweight in v2.0.
- No OCR, image recognition, scraping, pricing APIs, market forecasting, or Numista expansion.

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

## Collection Quality Engine

The Collection Quality Engine evaluates collection strength as decision support, not as a vanity score. It uses only available local collection data and staged WANT_LIST context.

Score categories:

- Completeness: observed series completion, collection gaps, and missing dates.
- Upgrade: duplicate-based upgrade opportunities and grade improvement pressure.
- WANT_LIST Progress: completed, remaining, and high-priority staged WANT_LIST targets.
- Diversity: countries, denominations, and series represented.
- Certification: certified/slabbed evidence versus raw items.

Outputs:

- Overall Quality Score
- Category scores with explanations and supporting metrics
- Top strengths
- Top weaknesses
- Ranked recommended actions with why they matter and expected impact

The dashboard displays the quality score, strengths, weaknesses, and top recommended actions. The quality report also supports CSV and Markdown export.

Known limitations:

- No rarity guides, market pricing, population reports, or external value estimates are used.
- Certification coverage depends on available text fields such as notes, comments, certifier, or certification number.
- WANT_LIST progress depends on staged workbook WANT_LIST context being loaded.

## Smarter Acquisition Intelligence

The Acquisition Impact Engine answers how much a candidate improves the collection if acquired.

It simulates:

1. Current collection.
2. Add candidate, or replace the weaker matching item for better-grade upgrade scenarios.
3. Recalculate quality metrics.
4. Measure quality, completion, WANT_LIST, and upgrade deltas.

Impact categories:

- LOW
- MEDIUM
- HIGH
- MAJOR

Impact outputs:

- Acquisition Impact Score from 0 to 100
- Quality score before and after
- Series completion before and after
- Upgrade opportunity impact
- WANT_LIST completion impact
- Recommendation reasoning such as quality gain, completion gain, WANT_LIST resolution, upgrade impact, and priority-series signals

Known limitations:

- No market pricing, rarity guides, population reports, web scraping, OCR, or Numista expansion.
- Impact simulation is deterministic planning guidance and does not modify collection data.
- Upgrade scenarios assume the candidate replaces the weaker matching example for impact measurement.

## Series Tracker

The Series Tracker shows progress within supported collecting goals using local collection and staged WANT_LIST data.

Supported series:

- Newfoundland 5 Cents
- Newfoundland 10 Cents
- Newfoundland 20 Cents
- Newfoundland 50 Cents
- Newfoundland 1 Cent
- Canadian Large Cents
- Canadian Small Cents
- Canadian Silver Dollars

Series outputs:

- Series name
- Owned dates
- Missing dates
- Completion percentage
- WANT_LIST count
- Upgrade count
- Priority score

Priority scoring considers:

- Near-completion opportunities
- WANT_LIST matches
- Duplicate-based upgrade opportunities
- Collection-quality impact signals
- Adam-specific priority weight built into the series definition

Known limitations:

- Definitions identify supported series; they do not include fabricated master mintage checklists.
- Completion uses actual owned dates and missing years inside the observed owned date span.
- Sparse series with only one owned date may not show missing dates until the observed span expands.
- No market pricing, rarity guides, OCR, scraping, or Numista expansion.

## Photo Vault

The Photo Vault is a metadata-only photo organization layer. It links local photo paths to collection items, candidate purchases, reference images, auction records, and sold examples.

Supported photo types:

- Collection Photo
- Candidate Photo
- Reference Photo
- Auction Photo
- Sold Photo

Recommended folders:

- `coin_photos/collection`
- `coin_photos/candidates`
- `coin_photos/references`
- `coin_photos/auction_wins`
- `coin_photos/sold`

Photo records can store:

- File path
- Photo type
- Linked collection item ID
- Linked candidate ID
- Linked coin name
- Created date
- Notes
- Optional ICCS, PCGS, or NGC certification number

Search supports:

- Certification number
- File name
- Coin name
- Notes

Dashboard coverage metrics:

- Items with photos
- Items without photos
- Collection photo coverage percentage
- Certified coins with photos percentage

Known limitations:

- The vault does not move files automatically.
- The vault does not perform OCR, image recognition, AI grading, scraping, or Numista lookups.
- Photo records are metadata objects; persistence can be added later if needed.

## Market Awareness Layer

The Market Awareness Layer is personal market memory, not live pricing. It records what was observed, purchased, sold, or bid on locally so future purchase decisions can be compared against the collector's own history.

Tracked records:

- Observed prices: item, country, denomination, year, grade, observed price, shipping, total observed cost, source, date, notes, and linked photo references.
- Purchases: item, purchase price, shipping, total cost, seller/source, date, notes, and linked photo references.
- Sales: item, sale price, fees, net proceeds, buyer/source, date, notes, and linked photo references.
- Auctions: item, bid amount, winning bid, Won/Lost/Passed result, source, date, notes, and linked photo references.

Dashboard integration:

- Purchases tracked
- Sales tracked
- Observations tracked
- Auctions tracked
- Average observed price
- Recent local market activity

Acquisition Impact integration:

- Candidate analysis can show local historical observed-price context such as below, within, or above the recent observed range.
- This context is informational and does not replace the deterministic acquisition recommendation rules.

Known limitations:

- No scraping, URL fetching, market APIs, live pricing, market prediction, OCR, image recognition, or Numista lookup.
- Market records are in-memory/local data structures unless a future persistence layer is added.
- Historical context depends entirely on records the collector has entered or loaded locally.

## Smart Shopping Assistant

The Smart Shopping Assistant combines existing collection intelligence systems into one ranked purchase-opportunity workflow. It is designed to answer what to buy next, which opportunities deserve attention, which are overpriced relative to local observations, and which purchases improve the collection most.

Inputs:

- Manual shopping candidates
- Listing Analyzer candidates
- Staged WANT_LIST targets
- Local Market Awareness observations
- Existing acquisition candidates

Ranking methodology:

- Acquisition Impact Score
- Quality score delta
- Series completion delta
- WANT_LIST priority
- Upgrade opportunity impact
- Local historical market context
- Existing Acquisition Workflow recommendation

Recommendation statuses:

- STRONG BUY
- BUY
- NEGOTIATE
- WATCH
- PASS
- REVIEW

Dashboard integration:

- Best Next Purchase
- Top 5 Opportunities
- Highest Impact Candidate
- Highest Priority WANT_LIST Target

Known limitations:

- No scraping, URL fetching, market APIs, live pricing, market forecasting, OCR, image recognition, or Numista lookup.
- Ranking is deterministic planning guidance from local data and provided opportunities only.
- Smart Shopping Assistant does not modify collection data.

## Data Safety

- Production collection data lives in `data/collection.json`.
- Tests use `test_data/` fixtures and temporary files.
- Legacy portfolio import workflows stage previews first and do not overwrite collection data.
- Keep regular backups of the repository, collection JSON, and legacy workbook. See [docs/BACKUP.md](docs/BACKUP.md).
