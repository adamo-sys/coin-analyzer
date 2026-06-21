"""Offline external listing connector framework.

Connectors normalize user-supplied local files only. They do not scrape,
fetch URLs, call seller APIs, retrieve live listings, or mutate collection data.
"""

import csv
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from deal_hunter import DealListing
from deal_hunter_ranking import CandidatePool, DealHunterRankingEngine, ImportProfile


SOURCE_TYPE_EBAY = "eBay CSV"
SOURCE_TYPE_AUCTION = "Auction CSV"
SOURCE_TYPE_DEALER = "Dealer Inventory"
SOURCE_TYPE_GENERIC = "Generic CSV"


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


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
class NormalizedListing:
    """Connector-neutral listing model."""

    title: str
    description: str = ""
    price: float = 0.0
    shipping: float = 0.0
    seller: str = ""
    source: str = ""
    source_type: str = ""
    url: str = ""
    image_url: str = ""
    import_timestamp: str = ""
    connector_name: str = ""
    row_number: int = 0
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.import_timestamp = self.import_timestamp or _now_iso()
        self.title = str(self.title or "").strip()
        self.description = str(self.description or "").strip()
        self.seller = str(self.seller or "").strip()
        self.source = str(self.source or "").strip()
        self.source_type = str(self.source_type or "").strip()
        self.url = str(self.url or "").strip()
        self.image_url = str(self.image_url or "").strip()
        self.connector_name = str(self.connector_name or "").strip()
        self.price = _money(self.price)
        self.shipping = _money(self.shipping)

    @property
    def total_cost(self) -> float:
        return round(self.price + self.shipping, 2)

    def to_deal_listing(self) -> DealListing:
        listing = DealListing(
            title=self.title,
            price_cad=self.price,
            shipping_cad=self.shipping,
            seller=self.seller,
            source=self.source or self.source_type or self.connector_name,
            listing_url=self.url,
            image_url=self.image_url,
            description=self.description,
            created_at=self.import_timestamp,
            input_warnings=list(self.warnings),
        )
        listing.connector_name = self.connector_name
        listing.source_type = self.source_type
        listing.import_timestamp = self.import_timestamp
        listing.row_number = self.row_number
        return listing

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "price": self.price,
            "shipping": self.shipping,
            "total_cost": self.total_cost,
            "seller": self.seller,
            "source": self.source,
            "source_type": self.source_type,
            "url": self.url,
            "image_url": self.image_url,
            "import_timestamp": self.import_timestamp,
            "connector_name": self.connector_name,
            "row_number": self.row_number,
            "warnings": "; ".join(self.warnings),
        }


@dataclass
class ConnectorValidationReport:
    connector_name: str
    rows_found: int = 0
    valid_count: int = 0
    skipped_rows: int = 0
    warnings: List[str] = field(default_factory=list)
    unsupported_columns: List[str] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()

    @property
    def status(self) -> str:
        if self.skipped_rows:
            return "WARNING"
        if self.warnings:
            return "WARNING"
        return "OK"

    def format_markdown(self) -> str:
        lines = [
            f"# Connector Validation Report - {self.connector_name}",
            "",
            f"- Generated: {self.generated_at}",
            f"- Status: {self.status}",
            f"- Rows found: {self.rows_found}",
            f"- Valid listings: {self.valid_count}",
            f"- Skipped rows: {self.skipped_rows}",
            "",
            "## Warnings",
            "",
        ]
        lines.extend(f"- {warning}" for warning in self.warnings) if self.warnings else lines.append("- No warnings.")
        if self.unsupported_columns:
            lines.extend(["", "## Unsupported Columns", ""])
            lines.extend(f"- {column}" for column in self.unsupported_columns)
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "connector_name",
                "status",
                "rows_found",
                "valid_count",
                "skipped_rows",
                "warnings",
                "unsupported_columns",
                "generated_at",
            ])
            writer.writeheader()
            writer.writerow({
                "connector_name": self.connector_name,
                "status": self.status,
                "rows_found": self.rows_found,
                "valid_count": self.valid_count,
                "skipped_rows": self.skipped_rows,
                "warnings": "; ".join(self.warnings),
                "unsupported_columns": "; ".join(self.unsupported_columns),
                "generated_at": self.generated_at,
            })
        return True


