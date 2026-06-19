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
9. Every completed version must end with implementation, acceptance audit, tag creation, and push verification.
10. A version is not complete until its release tag exists locally and remotely and both tag targets are verified.
11. Never leave a completed version untagged.

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
14. `[x]` Implement legacy portfolio staging importer
15. `[x]` Add Portfolio Import Preview GUI
16. `[x]` Build Melt Value Engine
17. `[x]` Build Upgrade Advisor
18. `[x]` Recreate dashboard metrics in app
19. `[x]` Refine Collection Gap Report MVP CSV export
20. `[x]` Perform v0.3 release audit
21. `[x]` Finalize v0.3 release and plan WANT_LIST integration
22. `[x]` Implement legacy WANT_LIST staging integration
23. `[x]` Add WANT_LIST Preview GUI
24. `[x]` Connect staged WANT_LIST intent to Want List Generator
25. `[x]` Connect staged WANT_LIST intent to Buy Advisor
26. `[x]` Perform v0.4 integration audit
27. `[x]` Fix low-priority world base metal Buy Advisor guardrail
28. `[x]` Perform v0.6 release audit
29. `[x]` Perform complete v0.5 release audit rerun
30. `[x]` Build focused Collection Intelligence Engine
31. `[x]` Consolidate advisor decisions on Collection Intelligence Engine
32. `[x]` Integrate WANT_LIST context into Collection Intelligence Engine and Do I Own This
33. `[x]` Build Acquisition Workflow on Collection Intelligence Engine
34. `[x]` Perform v1.0 release-readiness audit
35. `[x]` Complete post-v1.0 release packaging documentation
36. `[x]` Build Shared Session Context
37. `[x]` Build Listing Analyzer
38. `[x]` Perform v1.2 post-release usability documentation audit
39. `[x]` Build v1.3 Collection Dashboard release line
40. `[x]` Build v1.4 Collection Quality Engine
41. `[x]` Build v1.5 Smarter Acquisition Intelligence
42. `[x]` Build v1.6 Series Tracker
43. `[x]` Build v1.7 Photo Vault
44. `[x]` Build v1.8 Market Awareness Layer
45. `[ ]` Improve Buy Advisor validation messages
46. `[ ]` Add autocomplete for country/denomination
47. `[x]` Build v1.9 Smart Shopping Assistant
48. `[x]` Build v2.0 Collector Operating System
49. `[x]` Build v2.1 Persistence Layer
50. `[x]` Build v2.2 Data Safety and Backup Hardening
51. `[x]` Build v2.3 Mobile Readiness
52. `[x]` Build v2.4 Mobile Companion Prototype
53. `[x]` Build v2.4.1 Critical Collection Backup Hardening
54. `[x]` Build v2.4.2 Collection Integrity Audit
55. `[x]` Build v2.4.3 Collection Snapshot System
56. `[x]` Build v2.5 Photo-Assisted Entry
57. `[x]` Build v2.5.1 Photo Vault Hardening
58. `[x]` Build v2.5.2 Shopping Explainability
59. `[x]` Build v2.6 OCR Experiments
60. `[ ]` Build v3.0 Collector Companion
61. `[ ]` Improve Buy Advisor validation messages
62. `[ ]` Add autocomplete for country/denomination
63. `[ ]` Consider storage/file-picker/photo URI adapters before mobile implementation

## Official Post-v2.2 Roadmap

1. `v2.3` Mobile Readiness
2. `v2.4` Mobile Companion Prototype
3. `v2.5` Photo-Assisted Entry
4. `v2.6` OCR Experiments
5. `v3.0` Collector Companion

Clarification: `v2.3` is not a mobile app. It is a readiness and architecture milestone focused on desktop dependency audit, service layer boundary review, mobile-friendly input workflows, API readiness mapping, and phone workflow audit.

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

### 2026-06-19

#### `[x]` Build v2.6 OCR Experiments

- Date completed: 2026-06-19
- Files modified:
  - `ocr_experiment.py` (new file)
  - `test_ocr_experiment.py` (new file)
  - `coin_collection_gui.py`
  - `persistence_manager.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.6.md` (new file)
- Implementation commit hash: `f569393`
- Test coverage: total passing tests increased from 422 to 433; existing regression suites remained green.

#### `[x]` Build v2.5.2 Shopping Explainability

