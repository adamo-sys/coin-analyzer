"""Mobile-oriented Collector Companion workflow layer.

This module models phone-like collector workflows while remaining fully
desktop/local. It does not implement Android, iOS, cloud sync, phone camera
capture, OCR identification, live fetching, purchasing, or collection mutation.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from deal_hunter import DealListing
from deal_hunter_ranking import CandidatePool, DealHunterRankingEngine, RankedDeal
from field_test_framework import ScenarioRunner, default_field_test_scenarios
from market_awareness import MarketAwarenessEngine
from market_intelligence_automation import MarketEnrichedCandidate, MarketIntelligenceAutomationEngine
from photo_capture_workflow import PhotoCaptureReport, PhotoCaptureSession, PhotoCaptureWorkflow
from portfolio_performance import PortfolioPerformanceEngine
from watchlist_engine import AlertEngine, AlertReport, Watchlist, WatchlistEngine


WORKFLOW_COIN_SHOW = "Coin Show Workflow"
WORKFLOW_DEALER_VISIT = "Dealer Visit Workflow"
WORKFLOW_ANTIQUE_MARKET = "Antique Market Workflow"
WORKFLOW_COIN_SHOP = "Coin Shop Workflow"
WORKFLOW_AUCTION_PREVIEW = "Auction Preview Workflow"


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _dedupe(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        text = _text(value)
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def _normalize_recommendation(value: str) -> str:
    text = _text(value).upper()
    if "PASS" in text:
        return "PASS"
    if "REVIEW" in text:
        return "REVIEW"
    if "NEGOTIATE" in text or "WATCH" in text:
        return "WATCH"
    if "BUY" in text:
        return "BUY"
    return "REVIEW"


def _candidate_title(candidate: Any) -> str:
    if isinstance(candidate, DealListing):
        return candidate.title
    if isinstance(candidate, RankedDeal):
        return candidate.listing.title
    if isinstance(candidate, MarketEnrichedCandidate):
        return candidate.original_listing.title
    if isinstance(candidate, dict):
        return _text(candidate.get("title") or candidate.get("item_title"))
    return _text(getattr(candidate, "title", "Candidate"))


def _to_listing(candidate: Any) -> DealListing:
    if isinstance(candidate, DealListing):
        return candidate
    if isinstance(candidate, RankedDeal):
        return candidate.listing
    if isinstance(candidate, MarketEnrichedCandidate):
        return candidate.original_listing
    if hasattr(candidate, "to_deal_listing"):
        return candidate.to_deal_listing()
    if isinstance(candidate, dict):
        return DealListing.from_dict(candidate)
    return DealListing(title=_candidate_title(candidate))


@dataclass
class MobileSession:
    session_id: str
    workflow_type: str = WORKFLOW_COIN_SHOW
    location: str = ""
    started_at: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        self.started_at = self.started_at or _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class MobileWorkflow:
    name: str
    purpose: str
    supported_inputs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "supported_inputs": "; ".join(self.supported_inputs),
        }


@dataclass
class QuickDecisionSummary:
    candidate_title: str
    recommendation: str
    confidence: int = 0
    top_reasons: List[str] = field(default_factory=list)
    key_risks: List[str] = field(default_factory=list)
    watchlist_matches: List[str] = field(default_factory=list)
    collection_relevance: str = ""
    market_intelligence_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_title": self.candidate_title,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "top_reasons": "; ".join(self.top_reasons),
            "key_risks": "; ".join(self.key_risks),
            "watchlist_matches": "; ".join(self.watchlist_matches),
            "collection_relevance": self.collection_relevance,
            "market_intelligence_summary": self.market_intelligence_summary,
        }

    def format_brief(self) -> str:
        reasons = "; ".join(self.top_reasons[:3]) or "No top reason available."
        risks = "; ".join(self.key_risks[:3]) or "No major risk flags."
        return f"{self.recommendation} ({self.confidence}) - {self.candidate_title}. Reasons: {reasons}. Risks: {risks}"


@dataclass
class MobileCollectionContext:
    watchlist_summary: str = ""
    active_targets: List[str] = field(default_factory=list)
    collection_priorities: List[str] = field(default_factory=list)
    recent_opportunities: List[str] = field(default_factory=list)
    portfolio_highlights: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "watchlist_summary": self.watchlist_summary,
            "active_targets": "; ".join(self.active_targets),
            "collection_priorities": "; ".join(self.collection_priorities),
            "recent_opportunities": "; ".join(self.recent_opportunities),
            "portfolio_highlights": "; ".join(self.portfolio_highlights),
        }


@dataclass
class MobileDashboard:
    active_watchlists: List[str] = field(default_factory=list)
    high_priority_targets: List[str] = field(default_factory=list)
    recent_alerts: List[str] = field(default_factory=list)
    recent_opportunities: List[str] = field(default_factory=list)
    collection_priorities: List[str] = field(default_factory=list)
    quick_decisions: List[QuickDecisionSummary] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_watchlists": "; ".join(self.active_watchlists),
            "high_priority_targets": "; ".join(self.high_priority_targets),
            "recent_alerts": "; ".join(self.recent_alerts),
            "recent_opportunities": "; ".join(self.recent_opportunities),
            "collection_priorities": "; ".join(self.collection_priorities),
            "quick_decisions": [decision.to_dict() for decision in self.quick_decisions],
        }


@dataclass
class FieldWorkMode:
    workflow_name: str
    quick_decisions: List[QuickDecisionSummary] = field(default_factory=list)
    minimal_summary: str = ""
    risk_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_name": self.workflow_name,
            "minimal_summary": self.minimal_summary,
            "risk_flags": "; ".join(self.risk_flags),
            "quick_decisions": [decision.to_dict() for decision in self.quick_decisions],
        }


@dataclass
class MobileCompanionReport:
    session: MobileSession
    workflow: MobileWorkflow
    dashboard: MobileDashboard
    collection_context: MobileCollectionContext
    field_work_mode: FieldWorkMode
    quick_decisions: List[QuickDecisionSummary] = field(default_factory=list)
    photo_capture_report: Optional[PhotoCaptureReport] = None
    generated_at: str = ""
    limitations: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()
        self.limitations = self.limitations or [
            "Desktop/local mobile workflow simulation only.",
            "No Android or iOS app.",
            "No cloud sync, phone camera integration, OCR identification, live fetching, purchasing, or collection mutation.",
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "session": self.session.to_dict(),
            "workflow": self.workflow.to_dict(),
            "dashboard": self.dashboard.to_dict(),
            "collection_context": self.collection_context.to_dict(),
            "field_work_mode": self.field_work_mode.to_dict(),
            "quick_decisions": [decision.to_dict() for decision in self.quick_decisions],
            "photo_capture_report": self.photo_capture_report.to_dict() if self.photo_capture_report else {},
            "limitations": "; ".join(self.limitations),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Mobile Collector Companion Report",
            "",
            f"- Generated: {self.generated_at}",
            f"- Workflow: {self.workflow.name}",
            f"- Session: {self.session.session_id}",
            "- Safety note: desktop/local mobile workflow simulation only; no mobile app, cloud sync, phone camera integration, purchasing, or collection mutation.",
            "",
            "## Quick Decisions",
            "",
        ]
        lines.extend(f"- {decision.format_brief()}" for decision in self.quick_decisions) if self.quick_decisions else lines.append("- None.")
        lines.extend(["", "## Mobile Dashboard", ""])
        for key, value in self.dashboard.to_dict().items():
            if key != "quick_decisions":
                lines.append(f"- {key.replace('_', ' ').title()}: {value or 'None'}")
        lines.extend(["", "## Collection Context", ""])
        for key, value in self.collection_context.to_dict().items():
            lines.append(f"- {key.replace('_', ' ').title()}: {value or 'None'}")
        lines.extend(["", "## Field Work Mode", "", f"- Summary: {self.field_work_mode.minimal_summary or 'None'}"])
        lines.extend(f"- Risk: {risk}" for risk in self.field_work_mode.risk_flags) if self.field_work_mode.risk_flags else lines.append("- Risk: None")
        if self.photo_capture_report:
            lines.extend([
                "",
                "## Phone Photo Capture",
                "",
                f"- Capture sessions: {self.photo_capture_report.total_sessions}",
                f"- Photos collected: {self.photo_capture_report.total_photos}",
                f"- Missing front photos: {self.photo_capture_report.missing_front_count}",
                f"- Missing back photos: {self.photo_capture_report.missing_back_count}",
                f"- Ready for OCR: {self.photo_capture_report.ready_for_ocr_count}",
                f"- Ready for review: {self.photo_capture_report.ready_for_review_count}",
            ])
        lines.extend(["", "## Limitations", ""])
        lines.extend(f"- {item}" for item in self.limitations)
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        fieldnames = [
            "candidate_title", "recommendation", "confidence", "top_reasons",
            "key_risks", "watchlist_matches", "collection_relevance", "market_intelligence_summary",
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for decision in self.quick_decisions:
                writer.writerow(decision.to_dict())
        return True


class MobileCollectorCompanion:
    """Coordinate phone-like collector workflows using existing engines."""

    def __init__(
        self,
        collection_items: Optional[Iterable[Any]] = None,
        want_list_intents: Optional[Iterable[Any]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
        watchlists: Optional[Sequence[Watchlist]] = None,
        photo_capture_workflow: Optional[PhotoCaptureWorkflow] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()
        self.watchlists = list(watchlists or [WatchlistEngine.adam_presets()])
        self.photo_capture_workflow = photo_capture_workflow or PhotoCaptureWorkflow()
        self.ranking_engine = DealHunterRankingEngine(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
        )
        self.market_automation = MarketIntelligenceAutomationEngine(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
        )
        self.watchlist_engine = WatchlistEngine(self.watchlists)
        self.alert_engine = AlertEngine(self.watchlist_engine)

    @staticmethod
    def workflows() -> List[MobileWorkflow]:
        return [
            MobileWorkflow(WORKFLOW_COIN_SHOW, "Fast review while walking a coin show floor.", ["title", "price", "notes"]),
            MobileWorkflow(WORKFLOW_DEALER_VISIT, "Evaluate dealer tray opportunities with minimal entry.", ["title", "price", "seller"]),
            MobileWorkflow(WORKFLOW_ANTIQUE_MARKET, "Review uncertain antique-market finds conservatively.", ["title", "price", "risk notes"]),
            MobileWorkflow(WORKFLOW_COIN_SHOP, "Compare shop inventory against collection priorities.", ["title", "price", "shop notes"]),
            MobileWorkflow(WORKFLOW_AUCTION_PREVIEW, "Preview auction lots and watchlist hits before bidding decisions.", ["title", "estimate", "url"]),
        ]

    def start_session(self, workflow_type: str = WORKFLOW_COIN_SHOW, location: str = "", notes: str = "") -> MobileSession:
        slug = workflow_type.lower().replace(" ", "-")
        return MobileSession(session_id=f"{slug}-{datetime.now().strftime('%Y%m%d%H%M%S')}", workflow_type=workflow_type, location=location, notes=notes)

    def collection_context(self, recent_opportunities: Optional[Sequence[Any]] = None) -> MobileCollectionContext:
        watch_items = [item for watchlist in self.watchlists for item in watchlist.active_items()]
        active_targets = [item.name for item in watch_items[:10]]
        priorities = [
            "Newfoundland coinage",
            "1859 Canadian Large Cents and varieties",
            "Canadian silver coinage",
            "Date-run completion",
            "Upgrade-over-duplicate strategy",
        ]
        highlights = [
            f"Collection items loaded: {len(self.collection_items)}",
            f"WANT_LIST intents loaded: {len(self.want_list_intents)}",
            f"Active watch items: {len(watch_items)}",
        ]
        try:
            performance = PortfolioPerformanceEngine(
                self.collection_items,
                self.want_list_intents,
                market_awareness_engine=self.market_awareness_engine,
            ).generate_report()
            highlights.append(f"Portfolio health: {performance.health_score.score}/100")
        except Exception:
            highlights.append("Portfolio health unavailable in mobile context.")
        return MobileCollectionContext(
            watchlist_summary=f"{len(self.watchlists)} watchlist(s), {len(watch_items)} active target(s)",
            active_targets=active_targets,
            collection_priorities=priorities,
            recent_opportunities=[_candidate_title(item) for item in list(recent_opportunities or [])[:5]],
            portfolio_highlights=highlights,
        )

    def quick_decision(self, candidate: Any) -> QuickDecisionSummary:
        listing = _to_listing(candidate)
        pool = CandidatePool.from_listings([listing])
        ranking_report = self.ranking_engine.rank_pool(pool, limit=1)
        ranked = ranking_report.ranked_deals[0] if ranking_report.ranked_deals else None
        enrichment = self.market_automation.enrich_candidates([ranked or listing], "Mobile Collector Companion")
        enriched = enrichment.enriched_candidates[0] if enrichment.enriched_candidates else None
        alert_report = self.alert_engine.generate_alerts([enriched or ranked or listing])

        recommendation_source = (
            getattr(enriched, "escalated_recommendation", "")
            or getattr(ranked, "recommendation", "")
            or "REVIEW"
        )
        recommendation = _normalize_recommendation(recommendation_source)
        confidence = int(getattr(enriched, "opportunity_confidence", 0) or getattr(getattr(ranked, "ranking_score", None), "score", 0) or 0)
        reasons = self._decision_reasons(enriched, ranked, alert_report)
        risks = self._decision_risks(enriched, ranked, alert_report)
        return QuickDecisionSummary(
            candidate_title=listing.title,
            recommendation=recommendation,
            confidence=confidence,
            top_reasons=reasons[:5],
            key_risks=risks[:5],
            watchlist_matches=[alert.matched_watch.watch_item.name for alert in alert_report.alerts if alert.matched_watch][:5],
            collection_relevance=getattr(getattr(enriched, "collection_relevance", None), "collection_goal_advanced", ""),
            market_intelligence_summary=self._market_summary(enriched),
        )

    def analyze_candidates(self, candidates: Sequence[Any]) -> List[QuickDecisionSummary]:
        return [self.quick_decision(candidate) for candidate in candidates]

    def dashboard(self, candidates: Optional[Sequence[Any]] = None) -> MobileDashboard:
        decisions = self.analyze_candidates(candidates or [])
        alert_report = self.alert_engine.generate_alerts([_to_listing(candidate) for candidate in (candidates or [])])
        context = self.collection_context(candidates)
        return MobileDashboard(
            active_watchlists=[watchlist.name for watchlist in self.watchlists],
            high_priority_targets=context.active_targets[:5],
            recent_alerts=[f"{alert.alert_type}: {alert.candidate_title}" for alert in alert_report.alerts[:5]],
            recent_opportunities=[decision.candidate_title for decision in decisions[:5]],
            collection_priorities=context.collection_priorities,
            quick_decisions=decisions,
        )

    def field_work_mode(self, candidates: Sequence[Any], workflow_name: str = WORKFLOW_COIN_SHOW) -> FieldWorkMode:
        decisions = self.analyze_candidates(candidates)
        risk_flags = _dedupe(risk for decision in decisions for risk in decision.key_risks)
        buys = sum(1 for decision in decisions if decision.recommendation == "BUY")
        reviews = sum(1 for decision in decisions if decision.recommendation == "REVIEW")
        summary = f"{len(decisions)} candidate(s), {buys} BUY, {reviews} REVIEW. Use REVIEW when uncertain."
        return FieldWorkMode(workflow_name=workflow_name, quick_decisions=decisions, minimal_summary=summary, risk_flags=risk_flags)

    def generate_report(
        self,
        candidates: Optional[Sequence[Any]] = None,
        workflow_type: str = WORKFLOW_COIN_SHOW,
        location: str = "",
        photo_capture_sessions: Optional[Sequence[PhotoCaptureSession]] = None,
    ) -> MobileCompanionReport:
        session = self.start_session(workflow_type=workflow_type, location=location)
        workflow = next((item for item in self.workflows() if item.name == workflow_type), self.workflows()[0])
        candidates = list(candidates or [])
        decisions = self.analyze_candidates(candidates)
        dashboard = self.dashboard(candidates)
        context = self.collection_context(candidates)
        field_mode = FieldWorkMode(
            workflow_name=workflow.name,
            quick_decisions=decisions,
            minimal_summary=self.field_work_mode(candidates, workflow.name).minimal_summary,
            risk_flags=_dedupe(risk for decision in decisions for risk in decision.key_risks),
        )
        return MobileCompanionReport(
            session=session,
            workflow=workflow,
            dashboard=dashboard,
            collection_context=context,
            field_work_mode=field_mode,
            quick_decisions=decisions,
            photo_capture_report=PhotoCaptureReport(photo_capture_sessions) if photo_capture_sessions is not None else self.photo_capture_workflow.report(),
        )

    def run_field_test_snapshot(self):
        return ScenarioRunner(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
            self.watchlists,
        ).run_scenarios(default_field_test_scenarios()[:3])

    def _decision_reasons(self, enriched: Any, ranked: Any, alert_report: AlertReport) -> List[str]:
        reasons: List[str] = []
        if enriched:
            reasons.extend(getattr(enriched, "strengths", []) or [])
            relevance = getattr(enriched, "collection_relevance", None)
            if relevance:
                reasons.append(getattr(relevance, "collection_goal_advanced", ""))
                reasons.extend(getattr(relevance, "classifications", []) or [])
        if ranked:
            reasons.append(getattr(ranked, "collection_impact", ""))
        reasons.extend(alert.reason for alert in alert_report.alerts[:3])
        return _dedupe(reasons) or ["Existing intelligence recommends manual review."]

    def _decision_risks(self, enriched: Any, ranked: Any, alert_report: AlertReport) -> List[str]:
        risks: List[str] = []
        if enriched:
            risks.extend(getattr(enriched, "weaknesses", []) or [])
            risks.extend(getattr(enriched, "market_intelligence_warnings", []) or [])
            risk_summary = getattr(enriched, "risk_summary", "")
            if risk_summary:
                risks.append(f"Market risk: {risk_summary}")
        if ranked:
            risks.extend(getattr(ranked, "risk_flags", []) or [])
            if getattr(ranked, "counterargument", ""):
                risks.append(ranked.counterargument)
        risks.extend(alert.reason for alert in alert_report.alerts if alert.score.score < 45)
        return _dedupe(risks) or ["No major risk flags from existing engines."]

    def _market_summary(self, enriched: Any) -> str:
        if not enriched:
            return "Market intelligence unavailable."
        return (
            f"{enriched.deal_quality}; fair value guidance ${enriched.fair_value_estimate:.2f}; "
            f"confidence {enriched.opportunity_confidence}"
        )
