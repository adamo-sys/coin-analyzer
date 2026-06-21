"""Live Deal Hunter readiness models.

This module defines contracts and validation reports for future live listing
ingestion. It performs no network calls and implements no live source fetching.
"""

import csv
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional


STALENESS_FRESH = "FRESH"
STALENESS_STALE = "STALE"
STALENESS_UNKNOWN = "UNKNOWN"


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _now_iso() -> str:
    return _now().isoformat(sep=" ")


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.replace(tzinfo=None)
    except ValueError:
        return None


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


def _valid_url(value: str) -> bool:
    return not value or value.startswith("http://") or value.startswith("https://")


@dataclass
class LiveListingSource:
    """Interface-style contract for future live listing sources."""

    source_name: str
    source_type: str = "Future Live Source"
    supports_fetch: bool = False
    requires_authentication: bool = False
    rate_limit_policy_name: str = ""

    def fetch_listings(self, *_args: Any, **_kwargs: Any) -> "LiveListingFetchResult":
        raise NotImplementedError("Live fetching is not implemented in v3.7 readiness.")


@dataclass
class LiveListingBatch:
    """Future live-source output contract."""

    source_name: str
    listings: List[Dict[str, Any]] = field(default_factory=list)
    fetched_at: str = ""
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.fetched_at = self.fetched_at or _now_iso()


@dataclass
class LiveListingFetchResult:
    """Contract result for a future user-triggered fetch."""

    source_name: str
    batch: Optional[LiveListingBatch] = None
    success: bool = False
    failures: List["LiveSourceFailure"] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    fetched_at: str = ""

    def __post_init__(self) -> None:
        self.fetched_at = self.fetched_at or _now_iso()


@dataclass
class LiveSourceFailure:
    """Structured failure model for future live sources."""

    source_name: str
    failure_type: str
    message: str
    retryable: bool = False
    occurred_at: str = ""

    def __post_init__(self) -> None:
        self.occurred_at = self.occurred_at or _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "failure_type": self.failure_type,
            "message": self.message,
            "retryable": self.retryable,
            "occurred_at": self.occurred_at,
        }


@dataclass
class RateLimitPolicy:
    """Planning model for source-specific fetch safety."""

    source_name: str
    allowed_fetch_cadence_minutes: int = 30
    batch_size_guidance: int = 50
    retry_guidance: str = "Manual retry only after reviewing source status."
    cooldown_guidance: str = "Wait for the full cadence window before another fetch."
    notes: str = "No background fetching or scheduling in v3.7."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "allowed_fetch_cadence_minutes": self.allowed_fetch_cadence_minutes,
            "batch_size_guidance": self.batch_size_guidance,
            "retry_guidance": self.retry_guidance,
            "cooldown_guidance": self.cooldown_guidance,
            "notes": self.notes,
        }


@dataclass
class LiveListingValidationFinding:
    listing_index: int
    severity: str
    finding_type: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "listing_index": self.listing_index,
            "severity": self.severity,
            "finding_type": self.finding_type,
            "message": self.message,
        }


