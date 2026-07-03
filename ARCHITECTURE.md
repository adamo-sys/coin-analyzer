# Coin Analyzer Architecture

> **Version:** post-v8.5 / v8.6 roadmap lock
> **Status:** living document  
> **Scope:** architectural map of the collector application after the Collector Advisor release and at the start of v8.6 Collector Intelligence & Workflow.

---

## 1. System Overview

Coin Analyzer is a desktop collector application for coin and banknote collections. It provides deterministic, explainable intelligence — grading guidance, acquisition recommendations, collection gap analysis, and portfolio tracking — without machine learning, computer vision, or live market data scraping.

The application is built as a **layered system of reusable engines** coordinated by thin orchestration and presentation layers. All business logic lives in engines. All GUI code is display-only. All workspace code is aggregation-only.

---

## 2. Layered Architecture

```
┌─────────────────────────────────────────┐
│  GUI Layer (coin_collection_gui.py)     │  ← Tkinter, read-only display,
│  ── menus, dialogs, notebooks, forms   │    "Open in Tool..." delegation
├─────────────────────────────────────────┤
│  ViewModel / Workspace Layer            │  ← CollectorWorkspace (v8.3)
│  ── aggregation, caching, lifecycle      │    Zero business logic
├─────────────────────────────────────────┤
│  Workflow / Orchestration Engines         │  ← BatchProcessing, Workflows,
│  ── coordinate existing engines          │    SmartPhoneCataloguer, CollectionAssistant
├─────────────────────────────────────────┤
│  Intelligence Engines                     │  ← CollectionIntelligence, DealHunter,
│  ── deterministic analysis & scoring     │    AIGradingAssistant, MarketIntelligence,
│                                          │    OpportunityEngine, Quality, Integrity, ...
├─────────────────────────────────────────┤
│  Data / Model Layer                      │  ← CoinItem, CoinCollection, PhotoRecord,
│  ── entities, persistence, JSON storage  │    MarketRecord, AppState, Snapshots
├─────────────────────────────────────────┤
│  Release & Governance Docs                │  ← PROJECT_STATE, AI_HANDOFF, TASK_QUEUE,
│  ── source-of-truth status & process     │    RELEASE_HISTORY, RELEASE_GOVERNANCE
└─────────────────────────────────────────┘
```

---

## 3. Major Modules and Ownership Boundaries

### Data / Model Layer
| Module | Responsibility | Key Types |
|--------|---------------|-----------|
| `coin_collection.py` | Collection CRUD, JSON persistence | `CoinItem`, `CoinCollection` |
| `photo_vault.py` | Photo metadata, linking, coverage | `PhotoRecord`, `PhotoVault` |
| `market_awareness.py` | Observed prices, purchases, sales | `MarketRecord`, `MarketAwarenessEngine` |
| `persistence_manager.py` | App state JSON save/load/backup | `PersistenceManager`, `AppState` |
| `session_context.py` | Shared workbook/WANT_LIST context | `SessionContext` |

### Intelligence Engines
| Module | Responsibility | Key Types |
|--------|---------------|-----------|
| `collection_intelligence.py` | Gaps, duplicates, upgrades, priorities | `CollectionIntelligenceEngine`, `AcquisitionTarget` |
| `collection_quality.py` | Quality scoring, strengths, weaknesses | `CollectionQualityEngine` |
| `collection_integrity.py` | Data integrity audit | `CollectionIntegrityAudit` |
| `ai_grading_assistant.py` | Deterministic grading guidance | `AIGradingAssistant`, `GradingAssessment` |
| `deal_hunter.py` | Offline listing evaluation | `DealHunter`, `DealHunterResult` |
| `opportunity_engine.py` | Budget-aware opportunity ranking | `OpportunityEngine` |
| `market_intelligence.py` | Fair-value bands from local data | `MarketIntelligenceEngine` |
| `acquisition_workflow.py` | BUY/PASS/WATCH/NEGOTIATE/REVIEW | `AcquisitionWorkflow` |
| `upgrade_advisor.py` | Upgrade potential analysis | `UpgradeAdvisor` |
| `portfolio_performance.py` | Growth, health, series progress | `PortfolioPerformanceEngine` |