- Date completed: 2026-06-19
- Files modified:
  - `shopping_explainability.py` (new file)
  - `test_shopping_explainability.py` (new file)
  - `smart_shopping_assistant.py`
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.5.2.md` (new file)
- Implementation commit hash: `17821de`
- Test coverage: total passing tests increased from 410 to 422; existing regression suites remained green.

### 2026-06-18

#### `[x]` Build v2.5.1 Photo Vault Hardening

- Date completed: 2026-06-18
- Files modified:
  - `photo_vault.py`
  - `test_photo_vault.py`
  - `backup_manager.py`
  - `test_backup_manager.py`
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.5.1.md` (new file)
- Implementation commit hash: `749182f`
- Test coverage: total passing tests increased from 399 to 410; existing regression suites remained green.

#### `[x]` Build v2.5 Photo-Assisted Entry

- Date completed: 2026-06-18
- Files modified:
  - `photo_assisted_entry.py` (new file)
  - `test_photo_assisted_entry.py` (new file)
  - `coin_collection_gui.py`
  - `persistence_manager.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.5.md` (new file)
- Implementation commit hash: `fd817b6`
- Test coverage: total passing tests increased from 391 to 399; existing regression suites remained green.

#### `[x]` Build v2.4.3 Collection Snapshot System

- Date completed: 2026-06-18
- Files modified:
  - `collection_snapshot.py` (new file)
  - `test_collection_snapshot.py` (new file)
  - `coin_collection_gui.py`
  - `backup_manager.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.4.3.md` (new file)
- Implementation commit hash: `044dd50`
- Test coverage: total passing tests increased from 382 to 391; existing regression suites remained green.

#### `[x]` Build v2.4.2 Collection Integrity Audit

- Date completed: 2026-06-18
- Files modified:
  - `collection_integrity.py` (new file)
  - `test_collection_integrity.py` (new file)
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.4.2.md` (new file)
- Implementation commit hash: `bbb7314`
- Test coverage: total passing tests increased from 368 to 382; existing regression suites remained green.

#### `[x]` Build v2.4.1 Critical Collection Backup Hardening

- Date completed: 2026-06-18
- Files modified:
  - `backup_manager.py`
  - `coin_collection_gui.py`
  - `test_backup_manager.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/BACKUP.md`
  - `docs/releases/v2.4.1.md` (new file)
- Implementation commit hash: `a9ca10c`
- Test coverage: total passing tests increased from 361 to 368; existing regression suites remained green.

#### `[x]` Build v2.4 Mobile Companion Prototype

- Date completed: 2026-06-18
- Files modified:
  - `mobile_companion.py` (new file)
  - `test_mobile_companion.py` (new file)
  - `collection_dashboard.py`
  - `persistence_manager.py`
  - `backup_manager.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.4.md` (new file)
- Implementation commit hash: `8de41c7`
- Test coverage: total passing tests increased from 344 to 361; existing regression suites remained green.

#### `[x]` Build v2.3 Mobile Readiness

- Date completed: 2026-06-18
- Files modified:
  - `mobile_readiness.py` (new file)
  - `test_mobile_readiness.py` (new file)
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.2.md`
  - `docs/releases/v2.3.md` (new file)
- Implementation commit hash: `539472b`

#### `[x]` Lock post-v2.2 roadmap

- Date completed: 2026-06-18
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `README.md`
- Roadmap locked:
  - `v2.3` Mobile Readiness
  - `v2.4` Mobile Companion Prototype
  - `v2.5` Photo-Assisted Entry
  - `v2.6` OCR Experiments
  - `v3.0` Collector Companion
- Clarification: `v2.3` is a readiness and architecture milestone only, not a mobile app.

#### `[x]` Build v2.2 Data Safety and Backup Hardening

- Date completed: 2026-06-18
- Files modified:
  - `backup_manager.py` (new file)
  - `test_backup_manager.py` (new file)
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/BACKUP.md`
  - `docs/releases/v2.2.md` (new file)
- Implementation commit hash: `e70fc4c`

#### `[x]` Build v2.1 Persistence Layer

- Date completed: 2026-06-18
- Files modified:
  - `persistence_manager.py` (new file)
  - `test_persistence_manager.py` (new file)
  - `collection_data/app_state/README.md` (new file)
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/BACKUP.md`
  - `docs/releases/v2.1.md` (new file)
- Implementation commit hash: `95ef0c0`

#### `[x]` Build v2.0 Collector Operating System

- Date completed: 2026-06-18
- Files modified:
  - `collector_operating_system.py` (new file)
  - `test_collector_operating_system.py` (new file)
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
  - `docs/releases/v2.0.md` (new file)
  - `project_docs/release_prompts/v2.0.txt`
