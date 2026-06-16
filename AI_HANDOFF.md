# AI Handoff

## Snapshot

- Date: 2026-06-16
- Branch: `main`
- Current project state file reports release version: `v0.7`
- Current active task completed: advisor decision-source consolidation on the focused Collection Intelligence Engine

## What Changed

- Added `focused_collection_intelligence.py` with reusable deterministic candidate classification.
- Added Tools -> Do I Own This in `coin_collection_gui.py`.
- Added `test_focused_collection_intelligence.py` with focused unit coverage.
- Refactored `buy_advisor.py` duplicate/upgrade flags to use `FocusedCollectionIntelligenceEngine`.
- Refactored `upgrade_advisor.py` match/upgrade decisions to use `FocusedCollectionIntelligenceEngine`.
- Added regression tests proving both advisors route through the focused engine while preserving existing verdict behavior.
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

- `py -m unittest test_focused_collection_intelligence.py test_upgrade_advisor.py test_buy_advisor_regression.py`: 46 tests OK.
- `.\run_tests.bat`: 184 tests OK.
- Ad-hoc `py -c` GUI smoke failed because the Windows launcher reported no installed Python; the full test runner succeeded.

## Known Limitations

- Fuzzy matching is deterministic and intentionally basic.
- Variety matching depends on existing text fields such as reference, title, notes, and comments.
- The Do I Own This dialog currently analyzes current collection items only; staged WANT_LIST context is supported by the engine but not yet loaded through that dialog.
- Buy Advisor still keeps its legacy collection-intelligence boost scoring separate from duplicate/upgrade classification to preserve current user-visible behavior.
- GUI workflows still have limited automated coverage.

## Recommended Next Steps

1. Run a focused v0.7 acceptance audit for Buy Advisor, Upgrade Advisor, and Do I Own This.
2. Add a safe optional WANT_LIST context loader to the Do I Own This workflow.
3. Expand normalization fixtures for country, denomination, and variety edge cases.
4. Continue reducing older duplicate matching helpers only where regression coverage proves behavior is preserved.