@dataclass
class ConnectorImportReport:
    connector_name: str
    source_path: str = ""
    listings: List[NormalizedListing] = field(default_factory=list)
    validation_report: ConnectorValidationReport = field(default_factory=lambda: ConnectorValidationReport(""))
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()

    @property
    def imported_count(self) -> int:
        return len(self.listings)

    def to_candidate_pool(self) -> CandidatePool:
        return CandidatePool.from_listings(listing.to_deal_listing() for listing in self.listings)

    def format_markdown(self) -> str:
        lines = [
            f"# Connector Import Report - {self.connector_name}",
            "",
            f"- Generated: {self.generated_at}",
            f"- Source path: {self.source_path}",
            f"- Imported listings: {self.imported_count}",
            f"- Validation status: {self.validation_report.status}",
            "",
            "## Listings",
            "",
        ]
        if not self.listings:
            lines.append("- No listings imported.")
        for listing in self.listings:
            lines.append(f"- {listing.title} (${listing.total_cost:.2f}) via {listing.source or listing.source_type}")
        if self.validation_report.warnings:
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- {warning}" for warning in self.validation_report.warnings)
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            fieldnames = list(NormalizedListing("", "").to_dict().keys())
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for listing in self.listings:
                writer.writerow(listing.to_dict())
        return True


@dataclass
class SourceSummaryReport:
    source_counts: Dict[str, int] = field(default_factory=dict)
    source_type_counts: Dict[str, int] = field(default_factory=dict)
    connector_counts: Dict[str, int] = field(default_factory=dict)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()

    @classmethod
    def from_listings(cls, listings: Iterable[NormalizedListing]) -> "SourceSummaryReport":
        source_counts: Dict[str, int] = {}
        source_type_counts: Dict[str, int] = {}
        connector_counts: Dict[str, int] = {}
        for listing in listings or []:
            source_counts[listing.source or "Unknown"] = source_counts.get(listing.source or "Unknown", 0) + 1
            source_type_counts[listing.source_type or "Unknown"] = source_type_counts.get(listing.source_type or "Unknown", 0) + 1
            connector_counts[listing.connector_name or "Unknown"] = connector_counts.get(listing.connector_name or "Unknown", 0) + 1
        return cls(source_counts, source_type_counts, connector_counts)

    def format_markdown(self) -> str:
        lines = ["# Source Summary Report", "", f"- Generated: {self.generated_at}", ""]
        for title, payload in [
            ("Sources", self.source_counts),
            ("Source Types", self.source_type_counts),
            ("Connectors", self.connector_counts),
        ]:
            lines.extend([f"## {title}", ""])
            lines.extend(f"- {key}: {value}" for key, value in sorted(payload.items())) if payload else lines.append("- None.")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["category", "name", "count"])
            writer.writeheader()
            for category, payload in [
                ("source", self.source_counts),
                ("source_type", self.source_type_counts),
                ("connector", self.connector_counts),
            ]:
                for name, count in sorted(payload.items()):
                    writer.writerow({"category": category, "name": name, "count": count})
        return True


@dataclass
class DuplicateOpportunity:
    duplicate_type: str
    key: str
    count: int
    titles: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    recommendation: str = "Review duplicate opportunity before ranking."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "duplicate_type": self.duplicate_type,
            "key": self.key,
            "count": self.count,
            "titles": "; ".join(self.titles),
            "sources": "; ".join(self.sources),
            "recommendation": self.recommendation,
        }


