"""Field-test and tuning framework for the live opportunity pipeline.

The framework runs deterministic, local scenarios through the existing live
pipeline. It does not fetch live sources, scrape, buy, bid, notify, or mutate
collection data.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from live_deal_hunter import LiveDealHunter, LiveDealHunterReport, LiveListing, LiveListingBatch
from live_source_validation import LiveSourceValidationReport
from market_awareness import MarketAwarenessEngine
from watchlist_engine import AlertEngine, AlertReport, Watchlist, WatchlistEngine, WatchlistReport


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


def _recommendation_of(candidate: Any) -> str:
    for attr in ("escalated_recommendation", "recommendation", "original_recommendation"):
        if hasattr(candidate, attr):
            value = _text(getattr(candidate, attr)).upper()
            if value:
                return value
    if hasattr(candidate, "deal_result"):
        return _recommendation_of(candidate.deal_result)
    return ""


def _confidence_of(candidate: Any) -> int:
    if hasattr(candidate, "opportunity_confidence"):
        try:
            return int(getattr(candidate, "opportunity_confidence"))
        except (TypeError, ValueError):
            return 0
    if hasattr(candidate, "market_report") and hasattr(candidate.market_report, "confidence"):
        try:
            return int(getattr(candidate.market_report.confidence, "score", 0))
        except (TypeError, ValueError):
            return 0
    if hasattr(candidate, "ranking_score") and hasattr(candidate.ranking_score, "score"):
        try:
            return int(candidate.ranking_score.score)
        except (TypeError, ValueError):
            return 0
    return 0


def _classifications_of(candidate: Any) -> List[str]:
    values: List[str] = []
    if hasattr(candidate, "collection_relevance"):
        values.extend(_text(item) for item in getattr(candidate.collection_relevance, "classifications", []) or [])
        values.append(_text(getattr(candidate.collection_relevance, "collection_goal_advanced", "")))
        values.append(_text(getattr(candidate.collection_relevance, "relevance_explanation", "")))
    if hasattr(candidate, "deal_result"):
        values.extend(_classifications_of(candidate.deal_result))
    for attr in ("collection_status", "collection_impact", "risk_flags"):
        if hasattr(candidate, attr):
            value = getattr(candidate, attr)
            if isinstance(value, list):
                values.extend(_text(item) for item in value)
            else:
                values.append(_text(value))
    return _dedupe(values)


@dataclass
class FieldTestScenario:
    scenario_id: str
    name: str
    description: str
    listings: List[LiveListing] = field(default_factory=list)
    expected_signals: List[str] = field(default_factory=list)
    notes: str = ""

    def to_batch(self) -> LiveListingBatch:
        return LiveListingBatch(source_name=self.name, listings=list(self.listings))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "listing_count": len(self.listings),
            "expected_signals": "; ".join(self.expected_signals),
            "notes": self.notes,
        }


@dataclass
class OpportunityQualityReport:
    buy_recommendations: int = 0
    review_recommendations: int = 0
    pass_recommendations: int = 0
    watch_recommendations: int = 0
    negotiate_recommendations: int = 0
    total_recommendations: int = 0
    escalation_frequency: int = 0
    high_confidence: int = 0
    medium_confidence: int = 0
    low_confidence: int = 0
    recommendations: List[str] = field(default_factory=list)

    @classmethod
    def from_candidates(cls, candidates: Sequence[Any]) -> "OpportunityQualityReport":
        report = cls()
        for candidate in candidates:
            recommendation = _recommendation_of(candidate)
            confidence = _confidence_of(candidate)
            if recommendation:
                report.total_recommendations += 1
            if "BUY" in recommendation:
                report.buy_recommendations += 1
            elif "REVIEW" in recommendation:
                report.review_recommendations += 1
            elif "PASS" in recommendation:
                report.pass_recommendations += 1
            elif "NEGOTIATE" in recommendation:
                report.negotiate_recommendations += 1
            elif "WATCH" in recommendation:
                report.watch_recommendations += 1
            if "REVIEW" in recommendation:
                report.escalation_frequency += 1
            if confidence >= 75:
                report.high_confidence += 1
            elif confidence >= 45:
                report.medium_confidence += 1
            elif confidence > 0:
                report.low_confidence += 1
        if report.buy_recommendations and report.low_confidence:
            report.recommendations.append("Review BUY signals with low confidence before field use.")
        if report.review_recommendations:
            report.recommendations.append("REVIEW escalations are present; prefer manual review over overconfident action.")
        if not report.total_recommendations:
            report.recommendations.append("No recommendations were produced; check validation and candidate parsing.")
        return report

    def to_dict(self) -> Dict[str, Any]:
        return {
            "buy_recommendations": self.buy_recommendations,
            "review_recommendations": self.review_recommendations,
            "pass_recommendations": self.pass_recommendations,
            "watch_recommendations": self.watch_recommendations,
            "negotiate_recommendations": self.negotiate_recommendations,
            "total_recommendations": self.total_recommendations,
            "escalation_frequency": self.escalation_frequency,
            "high_confidence": self.high_confidence,
            "medium_confidence": self.medium_confidence,
            "low_confidence": self.low_confidence,
            "recommendations": "; ".join(self.recommendations),
        }

    def format_markdown(self) -> str:
        lines = [
            "## Opportunity Quality",
            "",
            f"- BUY recommendations: {self.buy_recommendations}",
            f"- REVIEW recommendations: {self.review_recommendations}",
            f"- PASS recommendations: {self.pass_recommendations}",
            f"- WATCH recommendations: {self.watch_recommendations}",
            f"- NEGOTIATE recommendations: {self.negotiate_recommendations}",
            f"- Escalation frequency: {self.escalation_frequency}",
            f"- Confidence distribution: high={self.high_confidence}, medium={self.medium_confidence}, low={self.low_confidence}",
            "",
            "### Quality Recommendations",
            "",
        ]
        lines.extend(f"- {item}" for item in self.recommendations) if self.recommendations else lines.append("- None.")
        return "\n".join(lines)

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown() + "\n")
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(self.to_dict().keys()))
            writer.writeheader()
            writer.writerow(self.to_dict())
        return True


@dataclass
class PipelineHealthReport:
    listings_processed: int = 0
    validation_failures: int = 0
    duplicates_detected: int = 0
    watchlist_matches: int = 0
    alerts_generated: int = 0
    review_escalations: int = 0
    validation_warnings: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    health_status: str = "OK"
    notes: List[str] = field(default_factory=list)

    @classmethod
    def from_reports(
        cls,
        validation_report: LiveSourceValidationReport,
        live_report: LiveDealHunterReport,
        watch_report: WatchlistReport,
        alert_report: AlertReport,
        quality_report: OpportunityQualityReport,
    ) -> "PipelineHealthReport":
        summary = validation_report.summary
        report = cls(
            listings_processed=summary.total_listings,
            validation_failures=summary.invalid_count,
            duplicates_detected=summary.duplicate_count,
            watchlist_matches=len(watch_report.matches),
            alerts_generated=len(alert_report.alerts),
            review_escalations=quality_report.review_recommendations,
            validation_warnings=summary.warning_count,
            accepted_count=live_report.accepted_count,
            rejected_count=live_report.rejected_count,
        )
        if report.validation_failures or report.duplicates_detected or report.review_escalations:
            report.health_status = "REVIEW"
            report.notes.append("Pipeline produced validation failures, duplicates, or review escalations.")
        if report.alerts_generated > report.listings_processed * 3 and report.listings_processed:
            report.health_status = "WARNING"
            report.notes.append("Alert volume is high relative to listings processed; audit noisy watches.")
        if report.listings_processed == 0:
            report.health_status = "WARNING"
            report.notes.append("No listings were processed.")
        return report

    def to_dict(self) -> Dict[str, Any]:
        return {
            "listings_processed": self.listings_processed,
            "validation_failures": self.validation_failures,
            "duplicates_detected": self.duplicates_detected,
            "watchlist_matches": self.watchlist_matches,
            "alerts_generated": self.alerts_generated,
            "review_escalations": self.review_escalations,
            "validation_warnings": self.validation_warnings,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "health_status": self.health_status,
            "notes": "; ".join(self.notes),
        }

    def format_markdown(self) -> str:
        lines = [
            "## Pipeline Health",
            "",
            f"- Health status: {self.health_status}",
            f"- Listings processed: {self.listings_processed}",
            f"- Accepted listings: {self.accepted_count}",
            f"- Rejected listings: {self.rejected_count}",
            f"- Validation failures: {self.validation_failures}",
            f"- Duplicate URLs: {self.duplicates_detected}",
            f"- Validation warnings: {self.validation_warnings}",
            f"- Watchlist matches: {self.watchlist_matches}",
            f"- Alerts generated: {self.alerts_generated}",
            f"- Review escalations: {self.review_escalations}",
            "",
            "### Health Notes",
            "",
        ]
        lines.extend(f"- {note}" for note in self.notes) if self.notes else lines.append("- None.")
        return "\n".join(lines)

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown() + "\n")
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(self.to_dict().keys()))
            writer.writeheader()
            writer.writerow(self.to_dict())
        return True


@dataclass
class FalsePositiveFinding:
    category: str
    severity: str
    detail: str
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class FalsePositiveAudit:
    findings: List[FalsePositiveFinding] = field(default_factory=list)

    @classmethod
    def from_reports(
        cls,
        validation_report: LiveSourceValidationReport,
        watch_report: WatchlistReport,
        alert_report: AlertReport,
    ) -> "FalsePositiveAudit":
        findings: List[FalsePositiveFinding] = []
        for result in validation_report.results:
            if result.issue_codes and "DUPLICATE_URL" in result.issue_codes:
                findings.append(FalsePositiveFinding(
                    "Duplicate misclassification risk",
                    "MEDIUM",
                    f"Listing {result.listing_index} has a duplicate URL warning.",
                    "Review duplicate handling before trusting repeated recommendations.",
                ))
        for match in watch_report.matches:
            watch_type = match.watch_item.watch_type.lower()
            if match.confidence < 60:
                findings.append(FalsePositiveFinding(
                    "Weak watchlist match",
                    "LOW",
                    f"{match.candidate_title} matched {match.watch_item.name} with confidence {match.confidence}.",
                    "Tighten watch keywords or require manual review.",
                ))
            if "keyword" in watch_type and match.confidence < 75:
                findings.append(FalsePositiveFinding(
                    "Weak keyword match",
                    "LOW",
                    f"Keyword watch {match.watch_item.name} produced a low-confidence match.",
                    "Prefer series or specific coin watches for important targets.",
                ))
        for alert in alert_report.alerts:
            if alert.alert_type == "Upgrade Opportunity" and alert.score.score < 55:
                findings.append(FalsePositiveFinding(
                    "Weak upgrade signal",
                    "MEDIUM",
                    f"{alert.candidate_title} produced a weak upgrade alert score of {alert.score.score}.",
                    "Escalate to REVIEW until grade and variety evidence is clearer.",
                ))
            if alert.score.score < 45:
                findings.append(FalsePositiveFinding(
                    "Noisy alert",
                    "LOW",
                    f"{alert.candidate_title} produced alert score {alert.score.score}.",
                    "Suppress or review low-scoring alerts during field use.",
                ))
        return cls(findings=findings)

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_count": self.finding_count,
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def format_markdown(self) -> str:
        lines = ["## False Positive Audit", "", f"- Findings: {self.finding_count}", ""]
        if not self.findings:
            lines.append("- No likely false positives detected.")
        for finding in self.findings:
            lines.extend([
                f"### {finding.category}",
                f"- Severity: {finding.severity}",
                f"- Detail: {finding.detail}",
                f"- Recommendation: {finding.recommendation}",
                "",
            ])
        return "\n".join(lines).rstrip()

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown() + "\n")
        return True

    def export_csv(self, output_path: str) -> bool:
        fieldnames = ["category", "severity", "detail", "recommendation"]
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for finding in self.findings:
                writer.writerow(finding.to_dict())
        return True


@dataclass
class FieldTestResult:
    scenario: FieldTestScenario
    validation_report: LiveSourceValidationReport
    live_deal_hunter_report: LiveDealHunterReport
    watchlist_report: WatchlistReport
    alert_report: AlertReport
    opportunity_quality: OpportunityQualityReport
    pipeline_health: PipelineHealthReport
    false_positive_audit: FalsePositiveAudit
    status: str = "PASS"
    review_notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.pipeline_health.health_status in {"REVIEW", "WARNING"} or self.false_positive_audit.findings:
            self.status = "REVIEW"
        self.review_notes = _dedupe(self.review_notes + self.pipeline_health.notes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario.scenario_id,
            "scenario_name": self.scenario.name,
            "status": self.status,
            "listings": len(self.scenario.listings),
            "accepted": self.live_deal_hunter_report.accepted_count,
            "rejected": self.live_deal_hunter_report.rejected_count,
            "watchlist_matches": len(self.watchlist_report.matches),
            "alerts_generated": len(self.alert_report.alerts),
            "false_positive_findings": self.false_positive_audit.finding_count,
            "review_notes": "; ".join(self.review_notes),
        }

    def format_markdown(self) -> str:
        lines = [
            f"## Scenario: {self.scenario.name}",
            "",
            f"- Scenario ID: {self.scenario.scenario_id}",
            f"- Status: {self.status}",
            f"- Description: {self.scenario.description}",
            f"- Expected signals: {'; '.join(self.scenario.expected_signals) or 'None'}",
            "",
            self.pipeline_health.format_markdown(),
            "",
            self.opportunity_quality.format_markdown(),
            "",
            self.false_positive_audit.format_markdown(),
            "",
            "## Alerts",
            "",
        ]
        if not self.alert_report.alerts:
            lines.append("- None.")
        for alert in self.alert_report.alerts:
            lines.append(f"- {alert.alert_type}: {alert.candidate_title} ({alert.score.score}) - {alert.reason}")
        return "\n".join(lines).rstrip() + "\n"


@dataclass
class FieldTestReport:
    results: List[FieldTestResult] = field(default_factory=list)
    generated_at: str = ""
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()

    @property
    def scenario_count(self) -> int:
        return len(self.results)

    @property
    def review_count(self) -> int:
        return sum(1 for result in self.results if result.status == "REVIEW")

    @property
    def pass_count(self) -> int:
        return sum(1 for result in self.results if result.status == "PASS")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "scenario_count": self.scenario_count,
            "pass_count": self.pass_count,
            "review_count": self.review_count,
            "warnings": "; ".join(self.warnings),
            "results": [result.to_dict() for result in self.results],
        }

    def format_markdown(self) -> str:
        lines = [
            "# Field Test & Tuning Report",
            "",
            f"- Generated: {self.generated_at}",
            f"- Scenarios: {self.scenario_count}",
            f"- PASS: {self.pass_count}",
            f"- REVIEW: {self.review_count}",
            "- Safety note: deterministic local field tests only; no live fetching, scraping, purchasing, notifications, or collection mutation.",
            "",
        ]
        if self.warnings:
            lines.extend(["## Warnings", ""])
            lines.extend(f"- {warning}" for warning in self.warnings)
            lines.append("")
        for result in self.results:
            lines.append(result.format_markdown())
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        fieldnames = [
            "scenario_id", "scenario_name", "status", "listings", "accepted", "rejected",
            "watchlist_matches", "alerts_generated", "false_positive_findings", "review_notes",
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for result in self.results:
                writer.writerow(result.to_dict())
        return True


class ScenarioRunner:
    """Run deterministic scenarios through the existing live pipeline."""

    def __init__(
        self,
        collection_items: Optional[Iterable[Any]] = None,
        want_list_intents: Optional[Iterable[Any]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
        watchlists: Optional[Sequence[Watchlist]] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()
        self.watchlists = list(watchlists or [WatchlistEngine.adam_presets()])

    def run_scenario(self, scenario: FieldTestScenario, limit: int = 10) -> FieldTestResult:
        batch = scenario.to_batch()
        hunter = LiveDealHunter(self.collection_items, self.want_list_intents, self.market_awareness_engine)
        live_report = hunter.analyze_batch(batch, limit=limit)
        validation_report = live_report.validation_report or hunter.validator.validate_batch(batch)
        candidate_outputs = self._candidate_outputs(live_report)
        watch_engine = WatchlistEngine(self.watchlists)
        watch_report = watch_engine.scan(candidate_outputs)
        alert_report = AlertEngine(watch_engine).generate_alerts(candidate_outputs)
        quality_report = OpportunityQualityReport.from_candidates(candidate_outputs)
        pipeline_health = PipelineHealthReport.from_reports(
            validation_report,
            live_report,
            watch_report,
            alert_report,
            quality_report,
        )
        false_positive_audit = FalsePositiveAudit.from_reports(validation_report, watch_report, alert_report)
        return FieldTestResult(
            scenario=scenario,
            validation_report=validation_report,
            live_deal_hunter_report=live_report,
            watchlist_report=watch_report,
            alert_report=alert_report,
            opportunity_quality=quality_report,
            pipeline_health=pipeline_health,
            false_positive_audit=false_positive_audit,
        )

    def run_scenarios(self, scenarios: Sequence[FieldTestScenario], limit: int = 10) -> FieldTestReport:
        results = [self.run_scenario(scenario, limit=limit) for scenario in scenarios]
        return FieldTestReport(results=results)

    def _candidate_outputs(self, live_report: LiveDealHunterReport) -> List[Any]:
        if live_report.market_enrichment_report and live_report.market_enrichment_report.enriched_candidates:
            return list(live_report.market_enrichment_report.enriched_candidates)
        if live_report.ranking_report and live_report.ranking_report.ranked_deals:
            return list(live_report.ranking_report.ranked_deals)
        if live_report.candidate_pool and live_report.candidate_pool.listings:
            return list(live_report.candidate_pool.listings)
        return []


def default_field_test_scenarios() -> List[FieldTestScenario]:
    """Deterministic scenario library for local field testing."""
    rows = [
        ("newfoundland-upgrade", "Newfoundland upgrade", "Newfoundland 1904H 50 cents EF40 upgrade target", 145, 12, "CAD", "field.test/nfld-upgrade", ["upgrade", "newfoundland"]),
        ("newfoundland-duplicate", "Newfoundland duplicate", "Newfoundland 1943 10 cents same grade duplicate", 22, 5, "CAD", "field.test/nfld-duplicate", ["duplicate", "newfoundland"]),
        ("large-cent-1859", "1859 variety candidate", "Canada 1859 Large Cent Wide 9 variety VF", 80, 8, "CAD", "field.test/1859-wide9", ["1859", "variety"]),
        ("near-6-1926", "1926 Near 6 candidate", "Canada 1926 Near 6 nickel VF", 95, 7, "CAD", "field.test/1926-near6", ["near 6", "rare target"]),
        ("canadian-silver-lot", "Canadian silver lot", "Canada silver dime quarter half dollar mixed lot", 55, 18, "CAD", "field.test/silver-lot", ["silver", "lot risk"]),
        ("banknote-opportunity", "Banknote opportunity", "Canada 1937 banknote PMG VF", 48, 5, "CAD", "field.test/banknote", ["banknote"]),
        ("high-shipping-trap", "High shipping trap", "Newfoundland 5 cents low price high shipping", 8, 42, "CAD", "field.test/high-shipping", ["high shipping"]),
        ("non-cad-listing", "Non-CAD listing", "Canada 1973 Large Bust quarter", 60, 9, "USD", "field.test/non-cad", ["non-cad"]),
        ("weak-title", "Weak title listing", "old coin", 12, 4, "CAD", "field.test/weak-title", ["weak title"]),
        ("duplicate-url", "Duplicate URL listing A", "Canada 1926 Near 6 nickel duplicate URL", 85, 5, "CAD", "field.test/duplicate-url", ["duplicate url"]),
        ("duplicate-url-copy", "Duplicate URL listing B", "Canada 1926 Near 6 nickel duplicate URL copy", 86, 5, "CAD", "field.test/duplicate-url", ["duplicate url"]),
        ("false-positive-watch", "False positive watchlist match", "Newfoundland dog token souvenir not coin", 10, 3, "CAD", "field.test/false-positive", ["false positive"]),
        ("strong-watch-match", "Strong watchlist match", "1973 Canada Large Bust quarter ICCS AU", 140, 8, "CAD", "field.test/large-bust", ["strong watchlist match"]),
    ]
    scenarios: List[FieldTestScenario] = []
    for index, (scenario_id, name, title, price, shipping, currency, url, signals) in enumerate(rows, start=1):
        listing = LiveListing(
            title=title,
            price=float(price),
            shipping=float(shipping),
            currency=currency,
            seller="Field Test Seller",
            source="Field Test Fixture",
            url=f"https://{url}",
            raw_metadata={"description": title, "scenario_index": index},
        )
        scenarios.append(FieldTestScenario(
            scenario_id=scenario_id,
            name=name,
            description=f"Deterministic field-test fixture for {name}.",
            listings=[listing],
            expected_signals=list(signals),
        ))
    # Add one combined duplicate scenario so duplicate URL detection can be measured in one batch.
    duplicate_pair = FieldTestScenario(
        scenario_id="duplicate-url-pair",
        name="Duplicate URL listing",
        description="Two listings with the same URL to verify duplicate suppression and review reporting.",
        listings=[scenarios[9].listings[0], scenarios[10].listings[0]],
        expected_signals=["duplicate url", "review"],
    )
    return scenarios[:9] + [duplicate_pair] + scenarios[11:]
