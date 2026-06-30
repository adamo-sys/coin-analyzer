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


# ---------------------------------------------------------------------------
# CollectorWorkspace
# ---------------------------------------------------------------------------

class CollectorWorkspace:
    """Unified workspace — thin aggregation layer. Zero business logic."""

    def __init__(self, collection_items: List[Any]):
        """Initialize with collection items. No collection copy. No engine instantiation yet."""
        self._collection_items = collection_items
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

            return CollectionDashboard(self._collection_items)

        elif name == "collector_home_dashboard":
            from collector_home_dashboard import CollectorHomeDashboard

            return CollectorHomeDashboard(self._collection_items)

        elif name == "collector_operating_system":
            from collector_operating_system import CollectorHome, CollectionHealthReportEngine

            return {
                "home": CollectorHome(self._collection_items),
                "health": CollectionHealthReportEngine(self._collection_items),
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

            return CollectorWorkflowEngine(self._collection_items)

        elif name == "collection_snapshot":
            from collection_snapshot import CollectionSnapshotManager

            return CollectionSnapshotManager()

        elif name == "collection_quality":
            from collection_quality import CollectionQualityEngine

            return CollectionQualityEngine(self._collection_items)

        elif name == "collection_integrity":
            from collection_integrity import CollectionIntegrityAudit

            return CollectionIntegrityAudit(self._collection_items)

        else:
            raise ValueError(f"Unknown engine: {name}")

    # -- Refresh ----------------------------------------------------------

    def refresh(self) -> None:
        """Clear all caches. Next panel query will re-query engines."""
        self._cache.clear()

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
            current = snapshot_engine.create_snapshot(self._collection_items)
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