- Implementation commit hash: `11b4f6e`

#### `[x]` Build v1.9 Smart Shopping Assistant

- Date completed: 2026-06-18
- Files modified:
  - `smart_shopping_assistant.py` (new file)
  - `test_smart_shopping_assistant.py` (new file)
  - `collection_dashboard.py`
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Implementation commit hash: `efe7a1b`

### 2026-06-17

#### `[x]` Build v1.8 Market Awareness Layer

- Date completed: 2026-06-17
- Files modified:
  - `market_awareness.py` (new file)
  - `test_market_awareness.py` (new file)
  - `collection_dashboard.py`
  - `acquisition_impact.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Implementation commit hash: `5a73332`

#### `[x]` Build v1.7 Photo Vault

- Date completed: 2026-06-17
- Files modified:
  - `photo_vault.py` (new file)
  - `test_photo_vault.py` (new file)
  - `collection_dashboard.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Implementation commit hash: `0b961d9`

#### `[x]` Build v1.6 Series Tracker

- Date completed: 2026-06-17
- Files modified:
  - `series_definitions.py` (new file)
  - `series_tracker.py` (new file)
  - `test_series_tracker.py` (new file)
  - `collection_dashboard.py`
  - `acquisition_impact.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Implementation commit hash: `8c4b58b`

### 2026-06-16

#### `[x]` Build v1.5 Smarter Acquisition Intelligence

- Date completed: 2026-06-16
- Files modified:
  - `acquisition_impact.py` (new file)
  - `test_acquisition_impact.py` (new file)
  - `listing_analyzer.py`
  - `coin_collection_gui.py`
  - `collection_dashboard.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Implementation commit hash: `549665a`

#### `[x]` Build v1.4 Collection Quality Engine

- Date completed: 2026-06-16
- Files modified:
  - `collection_quality.py` (new file)
  - `test_collection_quality.py` (new file)
  - `collection_dashboard.py`
  - `test_collection_dashboard.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Implementation commit hash: `4df68f2`

#### `[x]` Build v1.3 Collection Dashboard release line

- Date completed: 2026-06-16
- Files modified:
  - `collection_dashboard.py` (new file)
  - `test_collection_dashboard.py` (new file)
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Implementation commit hash: `da1c37f`

#### `[x]` Perform v1.2 post-release usability documentation audit

- Date completed: 2026-06-16
- Files modified:
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Commit hash: `d3eac79`

#### `[x]` Build Listing Analyzer

- Date completed: 2026-06-16
- Files modified:
  - `listing_analyzer.py` (new file)
  - `test_listing_analyzer.py` (new file)
  - `coin_collection_gui.py`
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Commit hash: `7d12b54`

#### `[x]` Build Shared Session Context

- Date completed: 2026-06-16
- Files modified:
  - `session_context.py` (new file)
  - `coin_collection_gui.py`
  - `test_session_context.py` (new file)
  - `README.md`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
  - `RELEASE_HISTORY.md`
- Commit hash: `a63edb5`

#### `[x]` Complete post-v1.0 release packaging documentation

- Date completed: 2026-06-16
- Files modified:
  - `README.md`
  - `RELEASE_HISTORY.md` (new file)
  - `docs/BACKUP.md` (new file)
  - `docs/releases/v1.0.md` (new file)
  - `docs/screenshots/README.md` (new file)
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
- Commit hash: `2318550`

#### `[x]` Perform v1.0 release-readiness audit

- Date completed: 2026-06-16
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
- Commit hash: `f20fd22`

#### `[x]` Build Acquisition Workflow on Collection Intelligence Engine

- Date completed: 2026-06-16
- Files modified:
  - `acquisition_workflow.py` (new file)
  - `test_acquisition_workflow.py` (new file)
  - `focused_collection_intelligence.py`
  - `buy_advisor.py`
  - `coin_collection_gui.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
- Commit hash: `77771f6`

#### `[x]` Integrate WANT_LIST context into Collection Intelligence Engine and Do I Own This