@dataclass
class LiveSourceValidationReport:
    source_name: str
    listings_checked: int = 0
    findings: List[LiveListingValidationFinding] = field(default_factory=list)
    duplicate_urls: List[str] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()

    @property
    def status(self) -> str:
        severities = {finding.severity for finding in self.findings}
        if "FAIL" in severities:
            return "FAIL"
        if "WARNING" in severities or self.duplicate_urls:
            return "WARNING"
        return "OK"

    @classmethod
    def validate_batch(cls, batch: LiveListingBatch, stale_after_hours: int = 24) -> "LiveSourceValidationReport":
        findings: List[LiveListingValidationFinding] = []
        seen_urls: Dict[str, int] = {}
        duplicate_urls: List[str] = []
        now = _now()
        for index, row in enumerate(batch.listings, start=1):
            title = str(row.get("title") or "").strip()
            seller = str(row.get("seller") or "").strip()
            url = str(row.get("url") or row.get("listing_url") or "").strip()
            image_url = str(row.get("image_url") or "").strip()
            currency = str(row.get("currency") or "CAD").strip().upper()
            price = row.get("price", row.get("price_cad"))
            shipping = row.get("shipping", row.get("shipping_cad"))
            fetched_at = row.get("fetched_timestamp") or row.get("fetched_at") or batch.fetched_at

            if not title:
                findings.append(LiveListingValidationFinding(index, "FAIL", "MISSING_TITLE", "Listing is missing title."))
            if price in (None, ""):
                findings.append(LiveListingValidationFinding(index, "FAIL", "MISSING_PRICE", "Listing is missing price."))
            if shipping in (None, ""):
                findings.append(LiveListingValidationFinding(index, "WARNING", "MISSING_SHIPPING", "Listing is missing shipping."))
            if currency and currency != "CAD":
                findings.append(LiveListingValidationFinding(index, "WARNING", "NON_CAD_CURRENCY", "Listing currency is not CAD."))
            if not seller:
                findings.append(LiveListingValidationFinding(index, "WARNING", "MISSING_SELLER", "Listing is missing seller."))
            if url and not _valid_url(url):
                findings.append(LiveListingValidationFinding(index, "FAIL", "MALFORMED_URL", "Listing URL must start with http:// or https://."))
            if image_url and not _valid_url(image_url):
                findings.append(LiveListingValidationFinding(index, "WARNING", "MALFORMED_IMAGE_URL", "Image URL should start with http:// or https://."))
            if url:
                key = url.lower()
                if key in seen_urls:
                    duplicate_urls.append(url)
                    findings.append(LiveListingValidationFinding(index, "WARNING", "DUPLICATE_URL", f"Duplicate URL also seen at row {seen_urls[key]}."))
                else:
                    seen_urls[key] = index

            staleness = classify_staleness(fetched_at, now=now, stale_after_hours=stale_after_hours)
            if staleness == STALENESS_STALE:
                findings.append(LiveListingValidationFinding(index, "WARNING", "STALE_LISTING", "Listing fetched timestamp is stale."))
            elif staleness == STALENESS_UNKNOWN:
                findings.append(LiveListingValidationFinding(index, "WARNING", "UNKNOWN_STALENESS", "Listing staleness could not be determined."))

            metadata = row.get("raw_metadata")
            if metadata is not None and not isinstance(metadata, dict):
                findings.append(LiveListingValidationFinding(index, "WARNING", "SUSPICIOUS_METADATA", "Raw metadata should be structured as a dictionary."))

        return cls(batch.source_name, len(batch.listings), findings, _dedupe(duplicate_urls))

    def format_markdown(self) -> str:
        lines = [
            f"# Live Source Validation Report - {self.source_name}",
            "",
            f"- Generated: {self.generated_at}",
            f"- Status: {self.status}",
            f"- Listings checked: {self.listings_checked}",
            f"- Findings: {len(self.findings)}",
            f"- Duplicate URLs: {len(self.duplicate_urls)}",
            "",
            "## Findings",
            "",
        ]
        if not self.findings:
            lines.append("- No validation findings.")
        for finding in self.findings:
            lines.append(f"- Row {finding.listing_index} [{finding.severity}] {finding.finding_type}: {finding.message}")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            fieldnames = ["listing_index", "severity", "finding_type", "message"]
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for finding in self.findings:
                writer.writerow(finding.to_dict())
        return True


def classify_staleness(value: Any, now: Optional[datetime] = None, stale_after_hours: int = 24) -> str:
    parsed = _parse_datetime(value)
    if not parsed:
        return STALENESS_UNKNOWN
    now = now or _now()
    if parsed < now - timedelta(hours=stale_after_hours):
        return STALENESS_STALE
    return STALENESS_FRESH


@dataclass
class ReadinessCheck:
    name: str
    status: str
    details: str

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "status": self.status, "details": self.details}