### Workflow / Orchestration Engines
| Module | Responsibility | Key Types |
|--------|---------------|-----------|
| `batch_processing.py` | Folder → batch candidates → review | `BatchProcessingEngine`, `BatchCandidate` |
| `smart_phone_cataloguer.py` | Photo → OCR → candidate → entry | `SmartPhoneCataloguer`, `CatalogueResult` |
| `collection_assistant.py` | Guided cataloguing workflow | `CollectionAssistantEngine` |
| `collector_advisor.py` | Unified acquisition guidance (v8.5) | `CollectorAdvisor`, `AdvisorRecommendation`, `AdvisorReport` |
| `collector_workflows.py` | Unified workflow review target (v8.6) | `CollectorWorkflowEngine`, `WorkflowSummary` |
| `collector_workflow_integration.py` | End-to-end workflow sessions | `CollectorWorkflowIntegrationEngine` |
| `mobile_collection_entry.py` | Field entry candidates | `MobileCollectionEntryEngine` |
| `live_deal_hunter.py` | User-triggered RSS/XML ingestion | `LiveDealHunter`, `RSSListingConnector` |

### ViewModel / Workspace Layer
| Module | Responsibility | Key Types |
|--------|---------------|-----------|
| `collector_workspace.py` | Panel aggregation, lazy engines, cache | `CollectorWorkspace`, `DashboardReport`, `ReportsMenu` |
| `collector_home_dashboard.py` | Daily collector dashboard | `CollectorHomeDashboard` |
| `collector_operating_system.py` | Home + health consolidation | `CollectorHome`, `CollectionHealthReportEngine` |
| `collection_dashboard.py` | Snapshot, priorities, gaps | `CollectionDashboard` |

### GUI Layer
| Module | Responsibility |
|--------|---------------|
| `coin_collection_gui.py` | Tkinter app, menus, dialogs, all tool entry points |

### Supporting / Platform
| Module | Responsibility |
|--------|---------------|
| `backup_manager.py` | Backup packages, manifests, restore |
| `sync_backup_engine.py` | Sync simulation, conflict reporting |
| `collector_cloud.py` | Offline cloud architecture, snapshots |
| `multi_device_workspace.py` | Desktop/phone/tablet modeling |
| `platform_analytics.py` | Platform health metrics |
| `series_tracker.py` | Supported series completion |
| `photo_capture_workflow.py` | Phone photo capture metadata |
| `ocr_experiment.py` / `ocr_validation.py` / `ocr_assisted_identification.py` | OCR pipeline |
| `watchlist_engine.py` | Alert generation, presets |
| `listing_connectors.py` | CSV import normalization |
| `numista_intelligence.py` / `numista_importer.py` | Numista data integration |

---

## 4. Data Flow

### Collection Items
```
CoinItem (dataclass)
    ↓
CoinCollection (JSON persistence in data/collection.json)
    ↓
CollectionIntelligenceEngine → gaps, duplicates, upgrades
    ↓
CollectorWorkspace.get_collection_summary() → display
```

### Photos
```
PhotoCaptureWorkflow → CapturedPhoto metadata
    ↓
PhotoVault → PhotoRecord (linking, search, coverage)
    ↓
CollectorWorkspace.get_photo_vault() → coverage metrics
```

### OCR
```
CapturedPhoto / pasted text
    ↓
OCRExperiment → raw text, suggestions
    ↓
OCRValidation → trust levels, findings
    ↓
OCRAssistedIdentification → candidates with evidence
    ↓
SmartPhoneCataloguer / BatchProcessing → proposed entries
```

### Grading
```
GradingCandidate (country, denomination, year, claimed_grade, photo refs, OCR evidence)
    ↓
AIGradingAssistant → pattern analysis, evidence, confidence
    ↓
GradingAssessment (grade range, most likely, review flag, collection context)
    ↓
GUI display or batch export
```

### Batch Processing
```
Folder of photos
    ↓
BatchProcessingEngine → auto-pair, discover, create BatchCandidates
    ↓
SmartPhoneCataloguer per candidate → OCR, match, proposed entry
    ↓
CollectionIntelligence → gap/duplicate/upgrade analysis
    ↓
Review workflow → approve / reject / needs-review
    ↓
BatchReport with review counts, export
```

### Reports
```
Existing engines (quality, integrity, snapshot, ...)
    ↓
CollectorWorkspace.get_reports() → 16 lazy descriptors
    ↓
CollectorWorkspace.generate_report(name) → dict
    ↓
CollectorWorkspace.export_report(name, format, path) → file
```

### Workspace
```
CollectorWorkspace(collection_items, optional context...)
    ↓
_lazy engine initialization on first _get_engine(name)_
    ↓
Panel getter → engine query → report DTO → cache
    ↓
refresh() → cache.clear() (engines preserved)
    ↓
GUI renders DTOs read-only
```

---

## 5. Public APIs / Main Entry Points

