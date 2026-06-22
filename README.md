# Coin Analyzer

Current version: `v5.4`

Latest tagged release: `v5.4`

Coin Analyzer is a local desktop application for managing a coin and banknote collection, evaluating possible acquisitions, and keeping collection priorities grounded in the actual holdings on disk.

The project is focused on practical collector decisions. A collector can enter a candidate coin or banknote and receive ownership status, duplicate detection, upgrade analysis, WANT_LIST status, an acquisition recommendation, and max rational price guidance without web scraping, live pricing APIs, automatic collection updates from OCR, or automatic image recognition decisions.

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
- Deal Hunter: import or manually enter eBay.ca-style listing rows, parse titles/descriptions, compare against collection and WANT_LIST context, flag risky/ambiguous listings, apply Adam's buying rules, and export deterministic deal reports without scraping or live pricing.
- Deal Hunter Ranking: merge large manual/CSV candidate pools, detect duplicate listings, rank opportunities by Deal Hunter score, Opportunity Engine score, collection fit, upgrades, gaps, WANT_LIST relevance, liquidity, risk, and budget fit, then export budget/category ranking reports.
- Deal Hunter Calibration: run offline collector-judgment cases against Deal Hunter and Ranking output to catch false BUY/PASS/REVIEW decisions, ranking misses, risk-flag misses, and explanation gaps before any live-source work.
- Live Deal Hunter Readiness: audit future live-source readiness, contracts, validation, staleness, rate-limit planning, and safety rules without fetching live listings.
- Live Deal Hunter: controlled-beta, user-triggered public RSS feed ingestion that validates, normalizes, deduplicates, ranks, and exports live listing opportunities through existing Deal Hunter, CandidatePool, Ranking, Opportunity, and Market Intelligence systems.
- Live Source Validation: deterministic trust layer for live source quality, listing validation, freshness checks, duplicate/malformed URL detection, source health scoring, REVIEW escalation, and CSV/Markdown export before live listings enter recommendation pipelines.
- Market Intelligence: estimate fair-value bands from local comparable sales and existing internal deal guidance, classify deal quality, explain confidence/risk, generate counterarguments, and export reports without scraping, APIs, or live pricing.
- Market Intelligence Automation: automatically enrich Deal Hunter, Ranking, Opportunity, Live Deal Hunter, and connector candidates with existing local Market Intelligence, collection relevance, evidence summaries, risk warnings, and review escalations while preserving original recommendations.
- Watchlists & Alerts: define editable series, specific coin, keyword, and custom watches, use Adam starter presets, scan existing deal/ranking/live/market-enriched candidates, generate on-demand alerts, score alert relevance, and export CSV/Markdown reports.
- Field Test & Tuning: run deterministic live-pipeline scenarios through validation, Deal Hunter, ranking, market enrichment, watchlists, and alerts to measure pipeline health, opportunity quality, alert quality, and likely false positives before mobile expansion.
- Mobile Collector Companion: desktop/local mobile-oriented workflow layer for coin shows, dealer visits, antique markets, coin shops, and auction previews with quick decisions, collection context, field work mode, dashboard summaries, and CSV/Markdown export.
- Phone Photo Capture: metadata-only capture sessions for phone-captured coin, banknote, and listing photos with front/back pairing, missing-side checks, OCR/review readiness, Photo Vault/OCR adapters, Tools -> Phone Photo Capture, and CSV/Markdown export.
- OCR-Assisted Identification: review-only pipeline that turns captured photos and OCR text into explainable identification candidates with evidence, confidence, collection relevance, watchlist/want-list context, Tools -> OCR-Assisted Identification, and CSV/Markdown export.
- Mobile Collection Entry: review-only field workflow that converts OCR identification candidates into proposed collection-entry records with field confidence, collection/want-list/watchlist context, portfolio impact previews, APPROVE/REJECT/REVIEW decisions, Tools -> Mobile Collection Entry, and CSV/Markdown export without inserting records automatically.
- Collector Workflow Integration: end-to-end workflow session layer that coordinates photo capture, OCR identification, evidence review, collection context, mobile collection entry candidates, portfolio preview, final review, workflow health reporting, Mobile Companion summaries, Tools -> Collector Workflow Integration, and CSV/Markdown export without automatic collection mutation.
- Portfolio Performance: explain collection growth, local estimated value, series progress, acquisition performance, budget allocation, health score, strengths, weaknesses, risks, and focus areas using deterministic local data.
- External Listing Connectors: normalize local eBay CSV, Auction CSV, Dealer Inventory CSV, and Generic CSV files into a common listing model with validation, source tracking, duplicate-opportunity detection, and multi-source ranking compatibility.
- Opportunity Engine: answers "What should I buy next?" with deterministic local opportunity scoring, budget-aware recommendations, counterarguments, and CSV/Markdown export.
- Collection Dashboard: actionable overview of collection size, priorities, WANT_LIST opportunities, upgrade opportunities, collection gaps, and series completion.
- Collection Quality Engine: deterministic quality scoring for completeness, upgrade pressure, WANT_LIST progress, diversity, certification, strengths, weaknesses, and recommended actions.
- Smarter Acquisition Intelligence: simulates candidate impact on quality score, series completion, WANT_LIST progress, and upgrade opportunities.
- Series Tracker: tracks supported collecting goals, owned dates, missing dates, WANT_LIST targets, upgrade counts, and series priority.
- Photo Vault: metadata-only photo organization, linking, certification lookup, search, coverage metrics, integrity audit, and exports.
- Market Awareness Layer: local-only observed price, purchase, sale, and auction records with dashboard summaries and acquisition historical context.
- Smart Shopping Assistant: ranked purchase-opportunity workflow that combines WANT_LIST, acquisition impact, collection quality, series completion, upgrade resolution, and local market context.
- Shopping Explainability: explains existing BUY/PASS/WATCH/NEGOTIATE/REVIEW recommendations with confidence, primary reasons, supporting reasons, impact summaries, warnings, and collector notes.
- OCR Experiments: advisory-only OCR suggestion reports for candidate photos, with raw text, possible years, denominations, countries, note prefixes, certification numbers, deterministic confidence, warnings, manual-review requirement, persistence, and CSV/Markdown export.
- OCR Validation Layer: evaluates whether OCR output can be trusted with HIGH/MEDIUM/LOW trust levels, validation scores, findings, warnings, explanations, manual-review recommendations, and CSV/Markdown export.
- Workflow Integration: guided collector workflows that orchestrate existing Photo-Assisted Entry, OCR, OCR Validation, Smart Shopping, Shopping Explainability, Collection Dashboard, Quality, Integrity, Snapshot, and Photo Vault Audit systems without replacing them.
- Collector Home Dashboard: one daily dashboard for status cards, ranked actions, top opportunities, review queues, data safety, progress, workflow status, and CSV/Markdown export.
- Collector Companion Readiness and Status: v3.0 product audit for report/export consistency, end-to-end workflow quality, readiness checklist, workflow status, persistence, and CSV/Markdown export.
- Collector Operating System: unified Collector Home and Collection Health Report that consolidate dashboard, quality, series, shopping, market, photo, and persistence findings.
- Persistence Layer: local JSON app state for session metadata, last workbook/WANT_LIST paths, market records, photo records, shopping candidates, app preferences, backups, and import/export.
- Data Safety and Backup Hardening: local backup packages, manifests, verification, safe restore, `data/collection.json` and persisted-workbook backup coverage, data validation reports, Collection Recovery Reports, and collector export bundles.
- Collection Integrity Audit: read-only data trust report for duplicates, missing fields, invalid values, broken photo/market/certification references, backup readiness, and integrity scoring.
- Collection Snapshot System: point-in-time snapshots and comparison reports for collection growth, quality, integrity, photo coverage, series progress, market records, and shopping candidates.
- Mobile Readiness: deterministic audit report for desktop dependencies, service boundaries, mobile input friction, future endpoint mappings, dealer-table phone workflow, and readiness scoring.
- Mobile Companion Prototype: local desktop prototype for a single candidate -> analysis -> recommendation dealer-table workflow using existing collector engines.
- Photo-Assisted Entry: metadata-only photo reference workflow for attaching front, reverse, and reference photos to acquisition candidates before manual review and recommendation.
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
4. Open Tools -> Collector Home Dashboard for the daily "what should I do today?" view.
5. Review Collection Health, Acquisition Focus, Review Queue, Data Safety, Progress, ranked daily actions, and top opportunities.
6. Open Tools -> Smart Shopping Assistant to compare multiple opportunities at once.
7. Enter candidate listings or rely on loaded WANT_LIST context.
8. For a single pasted listing, use Tools -> Listing Analyzer.
9. If a listing needs manual confirmation, compare it with Do I Own This, Buy Advisor, or Upgrade Advisor before purchasing.
10. Reuse the same shared context in Want List Generator, Portfolio Import Preview, and related tools without repeatedly selecting the workbook.
11. Open Tools -> Collection Health Report when you want strengths, weaknesses, priorities, recommended actions, and persistence expectations in one report.
12. For a coin-in-hand review, open Tools -> Photo-Assisted Entry, attach front/reverse/reference photo paths, enter manual details, and generate a review report.
13. If you want advisory text extraction from a photo, open Tools -> OCR Experiment and manually review the suggestion report before using any result.
14. Open Tools -> Mobile Collection Entry to turn OCR identification candidates into review-only proposed entry records, then APPROVE, REJECT, or REVIEW before manually saving anything.
15. Export reports when needed for collection planning or records.

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

