"""Automated local Market Intelligence enrichment for candidate listings.

This module reuses ``MarketIntelligenceEngine``. It does not fetch live prices,
scrape sources, call APIs, forecast markets, mutate collection data, or provide
investment advice.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from deal_hunter import DealListing
from deal_hunter_ranking import CandidatePool, DealHunterRankingReport, RankedDeal
from market_awareness import MarketAwarenessEngine
from market_intelligence import MarketIntelligenceEngine, MarketIntelligenceReport


REVIEW_CONFIDENCE_THRESHOLD = 45


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _dedupe(values: Iterable[str]) -> List[str]:
    output: List[str] = []
    seen = set()
    for value in values or []:
        text = _text(value)
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            output.append(text)
    return output


@dataclass
class FairValueEvidenceSummary:
    comparable_sales_count: int = 0
    market_awareness_records_used: int = 0
    evidence_quality: str = "Weak"
    evidence_gaps: List[str] = field(default_factory=list)
    confidence_impact: str = "Limited local evidence lowers confidence."

    @classmethod
    def from_market_report(cls, report: MarketIntelligenceReport) -> "FairValueEvidenceSummary":
        count = len(report.comparable_sales)
        quality = "Strong" if count >= 3 else "Moderate" if count >= 1 else "Weak"
        gaps = []
        if count == 0:
            gaps.append("No local comparable sales or observations were available.")
        if report.fair_value.evidence_count == 0:
            gaps.append("Fair value relies on internal guidance rather than direct comparable records.")
        return cls(
            comparable_sales_count=count,
            market_awareness_records_used=sum(1 for row in report.comparable_sales if "local observation" in row.sale_type.lower()),
            evidence_quality=quality,
            evidence_gaps=_dedupe(gaps),
            confidence_impact="Local evidence improves confidence." if count else "Limited local evidence lowers confidence.",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "comparable_sales_count": self.comparable_sales_count,
            "market_awareness_records_used": self.market_awareness_records_used,
            "evidence_quality": self.evidence_quality,
            "evidence_gaps": "; ".join(self.evidence_gaps),
            "confidence_impact": self.confidence_impact,
        }


@dataclass
class CollectionRelevanceSummary:
    collection_relevance_score: int = 0
    relevance_explanation: str = ""
    collection_goal_advanced: str = "No specific collection objective advanced."
    classifications: List[str] = field(default_factory=list)
    helps_collection: str = ""
    does_not_help_collection: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "collection_relevance_score": self.collection_relevance_score,
            "relevance_explanation": self.relevance_explanation,
            "collection_goal_advanced": self.collection_goal_advanced,
            "classifications": "; ".join(self.classifications),
            "helps_collection": self.helps_collection,
            "does_not_help_collection": self.does_not_help_collection,
        }


@dataclass
class MarketEnrichedCandidate:
    original_listing: DealListing
    original_recommendation: str
    market_report: MarketIntelligenceReport
    evidence_summary: FairValueEvidenceSummary
    collection_relevance: CollectionRelevanceSummary
    escalated_recommendation: str
    escalation_reason: str = ""
    market_intelligence_warnings: List[str] = field(default_factory=list)

    @property
    def deal_quality(self) -> str:
        return self.market_report.deal_quality.quality

    @property
    def fair_value_estimate(self) -> float:
        return self.market_report.fair_value.expected_value

    @property
    def opportunity_confidence(self) -> int:
        return self.market_report.confidence.score

    @property
    def risk_summary(self) -> str:
        return self.market_report.risk_summary.severity

    @property
    def strengths(self) -> List[str]:
        return list(self.market_report.strengths)

    @property
    def weaknesses(self) -> List[str]:
        return list(self.market_report.weaknesses)

    @property
    def counterargument(self) -> str:
        return self.market_report.counterargument

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.original_listing.title,
            "total_cost": self.original_listing.total_cost,
            "original_recommendation": self.original_recommendation,
            "escalated_recommendation": self.escalated_recommendation,
            "escalation_reason": self.escalation_reason,
            "deal_quality": self.deal_quality,
            "fair_value_estimate": self.fair_value_estimate,
            "opportunity_confidence": self.opportunity_confidence,
            "risk_severity": self.risk_summary,
            "collection_relevance_score": self.collection_relevance.collection_relevance_score,
            "collection_goal_advanced": self.collection_relevance.collection_goal_advanced,
            "classifications": "; ".join(self.collection_relevance.classifications),
            "strengths": "; ".join(self.strengths),
            "weaknesses": "; ".join(self.weaknesses),
            "counterargument": self.counterargument,
            "warnings": "; ".join(self.market_intelligence_warnings),
            **{f"evidence_{key}": value for key, value in self.evidence_summary.to_dict().items()},
        }


@dataclass
class MarketEnrichmentBatchReport:
    source_name: str
    candidates_processed: int = 0
    enriched_count: int = 0
    skipped_count: int = 0
    enriched_candidates: List[MarketEnrichedCandidate] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "generated_at": self.generated_at,
            "candidates_processed": self.candidates_processed,
            "enriched_count": self.enriched_count,
            "skipped_count": self.skipped_count,
            "warnings": "; ".join(self.warnings),
            "errors": "; ".join(self.errors),
            "enriched_candidates": [row.to_dict() for row in self.enriched_candidates],
        }

    def format_markdown(self) -> str:
        lines = [
            "# Market Intelligence Automation Report",
            "",
            f"- Source: {self.source_name}",
            f"- Generated: {self.generated_at}",
            f"- Candidates processed: {self.candidates_processed}",
            f"- Enriched candidates: {self.enriched_count}",
            f"- Skipped candidates: {self.skipped_count}",
            "- Pricing note: deterministic local guidance only; no live pricing, scraping, APIs, exchange-rate lookup, or investment advice.",
            "",
            "## Enriched Candidates",
            "",
        ]
        if not self.enriched_candidates:
            lines.append("- None.")
        for row in self.enriched_candidates:
            lines.extend([
                f"### {row.original_listing.title}",
                f"- Original recommendation: {row.original_recommendation}",
                f"- Enriched recommendation: {row.escalated_recommendation}",
                f"- Deal quality: {row.deal_quality}",
                f"- Confidence: {row.opportunity_confidence}",
                f"- Expected fair value CAD: {row.fair_value_estimate:.2f}",
                f"- Collection relevance: {row.collection_relevance.collection_relevance_score}/100",
                f"- Classifications: {', '.join(row.collection_relevance.classifications) or 'None'}",
                f"- Goal advanced: {row.collection_relevance.collection_goal_advanced}",
                f"- Helps collection: {row.collection_relevance.helps_collection}",
                f"- Does not help collection: {row.collection_relevance.does_not_help_collection}",
                f"- Evidence quality: {row.evidence_summary.evidence_quality}",
                f"- Counterargument: {row.counterargument}",
            ])
            if row.escalation_reason:
                lines.append(f"- Escalation: {row.escalation_reason}")
            if row.market_intelligence_warnings:
                lines.append(f"- Warnings: {'; '.join(row.market_intelligence_warnings)}")
            lines.append("")
        lines.extend(["## Batch Warnings", ""])
        lines.extend(f"- {warning}" for warning in self.warnings) if self.warnings else lines.append("- None.")
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in self.errors) if self.errors else lines.append("- None.")
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        fieldnames = [
            "title", "total_cost", "original_recommendation", "escalated_recommendation",
            "escalation_reason", "deal_quality", "fair_value_estimate", "opportunity_confidence",
            "risk_severity", "collection_relevance_score", "collection_goal_advanced",
            "classifications", "strengths", "weaknesses", "counterargument", "warnings",
            "evidence_comparable_sales_count", "evidence_market_awareness_records_used",
            "evidence_evidence_quality", "evidence_evidence_gaps", "evidence_confidence_impact",
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in self.enriched_candidates:
                writer.writerow(row.to_dict())
        return True


class MarketIntelligenceAutomationEngine:
    """Apply existing Market Intelligence consistently across candidate sources."""

    def __init__(
        self,
        collection_items: Iterable[Any],
        want_list_intents: Optional[Iterable[Any]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
        market_intelligence_engine: Optional[MarketIntelligenceEngine] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()
        self.market_intelligence_engine = market_intelligence_engine or MarketIntelligenceEngine(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
        )

    def enrich_candidate(self, candidate: Any, source_name: str = "Manual candidate") -> MarketEnrichedCandidate:
        listing, original_recommendation = self._candidate_to_listing(candidate)
        report = self.market_intelligence_engine.evaluate_listing(listing)
        evidence = FairValueEvidenceSummary.from_market_report(report)
        relevance = self._collection_relevance(report)
        enriched_recommendation, reason, warnings = self._escalate(original_recommendation, report, evidence, relevance)
        return MarketEnrichedCandidate(
            original_listing=listing,
            original_recommendation=original_recommendation,
            market_report=report,
            evidence_summary=evidence,
            collection_relevance=relevance,
            escalated_recommendation=enriched_recommendation,
            escalation_reason=reason,
            market_intelligence_warnings=warnings,
        )

    def enrich_candidates(self, candidates: Iterable[Any], source_name: str = "Candidate batch") -> MarketEnrichmentBatchReport:
        enriched: List[MarketEnrichedCandidate] = []
        errors: List[str] = []
        processed = 0
        for candidate in candidates or []:
            processed += 1
            try:
                enriched.append(self.enrich_candidate(candidate, source_name=source_name))
            except Exception as exc:
                errors.append(f"Candidate {processed}: {exc}")
        return MarketEnrichmentBatchReport(
            source_name=source_name,
            candidates_processed=processed,
            enriched_count=len(enriched),
            skipped_count=processed - len(enriched),
            enriched_candidates=enriched,
            warnings=_dedupe([warning for row in enriched for warning in row.market_intelligence_warnings]),
            errors=errors,
        )

    def enrich_candidate_pool(self, pool: CandidatePool, source_name: str = "CandidatePool") -> MarketEnrichmentBatchReport:
        return self.enrich_candidates(pool.listings, source_name)

    def enrich_ranking_report(self, report: DealHunterRankingReport, source_name: str = "Deal Hunter Ranking") -> MarketEnrichmentBatchReport:
        return self.enrich_candidates(report.ranked_deals, source_name)

    def enrich_live_batch(self, batch: Any, source_name: str = "Live listing batch") -> MarketEnrichmentBatchReport:
        return self.enrich_candidates(batch.listings, source_name or batch.source_name)

    def enrich_live_deal_hunter_report(self, report: Any, source_name: str = "Live Deal Hunter") -> MarketEnrichmentBatchReport:
        candidates = report.ranking_report.ranked_deals if report.ranking_report else []
        return self.enrich_candidates(candidates, source_name or report.source_name)

    def _candidate_to_listing(self, candidate: Any) -> Tuple[DealListing, str]:
        if isinstance(candidate, RankedDeal):
            return candidate.listing, candidate.recommendation
        if hasattr(candidate, "listing") and hasattr(candidate, "recommendation"):
            return candidate.listing, _text(candidate.recommendation) or "UNKNOWN"
        if hasattr(candidate, "to_deal_listing"):
            return candidate.to_deal_listing(), "UNKNOWN"
        if isinstance(candidate, DealListing):
            return candidate, "UNKNOWN"
        if isinstance(candidate, dict):
            if isinstance(candidate.get("listing"), DealListing):
                return candidate["listing"], _text(candidate.get("recommendation")) or "UNKNOWN"
            return DealListing.from_dict(candidate), _text(candidate.get("recommendation")) or "UNKNOWN"
        raise TypeError("Unsupported candidate type for market intelligence automation")

    def _collection_relevance(self, report: MarketIntelligenceReport) -> CollectionRelevanceSummary:
        result = report.deal_result
        status = result.collection_status.lower()
        title = result.listing.title.lower()
        reasons = " ".join(result.reasons).lower()
        classifications: List[str] = []
        score = max(0, min(100, int(result.collection_fit_score)))
        goal = "General collection fit"
        if "upgrade" in status:
            classifications.append("Upgrade")
            goal = "Upgrade opportunity"
        if "gap" in status:
            classifications.append("Collection Gap")
            goal = "Date-run or type gap reduction"
        if "want-list" in status or "want_list" in status or "explicit want_list" in reasons:
            classifications.append("Want-List Match")
            goal = "Explicit WANT_LIST target"
        if "same-grade" in status or "same grade" in status:
            classifications.append("Same-Grade Duplicate")
        if "lower-grade" in status or "lower grade" in status:
            classifications.append("Lower-Grade Duplicate")
        if "duplicate" in status and not any("Duplicate" in row for row in classifications):
            classifications.append("Same-Grade Duplicate")
        if "newfoundland" in title:
            goal = "Newfoundland completion or upgrade"
            score = min(100, score + 10)
        elif "1859" in title and ("large cent" in title or "1 cent" in title):
            goal = "1859 Canadian Large Cent variety target"
            score = min(100, score + 10)
        elif "canada" in title and any(token in title for token in ("5 cents", "10 cents", "25 cents", "50 cents", "silver", "dime", "quarter", "half dollar", "dollar")):
            goal = "Canadian silver expansion"
            score = min(100, score + 5)
        elif "banknote" in title or "bank note" in title:
            goal = "Canadian banknote target"
        if not classifications and score >= 45:
            classifications.append("General Collection Fit")
        if not classifications and report.deal_quality.quality in {"Excellent", "Good"}:
            classifications.append("Speculative Opportunity")
        if not classifications:
            classifications.append("Not Collection Relevant")
        helps = "Improves collection fit through " + ", ".join(classifications) + "."
        does_not = "Limited collection benefit if it is duplicate, low-confidence, or outside Adam priorities."
        if "Not Collection Relevant" in classifications:
            helps = "Does not clearly advance a tracked collection objective."
            does_not = "No clear gap, upgrade, WANT_LIST, or priority-series relevance was detected."
        return CollectionRelevanceSummary(
            collection_relevance_score=score,
            relevance_explanation=f"Based on Deal Hunter collection status: {result.collection_status}.",
            collection_goal_advanced=goal,
            classifications=_dedupe(classifications),
            helps_collection=helps,
            does_not_help_collection=does_not,
        )

    def _escalate(
        self,
        original_recommendation: str,
        report: MarketIntelligenceReport,
        evidence: FairValueEvidenceSummary,
        relevance: CollectionRelevanceSummary,
    ) -> Tuple[str, str, List[str]]:
        warnings = list(report.risk_summary.warnings)
        reason = ""
        final = original_recommendation or report.deal_result.recommendation
        low_confidence = report.confidence.score < REVIEW_CONFIDENCE_THRESHOLD
        weak_evidence = evidence.evidence_quality == "Weak" and report.fair_value.evidence_count == 0
        high_risk = report.risk_summary.severity == "High"
        weak_relevance = "Not Collection Relevant" in relevance.classifications
        if low_confidence or high_risk or (weak_evidence and weak_relevance):
            final = "REVIEW"
            triggers = []
            if low_confidence:
                triggers.append("low Market Intelligence confidence")
            if high_risk:
                triggers.append("high market risk")
            if weak_evidence and weak_relevance:
                triggers.append("weak valuation evidence and weak collection relevance")
            reason = "Escalated to REVIEW because " + ", ".join(triggers) + "."
            warnings.append(reason)
        if weak_evidence:
            warnings.append("Fair value evidence is weak; no live price retrieval was performed.")
        return final, reason, _dedupe(warnings)
