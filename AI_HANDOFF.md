# AI Handoff

## Snapshot

- Date: 2026-06-16
- Branch: `main`
- Current project state file reports release version: `v1.4`
- Current active task completed: v1.4 Collection Quality Engine

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
- Updated `PROJECT_STATE.md` and `TASK_QUEUE.md` as source-of-truth files.

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
- Keep Buy Advisor, Upgrade Advisor, Want List Generator, Collection Gap Report, and import previews stable unless the active task explicitly targets them.
- Every completed version must end with implementation, acceptance audit, tag creation, and push verification.
- A version is not complete until its release tag exists locally and remotely and both tag targets are verified.
- Never leave a completed version untagged.

## Test Status

- `.\run_tests.bat`: 251 tests OK for the v1.4 quality engine release line.
- GUI smoke for Do I Own This, Buy Advisor, Upgrade Advisor, Want List Generator, Collection Gap Report, and Portfolio Import Preview passed.
- Export smoke for collection CSV, gap CSV, want-list CSV/Markdown, portfolio preview CSV, and WANT_LIST preview CSV passed.
- Tag metadata verified through `v1.2`; `v1.2` points to `db001da4187af5a2bd2350bd956b2876007f7587`.
- Local GUI smoke for v1.1 could not run because this Python/Tcl install cannot find `init.tcl`.
- Local GUI smoke for v1.3 also could not run because this Python/Tcl install cannot find `init.tcl`; dashboard and GUI module imports passed.
- Local GUI smoke for v1.4 also could not run because this Python/Tcl install cannot find `init.tcl`; quality/dashboard/GUI module imports passed.
- Direct multi-module `py -m unittest ...` commands may still hit the intermittent Windows launcher issue; use `run_tests.bat` as the project runner.

## Known Limitations

- Fuzzy matching is deterministic and intentionally basic.
- Variety matching depends on existing text fields such as reference, title, notes, and comments.
- Shared Session Context is per app session only; it does not persist loaded workbook or WANT_LIST state after closing the app.
- Buy Advisor still keeps its legacy collection-intelligence boost scoring separate from duplicate/upgrade classification to preserve current user-visible behavior.
- Acquisition workflow max rational price is rule-based internal guidance only; it is not market pricing.
- Listing Analyzer parsing is intentionally basic and requires manual review for ambiguous listing titles.
- Listing URLs are stored as reference data only; no website fetches, scraping, enrichment, or market-price lookups occur.
- Collection Dashboard does not estimate unknown values and depends on available collection fields for certified counts and collection evolution.
- Collection Quality Engine uses deterministic internal scoring only; it does not use rarity guides, market pricing, population reports, OCR, scraping, or Numista expansion.
- GUI workflows still have limited automated coverage.

## Recommended Next Steps

1. Begin v1.5 Smarter Acquisition Intelligence planning.
2. Improve Buy Advisor validation messages.
3. Add GUI autocomplete for country and denomination.
4. Decide whether Listing Analyzer should eventually export its result.
5. Expand normalization fixtures for listing-title parsing edge cases.