The v5.0 Mobile Collector Companion suite passed with `641 tests OK`.

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
| `v2.0` | `a661b06c846bdd0d5342ce892c350832c8907974` | Collector Operating System with unified Collector Home, Collection Health Report, workflow guidance, persistence audit, dashboard/quality/series/shopping/market/photo consolidation, and exports. |
| `v2.1` | `bd4897fbee4f8306b69fb369a2e81768631fb865` | Persistence Layer for local JSON session state, workbook/WANT_LIST paths, market records, photo records, shopping candidates, app preferences, backups, and import/export. |
| `v2.2` | `d84aa40334a6c3f859a996006bfe8005074ea6a4` | Data Safety and Backup Hardening with backup packages, manifests, verification, safe restore, validation reports, and export bundles. |
| `v2.3` | See verified tag `v2.3` | Mobile Readiness audit with desktop dependency findings, service boundary review, mobile input analysis, future endpoint mapping, phone workflow audit, readiness score, and exports. |
| `v2.4` | See verified tag `v2.4` | Mobile Companion Prototype with minimal candidate entry, concise recommendation report, provider abstractions, phone workflow simulation, dashboard summary, persistence, and exports. |
| `v2.4.1` | See verified tag `v2.4.1` | Critical Collection Backup Hardening with automatic collection JSON backup, persisted workbook copy support, recovery manifest flags, Collection Recovery Report, and enhanced Data Safety validation. |
| `v2.4.2` | See verified tag `v2.4.2` | Collection Integrity Audit with integrity score, duplicate detection, missing data checks, photo/market/certification integrity summaries, backup readiness integration, and CSV/Markdown export. |
| `v2.4.3` | See verified tag `v2.4.3` | Collection Snapshot System with persistent snapshots, collection growth metrics, quality/integrity/photo/series deltas, GUI snapshot workflows, and CSV/Markdown export. |
| `v2.5` | See verified tag `v2.5` | Photo-Assisted Entry with metadata-only photo candidate records, Photo Vault linking, Mobile Companion recommendation reuse, persistence, backup-compatible metadata, and CSV/Markdown review export. |
| `v2.5.1` | See verified tag `v2.5.1` | Photo Vault Hardening with integrity audit, coverage metrics, missing/duplicate/unlinked/invalid photo findings, Data Safety/recovery integration, and CSV/Markdown export. |
| `v2.5.2` | See verified tag `v2.5.2` | Shopping Explainability with confidence labels, primary/supporting reasons, impact summaries, collector notes, Listing Analyzer/Smart Shopping display integration, and CSV/Markdown export. |
| `v2.6` | See verified tag `v2.6` | OCR Experiments with advisory raw OCR text, possible field suggestions, deterministic confidence, manual-review requirement, persistence, Tools menu workflow, and CSV/Markdown export. |
| `v2.6.1` | See verified tag `v2.6.1` | OCR Validation Layer with trust levels, validation score, year/denomination/country/certification checks, warnings, explanations, Tools menu integration, and CSV/Markdown export. |
| `v2.7` | See verified tag `v2.7` | Workflow Integration with guided acquisition, collection review, photo review, daily collector summary, workflow status tracking, persistence, Tools menu entries, and CSV/Markdown export. |
| `v2.8` | See verified tag `v2.8` | Collector Home Dashboard with status cards, ranked daily actions, top opportunities, review queues, data safety, progress signals, persistence, and CSV/Markdown export. |
| `v2.9` | See verified tag `v2.9` | Collector Companion Release Candidate with menu cleanup, readiness checklist, report/export consistency audits, workflow audit, persistence, and CSV/Markdown export. |
| `v3.0` | See verified tag `v3.0` | Collector Companion milestone with final status report, full system audit, end-to-end workflow verification, release notes, and 475-test regression pass. |
| `v3.1` | See verified tag `v3.1` | eBay.ca-style Deal Hunter MVP with manual/CSV listing intake, deterministic parsing, collection-aware scoring, counterarguments, persistence, exports, and 494-test regression pass. |
| `v3.2` | See verified tag `v3.2` | Deal Hunter Workflow Refinement with improved parser coverage, risk flags, CSV import warnings, GUI import summaries, richer exports, and 505-test regression pass. |
| `v3.3` | See verified tag `v3.3` | Opportunity Engine with budget-aware collection opportunities, top opportunity groupings, counterarguments, Deal Hunter input support, and 515-test regression pass. |
| `v3.4` | See verified tag `v3.4` | Deal Hunter Ranking and Import Framework with candidate pools, import profiles, duplicate suppression, budget/category rankings, source summaries, CSV/Markdown export, and 527-test regression pass. |
| `v3.5` | See verified tag `v3.5` | External Listing Connectors with offline eBay/Auction/Dealer/Generic CSV normalization, validation, source tracking, duplicate-opportunity detection, multi-source ranking compatibility, and 538-test regression pass. |
| `v3.6` | See verified tag `v3.6` | Deal Hunter Calibration with offline collector-judgment fixtures, false recommendation detection, ranking/risk/explanation calibration reports, GUI workflow, and 550-test regression pass. |
| `v3.7` | See verified tag `v3.7` | Live Deal Hunter Readiness with future live-source contracts, validation reports, staleness flags, rate-limit/failure models, safety audit, GUI workflow, and 560-test regression pass. |
| `v3.8` | See verified tag `v3.8` | Market Intelligence with local comparable-sale fair-value bands, deal quality, opportunity confidence, risk summaries, counterarguments, Tools -> Market Intelligence, and 571-test regression pass. |
| `v3.9` | See verified tag `v3.9` | Portfolio Performance with growth analysis, acquisition performance, series progress, budget allocation, health score, snapshot comparison, Tools -> Portfolio Performance, and 579-test regression pass. |
| `v4.0` | See verified tag `v4.0` | Live Deal Hunter controlled beta with user-triggered RSS ingestion, source validation, listing normalization, CandidatePool/ranking/market-intelligence integration, GUI workflow, CSV/Markdown export, and 589-test regression pass. |
| `v4.1` | See verified tag `v4.1` | Live Source Validation with listing trust checks, freshness, source health scoring, REVIEW escalation, Live Deal Hunter pipeline gating, Tools -> Live Source Validation, and 602-test regression pass. |
| `v4.2` | See verified tag `v4.2` | Market Intelligence Automation with candidate enrichment, collection relevance summaries, fair-value evidence summaries, review escalation, Live Deal Hunter integration, Tools -> Market Intelligence Automation, and 615-test regression pass. |
| `v4.3` | See verified tag `v4.3` | Watchlists & Alerts with editable collector watches, Adam presets, on-demand alert generation, alert scoring, Tools -> Watchlists & Alerts, and regression coverage. |
| `v4.4` | See verified tag `v4.4` | Live Deal Hunter Field Test & Tuning with deterministic scenario library, pipeline health reporting, opportunity quality reporting, false-positive audit, Tools -> Field Test & Tuning, and regression coverage. |
| `v5.0` | See verified tag `v5.0` | Mobile Collector Companion with desktop/local mobile workflows, quick decisions, mobile collection context, field work mode, dashboard reporting, Tools -> Mobile Collector Companion, and regression coverage. |
| `v5.1` | See verified tag `v5.1` | Phone Photo Capture with metadata-only capture sessions, front/back workflows, listing-photo workflow, Photo Vault/OCR adapters, Mobile Companion summaries, Tools -> Phone Photo Capture, and 650-test regression pass. |
| `v5.2` | See verified tag `v5.2` | OCR-Assisted Identification with captured-photo-to-OCR-to-identification candidates, evidence model, confidence scoring, collection context, Mobile Companion integration, Tools -> OCR-Assisted Identification, CSV/Markdown export, and 660-test regression pass. |
| `v5.3` | See verified tag `v5.3` | Mobile Collection Entry with OCR-to-entry candidates, field confidence, collection context, portfolio impact previews, review decisions, Mobile Companion integration, Tools -> Mobile Collection Entry, CSV/Markdown export, and 669-test regression pass. |
| `v5.4` | See verified tag `v5.4` | Collector Workflow Integration with end-to-end sessions, review checkpoints, resume support, workflow health reporting, Mobile Companion integration, Tools -> Collector Workflow Integration, CSV/Markdown export, and 677-test regression pass. |

