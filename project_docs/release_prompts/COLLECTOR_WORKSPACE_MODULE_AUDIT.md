# Collector Workspace — Module Reusability Audit (v8.3 Phase 0 Design)

**Generated:** 2026-06-29T23:28:42-0400 (EDT)  
**Scope:** Read-only design survey of 19 existing modules for potential integration into a unified "Collector Workspace" v8.3.  
**Rule:** No code changes — API surface analysis only.

---

## 1. collection_assistant.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `CollectionAssistantEngine`, `CollectionAssistantCandidate`, `AssistantReviewQueue`, `AssistantSummary`, `ProductivityMetrics` |
| **Key Public Methods** | `start_session(session_id)` -> `AssistantSummary`<br>`add_photos_to_session(session_id, photo_paths, auto_pair=True)` -> `List[PhotoInfo]`<br>`process_ocr_for_candidate(session_id, candidate_id, ocr_text)` -> `OCRCandidate`<br>`check_collection_for_candidate(session_id, candidate_id, collection_items)` -> `CollectionMatch`<br>`check_collection_gaps(session_id, candidate_id, series_data)` -> `CollectionGapInfo`<br>`check_acquisition_priority(session_id, candidate_id, want_list, strategy_data)` -> `AcquisitionPriorityInfo`<br>`build_side_by_side_comparison(session_id, candidate_id)` -> `SideBySideComparison`<br>`review_candidate(session_id, candidate_id, status, notes)` -> `bool`<br>`get_next_candidate_for_review(session_id)` -> `CollectionAssistantCandidate | None`<br>`get_incomplete_reviews(session_id)` -> `List[CollectionAssistantCandidate]`<br>`complete_session(session_id)` -> `AssistantSummary`<br>`export_session_markdown(session_id)` -> `str`<br>`export_session_csv(session_id)` -> `str` |
| **Panel-worthy Output** | Yes — Review queue (pending/approved/rejected counts), candidate list with confidence & duplicate risk, productivity metrics (OCR success rate, time saved), session completion percentage. |
| **Read-only / Mutable** | **Mutable** — Creates sessions, modifies candidate review status, adds photos, completes sessions. Stores state in `self.sessions: Dict[str, AssistantSummary]`. |

---

## 2. ai_grading_assistant.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `AIGradingAssistant`, `GradingCandidate`, `GradingAssessment`, `BatchGradingReport`, `GradePattern` |
| **Key Public Methods** | `__init__(engine: CollectionIntelligenceEngine)`<br>`assess_candidate(candidate: GradingCandidate)` -> `GradingAssessment`<br>`assess_batch(candidates: List[GradingCandidate])` -> `BatchGradingReport`<br>`export_assessment(assessment, format, path)` -> `bool` (markdown / csv)<br>`export_report(report, format, path)` -> `bool` (markdown / csv) |
| **Panel-worthy Output** | Yes — Single-candidate grade estimates (range, most likely, recommendation: PROCEED/CAUTION/REVIEW), batch summary counts, collection context (duplicate risk, upgrade opportunities). |
| **Read-only / Mutable** | **Read-only advisory** — No collection mutation. Consumes `CollectionIntelligenceEngine` as a read dependency. |

---

## 3. batch_processing.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `BatchProcessingEngine`, `BatchReport`, `BatchCandidate`, `BatchSummary`, `BatchIntelligence` |
| **Key Public Methods** | `__init__(cataloguer: SmartPhoneCataloguer)`<br>`process_folder(folder_path, collection_items, file_pattern="*.jpg", auto_pair=True)` -> `BatchReport`<br>`process(source: BatchSource, collection_items)` -> `BatchReport`<br>`review_candidate(report, candidate_id, review_status, notes)` -> `None`<br>`auto_review(report)` -> `None` |
| **Panel-worthy Output** | Yes — Batch summary (total photos, processed, failed, OCR ready, review ready, duplicates, upgrades, gaps), per-candidate review status, collection intelligence outputs (gap report, duplicates, upgrades, acquisition priorities, deal evaluation). |
| **Read-only / Mutable** | **Mutable** — Modifies candidate review states (`approve`, `reject`, `mark_needs_review`). `BatchReport` is a mutable dataclass that gets updated in place. |

