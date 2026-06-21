"""Deterministic local market intelligence for candidate listings.

This module uses supplied listings, local Market Awareness records, and manual
comparable sales only. It does not scrape, fetch, call APIs, or claim live
market-pricing accuracy.
"""

import csv
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from deal_hunter import (
    DealHunter,
    DealHunterResult,
    DealListing,
    RISK_HIGH_SHIPPING,
    RISK_LOT_LISTING,
    RISK_NEEDS_MANUAL_REVIEW,
    RISK_NON_COLLECTION_RELEVANT,
    RISK_POSSIBLE_DAMAGE,
    RISK_RAW_OVERGRADED,
    RISK_UNCLEAR_CURRENCY,
    RISK_UNCLEAR_GRADE,
)
from market_awareness import MarketAwarenessEngine
from opportunity_engine import OpportunityEngine


QUALITY_EXCELLENT = "Excellent"
QUALITY_GOOD = "Good"
QUALITY_FAIR = "Fair"
QUALITY_WEAK = "Weak"
QUALITY_OVERPRICED = "Overpriced"
QUALITY_UNKNOWN = "Unknown"


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _money(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    cleaned = str(value).strip().replace("$", "").replace(",", "")
    return round(float(cleaned), 2) if cleaned else 0.0


def _dedupe(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


@dataclass
class ComparableSale:
    item_name: str
    amount: float
    source: str = "Manual comp"
    sale_type: str = "user-entered comp"
    date: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        self.item_name = str(self.item_name or "").strip()
        self.amount = _money(self.amount)
        self.source = str(self.source or "").strip()
        self.sale_type = str(self.sale_type or "").strip()
        self.date = str(self.date or "").strip()
        self.notes = str(self.notes or "").strip()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_name": self.item_name,
            "amount": self.amount,
            "source": self.source,
            "sale_type": self.sale_type,
            "date": self.date,
            "notes": self.notes,
        }


@dataclass
class FairValueEstimate:
    conservative_value: float = 0.0
    expected_value: float = 0.0
    aggressive_value: float = 0.0
    evidence_count: int = 0
    basis: str = "No local valuation evidence."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conservative_value": self.conservative_value,
            "expected_value": self.expected_value,
            "aggressive_value": self.aggressive_value,
            "evidence_count": self.evidence_count,
            "basis": self.basis,
        }


@dataclass
class OpportunityConfidence:
    score: int = 0
    collection_fit: int = 0
    duplicate_penalty: int = 0
    upgrade_potential: int = 0
    gap_impact: int = 0
    data_completeness: int = 0
    risk_penalty: int = 0
    valuation_evidence: int = 0
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "collection_fit": self.collection_fit,
            "duplicate_penalty": self.duplicate_penalty,
            "upgrade_potential": self.upgrade_potential,
            "gap_impact": self.gap_impact,
            "data_completeness": self.data_completeness,
            "risk_penalty": self.risk_penalty,
            "valuation_evidence": self.valuation_evidence,
            "explanation": self.explanation,
        }


@dataclass
class RiskSummary:
    risk_factors: List[str] = field(default_factory=list)
    risk_score: int = 0
    severity: str = "Low"
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_factors": "; ".join(self.risk_factors),
            "risk_score": self.risk_score,
            "severity": self.severity,
            "warnings": "; ".join(self.warnings),
        }


@dataclass
class DealQuality:
    quality: str
    reasoning: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"quality": self.quality, "reasoning": "; ".join(self.reasoning)}