See [RELEASE_HISTORY.md](RELEASE_HISTORY.md), [docs/releases/v1.0.md](docs/releases/v1.0.md), [docs/releases/v5.1.md](docs/releases/v5.1.md), [docs/releases/v5.2.md](docs/releases/v5.2.md), [docs/releases/v5.3.md](docs/releases/v5.3.md), and [docs/releases/v5.4.md](docs/releases/v5.4.md) for release documentation.


## Release Prompt Archive

Release prompts are treated as project documentation and architecture history. They live under `project_docs/release_prompts/` and should be preserved instead of overwritten.

Current archived prompts include `project_docs/release_prompts/v5.1.txt`, `project_docs/release_prompts/v5.2.txt`, `project_docs/release_prompts/v5.3.txt`, and `project_docs/release_prompts/v5.4.txt`. Release notes should state whether each release prompt was archived and where it was stored.

## Which Tool To Use

- Use Collector Home Dashboard when you want one daily view of what needs attention, what is safe, what should be reviewed, and what opportunity matters most.
- Use Collector Companion Readiness when validating Collector Companion status, readiness, report/export consistency, and end-to-end workflow cohesion.
- Use Collector Home when you want the older consolidated starting report for collection summary and workflow steps.
- Use Data Safety Check before shutdowns, imports, release work, or restore attempts.
- Use Collection Integrity Audit before trusting Dashboard, Shopping Assistant, Series Tracker, Quality Engine, Acquisition Impact, Collection Health Report, or Mobile Companion output after major data changes.
- Use Create Snapshot after major collection sessions, imports, photo cleanup, market record updates, or shopping candidate reviews.
- Use Snapshot Report to compare current collection state against the previous saved snapshot.
- Use Collection Health Report when you want consolidated strengths, weaknesses, priorities, recommended actions, and persistence expectations.
- Use Listing Analyzer when starting from a real listing title, asking price, shipping cost, seller notes, or URL.
- Use Deal Hunter when comparing eBay.ca-style listing rows from manual entry or CSV import and you want collection-aware BUY/WATCH/NEGOTIATE/REVIEW/PASS guidance with counterarguments.
- Use Deal Hunter Ranking when you have many candidate listings and want top overall, budget-specific, Newfoundland, Canadian silver, banknote, upgrade, gap, and WANT_LIST opportunity rankings.
- Use Deal Hunter Calibration when you want to test Deal Hunter and Ranking behavior against known offline collector-judgment cases before adding or trusting a new source format.
- Use Live Deal Hunter Readiness when planning future live-source work and checking source contracts, validation, staleness, rate-limit policy, failure handling, and no-mutation guardrails.
- Use Live Deal Hunter when you explicitly want to fetch a public RSS feed, validate/normalize current listing data, rank opportunities, and export the controlled-beta report.
- Use Live Source Validation when you want to check whether a live source is trustworthy enough before its listings enter Deal Hunter, Ranking, Opportunity, or Market Intelligence.
- Use Market Intelligence when you want a local fair-value estimate, deal-quality label, confidence score, risk summary, counterargument, and buy rationale for one listing before live-source work exists.
- Use Market Intelligence Automation when you want a batch of candidates enriched with deal quality, confidence, fair-value evidence, collection relevance, risks, and review escalation while preserving the original recommendation.
- Use Watchlists & Alerts when you want to define collector targets and scan existing candidate outputs for on-demand watchlist matches, upgrade opportunities, collection gaps, high-priority opportunities, or rare target opportunities.
- Use Field Test & Tuning when you want deterministic live-pipeline test scenarios, pipeline health metrics, opportunity quality summaries, alert quality checks, and false-positive audit findings before expanding live or mobile workflows.
- Use Mobile Collector Companion when you want a desktop/local simulation of field decisions at a coin show, dealer visit, antique market, coin shop, or auction preview.
- Use Collector Workflow Integration when you want one guided flow from photo/OCR intake through evidence, collection context, entry candidate, portfolio preview, and final review.
- Use Portfolio Performance when you want portfolio-level growth, health, series progress, acquisition performance, budget allocation, and focus recommendations from local collection data.
- Use External Listing Connectors when importing local CSV files from multiple offline source formats before sending the normalized listings to Deal Hunter Ranking.
- Use Opportunity Engine when you want a budget-aware answer to "What should I buy next?" using existing collection intelligence and candidate inputs.
- Use Photo-Assisted Entry when starting from front/reverse/reference photo paths and manual candidate details.
- Use Smart Shopping Assistant when comparing multiple opportunities and deciding what to buy next.
- Use Shopping Explainability output when you want to understand why a recommendation was BUY, PASS, WATCH, NEGOTIATE, or REVIEW.
- Use OCR Experiment when you want advisory text extraction from a photo; manually verify every suggestion before using it.
- Use Do I Own This? when manually checking a candidate coin or banknote without listing context.
- Use Buy Advisor when you already know the candidate details and want the legacy buy report format with pricing, priority, liquidity, and collection-intelligence factors.
- Use Collection Dashboard when you want the fastest overview of collection size, strengths, gaps, upgrade opportunities, WANT_LIST priorities, and next focus areas.
- Use Collection Quality Engine outputs inside Collection Dashboard when you want explainable quality scores, strengths, weaknesses, and ranked improvement actions.
- Use acquisition impact output from Listing Analyzer when you need to know how much a candidate improves the collection, not just whether it is buyable.
- Use Series Tracker output when you want to know which supported series are closest to completion and which dates matter next.
- Use Photo Vault output when you want to link and search photo metadata for collection items, candidates, references, auction wins, and sold items.
- Use Photo Vault Audit when you want to check whether photo metadata is trustworthy and which references need cleanup.
- Use Market Awareness output when you want to track what you observed, paid, sold, or bid locally without relying on live pricing.
- Use Want List Generator when planning what to look for next, not when evaluating one specific listing.
- Use Collection Gap Report when reviewing missing dates and completion percentages by country and denomination.
- Use Mobile Readiness Report output when planning future mobile architecture; it is an audit artifact, not a mobile app.
- Use Mobile Companion Prototype output when simulating a quick dealer-table candidate decision from minimal input.
- Use Acquisition Workflow when you want Photo -> OCR -> Validation -> Recommendation -> Review in one guided flow.
- Use Collection Review Workflow when you want Dashboard -> Quality -> Integrity -> Snapshot -> Actions in one guided flow.
- Use Daily Collector Summary when you want a concise "what should I do today?" list from current workflow state.

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