---

## 4. collection_intelligence.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `CollectionIntelligenceEngine`, `AcquisitionTarget` |
| **Key Public Methods** | `__init__(items: Iterable)`<br>`analyze_by_country()` -> `Dict[str, Dict]`<br>`analyze_by_denomination()` -> `Dict[str, Dict]`<br>`analyze_by_series()` -> `Dict[Tuple[str, str], Dict]`<br>`detect_missing_years()` -> `Dict[Tuple[str, str], List[int]]`<br>`calculate_completion_percentages(series)` -> `Dict[Tuple[str, str], float]`<br>`detect_duplicates()` -> `List[Dict]`<br>`detect_upgrade_candidates()` -> `List[Dict]`<br>`generate_acquisition_priorities(limit=None)` -> `List[AcquisitionTarget]`<br>`generate_gap_report()` -> `Dict`<br>`generate_gap_report_rows()` -> `List[Dict]`<br>`generate_want_list(limit=10)` -> `List[AcquisitionTarget]`<br>`export_gap_report_markdown(path)` / `export_gap_report_csv(path)` / `export_want_list_markdown(path)` / `export_want_list_csv(path)` |
| **Panel-worthy Output** | Yes — Country breakdowns, series completion %, missing dates, duplicate groups, upgrade candidates, acquisition priority scores, gap report rows. This is the **primary data backbone** for most dashboard panels. |
| **Read-only / Mutable** | **Read-only** — Pure analysis over `self.items`. No mutation of collection data. |

---

## 5. collection_dashboard.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `CollectionDashboard`, `CollectionDashboardData`, `CollectionSnapshot`, `DashboardItem`, `SeriesCompletion` |
| **Key Public Methods** | `__init__(items, want_list_intents, photo_records, market_awareness_engine, shopping_candidates, mobile_analysis_reports)`<br>`generate_dashboard()` -> `CollectionDashboardData`<br>`format_markdown()` -> `str`<br>`export_markdown(path)` / `export_csv(path)` |
| **Panel-worthy Output** | Yes — **Comprehensive dashboard data**: snapshot (item counts, duplicates, upgrades, countries, silver, certified), quality report, photo coverage, market report, shopping report, series tracker reports, top priorities, gaps, upgrades, want-list priorities, series completion %, collection evolution. Ideal as a **master aggregation panel** or **workspace hub**. |
| **Read-only / Mutable** | **Read-only** — Orchestrates other engines and returns composite data. No mutation. |

---

## 6. collection_snapshot.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `CollectionSnapshotManager`, `CollectionSnapshot`, `CollectionSnapshotReport`, `GrowthSummary`, `SeriesProgressDelta` |
| **Key Public Methods** | `__init__(snapshot_path="collection_data/app_state/collection_snapshots.json")`<br>`create_snapshot(collection_items, want_list_intents, photo_records, market_awareness_engine, shopping_candidates)` -> `CollectionSnapshot`<br>`save_snapshot(snapshot)` -> `bool`<br>`load_snapshots()` -> `List[CollectionSnapshot]`<br>`latest_report(current_snapshot=None)` -> `CollectionSnapshotReport`<br>`compare_snapshots(current, previous, first)` -> `CollectionSnapshotReport` |
| **Panel-worthy Output** | Yes — Point-in-time snapshot metrics (collection size, quality score, integrity score, photo coverage, series completion, market/shopping counts), growth deltas, series progress changes, quality/integrity/photo coverage deltas. |
| **Read-only / Mutable** | **Mixed** — `create_snapshot` and `compare_snapshots` are read-only computations. `save_snapshot` / `save_snapshots` are **mutable** (JSON file I/O). |

---

