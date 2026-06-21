"""Deal Hunter calibration against offline collector-judgment cases."""

import csv
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from deal_hunter import DealHunter, DealHunterResult, DealListing
from deal_hunter_ranking import CandidatePool, DealHunterRankingEngine, RankedDeal
from market_awareness import MarketAwarenessEngine


EXPECTED_POSITIVE = {"BUY", "WATCH", "NEGOTIATE"}
EXPECTED_NEGATIVE = {"PASS", "REVIEW"}


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _split_values(value: Any) -> List[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(row).strip() for row in value if str(row).strip()]
    return [part.strip() for part in str(value).replace(",", "|").split("|") if part.strip()]


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


@dataclass
class CalibrationCase:
    """Expected collector judgment for one offline listing scenario."""

    case_id: str
    title: str
    description: str = ""
    price_cad: float = 0.0
    shipping_cad: float = 0.0
    source: str = "Calibration"
    expected_recommendation: str = "WATCH"
    expected_rank_category: str = ""
    expected_risk_flags: List[str] = field(default_factory=list)
    expected_priority_reason: str = ""
    collector_notes: str = ""

    @classmethod
    def from_dict(cls, row: Dict[str, Any]) -> "CalibrationCase":
        return cls(
            case_id=str(row.get("case_id") or "").strip(),
            title=str(row.get("title") or "").strip(),
            description=str(row.get("description") or "").strip(),
            price_cad=float(row.get("price_cad") or 0),
            shipping_cad=float(row.get("shipping_cad") or 0),
            source=str(row.get("source") or "Calibration").strip(),
            expected_recommendation=str(row.get("expected_recommendation") or "WATCH").strip().upper(),
            expected_rank_category=str(row.get("expected_rank_category") or "").strip(),
            expected_risk_flags=_split_values(row.get("expected_risk_flags")),
            expected_priority_reason=str(row.get("expected_priority_reason") or "").strip(),
            collector_notes=str(row.get("collector_notes") or "").strip(),
        )

    def to_listing(self) -> DealListing:
        return DealListing(
            title=self.title,
            price_cad=self.price_cad,
            shipping_cad=self.shipping_cad,
            source=self.source,
            description=self.description,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "description": self.description,
            "price_cad": self.price_cad,
            "shipping_cad": self.shipping_cad,
            "source": self.source,
            "expected_recommendation": self.expected_recommendation,
            "expected_rank_category": self.expected_rank_category,
            "expected_risk_flags": "; ".join(self.expected_risk_flags),
            "expected_priority_reason": self.expected_priority_reason,
            "collector_notes": self.collector_notes,
        }


@dataclass
class CalibrationCaseResult:
    case: CalibrationCase
    deal_result: DealHunterResult
    ranked_deal: Optional[RankedDeal] = None
    passed: bool = True
    findings: List[str] = field(default_factory=list)
    false_buy: bool = False
    false_pass: bool = False
    false_review: bool = False
    ranking_miss: bool = False
    missing_risk_flags: List[str] = field(default_factory=list)
    over_penalized: bool = False
    under_penalized: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case.case_id,
            "title": self.case.title,
            "expected_recommendation": self.case.expected_recommendation,
            "actual_recommendation": self.deal_result.recommendation,
            "expected_rank_category": self.case.expected_rank_category,
            "actual_rank": self.ranked_deal.rank if self.ranked_deal else "",
            "ranking_score": self.ranked_deal.ranking_score.score if self.ranked_deal else "",
            "passed": self.passed,
            "false_buy": self.false_buy,
            "false_pass": self.false_pass,
            "false_review": self.false_review,
            "ranking_miss": self.ranking_miss,
            "missing_risk_flags": "; ".join(self.missing_risk_flags),
            "findings": "; ".join(self.findings),
            "risk_flags": "; ".join(self.deal_result.risk_flags),
            "reasons": "; ".join(self.deal_result.reasons),
            "warnings": "; ".join(self.deal_result.warnings),
            "counterargument": self.deal_result.counterargument,
        }