class DuplicateOpportunityDetector:
    """Detect repeated listings and likely repeated opportunities across sources."""

    def detect(self, listings: Iterable[NormalizedListing]) -> List[DuplicateOpportunity]:
        normalized = list(listings or [])
        findings: List[DuplicateOpportunity] = []
        findings.extend(self._bucket("identical_url", normalized, lambda row: f"url:{_normalize(row.url)}" if row.url else ""))
        findings.extend(self._bucket("same_listing", normalized, lambda row: "|".join([
            _normalize(row.title),
            f"{row.total_cost:.2f}",
            _normalize(row.seller),
        ])))
        findings.extend(self._bucket("likely_same_opportunity", normalized, self._opportunity_key))
        return self._dedupe_findings(findings)

    @staticmethod
    def _bucket(kind: str, listings: List[NormalizedListing], key_fn) -> List[DuplicateOpportunity]:
        buckets: Dict[str, List[NormalizedListing]] = {}
        for listing in listings:
            key = key_fn(listing)
            if key:
                buckets.setdefault(key, []).append(listing)
        return [
            DuplicateOpportunity(
                duplicate_type=kind,
                key=key,
                count=len(rows),
                titles=[row.title for row in rows],
                sources=[row.source or row.source_type for row in rows],
            )
            for key, rows in buckets.items()
            if len(rows) > 1
        ]

    @staticmethod
    def _opportunity_key(listing: NormalizedListing) -> str:
        words = [
            word for word in _normalize(listing.title).replace(",", " ").split()
            if word not in {"iccs", "pcgs", "ngc", "bcs", "pmg", "vf20", "vf-20", "ef40", "ef-40"}
        ]
        return " ".join(words[:8])

    @staticmethod
    def _dedupe_findings(findings: List[DuplicateOpportunity]) -> List[DuplicateOpportunity]:
        selected: Dict[str, DuplicateOpportunity] = {}
        for finding in findings:
            key = f"{finding.duplicate_type}:{finding.key}"
            selected[key] = finding
        return list(selected.values())


