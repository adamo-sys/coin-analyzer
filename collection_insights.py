"""
Collection Insights Engine

Transforms deterministic platform analytics into explainable, evidence-based observations
about the collection, portfolio, workflow, and acquisition strategy.

This is NOT AI reasoning, forecasting, machine learning, or external APIs.
All insights are deterministic, explainable, reproducible, and derived only from local collection data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional


class InsightCategory(Enum):
    """Categories of insights."""
    COLLECTION = "collection"
    PORTFOLIO = "portfolio"
    ACQUISITION = "acquisition"
    WORKFLOW = "workflow"
    HEALTH = "health"


class InsightPriority(Enum):
    """Priority levels for insights."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


@dataclass
class InsightEvidence:
    """Supporting evidence for an insight."""
    metric_name: str
    metric_value: Any
    description: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CollectionInsight:
    """A single insight about the collection."""
    id: str
    category: InsightCategory
    priority: InsightPriority
    title: str
    description: str
    explanation: str
    evidence: List[InsightEvidence]
    affected_modules: List[str]
    confidence: float  # Based on data completeness, not AI certainty
    timestamp: datetime = field(default_factory=datetime.now)
    actionable: bool = True


@dataclass
class CollectorHealthReport:
    """Health report for the collector's collection and workflow."""
    overall_score: float
    metadata_completeness: float
    photo_coverage: float
    ocr_coverage: float
    grading_completeness: float
    collection_documentation: float
    workflow_completion: float
    improvement_suggestions: List[str]
    strengths: List[str]
    weaknesses: List[str]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CollectionInsightReport:
    """Complete collection insights report."""
    insights: List[CollectionInsight]
    health_report: CollectorHealthReport
    collection_insights: List[CollectionInsight]
    portfolio_insights: List[CollectionInsight]
    acquisition_insights: List[CollectionInsight]
    workflow_insights: List[CollectionInsight]
    top_priorities: List[CollectionInsight]
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class InsightsDashboard:
    """Dashboard for collection insights."""
    report: CollectionInsightReport
    summary: str
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    informational_count: int
    category_breakdown: Dict[str, int]
    timestamp: datetime = field(default_factory=datetime.now)