Official v5.4-to-v7.0 roadmap:

- `v5.4` Collector Workflow Integration
- `v6.0` Collector Cloud Foundation
- `v6.1` Sync & Backup
- `v6.2` Multi-Device Collector Workspace
- `v6.3` Device Linking & Conflict Resolution
- `v7.0` Collector Platform

`v2.3` is not a mobile app. It is a readiness and architecture milestone focused on desktop dependency audit, service layer boundary review, mobile-friendly input workflows, API readiness mapping, and phone workflow audit.

v5.4 roadmap rationale: The v5.x series introduced Mobile Collector Companion, Phone Photo Capture, OCR-Assisted Identification, and Mobile Collection Entry. Before introducing cloud architecture, these capabilities should be unified into a complete collector workflow.

Post-v3.8 roadmap rationale: the platform can now evaluate, rank, explain, and calibrate opportunities. The next objective is understanding portfolio progress and collection development over time before live deal hunting begins.

v4.0 roadmap rationale: v3.x established Collection Intelligence, Deal Hunter, Opportunity Engine, Ranking Engine, Listing Connectors, Calibration, Live Readiness, Market Intelligence, and Portfolio Performance. v4.0 introduces controlled, user-triggered live opportunity discovery while preserving no-purchase, no-bidding, no-background-job, and no-collection-mutation safety rules.

v4.1 roadmap rationale: v4.0 introduced live opportunity discovery. v4.1 focuses on trust, validation, reliability, and source quality before live listings enter Deal Hunter, Opportunity Engine, Ranking Engine, or Market Intelligence.

v4.2 roadmap rationale: v4.0 introduced live opportunity discovery and v4.1 hardened live source validation. v4.2 automates the connection between live/imported candidates and local Market Intelligence so collectors can understand deal quality faster and with greater consistency.

Near-term maintenance candidates:

- Improve Buy Advisor validation messages.
- Add GUI autocomplete for country and denomination entry.
- Consider storage/file-picker/photo URI adapters before mobile implementation.
- Consider a compact dealer-table candidate workflow after mobile storage abstractions exist.
- Decide whether Acquisition Workflow guidance should become more visible in Buy Advisor reports.
- Expand normalization fixtures for country, denomination, and variety edge cases.
- Expand offline calibration fixtures before any live-source ingestion work.

Future candidates:

- Build Auction Evaluator from `AUCTION_EVALUATOR_SPEC.md`.
- Add image preview in the collection list.
- Add batch editing, undo/redo, and backup/restore workflows.
- Evaluate SQLite storage for larger collections.

## Known Limitations

- Acquisition price guidance is deterministic internal guidance, not live market pricing.
- Portfolio Performance is collection-development reporting, not investment advice, market forecasting, or live valuation.
- Listing Analyzer stores URLs as reference data only; it does not scrape, fetch, or enrich listings.
- Deal Hunter stores listing URLs and image URLs as reference data only. It does not scrape, fetch, use browser automation, call eBay APIs, or claim live market-pricing accuracy.
- Live Deal Hunter is a controlled beta. It only fetches a user-specified public RSS/XML feed after an explicit button press; it does not bid, buy, mutate collection data, poll in the background, scrape pages, log into services, or guarantee feed availability.
- Live Source Validation does not repair listings, convert currencies, fetch exchange rates, or guarantee source truth. It aggressively flags uncertainty and prefers REVIEW over false confidence.
- Market Intelligence Automation reuses local Market Intelligence only. It does not create a second valuation engine, retrieve live prices, convert currencies, forecast markets, provide investment advice, purchase, bid, or mutate collection data.
- Watchlists & Alerts are report-driven and user-triggered only. They do not send push, email, or SMS notifications, poll sources in the background, schedule jobs, purchase, bid, fetch live pricing, or mutate collection data.
- Field Test & Tuning uses deterministic local fixtures only. It does not add live sources, scrape, automate browsers, call APIs, purchase, mutate collection data, send notifications, or sync to cloud services.
- Mobile Collector Companion is a desktop/local workflow layer, not an Android app, iOS app, web app, cloud sync system, phone-camera integration, OCR identification workflow, purchasing tool, or collection-mutation workflow.
- Market Intelligence estimates are deterministic local guidance from supplied comparable sales, local Market Awareness records, and existing internal deal guidance. They are not appraisals, live market pricing, or guarantees of value.
- Experimental image/OCR modules exist in the repository but remain suggestion-only and manual-verification-only.
- Shared Session Context can save and restore metadata through the Persistence Layer, but workbook-backed context still requires the referenced workbook to remain available.
- Backup packages are local zip files; they are not cloud sync, remote backup, or disaster recovery by themselves.
- Mobile Readiness is documentation and architecture scoring only; no mobile UI or API server exists yet.
- Mobile Companion Prototype is still local desktop workflow logic, not a mobile app or web app.
- Future mobile work requires storage-provider, file-picker, export-destination, and photo URI abstractions.
- Photo-Assisted Entry stores photo paths and metadata only. It does not copy, move, inspect, OCR, classify, or grade images.
- Photo Vault Audit is metadata-only. It does not inspect image contents, repair files, delete records, or move photos.
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

## Persistence Layer

Use these Tools menu items to preserve local app state between sessions:

- Save Session State
- Load Session State
- Clear Session State
- Export Session State
- Import Session State

Default storage:

- `collection_data/app_state/app_state.json`
- `collection_data/app_state/backups/`

Persisted data:

- Shared Session Context metadata
- Last-used collection workbook path
- Last-used WANT_LIST path/source
- Market Awareness records
- Photo Vault records
- Smart Shopping candidates
- Recent Deal Hunter listings and reports
- Basic app preferences/settings
- Warnings and errors useful for restore diagnostics

Backup behavior:

- Saving over an existing state file creates a timestamped backup first.
- Clearing saved state also creates a backup before removing the active state file.
- Export and import use JSON and validate the schema before accepting imported state.

What does not persist:

- Credentials, cloud sync, user accounts, web sessions, live market data, or scraped listing content.
- The collection workbook itself; the state stores paths and reloads context when the referenced workbook still exists.
- Production collection ownership data beyond the existing `data/collection.json` system.

If a referenced workbook is missing, the app reports a warning and allows manual reload.

## Data Safety and Backup Hardening

Use these Tools menu items to validate and protect local app data:

- Data Safety Check
- Collection Recovery Report
- Create Backup Package
- List Backups
- Restore Backup

Backup packages are local `.zip` files stored by default under:

- `backups/packages/`

Backup package contents can include:

- `data/collection.json`
- Persisted collection workbook copy under `collection_workbook/`
- App state JSON
- Market Awareness records inside app state
- Photo Vault records inside app state
- Smart Shopping candidates inside app state
- Release history and release notes
- Backup manifest JSON
- Backup manifest Markdown

Backup manifests explicitly report:

- `collection_json_backed_up`: YES or NO
- `workbook_backed_up`: YES or NO
- `app_state_backed_up`: YES or NO
- Missing files and warnings

Restore behavior:

- Backup packages are verified before restore.
- Restore creates a pre-restore backup first.
- Restore only writes known safe app-state paths and `data/collection.json` by default.
- Existing files are not silently overwritten.
- Collection workbooks are not modified automatically.

Data Safety Check validates:

- `data/collection.json` exists.
- The latest verified backup includes `data/collection.json`.
- App state JSON exists and is readable.
- App state JSON schema is valid.
- Referenced collection workbook and WANT_LIST paths exist when present.
- Persisted workbook backup coverage when a workbook path is available.
- Market, photo, and shopping records can load.
- Referenced photo paths exist.
- Backup directory exists.

Collection Recovery Report shows:

- Whether `data/collection.json`, the persisted workbook, and app state are backed up.
- Which ownership records, workbook copies, app state, market records, photo metadata, and shopping candidates are recoverable.
- Missing files, warnings, and next backup actions.

Collector Export Bundle:

- Collection Health Report
- Shopping recommendations
- Market Awareness summary
- Series summary
- Photo coverage summary
- Backup manifest

Known limitations:

- Local backup packages do not replace off-machine backups.
- Collection workbook copying depends on a saved persisted workbook path; keep workbook backups separately too.
- No cloud sync, user accounts, live pricing, scraping, OCR, image recognition, or database server.

## Collection Integrity Audit

Use Tools -> Collection Integrity Audit when you want to answer:

- Can I trust my collection data?
- Are there duplicate ownership records?
- Are dates, grades, countries, denominations, or years missing or invalid?
- Are photo, market, certification, shopping, persistence, or backup references broken?

The audit is read-only. It does not edit, delete, merge, normalize, or import records.

Report output includes:

- Integrity Score
- Category scores for ownership data, photos, market records, certifications, persistence, and backups
- Findings
- Warnings
- Recommendations
- Photo Integrity Summary
- Market Integrity Summary
- Certification Integrity Summary
- Backup readiness status

Export support:

- Markdown
- CSV

Known limitations:

- Duplicate detection is probable and should be reviewed manually.
- Certification checks depend on available metadata fields.
- Photo and market reference checks can only validate local paths and IDs already stored in app state.
- The audit does not repair data automatically.

## Collection Snapshot System

Use these Tools menu items to measure collection evolution:

- Create Snapshot
- Snapshot Report

Snapshots are stored locally at:

- `collection_data/app_state/collection_snapshots.json`

Stored metrics include:

- Snapshot timestamp
- Collection size
- Quality score
- Integrity score
- Photo coverage percentage
- Supported-series completion metrics
- Market record count
- Shopping candidate count

Snapshot Report shows:

- Current snapshot
- Previous snapshot
- Growth since previous snapshot
- Growth since first snapshot
- Quality score delta
- Integrity score delta
- Photo coverage delta
- Supported-series completion deltas
- Newly completed supported series when detected

Export support:

- Markdown
- CSV

Backup behavior:

- Backup packages include `collection_data/app_state/collection_snapshots.json` when snapshots exist.

Known limitations:

- Snapshots compare stored local metrics only; they do not forecast trends.
- Series progress is limited to supported `SeriesTracker` definitions.
- Snapshot reports do not modify collection records.

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

## Deal Hunter

Use Workflows -> Deal Hunter to evaluate eBay.ca-style listing rows from manual entry or CSV import.

Supported CSV columns:

- `title`
- `price_cad`
- `shipping_cad`
- `seller`
- `source`
- `listing_url`
- `end_time`
- `image_url`
- `description`

Deal Hunter parses titles and descriptions for country, year, denomination, series/type, grade, slab company, grade words, and keywords such as silver, proof-like, specimen, large bust, near 6, wide 9, banknote, chartered banknote, lot listings, and possible problem-coin language.

It reuses existing collection intelligence, acquisition workflow, acquisition impact, smart shopping, WANT_LIST, series, and local market-awareness context. It reports collection status, priority score, liquidity score, collection-fit score, risk score, max rational price, recommendation, counterargument, reasons, warnings, and risk flags such as high shipping, unclear grade, raw overgraded, lot listing, possible damage, unclear currency, non-collection relevant, and needs manual review.

CSV import accepts common column aliases where safe, reports malformed price and skipped-row warnings, and keeps invalid required rows out of the analysis. Exports include parsed fields, total cost, scores, recommendation, risk flags, counterargument, reasons, warnings, and listing URL.

Recommendations:

- BUY
- WATCH
- PASS
- NEGOTIATE
- REVIEW

Scoring is deterministic local guidance only. Max rational price is not live market pricing, appraisal, or a guarantee of value.

Limitations:

- No scraping.
- No browser automation.
- No eBay API credentials.
- No live listing fetches.
- No live market-pricing accuracy claims.
- URLs and image URLs are stored as reference data only.

## Deal Hunter Ranking

Use Tools -> Deal Hunter Ranking when you have a pool of candidate listings and want the best opportunities surfaced before reviewing every row by hand.

Deal Hunter Ranking adds:

- `CandidatePool` for merged manual and CSV listing pools.
- `ImportProfile` for eBay CSV, Auction CSV, Dealer CSV, and Custom CSV mappings.
- Duplicate detection for identical URLs and repeated listing imports.
- Ranking scores from Deal Hunter results, Opportunity Engine results, collection fit, upgrade value, gap value, WANT_LIST relevance, liquidity, risk, and budget fit.
- Budget optimization for $50, $100, $250, and $500 scenarios.
- Category views for top overall, under-budget opportunities, Newfoundland, Canadian silver, banknotes, upgrades, collection gaps, and WANT_LIST targets.
- Markdown and CSV export.

Deal Hunter Ranking is deterministic local guidance only. It does not scrape, fetch URLs, use browser automation, call eBay APIs, retrieve live listings, claim live market pricing accuracy, purchase automatically, or mutate collection data.

## External Listing Connectors

Use Tools -> External Listing Connectors to normalize user-supplied local CSV files from multiple offline source formats before ranking them.

Supported connectors:

- eBay CSV Connector
- Auction CSV Connector
- Dealer Inventory Connector
- Generic CSV Connector

Connector outputs use a common `NormalizedListing` model with:

- title
- description
- price
- shipping
- total cost
- seller
- source
- source type
- URL
- image URL
- import timestamp
- connector name

Connector validation reports:

- required field issues
- malformed prices
- malformed URLs
- missing titles
- unsupported columns
- skipped rows
- import warnings

The connector registry supports single-file imports, multi-file imports, and mixed-source imports into one CandidatePool for Deal Hunter Ranking. DuplicateOpportunityDetector flags identical URLs, same listings, and likely duplicate opportunities across sources for collector review.

External Listing Connectors are local-file adapters only. They do not scrape, use browser automation, call eBay/dealer/auction APIs, fetch live listings, claim live market pricing accuracy, purchase automatically, recognize images, or mutate collection records.

## Deal Hunter Calibration

Use Tools -> Deal Hunter Calibration to run offline calibration cases against Deal Hunter and Deal Hunter Ranking output.

The calibration workflow adds:

- `CalibrationCase` rows with listing data, expected recommendation, expected rank category, expected risk flags, expected rationale, and collector notes.
- `DealHunterCalibrationEngine` for comparing expected collector judgment against actual deterministic Deal Hunter and Ranking results.
- `DealHunterCalibrationReport` with passed/failed cases, false BUYs, false PASSes, false REVIEWs, ranking misses, missing risk flags, over-penalized cases, under-penalized cases, and tuning notes.
- Fixture coverage under `test_data/deal_hunter/calibration_cases.csv` for Newfoundland, Canadian banknote, chartered banknote, upgrade, duplicate, high-shipping, raw-overgraded, damaged, estate-lot, bulk-lot, unclear-currency, and world base-metal scenarios.
- CSV and Markdown export.

