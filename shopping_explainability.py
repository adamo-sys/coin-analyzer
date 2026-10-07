"""Collector-readable explanations for existing shopping recommendations.

This module does not make recommendations. It translates existing Smart
Shopping, Listing Analyzer, Acquisition Workflow, and Acquisition Impact
outputs into auditable reasons.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class RecommendationConfidence:
    """Deterministic confidence label and explanation."""

    level: str
    score: Optional[int]
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "score": self.score,
            "explanation": self.explanation,
        }


@dataclass
class RecommendationExplanation:
    """Primary and supporting reasons for one recommendation."""

    recommendation: str
    confidence: RecommendationConfidence
    primary_reasons: List[str] = field(default_factory=list)
    supporting_reasons: List[str] = field(default_factory=list)
    impact_summary: str = ""
    warnings: List[str] = field(default_factory=list)
    collector_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation": self.recommendation,
            "confidence": self.confidence.to_dict(),
            "primary_reasons": list(self.primary_reasons),
            "supporting_reasons": list(self.supporting_reasons),
            "impact_summary": self.impact_summary,
            "warnings": list(self.warnings),
            "collector_notes": list(self.collector_notes),
        }


@dataclass
class ExplainableRecommendationReport:
    """Exportable collector-facing recommendation explanation."""

    item_name: str
    explanation: RecommendationExplanation
    source: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_name": self.item_name,
            "source": self.source,
            **self.explanation.to_dict(),
            "details": dict(self.details),
        }

    def format_markdown(self) -> str:
        explanation = self.explanation
        lines = [
            "# Recommendation Explanation",
            "",
            f"- Item: {self.item_name or 'Unknown item'}",
            f"- Source: {self.source or 'Existing recommendation output'}",
            f"- Recommendation: {explanation.recommendation}",
            f"- Confidence: {explanation.confidence.level} ({self._display(explanation.confidence.score)})",
            f"- Confidence basis: {explanation.confidence.explanation}",
            "",
            "## Primary Reasons",
            "",
        ]
        lines.extend(f"- {reason}" for reason in explanation.primary_reasons) if explanation.primary_reasons else lines.append("- No primary reasons available.")
        lines.extend(["", "## Supporting Reasons", ""])
        lines.extend(f"- {reason}" for reason in explanation.supporting_reasons) if explanation.supporting_reasons else lines.append("- No supporting reasons available.")
        lines.extend(["", "## Impact Summary", ""])
        lines.append(f"- {explanation.impact_summary or 'No impact summary available.'}")
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in explanation.warnings) if explanation.warnings else lines.append("- None")
        lines.extend(["", "## Collector Notes", ""])
        lines.extend(f"- {note}" for note in explanation.collector_notes) if explanation.collector_notes else lines.append("- None")
        if self.details:
            lines.extend(["", "## Supplied Values", ""])
            lines.extend(f"- {key}: {self._display(value)}" for key, value in self.details.items())
        return "\n".join(lines) + "\n"

    @staticmethod
    def _display(value: Any) -> str:
        return "unavailable" if value is None else str(value)

    def export_markdown(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_markdown())
            return True
        except Exception as exc:
            print(f"Error exporting explanation markdown: {exc}")
            return False

    def export_csv(self, output_path: str) -> bool:
        try:
            explanation = self.explanation
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "item_name",
                    "source",
                    "recommendation",
                    "confidence_level",
                    "confidence_score",
                    "confidence_explanation",
                    "primary_reasons",
                    "supporting_reasons",
                    "impact_summary",
                    "warnings",
                    "collector_notes",
                ] + list(self.details))
                writer.writeheader()
                writer.writerow({
                    "item_name": self.item_name,
                    "source": self.source,
                    "recommendation": explanation.recommendation,
                    "confidence_level": explanation.confidence.level,
                    "confidence_score": self._display(explanation.confidence.score),
                    "confidence_explanation": explanation.confidence.explanation,
                    "primary_reasons": "; ".join(explanation.primary_reasons),
                    "supporting_reasons": "; ".join(explanation.supporting_reasons),
                    "impact_summary": explanation.impact_summary,
                    "warnings": "; ".join(explanation.warnings),
                    "collector_notes": "; ".join(explanation.collector_notes),
                    **{key: self._display(value) for key, value in self.details.items()},
                })
            return True
        except Exception as exc:
            print(f"Error exporting explanation CSV: {exc}")
            return False


class ShoppingExplanationEngine:
    """Explain existing recommendation outputs without changing them."""

    def explain_shopping_recommendation(self, recommendation: Any) -> ExplainableRecommendationReport:
        status = self._status(getattr(recommendation, "recommendation_status", ""))
        acquisition = getattr(recommendation, "acquisition_decision", None)
        impact = getattr(recommendation, "impact_report", None)
        if self._unresolved(recommendation, acquisition, impact):
            status = "REVIEW"
        warnings = self._dedupe(list(getattr(recommendation, "warnings", []) or []) + list(getattr(acquisition, "warning_flags", []) or []))
        primary = self._primary_reasons(
            status,
            acquisition=acquisition,
            impact=impact,
            existing_reasons=getattr(recommendation, "reasons", []) or [],
            total_cost=getattr(recommendation, "total_cost", None),
            max_rational_price=getattr(recommendation, "max_rational_price", None),
        )
        supporting = self._supporting_reasons(
            acquisition=acquisition,
            impact=impact,
            existing_reasons=getattr(recommendation, "reasons", []) or [],
            market_context=str(getattr(recommendation, "market_context", "") or ""),
            unresolved=status == "REVIEW",
        )
        confidence = self._confidence(status, getattr(acquisition, "confidence_score", None), warnings)
        explanation = RecommendationExplanation(
            recommendation=status,
            confidence=confidence,
            primary_reasons=primary,
            supporting_reasons=supporting,
            impact_summary=self._impact_summary(impact, recommendation),
            warnings=warnings,
            collector_notes=self._collector_notes(status, acquisition, impact),
        )
        return ExplainableRecommendationReport(
            item_name=str(getattr(recommendation, "item_name", "") or ""),
            explanation=explanation,
            source=str(getattr(recommendation, "source", "") or "Smart Shopping Assistant"),
            details=self._details(recommendation, acquisition, impact, status),
        )

    def explain_listing_analysis(self, result: Any) -> ExplainableRecommendationReport:
        acquisition = getattr(result, "acquisition_decision", None)
        impact = getattr(result, "acquisition_impact_report", None)
        status = self._status(getattr(result, "recommendation", "") or getattr(acquisition, "recommendation", ""))
        if self._unresolved(result, acquisition, impact):
            status = "REVIEW"
        warnings = self._dedupe(list(getattr(result, "warnings", []) or []) + list(getattr(acquisition, "warning_flags", []) or []))
        primary = self._primary_reasons(
            status,
            acquisition=acquisition,
            impact=impact,
            existing_reasons=getattr(result, "recommendation_reasoning", []) or [],
            total_cost=getattr(getattr(result, "listing", None), "total_cost", None),
            max_rational_price=getattr(result, "max_rational_price", None),
        )
        supporting = self._supporting_reasons(
            acquisition=acquisition,
            impact=impact,
            existing_reasons=getattr(result, "recommendation_reasoning", []) or [],
            market_context=str(getattr(impact, "market_context_summary", "") or ""),
            unresolved=status == "REVIEW",
        )
        confidence = self._confidence(status, getattr(acquisition, "confidence_score", None), warnings)
        explanation = RecommendationExplanation(
            recommendation=status,
            confidence=confidence,
            primary_reasons=primary,
            supporting_reasons=supporting,
            impact_summary=self._impact_summary(impact, result),
            warnings=warnings,
            collector_notes=self._collector_notes(status, acquisition, impact),
        )
        listing = getattr(result, "listing", None)
        return ExplainableRecommendationReport(
            item_name=str(getattr(listing, "title", "") or getattr(result, "item_name", "") or ""),
            explanation=explanation,
            source="Listing Analyzer",
            details=self._details(result, acquisition, impact, status),
        )

    def explain_acquisition_decision(
        self,
        decision: Any,
        impact_report: Optional[Any] = None,
        item_name: str = "",
    ) -> ExplainableRecommendationReport:
        status = self._status(getattr(decision, "recommendation", ""))
        if self._unresolved(decision, impact_report):
            status = "REVIEW"
        warnings = list(getattr(decision, "warning_flags", []) or [])
        primary = self._primary_reasons(
            status,
            acquisition=decision,
            impact=impact_report,
            existing_reasons=list(getattr(decision, "priority_reasons", []) or []),
            total_cost=getattr(decision, "asking_price", None),
            max_rational_price=getattr(decision, "max_rational_price", None),
        )
        supporting = self._supporting_reasons(
            acquisition=decision,
            impact=impact_report,
            existing_reasons=list(getattr(decision, "priority_reasons", []) or []),
            market_context=str(getattr(impact_report, "market_context_summary", "") or ""),
            unresolved=status == "REVIEW",
        )
        explanation = RecommendationExplanation(
            recommendation=status,
            confidence=self._confidence(status, getattr(decision, "confidence_score", None), warnings),
            primary_reasons=primary,
            supporting_reasons=supporting,
            impact_summary=self._impact_summary(impact_report, decision),
            warnings=warnings,
            collector_notes=self._collector_notes(status, decision, impact_report),
        )
        return ExplainableRecommendationReport(
            item_name=item_name,
            explanation=explanation,
            source="Acquisition Workflow",
            details=self._details(decision, decision, impact_report, status),
        )

    def _primary_reasons(
        self,
        status: str,
        acquisition: Optional[Any],
        impact: Optional[Any],
        existing_reasons: Iterable[str],
        total_cost: Optional[float],
        max_rational_price: Optional[float],
    ) -> List[str]:
        reasons: List[str] = []
        ci_status = str(getattr(acquisition, "collection_intelligence_status", "") or "")
        want_status = str(getattr(acquisition, "want_list_status", "") or "")
        upgrade_status = str(getattr(acquisition, "upgrade_status", "") or "")

        if status == "REVIEW":
            return [
                "Review required: issue equivalence unresolved",
                "Ownership unresolved",
                "Duplicate unresolved",
                "Upgrade unresolved",
            ]

        if status in {"BUY", "STRONG BUY"}:
            if want_status == "ON_WANT_LIST":
                reasons.append("Explicit WANT_LIST target")
            if "COLLECTION_GAP" in ci_status:
                reasons.append("Fills a collection gap")
            if "BETTER_GRADE_UPGRADE" in ci_status or upgrade_status == "UPGRADE":
                reasons.append("Better-grade upgrade candidate")
            if impact and getattr(impact, "impact_score", 0):
                reasons.append("Positive acquisition impact")
            if max_rational_price and total_cost and total_cost <= max_rational_price:
                reasons.append("Asking price is at or below max rational price")
            if ci_status and ci_status not in {"SAME_GRADE_DUPLICATE", "LOWER_GRADE_DUPLICATE", "NOT_RELEVANT"}:
                reasons.append("Not blocked by duplicate or downgrade logic")
        elif status == "PASS":
            if "SAME_GRADE_DUPLICATE" in ci_status:
                reasons.append("Same-grade duplicate")
            if "LOWER_GRADE_DUPLICATE" in ci_status:
                reasons.append("Lower-grade duplicate")
            if "ALREADY_OWNED" in ci_status:
                reasons.append("Already owned")
            if "NOT_RELEVANT" in ci_status:
                reasons.append("No meaningful collection impact")
            if max_rational_price == 0:
                reasons.append("Max rational price is zero for this candidate")
            if total_cost and max_rational_price and total_cost > max_rational_price * 1.75:
                reasons.append("Poor asking price relative to max rational price")
        elif status == "WATCH":
            reasons.append("Interesting but not decisive")
            if total_cost is None or total_cost <= 0:
                reasons.append("Requires asking price before stronger recommendation")
            if max_rational_price and total_cost and total_cost > max_rational_price:
                reasons.append("Price is above max rational price")
        elif status == "NEGOTIATE":
            reasons.append("Relevant target but price needs work")
            if max_rational_price and total_cost and total_cost > max_rational_price:
                reasons.append("Asking price is above max rational price")
        # Free text is descriptive context, never authority for a primary claim.
        return self._dedupe(reasons) or ["Existing recommendation output did not provide a primary reason."]

    def _supporting_reasons(
        self,
        acquisition: Optional[Any],
        impact: Optional[Any],
        existing_reasons: Iterable[str],
        market_context: str = "",
        unresolved: bool = False,
    ) -> List[str]:
        reasons = []
        if unresolved:
            # Preserve only the established independent interest labels. Neither
            # retained raw intelligence nor prose can restore contained advice.
            interest_labels = {
                "High-Priority Series: Newfoundland",
                "High-Priority Series: 1859 Canadian Large Cent",
                "High-Priority Series: Canadian silver",
                "Low-priority world base-metal candidate",
            }
            reasons.extend(reason for reason in getattr(acquisition, "priority_reasons", []) or []
                           if reason in interest_labels)
            if getattr(acquisition, "want_list_status", "") == "ON_WANT_LIST":
                reasons.append("Explicit WANT_LIST interest; issue equivalence remains unresolved")
            if market_context and market_context != "No local observation context available.":
                reasons.append(market_context)
            return self._dedupe(reasons)
        for reason in existing_reasons:
            if reason and reason not in reasons:
                reasons.append(str(reason))
        if acquisition:
            for reason in getattr(acquisition, "priority_reasons", []) or []:
                if reason and reason not in reasons:
                    reasons.append(str(reason))
            if getattr(acquisition, "owned_current_match_summary", ""):
                reasons.append(str(getattr(acquisition, "owned_current_match_summary")))
        if impact:
            for reason in getattr(impact, "recommendation_reasoning", []) or []:
                if reason and reason not in reasons:
                    reasons.append(str(reason))
            if getattr(impact, "quality_delta", 0):
                reasons.append(f"Quality score changes {self._signed(getattr(impact, 'quality_delta', 0))}")
            if getattr(impact, "completion_delta", 0):
                reasons.append(f"Series completion changes {self._signed(getattr(impact, 'completion_delta', 0))}%")
            if getattr(impact, "series_name", ""):
                reasons.append(f"Series context: {getattr(impact, 'series_name')}")
        if market_context and market_context != "No local observation context available.":
            reasons.append(market_context)
        return self._dedupe(reasons)

    def _confidence(self, status: str, score: Optional[int], warnings: List[str]) -> RecommendationConfidence:
        if score is None:
            return RecommendationConfidence("Unavailable", None, "Classification confidence unavailable; review required.")
        score = int(score)
        if status == "REVIEW" or score < 70:
            return RecommendationConfidence("Low", score, "Manual review or low classification confidence limits certainty.")
        if warnings or status in {"WATCH", "NEGOTIATE"} or score < 85:
            return RecommendationConfidence("Medium", score, "Recommendation is useful but has warnings, price uncertainty, or moderate confidence.")
        return RecommendationConfidence("High", score, "Existing engines produced a decisive recommendation with high classification confidence.")

    def _impact_summary(self, impact: Optional[Any], source: Any) -> str:
        acquisition = getattr(source, "acquisition_decision", source)
        if self._unresolved(source, acquisition, impact):
            return "Impact score unavailable (collection impact unresolved); quality unavailable; series completion unavailable; upgrade impact unresolved"
        if not impact:
            return "Acquisition impact unavailable: no impact report was supplied."
        completion = getattr(impact, "completion_delta", None)
        parts = [
            f"Impact score {ExplainableRecommendationReport._display(getattr(impact, 'impact_score', None))} ({getattr(impact, 'collection_impact', None) or 'unresolved'})",
            f"quality {self._signed(getattr(impact, 'quality_delta', None))}",
            f"series completion {self._signed(completion)}{'%' if completion is not None else ''}",
        ]
        if getattr(impact, "want_list_impact", ""):
            parts.append(f"WANT_LIST impact: {getattr(impact, 'want_list_impact')}")
        if getattr(impact, "upgrade_impact", ""):
            parts.append(f"upgrade impact: {getattr(impact, 'upgrade_impact')}")
        return "; ".join(parts)

    def _collector_notes(self, status: str, acquisition: Optional[Any], impact: Optional[Any]) -> List[str]:
        notes = []
        if status == "PASS":
            notes.append("Passing preserves budget for higher-impact opportunities.")
        elif status == "WATCH":
            notes.append("Watch for better price, clearer attribution, or stronger collection impact.")
        elif status == "NEGOTIATE":
            notes.append("Negotiate toward the max rational price before buying.")
        elif status == "REVIEW":
            notes.append("Confirm attribution, grade, and certification before making a purchase decision.")
            notes.append("No supported best purchase can be determined from current evidence for this candidate; identity-dependent ranking unavailable.")
        elif status in {"BUY", "STRONG BUY"}:
            notes.append("Recommendation assumes the supplied manual details are accurate.")
        if status != "REVIEW" and acquisition and getattr(acquisition, "max_rational_price", None) is not None:
            notes.append(f"Max rational price: ${float(getattr(acquisition, 'max_rational_price')):.2f}.")
        elif status == "REVIEW" or getattr(acquisition, "max_rational_price", None) is None:
            notes.append("Max rational price: unavailable.")
        return notes

    @staticmethod
    def _unresolved(*outputs: Any) -> bool:
        """Required public evidence dominates mapped advice at every layer."""
        pending = list(outputs)
        seen = set()
        while pending:
            output = pending.pop()
            if output is None:
                continue
            if id(output) in seen:
                continue
            seen.add(id(output))
            # Follow only the structured public acquisition relationship, never
            # raw intelligence or arbitrary object attributes.
            pending.append(getattr(output, "acquisition_decision", None))
            if hasattr(output, "owned_current_match_summary"):
                summary = str(getattr(output, "owned_current_match_summary") or "").strip()
                # The workflow's ownership API is textual. Recognize only its
                # explicit unavailable sentinel, not general descriptive prose.
                if not summary or summary.upper() == "UNRESOLVED" or summary.upper().startswith("UNRESOLVED:"):
                    return True
            for name in ("opportunity_score", "composite_score", "max_rational_price",
                         "priority_score", "fit_score", "impact_score", "acquisition_impact_score",
                         "quality_delta", "quality_impact", "completion_delta", "completion_impact", "series_delta"):
                if hasattr(output, name) and getattr(output, name) is None:
                    return True
            for name in ("recommendation", "recommendation_status", "collection_intelligence_status",
                         "ownership_status", "duplicate_status", "upgrade_status", "collection_impact",
                         "upgrade_impact", "want_list_impact"):
                if hasattr(output, name):
                    value = getattr(output, name)
                    normalized = str(value).strip().upper()
                    if value is None or normalized in {"REVIEW", "NEEDS_REVIEW", "UNRESOLVED", "UNAVAILABLE"} or normalized.startswith("UNAVAILABLE:"):
                        return True
        return False

    def _details(self, source: Any, acquisition: Any, impact: Any, status: str) -> Dict[str, Any]:
        """Copy availability and independent context without deriving evidence."""
        def supplied(*fields: Any) -> Any:
            for output, name in fields:
                if output is not None and hasattr(output, name):
                    return getattr(output, name)
            return None

        details: Dict[str, Any] = {
            "max_rational_price": supplied((source, "max_rational_price"), (acquisition, "max_rational_price")),
            "priority": supplied((source, "priority_score"), (source, "priority")),
            "fit_score": supplied((source, "fit_score")),
            "composite_score": supplied((source, "opportunity_score"), (source, "composite_score")),
            "impact_score": supplied((source, "impact_score"), (source, "acquisition_impact_score"), (impact, "impact_score")),
            "quality_delta": supplied((source, "quality_delta"), (source, "quality_impact"), (impact, "quality_delta")),
            "completion_delta": supplied((source, "series_delta"), (source, "completion_impact"), (impact, "completion_delta")),
            "rank": supplied((source, "rank")),
        }
        if status == "REVIEW":
            details = {name: None for name in details}
        for name in ("ownership_status", "duplicate_status", "upgrade_status", "collection_impact"):
            value = supplied((source, name), (acquisition, name), (impact, name))
            details[name] = "UNRESOLVED" if status == "REVIEW" else value
            if name == "collection_impact" and (status == "REVIEW" or value is None):
                details[name] = None
        listing = getattr(source, "listing", None)
        details["asking_price"] = supplied((listing, "price"), (source, "asking_price"), (acquisition, "asking_price"))
        details["total_cost"] = supplied((listing, "total_cost"), (source, "total_cost"))
        if listing is not None:
            for name in ("shipping", "url", "seller", "source", "description", "notes", "created_at"):
                details["listing_" + name if name == "source" else name] = getattr(listing, name, None)
        return details

    @staticmethod
    def _status(value: str) -> str:
        text = str(value or "").strip().upper()
        if text in {"MUST BUY", "STRONG BUY", "BUY", "PASS", "WATCH", "NEGOTIATE", "REVIEW"}:
            return text
        return "REVIEW"

    @staticmethod
    def _signed(value: Optional[float]) -> str:
        if value is None:
            return "unavailable"
        value = float(value)
        return f"+{value:g}" if value > 0 else f"{value:g}"

    @staticmethod
    def _dedupe(values: Iterable[str]) -> List[str]:
        seen = set()
        result = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result
