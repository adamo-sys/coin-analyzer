# AI Handoff

## Snapshot

- Date: 2026-06-16
- Branch: `main`
- Current project state file reports release version: `v0.8-dev`
- Current active task completed: WANT_LIST context integration for the focused Collection Intelligence Engine and Do I Own This workflow

## What Changed

- Added `focused_collection_intelligence.py` with reusable deterministic candidate classification.
- Added Tools -> Do I Own This in `coin_collection_gui.py`.
- Added `test_focused_collection_intelligence.py` with focused unit coverage.
- Refactored `buy_advisor.py` duplicate/upgrade flags to use `FocusedCollectionIntelligenceEngine`.
- Refactored `upgrade_advisor.py` match/upgrade decisions to use `FocusedCollectionIntelligenceEngine`.
- Added regression tests proving both advisors route through the focused engine while preserving existing verdict behavior.
- Added WANT_LIST context status to focused candidate analysis: `ON_WANT_LIST`, `NOT_ON_WANT_LIST`, `GAP_NOT_EXPLICITLY_TARGETED`, and `WANT_LIST_UNAVAILABLE`.
- Added a lightweight Load WANT_LIST Context button to Tools -> Do I Own This.
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

## Test Status

- `py -m unittest test_focused_collection_intelligence.py`: 17 tests OK.
- `.\run_tests.bat`: 190 tests OK.
- GUI smoke for Do I Own This, Want List Generator, Collection Gap Report, and Portfolio Import Preview passed.
- Direct multi-module `py -m unittest ...` commands may still hit the intermittent Windows launcher issue; use `run_tests.bat` as the project runner.

## Known Limitations

- Fuzzy matching is deterministic and intentionally basic.
- Variety matching depends on existing text fields such as reference, title, notes, and comments.
- The Do I Own This dialog loads staged WANT_LIST context from a selected legacy workbook for the current session only; it does not persist that context.
- Buy Advisor still keeps its legacy collection-intelligence boost scoring separate from duplicate/upgrade classification to preserve current user-visible behavior.
- GUI workflows still have limited automated coverage.

## Recommended Next Steps

1. Run a focused v0.8 acceptance audit for Do I Own This with and without loaded WANT_LIST context.
2. Decide whether session-loaded WANT_LIST context should be shared across Buy Advisor, Want List Generator, and Do I Own This.
3. Expand normalization fixtures for country, denomination, and variety edge cases.
4. Continue reducing older duplicate matching helpers only where regression coverage proves behavior is preserved.
