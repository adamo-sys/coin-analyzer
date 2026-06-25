"""
Platform Analytics Engine

Provides deterministic analytics for measuring the health, activity, completeness,
and performance of every major subsystem of the Collector Platform using local data only.

This is NOT:
- AI recommendations
- Forecasting
- Machine learning
- Cloud analytics
- External APIs

Analytics are deterministic and based solely on local platform data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class MetricType(Enum):
    """Types of analytics metrics."""
    COUNTER = "counter"
    PERCENTAGE = "percentage"
    RATIO = "ratio"
    SCORE = "score"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"


@dataclass
class AnalyticsMetric:
    """A single analytics metric."""
    name: str
    value: Any
    metric_type: MetricType
    description: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalyticsTrend:
    """A trend over time for a metric."""
    metric_name: str
    values: List[float]
    timestamps: List[datetime]
    direction: str  # "up", "down", "stable"
    change_percent: float
    description: str


@dataclass
class ModuleMetrics:
    """Metrics for a specific platform module."""
    module_name: str
    metrics: List[AnalyticsMetric] = field(default_factory=list)
    health_score: float = 0.0
    activity_level: str = "unknown"  # "active", "moderate", "inactive"
    last_activity: Optional[datetime] = None


@dataclass
class AnalyticsSnapshot:
    """A point-in-time snapshot of platform analytics."""
    timestamp: datetime = field(default_factory=datetime.now)
    collection_metrics: Optional[ModuleMetrics] = None
    portfolio_metrics: Optional[ModuleMetrics] = None
    workflow_metrics: Optional[ModuleMetrics] = None
    deal_hunter_metrics: Optional[ModuleMetrics] = None
    opportunity_metrics: Optional[ModuleMetrics] = None
    market_metrics: Optional[ModuleMetrics] = None
    watchlist_metrics: Optional[ModuleMetrics] = None
    cloud_metrics: Optional[ModuleMetrics] = None
    sync_metrics: Optional[ModuleMetrics] = None
    workspace_metrics: Optional[ModuleMetrics] = None
    device_metrics: Optional[ModuleMetrics] = None
    overall_health_score: float = 0.0


@dataclass
class AnalyticsSummary:
    """A summary of analytics across all modules."""
    total_modules: int
    active_modules: int
    healthy_modules: int
    overall_health_score: float
    top_strengths: List[str]
    top_improvements: List[str]
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class PlatformHealthScore:
    """Overall platform health score with explanations."""
    score: float  # 0-100
    category: str  # "excellent", "good", "fair", "poor"
    module_coverage: float
    backup_readiness: float
    workflow_completeness: float
    metadata_quality: float
    collection_completeness: float
    explanations: List[str]
    recommendations: List[str]
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class AnalyticsDashboard:
    """Complete analytics dashboard."""
    snapshot: AnalyticsSnapshot
    summary: AnalyticsSummary
    health_score: PlatformHealthScore
    trends: List[AnalyticsTrend]
    generated_at: datetime = field(default_factory=datetime.now)


class PlatformAnalyticsEngine:
    """
    Main analytics engine for the Collector Platform.
    
    Generates deterministic metrics for all major subsystems using local data only.
    """

    def __init__(self):
        self.snapshots: List[AnalyticsSnapshot] = []
        self.current_snapshot: Optional[AnalyticsSnapshot] = None

    def generate_snapshot(self, collection_data: Optional[Dict] = None,
                         portfolio_data: Optional[Dict] = None,
                         workflow_data: Optional[Dict] = None,
                         deal_hunter_data: Optional[Dict] = None,
                         opportunity_data: Optional[Dict] = None,
                         market_data: Optional[Dict] = None,
                         watchlist_data: Optional[Dict] = None,
                         cloud_data: Optional[Dict] = None,
                         sync_data: Optional[Dict] = None,
                         workspace_data: Optional[Dict] = None,
                         device_data: Optional[Dict] = None) -> AnalyticsSnapshot:
        """
        Generate a complete analytics snapshot.
        
        Args:
            collection_data: Collection JSON data
            portfolio_data: Portfolio data
            workflow_data: Workflow/session data
            deal_hunter_data: Deal Hunter data
            opportunity_data: Opportunity Engine data
            market_data: Market Intelligence data
            watchlist_data: Watchlist data
            cloud_data: Collector Cloud data
            sync_data: Sync & Backup data
            workspace_data: Multi-Device Workspace data
            device_data: Device Linking data
            
        Returns:
            AnalyticsSnapshot with all module metrics
        """
        snapshot = AnalyticsSnapshot()
        
        # Generate metrics for each module
        snapshot.collection_metrics = self._generate_collection_metrics(collection_data)
        snapshot.portfolio_metrics = self._generate_portfolio_metrics(portfolio_data)
        snapshot.workflow_metrics = self._generate_workflow_metrics(workflow_data)
        snapshot.deal_hunter_metrics = self._generate_deal_hunter_metrics(deal_hunter_data)
        snapshot.opportunity_metrics = self._generate_opportunity_metrics(opportunity_data)
        snapshot.market_metrics = self._generate_market_metrics(market_data)
        snapshot.watchlist_metrics = self._generate_watchlist_metrics(watchlist_data)
        snapshot.cloud_metrics = self._generate_cloud_metrics(cloud_data)
        snapshot.sync_metrics = self._generate_sync_metrics(sync_data)
        snapshot.workspace_metrics = self._generate_workspace_metrics(workspace_data)
        snapshot.device_metrics = self._generate_device_metrics(device_data)
        
        # Calculate overall health score
        snapshot.overall_health_score = self._calculate_overall_health(snapshot)
        
        self.current_snapshot = snapshot
        self.snapshots.append(snapshot)
        
        return snapshot

    def _generate_collection_metrics(self, data: Optional[Dict]) -> ModuleMetrics:
        """Generate collection metrics."""
        metrics = ModuleMetrics(module_name="Collection Intelligence")
        
        if not data:
            metrics.health_score = 0.0
            metrics.activity_level = "inactive"
            return metrics
        
        collection_items = data.get("items", [])
        
        # Core metrics
        metrics.metrics.append(AnalyticsMetric(
            name="total_items",
            value=len(collection_items),
            metric_type=MetricType.COUNTER,
            description="Total number of collection items"
        ))
        
        # Count by country
        countries = {}
        for item in collection_items:
            country = item.get("country", "Unknown")
            countries[country] = countries.get(country, 0) + 1
        
        metrics.metrics.append(AnalyticsMetric(
            name="unique_countries",
            value=len(countries),
            metric_type=MetricType.COUNTER,
            description="Number of unique countries represented"
        ))
        
        # Count by denomination
        denominations = {}
        for item in collection_items:
            denom = item.get("denomination", "Unknown")
            denominations[denom] = denominations.get(denom, 0) + 1
        
        metrics.metrics.append(AnalyticsMetric(
            name="unique_denominations",
            value=len(denominations),
            metric_type=MetricType.COUNTER,
            description="Number of unique denominations"
        ))
        
        # Grade distribution
        grades = {}
        for item in collection_items:
            grade = item.get("grade", "Ungraded")
            grades[grade] = grades.get(grade, 0) + 1
        
        metrics.metrics.append(AnalyticsMetric(
            name="graded_items",
            value=grades.get("Ungraded", 0),
            metric_type=MetricType.COUNTER,
            description="Number of ungraded items"
        ))
        
        # Calculate health score based on data quality
        has_grades = sum(1 for item in collection_items if item.get("grade") and item.get("grade") != "Ungraded")
        grade_coverage = has_grades / len(collection_items) if collection_items else 0
        
        has_years = sum(1 for item in collection_items if item.get("year"))
        year_coverage = has_years / len(collection_items) if collection_items else 0
        
        metrics.health_score = (grade_coverage * 0.5 + year_coverage * 0.5) * 100
        metrics.activity_level = "active" if len(collection_items) > 0 else "inactive"
        
        return metrics

    def _generate_portfolio_metrics(self, data: Optional[Dict]) -> ModuleMetrics:
        """Generate portfolio metrics."""
        metrics = ModuleMetrics(module_name="Portfolio Performance")
        
        if not data:
            metrics.health_score = 0.0
            metrics.activity_level = "inactive"
            return metrics
        
        # Estimated value
        total_value = data.get("total_estimated_value", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="total_estimated_value",
            value=total_value,
            metric_type=MetricType.COUNTER,
            description="Total estimated portfolio value in CAD"
        ))
        
        # Acquisition cost
        total_cost = data.get("total_acquisition_cost", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="total_acquisition_cost",
            value=total_cost,
            metric_type=MetricType.COUNTER,
            description="Total acquisition cost in CAD"
        ))
        
        # Unrealized gain/loss
        if total_value > 0 and total_cost > 0:
            gain_loss = total_value - total_cost
            gain_loss_percent = (gain_loss / total_cost) * 100
            metrics.metrics.append(AnalyticsMetric(
                name="unrealized_gain_loss_percent",
                value=gain_loss_percent,
                metric_type=MetricType.PERCENTAGE,
                description="Unrealized gain/loss as percentage of cost"
            ))
        
        # Silver exposure
        silver_value = data.get("silver_value", 0)
        if total_value > 0:
            silver_exposure = (silver_value / total_value) * 100
            metrics.metrics.append(AnalyticsMetric(
                name="silver_exposure_percent",
                value=silver_exposure,
                metric_type=MetricType.PERCENTAGE,
                description="Silver value as percentage of total portfolio"
            ))
        
        metrics.health_score = 100.0 if total_value > 0 else 0.0
        metrics.activity_level = "active" if total_value > 0 else "inactive"
        
        return metrics

    def _generate_workflow_metrics(self, data: Optional[Dict]) -> ModuleMetrics:
        """Generate workflow metrics."""
        metrics = ModuleMetrics(module_name="Workflow Integration")
        
        if not data:
            metrics.health_score = 0.0
            metrics.activity_level = "inactive"
            return metrics
        
        # Photos captured
        photos_captured = data.get("photos_captured", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="photos_captured",
            value=photos_captured,
            metric_type=MetricType.COUNTER,
            description="Total photos captured"
        ))
        
        # OCR sessions
        ocr_sessions = data.get("ocr_sessions", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="ocr_sessions",
            value=ocr_sessions,
            metric_type=MetricType.COUNTER,
            description="Total OCR sessions"
        ))
        
        # Identification success rate
        total_ocr = data.get("total_ocr_attempts", 0)
        successful_identifications = data.get("successful_identifications", 0)
        if total_ocr > 0:
            success_rate = (successful_identifications / total_ocr) * 100
            metrics.metrics.append(AnalyticsMetric(
                name="identification_success_rate",
                value=success_rate,
                metric_type=MetricType.PERCENTAGE,
                description="OCR identification success rate"
            ))
        
        # Entry completion rate
        entry_attempts = data.get("entry_attempts", 0)
        completed_entries = data.get("completed_entries", 0)
        if entry_attempts > 0:
            completion_rate = (completed_entries / entry_attempts) * 100
            metrics.metrics.append(AnalyticsMetric(
                name="entry_completion_rate",
                value=completion_rate,
                metric_type=MetricType.PERCENTAGE,
                description="Collection entry completion rate"
            ))
        
        # Workflow completion rate
        workflow_sessions = data.get("workflow_sessions", 0)
        completed_workflows = data.get("completed_workflows", 0)
        if workflow_sessions > 0:
            workflow_completion = (completed_workflows / workflow_sessions) * 100
            metrics.metrics.append(AnalyticsMetric(
                name="workflow_completion_rate",
                value=workflow_completion,
                metric_type=MetricType.PERCENTAGE,
                description="End-to-end workflow completion rate"
            ))
        
        # Calculate health score
        metrics.health_score = 100.0 if workflow_sessions > 0 else 0.0
        metrics.activity_level = "active" if workflow_sessions > 0 else "inactive"
        
        return metrics

    def _generate_deal_hunter_metrics(self, data: Optional[Dict]) -> ModuleMetrics:
        """Generate Deal Hunter metrics."""
        metrics = ModuleMetrics(module_name="Deal Hunter")
        
        if not data:
            metrics.health_score = 0.0
            metrics.activity_level = "inactive"
            return metrics
        
        # Total listings processed
        total_listings = data.get("total_listings_processed", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="total_listings_processed",
            value=total_listings,
            metric_type=MetricType.COUNTER,
            description="Total listings processed by Deal Hunter"
        ))
        
        # BUY recommendations
        buy_count = data.get("buy_recommendations", 0)
        if total_listings > 0:
            buy_rate = (buy_count / total_listings) * 100
            metrics.metrics.append(AnalyticsMetric(
                name="buy_recommendation_rate",
                value=buy_rate,
                metric_type=MetricType.PERCENTAGE,
                description="Percentage of listings with BUY recommendation"
            ))
        
        # PASS recommendations
        pass_count = data.get("pass_recommendations", 0)
        if total_listings > 0:
            pass_rate = (pass_count / total_listings) * 100
            metrics.metrics.append(AnalyticsMetric(
                name="pass_recommendation_rate",
                value=pass_rate,
                metric_type=MetricType.PERCENTAGE,
                description="Percentage of listings with PASS recommendation"
            ))
        
        # Risk flags
        risk_flags = data.get("risk_flags", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="total_risk_flags",
            value=risk_flags,
            metric_type=MetricType.COUNTER,
            description="Total risk flags raised"
        ))
        
        metrics.health_score = 100.0 if total_listings > 0 else 0.0
        metrics.activity_level = "active" if total_listings > 0 else "inactive"
        
        return metrics

    def _generate_opportunity_metrics(self, data: Optional[Dict]) -> ModuleMetrics:
        """Generate Opportunity Engine metrics."""
        metrics = ModuleMetrics(module_name="Opportunity Engine")
        
        if not data:
            metrics.health_score = 0.0
            metrics.activity_level = "inactive"
            return metrics
        
        # Opportunities generated
        total_opportunities = data.get("total_opportunities", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="total_opportunities",
            value=total_opportunities,
            metric_type=MetricType.COUNTER,
            description="Total opportunities generated"
        ))
        
        # High-priority opportunities
        high_priority = data.get("high_priority_opportunities", 0)
        if total_opportunities > 0:
            high_priority_rate = (high_priority / total_opportunities) * 100
            metrics.metrics.append(AnalyticsMetric(
                name="high_priority_rate",
                value=high_priority_rate,
                metric_type=MetricType.PERCENTAGE,
                description="Percentage of high-priority opportunities"
            ))
        
        metrics.health_score = 100.0 if total_opportunities > 0 else 0.0
        metrics.activity_level = "active" if total_opportunities > 0 else "inactive"
        
        return metrics

    def _generate_market_metrics(self, data: Optional[Dict]) -> ModuleMetrics:
        """Generate Market Intelligence metrics."""
        metrics = ModuleMetrics(module_name="Market Intelligence")
        
        if not data:
            metrics.health_score = 0.0
            metrics.activity_level = "inactive"
            return metrics
        
        # Market records
        total_records = data.get("total_market_records", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="total_market_records",
            value=total_records,
            metric_type=MetricType.COUNTER,
            description="Total market intelligence records"
        ))
        
        # Comparable sales
        comparable_sales = data.get("comparable_sales", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="comparable_sales",
            value=comparable_sales,
            metric_type=MetricType.COUNTER,
            description="Total comparable sales tracked"
        ))
        
        metrics.health_score = 100.0 if total_records > 0 else 0.0
        metrics.activity_level = "active" if total_records > 0 else "inactive"
        
        return metrics

    def _generate_watchlist_metrics(self, data: Optional[Dict]) -> ModuleMetrics:
        """Generate Watchlist metrics."""
        metrics = ModuleMetrics(module_name="Watchlists & Alerts")
        
        if not data:
            metrics.health_score = 0.0
            metrics.activity_level = "inactive"
            return metrics
        
        # Total watchlists
        total_watchlists = data.get("total_watchlists", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="total_watchlists",
            value=total_watchlists,
            metric_type=MetricType.COUNTER,
            description="Total watchlists defined"
        ))
        
        # Watchlist items
        total_items = data.get("total_watchlist_items", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="total_watchlist_items",
            value=total_items,
            metric_type=MetricType.COUNTER,
            description="Total watchlist items"
        ))
        
        # Alerts generated
        alerts_generated = data.get("alerts_generated", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="alerts_generated",
            value=alerts_generated,
            metric_type=MetricType.COUNTER,
            description="Total alerts generated"
        ))
        
        metrics.health_score = 100.0 if total_watchlists > 0 else 0.0
        metrics.activity_level = "active" if total_watchlists > 0 else "inactive"
        
        return metrics

    def _generate_cloud_metrics(self, data: Optional[Dict]) -> ModuleMetrics:
        """Generate Collector Cloud metrics."""
        metrics = ModuleMetrics(module_name="Collector Cloud")
        
        if not data:
            metrics.health_score = 0.0
            metrics.activity_level = "inactive"
            return metrics
        
        # Snapshots created
        snapshots = data.get("snapshots_created", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="snapshots_created",
            value=snapshots,
            metric_type=MetricType.COUNTER,
            description="Total cloud snapshots created"
        ))
        
        # Sync plans generated
        sync_plans = data.get("sync_plans_generated", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="sync_plans_generated",
            value=sync_plans,
            metric_type=MetricType.COUNTER,
            description="Total sync plans generated"
        ))
        
        metrics.health_score = 100.0 if snapshots > 0 else 0.0
        metrics.activity_level = "active" if snapshots > 0 else "inactive"
        
        return metrics

    def _generate_sync_metrics(self, data: Optional[Dict]) -> ModuleMetrics:
        """Generate Sync & Backup metrics."""
        metrics = ModuleMetrics(module_name="Sync & Backup")
        
        if not data:
            metrics.health_score = 0.0
            metrics.activity_level = "inactive"
            return metrics
        
        # Backup archives created
        backups = data.get("backup_archives_created", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="backup_archives_created",
            value=backups,
            metric_type=MetricType.COUNTER,
            description="Total backup archives created"
        ))
        
        # Last backup age (in hours)
        last_backup_hours = data.get("last_backup_hours_ago", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="last_backup_hours_ago",
            value=last_backup_hours,
            metric_type=MetricType.COUNTER,
            description="Hours since last backup"
        ))
        
        # Sync simulations run
        sync_sims = data.get("sync_simulations_run", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="sync_simulations_run",
            value=sync_sims,
            metric_type=MetricType.COUNTER,
            description="Total sync simulations run"
        ))
        
        # Backup readiness score
        backup_ready = data.get("backup_ready", True)
        metrics.health_score = 100.0 if backup_ready else 0.0
        metrics.activity_level = "active" if backups > 0 else "inactive"
        
        return metrics

    def _generate_workspace_metrics(self, data: Optional[Dict]) -> ModuleMetrics:
        """Generate Multi-Device Workspace metrics."""
        metrics = ModuleMetrics(module_name="Multi-Device Workspace")
        
        if not data:
            metrics.health_score = 0.0
            metrics.activity_level = "inactive"
            return metrics
        
        # Registered devices
        devices = data.get("registered_devices", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="registered_devices",
            value=devices,
            metric_type=MetricType.COUNTER,
            description="Total registered devices"
        ))
        
        # Workspace snapshots
        workspace_snapshots = data.get("workspace_snapshots", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="workspace_snapshots",
            value=workspace_snapshots,
            metric_type=MetricType.COUNTER,
            description="Total workspace snapshots"
        ))
        
        metrics.health_score = 100.0 if devices > 0 else 0.0
        metrics.activity_level = "active" if devices > 0 else "inactive"
        
        return metrics

    def _generate_device_metrics(self, data: Optional[Dict]) -> ModuleMetrics:
        """Generate Device Linking metrics."""
        metrics = ModuleMetrics(module_name="Device Linking")
        
        if not data:
            metrics.health_score = 0.0
            metrics.activity_level = "inactive"
            return metrics
        
        # Linked devices
        linked_devices = data.get("linked_devices", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="linked_devices",
            value=linked_devices,
            metric_type=MetricType.COUNTER,
            description="Total linked devices"
        ))
        
        # Unresolved conflicts
        conflicts = data.get("unresolved_conflicts", 0)
        metrics.metrics.append(AnalyticsMetric(
            name="unresolved_conflicts",
            value=conflicts,
            metric_type=MetricType.COUNTER,
            description="Total unresolved conflicts"
        ))
        
        metrics.health_score = 100.0 if linked_devices > 0 and conflicts == 0 else 50.0 if linked_devices > 0 else 0.0
        metrics.activity_level = "active" if linked_devices > 0 else "inactive"
        
        return metrics

    def _calculate_overall_health(self, snapshot: AnalyticsSnapshot) -> float:
        """Calculate overall platform health score."""
        modules = [
            snapshot.collection_metrics,
            snapshot.portfolio_metrics,
            snapshot.workflow_metrics,
            snapshot.deal_hunter_metrics,
            snapshot.opportunity_metrics,
            snapshot.market_metrics,
            snapshot.watchlist_metrics,
            snapshot.cloud_metrics,
            snapshot.sync_metrics,
            snapshot.workspace_metrics,
            snapshot.device_metrics
        ]
        
        valid_scores = [m.health_score for m in modules if m and m.health_score > 0]
        
        if not valid_scores:
            return 0.0
        
        return sum(valid_scores) / len(valid_scores)

    def generate_summary(self, snapshot: AnalyticsSnapshot) -> AnalyticsSummary:
        """Generate analytics summary from snapshot."""
        modules = [
            snapshot.collection_metrics,
            snapshot.portfolio_metrics,
            snapshot.workflow_metrics,
            snapshot.deal_hunter_metrics,
            snapshot.opportunity_metrics,
            snapshot.market_metrics,
            snapshot.watchlist_metrics,
            snapshot.cloud_metrics,
            snapshot.sync_metrics,
            snapshot.workspace_metrics,
            snapshot.device_metrics
        ]
        
        total_modules = len([m for m in modules if m])
        active_modules = len([m for m in modules if m and m.activity_level == "active"])
        healthy_modules = len([m for m in modules if m and m.health_score >= 80])
        
        overall_health = snapshot.overall_health_score
        
        # Generate strengths and improvements
        strengths = []
        improvements = []
        
        for module in modules:
            if module and module.health_score >= 80:
                strengths.append(f"{module.module_name}: {module.health_score:.1f}%")
            elif module and module.health_score < 50:
                improvements.append(f"{module.module_name}: {module.health_score:.1f}%")
        
        return AnalyticsSummary(
            total_modules=total_modules,
            active_modules=active_modules,
            healthy_modules=healthy_modules,
            overall_health_score=overall_health,
            top_strengths=strengths[:5],
            top_improvements=improvements[:5]
        )

    def calculate_health_score(self, snapshot: AnalyticsSnapshot) -> PlatformHealthScore:
        """Calculate comprehensive platform health score."""
        # Module coverage
        modules = [
            snapshot.collection_metrics,
            snapshot.portfolio_metrics,
            snapshot.workflow_metrics,
            snapshot.deal_hunter_metrics,
            snapshot.opportunity_metrics,
            snapshot.market_metrics,
            snapshot.watchlist_metrics,
            snapshot.cloud_metrics,
            snapshot.sync_metrics,
            snapshot.workspace_metrics,
            snapshot.device_metrics
        ]
        
        module_coverage = len([m for m in modules if m and m.activity_level == "active"]) / len(modules) * 100
        
        # Backup readiness
        backup_readiness = snapshot.sync_metrics.health_score if snapshot.sync_metrics else 0.0
        
        # Workflow completeness
        workflow_completeness = snapshot.workflow_metrics.health_score if snapshot.workflow_metrics else 0.0
        
        # Metadata quality (based on collection grades and years)
        metadata_quality = snapshot.collection_metrics.health_score if snapshot.collection_metrics else 0.0
        
        # Collection completeness (based on activity)
        collection_completeness = snapshot.collection_metrics.health_score if snapshot.collection_metrics else 0.0
        
        # Overall score (weighted average)
        overall_score = (
            module_coverage * 0.2 +
            backup_readiness * 0.25 +
            workflow_completeness * 0.15 +
            metadata_quality * 0.2 +
            collection_completeness * 0.2
        )
        
        # Category
        if overall_score >= 90:
            category = "excellent"
        elif overall_score >= 70:
            category = "good"
        elif overall_score >= 50:
            category = "fair"
        else:
            category = "poor"
        
        # Explanations
        explanations = []
        if module_coverage < 50:
            explanations.append("Low module coverage - many subsystems inactive")
        if backup_readiness < 50:
            explanations.append("Backup readiness needs attention")
        if workflow_completeness < 50:
            explanations.append("Workflow completion rate is low")
        if metadata_quality < 50:
            explanations.append("Collection metadata quality needs improvement")
        if overall_score >= 80:
            explanations.append("Platform is operating well across most subsystems")
        
        # Recommendations
        recommendations = []
        if backup_readiness < 80:
            recommendations.append("Create regular backup archives")
        if metadata_quality < 80:
            recommendations.append("Add grades and years to collection items")
        if workflow_completeness < 80:
            recommendations.append("Complete workflow sessions to improve metrics")
        if module_coverage < 80:
            recommendations.append("Activate additional platform modules")
        
        return PlatformHealthScore(
            score=overall_score,
            category=category,
            module_coverage=module_coverage,
            backup_readiness=backup_readiness,
            workflow_completeness=workflow_completeness,
            metadata_quality=metadata_quality,
            collection_completeness=collection_completeness,
            explanations=explanations,
            recommendations=recommendations
        )

    def generate_dashboard(self, snapshot: AnalyticsSnapshot) -> AnalyticsDashboard:
        """Generate complete analytics dashboard."""
        summary = self.generate_summary(snapshot)
        health_score = self.calculate_health_score(snapshot)
        trends = self._generate_trends(snapshot)
        
        return AnalyticsDashboard(
            snapshot=snapshot,
            summary=summary,
            health_score=health_score,
            trends=trends
        )

    def _generate_trends(self, snapshot: AnalyticsSnapshot) -> List[AnalyticsTrend]:
        """Generate trend data for key metrics."""
        trends = []
        
        if len(self.snapshots) < 2:
            return trends
        
        previous_snapshot = self.snapshots[-2]
        
        # Collection growth trend
        if snapshot.collection_metrics and previous_snapshot.collection_metrics:
            current_items = next((m.value for m in snapshot.collection_metrics.metrics if m.name == "total_items"), 0)
            previous_items = next((m.value for m in previous_snapshot.collection_metrics.metrics if m.name == "total_items"), 0)
            
            if previous_items > 0:
                change_percent = ((current_items - previous_items) / previous_items) * 100
                direction = "up" if change_percent > 0 else "down" if change_percent < 0 else "stable"
                
                trends.append(AnalyticsTrend(
                    metric_name="total_items",
                    values=[previous_items, current_items],
                    timestamps=[previous_snapshot.timestamp, snapshot.timestamp],
                    direction=direction,
                    change_percent=change_percent,
                    description=f"Collection size changed by {change_percent:.1f}%"
                ))
        
        # Health score trend
        change_percent = snapshot.overall_health_score - previous_snapshot.overall_health_score
        direction = "up" if change_percent > 0 else "down" if change_percent < 0 else "stable"
        
        trends.append(AnalyticsTrend(
            metric_name="overall_health_score",
            values=[previous_snapshot.overall_health_score, snapshot.overall_health_score],
            timestamps=[previous_snapshot.timestamp, snapshot.timestamp],
            direction=direction,
            change_percent=change_percent,
            description=f"Overall health score changed by {change_percent:.1f}%"
        ))
        
        return trends

    def export_snapshot_markdown(self, snapshot: AnalyticsSnapshot) -> str:
        """Export analytics snapshot as Markdown."""
        lines = []
        lines.append("# Platform Analytics Snapshot")
        lines.append(f"\nGenerated: {snapshot.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"\nOverall Health Score: {snapshot.overall_health_score:.1f}%")
        lines.append("\n---\n")
        
        for module_metrics in [
            snapshot.collection_metrics,
            snapshot.portfolio_metrics,
            snapshot.workflow_metrics,
            snapshot.deal_hunter_metrics,
            snapshot.opportunity_metrics,
            snapshot.market_metrics,
            snapshot.watchlist_metrics,
            snapshot.cloud_metrics,
            snapshot.sync_metrics,
            snapshot.workspace_metrics,
            snapshot.device_metrics
        ]:
            if module_metrics:
                lines.append(f"\n## {module_metrics.module_name}")
                lines.append(f"\nHealth Score: {module_metrics.health_score:.1f}%")
                lines.append(f"Activity Level: {module_metrics.activity_level}")
                lines.append("\n### Metrics")
                lines.append("\n| Metric | Value | Type | Description |")
                lines.append("| --- | --- | --- | --- |")
                
                for metric in module_metrics.metrics:
                    lines.append(f"| {metric.name} | {metric.value} | {metric.metric_type.value} | {metric.description} |")
        
        return "\n".join(lines)

    def export_snapshot_csv(self, snapshot: AnalyticsSnapshot) -> str:
        """Export analytics snapshot as CSV."""
        lines = []
        lines.append("Module,Metric,Value,Type,Description,Timestamp")
        
        for module_metrics in [
            snapshot.collection_metrics,
            snapshot.portfolio_metrics,
            snapshot.workflow_metrics,
            snapshot.deal_hunter_metrics,
            snapshot.opportunity_metrics,
            snapshot.market_metrics,
            snapshot.watchlist_metrics,
            snapshot.cloud_metrics,
            snapshot.sync_metrics,
            snapshot.workspace_metrics,
            snapshot.device_metrics
        ]:
            if module_metrics:
                for metric in module_metrics.metrics:
                    lines.append(f"{module_metrics.module_name},{metric.name},{metric.value},{metric.metric_type.value},{metric.description},{metric.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(lines)

    def export_health_score_markdown(self, health_score: PlatformHealthScore) -> str:
        """Export health score as Markdown."""
        lines = []
        lines.append("# Platform Health Score")
        lines.append(f"\nGenerated: {health_score.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"\nOverall Score: {health_score.score:.1f}%")
        lines.append(f"Category: {health_score.category.upper()}")
        lines.append("\n---\n")
        lines.append("## Component Scores")
        lines.append(f"\n- Module Coverage: {health_score.module_coverage:.1f}%")
        lines.append(f"- Backup Readiness: {health_score.backup_readiness:.1f}%")
        lines.append(f"- Workflow Completeness: {health_score.workflow_completeness:.1f}%")
        lines.append(f"- Metadata Quality: {health_score.metadata_quality:.1f}%")
        lines.append(f"- Collection Completeness: {health_score.collection_completeness:.1f}%")
        lines.append("\n## Explanations")
        lines.append("")
        for explanation in health_score.explanations:
            lines.append(f"- {explanation}")
        lines.append("\n## Recommendations")
        lines.append("")
        for recommendation in health_score.recommendations:
            lines.append(f"- {recommendation}")
        
        return "\n".join(lines)

    def export_health_score_csv(self, health_score: PlatformHealthScore) -> str:
        """Export health score as CSV."""
        lines = []
        lines.append("Component,Score")
        lines.append(f"Overall,{health_score.score:.1f}")
        lines.append(f"Module Coverage,{health_score.module_coverage:.1f}")
        lines.append(f"Backup Readiness,{health_score.backup_readiness:.1f}")
        lines.append(f"Workflow Completeness,{health_score.workflow_completeness:.1f}")
        lines.append(f"Metadata Quality,{health_score.metadata_quality:.1f}")
        lines.append(f"Collection Completeness,{health_score.collection_completeness:.1f}")
        
        return "\n".join(lines)