- Date completed: 2026-06-16
- Files modified:
  - `focused_collection_intelligence.py`
  - `coin_collection_gui.py`
  - `test_focused_collection_intelligence.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
- Commit hash: `76b4f11`

#### `[x]` Consolidate advisor decisions on Collection Intelligence Engine

- Date completed: 2026-06-16
- Files modified:
  - `focused_collection_intelligence.py`
  - `buy_advisor.py`
  - `upgrade_advisor.py`
  - `test_buy_advisor_regression.py`
  - `test_upgrade_advisor.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md`
- Commit hash: `fb96574`

#### `[x]` Build focused Collection Intelligence Engine

- Date completed: 2026-06-16
- Files modified:
  - `focused_collection_intelligence.py` (new file)
  - `test_focused_collection_intelligence.py` (new file)
  - `coin_collection_gui.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `AI_HANDOFF.md` (new file)
- Commit hash: `831d363`

#### `[x]` Perform complete v0.5 release audit rerun

- Date completed: 2026-06-16
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `36fc71b`

### 2026-06-15

#### `[x]` Build Upgrade Advisor

- Date completed: 2026-06-15
- Files modified:
  - `upgrade_advisor.py`
  - `coin_collection_gui.py`
  - `test_upgrade_advisor.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `4601863`

#### `[x]` Perform v0.7 release audit

- Date completed: 2026-06-15
- Files modified:
  - `test_v07_audit.py` (new file)
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `cabd83c`

#### `[x]` Recreate dashboard metrics in app

- Date completed: 2026-06-15
- Files modified:
  - `portfolio_dashboard.py` (new file)
  - `test_portfolio_dashboard.py` (new file)
  - `coin_collection_gui.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `714e875`

#### `[x]` Perform v0.6 release audit

- Date completed: 2026-06-15
- Files modified:
  - `test_v06_audit.py` (new file)
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `2aed7a0`

#### `[x]` Build Melt Value Engine

- Date completed: 2026-06-15
- Files modified:
  - `melt_value_engine.py` (new file)
  - `test_melt_value_engine.py` (new file)
  - `buy_advisor.py`
  - `upgrade_advisor.py`
  - `test_buy_advisor_regression.py`
  - `test_upgrade_advisor.py`
- Commit hash: `8f85073`

#### `[x]` Fix low-priority world base metal Buy Advisor guardrail

- Date completed: 2026-06-15
- Files modified:
  - `buy_advisor.py`
  - `test_buy_advisor_regression.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `2aec691`

#### `[x]` Perform v0.4 integration audit

- Date completed: 2026-06-15
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `7e17d42`

#### `[x]` Connect staged WANT_LIST intent to Buy Advisor

- Date completed: 2026-06-15
- Files modified:
  - `buy_advisor.py`
  - `coin_collection_gui.py`
  - `test_buy_advisor_regression.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `4c4b854`

#### `[x]` Connect staged WANT_LIST intent to Want List Generator

- Date completed: 2026-06-15
- Files modified:
  - `collection_intelligence.py`
  - `coin_collection_gui.py`
  - `test_collection_intelligence.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `8f11122`

#### `[x]` Add WANT_LIST Preview GUI

- Date completed: 2026-06-15
- Files modified:
  - `coin_collection_gui.py`
  - `legacy_portfolio_importer.py`
  - `test_legacy_portfolio_importer.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `eced7d9`

#### `[x]` Implement legacy WANT_LIST staging integration

- Date completed: 2026-06-15
- Files modified:
  - `legacy_portfolio_importer.py`
  - `test_legacy_portfolio_importer.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `b8fa9fa`

#### `[x]` Finalize v0.3 release and plan WANT_LIST integration

- Date completed: 2026-06-15
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
  - `WANT_LIST_INTEGRATION_PLAN.md`
- Commit hash: `fab99b0`

#### `[x]` Perform v0.3 release audit

- Date completed: 2026-06-15
- Files modified:
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `20513d9`

#### `[x]` Refine Collection Gap Report MVP CSV export

- Date completed: 2026-06-15
- Files modified:
  - `collection_intelligence.py`
  - `coin_collection_gui.py`
  - `test_collection_intelligence.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `701765a`

#### `[x]` Add Portfolio Import Preview GUI

- Date completed: 2026-06-15
- Files modified:
  - `coin_collection_gui.py`
  - `legacy_portfolio_importer.py`
  - `test_legacy_portfolio_importer.py`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `c50eb12`

#### `[x]` Implement legacy portfolio staging importer

- Date completed: 2026-06-15
- Files modified:
  - `legacy_portfolio_importer.py`
  - `test_legacy_portfolio_importer.py`
  - `requirements.txt`
  - `PROJECT_STATE.md`
  - `TASK_QUEUE.md`
- Commit hash: `5e2732b`

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