## 7. collection_quality.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `CollectionQualityEngine`, `CollectionQualityReport`, `QualityCategoryScore`, `QualityFinding`, `QualityRecommendedAction` |
| **Key Public Methods** | `__init__(items, staged_want_list_intents)`<br>`generate_report()` -> `CollectionQualityReport`<br>`format_markdown()` -> `str`<br>`export_markdown(path)` / `export_csv(path)` |
| **Panel-worthy Output** | Yes — Overall quality score (0-100), category scores (Completeness, Upgrade, WANT_LIST Progress, Diversity, Certification), strengths, weaknesses, top recommended actions with impact scores. |
| **Read-only / Mutable** | **Read-only** — Pure scoring engine. No mutation. |

---

## 8. collection_integrity.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `CollectionIntegrityAudit`, `CollectionIntegrityReport`, `CollectionIntegrityScore`, `IntegrityFinding`, `PhotoIntegritySummary`, `MarketIntegritySummary`, `CertificationIntegritySummary` |
| **Key Public Methods** | `__init__(collection_items, photo_records, market_awareness_engine, shopping_candidates, persistence_manager, backup_manager)`<br>`run()` -> `CollectionIntegrityReport` |
| **Panel-worthy Output** | Yes — Integrity score (0-100), category scores (ownership data, photos, market records, certifications, persistence, backups), findings list with severity/category, photo/market/certification summaries, backup status, recommendations. |
| **Read-only / Mutable** | **Read-only** — Explicitly documented as read-only audit. Validates but does not mutate. |

---

## 9. collector_home_dashboard.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `CollectorHomeDashboard`, `CollectorHomeReport`, `HomeStatusCard`, `DailyCollectorAction` |
| **Key Public Methods** | `__init__(collection_items, want_list_intents, photo_records, photo_candidates, shopping_candidates, ocr_reports, market_awareness_engine, snapshot_manager, backup_manager, workflow_statuses, acknowledged_action_ids)`<br>`generate_report()` -> `CollectorHomeReport` |
| **Panel-worthy Output** | Yes — Summary headline, status cards (Collection Health, Acquisition Focus, Review Queue, Data Safety, Progress), ranked daily actions with severity/urgency, warnings, top opportunities, recent progress, workflow statuses. This is a **pre-built unified dashboard** and could be the **primary workspace view** or decomposed into panels. |
| **Read-only / Mutable** | **Read-only** — Aggregates existing systems. No mutation. Acknowledged actions are filtered but not mutated here. |

---

## 10. collector_workflows.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `CollectorWorkflowEngine`, `WorkflowSummary`, `WorkflowStatus`, `CollectorDailySummary`, `AcquisitionWorkflowReport`, `CollectionReviewReport`, `PhotoWorkflowReport` |
| **Key Public Methods** | `__init__(collection_items, want_list_intents, photo_records, photo_candidates, shopping_candidates, ocr_reports, market_awareness_engine, snapshot_manager)`<br>`acquisition_workflow(candidate, raw_ocr_text)` -> `AcquisitionWorkflowReport`<br>`collection_review_workflow()` -> `CollectionReviewReport`<br>`photo_review_workflow()` -> `PhotoWorkflowReport`<br>`daily_summary()` -> `CollectorDailySummary` |
| **Panel-worthy Output** | Yes — Workflow statuses (list of `WorkflowStatus` with severity/detail/action), next actions, recommended tasks, nested reports (photo review, OCR, validation, shopping, dashboard, quality, integrity, snapshot). `daily_summary()` is especially useful as a **"Today's Tasks" panel**. |
| **Read-only / Mutable** | **Read-only** — Orchestrates other engines into guided workflows. No mutation. |

---