class CollectionInsightsEngine:
    """Engine for generating deterministic collection insights from local data."""

    def __init__(self):
        self.insights_history: List[CollectionInsightReport] = []

    def generate_insights(
        self,
        collection_data: Optional[Dict[str, Any]] = None,
        portfolio_data: Optional[Dict[str, Any]] = None,
        workflow_data: Optional[Dict[str, Any]] = None,
        watchlist_data: Optional[Dict[str, Any]] = None,
        market_data: Optional[Dict[str, Any]] = None
    ) -> CollectionInsightReport:
        """Generate complete collection insights report."""
        insights = []
        
        # Generate collection insights
        collection_insights = self._generate_collection_insights(collection_data or {})
        insights.extend(collection_insights)
        
        # Generate portfolio insights
        portfolio_insights = self._generate_portfolio_insights(portfolio_data or {})
        insights.extend(portfolio_insights)
        
        # Generate acquisition insights
        acquisition_insights = self._generate_acquisition_insights(
            collection_data or {}, watchlist_data or {}
        )
        insights.extend(acquisition_insights)
        
        # Generate workflow insights
        workflow_insights = self._generate_workflow_insights(workflow_data or {})
        insights.extend(workflow_insights)
        
        # Generate health report
        health_report = self._generate_health_report(
            collection_data or {}, workflow_data or {}
        )
        
        # Prioritize insights
        top_priorities = self._prioritize_insights(insights)
        
        report = CollectionInsightReport(
            insights=insights,
            health_report=health_report,
            collection_insights=collection_insights,
            portfolio_insights=portfolio_insights,
            acquisition_insights=acquisition_insights,
            workflow_insights=workflow_insights,
            top_priorities=top_priorities
        )
        
        self.insights_history.append(report)
        return report

    def _generate_collection_insights(self, collection_data: Dict[str, Any]) -> List[CollectionInsight]:
        """Generate insights about collection growth and composition."""
        insights = []
        items = collection_data.get("items", [])
        
        if not items:
            insights.append(CollectionInsight(
                id="collection_empty",
                category=InsightCategory.COLLECTION,
                priority=InsightPriority.HIGH,
                title="Collection is empty",
                description="No items found in collection",
                explanation="Start by adding items to begin tracking collection insights",
                evidence=[],
                affected_modules=["Collection Intelligence"],
                confidence=1.0
            ))
            return insights
        
        # Collection growth insight
        total_items = len(items)
        insights.append(CollectionInsight(
            id="collection_size",
            category=InsightCategory.COLLECTION,
            priority=InsightPriority.INFORMATIONAL,
            title=f"Collection size: {total_items} items",
            description=f"Current collection contains {total_items} items",
            explanation="Collection size provides baseline for growth tracking",
            evidence=[InsightEvidence(
                metric_name="total_items",
                metric_value=total_items,
                description="Total number of items in collection"
            )],
            affected_modules=["Collection Intelligence"],
            confidence=1.0
        ))
        
        # Missing denominations insight
        countries = set(item.get("country") for item in items if item.get("country"))
        denominations = set(item.get("denomination") for item in items if item.get("denomination"))
        
        if len(countries) > 0 and len(denominations) > 0:
            insights.append(CollectionInsight(
                id="diversity",
                category=InsightCategory.COLLECTION,
                priority=InsightPriority.INFORMATIONAL,
                title=f"Collection spans {len(countries)} countries, {len(denominations)} denominations",
                description="Collection diversity across countries and denominations",
                explanation="Diversity indicates collection breadth and collecting scope",
                evidence=[
                    InsightEvidence("countries", len(countries), "Unique countries"),
                    InsightEvidence("denominations", len(denominations), "Unique denominations")
                ],
                affected_modules=["Collection Intelligence"],
                confidence=1.0
            ))
        
        # Grade coverage insight
        graded_items = [item for item in items if item.get("grade") and item.get("grade") != "Ungraded"]
        grade_coverage = len(graded_items) / total_items if total_items > 0 else 0.0
        
        if grade_coverage < 0.5:
            insights.append(CollectionInsight(
                id="low_grade_coverage",
                category=InsightCategory.COLLECTION,
                priority=InsightPriority.MEDIUM,
                title=f"Low grade coverage: {grade_coverage:.1%}",
                description=f"Only {grade_coverage:.1%} of items have grades assigned",
                explanation="Grading improves collection documentation and value tracking",
                evidence=[InsightEvidence(
                    metric_name="grade_coverage",
                    metric_value=grade_coverage,
                    description="Percentage of graded items"
                )],
                affected_modules=["Collection Intelligence"],
                confidence=1.0,
                actionable=True
            ))
        
        # Year coverage insight
        years = [item.get("year") for item in items if item.get("year")]
        if years:
            year_range = max(years) - min(years) + 1
            insights.append(CollectionInsight(
                id="year_span",
                category=InsightCategory.COLLECTION,
                priority=InsightPriority.INFORMATIONAL,
                title=f"Collection spans {year_range} years",
                description=f"Year range from {min(years)} to {max(years)}",
                explanation="Year span indicates collection temporal coverage",
                evidence=[
                    InsightEvidence("min_year", min(years), "Earliest year"),
                    InsightEvidence("max_year", max(years), "Latest year"),
                    InsightEvidence("year_span", year_range, "Total years covered")
                ],
                affected_modules=["Collection Intelligence"],
                confidence=1.0
            ))
        
        return insights

    def _generate_portfolio_insights(self, portfolio_data: Dict[str, Any]) -> List[CollectionInsight]:
        """Generate insights about portfolio composition and performance."""
        insights = []
        
        total_value = portfolio_data.get("total_estimated_value", 0)
        total_cost = portfolio_data.get("total_acquisition_cost", 0)
        
        if total_value > 0:
            # Portfolio value insight
            insights.append(CollectionInsight(
                id="portfolio_value",
                category=InsightCategory.PORTFOLIO,
                priority=InsightPriority.INFORMATIONAL,
                title=f"Portfolio value: ${total_value:,.2f}",
                description="Total estimated collection value",
                explanation="Portfolio value represents current estimated market value",
                evidence=[InsightEvidence(
                    metric_name="total_value",
                    metric_value=total_value,
                    description="Total estimated value in CAD"
                )],
                affected_modules=["Portfolio Performance"],
                confidence=0.8 if total_cost > 0 else 0.5
            ))
            
            # Unrealized gain/loss insight
            if total_cost > 0:
                gain_loss = total_value - total_cost
                gain_loss_pct = (gain_loss / total_cost) * 100
                
                priority = InsightPriority.INFORMATIONAL
                if gain_loss_pct < -20:
                    priority = InsightPriority.HIGH
                elif gain_loss_pct < -10:
                    priority = InsightPriority.MEDIUM
                
                insights.append(CollectionInsight(
                    id="unrealized_gain_loss",
                    category=InsightCategory.PORTFOLIO,
                    priority=priority,
                    title=f"Unrealized gain/loss: {gain_loss_pct:+.1f}%",
                    description=f"Portfolio is {'up' if gain_loss >= 0 else 'down'} {abs(gain_loss_pct):.1f}% from acquisition cost",
                    explanation="Unrealized gain/loss tracks portfolio performance over time",
                    evidence=[
                        InsightEvidence("total_value", total_value, "Current value"),
                        InsightEvidence("total_cost", total_cost, "Acquisition cost"),
                        InsightEvidence("gain_loss", gain_loss, "Absolute gain/loss"),
                        InsightEvidence("gain_loss_pct", gain_loss_pct, "Percentage gain/loss")
                    ],
                    affected_modules=["Portfolio Performance"],
                    confidence=0.8
                ))
            
            # Silver exposure insight
            silver_value = portfolio_data.get("silver_value", 0)
            if silver_value > 0:
                silver_exposure = (silver_value / total_value) * 100
                insights.append(CollectionInsight(
                    id="silver_exposure",
                    category=InsightCategory.PORTFOLIO,
                    priority=InsightPriority.INFORMATIONAL,
                    title=f"Silver exposure: {silver_exposure:.1f}%",
                    description=f"Silver content represents {silver_exposure:.1f}% of portfolio value",
                    explanation="Silver exposure indicates precious metal concentration",
                    evidence=[
                        InsightEvidence("silver_value", silver_value, "Silver value"),
                        InsightEvidence("total_value", total_value, "Total value"),
                        InsightEvidence("silver_exposure", silver_exposure, "Silver percentage")
                    ],
                    affected_modules=["Portfolio Performance"],
                    confidence=0.8
                ))
        
        return insights

    def _generate_acquisition_insights(
        self, collection_data: Dict[str, Any], watchlist_data: Dict[str, Any]
    ) -> List[CollectionInsight]:
        """Generate insights about acquisition patterns and opportunities."""
        insights = []
        items = collection_data.get("items", [])
        watchlists = watchlist_data.get("watchlists", [])
        
        if not items:
            return insights
        
        # Watchlist progress insight
        if watchlists:
            total_watchlist_items = sum(len(w.get("items", [])) for w in watchlists)
            if total_watchlist_items > 0:
                insights.append(CollectionInsight(
                    id="watchlist_progress",
                    category=InsightCategory.ACQUISITION,
                    priority=InsightPriority.MEDIUM,
                    title=f"Watchlist contains {total_watchlist_items} target items",
                    description="Active watchlist defines acquisition priorities",
                    explanation="Watchlist items represent targeted acquisitions",
                    evidence=[InsightEvidence(
                        metric_name="watchlist_items",
                        metric_value=total_watchlist_items,
                        description="Total watchlist items"
                    )],
                    affected_modules=["Watchlists", "Opportunity Engine"],
                    confidence=1.0,
                    actionable=True
                ))
        
        # Duplicate concentration insight
        from collections import Counter
        denominations = [item.get("denomination") for item in items if item.get("denomination")]
        if denominations:
            denom_counts = Counter(denominations)
            max_denom, max_count = denom_counts.most_common(1)[0]
            
            if max_count > len(items) * 0.3:
                insights.append(CollectionInsight(
                    id="duplicate_concentration",
                    category=InsightCategory.ACQUISITION,
                    priority=InsightPriority.MEDIUM,
                    title=f"High concentration in {max_denom}: {max_count} items",
                    description=f"{max_denom} represents {max_count/len(items):.1%} of collection",
                    explanation="High concentration may indicate over-representation",
                    evidence=[
                        InsightEvidence("denomination", max_denom, "Most common denomination"),
                        InsightEvidence("count", max_count, "Item count"),
                        InsightEvidence("percentage", max_count/len(items), "Percentage of collection")
                    ],
                    affected_modules=["Collection Intelligence"],
                    confidence=1.0,
                    actionable=True
                ))
        
        return insights

    def _generate_workflow_insights(self, workflow_data: Dict[str, Any]) -> List[CollectionInsight]:
        """Generate insights about workflow completion and efficiency."""
        insights = []
        
        photos_captured = workflow_data.get("photos_captured", 0)
        ocr_sessions = workflow_data.get("ocr_sessions", 0)
        completed_workflows = workflow_data.get("completed_workflows", 0)
        workflow_sessions = workflow_data.get("workflow_sessions", 0)
        
        # Workflow completion rate
        if workflow_sessions > 0:
            completion_rate = completed_workflows / workflow_sessions
            insights.append(CollectionInsight(
                id="workflow_completion_rate",
                category=InsightCategory.WORKFLOW,
                priority=InsightPriority.INFORMATIONAL if completion_rate > 0.5 else InsightPriority.MEDIUM,
                title=f"Workflow completion rate: {completion_rate:.1%}",
                description=f"{completed_workflows} of {workflow_sessions} workflows completed",
                explanation="Workflow completion rate indicates process efficiency",
                evidence=[
                    InsightEvidence("completed_workflows", completed_workflows, "Completed workflows"),
                    InsightEvidence("workflow_sessions", workflow_sessions, "Total sessions"),
                    InsightEvidence("completion_rate", completion_rate, "Completion rate")
                ],
                affected_modules=["Workflow Integration"],
                confidence=1.0
            ))
        
        # Photo coverage insight
        if photos_captured > 0:
            insights.append(CollectionInsight(
                id="photo_coverage",
                category=InsightCategory.WORKFLOW,
                priority=InsightPriority.INFORMATIONAL,
                title=f"Photos captured: {photos_captured}",
                description="Photo documentation progress",
                explanation="Photos improve documentation and identification accuracy",
                evidence=[InsightEvidence(
                    metric_name="photos_captured",
                    metric_value=photos_captured,
                    description="Total photos captured"
                )],
                affected_modules=["Photo Vault", "Phone Photo Capture"],
                confidence=1.0
            ))
        
        # OCR utilization insight
        if ocr_sessions > 0:
            insights.append(CollectionInsight(
                id="ocr_utilization",
                category=InsightCategory.WORKFLOW,
                priority=InsightPriority.INFORMATIONAL,
                title=f"OCR sessions: {ocr_sessions}",
                description="OCR-assisted identification usage",
                explanation="OCR sessions indicate adoption of identification assistance",
                evidence=[InsightEvidence(
                    metric_name="ocr_sessions",
                    metric_value=ocr_sessions,
                    description="Total OCR sessions"
                )],
                affected_modules=["OCR-Assisted Identification"],
                confidence=1.0
            ))
        
        return insights

    def _generate_health_report(
        self, collection_data: Dict[str, Any], workflow_data: Dict[str, Any]
    ) -> CollectorHealthReport:
        """Generate comprehensive collector health report."""
        items = collection_data.get("items", [])
        
        # Metadata completeness
        metadata_completeness = 0.0
        if items:
            complete_items = 0
            for item in items:
                required_fields = ["country", "denomination", "year"]
                if all(item.get(f) for f in required_fields):
                    complete_items += 1
            metadata_completeness = complete_items / len(items)
        
        # Photo coverage
        photo_coverage = 0.0
        if items:
            items_with_photos = sum(1 for item in items if item.get("has_photo"))
            photo_coverage = items_with_photos / len(items)
        
        # OCR coverage
        ocr_coverage = 0.0
        if items:
            items_with_ocr = sum(1 for item in items if item.get("ocr_processed"))
            ocr_coverage = items_with_ocr / len(items)
        
        # Grading completeness
        grading_completeness = 0.0
        if items:
            graded_items = sum(1 for item in items if item.get("grade") and item.get("grade") != "Ungraded")
            grading_completeness = graded_items / len(items)
        
        # Collection documentation (average of metadata, photo, OCR, grading)
        collection_documentation = (
            metadata_completeness + photo_coverage + ocr_coverage + grading_completeness
        ) / 4
        
        # Workflow completion
        workflow_completion = 0.0
        workflow_sessions = workflow_data.get("workflow_sessions", 0)
        completed_workflows = workflow_data.get("completed_workflows", 0)
        if workflow_sessions > 0:
            workflow_completion = completed_workflows / workflow_sessions
        
        # Overall score
        overall_score = (
            metadata_completeness * 0.3 +
            photo_coverage * 0.2 +
            ocr_coverage * 0.1 +
            grading_completeness * 0.2 +
            collection_documentation * 0.1 +
            workflow_completion * 0.1
        )
        
        # Generate suggestions
        improvement_suggestions = []
        if metadata_completeness < 0.8:
            improvement_suggestions.append("Improve metadata completeness by filling in missing country, denomination, and year fields")
        if photo_coverage < 0.5:
            improvement_suggestions.append("Increase photo coverage by capturing photos for collection items")
        if grading_completeness < 0.5:
            improvement_suggestions.append("Add grades to more items to improve collection documentation")
        if workflow_completion < 0.7:
            improvement_suggestions.append("Focus on completing workflows to improve process efficiency")
        
        # Generate strengths
        strengths = []
        if metadata_completeness >= 0.9:
            strengths.append("Excellent metadata completeness")
        if photo_coverage >= 0.8:
            strengths.append("Strong photo documentation")
        if grading_completeness >= 0.8:
            strengths.append("Good grading coverage")
        if workflow_completion >= 0.8:
            strengths.append("High workflow completion rate")
        
        # Generate weaknesses
        weaknesses = []
        if metadata_completeness < 0.6:
            weaknesses.append("Low metadata completeness")
        if photo_coverage < 0.4:
            weaknesses.append("Limited photo coverage")
        if grading_completeness < 0.4:
            weaknesses.append("Poor grading coverage")
        if workflow_completion < 0.5:
            weaknesses.append("Low workflow completion rate")
        
        return CollectorHealthReport(
            overall_score=overall_score,
            metadata_completeness=metadata_completeness,
            photo_coverage=photo_coverage,
            ocr_coverage=ocr_coverage,
            grading_completeness=grading_completeness,
            collection_documentation=collection_documentation,
            workflow_completion=workflow_completion,
            improvement_suggestions=improvement_suggestions,
            strengths=strengths,
            weaknesses=weaknesses
        )

    def _prioritize_insights(self, insights: List[CollectionInsight]) -> List[CollectionInsight]:
        """Prioritize insights by priority and confidence."""
        priority_order = {
            InsightPriority.CRITICAL: 0,
            InsightPriority.HIGH: 1,
            InsightPriority.MEDIUM: 2,
            InsightPriority.LOW: 3,
            InsightPriority.INFORMATIONAL: 4
        }
        
        return sorted(
            insights,
            key=lambda i: (priority_order.get(i.priority, 5), -i.confidence)
        )[:10]  # Top 10 priorities

    def generate_dashboard(self, report: CollectionInsightReport) -> InsightsDashboard:
        """Generate insights dashboard from report."""
        # Count by priority
        critical_count = sum(1 for i in report.insights if i.priority == InsightPriority.CRITICAL)
        high_count = sum(1 for i in report.insights if i.priority == InsightPriority.HIGH)
        medium_count = sum(1 for i in report.insights if i.priority == InsightPriority.MEDIUM)
        low_count = sum(1 for i in report.insights if i.priority == InsightPriority.LOW)
        informational_count = sum(1 for i in report.insights if i.priority == InsightPriority.INFORMATIONAL)
        
        # Category breakdown
        category_breakdown = {}
        for insight in report.insights:
            category = insight.category.value
            category_breakdown[category] = category_breakdown.get(category, 0) + 1
        
        # Summary
        summary_parts = []
        if critical_count > 0:
            summary_parts.append(f"{critical_count} critical")
        if high_count > 0:
            summary_parts.append(f"{high_count} high priority")
        summary_parts.append(f"{len(report.insights)} total insights")
        summary_parts.append(f"Health score: {report.health_report.overall_score:.1%}")
        summary = ", ".join(summary_parts)
        
        return InsightsDashboard(
            report=report,
            summary=summary,
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            informational_count=informational_count,
            category_breakdown=category_breakdown
        )

    def export_report_markdown(self, report: CollectionInsightReport) -> str:
        """Export insights report as Markdown."""
        lines = [
            "# Collection Insights Report",
            "",
            f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Collector Health Report",
            "",
            f"**Overall Score:** {report.health_report.overall_score:.1%}",
            "",
            "### Health Components",
            "",
            f"- Metadata Completeness: {report.health_report.metadata_completeness:.1%}",
            f"- Photo Coverage: {report.health_report.photo_coverage:.1%}",
            f"- OCR Coverage: {report.health_report.ocr_coverage:.1%}",
            f"- Grading Completeness: {report.health_report.grading_completeness:.1%}",
            f"- Collection Documentation: {report.health_report.collection_documentation:.1%}",
            f"- Workflow Completion: {report.health_report.workflow_completion:.1%}",
            ""
        ]
        
        if report.health_report.strengths:
            lines.extend([
                "### Strengths",
                ""
            ])
            for strength in report.health_report.strengths:
                lines.append(f"- {strength}")
            lines.append("")
        
        if report.health_report.weaknesses:
            lines.extend([
                "### Weaknesses",
                ""
            ])
            for weakness in report.health_report.weaknesses:
                lines.append(f"- {weakness}")
            lines.append("")
        
        if report.health_report.improvement_suggestions:
            lines.extend([
                "### Improvement Suggestions",
                ""
            ])
            for suggestion in report.health_report.improvement_suggestions:
                lines.append(f"- {suggestion}")
            lines.append("")
        
        lines.extend([
            "## Top Priorities",
            ""
        ])
        
        for insight in report.top_priorities:
            lines.extend([
                f"### {insight.title}",
                "",
                f"**Priority:** {insight.priority.value}",
                f"**Category:** {insight.category.value}",
                f"**Confidence:** {insight.confidence:.1%}",
                "",
                insight.description,
                "",
                insight.explanation,
                ""
            ])
            
            if insight.evidence:
                lines.append("**Evidence:**")
                for evidence in insight.evidence:
                    lines.append(f"- {evidence.metric_name}: {evidence.metric_value} - {evidence.description}")
                lines.append("")
        
        lines.extend([
            "## All Insights",
            ""
        ])
        
        for insight in report.insights:
            lines.extend([
                f"### {insight.title}",
                "",
                f"**Priority:** {insight.priority.value}",
                f"**Category:** {insight.category.value}",
                f"**Confidence:** {insight.confidence:.1%}",
                "",
                insight.description,
                "",
                insight.explanation,
                ""
            ])
        
        return "\n".join(lines)

    def export_report_csv(self, report: CollectionInsightReport) -> str:
        """Export insights report as CSV."""
        lines = [
            "ID,Title,Category,Priority,Confidence,Description,Explanation,Affected Modules"
        ]
        
        for insight in report.insights:
            affected = ";".join(insight.affected_modules)
            lines.append(f'"{insight.id}","{insight.title}","{insight.category.value}","{insight.priority.value}",{insight.confidence:.2f},"{insight.description}","{insight.explanation}","{affected}"')
        
        return "\n".join(lines)

    def export_health_markdown(self, health_report: CollectorHealthReport) -> str:
        """Export health report as Markdown."""
        lines = [
            "# Collector Health Report",
            "",
            f"Generated: {health_report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Overall Score",
            "",
            f"**{health_report.overall_score:.1%}**",
            "",
            "## Health Components",
            "",
            f"- Metadata Completeness: {health_report.metadata_completeness:.1%}",
            f"- Photo Coverage: {health_report.photo_coverage:.1%}",
            f"- OCR Coverage: {health_report.ocr_coverage:.1%}",
            f"- Grading Completeness: {health_report.grading_completeness:.1%}",
            f"- Collection Documentation: {health_report.collection_documentation:.1%}",
            f"- Workflow Completion: {health_report.workflow_completion:.1%}",
            ""
        ]
        
        if health_report.strengths:
            lines.extend([
                "## Strengths",
                ""
            ])
            for strength in health_report.strengths:
                lines.append(f"- {strength}")
            lines.append("")
        
        if health_report.weaknesses:
            lines.extend([
                "## Weaknesses",
                ""
            ])
            for weakness in health_report.weaknesses:
                lines.append(f"- {weakness}")
            lines.append("")
        
        if health_report.improvement_suggestions:
            lines.extend([
                "## Improvement Suggestions",
                ""
            ])
            for suggestion in health_report.improvement_suggestions:
                lines.append(f"- {suggestion}")
            lines.append("")
        
        return "\n".join(lines)

    def export_health_csv(self, health_report: CollectorHealthReport) -> str:
        """Export health report as CSV."""
        lines = [
            "Component,Score",
            f"Overall Score,{health_report.overall_score:.2f}",
            f"Metadata Completeness,{health_report.metadata_completeness:.2f}",
            f"Photo Coverage,{health_report.photo_coverage:.2f}",
            f"OCR Coverage,{health_report.ocr_coverage:.2f}",
            f"Grading Completeness,{health_report.grading_completeness:.2f}",
            f"Collection Documentation,{health_report.collection_documentation:.2f}",
            f"Workflow Completion,{health_report.workflow_completion:.2f}"
        ]
        
        if health_report.strengths:
            lines.append("Strengths")
            for strength in health_report.strengths:
                lines.append(f'"{strength}"')
        
        if health_report.weaknesses:
            lines.append("Weaknesses")
            for weakness in health_report.weaknesses:
                lines.append(f'"{weakness}"')
        
        if health_report.improvement_suggestions:
            lines.append("Improvement Suggestions")
            for suggestion in health_report.improvement_suggestions:
                lines.append(f'"{suggestion}"')
        
        return "\n".join(lines)
