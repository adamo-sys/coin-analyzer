"""CollectorAdvisor — deterministic, explainable recommendation orchestrator.

v8.5 Phase 1: Core recommendation engine. No intelligence. No persistence.
Consumes existing CollectorWorkspace panels and produces advisory recommendations.

Mission: "Collector Advisor helps the collector decide what to do next using
deterministic, explainable recommendations built entirely from existing engines."

Permanent rules:
- Reuse first. Compute second. Orchestrate, don't absorb.
- Every recommendation must include evidence (List[str]) with human-readable reasons.
- Deterministic ordering: identical inputs → identical outputs.
- No ML. No LLM. No black box. No probabilistic scoring.
- Advisory only. The collector decides. The software explains.
- Public APIs are stable after Phase 1.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# RecommendationCategory enum
# ---------------------------------------------------------------------------

class RecommendationCategory(Enum):
    """Deterministic recommendation category.

    Enum values are strings for backward compatibility.
    Phase 2 addition: replaces raw recommendation_type strings.
    """

    PRIORITY_ACQUISITION = "PRIORITY_ACQUISITION"
    GRADE_SUBMIT = "GRADE_SUBMIT"
    UPGRADE = "UPGRADE"
    DISPOSE_DUPLICATE = "DISPOSE_DUPLICATE"
    BUDGET_ALLOCATE = "BUDGET_ALLOCATE"
    NEXT_ACTION = "NEXT_ACTION"


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass
class RecommendationReason:
    """Human-readable reason for a recommendation.

    category: str — e.g., "priority", "upgrade", "risk", "budget"
    description: str — e.g., "highest priority want-list gap"
    source_engine: str — e.g., "collection_intelligence", "smart_shopping"
    confidence: str — "HIGH", "MEDIUM", "LOW"
    """

    category: str
    description: str
    source_engine: str
    confidence: str = "HIGH"


@dataclass
class CollectorRecommendation:
    """A single advisory recommendation with evidence.

    Every recommendation must include non-empty evidence.
    """

    recommendation_id: str
    recommendation_type: RecommendationCategory
    title: str
    description: str
    evidence: List[RecommendationReason] = field(default_factory=list)
    priority: str = "MEDIUM"  # HIGH, MEDIUM, LOW — deterministic categories only
    urgency: str = "ONGOING"  # IMMEDIATE, SHORT_TERM, LONG_TERM, ONGOING
    status: str = "ACTIVE"  # ACTIVE, COMPLETED, DISMISSED, REVIEW
    related_items: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.evidence:
            raise ValueError(
                "Every CollectorRecommendation must include non-empty evidence. "
                "Use RecommendationReason to document why this recommendation exists."
            )

    @property
    def evidence_summary(self) -> str:
        """Human-readable evidence summary for display."""
        lines = [f"  • [{r.source_engine}] {r.description} (confidence: {r.confidence})"
                 for r in self.evidence]
        return "\n".join(lines)

    recommendation_id: str
    recommendation_type: str
    title: str
    description: str
    evidence: List[RecommendationReason] = field(default_factory=list)
    priority: str = "MEDIUM"  # HIGH, MEDIUM, LOW — deterministic categories only
    urgency: str = "ONGOING"  # IMMEDIATE, SHORT_TERM, LONG_TERM, ONGOING
    status: str = "ACTIVE"  # ACTIVE, COMPLETED, DISMISSED, REVIEW
    related_items: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.evidence:
            raise ValueError(
                "Every CollectorRecommendation must include non-empty evidence. "
                "Use RecommendationReason to document why this recommendation exists."
            )

    @property
    def evidence_summary(self) -> str:
        """Human-readable evidence summary for display."""
        lines = [f"  • [{r.source_engine}] {r.description} (confidence: {r.confidence})"
                 for r in self.evidence]
        return "\n".join(lines)


@dataclass
class AdvisorReport:
    """Complete advisory report with all recommendations."""

    recommendations: List[CollectorRecommendation] = field(default_factory=list)
    summary: str = ""
    next_best_action: Optional[CollectorRecommendation] = None
    risks: List[str] = field(default_factory=list)
    opportunities: List[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Priority helpers (deterministic, no numeric scoring)
# ---------------------------------------------------------------------------

_PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
_URGENCY_ORDER = {"IMMEDIATE": 0, "SHORT_TERM": 1, "LONG_TERM": 2, "ONGOING": 3}


def _priority_sort_key(rec: CollectorRecommendation) -> Tuple[int, int, str]:
    """Stable sort key for deterministic recommendation ordering.

    Sorts by priority (HIGH → LOW), then urgency (IMMEDIATE → ONGOING),
    then by stable recommendation_id for tie-breaking.
    """
    return (
        _PRIORITY_ORDER.get(rec.priority, 1),
        _URGENCY_ORDER.get(rec.urgency, 3),
        rec.recommendation_id,
    )


# ---------------------------------------------------------------------------
# CollectorAdvisor
# ---------------------------------------------------------------------------

class CollectorAdvisor:
    """Deterministic recommendation orchestrator.

    Consumes CollectorWorkspace panel outputs and produces advisory
    recommendations. No new intelligence. No new persistence. No mutation.
    """

    def __init__(self, workspace: Any):
        """Initialize with a CollectorWorkspace (or any object with panel getters).

        The workspace parameter is typed as Any to avoid circular imports
        and keep the advisor decoupled from workspace internals.
        """
        self.workspace = workspace

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_advisory_report(self) -> AdvisorReport:
        """Generate complete advisory report from all engines.

        Returns an AdvisorReport with all recommendations sorted
        deterministically by priority, urgency, and stable ID.
        """
        recommendations: List[CollectorRecommendation] = []
        risks: List[str] = []
        opportunities: List[str] = []

        # Collect recommendations from each source
        try:
            recommendations.extend(self.recommend_priority_acquisitions())
        except Exception as e:
            risks.append(f"Priority acquisition recommendation failed: {e}")

        try:
            recommendations.extend(self.recommend_grade_submissions())
        except Exception as e:
            risks.append(f"Grade submission recommendation failed: {e}")

        try:
            recommendations.extend(self.recommend_upgrades())
        except Exception as e:
            risks.append(f"Upgrade recommendation failed: {e}")

        try:
            recommendations.extend(self.recommend_duplicate_disposal())
        except Exception as e:
            risks.append(f"Duplicate disposal recommendation failed: {e}")

        try:
            recommendations.extend(self.recommend_budget_allocation())
        except Exception as e:
            risks.append(f"Budget allocation recommendation failed: {e}")

        # Deterministic sort: priority → urgency → stable ID
        recommendations.sort(key=_priority_sort_key)

        next_best = self.recommend_next_action(recommendations)

        summary = self._build_summary(recommendations, next_best)
        opportunities = self._extract_opportunities(recommendations)

        return AdvisorReport(
            recommendations=recommendations,
            summary=summary,
            next_best_action=next_best,
            risks=risks,
            opportunities=opportunities,
            generated_at=datetime.now(),
        )

    def recommend_priority_acquisitions(self) -> List[CollectorRecommendation]:
        """Recommend highest-priority acquisitions from want-list, gaps, and opportunities.

        Sources: WantListReport, OpportunitiesReport, CollectionSummaryReport, DashboardReport
        """
        recommendations: List[CollectorRecommendation] = []

        try:
            want_list = self.workspace.get_want_list()
        except Exception:
            want_list = None

        try:
            opportunities = self.workspace.get_opportunities()
        except Exception:
            opportunities = None

        try:
            collection_summary = self.workspace.get_collection_summary()
        except Exception:
            collection_summary = None

        try:
            dashboard = self.workspace.get_dashboard()
        except Exception:
            dashboard = None

        # Extract cross-panel context for evidence enrichment
        total_items = getattr(collection_summary, "total_items", 0) if collection_summary else 0
        quality_score = getattr(collection_summary, "quality_score", None) if collection_summary else None
        total_gaps = getattr(want_list, "total_gaps", 0) if want_list else 0
        total_upgrades = getattr(want_list, "total_upgrades", 0) if want_list else 0
        best_next_purchase = getattr(dashboard, "best_next_purchase", None) if dashboard else None
        total_opportunities = getattr(opportunities, "total_opportunities", 0) if opportunities else 0

        # Want-list gaps (highest priority)
        if want_list and want_list.gap_targets:
            for idx, gap in enumerate(want_list.gap_targets[:3]):
                country = gap.get("country", "Unknown")
                denomination = gap.get("denomination", "")
                year = gap.get("year", "")
                title = f"Acquire {country} {denomination} {year}".strip()
                rec_id = f"acq_gap_{idx}"

                evidence = [
                    RecommendationReason(
                        category="priority",
                        description=f"Collection gap target identified in want-list ({total_gaps} total gaps)",
                        source_engine="want_list_generator",
                        confidence="HIGH",
                    ),
                    RecommendationReason(
                        category="priority",
                        description=f"No owned example of {country} {denomination} {year}",
                        source_engine="collection_intelligence",
                        confidence="HIGH",
                    ),
                ]
                if total_items > 0:
                    evidence.append(RecommendationReason(
                        category="context",
                        description=f"Collection currently has {total_items} items",
                        source_engine="collection_summary",
                        confidence="HIGH",
                    ))
                if best_next_purchase and (country in str(best_next_purchase) or denomination in str(best_next_purchase)):
                    evidence.append(RecommendationReason(
                        category="alignment",
                        description=f"Aligns with dashboard best-next-purchase: {best_next_purchase}",
                        source_engine="dashboard",
                        confidence="MEDIUM",
                    ))

                recommendations.append(CollectorRecommendation(
                    recommendation_id=rec_id,
                    recommendation_type=RecommendationCategory.PRIORITY_ACQUISITION,
                    title=title,
                    description=f"Fill collection gap: {country} {denomination} {year}",
                    evidence=evidence,
                    priority="HIGH",
                    urgency="SHORT_TERM",
                    related_items=[str(gap.get("id", "")),],
                ))

        # Want-list upgrade candidates
        if want_list and want_list.upgrade_candidates:
            for idx, upgrade in enumerate(want_list.upgrade_candidates[:2]):
                country = upgrade.get("country", "Unknown")
                denomination = upgrade.get("denomination", "")
                year = upgrade.get("year", "")
                title = f"Upgrade {country} {denomination} {year}".strip()
                rec_id = f"acq_upg_{idx}"

                evidence = [
                    RecommendationReason(
                        category="upgrade",
                        description=f"Upgrade candidate in want-list ({total_upgrades} total upgrade targets)",
                        source_engine="want_list_generator",
                        confidence="MEDIUM",
                    ),
                    RecommendationReason(
                        category="upgrade",
                        description=f"Higher grade example may improve collection quality",
                        source_engine="upgrade_advisor",
                        confidence="MEDIUM",
                    ),
                ]
                if quality_score is not None:
                    evidence.append(RecommendationReason(
                        category="context",
                        description=f"Collection quality score is {quality_score}",
                        source_engine="collection_summary",
                        confidence="HIGH",
                    ))

                recommendations.append(CollectorRecommendation(
                    recommendation_id=rec_id,
                    recommendation_type=RecommendationCategory.PRIORITY_ACQUISITION,
                    title=title,
                    description=f"Upgrade opportunity: {country} {denomination} {year}",
                    evidence=evidence,
                    priority="MEDIUM",
                    urgency="LONG_TERM",
                    related_items=[str(upgrade.get("id", "")),],
                ))

        # Top opportunities from smart shopping
        if opportunities and opportunities.top_recommendations:
            for idx, rec in enumerate(opportunities.top_recommendations[:2]):
                title = rec.get("title", rec.get("description", f"Opportunity {idx}"))
                rec_id = f"acq_opp_{idx}"

                evidence = [
                    RecommendationReason(
                        category="opportunity",
                        description=f"Top-ranked acquisition opportunity (#{idx + 1} of {total_opportunities})",
                        source_engine="smart_shopping",
                        confidence="HIGH",
                    ),
                    RecommendationReason(
                        category="opportunity",
                        description=f"Evaluated for collection fit and impact",
                        source_engine="opportunity_engine",
                        confidence="MEDIUM",
                    ),
                ]
                if total_gaps > 0:
                    evidence.append(RecommendationReason(
                        category="context",
                        description=f"Collection has {total_gaps} unfilled gaps",
                        source_engine="want_list_generator",
                        confidence="HIGH",
                    ))
                if best_next_purchase and title in str(best_next_purchase):
                    evidence.append(RecommendationReason(
                        category="alignment",
                        description=f"Aligns with dashboard best-next-purchase: {best_next_purchase}",
                        source_engine="dashboard",
                        confidence="MEDIUM",
                    ))

                recommendations.append(CollectorRecommendation(
                    recommendation_id=rec_id,
                    recommendation_type=RecommendationCategory.PRIORITY_ACQUISITION,
                    title=title,
                    description=f"Ranked opportunity from smart shopping analysis",
                    evidence=evidence,
                    priority="HIGH" if idx == 0 else "MEDIUM",
                    urgency="SHORT_TERM" if idx == 0 else "LONG_TERM",
                    related_items=[str(rec.get("id", "")),],
                ))

        return recommendations

    def recommend_grade_submissions(self) -> List[CollectorRecommendation]:
        """Recommend candidates for grading submission based on assessments.

        Sources: AIQueueReport, PhotoVaultReport, CollectionSummaryReport
        """
        recommendations: List[CollectorRecommendation] = []

        try:
            ai_queue = self.workspace.get_ai_queue()
        except Exception:
            ai_queue = None

        try:
            photo_vault = self.workspace.get_photo_vault()
        except Exception:
            photo_vault = None

        try:
            collection_summary = self.workspace.get_collection_summary()
        except Exception:
            collection_summary = None

        # Cross-panel context
        total_items = getattr(collection_summary, "total_items", 0) if collection_summary else 0
        quality_score = getattr(collection_summary, "quality_score", None) if collection_summary else None

        # Items with photos but no grading (simplified heuristic)
        if photo_vault and photo_vault.coverage_percentage is not None:
            if photo_vault.coverage_percentage < 100.0:
                missing = photo_vault.missing_photo_count or 0
                if missing > 0:
                    evidence = [
                        RecommendationReason(
                            category="grading",
                            description=f"{missing} items without photos",
                            source_engine="photo_vault",
                            confidence="HIGH",
                        ),
                        RecommendationReason(
                            category="grading",
                            description="Photos are required for grading submission",
                            source_engine="ai_grading_assistant",
                            confidence="HIGH",
                        ),
                    ]
                    if total_items > 0:
                        evidence.append(RecommendationReason(
                            category="context",
                            description=f"Collection has {total_items} total items",
                            source_engine="collection_summary",
                            confidence="HIGH",
                        ))
                    if quality_score is not None:
                        evidence.append(RecommendationReason(
                            category="context",
                            description=f"Collection quality score is {quality_score}",
                            source_engine="collection_summary",
                            confidence="HIGH",
                        ))
                    certified = getattr(photo_vault, "certified_items", 0) or 0
                    certified_with_photos = getattr(photo_vault, "certified_with_photos", 0) or 0
                    if certified > 0:
                        evidence.append(RecommendationReason(
                            category="context",
                            description=f"{certified} certified items, {certified_with_photos} with photos",
                            source_engine="photo_vault",
                            confidence="HIGH",
                        ))

                    recommendations.append(CollectorRecommendation(
                        recommendation_id="grade_photo_coverage",
                        recommendation_type=RecommendationCategory.GRADE_SUBMIT,
                        title="Add photos for unphotographed items",
                        description=f"{missing} collection items lack photos. Add photos before grading.",
                        evidence=evidence,
                        priority="MEDIUM",
                        urgency="LONG_TERM",
                    ))

        # AI grading review queue
        if ai_queue and ai_queue.ai_grading_review > 0:
            evidence = [
                RecommendationReason(
                    category="grading",
                    description=f"{ai_queue.ai_grading_review} grading assessment(s) awaiting review",
                    source_engine="ai_grading_assistant",
                    confidence="HIGH",
                ),
                RecommendationReason(
                    category="grading",
                    description="Review assessments before submitting for professional grading",
                    source_engine="collector_advisor",
                    confidence="HIGH",
                ),
            ]
            if total_items > 0:
                evidence.append(RecommendationReason(
                    category="context",
                    description=f"Collection has {total_items} total items",
                    source_engine="collection_summary",
                    confidence="HIGH",
                ))
            if quality_score is not None:
                evidence.append(RecommendationReason(
                    category="context",
                    description=f"Collection quality score is {quality_score}",
                    source_engine="collection_summary",
                    confidence="HIGH",
                ))

            recommendations.append(CollectorRecommendation(
                recommendation_id="grade_ai_review",
                recommendation_type=RecommendationCategory.GRADE_SUBMIT,
                title="Review AI grading assessments",
                description=f"{ai_queue.ai_grading_review} grading assessment(s) awaiting review.",
                evidence=evidence,
                priority="MEDIUM",
                urgency="SHORT_TERM",
            ))

        return recommendations

    def recommend_upgrades(self) -> List[CollectorRecommendation]:
        """Recommend upgrade candidates from collection intelligence.

        Sources: WantListReport, OpportunitiesReport, CollectionSummaryReport, DashboardReport
        """
        recommendations: List[CollectorRecommendation] = []

        try:
            want_list = self.workspace.get_want_list()
        except Exception:
            want_list = None

        try:
            opportunities = self.workspace.get_opportunities()
        except Exception:
            opportunities = None

        try:
            collection_summary = self.workspace.get_collection_summary()
        except Exception:
            collection_summary = None

        try:
            dashboard = self.workspace.get_dashboard()
        except Exception:
            dashboard = None

        # Cross-panel context
        total_items = getattr(collection_summary, "total_items", 0) if collection_summary else 0
        quality_score = getattr(collection_summary, "quality_score", None) if collection_summary else None
        dashboard_quality = getattr(dashboard, "quality_score", None) if dashboard else None
        total_opportunities = getattr(opportunities, "total_opportunities", 0) if opportunities else 0
        total_upgrades = getattr(want_list, "total_upgrades", 0) if want_list else 0

        # Upgrade candidates from want list
        if want_list and want_list.upgrade_candidates:
            for idx, upgrade in enumerate(want_list.upgrade_candidates[:3]):
                country = upgrade.get("country", "Unknown")
                denomination = upgrade.get("denomination", "")
                year = upgrade.get("year", "")
                current_grade = upgrade.get("current_grade", "")
                target_grade = upgrade.get("target_grade", "")
                title = f"Upgrade {country} {denomination} {year}".strip()
                rec_id = f"upg_{idx}"

                evidence = [
                    RecommendationReason(
                        category="upgrade",
                        description=f"Upgrade candidate identified in want-list ({total_upgrades} total upgrade targets)",
                        source_engine="want_list_generator",
                        confidence="HIGH",
                    ),
                    RecommendationReason(
                        category="upgrade",
                        description=f"Collection contains lower-grade example ({current_grade} -> {target_grade})",
                        source_engine="upgrade_advisor",
                        confidence="HIGH",
                    ),
                ]
                if total_items > 0:
                    evidence.append(RecommendationReason(
                        category="context",
                        description=f"Collection has {total_items} total items",
                        source_engine="collection_summary",
                        confidence="HIGH",
                    ))
                if quality_score is not None:
                    evidence.append(RecommendationReason(
                        category="context",
                        description=f"Collection quality score is {quality_score}",
                        source_engine="collection_summary",
                        confidence="HIGH",
                    ))
                if dashboard_quality is not None:
                    evidence.append(RecommendationReason(
                        category="context",
                        description=f"Dashboard quality score is {dashboard_quality}",
                        source_engine="dashboard",
                        confidence="HIGH",
                    ))

                recommendations.append(CollectorRecommendation(
                    recommendation_id=rec_id,
                    recommendation_type=RecommendationCategory.UPGRADE,
                    title=title,
                    description=f"Upgrade from {current_grade} to {target_grade} "
                                  f"for {country} {denomination} {year}",
                    evidence=evidence,
                    priority="MEDIUM",
                    urgency="LONG_TERM",
                    related_items=[str(upgrade.get("id", "")),],
                ))

        # Highest-impact upgrade from opportunities
        if opportunities and opportunities.highest_impact:
            evidence = [
                RecommendationReason(
                    category="upgrade",
                    description=f"Highest-impact upgrade opportunity",
                    source_engine="opportunity_engine",
                    confidence="HIGH",
                ),
                RecommendationReason(
                    category="impact",
                    description=f"Evaluated for collection quality delta",
                    source_engine="acquisition_impact",
                    confidence="MEDIUM",
                ),
            ]
            if total_opportunities > 0:
                evidence.append(RecommendationReason(
                    category="context",
                    description=f"{total_opportunities} total opportunities available",
                    source_engine="opportunity_engine",
                    confidence="HIGH",
                ))
            if total_items > 0:
                evidence.append(RecommendationReason(
                    category="context",
                    description=f"Collection has {total_items} total items",
                    source_engine="collection_summary",
                    confidence="HIGH",
                ))
            if quality_score is not None:
                evidence.append(RecommendationReason(
                    category="context",
                    description=f"Collection quality score is {quality_score}",
                    source_engine="collection_summary",
                    confidence="HIGH",
                ))

            recommendations.append(CollectorRecommendation(
                recommendation_id="upg_highest_impact",
                recommendation_type=RecommendationCategory.UPGRADE,
                title=f"Highest-impact upgrade: {opportunities.highest_impact}",
                description="This upgrade offers the greatest collection improvement potential.",
                evidence=evidence,
                priority="HIGH",
                urgency="SHORT_TERM",
            ))

        return recommendations

    def recommend_duplicate_disposal(self) -> List[CollectorRecommendation]:
        """Recommend duplicate candidates for sale/trade/disposal.

        Sources: CollectionSummaryReport, WantListReport, PhotoVaultReport
        """
        recommendations: List[CollectorRecommendation] = []

        try:
            summary = self.workspace.get_collection_summary()
        except Exception:
            summary = None

        try:
            want_list = self.workspace.get_want_list()
        except Exception:
            want_list = None

        try:
            photo_vault = self.workspace.get_photo_vault()
        except Exception:
            photo_vault = None

        # Cross-panel context
        total_gaps = getattr(want_list, "total_gaps", 0) if want_list else 0
        total_upgrades = getattr(want_list, "total_upgrades", 0) if want_list else 0
        duplicate_photo_count = getattr(photo_vault, "duplicate_photo_count", 0) if photo_vault else 0

        # Simple heuristic: if we have many items, suggest reviewing duplicates
        if summary and summary.total_items > 0:
            # Note: we don't have direct duplicate count in CollectionSummaryReport,
            # so we use a conservative advisory based on collection size
            if summary.total_items > 50:
                evidence = [
                    RecommendationReason(
                        category="duplicate",
                        description=f"Collection size ({summary.total_items}) suggests review needed",
                        source_engine="collection_intelligence",
                        confidence="MEDIUM",
                    ),
                    RecommendationReason(
                        category="duplicate",
                        description="Duplicate disposal frees budget for priority acquisitions",
                        source_engine="collector_advisor",
                        confidence="HIGH",
                    ),
                ]
                if total_gaps > 0:
                    evidence.append(RecommendationReason(
                        category="context",
                        description=f"Collection has {total_gaps} unfilled gaps to fund",
                        source_engine="want_list_generator",
                        confidence="HIGH",
                    ))
                if total_upgrades > 0:
                    evidence.append(RecommendationReason(
                        category="context",
                        description=f"Collection has {total_upgrades} upgrade targets",
                        source_engine="want_list_generator",
                        confidence="HIGH",
                    ))
                if duplicate_photo_count > 0:
                    evidence.append(RecommendationReason(
                        category="duplicate",
                        description=f"Photo vault identifies {duplicate_photo_count} duplicate photos",
                        source_engine="photo_vault",
                        confidence="HIGH",
                    ))

                recommendations.append(CollectorRecommendation(
                    recommendation_id="dup_review",
                    recommendation_type=RecommendationCategory.DISPOSE_DUPLICATE,
                    title="Review collection for duplicate disposal",
                    description=f"Collection has {summary.total_items} items. "
                                  f"Review duplicates and surplus items for sale or trade.",
                    evidence=evidence,
                    priority="LOW",
                    urgency="ONGOING",
                ))

        return recommendations

    def recommend_budget_allocation(self) -> List[CollectorRecommendation]:
        """Recommend budget allocation across priority categories.

        Sources: OpportunitiesReport, DashboardReport, WantListReport, CollectionSummaryReport
        """
        recommendations: List[CollectorRecommendation] = []

        try:
            opportunities = self.workspace.get_opportunities()
        except Exception:
            opportunities = None

        try:
            dashboard = self.workspace.get_dashboard()
        except Exception:
            dashboard = None

        try:
            want_list = self.workspace.get_want_list()
        except Exception:
            want_list = None

        try:
            collection_summary = self.workspace.get_collection_summary()
        except Exception:
            collection_summary = None

        # Cross-panel context
        total_gaps = getattr(want_list, "total_gaps", 0) if want_list else 0
        total_upgrades = getattr(want_list, "total_upgrades", 0) if want_list else 0
        total_watchlist_matches = getattr(want_list, "total_watchlist_matches", 0) if want_list else 0
        total_items = getattr(collection_summary, "total_items", 0) if collection_summary else 0
        quality_score = getattr(collection_summary, "quality_score", None) if collection_summary else None
        total_opportunities = getattr(opportunities, "total_opportunities", 0) if opportunities else 0

        # Budget recommendations from opportunities
        if opportunities and opportunities.budget_recommendations:
            for idx, rec in enumerate(opportunities.budget_recommendations[:2]):
                evidence = [
                    RecommendationReason(
                        category="budget",
                        description=f"Budget recommendation: {rec}",
                        source_engine="opportunity_engine",
                        confidence="MEDIUM",
                    ),
                    RecommendationReason(
                        category="budget",
                        description="Evaluated for collection fit and priority alignment",
                        source_engine="acquisition_strategy",
                        confidence="MEDIUM",
                    ),
                ]
                if total_gaps > 0:
                    evidence.append(RecommendationReason(
                        category="context",
                        description=f"Collection has {total_gaps} unfilled gaps",
                        source_engine="want_list_generator",
                        confidence="HIGH",
                    ))
                if total_upgrades > 0:
                    evidence.append(RecommendationReason(
                        category="context",
                        description=f"Collection has {total_upgrades} upgrade targets",
                        source_engine="want_list_generator",
                        confidence="HIGH",
                    ))
                if total_watchlist_matches > 0:
                    evidence.append(RecommendationReason(
                        category="context",
                        description=f"Watchlist has {total_watchlist_matches} matched items",
                        source_engine="want_list_generator",
                        confidence="HIGH",
                    ))

                recommendations.append(CollectorRecommendation(
                    recommendation_id=f"budget_{idx}",
                    recommendation_type=RecommendationCategory.BUDGET_ALLOCATE,
                    title=f"Budget allocation: {rec}",
                    description=f"Budget recommendation from opportunity analysis: {rec}",
                    evidence=evidence,
                    priority="MEDIUM",
                    urgency="LONG_TERM",
                ))

        # Quality-based budget suggestion
        if dashboard and dashboard.quality_score is not None:
            if dashboard.quality_score < 50:
                evidence = [
                    RecommendationReason(
                        category="budget",
                        description=f"Quality score ({dashboard.quality_score}) suggests investment needed",
                        source_engine="collection_quality",
                        confidence="MEDIUM",
                    ),
                    RecommendationReason(
                        category="budget",
                        description="Higher-grade acquisitions improve overall collection quality",
                        source_engine="collector_advisor",
                        confidence="HIGH",
                    ),
                ]
                if total_items > 0:
                    evidence.append(RecommendationReason(
                        category="context",
                        description=f"Collection has {total_items} total items",
                        source_engine="collection_summary",
                        confidence="HIGH",
                    ))
                if total_gaps > 0:
                    evidence.append(RecommendationReason(
                        category="context",
                        description=f"Collection has {total_gaps} unfilled gaps",
                        source_engine="want_list_generator",
                        confidence="HIGH",
                    ))
                if total_opportunities > 0:
                    evidence.append(RecommendationReason(
                        category="context",
                        description=f"{total_opportunities} opportunities identified",
                        source_engine="opportunity_engine",
                        confidence="HIGH",
                    ))
                if quality_score is not None:
                    evidence.append(RecommendationReason(
                        category="context",
                        description=f"Collection quality score is {quality_score}",
                        source_engine="collection_summary",
                        confidence="HIGH",
                    ))

                recommendations.append(CollectorRecommendation(
                    recommendation_id="budget_quality",
                    recommendation_type=RecommendationCategory.BUDGET_ALLOCATE,
                    title="Allocate budget to quality improvements",
                    description=f"Collection quality score is {dashboard.quality_score}. "
                                  f"Consider allocating budget to higher-grade acquisitions.",
                    evidence=evidence,
                    priority="MEDIUM",
                    urgency="LONG_TERM",
                ))

        return recommendations

    def recommend_next_action(self, recommendations: Optional[List[CollectorRecommendation]] = None) -> Optional[CollectorRecommendation]:
        """Single "next best action" recommendation.

        If recommendations list is provided, returns the highest-priority item
        from that list. Otherwise, generates a fresh report and returns the top item.
        """
        if recommendations is None:
            try:
                report = self.generate_advisory_report()
                recommendations = report.recommendations
            except Exception:
                return None

        if not recommendations:
            return None

        # Deterministic sort: priority → urgency → stable ID
        recommendations.sort(key=_priority_sort_key)

        return recommendations[0]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_summary(self, recommendations: List[CollectorRecommendation], next_best: Optional[CollectorRecommendation]) -> str:
        """Build a human-readable summary of the advisory report."""
        lines = ["Collector Advisor Report", "=" * 40]
        lines.append(f"Total recommendations: {len(recommendations)}")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        if next_best:
            lines.append(f"Next Best Action: {next_best.title}")
            lines.append(f"Type: {next_best.recommendation_type.value}")
            lines.append(f"Priority: {next_best.priority}")
            lines.append("")

        by_type: Dict[str, List[CollectorRecommendation]] = {}
        for rec in recommendations:
            by_type.setdefault(rec.recommendation_type.value, []).append(rec)

        for rec_type, recs in sorted(by_type.items()):
            lines.append(f"{rec_type}: {len(recs)} recommendation(s)")

        lines.append("")
        lines.append("All recommendations include evidence. Review each recommendation")
        lines.append("and its supporting reasons before acting.")

        return "\n".join(lines)

    def _extract_opportunities(self, recommendations: List[CollectorRecommendation]) -> List[str]:
        """Extract opportunity descriptions from recommendations."""
        opportunities: List[str] = []
        for rec in recommendations:
            if rec.recommendation_type in (RecommendationCategory.PRIORITY_ACQUISITION, RecommendationCategory.UPGRADE):
                opportunities.append(f"{rec.title} ({rec.priority} priority)")
        return opportunities