### Application Entry Point
```python
coin_collection_gui.py  →  CoinCollectionGUI (Tkinter main loop)
```

### Workspace Public API
```python
class CollectorWorkspace:
    def __init__(self, collection_items, *, ...): ...  # keyword-only options
    def refresh(self) -> None: ...                    # clear cache, keep engines
    def get_dashboard(self) -> DashboardReport: ...
    def get_inbox(self) -> InboxReport: ...
    def get_collection_summary(self) -> CollectionSummaryReport: ...
    def get_want_list(self) -> WantListReport: ...
    def get_opportunities(self) -> OpportunitiesReport: ...
    def get_ai_queue(self) -> AIQueueReport: ...
    def get_batch_queue(self) -> BatchQueueReport: ...
    def get_photo_vault(self) -> PhotoVaultReport: ...
    def get_workflow_status(self) -> WorkflowStatusReport: ...
    def get_data_safety(self) -> DataSafetyReport: ...
    def get_reports(self) -> ReportsMenu: ...
    def generate_report(self, name: str) -> Dict[str, Any]: ...
    def export_report(self, name: str, format: str, path: str) -> bool: ...
    def get_lifecycle(self) -> LifecycleInfo: ...
```

### Key Engine Public APIs (representative)
```python
CollectionIntelligenceEngine(collection_items).analyze_by_country()
CollectionIntelligenceEngine(collection_items).detect_duplicates()
CollectionIntelligenceEngine(collection_items).detect_upgrade_candidates()

AIGradingAssistant(collection_items).assess_candidate(candidate)
AIGradingAssistant(collection_items).assess_batch(candidates)

BatchProcessingEngine(cataloguer).process_folder(source)
BatchProcessingEngine(cataloguer).review_candidate(candidate_id, decision)
```

---

## 6. Dependency Rules

These are **hard constraints**. Violations are architectural regressions.

| Rule | Rationale |
|------|-----------|
| **GUI calls workspace/tools only** | The GUI is a thin presentation layer. It never calls engines directly. |
| **Workspace aggregates only** | `CollectorWorkspace` contains zero business logic. It requests, caches, and presents results from existing engines. |
| **Engines own business logic** | Every analysis, score, recommendation, and report comes from an existing engine. The workspace never recomputes anything. |
| **No circular dependencies** | Engines should not import each other. Orchestration layers may import engines. |
| **No duplicated intelligence** | If an engine already computes it, reuse it. Do not reimplement. |
| **No duplicated collection storage** | The workspace holds a reference to collection items, not a copy. |
| **Keyword-only constructor for optional context** | `CollectorWorkspace(..., *, want_list_intents=None, ...)` — required args are positional, all optional context is keyword-only. |
| **Refresh clears cache, preserves engines** | `refresh()` calls `self._cache.clear()` but never recreates `self._engines`. |

---

## 7. Extension Points

### New Workspace Panels
1. Add a new `*Report` dataclass in `collector_workspace.py` (extend `WorkspaceReport`).
2. Add `get_*()` method that queries existing engines and returns the DTO.
3. Add a cache key in `_get_cache_key()`.
4. Add GUI rendering method in `coin_collection_gui.py`.
5. Add GUI smoke test in `test_collector_workspace.py`.

### New Reports
1. Add report descriptor to `ReportsMenu` in `collector_workspace.py`.
2. Wire `generate_report()` to existing engine method.
3. Add export support if the engine supports it.

### New Grading Evidence
1. Extend `GradingCandidate` in `ai_grading_assistant.py` with new optional fields.
2. Add factory method if integrating with another engine (e.g., `from_ocr_candidate`).
3. Update `AIGradingAssistant.assess_candidate()` to consider new evidence.
4. Update `GradingAssessment` to include new outputs.

### New Import/Export Paths
1. Extend existing import engines (`listing_connectors.py`, `legacy_portfolio_importer.py`) with new format support.
2. Reuse `CollectionItem` data model. Do not create parallel item types.
3. Add GUI workflow in `coin_collection_gui.py` using existing dialog patterns.

---

## 8. Non-Goals / Guardrails

These are **intentional boundaries**. Cross them only after explicit design review.

