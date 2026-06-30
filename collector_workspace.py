"""CollectorWorkspace — unified workspace aggregation layer (ViewModel only).

v8.3 Phase 1: Core aggregation engine. Zero business logic.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Report dataclasses (plain, serializable, no engine objects)
# ---------------------------------------------------------------------------

@dataclass
class WorkspaceReport:
    """Base class for all workspace reports."""

    generated_at: datetime = field(default_factory=datetime.now)
    engine_errors: List[str] = field(default_factory=list)

    def has_errors(self) -> bool:
        return bool(self.engine_errors)


@dataclass
class DashboardReport(WorkspaceReport):
    """Aggregated daily dashboard."""

    health_score: Optional[int] = None
    quality_score: Optional[int] = None
    integrity_score: Optional[int] = None
    top_priority: Optional[str] = None
    best_next_purchase: Optional[str] = None
    todays_tasks: List[str] = field(default_factory=list)
    recent_activity: List[str] = field(default_factory=list)
    data_safety_status: Optional[str] = None
    backup_ready: bool = False


@dataclass
class InboxReport(WorkspaceReport):
    """Consolidated review queue."""

    total_pending: int = 0
    collection_assistant_pending: int = 0
    batch_processing_pending: int = 0
    ai_grading_review: int = 0
    workflow_items: List[str] = field(default_factory=list)
    items: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CollectionSummaryReport(WorkspaceReport):
    """One-glance collection snapshot."""

    total_items: int = 0
    total_countries: int = 0
    total_denominations: int = 0
    total_years: int = 0
    grade_coverage: Optional[str] = None
    series_completion: List[Dict[str, Any]] = field(default_factory=list)
    recent_additions: int = 0
    quality_score: Optional[int] = None
    integrity_score: Optional[int] = None


@dataclass
class WantListReport(WorkspaceReport):
    """Upgrade candidates, collection gaps, and watchlist targets."""

    upgrade_candidates: List[Dict[str, Any]] = field(default_factory=list)
    gap_targets: List[Dict[str, Any]] = field(default_factory=list)
    watchlist_matches: List[Dict[str, Any]] = field(default_factory=list)
    total_upgrades: int = 0
    total_gaps: int = 0
    total_watchlist_matches: int = 0


@dataclass
class OpportunitiesReport(WorkspaceReport):
    """Shopping opportunities and purchase pipeline."""

    top_recommendations: List[Dict[str, Any]] = field(default_factory=list)
    best_next_purchase: Optional[str] = None
    highest_impact: Optional[str] = None
    total_opportunities: int = 0
    budget_recommendations: List[str] = field(default_factory=list)


@dataclass
class AIQueueReport(WorkspaceReport):
    """Pending AI grading assessments."""

    total_assessments: int = 0
    proceed_count: int = 0
    caution_count: int = 0
    review_count: int = 0
    assessments: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class BatchQueueReport(WorkspaceReport):
    """Batch processing sessions and review status."""

    total_sessions: int = 0
    total_candidates: int = 0
    reviewed_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    needs_review_count: int = 0
    duplicate_count: int = 0
    upgrade_count: int = 0
    gap_count: int = 0
    sessions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PhotoVaultReport(WorkspaceReport):
    """Photo coverage, missing photos, and integrity."""

    total_collection_items: int = 0
    items_with_photos: int = 0
    items_without_photos: int = 0
    coverage_percentage: float = 0.0
    certified_items: int = 0
    certified_with_photos: int = 0
    missing_photo_count: int = 0
    duplicate_photo_count: int = 0
    recommended_actions: List[str] = field(default_factory=list)


@dataclass
class WorkflowStatusReport(WorkspaceReport):
    """Active workflows and today's tasks."""

    active_workflows: List[str] = field(default_factory=list)
    todays_tasks: List[str] = field(default_factory=list)
    pending_reviews: int = 0
    next_actions: List[str] = field(default_factory=list)
    workflow_health: Optional[str] = None


@dataclass
class DataSafetyReport(WorkspaceReport):
    """Backup readiness, integrity warnings, persistence status."""

    backup_ready: bool = False
    last_snapshot_age: Optional[str] = None
    integrity_warnings: List[str] = field(default_factory=list)
    persistence_areas: List[Dict[str, Any]] = field(default_factory=list)
    total_persistence_areas: int = 0
    persisted_areas: int = 0
    session_only_areas: int = 0


@dataclass
class LifecycleInfo:
    """Diagnostic snapshot of CollectorWorkspace runtime state. No engine calls."""

    engine_count: int = 0
    cached_panel_count: int = 0
    total_panels: int = 10
    reports_menu_cached: bool = False
    panel_names_cached: List[str] = field(default_factory=list)
    collection_item_count: int = 0


