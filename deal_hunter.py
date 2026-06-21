"""Offline collection-aware Deal Hunter for manually supplied listings.

Deal Hunter is deterministic local guidance only. It does not scrape websites,
fetch listing pages, call market-price APIs, or provide appraisal accuracy.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from acquisition_workflow import AcquisitionWorkflow
from acquisition_impact import AcquisitionImpactEngine
from focused_collection_intelligence import CandidateItem, MatchStatus
from listing_analyzer import ListingAnalyzer, ListingCandidate
from market_awareness import MarketAwarenessEngine
from smart_shopping_assistant import ShoppingCandidate, SmartShoppingAssistant


RECOMMENDATIONS = {"BUY", "WATCH", "PASS", "NEGOTIATE", "REVIEW"}
CAD_TERMS = {"", "cad", "c$", "ca$", "$"}
SLAB_COMPANIES = ["ICCS", "CCCS", "PCGS", "NGC", "BCS", "PMG"]
KEYWORDS = [
    "silver",
    "proof-like",
    "proof like",
    "specimen",
    "large bust",
    "near 6",
    "wide 9",
    "banknote",
    "chartered banknote",
    "estate lot",
    "bulk lot",
    "lot",
    "cleaned",
    "damaged",
    "holed",
    "bent",
    "environmental damage",
]
RISK_HIGH_SHIPPING = "HIGH_SHIPPING"
RISK_UNCLEAR_GRADE = "UNCLEAR_GRADE"
RISK_RAW_OVERGRADED = "RAW_OVERGRADED"
RISK_LOT_LISTING = "LOT_LISTING"
RISK_POSSIBLE_DAMAGE = "POSSIBLE_DAMAGE"
RISK_UNCLEAR_CURRENCY = "UNCLEAR_CURRENCY"
RISK_NON_COLLECTION_RELEVANT = "NON_COLLECTION_RELEVANT"
RISK_NEEDS_MANUAL_REVIEW = "NEEDS_MANUAL_REVIEW"
DAMAGE_TERMS = ["damaged", "cleaned", "holed", "bent", "environmental damage", "corrosion", "scratched"]
LOT_TERMS = ["estate lot", "bulk lot", "group lot", "coin lot", "collection lot", "lot of", "mixed lot"]
GRADE_WORDS = [
    (r"\bvery\s+fine\b", "VF-20"),
    (r"\bextra\s+fine\b|\bextremely\s+fine\b", "EF-40"),
    (r"\balmost\s+uncirculated\b", "AU-50"),
    (r"\buncirculated\b|\bbrilliant\s+uncirculated\b", "MS-60"),
    (r"\bgood\b", "G-4"),
    (r"\bfine\b", "F-12"),
]
RAW_OVERGRADED_TERMS = ["gem", "high grade", "rare", "unc", "ms+++"]


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _money(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    cleaned = (
        str(value)
        .strip()
        .lower()
        .replace("cad", "")
        .replace("c$", "")
        .replace("ca$", "")
        .replace("$", "")
        .replace(",", "")
    )
    cleaned = re.sub(r"\b(?:usd|us|gbp|eur)\b", "", cleaned).strip()
    return round(float(cleaned), 2) if cleaned else 0.0


def _money_with_warning(value: Any, field_name: str) -> Tuple[float, List[str]]:
    if value in (None, ""):
        return 0.0, []
    try:
        return _money(value), []
    except (TypeError, ValueError):
        return 0.0, [f"Malformed {field_name}: {value}"]


def _currency_warnings(*values: Any, currency: str = "CAD") -> List[str]:
    warnings = []
    currency_text = str(currency or "CAD").strip().lower()
    if currency_text not in CAD_TERMS:
        warnings.append(f"Currency is not verified as CAD: {currency}")
    combined = " ".join(str(value or "") for value in values).lower()
    if re.search(r"\b(?:usd|us \$|us\$|gbp|eur)\b", combined):
        warnings.append("Listing mentions non-CAD currency")
    return warnings


def _dedupe(values: Iterable[str]) -> List[str]:
    result = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


@dataclass
class DealListing:
    """Manual or CSV-sourced eBay.ca-style listing data."""

    title: str
    price_cad: float = 0.0
    shipping_cad: float = 0.0
    seller: str = ""
    source: str = ""
    listing_url: str = ""
    end_time: str = ""
    image_url: str = ""
    description: str = ""
    currency: str = "CAD"
    created_at: str = ""
    total_cost: float = field(init=False)
    input_warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        raw_price = self.price_cad
        raw_shipping = self.shipping_cad
        self.title = str(self.title or "").strip()
        price, price_warnings = _money_with_warning(self.price_cad, "price_cad")
        shipping, shipping_warnings = _money_with_warning(self.shipping_cad, "shipping_cad")
        self.price_cad = price
        self.shipping_cad = shipping
        self.seller = str(self.seller or "").strip()
        self.source = str(self.source or "").strip()
        self.listing_url = str(self.listing_url or "").strip()
        self.end_time = str(self.end_time or "").strip()
        self.image_url = str(self.image_url or "").strip()
        self.description = str(self.description or "").strip()
        self.currency = str(self.currency or "CAD").strip() or "CAD"
        self.created_at = self.created_at or _now_iso()
        self.total_cost = round(self.price_cad + self.shipping_cad, 2)
        self.input_warnings = _dedupe(
            list(self.input_warnings)
            + price_warnings
            + shipping_warnings
            + _currency_warnings(raw_price, raw_shipping, self.title, self.description, currency=self.currency)
        )

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "DealListing":
        return cls(
            title=str(payload.get("title") or ""),
            price_cad=payload.get("price_cad", 0.0),
            shipping_cad=payload.get("shipping_cad", 0.0),
            seller=str(payload.get("seller") or ""),
            source=str(payload.get("source") or ""),
            listing_url=str(payload.get("listing_url") or ""),
            end_time=str(payload.get("end_time") or ""),
            image_url=str(payload.get("image_url") or ""),
            description=str(payload.get("description") or ""),
            currency=str(payload.get("currency") or "CAD"),
            created_at=str(payload.get("created_at") or ""),
            input_warnings=list(payload.get("input_warnings") or []),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "price_cad": self.price_cad,
            "shipping_cad": self.shipping_cad,
            "total_cost": self.total_cost,
            "seller": self.seller,
            "source": self.source,
            "listing_url": self.listing_url,
            "end_time": self.end_time,
            "image_url": self.image_url,
            "description": self.description,
            "currency": self.currency,
            "created_at": self.created_at,
            "input_warnings": list(self.input_warnings),
        }

    def to_listing_candidate(self) -> ListingCandidate:
        return ListingCandidate(
            title=self.title,
            price=self.price_cad,
            shipping=self.shipping_cad,
            url=self.listing_url,
            notes=f"Image URL: {self.image_url}".strip() if self.image_url else "",
            seller=self.seller,
            source=self.source,
            description=self.description,
            created_at=self.created_at,
        )


@dataclass
class ParsedDealCandidate:
    country: str = ""
    year: str = ""
    denomination: str = ""
    series_type: str = ""
    grade: str = ""
    certifier: str = ""
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "country": self.country,
            "year": self.year,
            "denomination": self.denomination,
            "series_type": self.series_type,
            "grade": self.grade,
            "certifier": self.certifier,
            "keywords": list(self.keywords),
        }


@dataclass
class DealHunterResult:
    listing: DealListing
    parsed_candidate: ParsedDealCandidate
    collection_status: str
    priority_score: int
    liquidity_score: int
    collection_fit_score: int
    risk_score: int
    max_rational_price: float
    recommendation: str
    counterargument: str
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        parsed = self.parsed_candidate.to_dict()
        return {
            "title": self.listing.title,
            "total_cost": self.listing.total_cost,
            "seller": self.listing.seller,
            "source": self.listing.source,
            "listing_url": self.listing.listing_url,
            "parsed_candidate": parsed,
            "parsed_country": parsed["country"],
            "parsed_year": parsed["year"],
            "parsed_denomination": parsed["denomination"],
            "parsed_series_type": parsed["series_type"],
            "parsed_grade": parsed["grade"],
            "parsed_certifier": parsed["certifier"],
            "parsed_keywords": "; ".join(parsed["keywords"]),
            "collection_status": self.collection_status,
            "priority_score": self.priority_score,
            "liquidity_score": self.liquidity_score,
            "collection_fit_score": self.collection_fit_score,
            "risk_score": self.risk_score,
            "max_rational_price": self.max_rational_price,
            "recommendation": self.recommendation,
            "counterargument": self.counterargument,
            "reasons": "; ".join(self.reasons),
            "warnings": "; ".join(self.warnings),
            "risk_flags": "; ".join(self.risk_flags),
        }


@dataclass
class DealHunterReport:
    results: List[DealHunterResult] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "results": [result.to_dict() for result in self.results],
        }

    def format_markdown(self) -> str:
        lines = [
            "# Deal Hunter Report",
            "",
            f"- Generated: {self.generated_at}",
            "- Pricing note: deterministic CAD guidance only; not live market pricing or appraisal.",
            "",
        ]
        if not self.results:
            lines.append("- No listings analyzed.")
            return "\n".join(lines) + "\n"
        for index, result in enumerate(self.results, start=1):
            parsed = result.parsed_candidate
            lines.extend([
                f"## {index}. {result.listing.title}",
                "",
                f"- Recommendation: {result.recommendation}",
                f"- Total cost CAD: {result.listing.total_cost:.2f}",
                f"- Collection status: {result.collection_status}",
                f"- Parsed candidate: {' '.join(part for part in [parsed.country, parsed.year, parsed.denomination, parsed.grade, parsed.certifier] if part)}",
                f"- Priority score: {result.priority_score}",
                f"- Liquidity score: {result.liquidity_score}",
                f"- Collection-fit score: {result.collection_fit_score}",
                f"- Risk score: {result.risk_score}",
                f"- Max rational price CAD: {result.max_rational_price:.2f}",
                f"- Risk flags: {', '.join(result.risk_flags) if result.risk_flags else 'None'}",
                f"- Counterargument: {result.counterargument}",
                "",
                "Reasons:",
            ])
            lines.extend(f"- {reason}" for reason in result.reasons) if result.reasons else lines.append("- No positive reasons.")
            lines.append("")
            lines.append("Warnings:")
            lines.extend(f"- {warning}" for warning in result.warnings) if result.warnings else lines.append("- No warnings.")
            lines.append("")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "title",
                "total_cost",
                "seller",
                "source",
                "listing_url",
                "parsed_country",
                "parsed_year",
                "parsed_denomination",
                "parsed_series_type",
                "parsed_grade",
                "parsed_certifier",
                "parsed_keywords",
                "collection_status",
                "priority_score",
                "liquidity_score",
                "collection_fit_score",
                "risk_score",
                "max_rational_price",
                "recommendation",
                "counterargument",
                "risk_flags",
                "reasons",
                "warnings",
            ])
            writer.writeheader()
            for result in self.results:
                row = result.to_dict()
                row.pop("parsed_candidate", None)
                writer.writerow(row)
        return True


@dataclass
class DealHunterCSVImportResult:
    rows_found: int
    listings: List[DealListing] = field(default_factory=list)
    skipped_rows: int = 0
    warnings: List[str] = field(default_factory=list)

    @property
    def importable_count(self) -> int:
        return len(self.listings)


class DealHunter:
    """Evaluate manually supplied eBay.ca-style listing data."""

    def __init__(
        self,
        collection_items: Iterable[Any],
        want_list_intents: Optional[Iterable[Any]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()

    def analyze_listing(self, listing: DealListing) -> DealHunterResult:
        listing_analysis = ListingAnalyzer(self.collection_items, self.want_list_intents).analyze(listing.to_listing_candidate())
        candidate = self._enhance_candidate(listing, listing_analysis.candidate)
        acquisition = AcquisitionWorkflow(self.collection_items, self.want_list_intents).evaluate(candidate)
        impact = AcquisitionImpactEngine(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
        ).evaluate(candidate)
        shopping_report = SmartShoppingAssistant(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
        ).generate_report([
            ShoppingCandidate(
                listing.title,
                source=listing.source,
                asking_price=listing.price_cad,
                shipping=listing.shipping_cad,
                recommendation_source="Deal Hunter",
                notes=listing.description,
                url=listing.listing_url,
                seller=listing.seller,
                candidate=candidate,
            )
        ], include_want_list_targets=False)
        shopping = shopping_report.best_next_purchase
        parsed = self.parse_listing(listing, candidate)
        warnings = _dedupe(list(listing.input_warnings) + list(acquisition.warning_flags) + self._risk_warnings(listing, parsed, candidate, acquisition.collection_intelligence_status))
        risk_flags = self._risk_flags(listing, parsed, candidate, acquisition.collection_intelligence_status, warnings)
        reasons = self._reasons(listing, parsed, acquisition, impact, shopping)
        liquidity = self._liquidity_score(listing, parsed)
        fit = self._collection_fit_score(acquisition.collection_intelligence_status, impact.impact_score, parsed)
        risk = self._risk_score(listing, parsed, warnings, risk_flags)
        priority = self._priority_score(shopping.opportunity_score if shopping else 0, impact.impact_score, liquidity, fit, risk, parsed, acquisition.collection_intelligence_status)
        counterargument = self._counterargument(listing, acquisition.collection_intelligence_status, risk, warnings, risk_flags)
        recommendation = self._recommendation(acquisition.recommendation, priority, fit, risk, listing, counterargument, warnings, risk_flags)

        return DealHunterResult(
            listing=listing,
            parsed_candidate=parsed,
            collection_status=self._collection_status(acquisition.collection_intelligence_status),
            priority_score=priority,
            liquidity_score=liquidity,
            collection_fit_score=fit,
            risk_score=risk,
            max_rational_price=acquisition.max_rational_price,
            recommendation=recommendation,
            counterargument=counterargument,
            reasons=reasons,
            warnings=warnings,
            risk_flags=risk_flags,
        )

    def generate_report(self, listings: Iterable[DealListing]) -> DealHunterReport:
        results = [self.analyze_listing(listing) for listing in listings]
        results = sorted(results, key=lambda row: (-row.priority_score, row.risk_score, row.listing.total_cost, row.listing.title))
        return DealHunterReport(results)

    @staticmethod
    def import_csv(input_path: str) -> List[DealListing]:
        return DealHunter.import_csv_with_warnings(input_path).listings

    @staticmethod
    def import_csv_with_warnings(input_path: str) -> "DealHunterCSVImportResult":
        with open(input_path, "r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            listings = []
            warnings = []
            skipped_rows = 0
            rows_found = 0
            for index, row in enumerate(reader, start=2):
                rows_found += 1
                normalized = DealHunter._normalize_csv_row(row)
                if not normalized.get("title"):
                    skipped_rows += 1
                    warnings.append(f"Row {index}: missing required title")
                    continue
                if str(normalized.get("price_cad") or "").strip() == "":
                    skipped_rows += 1
                    warnings.append(f"Row {index}: missing required price_cad")
                    continue
                listing = DealListing.from_dict(normalized)
                warnings.extend(f"Row {index}: {warning}" for warning in listing.input_warnings)
                listings.append(listing)
            return DealHunterCSVImportResult(rows_found, listings, skipped_rows, _dedupe(warnings))

    @staticmethod
    def _normalize_csv_row(row: Dict[str, Any]) -> Dict[str, Any]:
        aliases = {
            "title": ["title", "listing_title", "item_title", "name"],
            "price_cad": ["price_cad", "price", "asking_price", "asking_price_cad", "current_bid"],
            "shipping_cad": ["shipping_cad", "shipping", "postage", "shipping_cost"],
            "seller": ["seller", "dealer", "vendor"],
            "source": ["source", "platform"],
            "listing_url": ["listing_url", "url", "link"],
            "end_time": ["end_time", "end_date", "date"],
            "image_url": ["image_url", "image", "photo_url"],
            "description": ["description", "desc", "notes"],
            "currency": ["currency", "currency_code"],
        }
        lowered = {str(key or "").strip().lower(): value for key, value in (row or {}).items()}
        normalized = {}
        for target, names in aliases.items():
            normalized[target] = ""
            for name in names:
                if name in lowered:
                    normalized[target] = lowered[name]
                    break
        return normalized

    def parse_listing(self, listing: DealListing, candidate: Optional[CandidateItem] = None) -> ParsedDealCandidate:
        candidate = candidate or ListingAnalyzer(self.collection_items, self.want_list_intents).to_candidate_item(listing.to_listing_candidate())
        text = " ".join([listing.title, listing.description]).lower()
        certifier = self._extract_certifier(text) or candidate.certifier
        keywords = [keyword for keyword in KEYWORDS if keyword in text]
        series = candidate.type_series
        if "banknote" in text:
            series = "Banknote"
        elif "large cent" in text:
            series = "Large Cent"
        elif "large bust" in text:
            series = "Large Bust"
        return ParsedDealCandidate(
            country=candidate.country,
            year=candidate.year,
            denomination=candidate.denomination,
            series_type=series,
            grade=candidate.grade or self._extract_grade_word(text),
            certifier=certifier,
            keywords=_dedupe(keywords),
        )

    def _enhance_candidate(self, listing: DealListing, candidate: CandidateItem) -> CandidateItem:
        text = " ".join([listing.title, listing.description])
        parsed_cert = self._extract_certifier(text)
        if parsed_cert:
            candidate.certifier = parsed_cert
        if not candidate.grade:
            candidate.grade = self._extract_grade_word(text.lower())
        lowered = text.lower()
        if "banknote" in lowered and not candidate.denomination:
            candidate.denomination = "banknote"
        if "chartered banknote" in lowered and not candidate.country:
            candidate.country = "Canada"
        if "large bust" in lowered:
            candidate.variety = _dedupe([candidate.variety, "large bust"])[-1]
        if "near 6" in lowered:
            candidate.variety = ", ".join(_dedupe([candidate.variety, "near 6"]))
        return candidate

    @staticmethod
    def _extract_certifier(text: str) -> str:
        lowered = text.lower()
        for company in SLAB_COMPANIES:
            if company.lower() in lowered:
                return company
        return ""

    @staticmethod
    def _extract_grade_word(text: str) -> str:
        lowered = text.lower()
        for pattern, grade in GRADE_WORDS:
            if re.search(pattern, lowered):
                return grade
        return ""

    def _collection_status(self, status: str) -> str:
        mapping = {
            MatchStatus.ALREADY_OWNED.value: "already owned",
            MatchStatus.SAME_GRADE_DUPLICATE.value: "same-grade duplicate",
            MatchStatus.LOWER_GRADE_DUPLICATE.value: "lower-grade duplicate",
            MatchStatus.BETTER_GRADE_UPGRADE.value: "better-grade upgrade",
            MatchStatus.WANT_LIST_MATCH.value: "want-list match",
            MatchStatus.COLLECTION_GAP.value: "collection gap",
            MatchStatus.NEEDS_REVIEW.value: "needs review",
            MatchStatus.NOT_RELEVANT.value: "not collection relevant",
        }
        return mapping.get(status, "needs review")

    def _liquidity_score(self, listing: DealListing, parsed: ParsedDealCandidate) -> int:
        score = 0
        text = " ".join([listing.seller, listing.source, listing.title]).lower()
        if "canada" in text or ".ca" in listing.listing_url.lower() or "ebay.ca" in text:
            score += 20
        if parsed.certifier in SLAB_COMPANIES:
            score += 18
        if "silver" in parsed.keywords:
            score += 12
        if "banknote" in parsed.keywords or "chartered banknote" in parsed.keywords:
            score += 10
        if parsed.country in {"Canada", "Newfoundland"}:
            score += 8
        return min(100, score)

    def _collection_fit_score(self, status: str, impact_score: int, parsed: ParsedDealCandidate) -> int:
        score = {
            MatchStatus.WANT_LIST_MATCH.value: 82,
            MatchStatus.BETTER_GRADE_UPGRADE.value: 76,
            MatchStatus.COLLECTION_GAP.value: 68,
            MatchStatus.NEEDS_REVIEW.value: 42,
            MatchStatus.ALREADY_OWNED.value: 18,
            MatchStatus.SAME_GRADE_DUPLICATE.value: 8,
            MatchStatus.LOWER_GRADE_DUPLICATE.value: 3,
            MatchStatus.NOT_RELEVANT.value: 0,
        }.get(status, 25)
        score += min(18, impact_score // 5)
        score += self._priority_boost(parsed) // 3
        return max(0, min(100, score))

    def _risk_score(self, listing: DealListing, parsed: ParsedDealCandidate, warnings: List[str], risk_flags: Optional[List[str]] = None) -> int:
        score = 0
        if listing.shipping_cad > 25 or (listing.price_cad > 0 and listing.shipping_cad / listing.price_cad >= 0.35):
            score += 28
        if not parsed.grade:
            score += 12
        if not parsed.country or not parsed.denomination:
            score += 20
        if len(listing.title.split()) < 4:
            score += 10
        lowered = " ".join([listing.title, listing.description]).lower()
        if "raw" in lowered and self._has_ambitious_raw_grade_language(lowered, parsed):
            score += 18
        if parsed.country not in {"Canada", "Newfoundland"} and "banknote" not in parsed.keywords:
            score += 18
        if any("currency" in warning.lower() for warning in warnings):
            score += 30
        flags = set(risk_flags or [])
        score += 12 if RISK_LOT_LISTING in flags else 0
        score += 18 if RISK_POSSIBLE_DAMAGE in flags else 0
        score += 12 if RISK_RAW_OVERGRADED in flags else 0
        return max(0, min(100, score))

    def _priority_score(self, shopping_score: int, impact_score: int, liquidity: int, fit: int, risk: int, parsed: ParsedDealCandidate, status: str) -> int:
        score = max(shopping_score, impact_score)
        score += fit // 3
        score += liquidity // 4
        score += self._priority_boost(parsed)
        score -= risk // 2
        if status in {MatchStatus.SAME_GRADE_DUPLICATE.value, MatchStatus.LOWER_GRADE_DUPLICATE.value, MatchStatus.NOT_RELEVANT.value}:
            cap = 35 if status == MatchStatus.NOT_RELEVANT.value and self._priority_boost(parsed) >= 18 else 25
            score = min(score, cap)
            if status == MatchStatus.NOT_RELEVANT.value and self._priority_boost(parsed) >= 18:
                score = max(score, 30)
        return max(0, min(100, int(round(score))))

    def _priority_boost(self, parsed: ParsedDealCandidate) -> int:
        text = " ".join([parsed.country, parsed.denomination, parsed.series_type, " ".join(parsed.keywords), parsed.year]).lower()
        boost = 0
        if "newfoundland" in text:
            boost += 22
        if "canada" in text and ("silver" in text or parsed.denomination in {"10 cents", "25 cents", "50 cents", "dollar"}):
            boost += 14
        if parsed.year == "1859" and "cent" in parsed.denomination:
            boost += 20
        if parsed.year == "1973" and "large bust" in text:
            boost += 18
        if parsed.year == "1926" and "near 6" in text:
            boost += 18
        if "banknote" in text:
            boost += 15
        if "chartered banknote" in text:
            boost += 22
        return boost

    def _risk_warnings(self, listing: DealListing, parsed: ParsedDealCandidate, candidate: CandidateItem, status: str) -> List[str]:
        warnings = []
        if listing.shipping_cad > 25 or (listing.price_cad > 0 and listing.shipping_cad / listing.price_cad >= 0.35):
            warnings.append("High shipping weakens the deal")
        if not parsed.grade:
            warnings.append("Missing grade")
        if not parsed.country:
            warnings.append("Uncertain country")
        if not parsed.denomination:
            warnings.append("Uncertain denomination")
        if parsed.country not in {"Canada", "Newfoundland"} and "banknote" not in parsed.keywords:
            warnings.append("Non-Canadian item appears outside Adam's core priorities")
        lowered = " ".join([listing.title, listing.description]).lower()
        if not candidate.certifier and self._has_ambitious_raw_grade_language(lowered, parsed):
            warnings.append("Raw coin with ambitious grade language")
        if any(term in lowered for term in LOT_TERMS):
            warnings.append("Lot listing requires manual review")
        if any(term in lowered for term in DAMAGE_TERMS):
            warnings.append("Possible damage or problem-coin keyword")
        if status == MatchStatus.NOT_RELEVANT.value:
            warnings.append("Not collection relevant")
        return warnings

    def _risk_flags(self, listing: DealListing, parsed: ParsedDealCandidate, candidate: CandidateItem, status: str, warnings: List[str]) -> List[str]:
        lowered = " ".join([listing.title, listing.description]).lower()
        flags = []
        if listing.shipping_cad > 25 or (listing.price_cad > 0 and listing.shipping_cad / listing.price_cad >= 0.35):
            flags.append(RISK_HIGH_SHIPPING)
        if not parsed.grade:
            flags.append(RISK_UNCLEAR_GRADE)
        if not candidate.certifier and self._has_ambitious_raw_grade_language(lowered, parsed):
            flags.append(RISK_RAW_OVERGRADED)
        if any(term in lowered for term in LOT_TERMS):
            flags.append(RISK_LOT_LISTING)
        if any(term in lowered for term in DAMAGE_TERMS):
            flags.append(RISK_POSSIBLE_DAMAGE)
        if any("currency" in warning.lower() or "malformed price" in warning.lower() for warning in warnings):
            flags.append(RISK_UNCLEAR_CURRENCY)
        on_theme_incomplete = parsed.country in {"Canada", "Newfoundland"} and (
            self._priority_boost(parsed) > 0
            or any(keyword in parsed.keywords for keyword in ["silver", "estate lot", "bulk lot", "lot", "large bust", "near 6", "banknote", "chartered banknote"])
        )
        if (status == MatchStatus.NOT_RELEVANT.value and not on_theme_incomplete) or (parsed.country not in {"Canada", "Newfoundland"} and "banknote" not in parsed.keywords):
            flags.append(RISK_NON_COLLECTION_RELEVANT)
        if flags and any(flag in flags for flag in [RISK_LOT_LISTING, RISK_POSSIBLE_DAMAGE, RISK_UNCLEAR_CURRENCY, RISK_RAW_OVERGRADED]):
            flags.append(RISK_NEEDS_MANUAL_REVIEW)
        return _dedupe(flags)

    @staticmethod
    def _has_ambitious_raw_grade_language(text: str, parsed: ParsedDealCandidate) -> bool:
        if any(term in text for term in RAW_OVERGRADED_TERMS):
            return True
        grade = (parsed.grade or "").upper()
        if grade.startswith(("MS-", "AU-")):
            return True
        return any(token in text for token in [" ms60", " ms61", " ms62", " ms63", " ms64", " ms65", " au50", " au55", " au58"])

    def _reasons(self, listing: DealListing, parsed: ParsedDealCandidate, acquisition: Any, impact: Any, shopping: Any) -> List[str]:
        reasons = []
        if acquisition.want_list_status == "ON_WANT_LIST":
            reasons.append("Explicit WANT_LIST match")
        if acquisition.collection_intelligence_status == MatchStatus.COLLECTION_GAP.value:
            reasons.append("Fills a collection gap")
        if acquisition.collection_intelligence_status == MatchStatus.BETTER_GRADE_UPGRADE.value:
            reasons.append("Potential upgrade over current holding")
        if parsed.country == "Newfoundland":
            reasons.append("Newfoundland priority")
        if "silver" in parsed.keywords or parsed.denomination in {"10 cents", "25 cents", "50 cents", "dollar"} and parsed.country == "Canada":
            reasons.append("Canadian silver priority")
        if parsed.year == "1859" and "cent" in parsed.denomination:
            reasons.append("1859 Large Cent priority")
        if "banknote" in parsed.keywords:
            reasons.append("Canadian banknote target")
        if parsed.certifier:
            reasons.append(f"Slabbed/certified by {parsed.certifier}")
        if impact.impact_score:
            reasons.append(f"Acquisition impact score {impact.impact_score}")
        if shopping:
            reasons.extend(shopping.reasons[:3])
        return _dedupe(reasons)

    def _counterargument(self, listing: DealListing, status: str, risk: int, warnings: List[str], risk_flags: Optional[List[str]] = None) -> str:
        points = []
        if status in {MatchStatus.ALREADY_OWNED.value, MatchStatus.SAME_GRADE_DUPLICATE.value}:
            points.append("already have a similar item")
        if listing.shipping_cad > 0:
            points.append("shipping raises the real total cost")
        if any("grade" in warning.lower() for warning in warnings):
            points.append("grade is uncertain")
        if risk >= 45:
            points.append("risk factors are material")
        if RISK_LOT_LISTING in set(risk_flags or []):
            points.append("lot contents may not match the target coin")
        if RISK_POSSIBLE_DAMAGE in set(risk_flags or []):
            points.append("problem-coin keywords reduce confidence")
        if listing.total_cost > 0:
            points.append("better opportunities may exist at the same budget")
        return "; ".join(points) if points else "No major counterargument beyond normal manual review."

    def _recommendation(self, base: str, priority: int, fit: int, risk: int, listing: DealListing, counterargument: str, warnings: List[str], risk_flags: Optional[List[str]] = None) -> str:
        flags = set(risk_flags or [])
        if RISK_UNCLEAR_CURRENCY in flags:
            return "REVIEW" if fit >= 45 else "PASS"
        if RISK_POSSIBLE_DAMAGE in flags or RISK_LOT_LISTING in flags or RISK_RAW_OVERGRADED in flags:
            if RISK_NON_COLLECTION_RELEVANT not in flags:
                return "REVIEW"
            return "REVIEW" if fit >= 35 else "PASS"
        if fit <= 8:
            return "PASS"
        if risk >= 70:
            return "REVIEW"
        if listing.total_cost <= 0:
            return "WATCH"
        if base == "PASS":
            return "PASS"
        if base == "REVIEW":
            return "REVIEW"
        if base == "NEGOTIATE":
            return "NEGOTIATE"
        if any("high shipping" in warning.lower() for warning in warnings):
            return "NEGOTIATE" if fit >= 45 else "WATCH"
        if base == "BUY" and priority >= 60 and fit >= 55 and risk <= 40:
            if "already have a similar item" not in counterargument and "grade is uncertain" not in counterargument:
                return "BUY"
            return "WATCH"
        if priority >= 50 and fit >= 45:
            return "NEGOTIATE" if risk >= 35 or listing.shipping_cad > 0 else "WATCH"
        return "WATCH" if fit >= 25 else "PASS"