| Boundary | Rule |
|----------|------|
| **No ML** | No machine learning, neural networks, or AI models. The `AIGradingAssistant` is deterministic pattern analysis only. |
| **No Computer Vision** | No automated image recognition, grading from pixels, or OCR that claims authoritative results. OCR is advisory-only. |
| **No Collection Mutation Outside Workflows** | The workspace, dashboard, and reports are read-only. Only existing tool workflows (Collection Assistant, Batch Processing, manual entry) may modify collection data. |
| **No New Storage Layer Without Approval** | No new databases, no new JSON formats, no new persistence mechanisms. Use `PersistenceManager` and `collection.json` patterns. |
| **No Live Pricing** | Market Awareness is local recordkeeping only. No scraping, APIs, or live market data. |
| **No Background Jobs** | No polling, scheduled tasks, or background sync. All work is user-triggered. |
| **No Cloud Sync** | Cloud, sync, and multi-device features are offline architecture only. No real network calls. |
| **Read-Only Workspace** | The Collector Workspace never modifies collection data. All mutation flows through "Open in Tool..." buttons that launch existing dialogs. |

---

## 9. Testing Expectations

| Layer | Test Approach | Example |
|-------|-------------|---------|
| **Data/Model** | Unit tests for CRUD, serialization, edge cases | `test_backend.py` |
| **Intelligence Engines** | Unit tests with mock collection data, deterministic outputs | `test_collection_intelligence.py`, `test_ai_grading_assistant.py` |
| **Workflow Engines** | Integration tests with real engines, verify orchestration | `test_batch_processing.py`, `test_collector_workflow_integration.py` |
| **Workspace** | Mock-based unit tests + real-engine integration tests | `test_collector_workspace.py` (77 tests) |
| **GUI** | Smoke tests: import checks, method existence, no crashes | `test_collector_workspace.py` GUI smoke tests |
| **Full Suite** | `py -m unittest discover` or `run_tests.bat` | 1124 tests at v8.3 |

### Key Test Rules
- Tests must not mutate `data/collection.json`. Use temp directories and fixture copies.
- GUI tests are import/method-existence smoke tests. No Tkinter automation.
- Every engine must have error-handling tests: failures should return structured errors, not crash.
- `refresh()` must preserve engine instances (identity check: `is`).
- Cache isolation: two workspace instances must have independent caches.

---

## 10. Release Process

Releases follow a **6-phase lifecycle** defined in:

```
project_docs/release_prompts/RELEASE_GOVERNANCE.md
```

Standard phases:

```
Phase 0 — Roadmap Lock (docs, metadata, approval)
    ↓
Phase 1 — Core Engine (public API, dataclasses, unit tests)
    ↓
Phase 2 — Integration (engine wiring, panel expansion)
    ↓
Phase 3 — Integration (reports, export, advanced features)
    ↓
Phase 4 — Workflow / Lifecycle (refresh, error handling, diagnostics)
    ↓
Phase 5 — GUI (notebook tabs, read-only display, "Open in Tool...")
    ↓
Phase 6 — Release (final regression, metadata updates, tag, push, verify)
```

**Release checklist (every version):**
- [ ] All phases committed and pushed
- [ ] Full regression pass (count recorded in `PROJECT_STATE.md`)
- [ ] Metadata files updated (`PROJECT_STATE.md`, `AI_HANDOFF.md`, `TASK_QUEUE.md`, `RELEASE_HISTORY.md`)
- [ ] Release notes created (`docs/releases/vX.Y.md`)
- [ ] Release prompt archived (`project_docs/release_prompts/vX.Y.txt`)
- [ ] Annotated tag created: `git tag -a vX.Y -m "vX.Y Description"`
- [ ] Tag pushed: `git push origin vX.Y`
- [ ] Remote verified: `git ls-remote origin refs/tags/vX.Y` and `refs/tags/vX.Y^{}`

---

## Appendix: Module Count by Layer (v8.3)

| Layer | Module Count | Representative Files |
|-------|-------------|---------------------|
| Data/Model | ~8 | `coin_collection.py`, `photo_vault.py`, `market_awareness.py`, `persistence_manager.py` |
| Intelligence Engines | ~18 | `collection_intelligence.py`, `ai_grading_assistant.py`, `deal_hunter.py`, `market_intelligence.py` |
| Workflow/Orchestration | ~8 | `batch_processing.py`, `smart_phone_cataloguer.py`, `collection_assistant.py`, `collector_workflows.py` |
| ViewModel/Workspace | ~5 | `collector_workspace.py`, `collector_home_dashboard.py`, `collection_dashboard.py` |
| GUI | 1 | `coin_collection_gui.py` |
| Platform/Support | ~15 | `backup_manager.py`, `sync_backup_engine.py`, `collector_cloud.py`, `platform_analytics.py` |
| **Total** | **~55 modules** | **~1124 tests** |

---

*This document is a living reference. Update it when major architectural changes occur (new layers, new dependency rules, new extension patterns). Do not let it drift more than one release behind.*