@dataclass
class LiveDealHunterReadinessReport:
    checks: List[ReadinessCheck] = field(default_factory=list)
    safety_rules: List[str] = field(default_factory=list)
    rate_limit_policies: List[RateLimitPolicy] = field(default_factory=list)
    validation_report: Optional[LiveSourceValidationReport] = None
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()

    @property
    def blockers(self) -> List[ReadinessCheck]:
        return [check for check in self.checks if check.status == "BLOCKED"]

    @property
    def warnings(self) -> List[ReadinessCheck]:
        return [check for check in self.checks if check.status == "WARNING"]

    @property
    def status(self) -> str:
        return "NEEDS_WORK" if self.blockers else "READY_WITH_GUARDRAILS"

    @property
    def required_next_steps(self) -> List[str]:
        steps = [
            "Keep live fetches explicitly user-triggered.",
            "Validate every fetched batch before ranking.",
            "Route every listing through existing Deal Hunter, Ranking, Calibration, and duplicate-detection systems.",
            "Add source-specific rate-limit policies before enabling any real connector.",
            "Keep collection ownership data read-only during live listing review.",
        ]
        if self.validation_report and self.validation_report.status != "OK":
            steps.insert(0, "Resolve live source validation warnings before candidate ranking.")
        return steps

    def format_markdown(self) -> str:
        lines = [
            "# Live Deal Hunter Readiness Report",
            "",
            f"- Generated: {self.generated_at}",
            f"- Status: {self.status}",
            f"- Blockers: {len(self.blockers)}",
            f"- Warnings: {len(self.warnings)}",
            "",
            "## Readiness Checks",
            "",
        ]
        for check in self.checks:
            lines.append(f"- [{check.status}] {check.name}: {check.details}")
        lines.extend(["", "## Safety Rules", ""])
        lines.extend(f"- {rule}" for rule in self.safety_rules)
        lines.extend(["", "## Rate Limit Policies", ""])
        for policy in self.rate_limit_policies:
            lines.append(f"- {policy.source_name}: every {policy.allowed_fetch_cadence_minutes} minutes, batch guidance {policy.batch_size_guidance}")
        if self.validation_report:
            lines.extend(["", "## Validation Summary", ""])
            lines.append(f"- Source: {self.validation_report.source_name}")
            lines.append(f"- Status: {self.validation_report.status}")
            lines.append(f"- Findings: {len(self.validation_report.findings)}")
        lines.extend(["", "## Required Next Steps", ""])
        lines.extend(f"- {step}" for step in self.required_next_steps)
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            fieldnames = ["name", "status", "details"]
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for check in self.checks:
                writer.writerow(check.to_dict())
        return True


class LiveDealHunterReadinessAudit:
    """Evaluate future live-source readiness without fetching live data."""

    SAFETY_RULES = [
        "No automatic purchasing.",
        "No automatic collection mutation.",
        "No hidden network calls.",
        "Fetches must be explicit and user-triggered in future versions.",
        "Every source needs rate-limit awareness before activation.",
        "Failures must be reported clearly.",
        "Stale listing warnings are required.",
        "Currency validation is required.",
        "Shipping must be included in total cost.",
    ]

    def run(self, validation_batch: Optional[LiveListingBatch] = None) -> LiveDealHunterReadinessReport:
        checks = [
            ReadinessCheck("Connector framework readiness", "OK", "Offline connector registry and normalized listing model exist."),
            ReadinessCheck("Ranking readiness", "OK", "CandidatePool and DealHunterRankingEngine can rank supplied listings."),
            ReadinessCheck("Calibration readiness", "OK", "DealHunterCalibrationEngine can test expected collector judgments."),
            ReadinessCheck("Duplicate detection readiness", "OK", "CandidatePool and DuplicateOpportunityDetector support URL/listing duplicate checks."),
            ReadinessCheck("Source validation readiness", "OK", "LiveSourceValidationReport validates future batch fields before ranking."),
            ReadinessCheck("Rate-limit safety planning", "WARNING", "Policies are documented only; no live source should activate without source-specific cadence review."),
            ReadinessCheck("Failure handling", "OK", "LiveSourceFailure models network, auth, malformed response, rate limit, and unsupported source failures."),
            ReadinessCheck("No collection mutation safety", "OK", "Readiness models produce reports only and do not write collection ownership records."),
            ReadinessCheck("No live fetch behavior", "OK", "LiveListingSource.fetch_listings is a contract stub and raises NotImplementedError."),
        ]
        validation_report = LiveSourceValidationReport.validate_batch(validation_batch) if validation_batch else None
        policies = [
            RateLimitPolicy("eBay future source", 30, 50),
            RateLimitPolicy("Dealer future source", 60, 100),
            RateLimitPolicy("Auction future source", 60, 75),
        ]
        return LiveDealHunterReadinessReport(checks, list(self.SAFETY_RULES), policies, validation_report)