Deal Hunter Calibration is offline and deterministic. It does not scrape, use browser automation, call eBay/dealer/auction APIs, retrieve live listings, claim live market pricing accuracy, purchase automatically, recognize images, or mutate collection records.

## Live Deal Hunter Readiness

Use Tools -> Live Deal Hunter Readiness to audit whether the offline Deal Hunter stack is prepared for future live-source ingestion.

The readiness layer adds:

- `LiveDealHunterReadinessAudit` for connector, ranking, calibration, duplicate detection, validation, rate-limit, failure-handling, and no-mutation readiness checks.
- `LiveListingSource`, `LiveListingBatch`, and `LiveListingFetchResult` contract models for future live sources.
- `LiveSourceValidationReport` for future batch validation, including missing title, missing price, missing shipping, non-CAD currency, malformed URL, missing seller, suspicious metadata, duplicate URL, and stale listing checks.
- Deterministic staleness flags: `FRESH`, `STALE`, and `UNKNOWN`.
- `RateLimitPolicy` and `LiveSourceFailure` planning models.
- CSV and Markdown export.

Live Deal Hunter Readiness performs zero live fetching. The source contract stub raises `NotImplementedError` and exists only to document the future boundary. It does not scrape, use browser automation, call APIs, fetch listings, claim live market-pricing accuracy, purchase automatically, recognize images, or mutate collection records.

## Market Intelligence

Use Tools -> Market Intelligence when you want a value and risk explanation for a single supplied listing before live-source ingestion exists.

Market Intelligence adds:

- `MarketIntelligenceEngine` for deterministic local listing evaluation.
- `FairValueEstimate` with conservative, expected, and aggressive bands.
- `ComparableSale` support from supplied rows and local Market Awareness observations.
- `DealQuality` labels: Excellent, Good, Fair, Weak, Overpriced, or Unknown.
- `OpportunityConfidence` score using collection fit, duplicate risk, upgrade/gap impact, data completeness, valuation evidence, and risk penalties.
- `RiskSummary` with clear warnings for shipping, raw/unclear grade, damage, lots, currency ambiguity, and duplicate risk.
- Collector-facing counterargument and buy rationale.
- CSV and Markdown export.

Market Intelligence reuses Deal Hunter, Opportunity Engine, Deal Hunter Ranking context, Collection Intelligence, WANT_LIST context, and local Market Awareness records. It does not scrape, use browser automation, call APIs, fetch listings, claim live market-pricing accuracy, purchase automatically, recognize images, or mutate collection data.

## Portfolio Performance

Use Tools -> Portfolio Performance when you want a portfolio-level view of how the collection is developing over time.

Portfolio Performance adds:

- `PortfolioPerformanceEngine` for local portfolio-level reporting.
- `CollectionGrowthReport` for collection size, local estimated value, silver holdings, slab count, banknote count, Newfoundland count, category counts, and snapshot comparison.
- `AcquisitionPerformanceReport` for best acquisitions, biggest upgrades, highest collection impact, strongest opportunity captures, and highest-confidence purchases from local records.
- `SeriesProgressReport` for completion percentages, nearest completions, neglected series, strongest-performing series, and snapshot deltas.
- `BudgetAllocationReport` for Newfoundland, Canadian silver, banknotes, slabs, upgrades, duplicates, and other categories.
- `CollectionHealthScore` for backup readiness, integrity, photo coverage, documentation/certification coverage, duplicate control, WANT_LIST alignment, snapshot coverage, and series progress.
- `PortfolioPerformanceReport` executive dashboard with strengths, weaknesses, opportunities, risks, recommended focus areas, and CSV/Markdown export.

Portfolio Performance reuses the Collection Snapshot System, Collection Intelligence, Opportunity Engine, Market Intelligence context, Series Tracker, Collection Quality, Collection Integrity, Market Awareness, and local collection records. It does not scrape, call APIs, forecast markets, provide investment advice, purchase automatically, or mutate collection data.

## Watchlists & Alerts

Use Tools -> Watchlists & Alerts when you want to define what the collector is actively seeking and scan existing candidate outputs for matching opportunities.

Watchlists & Alerts adds:

- `WatchlistEngine` for report-driven matching against existing deal, ranking, live, connector, and market-enriched candidate outputs.
- Editable watch types for series watches, specific coin watches, keyword watches, and custom watches.
- `WatchPriority` levels: `CRITICAL`, `HIGH`, `NORMAL`, and `LOW`.
- Adam starter presets for Newfoundland Coins, Newfoundland Silver, Canadian Silver, Canadian Banknotes, 1859 Large Cent Varieties, 1926 Near 6 Nickel, and 1973 Large Bust Quarter.
- `AlertEngine` for on-demand watchlist match, upgrade opportunity, collection gap opportunity, high-priority opportunity, and rare target opportunity alerts.
- `AlertScore` from watch priority, collection relevance, opportunity score, market intelligence confidence, and upgrade/rare-target relevance.
- CSV and Markdown export through `WatchlistReport` and `AlertReport`.

Known limitations:

- Alerts are generated only when the user runs a scan.
- No push notifications, email, SMS, background polling, scheduled jobs, automatic purchasing, bidding, live pricing, or collection mutation.
- Watchlist matching is deterministic text/metadata matching and should be reviewed before buying.

## Field Test & Tuning

Use Tools -> Field Test & Tuning when you want to measure the live opportunity pipeline against deterministic realistic scenarios.

The field-test pipeline is:

Live Source
to Validation
to Deal Hunter
to Ranking
to Market Intelligence
to Watchlists
to Alerts

Field Test & Tuning adds:

- `FieldTestScenario`, `FieldTestResult`, `FieldTestReport`, and `ScenarioRunner`.
- Deterministic sample scenarios for Newfoundland upgrades and duplicates, 1859 variety candidates, 1926 Near 6, Canadian silver lots, banknotes, high shipping traps, non-CAD listings, weak titles, duplicate URLs, false-positive watchlist matches, and strong watchlist matches.
- `OpportunityQualityReport` for BUY/REVIEW/PASS/WATCH/NEGOTIATE counts, escalation frequency, and confidence distribution.
- `PipelineHealthReport` for listings processed, validation failures, duplicates, watchlist matches, alerts, review escalations, accepted listings, and rejected listings.
- `FalsePositiveAudit` for duplicate misclassification risk, weak watchlist matches, weak keyword matches, weak upgrade signals, and noisy low-score alerts.
- CSV and Markdown export.

Known limitations:

- No live network dependency and no live source fetching.
- No automatic tuning changes are applied from audit findings.
- Findings are review recommendations only.
- No scraping, browser automation, API integrations, automatic purchasing, collection mutation, push notifications, or cloud sync.

## Mobile Collector Companion

Use Tools -> Mobile Collector Companion when you want a phone-like collector workflow while still working inside the desktop app.

Supported mobile-oriented workflows:

- Coin Show Workflow
- Dealer Visit Workflow
- Antique Market Workflow
- Coin Shop Workflow
- Auction Preview Workflow

Mobile Collector Companion adds:

- `MobileCollectorCompanion` as the orchestration layer.
- `MobileSession` and `MobileWorkflow` for phone-like field sessions.
- `QuickDecisionSummary` for concise BUY/WATCH/PASS/REVIEW guidance, confidence, top reasons, key risks, watchlist matches, collection relevance, and market summary.
- `MobileCollectionContext` for watchlist summary, active targets, collection priorities, recent opportunities, and portfolio highlights.
- `MobileDashboard` for active watchlists, high-priority targets, recent alerts, recent opportunities, collection priorities, and quick decisions.
- `FieldWorkMode` for short-form summaries optimized for on-the-go review.
- `MobileCompanionReport` with CSV and Markdown export.

The companion reuses Deal Hunter Ranking, Market Intelligence Automation, Watchlists, Alerts, Portfolio Performance, and Field Test Framework outputs. It does not create a second recommendation engine.