class ListingConnector:
    """Base class for local-file listing connectors."""

    connector_name = "Listing Connector"
    source_type = SOURCE_TYPE_GENERIC
    source_name = ""
    import_profile = ImportProfile.custom_csv()
    supported_columns: List[str] = []

    def import_file(self, input_path: str, source_name: str = "") -> ConnectorImportReport:
        listings: List[NormalizedListing] = []
        warnings: List[str] = []
        skipped_rows = 0
        rows_found = 0
        unsupported = set()
        with open(input_path, "r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            headers = [str(header or "").strip() for header in (reader.fieldnames or [])]
            supported = {column.lower() for column in self.supported_columns}
            aliases = {alias.lower() for aliases in self.import_profile.field_aliases.values() for alias in aliases}
            aliases.update({"title", "listing_title", "price", "price_cad", "shipping", "shipping_cad", "seller", "source", "listing_url", "url", "image_url", "description", "currency", "end_time"})
            for header in headers:
                if supported and header.lower() not in supported and header.lower() not in aliases:
                    unsupported.add(header)
            for row_number, row in enumerate(reader, start=2):
                rows_found += 1
                normalized = self.import_profile.normalize_row(row)
                row_warnings = self.import_profile.validate_normalized_row(normalized, row_number)
                if any("missing required" in warning for warning in row_warnings):
                    skipped_rows += 1
                    warnings.extend(row_warnings)
                    continue
                listing = DealListing.from_dict(normalized)
                combined_warnings = _dedupe(row_warnings + [f"Row {row_number}: {warning}" for warning in listing.input_warnings])
                warnings.extend(combined_warnings)
                listings.append(NormalizedListing(
                    title=listing.title,
                    description=listing.description,
                    price=listing.price_cad,
                    shipping=listing.shipping_cad,
                    seller=listing.seller,
                    source=source_name or listing.source or self.source_name or self.source_type,
                    source_type=self.source_type,
                    url=listing.listing_url,
                    image_url=listing.image_url,
                    import_timestamp=listing.created_at,
                    connector_name=self.connector_name,
                    row_number=row_number,
                    warnings=combined_warnings,
                ))
        validation = ConnectorValidationReport(
            connector_name=self.connector_name,
            rows_found=rows_found,
            valid_count=len(listings),
            skipped_rows=skipped_rows,
            warnings=_dedupe(warnings),
            unsupported_columns=sorted(unsupported),
        )
        return ConnectorImportReport(self.connector_name, input_path, listings, validation)


class eBayCSVConnector(ListingConnector):
    connector_name = "eBay CSV Connector"
    source_type = SOURCE_TYPE_EBAY
    source_name = "eBay.ca"
    import_profile = ImportProfile.ebay_csv()
    supported_columns = ["title", "listing_title", "price", "price_cad", "shipping", "shipping_cad", "seller", "source", "listing_url", "url", "image_url", "description", "end_time", "currency"]


class AuctionCSVConnector(ListingConnector):
    connector_name = "Auction CSV Connector"
    source_type = SOURCE_TYPE_AUCTION
    source_name = "Auction"
    import_profile = ImportProfile.auction_csv()
    supported_columns = ["lot_title", "title", "hammer_price", "price", "price_cad", "buyer_premium", "shipping", "seller", "auction_house", "url", "listing_url", "image_url", "description"]


class DealerInventoryConnector(ListingConnector):
    connector_name = "Dealer Inventory Connector"
    source_type = SOURCE_TYPE_DEALER
    source_name = "Dealer Inventory"
    import_profile = ImportProfile.dealer_csv()
    supported_columns = ["item", "title", "dealer_price", "price", "price_cad", "shipping", "seller", "dealer", "url", "listing_url", "image_url", "description"]


class GenericCSVConnector(ListingConnector):
    connector_name = "Generic CSV Connector"
    source_type = SOURCE_TYPE_GENERIC
    source_name = "Generic CSV"
    import_profile = ImportProfile.custom_csv({
        "title": ["title", "name", "item"],
        "price_cad": ["price_cad", "price", "cost"],
        "shipping_cad": ["shipping_cad", "shipping"],
        "seller": ["seller", "dealer", "auction_house"],
        "listing_url": ["listing_url", "url"],
    })
    supported_columns = []


class ConnectorRegistry:
    """Registry for offline listing connectors."""

    def __init__(self, connectors: Optional[Iterable[ListingConnector]] = None):
        self._connectors: Dict[str, ListingConnector] = {}
        for connector in connectors or [eBayCSVConnector(), AuctionCSVConnector(), DealerInventoryConnector(), GenericCSVConnector()]:
            self.register(connector)

    def register(self, connector: ListingConnector) -> None:
        self._connectors[connector.connector_name] = connector

    def names(self) -> List[str]:
        return sorted(self._connectors)

    def get(self, name: str) -> ListingConnector:
        if name not in self._connectors:
            raise KeyError(f"Unknown connector: {name}")
        return self._connectors[name]

    def import_file(self, connector_name: str, input_path: str, source_name: str = "") -> ConnectorImportReport:
        return self.get(connector_name).import_file(input_path, source_name=source_name)

    def import_files(self, imports: Iterable[Dict[str, str]]) -> ConnectorImportReport:
        all_listings: List[NormalizedListing] = []
        warnings: List[str] = []
        skipped = 0
        rows = 0
        source_paths = []
        connector_names = []
        for request in imports or []:
            connector_name = request.get("connector_name") or request.get("connector") or GenericCSVConnector.connector_name
            report = self.import_file(connector_name, request.get("path", ""), request.get("source_name", ""))
            all_listings.extend(report.listings)
            warnings.extend(report.validation_report.warnings)
            skipped += report.validation_report.skipped_rows
            rows += report.validation_report.rows_found
            source_paths.append(report.source_path)
            connector_names.append(report.connector_name)
        validation = ConnectorValidationReport(
            connector_name="Mixed Source Import",
            rows_found=rows,
            valid_count=len(all_listings),
            skipped_rows=skipped,
            warnings=_dedupe(warnings),
        )
        return ConnectorImportReport(
            connector_name=", ".join(_dedupe(connector_names)) or "Mixed Source Import",
            source_path="; ".join(source_paths),
            listings=all_listings,
            validation_report=validation,
        )

    @staticmethod
    def to_candidate_pool(reports: Iterable[ConnectorImportReport]) -> CandidatePool:
        listings = []
        for report in reports or []:
            listings.extend(row.to_deal_listing() for row in report.listings)
        return CandidatePool.from_listings(listings)

    @staticmethod
    def rank_reports(
        reports: Iterable[ConnectorImportReport],
        ranking_engine: DealHunterRankingEngine,
    ):
        return ranking_engine.rank_pool(ConnectorRegistry.to_candidate_pool(reports))