@dataclass
class DealHunterCalibrationReport:
    case_results: List[CalibrationCaseResult] = field(default_factory=list)
    tuning_notes: List[str] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()

    @property
    def total_cases(self) -> int:
        return len(self.case_results)

    @property
    def passed_cases(self) -> int:
        return sum(1 for row in self.case_results if row.passed)

    @property
    def failed_cases(self) -> int:
        return self.total_cases - self.passed_cases

    @property
    def false_buys(self) -> List[CalibrationCaseResult]:
        return [row for row in self.case_results if row.false_buy]

    @property
    def false_passes(self) -> List[CalibrationCaseResult]:
        return [row for row in self.case_results if row.false_pass]

    @property
    def false_reviews(self) -> List[CalibrationCaseResult]:
        return [row for row in self.case_results if row.false_review]

    @property
    def ranking_misses(self) -> List[CalibrationCaseResult]:
        return [row for row in self.case_results if row.ranking_miss]

    @property
    def missing_risk_flag_cases(self) -> List[CalibrationCaseResult]:
        return [row for row in self.case_results if row.missing_risk_flags]

    @property
    def over_penalized_listings(self) -> List[CalibrationCaseResult]:
        return [row for row in self.case_results if row.over_penalized]

    @property
    def under_penalized_listings(self) -> List[CalibrationCaseResult]:
        return [row for row in self.case_results if row.under_penalized]

    @property
    def status(self) -> str:
        return "PASS" if self.failed_cases == 0 else "REVIEW"

    def format_markdown(self) -> str:
        lines = [
            "# Deal Hunter Calibration Report",
            "",
            f"- Generated: {self.generated_at}",
            f"- Status: {self.status}",
            f"- Total cases: {self.total_cases}",
            f"- Passed cases: {self.passed_cases}",
            f"- Failed cases: {self.failed_cases}",
            f"- False BUYs: {len(self.false_buys)}",
            f"- False PASSes: {len(self.false_passes)}",
            f"- False REVIEWs: {len(self.false_reviews)}",
            f"- Ranking misses: {len(self.ranking_misses)}",
            f"- Missing risk flags: {len(self.missing_risk_flag_cases)}",
            f"- Over-penalized listings: {len(self.over_penalized_listings)}",
            f"- Under-penalized listings: {len(self.under_penalized_listings)}",
            "",
            "## Failed Cases",
            "",
        ]
        failed = [row for row in self.case_results if not row.passed]
        if not failed:
            lines.append("- No failed calibration cases.")
        for row in failed:
            lines.append(f"- {row.case.case_id}: {row.case.title}")
            lines.append(f"  - Expected: {row.case.expected_recommendation}; actual: {row.deal_result.recommendation}")
            lines.append(f"  - Findings: {'; '.join(row.findings)}")
        lines.extend(["", "## Tuning Notes", ""])
        lines.extend(f"- {note}" for note in self.tuning_notes) if self.tuning_notes else lines.append("- No tuning notes.")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            fieldnames = [
                "case_id",
                "title",
                "expected_recommendation",
                "actual_recommendation",
                "expected_rank_category",
                "actual_rank",
                "ranking_score",
                "passed",
                "false_buy",
                "false_pass",
                "false_review",
                "ranking_miss",
                "missing_risk_flags",
                "findings",
                "risk_flags",
                "reasons",
                "warnings",
                "counterargument",
            ]
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in self.case_results:
                writer.writerow(row.to_dict())
        return True