Known limitations:

- Desktop/local workflow simulation only.
- No Android app, iOS app, web app, cloud sync, phone-camera integration, OCR identification, live fetching, purchasing, or collection mutation.
- Quick decisions are compact summaries of existing deterministic engines and should be manually reviewed before spending money.

## Phone Photo Capture

Use Tools -> Phone Photo Capture when you want to organize photos captured in the field before later OCR or manual identification work.

Phone Photo Capture adds:

- `PhotoCaptureWorkflow`, `CapturedPhoto`, `PhotoCaptureSession`, and `PhotoCaptureReport`.
- Single photo capture records with timestamp, source type, photo role, workflow status, review status, and notes.
- Coin front/back and banknote front/back sessions with missing-side checks.
- Optional listing-photo sessions for auction/dealer/listing intake.
- OCR-ready and review-ready status summaries.
- Photo Vault record conversion and OCR source adapters.
- Mobile Collector Companion photo capture summary integration.
- CSV and Markdown export.

Known limitations:

- Metadata-only photo intake.
- No image recognition, attribution, grading, OCR identification, cloud sync, automatic collection entry, purchasing, or collection mutation.

## OCR-Assisted Identification

Use Tools -> OCR-Assisted Identification when you want to turn a captured photo or pasted OCR text into a reviewable identification candidate.

OCR-Assisted Identification adds:

- `OCRIdentificationEngine`, `OCRIdentificationCandidate`, `OCRIdentificationReport`, and `IdentificationEvidence`.
- CapturedPhoto -> OCR Extraction -> OCR Validation -> Identification Candidate -> Review Report.
- Candidate fields for year, denomination, country, monarch, banknote prefix, certification number, series/type, silver indicator, and possible variety keywords.
- Evidence for OCR text used, validation score, trust level, supporting keywords, conflicts detected, and missing evidence.
- HIGH/MEDIUM/LOW confidence classification with explicit reasoning.
- Collection, WANT_LIST, and watchlist context that can surface already-owned, possible-upgrade, collection-gap, watchlist-match, and needs-review signals.
- Mobile Collector Companion identification summary integration.
- CSV and Markdown export.

Known limitations:

- OCR remains advisory only.
- Manual review is mandatory.
- No computer vision attribution, AI grading, automatic collection entry, automatic ownership decisions, automatic purchases, or collection mutation.

## Opportunity Engine

Use Workflows -> Opportunity Engine to identify the highest-impact collection opportunities from current holdings, active WANT_LIST context, optional manual candidates, and Deal Hunter results.

Opportunity types:

- Upgrade Opportunity
- Collection Gap Opportunity
- Series Completion Opportunity
- Want List Opportunity
- Newfoundland Opportunity
- Canadian Silver Opportunity
- Canadian Banknote Opportunity
- High-ROI Opportunity

Budget analysis covers $50, $100, $250, and $500 scenarios. Every opportunity includes a deterministic score, reasoning, risks, budget fit, estimated collection impact, and counterargument before any recommendation.

The engine reuses existing Collection Intelligence, Smart Shopping Assistant, Acquisition Impact, Collection Quality, Series Tracker, WANT_LIST, Deal Hunter, and local Market Awareness context. It does not scrape, call APIs, fetch listings, predict markets, mutate collection data, or claim live pricing accuracy.

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
- Deal Hunter: CSV and Markdown export.
- Deal Hunter Ranking: CSV and Markdown export.
- Deal Hunter Calibration: CSV and Markdown export.
- Live Deal Hunter Readiness: CSV and Markdown export.
- Market Intelligence: CSV and Markdown export.
- Portfolio Performance: CSV and Markdown export.
- Watchlists & Alerts: CSV and Markdown export.
- Field Test & Tuning: CSV and Markdown export.
- Mobile Collector Companion: CSV and Markdown export.
- Phone Photo Capture: CSV and Markdown export.
- OCR-Assisted Identification: CSV and Markdown export.
- External Listing Connectors: CSV and Markdown export.
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

## Mobile Readiness

v2.3 documents the path toward future mobile use without building a mobile app. `mobile_readiness.py` generates a structured Mobile Readiness Report with:

- Desktop dependency audit for Tkinter, file dialogs, workbook loading, exports, photo paths, and persistence paths.
- Service boundary review for Collection Intelligence, Listing Analyzer, Smart Shopping Assistant, Collection Dashboard, Collection Health Report, Persistence Layer, and Backup Manager.
- Mobile input readiness for manual candidate entry, pasted listing text, pasted URLs, photo references, and persisted context.
- Documentation-only future endpoint mapping for `analyze_candidate`, `collection_health`, `shopping_recommendations`, and `dashboard_summary`.
- Dealer-table phone workflow audit for reaching BUY/PASS guidance from a candidate coin and asking price.
- Mobile Readiness Score across architecture, workflow, persistence, exports, and inputs.
- CSV and Markdown export.

Current mobile blockers:

- Tkinter is desktop-only.
- File dialogs and local filesystem paths are embedded in GUI workflows.
- Photo Vault uses local paths rather than portable photo URIs.
- No API server, mobile storage adapter, or mobile UI exists yet.

Future mobile work should start with storage-provider, file-picker, export-destination, and photo URI abstractions before any mobile interface is attempted.

## Mobile Companion Prototype

v2.4 proves a mobile-style collector workflow without building a mobile app. The workflow is intentionally simple:

Candidate
Analyze
Recommendation

`mobile_companion.py` provides:

- `MobileCandidateEntry` for minimal dealer-table input: item title, asking price, shipping, notes, URL, photo reference ID, and source.
- `MobileCompanionWorkflow` for a single local recommendation path that reuses Listing Analyzer, Acquisition Workflow, Acquisition Impact, Smart Shopping Assistant, Photo Vault metadata, and Persistence Manager.
- `MobileAnalysisReport` with recommendation, impact score, quality delta, series delta, WANT_LIST status, top reason, concise summary, warnings, and max rational price.
- `PhoneWorkflowSimulation` for deterministic coin-shop workflow checks.
- Desktop provider abstractions for storage, photo metadata lookup, and local CSV/Markdown export.

Mobile Companion is not a native mobile app, web app, API server, OCR workflow, image recognition workflow, scraper, live pricing system, cloud sync layer, or new database.

## Photo-Assisted Entry

v2.5 reduces candidate-entry friction by letting the collector attach photo references before manual review. It is evidence management, not image interpretation.

Workflow:

Photo
Candidate Entry
Manual Review
Collection Intelligence
Recommendation

`photo_assisted_entry.py` provides:

- `PhotoCandidate` for title, front photo, reverse photo, reference photo paths, notes, asking price, source, timestamp, and workflow state.
- `PhotoAssistedEntry` for creating candidates, linking photo paths through Photo Vault metadata, and routing the candidate through Mobile Companion and the existing acquisition engines.
- `PhotoReviewReport` for attached photos, candidate details, recommendation context, warnings, and CSV/Markdown export.

Photo-Assisted Entry integrates with:

- Photo Vault for metadata-only candidate/reference photo links.
- Mobile Companion for concise BUY/PASS/WATCH/NEGOTIATE/REVIEW guidance.
- Persistence Layer for saved photo candidate metadata.
- Backup packages through app-state metadata only.

Limitations:

- Photos are not moved, copied, read, OCRed, classified, or graded.
- Missing photo paths are reported as warnings.
- Backup packages preserve photo candidate metadata, not arbitrary photo folders.

## Photo Vault Audit

v2.5.1 adds a read-only Photo Vault integrity audit. It answers whether photo records are useful, findable, valid, and safely reportable.

Audit checks:

- Missing photo files
- Invalid or unsupported photo paths
- Duplicate photo references
- Unlinked photo metadata
- Collection items without photos
- Candidate records without photos
- Certified/slabbed items without photos
- Invalid image extensions