## 11. collector_operating_system.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `CollectorHome`, `CollectionHealthReportEngine`, `CollectorHomeData`, `CollectionHealthReport`, `PersistenceFinding` |
| **Key Public Methods** | `CollectorHome.__init__(items, want_list_intents, shopping_candidates, market_awareness_engine, photo_records)`<br>`generate_home()` -> `CollectorHomeData`<br>`format_markdown()` / `export_markdown(path)` / `export_csv(path)`<br><br>`CollectionHealthReportEngine.__init__(items, want_list_intents, shopping_candidates, market_awareness_engine, photo_records)`<br>`generate_report()` -> `CollectionHealthReport`<br>`persistence_audit()` -> `List[PersistenceFinding]`<br>`format_markdown()` / `export_markdown(path)` / `export_csv(path)` |
| **Panel-worthy Output** | Yes — `CollectorHome` produces collection summary, best next purchase, highest impact opportunity, top WANT_LIST target, series closest to completion, quality score, photo coverage, recent market activity, workflow steps. `CollectionHealthReportEngine` adds strengths/weaknesses, priorities, recommended actions, series summaries, market summary, and persistence audit. |
| **Read-only / Mutable** | **Read-only** — Both are composite report generators. No mutation. |

---

## 12. photo_vault.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `PhotoVault`, `PhotoVaultIntegrityAudit`, `PhotoRecord`, `PhotoCoverageSummary`, `PhotoCoverageReport`, `CollectionPhotoStatus` |
| **Key Public Methods** | `PhotoVault.__init__(records, collection_items, root_path)`<br>`add_photo(record)` -> `PhotoRecord`<br>`link_collection_photo(file_path, item, notes, ...)` -> `PhotoRecord`<br>`link_candidate_photo(file_path, candidate_id, coin_name, ...)` -> `PhotoRecord`<br>`link_reference_photo(file_path, coin_name, notes)` -> `PhotoRecord`<br>`search(query)` -> `List[PhotoRecord]`<br>`find_by_certification_number(cert)` -> `List[PhotoRecord]`<br>`collection_photo_statuses()` -> `List[CollectionPhotoStatus]`<br>`coverage_summary()` -> `PhotoCoverageSummary`<br><br>`PhotoVaultIntegrityAudit.__init__(records, collection_items, photo_candidates, root_path)`<br>`run()` -> `PhotoCoverageReport` |
| **Panel-worthy Output** | Yes — Photo coverage %, items with/without photos, certified-item photo coverage, total photos, per-item photo status, audit findings (missing references, duplicates, orphans, unlinked records), recommended actions. |
| **Read-only / Mutable** | **Mixed** — `PhotoVaultIntegrityAudit` is **read-only**. `PhotoVault` itself is **mutable** (`add_photo`, `link_collection_photo`, etc.). For workspace aggregation, use `PhotoVault.coverage_summary()` and `PhotoVaultIntegrityAudit.run()`. |

---

## 13. market_awareness.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `MarketAwarenessEngine`, `MarketAwarenessReport`, `MarketSummary`, `MarketContext`, `ObservedPriceRecord`, `PurchaseRecord`, `SaleRecord`, `AuctionRecord` |
| **Key Public Methods** | `__init__(observations, purchases, sales, auctions)`<br>`generate_report()` -> `MarketAwarenessReport`<br>`historical_context_for_candidate(candidate, current_listing_cost)` -> `MarketContext`<br>`format_markdown()` / `export_markdown(path)` / `export_csv(path)` |
| **Panel-worthy Output** | Yes — Market summary (observation/purchase/sale/auction counts, average prices), recent activity list, candidate-specific market context (price range, above/below/within range). |
| **Read-only / Mutable** | **Read-only** over stored records — The engine holds lists of records but does not mutate external collection data. Records are supplied at init. |

---

## 14. smart_shopping_assistant.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `SmartShoppingAssistant`, `ShoppingRecommendationReport`, `ShoppingRecommendation`, `ShoppingCandidate` |
| **Key Public Methods** | `__init__(collection_items, want_list_intents, market_awareness_engine)`<br>`generate_report(candidates, include_want_list_targets, include_market_observations, limit)` -> `ShoppingRecommendationReport`<br>`format_markdown(report)` / `export_markdown(path, report)` / `export_csv(path, report)` |
| **Panel-worthy Output** | Yes — Ranked recommendations (STRONG BUY / BUY / NEGOTIATE / WATCH / REVIEW / PASS), best next purchase, highest impact candidate, highest priority WANT_LIST target, opportunity scores, impact scores, quality delta, series completion delta, market context, reasons, warnings. |
| **Read-only / Mutable** | **Read-only** — No collection mutation. |