@dataclass
class MarketIntelligenceReport:
    listing: DealListing
    deal_result: DealHunterResult
    deal_quality: DealQuality
    confidence: OpportunityConfidence
    fair_value: FairValueEstimate
    risk_summary: RiskSummary
    comparable_sales: List[ComparableSale] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    counterargument: str = ""
    buy_rationale: str = ""
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "title": self.listing.title,
            "total_cost": self.listing.total_cost,
            "deal_quality": self.deal_quality.quality,
            "confidence_score": self.confidence.score,
            "conservative_value": self.fair_value.conservative_value,
            "expected_value": self.fair_value.expected_value,
            "aggressive_value": self.fair_value.aggressive_value,
            "evidence_count": self.fair_value.evidence_count,
            "collection_status": self.deal_result.collection_status,
            "deal_hunter_recommendation": self.deal_result.recommendation,
            "priority_score": self.deal_result.priority_score,
            "collection_fit_score": self.deal_result.collection_fit_score,
            "risk_score": self.risk_summary.risk_score,
            "risk_severity": self.risk_summary.severity,
            "strengths": "; ".join(self.strengths),
            "weaknesses": "; ".join(self.weaknesses),
            "risk_factors": "; ".join(self.risk_summary.risk_factors),
            "counterargument": self.counterargument,
            "buy_rationale": self.buy_rationale,
        }

    def format_markdown(self) -> str:
        lines = [
            "# Market Intelligence Report",
            "",
            f"- Generated: {self.generated_at}",
            "- Pricing note: deterministic local guidance only; not live market pricing or appraisal.",
            f"- Listing: {self.listing.title}",
            f"- Total cost CAD: {self.listing.total_cost:.2f}",
            f"- Deal quality: {self.deal_quality.quality}",
            f"- Confidence score: {self.confidence.score}",
            f"- Fair value range CAD: {self.fair_value.conservative_value:.2f} - {self.fair_value.aggressive_value:.2f}",
            f"- Expected value CAD: {self.fair_value.expected_value:.2f}",
            f"- Valuation basis: {self.fair_value.basis}",
            f"- Deal Hunter recommendation: {self.deal_result.recommendation}",
            f"- Collection status: {self.deal_result.collection_status}",
            f"- Counterargument: {self.counterargument}",
            f"- Buy rationale: {self.buy_rationale}",
            "",
            "## Strengths",
            "",
        ]
        lines.extend(f"- {row}" for row in self.strengths) if self.strengths else lines.append("- None.")
        lines.extend(["", "## Weaknesses", ""])
        lines.extend(f"- {row}" for row in self.weaknesses) if self.weaknesses else lines.append("- None.")
        lines.extend(["", "## Risk Factors", ""])
        lines.extend(f"- {row}" for row in self.risk_summary.risk_factors) if self.risk_summary.risk_factors else lines.append("- Normal manual review.")
        lines.extend(["", "## Comparable Sales", ""])
        if not self.comparable_sales:
            lines.append("- No local comparable sales used.")
        for comp in self.comparable_sales:
            lines.append(f"- {comp.item_name}: ${comp.amount:.2f} ({comp.sale_type}, {comp.source})")
        lines.extend(["", "## Deal Quality Reasoning", ""])
        lines.extend(f"- {row}" for row in self.deal_quality.reasoning) if self.deal_quality.reasoning else lines.append("- No quality reasoning generated.")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(self.to_dict().keys()))
            writer.writeheader()
            writer.writerow(self.to_dict())
        return True