@dataclass
class ReportDescriptor:
    """Metadata for a single report type available in the workspace."""

    name: str
    title: str
    category: str
    description: str
    engine_name: str
    method_name: str
    has_markdown_export: bool = False
    has_csv_export: bool = False
    available: bool = True


@dataclass
class ReportsMenu(WorkspaceReport):
    """Menu of all available report types."""

    reports: List[ReportDescriptor] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    total_reports: int = 0
    available_reports: int = 0

    def by_category(self, category: str) -> List[ReportDescriptor]:
        return [r for r in self.reports if r.category == category]

    def by_name(self, name: str) -> Optional[ReportDescriptor]:
        for r in self.reports:
            if r.name == name:
                return r
        return None


# ---------------------------------------------------------------------------
# CollectorWorkspace
# ---------------------------------------------------------------------------

class CollectorWorkspace:
    """Unified workspace — thin aggregation layer. Zero business logic."""

    def __init__(
        self,
        collection_items: List[Any],
        *,
        want_list_intents: Optional[List[Any]] = None,
        photo_records: Optional[List[Any]] = None,
        shopping_candidates: Optional[List[Any]] = None,
        market_awareness_engine: Optional[Any] = None,
        photo_candidates: Optional[List[Any]] = None,
        watchlists: Optional[List[Any]] = None,
        ocr_reports: Optional[List[Any]] = None,
        workflow_statuses: Optional[List[Dict[str, Any]]] = None,
        acknowledged_action_ids: Optional[List[str]] = None,
    ):
        """Initialize with collection items and optional context. No collection copy. No engine instantiation yet.

        Args:
            collection_items: Source collection (required).
            want_list_intents: Optional want list items for gap/upgrade analysis.
            photo_records: Optional photo records for vault/integrity panels.
            shopping_candidates: Optional shopping candidates for opportunities panel.
            market_awareness_engine: Optional market awareness engine for shopping/integrity.
            photo_candidates: Optional photo candidates for vault audit.
            watchlists: Optional watchlists for want list panel.
            ocr_reports: Optional OCR reports for workflow panel.
            workflow_statuses: Optional workflow statuses for dashboard panel.
            acknowledged_action_ids: Optional acknowledged action IDs for home dashboard.
        """
        self._collection_items = collection_items
        self._want_list_intents = want_list_intents
        self._photo_records = photo_records
        self._shopping_candidates = shopping_candidates
        self._market_awareness_engine = market_awareness_engine
        self._photo_candidates = photo_candidates
        self._watchlists = watchlists
        self._ocr_reports = ocr_reports
        self._workflow_statuses = workflow_statuses
        self._acknowledged_action_ids = acknowledged_action_ids
        self._engines: Dict[str, Any] = {}
        self._cache: Dict[str, WorkspaceReport] = {}

    # -- Lazy engine initialization ----------------------------------------

    def _get_engine(self, name: str) -> Any:
        """Lazy engine initialization. Creates engine on first access."""
        if name not in self._engines:
            self._engines[name] = self._create_engine(name)
        return self._engines[name]

    def _create_engine(self, name: str) -> Any:
        """Factory for creating engines."""
        if name == "collection_intelligence":
            from collection_intelligence import CollectionIntelligenceEngine

            return CollectionIntelligenceEngine(self._collection_items)

        elif name == "collection_dashboard":
            from collection_dashboard import CollectionDashboard

            return CollectionDashboard(
                self._collection_items,
                self._want_list_intents,
                photo_records=self._photo_records,
                market_awareness_engine=self._market_awareness_engine,
                shopping_candidates=self._shopping_candidates,
            )

        elif name == "collector_home_dashboard":
            from collector_home_dashboard import CollectorHomeDashboard

            return CollectorHomeDashboard(
                self._collection_items,
                want_list_intents=self._want_list_intents,
                photo_records=self._photo_records,
                photo_candidates=self._photo_candidates,
                shopping_candidates=self._shopping_candidates,
                ocr_reports=self._ocr_reports,
                market_awareness_engine=self._market_awareness_engine,
                workflow_statuses=self._workflow_statuses,
                acknowledged_action_ids=self._acknowledged_action_ids,
            )

        elif name == "collector_operating_system":
            from collector_operating_system import CollectorHome, CollectionHealthReportEngine

            return {
                "home": CollectorHome(
                    self._collection_items,
                    want_list_intents=self._want_list_intents,
                    shopping_candidates=self._shopping_candidates,
                    market_awareness_engine=self._market_awareness_engine,
                    photo_records=self._photo_records,
                ),
                "health": CollectionHealthReportEngine(
                    self._collection_items,
                    want_list_intents=self._want_list_intents,
                    shopping_candidates=self._shopping_candidates,
                    market_awareness_engine=self._market_awareness_engine,
                    photo_records=self._photo_records,
                ),
            }

        elif name == "collection_assistant":
            from collection_assistant import CollectionAssistantEngine

            return CollectionAssistantEngine()

        elif name == "batch_processing":
            from batch_processing import BatchProcessingEngine
            from smart_phone_cataloguer import SmartPhoneCataloguer

            return BatchProcessingEngine(SmartPhoneCataloguer())

        elif name == "ai_grading":
            from ai_grading_assistant import AIGradingAssistant
            from collection_intelligence import CollectionIntelligenceEngine

            return AIGradingAssistant(CollectionIntelligenceEngine(self._collection_items))

        elif name == "collector_workflows":
            from collector_workflows import CollectorWorkflowEngine

            return CollectorWorkflowEngine(
                self._collection_items,
                want_list_intents=self._want_list_intents,
                photo_records=self._photo_records,
                photo_candidates=self._photo_candidates,
                shopping_candidates=self._shopping_candidates,
                ocr_reports=self._ocr_reports,
                market_awareness_engine=self._market_awareness_engine,
            )

        elif name == "collection_snapshot":
            from collection_snapshot import CollectionSnapshotManager

            return CollectionSnapshotManager()

        elif name == "collection_quality":
            from collection_quality import CollectionQualityEngine

            return CollectionQualityEngine(self._collection_items, self._want_list_intents)

        elif name == "collection_integrity":
            from collection_integrity import CollectionIntegrityAudit

            return CollectionIntegrityAudit(
                self._collection_items,
                photo_records=self._photo_records,
                market_awareness_engine=self._market_awareness_engine,
                shopping_candidates=self._shopping_candidates,
            )

        elif name == "watchlist_engine":
            from watchlist_engine import WatchlistEngine

            return WatchlistEngine(self._watchlists)

        elif name == "opportunity_engine":
            from opportunity_engine import OpportunityEngine

            return OpportunityEngine(
                self._collection_items,
                self._want_list_intents,
                self._market_awareness_engine,
            )

        elif name == "smart_shopping":
            from smart_shopping_assistant import SmartShoppingAssistant

            return SmartShoppingAssistant(
                self._collection_items,
                self._want_list_intents,
                self._market_awareness_engine,
            )

        elif name == "photo_vault":
            from photo_vault import PhotoVault

            return PhotoVault(self._photo_records, self._collection_items)

        elif name == "photo_vault_audit":
            from photo_vault import PhotoVaultIntegrityAudit

            return PhotoVaultIntegrityAudit(
                self._photo_records, self._collection_items, self._photo_candidates
            )

        elif name == "persistence_manager":
            from persistence_manager import PersistenceManager

            return PersistenceManager()

        else:
            raise ValueError(f"Unknown engine: {name}")

    # -- Refresh & Lifecycle ------------------------------------------------

    def refresh(self) -> None:
        """Clear all caches. Next panel query will re-query engines."""
        self._cache.clear()

    def get_lifecycle(self) -> LifecycleInfo:
        """Return a diagnostic snapshot of workspace state. No engine calls, no mutations."""
        return LifecycleInfo(
            engine_count=len(self._engines),
            cached_panel_count=len(self._cache),
            reports_menu_cached="reports" in self._cache,
            panel_names_cached=list(self._cache.keys()),
            collection_item_count=len(self._collection_items),
        )

    # -- Panel aggregation (Phase 1: three panels only) -------------------

    def get_dashboard(self) -> DashboardReport:
        """Aggregate home dashboard + operating system into unified daily dashboard."""
        if "dashboard" in self._cache:
            return self._cache["dashboard"]

        report = DashboardReport()
        errors: List[str] = []

        # Query CollectorHomeDashboard
        try:
            home_engine = self._get_engine("collector_home_dashboard")
            home_report = home_engine.generate_report()
            report.health_score = getattr(home_report, "health_score", None)
            report.top_priority = getattr(home_report, "top_priority", None)
            report.recent_activity = getattr(home_report, "recent_activity", [])
            # Derive top_priority from daily_actions if not present directly
            daily_actions = getattr(home_report, "daily_actions", [])
            if not report.top_priority and daily_actions:
                first = daily_actions[0]
                report.top_priority = getattr(first, "title", None) or getattr(first, "action", None)
        except Exception as e:
            errors.append(f"Home dashboard: {e}")

        # Query CollectorOperatingSystem
        try:
            os_engine = self._get_engine("collector_operating_system")
            home = os_engine["home"]
            health = os_engine["health"]
            home_data = home.generate_home()
            health_report = health.generate_report()
            report.best_next_purchase = getattr(home_data, "best_next_purchase", None)
            # Derive data safety from persistence findings
            findings = getattr(health_report, "persistence_findings", [])
            json_finding = next(
                (f for f in findings if getattr(f, "area", "") == "Collection JSON"), None
            )
            if json_finding:
                report.data_safety_status = "Persisted" if getattr(json_finding, "survives_restart", False) else "Session-only"
                report.backup_ready = getattr(json_finding, "survives_restart", False)
        except Exception as e:
            errors.append(f"Operating system: {e}")

        # Query CollectorWorkflowEngine for today's tasks
        try:
            workflow_engine = self._get_engine("collector_workflows")
            daily = workflow_engine.daily_summary()
            report.todays_tasks = getattr(daily, "recommended_tasks", [])
        except Exception as e:
            errors.append(f"Workflows: {e}")

        # Query CollectionQualityEngine for quality score
        try:
            quality_engine = self._get_engine("collection_quality")
            quality_report = quality_engine.generate_report()
            report.quality_score = getattr(quality_report, "overall_quality_score", None)
        except Exception as e:
            errors.append(f"Quality: {e}")

        # Query CollectionIntegrityAudit for integrity score
        try:
            integrity_engine = self._get_engine("collection_integrity")
            integrity_report = integrity_engine.run()
            score_obj = getattr(integrity_report, "integrity_score", None)
            report.integrity_score = getattr(score_obj, "score", None) if score_obj else None
        except Exception as e:
            errors.append(f"Integrity: {e}")

        report.engine_errors = errors
        self._cache["dashboard"] = report
        return report

    def get_inbox(self) -> InboxReport:
        """Aggregate review queues from CollectionAssistant, BatchProcessing, and AIGradingAssistant."""
        if "inbox" in self._cache:
            return self._cache["inbox"]

        report = InboxReport()
        errors: List[str] = []
        items: List[Dict[str, Any]] = []

        # Query CollectionAssistant
        try:
            assistant_engine = self._get_engine("collection_assistant")
            session = assistant_engine.start_session("workspace")
            queue = session.queue
            report.collection_assistant_pending = getattr(queue, "pending_count", 0)
            for candidate in getattr(queue, "candidates", []):
                if getattr(candidate, "is_pending", False):
                    items.append(
                        {
                            "source": "Collection Assistant",
                            "label": getattr(candidate, "display_label", "Unknown"),
                            "confidence": getattr(candidate, "confidence", 0.0),
                            "id": getattr(candidate, "id", ""),
                        }
                    )
        except Exception as e:
            errors.append(f"Collection Assistant: {e}")

        # Query BatchProcessing (Phase 1: placeholder)
        try:
            _batch_engine = self._get_engine("batch_processing")
            report.batch_processing_pending = 0  # Phase 1: session-based, not yet persisted
        except Exception as e:
            errors.append(f"Batch Processing: {e}")

        # Query AIGradingAssistant (Phase 1: placeholder)
        try:
            _ai_engine = self._get_engine("ai_grading")
            report.ai_grading_review = 0  # Phase 1: not yet persisted
        except Exception as e:
            errors.append(f"AI Grading: {e}")

        report.total_pending = (
            report.collection_assistant_pending + report.batch_processing_pending + report.ai_grading_review
        )
        report.items = items
        report.engine_errors = errors
        self._cache["inbox"] = report
        return report

    def get_collection_summary(self) -> CollectionSummaryReport:
        """Aggregate collection intelligence + dashboard + snapshot into one-glance summary."""
        if "collection_summary" in self._cache:
            return self._cache["collection_summary"]

        report = CollectionSummaryReport()
        errors: List[str] = []

        # Query CollectionIntelligenceEngine
        try:
            intel_engine = self._get_engine("collection_intelligence")
            by_country = intel_engine.analyze_by_country()
            report.total_items = sum(data.get("count", 0) for data in by_country.values())
            report.total_countries = len(by_country)
            report.total_denominations = len(
                set(denom for data in by_country.values() for denom in data.get("denominations", []))
            )
            all_years: set = set()
            for data in by_country.values():
                all_years.update(data.get("years", []))
            report.total_years = len(all_years)
        except Exception as e:
            errors.append(f"Collection Intelligence: {e}")

        # Query CollectionDashboard
        try:
            dashboard_engine = self._get_engine("collection_dashboard")
            dashboard = dashboard_engine.generate_dashboard()
            report.grade_coverage = getattr(dashboard, "grade_coverage", None)
            series_completion = getattr(dashboard, "series_completion", [])
            report.series_completion = [row.to_dict() for row in series_completion]
        except Exception as e:
            errors.append(f"Collection Dashboard: {e}")

        # Query CollectionSnapshotManager
        try:
            snapshot_engine = self._get_engine("collection_snapshot")
            current = snapshot_engine.create_snapshot(
                self._collection_items,
                want_list_intents=self._want_list_intents,
                photo_records=self._photo_records,
                market_awareness_engine=self._market_awareness_engine,
                shopping_candidates=self._shopping_candidates,
            )
            latest = snapshot_engine.latest_report(current)
            growth = getattr(latest, "growth_summary", None)
            report.recent_additions = getattr(growth, "growth_since_last_snapshot", 0) if growth else 0
        except Exception as e:
            errors.append(f"Collection Snapshot: {e}")

        # Query CollectionQualityEngine
        try:
            quality_engine = self._get_engine("collection_quality")
            quality_report = quality_engine.generate_report()
            report.quality_score = getattr(quality_report, "overall_quality_score", None)
        except Exception as e:
            errors.append(f"Quality: {e}")

        # Query CollectionIntegrityAudit
        try:
            integrity_engine = self._get_engine("collection_integrity")
            integrity_report = integrity_engine.run()
            score_obj = getattr(integrity_report, "integrity_score", None)
            report.integrity_score = getattr(score_obj, "score", None) if score_obj else None
        except Exception as e:
            errors.append(f"Integrity: {e}")

        report.engine_errors = errors
        self._cache["collection_summary"] = report
        return report

    # -- Phase 2 panels (7 new panels) ------------------------------------

    def get_want_list(self) -> WantListReport:
        """Aggregate upgrade candidates, collection gaps, and watchlist targets."""
        if "want_list" in self._cache:
            return self._cache["want_list"]

        report = WantListReport()
        errors: List[str] = []

        # CollectionIntelligenceEngine: upgrade candidates + gaps
        try:
            intel = self._get_engine("collection_intelligence")
            upgrades = intel.detect_upgrade_candidates()
            report.upgrade_candidates = [u.to_dict() if hasattr(u, "to_dict") else dict(u) for u in upgrades]
            report.total_upgrades = len(upgrades)
            gap = intel.generate_gap_report()
            gaps = gap.get("series_rows", []) if isinstance(gap, dict) else []
            report.gap_targets = [g.to_dict() if hasattr(g, "to_dict") else dict(g) for g in gaps]
            report.total_gaps = len(gaps)
        except Exception as e:
            errors.append(f"Collection Intelligence: {e}")

        # WatchlistEngine: scan for matches
        try:
            watch = self._get_engine("watchlist_engine")
            watch_report = watch.scan(self._collection_items, self._watchlists)
            matches = getattr(watch_report, "matches", [])
            report.watchlist_matches = [m.to_dict() if hasattr(m, "to_dict") else dict(m) for m in matches]
            report.total_watchlist_matches = len(matches)
        except Exception as e:
            errors.append(f"Watchlist: {e}")

        report.engine_errors = errors
        self._cache["want_list"] = report
        return report

    def get_opportunities(self) -> OpportunitiesReport:
        """Aggregate shopping opportunities and purchase pipeline."""
        if "opportunities" in self._cache:
            return self._cache["opportunities"]

        report = OpportunitiesReport()
        errors: List[str] = []

        # SmartShoppingAssistant: top recommendations
        try:
            shopping = self._get_engine("smart_shopping")
            shop_report = shopping.generate_report(
                self._shopping_candidates,
                include_want_list_targets=bool(self._want_list_intents),
                limit=10,
            )
            recs = getattr(shop_report, "recommendations", [])
            report.top_recommendations = [r.to_dict() if hasattr(r, "to_dict") else dict(r) for r in recs]
            report.total_opportunities = len(recs)
            report.best_next_purchase = getattr(shop_report, "best_next_purchase", None)
            report.highest_impact = getattr(shop_report, "highest_impact_candidate", None)
        except Exception as e:
            errors.append(f"Smart Shopping: {e}")

        # OpportunityEngine: budget recommendations + top opportunities
        try:
            opp = self._get_engine("opportunity_engine")
            opp_report = opp.generate_report(self._shopping_candidates, limit=5)
            budget = getattr(opp_report, "budget_recommendations", [])
            report.budget_recommendations = budget if isinstance(budget, list) else []
        except Exception as e:
            errors.append(f"Opportunity Engine: {e}")

        report.engine_errors = errors
        self._cache["opportunities"] = report
        return report

    def get_ai_queue(self) -> AIQueueReport:
        """Pending AI grading assessments. Phase 2: placeholder (no persisted queue)."""
        if "ai_queue" in self._cache:
            return self._cache["ai_queue"]

        report = AIQueueReport()
        # Phase 2: AI grading queue is not yet persisted.
        # When candidates are available, this will aggregate assess_batch() results.
        self._cache["ai_queue"] = report
        return report

    def get_batch_queue(self) -> BatchQueueReport:
        """Batch processing sessions and review status. Phase 2: placeholder (no persisted sessions)."""
        if "batch_queue" in self._cache:
            return self._cache["batch_queue"]

        report = BatchQueueReport()
        # Phase 2: Batch processing is session-based, not yet persisted.
        # When sessions are available, this will aggregate BatchReport summaries.
        self._cache["batch_queue"] = report
        return report

    def get_photo_vault(self) -> PhotoVaultReport:
        """Aggregate photo coverage, missing photos, and integrity."""
        if "photo_vault" in self._cache:
            return self._cache["photo_vault"]

        report = PhotoVaultReport()
        errors: List[str] = []

        # PhotoVault: coverage summary
        try:
            vault = self._get_engine("photo_vault")
            coverage = vault.coverage_summary()
            report.total_collection_items = getattr(coverage, "total_collection_items", 0)
            report.items_with_photos = getattr(coverage, "items_with_photos", 0)
            report.items_without_photos = getattr(coverage, "items_without_photos", 0)
            report.coverage_percentage = getattr(coverage, "photo_coverage_percentage", 0.0)
            report.certified_items = getattr(coverage, "certified_items", 0)
            report.certified_with_photos = getattr(coverage, "certified_items_with_photos", 0)
        except Exception as e:
            errors.append(f"Photo Vault: {e}")

        # PhotoVaultIntegrityAudit: missing/duplicate photos
        try:
            audit = self._get_engine("photo_vault_audit")
            audit_report = audit.run()
            report.missing_photo_count = getattr(audit_report, "missing_photo_references", 0)
            report.duplicate_photo_count = getattr(audit_report, "duplicate_photo_references", 0)
            report.recommended_actions = getattr(audit_report, "recommended_actions", [])
        except Exception as e:
            errors.append(f"Photo Vault Audit: {e}")

        report.engine_errors = errors
        self._cache["photo_vault"] = report
        return report

    def get_workflow_status(self) -> WorkflowStatusReport:
        """Aggregate active workflows and today's tasks."""
        if "workflow_status" in self._cache:
            return self._cache["workflow_status"]

        report = WorkflowStatusReport()
        errors: List[str] = []

        try:
            workflow = self._get_engine("collector_workflows")
            daily = workflow.daily_summary()
            report.todays_tasks = getattr(daily, "recommended_tasks", [])
            summary = getattr(daily, "summary", None)
            if summary:
                report.active_workflows = [getattr(summary, "workflow_name", "Workflow")]
                report.pending_reviews = len(getattr(summary, "statuses", []))
                report.next_actions = getattr(summary, "next_actions", [])
                report.workflow_health = getattr(summary, "status", None)
        except Exception as e:
            errors.append(f"Workflows: {e}")

        report.engine_errors = errors
        self._cache["workflow_status"] = report
        return report

    def get_data_safety(self) -> DataSafetyReport:
        """Aggregate backup readiness, integrity warnings, and persistence status."""
        if "data_safety" in self._cache:
            return self._cache["data_safety"]

        report = DataSafetyReport()
        errors: List[str] = []

        # PersistenceManager: load state to check persistence
        try:
            pm = self._get_engine("persistence_manager")
            result = pm.load_state()
            state = getattr(result, "state", None)
            if state:
                report.backup_ready = True
                saved_at = getattr(state, "saved_at", None)
                if saved_at:
                    report.last_snapshot_age = str(saved_at)
        except Exception as e:
            errors.append(f"Persistence Manager: {e}")

        # CollectionIntegrityAudit: persistence findings
        try:
            integrity = self._get_engine("collection_integrity")
            integrity_report = integrity.run()
            findings = getattr(integrity_report, "persistence_findings", [])
            if not findings:
                # Fallback: try health report engine
                health = self._get_engine("collector_operating_system")["health"]
                health_report = health.generate_report()
                findings = getattr(health_report, "persistence_findings", [])
            report.persistence_areas = [f.to_dict() if hasattr(f, "to_dict") else dict(f) for f in findings]
            report.total_persistence_areas = len(report.persistence_areas)
            report.persisted_areas = sum(1 for f in findings if getattr(f, "survives_restart", False))
            report.session_only_areas = report.total_persistence_areas - report.persisted_areas
            report.integrity_warnings = getattr(integrity_report, "warnings", [])
        except Exception as e:
            errors.append(f"Integrity Audit: {e}")

        report.engine_errors = errors
        self._cache["data_safety"] = report
        return report

    # ---------------------------------------------------------------------------
    # Reports Panel (Phase 3)
    # ---------------------------------------------------------------------------

    def get_reports(self) -> ReportsMenu:
        """Return a menu of all available report types. No eager generation."""
        if "reports" in self._cache:
            return self._cache["reports"]

        menu = ReportsMenu()
        descriptors = self._report_registry()
        menu.reports = descriptors
        menu.categories = sorted(set(r.category for r in descriptors))
        menu.total_reports = len(descriptors)
        menu.available_reports = sum(1 for r in descriptors if r.available)
        self._cache["reports"] = menu
        return menu

    def generate_report(self, name: str) -> Dict[str, Any]:
        """Lazily generate a specific report by name. Returns the report as a dict."""
        menu = self.get_reports()
        descriptor = menu.by_name(name)
        if not descriptor:
            raise ValueError(f"Unknown report: {name}")
        if not descriptor.available:
            return {
                "error": "Report unavailable",
                "reason": f"Report '{name}' requires context that is not provided (e.g., watchlists, photo_records, candidates)",
                "name": name,
            }

        try:
            report = self._invoke_report_method(descriptor)
        except Exception as e:
            return {
                "error": "Report generation failed",
                "reason": str(e),
                "name": name,
            }

        return report.to_dict() if hasattr(report, "to_dict") else dict(report)

    def export_report(self, name: str, format: str, path: str) -> bool:
        """Export a specific report to a file. Delegates to engine or report export method."""
        if format not in ("markdown", "csv"):
            raise ValueError(f"Unsupported format: {format}")

        menu = self.get_reports()
        descriptor = menu.by_name(name)
        if not descriptor:
            raise ValueError(f"Unknown report: {name}")
        if not descriptor.available:
            raise RuntimeError(f"Report '{name}' is not available (missing context)")

        export_attr = "export_markdown" if format == "markdown" else "export_csv"

        try:
            report = self._invoke_report_method(descriptor)
        except Exception as e:
            raise RuntimeError(f"Failed to generate report '{name}': {e}") from e

        # Try engine first, then report object
        engine = self._get_engine(descriptor.engine_name)
        if descriptor.engine_name == "collector_operating_system":
            engine = engine["health"]
        export_method = getattr(engine, export_attr, None)
        if export_method is None:
            export_method = getattr(report, export_attr, None)
        if export_method is None:
            raise ValueError(f"No export method '{export_attr}' for report '{name}'")

        return export_method(path)

    # -- Internal helpers --------------------------------------------------

    def _invoke_report_method(self, descriptor: ReportDescriptor) -> Any:
        """Invoke the engine method for a report descriptor."""
        engine = self._get_engine(descriptor.engine_name)
        if descriptor.engine_name == "collector_operating_system":
            engine = engine["health"]
            method = getattr(engine, descriptor.method_name)
            return method()
        elif descriptor.engine_name == "collection_snapshot":
            # Snapshot: create snapshot then get latest report
            snapshot_mgr = engine
            current = snapshot_mgr.create_snapshot(
                self._collection_items,
                want_list_intents=self._want_list_intents,
                photo_records=self._photo_records,
                market_awareness_engine=self._market_awareness_engine,
                shopping_candidates=self._shopping_candidates,
            )
            return snapshot_mgr.latest_report(current)
        elif descriptor.engine_name == "ai_grading":
            # AI Grading: batch assess with no candidates returns empty report
            method = getattr(engine, descriptor.method_name)
            return method([])
        elif descriptor.engine_name == "watchlist_engine":
            method = getattr(engine, descriptor.method_name)
            return method(self._collection_items, self._watchlists)
        elif descriptor.engine_name == "deal_hunter":
            method = getattr(engine, descriptor.method_name)
            return method([])
        else:
            method = getattr(engine, descriptor.method_name)
            return method()

    def _report_registry(self) -> List[ReportDescriptor]:
        """Registry of all available report types. No engine calls."""
        return [
            ReportDescriptor(
                name="collection_dashboard",
                title="Collection Dashboard",
                category="Collection",
                description="Overview of collection items, duplicates, upgrades, and gaps",
                engine_name="collection_dashboard",
                method_name="generate_dashboard",
                has_markdown_export=True,
                has_csv_export=False,
                available=True,
            ),
            ReportDescriptor(
                name="collection_quality",
                title="Collection Quality Report",
                category="Collection Health",
                description="Quality score across completeness, diversity, upgrade, and certification",
                engine_name="collection_quality",
                method_name="generate_report",
                has_markdown_export=True,
                has_csv_export=False,
                available=True,
            ),
            ReportDescriptor(
                name="collection_integrity",
                title="Collection Integrity Report",
                category="Collection Health",
                description="Integrity score, warnings, and recommendations",
                engine_name="collection_integrity",
                method_name="run",
                has_markdown_export=True,
                has_csv_export=False,
                available=True,
            ),
            ReportDescriptor(
                name="collection_snapshot",
                title="Collection Snapshot",
                category="Progress",
                description="Growth summary and series progress since last snapshot",
                engine_name="collection_snapshot",
                method_name="latest_report",
                has_markdown_export=True,
                has_csv_export=False,
                available=True,
            ),
            ReportDescriptor(
                name="home_dashboard",
                title="Collector Home Dashboard",
                category="Dashboard",
                description="Daily collector status, actions, and opportunities",
                engine_name="collector_home_dashboard",
                method_name="generate_report",
                has_markdown_export=True,
                has_csv_export=True,
                available=True,
            ),
            ReportDescriptor(
                name="health_report",
                title="Collection Health Report",
                category="Dashboard",
                description="Consolidated health report with strengths, weaknesses, and priorities",
                engine_name="collector_operating_system",
                method_name="generate_report",
                has_markdown_export=True,
                has_csv_export=False,
                available=True,
            ),
            ReportDescriptor(
                name="market_awareness",
                title="Market Awareness Report",
                category="Market",
                description="Observations, purchases, sales, and auction records",
                engine_name="market_awareness",
                method_name="generate_report",
                has_markdown_export=True,
                has_csv_export=False,
                available=True,
            ),
            ReportDescriptor(
                name="portfolio_performance",
                title="Portfolio Performance Report",
                category="Portfolio",
                description="Portfolio summary, value estimates, and performance metrics",
                engine_name="portfolio_performance",
                method_name="generate_report",
                has_markdown_export=True,
                has_csv_export=False,
                available=True,
            ),
            ReportDescriptor(
                name="opportunities",
                title="Top Opportunities Report",
                category="Shopping",
                description="Top opportunities ranked by collection impact and budget fit",
                engine_name="opportunity_engine",
                method_name="generate_report",
                has_markdown_export=True,
                has_csv_export=True,
                available=True,
            ),
            ReportDescriptor(
                name="shopping_assistant",
                title="Shopping Recommendations",
                category="Shopping",
                description="Smart shopping recommendations and best next purchase",
                engine_name="smart_shopping",
                method_name="generate_report",
                has_markdown_export=True,
                has_csv_export=True,
                available=True,
            ),
            ReportDescriptor(
                name="deal_hunter",
                title="Deal Hunter Report",
                category="Shopping",
                description="Deal analysis and recommendations for listings",
                engine_name="deal_hunter",
                method_name="generate_report",
                has_markdown_export=True,
                has_csv_export=True,
                available=True,
            ),
            ReportDescriptor(
                name="ai_grading",
                title="AI Grading Assessment",
                category="AI Assistant",
                description="Batch grading assessments and grade patterns",
                engine_name="ai_grading",
                method_name="assess_batch",
                has_markdown_export=True,
                has_csv_export=True,
                available=True,
            ),
            ReportDescriptor(
                name="photo_vault",
                title="Photo Vault Coverage",
                category="Photo",
                description="Photo coverage metrics and missing photos",
                engine_name="photo_vault",
                method_name="coverage_summary",
                has_markdown_export=True,
                has_csv_export=True,
                available=bool(self._photo_records),
            ),
            ReportDescriptor(
                name="photo_audit",
                title="Photo Vault Integrity Audit",
                category="Photo",
                description="Photo integrity audit findings and recommendations",
                engine_name="photo_vault_audit",
                method_name="run",
                has_markdown_export=True,
                has_csv_export=True,
                available=bool(self._photo_records),
            ),
            ReportDescriptor(
                name="workflow_summary",
                title="Workflow Summary",
                category="Workflow",
                description="Daily workflow summary and recommended tasks",
                engine_name="collector_workflows",
                method_name="daily_summary",
                has_markdown_export=True,
                has_csv_export=False,
                available=True,
            ),
            ReportDescriptor(
                name="watchlist_scan",
                title="Watchlist Scan Results",
                category="Alerts",
                description="Watchlist matches and alerts for collection candidates",
                engine_name="watchlist_engine",
                method_name="scan",
                has_markdown_export=True,
                has_csv_export=True,
                available=bool(self._watchlists),
            ),
        ]