---

## 15. opportunity_engine.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `OpportunityEngine`, `TopOpportunitiesReport`, `OpportunityReport`, `OpportunityScore` |
| **Key Public Methods** | `__init__(collection_items, want_list_intents, market_awareness_engine)`<br>`generate_report(shopping_candidates, deal_hunter_results, budgets, limit)` -> `TopOpportunitiesReport`<br>`export_markdown(path, report)` / `export_csv(path, report)` |
| **Panel-worthy Output** | Yes — Top overall opportunities, budget-tier recommendations ($50/$100/$250/$500), filtered lists (under $100, Newfoundland, banknote, upgrade), per-opportunity scores with explainable components (collection fit, upgrade impact, completion impact, liquidity, risk, priority). |
| **Read-only / Mutable** | **Read-only** — No mutation. |

---

## 16. deal_hunter.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `DealHunter`, `DealHunterReport`, `DealHunterResult`, `DealListing`, `ParsedDealCandidate`, `DealHunterCSVImportResult` |
| **Key Public Methods** | `__init__(collection_items, want_list_intents, market_awareness_engine)`<br>`analyze_listing(listing)` -> `DealHunterResult`<br>`generate_report(listings)` -> `DealHunterReport`<br>`import_csv(input_path)` -> `List[DealListing]`<br>`import_csv_with_warnings(input_path)` -> `DealHunterCSVImportResult` |
| **Panel-worthy Output** | Yes — Per-listing recommendations (BUY/NEGOTIATE/WATCH/REVIEW/PASS), priority/liquidity/collection-fit/risk scores, max rational price, parsed candidate fields, risk flags, reasons, counterarguments. |
| **Read-only / Mutable** | **Read-only** — No mutation. |

---

## 17. watchlist_engine.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `WatchlistEngine`, `AlertEngine`, `Watchlist`, `WatchlistItem`, `WatchlistMatch`, `WatchlistReport`, `AlertReport`, `AlertRecord`, `AlertScore` |
| **Key Public Methods** | `WatchlistEngine.__init__(watchlists)`<br>`adam_presets()` -> `Watchlist` (class method)<br>`add_watchlist(watchlist)` / `remove_watchlist(name)` / `update_watchlist(watchlist)`<br>`scan(candidates, watchlists)` -> `WatchlistReport`<br>`match_candidate(candidate, watch_item, watchlist_name)` -> `WatchlistMatch | None`<br><br>`AlertEngine.__init__(watchlist_engine)`<br>`generate_alerts(candidates, watchlists)` -> `AlertReport` |
| **Panel-worthy Output** | Yes — Watchlist matches with confidence/relevance, alert records with scored components (priority, relevance, opportunity, market confidence, upgrade), candidate summaries, recommendations. |
| **Read-only / Mutable** | **Mixed** — `WatchlistEngine` is **mutable** (add/remove/update watchlists). `AlertEngine` is **read-only** (generates alerts from existing watchlists). For workspace aggregation, treat watchlist management as a separate config panel and use `scan()` / `generate_alerts()` as read-only query panels. |

---

## 18. persistence_manager.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `PersistenceManager`, `AppState`, `PersistenceResult` |
| **Key Public Methods** | `__init__(state_dir, state_filename)`<br>`save_state(state)` -> `PersistenceResult`<br>`load_state(path)` -> `PersistenceResult`<br>`clear_state()` -> `PersistenceResult`<br>`backup_state()` -> `PersistenceResult`<br>`export_state(output_path, state)` -> `PersistenceResult`<br>`import_state(input_path)` -> `PersistenceResult`<br>`validate_state(payload)` -> `PersistenceResult`<br>`create_state(session_context, market_awareness_engine, photo_records, shopping_candidates, ...)` -> `AppState`<br>`restore_session_context(state, existing_collection_items, reload_workbook)` -> `SessionLoadResult`<br>`state_from_dict(payload)` -> `AppState` |
| **Panel-worthy Output** | Indirect — `AppState` exposes all persisted runtime objects: collection workbook path, WANT_LIST path, market records, photo records, shopping candidates, mobile candidates, OCR results, workflow statuses, home reports, deal listings, preferences, warnings, errors. Can be queried to populate **"Last Session State"** or **"Data Safety"** panels. |
| **Read-only / Mutable** | **Mutable** — Core I/O engine: save, load, clear, backup, export, import. Critical for workspace state persistence but is a **mutation layer**, not a read-only panel source. |