class MarketIntelligenceEngine:
    """Evaluate local deal quality without live pricing or external retrieval."""

    def __init__(
        self,
        collection_items: Iterable[Any],
        want_list_intents: Optional[Iterable[Any]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()

    def evaluate_listing(
        self,
        listing: DealListing,
        comparable_sales: Optional[Iterable[ComparableSale]] = None,
    ) -> MarketIntelligenceReport:
        deal_result = DealHunter(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
        ).analyze_listing(listing)
        OpportunityEngine(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
        ).generate_report(deal_hunter_results=[deal_result], limit=1)
        comps = self._local_comparables(deal_result) + list(comparable_sales or [])
        fair_value = self._fair_value(deal_result, comps)
        risk_summary = self._risk_summary(deal_result)
        confidence = self._confidence(deal_result, fair_value, risk_summary)
        deal_quality = self._deal_quality(deal_result, fair_value, confidence, risk_summary)
        strengths = self._strengths(deal_result, fair_value, confidence)
        weaknesses = self._weaknesses(deal_result, fair_value, risk_summary)
        counterargument = self._counterargument(deal_result, deal_quality, fair_value, risk_summary)
        buy_rationale = self._buy_rationale(deal_result, deal_quality, confidence, fair_value)
        return MarketIntelligenceReport(
            listing=listing,
            deal_result=deal_result,
            deal_quality=deal_quality,
            confidence=confidence,
            fair_value=fair_value,
            risk_summary=risk_summary,
            comparable_sales=comps,
            strengths=strengths,
            weaknesses=weaknesses,
            counterargument=counterargument,
            buy_rationale=buy_rationale,
        )

    def _local_comparables(self, deal_result: DealHunterResult) -> List[ComparableSale]:
        parsed = deal_result.parsed_candidate
        comps = []
        for record in getattr(self.market_awareness_engine, "observations", []):
            if (
                self._norm(record.country) == self._norm(parsed.country)
                and self._norm(record.denomination) == self._norm(parsed.denomination)
                and str(record.year or "").strip() == str(parsed.year or "").strip()
            ):
                comps.append(ComparableSale(
                    item_name=record.item_name,
                    amount=record.total_observed_cost,
                    source=record.source or "Market Awareness",
                    sale_type="local observation",
                    date=record.date_observed,
                    notes=record.notes,
                ))
        return comps

    @staticmethod
    def _fair_value(deal_result: DealHunterResult, comps: List[ComparableSale]) -> FairValueEstimate:
        values = sorted(comp.amount for comp in comps if comp.amount > 0)
        if values:
            expected = round(sum(values) / len(values), 2)
            return FairValueEstimate(
                conservative_value=round(values[0] * 0.95, 2),
                expected_value=expected,
                aggressive_value=round(values[-1] * 1.05, 2),
                evidence_count=len(values),
                basis="Local comparable sales and observations.",
            )
        if deal_result.max_rational_price > 0:
            basis = deal_result.max_rational_price
            return FairValueEstimate(
                conservative_value=round(basis * 0.85, 2),
                expected_value=round(basis, 2),
                aggressive_value=round(basis * 1.15, 2),
                evidence_count=0,
                basis="Internal max rational price; no local comparable sales.",
            )
        if deal_result.listing.total_cost > 0:
            basis = deal_result.listing.total_cost
            return FairValueEstimate(
                conservative_value=round(basis * 0.8, 2),
                expected_value=round(basis, 2),
                aggressive_value=round(basis * 1.2, 2),
                evidence_count=0,
                basis="Listing total used as placeholder because no local valuation evidence exists.",
            )
        return FairValueEstimate()

    @staticmethod
    def _risk_summary(deal_result: DealHunterResult) -> RiskSummary:
        factors = []
        flag_map = {
            RISK_HIGH_SHIPPING: "High shipping",
            RISK_UNCLEAR_GRADE: "Unclear grade",
            RISK_RAW_OVERGRADED: "Raw grade risk",
            RISK_LOT_LISTING: "Lot listing uncertainty",
            RISK_POSSIBLE_DAMAGE: "Damage or cleaning risk",
            RISK_UNCLEAR_CURRENCY: "Unclear currency",
            RISK_NON_COLLECTION_RELEVANT: "Weak collection relevance",
            RISK_NEEDS_MANUAL_REVIEW: "Manual review required",
        }
        for flag in deal_result.risk_flags:
            factors.append(flag_map.get(flag, flag))
        if "duplicate" in deal_result.collection_status.lower():
            factors.append("Duplicate ownership")
        if not deal_result.parsed_candidate.grade:
            factors.append("Low-information listing")
        severity = "Low"
        if deal_result.risk_score >= 55 or RISK_NEEDS_MANUAL_REVIEW in deal_result.risk_flags:
            severity = "High"
        elif deal_result.risk_score >= 25 or factors:
            severity = "Medium"
        return RiskSummary(_dedupe(factors), deal_result.risk_score, severity, list(deal_result.warnings))

    @staticmethod
    def _confidence(deal_result: DealHunterResult, fair_value: FairValueEstimate, risk_summary: RiskSummary) -> OpportunityConfidence:
        collection_fit = min(25, max(0, deal_result.collection_fit_score // 4))
        duplicate_penalty = -20 if "duplicate" in deal_result.collection_status.lower() else 0
        upgrade_potential = 15 if "upgrade" in deal_result.collection_status.lower() else 0
        gap_impact = 15 if "gap" in deal_result.collection_status.lower() or "want-list" in deal_result.collection_status.lower() else 0
        data_completeness = 20
        if not deal_result.parsed_candidate.grade:
            data_completeness -= 7
        if not deal_result.parsed_candidate.country or not deal_result.parsed_candidate.denomination or not deal_result.parsed_candidate.year:
            data_completeness -= 8
        risk_penalty = min(30, deal_result.risk_score // 3)
        valuation_evidence = min(20, fair_value.evidence_count * 7)
        score = 40 + collection_fit + upgrade_potential + gap_impact + data_completeness + valuation_evidence + duplicate_penalty - risk_penalty
        score = max(0, min(100, int(round(score))))
        explanation = "Confidence is based on collection fit, duplicate/upgrade/gap status, data completeness, risk, and local valuation evidence."
        return OpportunityConfidence(score, collection_fit, duplicate_penalty, upgrade_potential, gap_impact, max(0, data_completeness), risk_penalty, valuation_evidence, explanation)

    @staticmethod
    def _deal_quality(
        deal_result: DealHunterResult,
        fair_value: FairValueEstimate,
        confidence: OpportunityConfidence,
        risk_summary: RiskSummary,
    ) -> DealQuality:
        total = deal_result.listing.total_cost
        reasons = []
        if total <= 0 or fair_value.expected_value <= 0:
            return DealQuality(QUALITY_UNKNOWN, ["Missing price or valuation evidence."])
        if "duplicate" in deal_result.collection_status.lower() and deal_result.recommendation == "PASS":
            return DealQuality(QUALITY_WEAK, ["Duplicate ownership limits opportunity quality."])
        if risk_summary.severity == "High" and deal_result.recommendation == "REVIEW":
            return DealQuality(QUALITY_WEAK, ["Material risk factors require manual review."])
        if total <= fair_value.conservative_value and confidence.score >= 70 and risk_summary.severity != "High":
            reasons.append("Total cost is at or below conservative local value estimate.")
            reasons.append("Confidence is strong enough to treat this as a high-quality deal.")
            return DealQuality(QUALITY_EXCELLENT, reasons)
        if total <= fair_value.expected_value and confidence.score >= 55 and risk_summary.severity != "High":
            return DealQuality(QUALITY_GOOD, ["Total cost is at or below expected local value estimate."])
        if total <= fair_value.aggressive_value:
            return DealQuality(QUALITY_FAIR, ["Total cost is within the aggressive value band but not clearly cheap."])
        if total > fair_value.aggressive_value:
            return DealQuality(QUALITY_OVERPRICED, ["Total cost exceeds the aggressive local value estimate."])
        return DealQuality(QUALITY_UNKNOWN, ["Deal quality could not be classified deterministically."])

    @staticmethod
    def _strengths(deal_result: DealHunterResult, fair_value: FairValueEstimate, confidence: OpportunityConfidence) -> List[str]:
        strengths = []
        if deal_result.collection_fit_score >= 55:
            strengths.append("Strong collection fit")
        if "upgrade" in deal_result.collection_status.lower():
            strengths.append("Upgrade potential")
        if "gap" in deal_result.collection_status.lower() or "want-list" in deal_result.collection_status.lower():
            strengths.append("Collection gap or WANT_LIST relevance")
        if fair_value.evidence_count:
            strengths.append("Local comparable evidence available")
        if confidence.score >= 70:
            strengths.append("High confidence")
        return _dedupe(strengths)

    @staticmethod
    def _weaknesses(deal_result: DealHunterResult, fair_value: FairValueEstimate, risk_summary: RiskSummary) -> List[str]:
        weaknesses = []
        if fair_value.evidence_count == 0:
            weaknesses.append("No local comparable sales")
        if deal_result.listing.total_cost > fair_value.aggressive_value > 0:
            weaknesses.append("Asking total exceeds aggressive value band")
        if "duplicate" in deal_result.collection_status.lower():
            weaknesses.append("Duplicate ownership")
        weaknesses.extend(risk_summary.risk_factors)
        return _dedupe(weaknesses)

    @staticmethod
    def _counterargument(deal_result: DealHunterResult, deal_quality: DealQuality, fair_value: FairValueEstimate, risk_summary: RiskSummary) -> str:
        points = []
        if fair_value.evidence_count == 0:
            points.append("value band lacks local comparable-sale evidence")
        if risk_summary.risk_factors:
            points.append("risk factors require manual review")
        if deal_quality.quality in {QUALITY_FAIR, QUALITY_WEAK, QUALITY_OVERPRICED, QUALITY_UNKNOWN}:
            points.append(f"deal quality is {deal_quality.quality.lower()}")
        if deal_result.counterargument:
            points.append(deal_result.counterargument)
        return "; ".join(_dedupe(points)) if points else "Normal manual review still applies before purchase."

    @staticmethod
    def _buy_rationale(deal_result: DealHunterResult, deal_quality: DealQuality, confidence: OpportunityConfidence, fair_value: FairValueEstimate) -> str:
        if deal_result.recommendation not in {"BUY", "NEGOTIATE", "WATCH"}:
            return "No buy rationale: Deal Hunter recommendation is not positive."
        parts = [f"Deal Hunter says {deal_result.recommendation}", f"deal quality is {deal_quality.quality}", f"confidence is {confidence.score}/100"]
        if fair_value.expected_value > 0:
            parts.append(f"expected local value estimate is ${fair_value.expected_value:.2f}")
        return "; ".join(parts) + "."

    @staticmethod
    def _norm(value: str) -> str:
        return " ".join(str(value or "").strip().lower().split())