Coverage metrics:

- Total photo records
- Valid photo references
- Missing photo references
- Duplicate photo references
- Collection photo coverage percentage
- Certified-item photo coverage percentage
- Candidate photo coverage percentage

Backup behavior:

- Backup packages preserve photo metadata in app state.
- Photo files themselves are not copied automatically.
- Keep `coin_photos/` folders in regular external backups.

Exports:

- Markdown
- CSV

## Shopping Explainability

v2.5.2 explains existing recommendations without changing them.

`shopping_explainability.py` provides:

- `RecommendationConfidence` with deterministic High, Medium, and Low labels.
- `RecommendationExplanation` with primary reasons, supporting reasons, impact summary, warnings, and collector notes.
- `ExplainableRecommendationReport` with Markdown and CSV export.
- `ShoppingExplanationEngine` for Smart Shopping recommendations, Listing Analyzer results, and Acquisition Workflow decisions.

Explanation examples:

- BUY: explicit WANT_LIST target, collection gap, positive acquisition impact, acceptable asking price.
- PASS: same-grade duplicate, lower-grade duplicate, no meaningful collection impact, poor asking price.
- WATCH: interesting target, missing price, price above max rational price, needs more information.
- NEGOTIATE: relevant target but asking price is above max rational price.
- REVIEW: low confidence, ambiguous classification, attribution or certification needs manual review.

Limitations:

- Explainability does not create a new recommendation engine.
- It does not change recommendation outcomes, thresholds, prices, or rankings.
- Confidence is deterministic rule output, not AI confidence.

## OCR Experiments

v2.6 adds an advisory OCR experiment workflow for collector-supplied image paths.

`ocr_experiment.py` provides:

- `OCRResult` for raw OCR text, source image path, engine metadata, timestamp, and warnings.
- `OCRConfidence` for deterministic High, Medium, and Low confidence labels.
- `OCRSuggestionReport` for possible years, denominations, countries, note prefixes, certification numbers, warnings, manual-review status, and CSV/Markdown export.
- `OCRExperiment` for optional local OCR execution or deterministic raw-text suggestion extraction in tests and manual workflows.

Tools -> OCR Experiment can:

- Select an image path.
- Accept pasted OCR text for review or deterministic testing.
- Display raw OCR output, extracted suggestions, confidence, and warnings.
- Export the suggestion report to Markdown or CSV.

Guardrails:

- OCR output is advisory only.
- Manual review is always required.
- OCR never creates or edits collection records.
- OCR never updates ownership, grades, recommendations, shopping rankings, or purchase decisions.
- OCR does not scrape, call pricing APIs, identify coins by image, or grade images.

Persistence:

- OCR results and reports can be stored in local app state through the existing Persistence Layer.
- App-state backups preserve OCR metadata, not arbitrary photo folders.

Known limitations:

- Local OCR depends on the user's installed OCR runtime. If unavailable, the workflow reports a warning and continues safely.
- Suggestion extraction is deterministic text parsing, not proof of attribution.
- Ambiguous or incomplete OCR text requires manual verification.

## OCR Validation Layer

v2.6.1 answers whether an OCR result is trustworthy enough to use after manual review.

`ocr_validation.py` provides:

- `OCRValidationEngine` for deterministic OCR quality checks.
- `OCRValidationReport` for trust level, validation score, findings, warnings, explanations, and review recommendations.
- `OCRTrustLevel` values: HIGH, MEDIUM, and LOW.
- `OCRValidationScore` with strengths, weaknesses, and recommended actions.
- `OCRValidationExplanation` explaining why the trust level was assigned.

Validation checks include:

- Year format, plausible ranges, conflicts, and ambiguous year readings.
- Denomination conflicts and ambiguous denomination readings.
- Country recognition quality, missing countries, conflicting countries, and incomplete country text.
- Certification-number format consistency and malformed or incomplete values.
- Overall OCR quality, incomplete text, low confidence, and OCR-source warnings.

Tools -> OCR Experiment now displays:

- Raw OCR suggestion report.
- Trust level.
- Validation score.
- Validation findings.
- Warnings.
- Explanation.
- Manual-review recommendations.

Exports:

- Markdown validation report.
- CSV validation report.

Limitations:

- Validation does not make OCR authoritative.
- Validation does not update collection records, ownership, grades, recommendations, shopping rankings, or acquisition decisions.
- LOW trust and MEDIUM trust results still require collector review before use.

## Workflow Integration

v2.7 turns existing modules into guided collector workflows.

`collector_workflows.py` provides:

- `CollectorWorkflowEngine` as a facade for guided workflows.
- `AcquisitionWorkflow` for Photo -> Photo-Assisted Entry -> OCR Experiment -> OCR Validation -> Smart Shopping -> Shopping Explainability -> Save Candidate review.
- `CollectionReviewWorkflow` for Collection Dashboard -> Collection Quality -> Collection Integrity -> Snapshot Review -> Recommended Actions.
- `PhotoReviewWorkflow` for Photo Vault -> Photo Vault Audit -> Coverage Review -> Missing Photo Actions.
- `CollectorDailySummary` for a daily "what should I do today?" task list.
- `WorkflowStatus` and `WorkflowSummary` for lightweight status tracking and persistence.

Tools menu entries:

- Tools -> Acquisition Workflow
- Tools -> Collection Review Workflow
- Tools -> Daily Collector Summary

Exports:

- Markdown workflow summaries.
- CSV workflow summaries where practical.

Persistence:

- Workflow statuses and workflow summaries are stored in local app state.
- No background jobs are created.

Limitations:

- Workflow Integration orchestrates existing systems only.
- It does not add new recommendation logic.
- It does not change OCR, validation, shopping, dashboard, integrity, snapshot, or photo-audit outcomes.
- It does not scrape, call APIs, grade images, or modify collection records automatically.

## Collector Home Dashboard

Use Tools -> Collector Home Dashboard when you want one daily command center for the collection.

The home dashboard answers:

- What needs attention today?
- What is safe?
- What should be reviewed?
- What acquisition opportunity matters most?
- What progress has been made?

Status cards:

- Collection Health: reuses Collection Quality and Collection Integrity.
- Acquisition Focus: reuses Smart Shopping Assistant, Shopping Explainability, and Acquisition Impact outputs.
- Review Queue: reuses OCR Validation, Photo Vault Audit, and workflow status.
- Data Safety: reuses BackupManager, DataSafetyValidator, and Persistence checks.
- Progress: reuses Snapshot System, Series Tracker, and Photo Vault coverage.

Daily actions are ranked by deterministic severity and urgency. Examples include backing up collection data, fixing integrity issues, reviewing OCR items, adding missing photos, reviewing top shopping opportunities, and creating snapshots.

Exports:

- Markdown home report.
- CSV home report.

Persistence:

- The last generated home reports and acknowledged action IDs can be stored in local app state.

Limitations:

- Collector Home Dashboard is a workflow-surfacing layer, not a new recommendation engine.
- It does not mutate collection data, run OCR, scrape prices, call APIs, grade images, or create background jobs.

## Collector Companion Readiness

Use Tools -> Collector Companion Readiness when validating the Collector Companion product status.

The readiness report includes:

- V3.0 readiness checklist.
- Export consistency audit.
- Report consistency audit.
- End-to-end workflow audit.
- Collector Companion Status: READY or NEEDS_WORK across collection management, acquisition, OCR, integrity, backup, and dashboard workflows.
- Findings and remaining friction points.

The checklist covers backups, persistence, integrity, snapshots, photo workflow, OCR workflow, explainability, Collector Home Dashboard, Series Tracker, exports, and documentation.

Exports:

- Markdown readiness report.
- CSV readiness report.

Limitations:

- Readiness is an audit/reporting layer only.
- It does not change recommendations, update collection data, run OCR, scrape, call APIs, or create background jobs.

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