---

## 19. numista_intelligence.py

| Attribute | Detail |
|-----------|--------|
| **Key Classes** | `NumistaIntelligenceEngine`, `NumistaCollectionAnalyzer`, `NumistaDataModel`, `NumistaIntelligenceReport`, `NumistaItemAnalysis`, `NumistaGapReport`, `NumistaDuplicateReport`, `NumistaUpgradeReport` |
| **Key Public Methods** | `__init__(collection: CoinCollection)`<br>`from_items(items)` -> `NumistaIntelligenceEngine` (class method)<br>`analyze_file(file_path)` -> `NumistaIntelligenceReport`<br>`analyze_data(items)` -> `NumistaIntelligenceReport`<br>`export_report_csv(file_path)` / `export_report_markdown(file_path)` |
| **Panel-worthy Output** | Yes — Numista vs. local collection comparison: owned count, duplicates, upgrades, gaps, varieties, new series, not-relevant counts, gap reports per series, top priorities, upgrade reports, duplicate reports, summary recommendations. |
| **Read-only / Mutable** | **Read-only** — Analyzes Numista export data against local collection. No mutation. |

---

## Workspace Aggregation Summary

### Recommended Panel Architecture (v8.3 Design Input)

| Panel | Primary Source Module(s) | Mutation Risk |
|-------|--------------------------|---------------|
| **Collection Snapshot** | `collection_snapshot`, `collection_dashboard` | Low (snapshot save is explicit) |
| **Health & Integrity** | `collection_integrity`, `collection_quality` | None |
| **Review Queue** | `collection_assistant`, `batch_processing` | Medium (review status changes) |
| **Photo Vault** | `photo_vault` (integrity audit), `photo_vault` (coverage) | Low (photo linking is explicit) |
| **Market Awareness** | `market_awareness` | None |
| **Shopping / Opportunities** | `smart_shopping_assistant`, `opportunity_engine`, `deal_hunter` | None |
| **Watchlist & Alerts** | `watchlist_engine` (AlertEngine), `watchlist_engine` (WatchlistEngine) | Low (watchlist edits are explicit) |
| **Workflow Status** | `collector_workflows`, `collector_home_dashboard` | None |
| **Numista Sync** | `numista_intelligence` | None |
| **Data Safety / Persistence** | `persistence_manager`, `collection_integrity` (backup status) | Medium (I/O operations) |
| **Collector Home (Master)** | `collector_home_dashboard` or `collector_operating_system` | None |

### Key Design Implications

1. **Read-only core**: ~13 of 19 modules are naturally read-only or can be used in a read-only mode. The workspace should query these freely without side effects.
2. **Mutation boundaries**: `collection_assistant`, `batch_processing`, `photo_vault` (add/link), `watchlist_engine` (watchlist CRUD), and `persistence_manager` are the only mutable surfaces. The workspace should wrap these with explicit action buttons (e.g., "Approve", "Reject", "Save Snapshot", "Add Photo").
3. **Aggregation hub**: `CollectionDashboard` and `CollectorHomeDashboard` already do most of the heavy lifting. A Collector Workspace could either **embed their outputs** directly or **decompose them into individual panels**.
4. **Snapshot history**: `CollectionSnapshotManager` provides time-series comparison. Ideal for a **"Progress Over Time"** panel.
5. **Workflow integration**: `CollectorWorkflowEngine.daily_summary()` generates a task list. Ideal for a **"Today's Tasks"** or **"Action Queue"** sidebar.
