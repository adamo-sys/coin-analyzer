# Task Queue

Work through this queue in priority order. Handle only one task at a time.

## Status Legend

- `[ ]` Not Started
- `[-]` In Progress
- `[x]` Complete
- `[!]` Blocked

## Working Rules

1. Work on only one task at a time.
2. After each task, run tests if possible.
3. Summarize changed files after each task.
4. Stop for approval before continuing to the next task.
5. Do not add unrelated features while completing a queued task.
6. When a task is blocked, explain why in the queue or changelog.
7. `TASK_QUEUE.md` and `PROJECT_STATE.md` are the source of truth for project status.
8. Whenever a task is completed:
   - Update `PROJECT_STATE.md`.
   - Update `TASK_QUEUE.md`.
   - Run tests if available.
   - Commit changes.
   - Include the commit hash in `PROJECT_STATE.md` Recent Changes.

## Queue

1. `[x]` Harden test infrastructure
2. `[x]` Add `run_tests.bat`
3. `[x]` Add `TESTING.md`
4. `[x]` Add GitHub Actions workflow
5. `[x]` Ensure tests use isolated test data
6. `[x]` Implement Collection Gap Report
7. `[x]` Add Markdown export for gap report
8. `[x]` Implement Want List Generator MVP
9. `[ ]` Improve Buy Advisor validation messages
10. `[ ]` Add autocomplete for country/denomination
11. `[x]` Add Auction Evaluator draft spec
12. `[x]` Add legacy portfolio import spec
13. `[x]` Add portfolio integration roadmap
14. `[ ]` Implement legacy portfolio staging importer
15. `[ ]` Build Melt Value Engine
16. `[ ]` Build Upgrade Advisor
17. `[ ]` Recreate dashboard metrics in app

## Adam-Specific Collection Priorities

Use these priorities when designing gap reports, Buy Advisor changes, acquisition ranking, and evaluator specs.

1. Newfoundland Coinage
   - Date runs
   - Key dates
   - Higher-grade examples
   - 5 cent, 10 cent, 20 cent, and 50 cent focus
2. 1859 Canadian Large Cents
   - Variety attribution
   - Narrow 9 / Wide 9
   - 8 over 9 varieties
   - Date and die variety analysis
   - Upgrade opportunities
3. Canadian Silver Coinage
   - Dimes
   - Quarters
   - Half dollars
   - Dollars
4. Date Run Completion
   - Identify missing years
   - Prioritize easiest completions
   - Calculate completion percentages
5. Upgrade Over Duplicate Strategy
   - Prefer quality upgrades
   - Minimize duplicate purchases
   - Identify replacement candidates
6. Budget-Conscious Acquisitions
   - Maximize value per dollar spent
   - Focus on high-ROI purchases
   - Highlight underpriced opportunities
7. Collection Gap Reduction
   - Generate want lists
   - Rank acquisition targets
   - Recommend highest-impact purchases

## Project Changelog

### 2026-06-15

#### `[x]` Add portfolio integration roadmap

- Date completed: 2026-06-15
- Files modified:
  - `PORTFOLIO_INTEGRATION_ROADMAP.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `b3d17bc`

#### `[x]` Add legacy portfolio import spec

- Date completed: 2026-06-15
- Files modified:
  - `LEGACY_PORTFOLIO_IMPORT_SPEC.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `217c467`

#### `[x]` Implement Collection Gap Report

- Date completed: 2026-06-15
- Files modified:
  - `collection_intelligence.py`
  - `coin_collection_gui.py`
  - `test_collection_intelligence.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `259ad42`

#### `[x]` Add Markdown export for gap report

- Date completed: 2026-06-15
- Files modified:
  - `collection_intelligence.py`
  - `coin_collection_gui.py`
  - `test_collection_intelligence.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `259ad42`

#### `[x]` Implement Want List Generator MVP

- Date completed: 2026-06-15
- Files modified:
  - `collection_intelligence.py`
  - `coin_collection_gui.py`
  - `test_collection_intelligence.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `259ad42`

#### `[x]` Add Auction Evaluator draft spec

- Date completed: 2026-06-15
- Files modified:
  - `AUCTION_EVALUATOR_SPEC.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `259ad42`

#### `[x]` Add Adam-specific collection priorities

- Date completed: 2026-06-15
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `f9014c3`

#### `[x]` Harden test infrastructure

- Date completed: 2026-06-15
- Files modified:
  - `test_accuracy.py`
  - `test_backend.py`
  - `test_buy_advisor_regression.py`
  - `test_collection_analysis.py`
  - `test_csv_import.py`
- Commit hash: `ac1d4e7`

#### `[x]` Add `run_tests.bat`

- Date completed: 2026-06-15
- Files modified:
  - `run_tests.bat`
- Commit hash: `ac1d4e7`

#### `[x]` Add `TESTING.md`

- Date completed: 2026-06-15
- Files modified:
  - `TESTING.md`
- Commit hash: `ac1d4e7`

#### `[x]` Add GitHub Actions workflow

- Date completed: 2026-06-15
- Files modified:
  - `.github/workflows/tests.yml`
- Commit hash: `ac1d4e7`

#### `[x]` Ensure tests use isolated test data

- Date completed: 2026-06-15
- Files modified:
  - `test_data/sample_collection.json`
  - `test_data/sample_import.csv`
  - `test_backend.py`
  - `test_buy_advisor_regression.py`
  - `test_collection_analysis.py`
  - `test_csv_import.py`
- Commit hash: `ac1d4e7`
