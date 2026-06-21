"""Deterministic validation for live listing sources.

The validator is intentionally conservative. It does not repair live data,
convert currencies, fetch exchange rates, or decide purchases. Its job is to
make bad or uncertain live data visible before listings enter Deal Hunter,
Ranking, Opportunity, or Market Intelligence workflows.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse


ISSUE_MISSING_TITLE = "MISSING_TITLE"
ISSUE_MISSING_PRICE = "MISSING_PRICE"
ISSUE_MISSING_URL = "MISSING_URL"
ISSUE_MISSING_SELLER = "MISSING_SELLER"
ISSUE_MISSING_SOURCE = "MISSING_SOURCE"
ISSUE_NON_CAD = "NON_CAD"
ISSUE_UNKNOWN_CURRENCY = "UNKNOWN_CURRENCY"
ISSUE_STALE = "STALE"
ISSUE_UNKNOWN_FRESHNESS = "UNKNOWN_FRESHNESS"
ISSUE_DUPLICATE_URL = "DUPLICATE_URL"
ISSUE_MALFORMED_URL = "MALFORMED_URL"
ISSUE_UNSUPPORTED_URL_SCHEME = "UNSUPPORTED_URL_SCHEME"
ISSUE_HIGH_SHIPPING = "HIGH_SHIPPING"
ISSUE_VAGUE_TITLE = "VAGUE_TITLE"
ISSUE_MISSING_DESCRIPTION = "MISSING_DESCRIPTION"
ISSUE_SUSPICIOUS_METADATA = "SUSPICIOUS_METADATA"


class ListingFreshness(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class SourceHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    WATCH = "WATCH"
    UNHEALTHY = "UNHEALTHY"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _timestamp_to_datetime(timestamp: str) -> Optional[datetime]:
    value = _text(timestamp)
    if not value:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


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
class ValidationWarning:
    listing_index: int
    issue_code: str
    message: str
    severity: str = "WARNING"
    recommendation: str = "Review before trusting this listing."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "listing_index": self.listing_index,
            "issue_code": self.issue_code,
            "message": self.message,
            "severity": self.severity,
            "recommendation": self.recommendation,
        }


@dataclass
class ValidationResult:
    listing_index: int
    valid_for_pipeline: bool
    freshness: ListingFreshness
    warnings: List[ValidationWarning] = field(default_factory=list)
    review_required: bool = False

    @property
    def issue_codes(self) -> List[str]:
        return _dedupe(warning.issue_code for warning in self.warnings)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "listing_index": self.listing_index,
            "valid_for_pipeline": self.valid_for_pipeline,
            "freshness": self.freshness.value,
            "review_required": self.review_required,
            "issue_codes": "; ".join(self.issue_codes),
            "warnings": [warning.to_dict() for warning in self.warnings],
        }


@dataclass
class ValidationSummary:
    total_listings: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    review_count: int = 0
    stale_count: int = 0
    duplicate_count: int = 0
    malformed_count: int = 0
    warning_count: int = 0

    @property
    def validation_pass_rate(self) -> float:
        if self.total_listings == 0:
            return 0.0
        return round(self.valid_count / self.total_listings, 4)

    @property
    def duplicate_rate(self) -> float:
        if self.total_listings == 0:
            return 0.0
        return round(self.duplicate_count / self.total_listings, 4)

    @property
    def stale_rate(self) -> float:
        if self.total_listings == 0:
            return 0.0
        return round(self.stale_count / self.total_listings, 4)

    @property
    def malformed_rate(self) -> float:
        if self.total_listings == 0:
            return 0.0
        return round(self.malformed_count / self.total_listings, 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_listings": self.total_listings,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "review_count": self.review_count,
            "stale_count": self.stale_count,
            "duplicate_count": self.duplicate_count,
            "malformed_count": self.malformed_count,
            "warning_count": self.warning_count,
            "validation_pass_rate": self.validation_pass_rate,
            "duplicate_rate": self.duplicate_rate,
            "stale_rate": self.stale_rate,
            "malformed_rate": self.malformed_rate,
        }


@dataclass
class SourceHealthReport:
    source_name: str
    fetch_success_rate: float
    validation_pass_rate: float
    duplicate_rate: float
    stale_rate: float
    malformed_rate: float
    status: SourceHealthStatus
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "fetch_success_rate": self.fetch_success_rate,
            "validation_pass_rate": self.validation_pass_rate,
            "duplicate_rate": self.duplicate_rate,
            "stale_rate": self.stale_rate,
            "malformed_rate": self.malformed_rate,
            "status": self.status.value,
            "reasons": "; ".join(self.reasons),
        }


@dataclass
class LiveSourceValidationReport:
    source_name: str
    generated_at: str
    summary: ValidationSummary
    source_health: SourceHealthReport
    results: List[ValidationResult] = field(default_factory=list)
    source_errors: List[str] = field(default_factory=list)

    @property
    def warnings(self) -> List[ValidationWarning]:
        return [warning for result in self.results for warning in result.warnings]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "generated_at": self.generated_at,
            "summary": self.summary.to_dict(),
            "source_health": self.source_health.to_dict(),
            "source_errors": list(self.source_errors),
            "results": [result.to_dict() for result in self.results],
        }

    def format_markdown(self) -> str:
        lines = [
            "# Live Source Validation Report",
            "",
            f"- Source: {self.source_name}",
            f"- Generated: {self.generated_at}",
            f"- Health: {self.source_health.status.value}",
            f"- Listings: {self.summary.total_listings}",
            f"- Valid for pipeline: {self.summary.valid_count}",
            f"- Invalid listings: {self.summary.invalid_count}",
            f"- Review required: {self.summary.review_count}",
            f"- Duplicate URLs: {self.summary.duplicate_count}",
            f"- Stale listings: {self.summary.stale_count}",
            f"- Malformed listings: {self.summary.malformed_count}",
            "",
            "## Source Health Reasons",
            "",
        ]
        lines.extend(f"- {reason}" for reason in self.source_health.reasons) if self.source_health.reasons else lines.append("- None.")
        lines.extend(["", "## Source Errors", ""])
        lines.extend(f"- {error}" for error in self.source_errors) if self.source_errors else lines.append("- None.")
        lines.extend(["", "## Validation Warnings", ""])
        if self.warnings:
            for warning in self.warnings:
                lines.append(
                    f"- Listing {warning.listing_index}: {warning.issue_code} "
                    f"({warning.severity}) - {warning.message}"
                )
        else:
            lines.append("- None.")
        lines.extend(["", "## Failed Listings", ""])
        failed = [result for result in self.results if not result.valid_for_pipeline]
        if failed:
            for result in failed:
                lines.append(
                    f"- Listing {result.listing_index}: "
                    f"{', '.join(result.issue_codes) or 'No issue code'}"
                )
        else:
            lines.append("- None.")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["section", "listing_index", "field", "value", "detail"])
            writer.writerow(["summary", "", "source", self.source_name, ""])
            writer.writerow(["summary", "", "health", self.source_health.status.value, ""])
            for key, value in self.summary.to_dict().items():
                writer.writerow(["summary", "", key, value, ""])
            for reason in self.source_health.reasons:
                writer.writerow(["health_reason", "", "reason", reason, ""])
            for error in self.source_errors:
                writer.writerow(["source_error", "", "error", error, ""])
            for result in self.results:
                writer.writerow([
                    "listing",
                    result.listing_index,
                    "valid_for_pipeline",
                    result.valid_for_pipeline,
                    f"freshness={result.freshness.value}; review_required={result.review_required}",
                ])
                for warning in result.warnings:
                    writer.writerow([
                        "warning",
                        warning.listing_index,
                        warning.issue_code,
                        warning.severity,
                        warning.message,
                    ])
        return True


class LiveSourceValidator:
    required_blocking_codes = {
        ISSUE_MISSING_TITLE,
        ISSUE_MISSING_PRICE,
        ISSUE_MISSING_URL,
        ISSUE_MISSING_SOURCE,
        ISSUE_MALFORMED_URL,
        ISSUE_UNSUPPORTED_URL_SCHEME,
        ISSUE_DUPLICATE_URL,
    }

    def validate_batch(self, batch: Any, fetch_succeeded: Optional[bool] = None) -> LiveSourceValidationReport:
        listings = list(getattr(batch, "listings", []) or [])
        errors = list(getattr(batch, "errors", []) or [])
        source_name = _text(getattr(batch, "source_name", "")) or "Unknown live source"
        success = (not errors) if fetch_succeeded is None else bool(fetch_succeeded)
        results = self.validate_listings(listings)
        summary = self.summarize(results)
        health = self.source_health(source_name, summary, fetch_success_rate=1.0 if success else 0.0)
        return LiveSourceValidationReport(
            source_name=source_name,
            generated_at=_now().isoformat(sep=" "),
            summary=summary,
            source_health=health,
            results=results,
            source_errors=errors,
        )

    def validate_listings(self, listings: Iterable[Any]) -> List[ValidationResult]:
        seen_urls = set()
        results: List[ValidationResult] = []
        for index, listing in enumerate(listings, start=1):
            warnings: List[ValidationWarning] = []
            title = self._field(listing, "title")
            price = self._number_field(listing, "price")
            url = self._field(listing, "url") or self._field(listing, "listing_url")
            seller = self._field(listing, "seller")
            source = self._field(listing, "source")
            currency = self._field(listing, "currency").upper()
            timestamp = self._field(listing, "listing_timestamp") or self._field(listing, "import_timestamp")
            description = self._description(listing)
            shipping = self._number_field(listing, "shipping")

            self._required(warnings, index, title, ISSUE_MISSING_TITLE, "Missing listing title", blocking=True)
            self._required(warnings, index, url, ISSUE_MISSING_URL, "Missing listing URL", blocking=True)
            self._required(warnings, index, seller, ISSUE_MISSING_SELLER, "Missing seller", blocking=False)
            self._required(warnings, index, source, ISSUE_MISSING_SOURCE, "Missing source", blocking=True)
            if price <= 0:
                warnings.append(self._warning(index, ISSUE_MISSING_PRICE, "Missing or unparseable listing price", "BLOCKING"))
            if not currency or currency == "UNKNOWN":
                warnings.append(self._warning(index, ISSUE_UNKNOWN_CURRENCY, "Unknown listing currency"))
            elif currency != "CAD":
                warnings.append(self._warning(index, ISSUE_NON_CAD, f"Non-CAD currency: {currency}"))

            if url:
                parsed = urlparse(url)
                if parsed.scheme and parsed.scheme not in {"http", "https"}:
                    warnings.append(self._warning(index, ISSUE_UNSUPPORTED_URL_SCHEME, f"Unsupported URL scheme: {parsed.scheme}", "BLOCKING"))
                elif not parsed.scheme or not parsed.netloc:
                    warnings.append(self._warning(index, ISSUE_MALFORMED_URL, "Malformed listing URL", "BLOCKING"))
                elif url.lower() in seen_urls:
                    warnings.append(self._warning(index, ISSUE_DUPLICATE_URL, "Duplicate listing URL", "BLOCKING"))
                else:
                    seen_urls.add(url.lower())

            freshness = self.freshness(timestamp)
            if freshness == ListingFreshness.STALE:
                warnings.append(self._warning(index, ISSUE_STALE, "Listing timestamp appears stale"))
            elif freshness == ListingFreshness.UNKNOWN:
                warnings.append(self._warning(index, ISSUE_UNKNOWN_FRESHNESS, "Listing freshness is unknown"))

            if shipping > 0 and price > 0 and shipping >= max(20.0, price * 0.35):
                warnings.append(self._warning(index, ISSUE_HIGH_SHIPPING, "Shipping is high relative to item price"))
            if title and len(title.split()) < 3:
                warnings.append(self._warning(index, ISSUE_VAGUE_TITLE, "Listing title is vague"))
            if not description:
                warnings.append(self._warning(index, ISSUE_MISSING_DESCRIPTION, "Missing listing description"))
            if any(marker in f"{title} {description}".lower() for marker in ("replica", "copy", "unknown", "estate lot", "as-is")):
                warnings.append(self._warning(index, ISSUE_SUSPICIOUS_METADATA, "Listing metadata contains suspicious or ambiguous terms"))

            issue_codes = {warning.issue_code for warning in warnings}
            valid = not bool(issue_codes & self.required_blocking_codes)
            review = (not valid) or any(
                code in issue_codes
                for code in {
                    ISSUE_MISSING_SELLER,
                    ISSUE_UNKNOWN_CURRENCY,
                    ISSUE_NON_CAD,
                    ISSUE_STALE,
                    ISSUE_UNKNOWN_FRESHNESS,
                    ISSUE_HIGH_SHIPPING,
                    ISSUE_VAGUE_TITLE,
                    ISSUE_MISSING_DESCRIPTION,
                    ISSUE_SUSPICIOUS_METADATA,
                }
            )
            results.append(ValidationResult(index, valid, freshness, warnings, review))
        return results

    def summarize(self, results: Iterable[ValidationResult]) -> ValidationSummary:
        rows = list(results)
        return ValidationSummary(
            total_listings=len(rows),
            valid_count=sum(1 for result in rows if result.valid_for_pipeline),
            invalid_count=sum(1 for result in rows if not result.valid_for_pipeline),
            review_count=sum(1 for result in rows if result.review_required),
            stale_count=sum(1 for result in rows if result.freshness == ListingFreshness.STALE),
            duplicate_count=sum(1 for result in rows if ISSUE_DUPLICATE_URL in result.issue_codes),
            malformed_count=sum(
                1 for result in rows
                if ISSUE_MALFORMED_URL in result.issue_codes or ISSUE_UNSUPPORTED_URL_SCHEME in result.issue_codes
            ),
            warning_count=sum(len(result.warnings) for result in rows),
        )

    def source_health(self, source_name: str, summary: ValidationSummary, fetch_success_rate: float = 1.0) -> SourceHealthReport:
        reasons: List[str] = []
        status = SourceHealthStatus.HEALTHY
        if fetch_success_rate < 1.0:
            reasons.append("Fetch did not complete successfully.")
            status = SourceHealthStatus.UNHEALTHY
        if summary.total_listings == 0:
            reasons.append("No listings were available for validation.")
            status = SourceHealthStatus.UNHEALTHY
        if summary.validation_pass_rate < 0.5 and summary.total_listings:
            reasons.append("Fewer than half of listings passed validation.")
            status = SourceHealthStatus.UNHEALTHY
        elif summary.validation_pass_rate < 0.85 and status != SourceHealthStatus.UNHEALTHY:
            reasons.append("Validation pass rate should be watched.")
            status = SourceHealthStatus.WATCH
        if summary.duplicate_rate >= 0.2 and summary.total_listings:
            reasons.append("Duplicate listing rate is elevated.")
            if status == SourceHealthStatus.HEALTHY:
                status = SourceHealthStatus.WATCH
        if summary.stale_rate >= 0.2 and summary.total_listings:
            reasons.append("Stale listing rate is elevated.")
            if status == SourceHealthStatus.HEALTHY:
                status = SourceHealthStatus.WATCH
        if summary.malformed_rate > 0:
            reasons.append("Malformed listing URLs were detected.")
            status = SourceHealthStatus.UNHEALTHY if summary.malformed_rate >= 0.2 else SourceHealthStatus.WATCH
        if not reasons:
            reasons.append("Source passed deterministic validation thresholds.")
        return SourceHealthReport(
            source_name=source_name,
            fetch_success_rate=round(fetch_success_rate, 4),
            validation_pass_rate=summary.validation_pass_rate,
            duplicate_rate=summary.duplicate_rate,
            stale_rate=summary.stale_rate,
            malformed_rate=summary.malformed_rate,
            status=status,
            reasons=reasons,
        )

    def freshness(self, timestamp: str) -> ListingFreshness:
        parsed = _timestamp_to_datetime(timestamp)
        if not parsed:
            return ListingFreshness.UNKNOWN
        return ListingFreshness.STALE if (_now() - parsed).days > 30 else ListingFreshness.FRESH

    def _required(self, warnings: List[ValidationWarning], index: int, value: str, code: str, message: str, blocking: bool) -> None:
        if not value:
            warnings.append(self._warning(index, code, message, "BLOCKING" if blocking else "WARNING"))

    def _warning(self, index: int, code: str, message: str, severity: str = "WARNING") -> ValidationWarning:
        recommendation = "Do not enter this listing into recommendations until corrected." if severity == "BLOCKING" else "Review before trusting this listing."
        return ValidationWarning(index, code, message, severity, recommendation)

    def _field(self, listing: Any, name: str) -> str:
        if isinstance(listing, dict):
            return _text(listing.get(name))
        return _text(getattr(listing, name, ""))

    def _number_field(self, listing: Any, name: str) -> float:
        value = self._field(listing, name)
        if not value and not isinstance(listing, dict):
            value = getattr(listing, name, 0.0)
        if isinstance(listing, dict):
            value = listing.get(name, 0.0)
        try:
            return float(str(value or 0.0).replace("$", "").replace(",", ""))
        except (TypeError, ValueError):
            return 0.0

    def _description(self, listing: Any) -> str:
        if isinstance(listing, dict):
            raw = listing.get("description") or listing.get("raw_metadata", {}).get("description")
            return _text(raw)
        raw_metadata = getattr(listing, "raw_metadata", {}) or {}
        return _text(getattr(listing, "description", "") or raw_metadata.get("description"))