class DealHunterCalibrationEngine:
    """Compare expected collector judgment against Deal Hunter and Ranking output."""

    def __init__(
        self,
        collection_items: Iterable[Any],
        want_list_intents: Optional[Iterable[Any]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()

    @staticmethod
    def load_cases(input_path: str) -> List[CalibrationCase]:
        with open(input_path, "r", newline="", encoding="utf-8-sig") as handle:
            return [CalibrationCase.from_dict(row) for row in csv.DictReader(handle)]

    def run(self, cases: Iterable[CalibrationCase]) -> DealHunterCalibrationReport:
        case_list = list(cases or [])
        hunter = DealHunter(self.collection_items, self.want_list_intents, self.market_awareness_engine)
        ranking = DealHunterRankingEngine(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
        ).rank_pool(CandidatePool.from_listings(case.to_listing() for case in case_list), limit=10)
        ranked_by_title = {_normalize(row.listing.title): row for row in ranking.ranked_deals}
        results = []
        for case in case_list:
            deal_result = hunter.analyze_listing(case.to_listing())
            ranked = ranked_by_title.get(_normalize(case.title))
            results.append(self._evaluate_case(case, deal_result, ranked))
        return DealHunterCalibrationReport(results, self._tuning_notes(results))

    def _evaluate_case(
        self,
        case: CalibrationCase,
        deal_result: DealHunterResult,
        ranked: Optional[RankedDeal],
    ) -> CalibrationCaseResult:
        findings: List[str] = []
        expected = case.expected_recommendation.upper()
        actual = deal_result.recommendation.upper()
        false_buy = actual == "BUY" and expected in {"PASS", "REVIEW"}
        false_pass = actual == "PASS" and expected in EXPECTED_POSITIVE
        false_review = actual == "REVIEW" and expected != "REVIEW"
        if actual != expected:
            findings.append(f"Expected {expected}, got {actual}")
        missing_risk_flags = [
            flag for flag in case.expected_risk_flags
            if flag and flag not in deal_result.risk_flags
        ]
        if missing_risk_flags:
            findings.append(f"Missing risk flags: {', '.join(missing_risk_flags)}")
        ranking_miss = self._ranking_miss(case.expected_rank_category, ranked)
        if ranking_miss:
            findings.append(f"Ranking miss for {case.expected_rank_category}")
        if case.expected_priority_reason:
            all_text = " ".join(deal_result.reasons + deal_result.warnings + [deal_result.counterargument]).lower()
            if case.expected_priority_reason.lower() not in all_text:
                findings.append(f"Missing expected rationale: {case.expected_priority_reason}")
        findings.extend(self._explanation_findings(expected, deal_result))
        over_penalized = expected in EXPECTED_POSITIVE and actual in {"PASS", "REVIEW"}
        under_penalized = expected in EXPECTED_NEGATIVE and actual in {"BUY", "NEGOTIATE"}
        passed = not findings and not false_buy and not false_pass and not false_review and not ranking_miss
        return CalibrationCaseResult(
            case=case,
            deal_result=deal_result,
            ranked_deal=ranked,
            passed=passed,
            findings=findings,
            false_buy=false_buy,
            false_pass=false_pass,
            false_review=false_review,
            ranking_miss=ranking_miss,
            missing_risk_flags=missing_risk_flags,
            over_penalized=over_penalized,
            under_penalized=under_penalized,
        )

    @staticmethod
    def _ranking_miss(expected_rank_category: str, ranked: Optional[RankedDeal]) -> bool:
        category = str(expected_rank_category or "").strip().upper()
        if not category:
            return False
        if not ranked:
            return True
        if category == "TOP_3":
            return ranked.rank > 3
        if category == "TOP_10":
            return ranked.rank > 10
        if category == "NOT_TOP_10":
            return ranked.rank <= 10
        if category == "TOP_UNDER_100":
            return not (ranked.rank <= 10 and ranked.listing.total_cost <= 100)
        if category == "LOW_PRIORITY":
            return ranked.ranking_score.score > 35
        return False

    @staticmethod
    def _explanation_findings(expected: str, result: DealHunterResult) -> List[str]:
        findings = []
        text = " ".join(result.reasons + result.warnings + result.risk_flags + [result.counterargument]).lower()
        if result.recommendation == "BUY":
            if not result.counterargument:
                findings.append("BUY recommendation missing counterargument")
            if not result.reasons:
                findings.append("BUY recommendation missing positive reasons")
        if expected == "PASS" and result.recommendation == "PASS":
            if not any(term in text for term in ["duplicate", "irrelevant", "damage", "risk", "weak"]):
                findings.append("PASS explanation does not clearly describe risk, duplicate, or poor fit")
        if expected == "REVIEW" and result.recommendation == "REVIEW":
            if not any(term in text for term in ["review", "unclear", "ambiguous", "currency", "lot"]):
                findings.append("REVIEW explanation does not identify uncertainty")
        return findings

    @staticmethod
    def _tuning_notes(results: List[CalibrationCaseResult]) -> List[str]:
        notes = []
        if any(row.false_buy for row in results):
            notes.append("Review positive recommendation thresholds; false BUYs were detected.")
        if any(row.false_pass for row in results):
            notes.append("Review risk penalties or priority boosts; false PASSes were detected.")
        if any(row.ranking_miss for row in results):
            notes.append("Review ranking score weights for high-priority opportunities.")
        if any(row.missing_risk_flags for row in results):
            notes.append("Review parser/risk-flag coverage for expected risk signals.")
        if not notes:
            notes.append("No deterministic scoring changes required by current calibration cases.")
        return notes
