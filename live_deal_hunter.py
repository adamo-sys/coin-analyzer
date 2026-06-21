"""Controlled-beta live listing ingestion for Deal Hunter.

Live Deal Hunter is explicitly user-triggered. It does not run background jobs,
poll feeds, purchase items, place bids, mutate collection records, use browser
automation, handle logins, or bypass access controls.
"""

from __future__ import annotations

import csv
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from deal_hunter import DealListing
from deal_hunter_ranking import CandidatePool, DealHunterRankingEngine, DealHunterRankingReport
from listing_connectors import NormalizedListing
from market_awareness import MarketAwarenessEngine
from market_intelligence import MarketIntelligenceEngine, MarketIntelligenceReport


FLAG_STALE = "STALE"
FLAG_UNKNOWN_CURRENCY = "UNKNOWN_CURRENCY"
FLAG_NON_CAD = "NON_CAD"
FLAG_MISSING_PRICE = "MISSING_PRICE"
FLAG_MISSING_TITLE = "MISSING_TITLE"
FLAG_DUPLICATE_URL = "DUPLICATE_URL"
FLAG_INVALID_URL = "INVALID_URL"
FLAG_UNKNOWN_SELLER = "UNKNOWN_SELLER"
FLAG_MISSING_URL = "MISSING_URL"
FLAG_MISSING_TIMESTAMP = "MISSING_TIMESTAMP"

DEFAULT_EBAY_RSS_URL = "https://www.ebay.ca/sch/i.html?_nkw=canada+coin&_rss=1"


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _dedupe(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values or []:
        text = _text(value)
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def _parse_money(text: str) -> Tuple[float, str]:
    value = _text(text)
    currency = ""
    if re.search(r"\bUSD\b|US\s*\$", value, re.IGNORECASE):
        currency = "USD"
    elif re.search(r"\bCAD\b|C\s*\$|CA\s*\$", value, re.IGNORECASE):
        currency = "CAD"
    elif "$" in value:
        currency = "UNKNOWN"
    match = re.search(r"(?:CA\$|C\$|US\$|\$)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", value, re.IGNORECASE)
    if not match:
        match = re.search(r"\b([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*(?:CAD|USD)\b", value, re.IGNORECASE)
    if not match:
        plain = re.search(r"\b([0-9][0-9,]*(?:\.[0-9]{1,2})?)\b", value)
        if plain:
            return round(float(plain.group(1).replace(",", "")), 2), currency
        return 0.0, currency
    return round(float(match.group(1).replace(",", "")), 2), currency or "CAD"


@dataclass
class LiveListing:
    title: str
    price: float = 0.0
    shipping: float = 0.0
    currency: str = "CAD"
    seller: str = ""
    source: str = ""
    url: str = ""
    image_url: str = ""
    listing_timestamp: str = ""
    end_timestamp: str = ""
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
    validation_flags: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        return round(float(self.price or 0.0) + float(self.shipping or 0.0), 2)

    def to_normalized_listing(self, connector_name: str = "RSSListingConnector") -> NormalizedListing:
        return NormalizedListing(
            title=self.title,
            description=_text(self.raw_metadata.get("description")),
            price=self.price,
            shipping=self.shipping,
            seller=self.seller,
            source=self.source,
            source_type="Live RSS",
            url=self.url,
            image_url=self.image_url,
            import_timestamp=self.listing_timestamp or _now_iso(),
            connector_name=connector_name,
            warnings=list(self.validation_warnings),
        )

    def to_deal_listing(self) -> DealListing:
        listing = self.to_normalized_listing().to_deal_listing()
        listing.currency = self.currency or "CAD"
        listing.end_time = self.end_timestamp
        return listing

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "price": self.price,
            "shipping": self.shipping,
            "total_cost": self.total_cost,
            "currency": self.currency,
            "seller": self.seller,
            "source": self.source,
            "url": self.url,
            "image_url": self.image_url,
            "listing_timestamp": self.listing_timestamp,
            "end_timestamp": self.end_timestamp,
            "validation_flags": "; ".join(self.validation_flags),
            "validation_warnings": "; ".join(self.validation_warnings),
        }


@dataclass
class LiveListingBatch:
    source_name: str
    fetch_timestamp: str = ""
    listings: List[LiveListing] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.fetch_timestamp = self.fetch_timestamp or _now_iso()

    @property
    def listing_count(self) -> int:
        return len(self.listings)

    def to_candidate_pool(self) -> CandidatePool:
        return CandidatePool.from_listings(listing.to_deal_listing() for listing in self.listings)


class LiveListingSource:
    """Base class for explicitly user-triggered live listing sources."""

    source_name = "Live Listing Source"

    def fetch_listings(self) -> LiveListingBatch:
        raise NotImplementedError("Live sources must implement explicitly user-triggered fetch_listings().")


class RSSListingConnector(LiveListingSource):
    """Fetch, parse, validate, and normalize a public RSS/XML listing feed."""

    source_name = "Public RSS Listing Feed"

    def __init__(self, feed_url: str = DEFAULT_EBAY_RSS_URL, timeout_seconds: int = 10, source_name: str = ""):
        self.feed_url = feed_url
        self.timeout_seconds = timeout_seconds
        self.source_name = source_name or self.source_name

    def fetch_listings(self) -> LiveListingBatch:
        try:
            request = urllib.request.Request(
                self.feed_url,
                headers={"User-Agent": "CoinAnalyzer/4.0 controlled-beta user-triggered fetch"},
            )
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
            return self.parse_feed(body, source_name=self.source_name, source_url=self.feed_url)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return LiveListingBatch(
                source_name=self.source_name,
                listings=[],
                errors=[f"Live source unavailable: {exc}"],
            )

    def parse_feed(self, feed_text: str, source_name: str = "", source_url: str = "") -> LiveListingBatch:
        source = source_name or self.source_name
        try:
            root = ET.fromstring(feed_text)
        except ET.ParseError as exc:
            return LiveListingBatch(source_name=source, errors=[f"Malformed RSS/XML feed: {exc}"])
        listings = []
        for item in self._iter_items(root):
            listings.append(self._listing_from_item(item, source, source_url))
        batch = LiveListingBatch(source_name=source, listings=listings)
        self.validate_batch(batch)
        return batch

    def validate_batch(self, batch: LiveListingBatch) -> LiveListingBatch:
        seen_urls = set()
        for listing in batch.listings:
            flags = []
            warnings = []
            if not listing.title:
                flags.append(FLAG_MISSING_TITLE)
                warnings.append("Missing listing title")
            if listing.price <= 0:
                flags.append(FLAG_MISSING_PRICE)
                warnings.append("Missing or unparseable listing price")
            if not listing.currency or listing.currency == "UNKNOWN":
                flags.append(FLAG_UNKNOWN_CURRENCY)
                warnings.append("Unknown listing currency")
            elif listing.currency.upper() != "CAD":
                flags.append(FLAG_NON_CAD)
                warnings.append(f"Non-CAD currency: {listing.currency}")
            if not listing.url:
                flags.append(FLAG_MISSING_URL)
                warnings.append("Missing listing URL")
            elif not self._valid_url(listing.url):
                flags.append(FLAG_INVALID_URL)
                warnings.append("Invalid listing URL")
            elif listing.url.lower() in seen_urls:
                flags.append(FLAG_DUPLICATE_URL)
                warnings.append("Duplicate listing URL")
            else:
                seen_urls.add(listing.url.lower())
            if not listing.seller:
                flags.append(FLAG_UNKNOWN_SELLER)
                warnings.append("Unknown seller")
            if not listing.listing_timestamp:
                flags.append(FLAG_MISSING_TIMESTAMP)
                warnings.append("Missing listing timestamp")
            if listing.listing_timestamp and self._is_stale(listing.listing_timestamp):
                flags.append(FLAG_STALE)
                warnings.append("Listing timestamp appears stale")
            listing.validation_flags = _dedupe(list(listing.validation_flags) + flags)
            listing.validation_warnings = _dedupe(list(listing.validation_warnings) + warnings)
        return batch

    def _listing_from_item(self, item: ET.Element, source: str, source_url: str) -> LiveListing:
        title = self._child_text(item, "title")
        description = self._child_text(item, "description") or self._child_text(item, "summary")
        url = self._child_text(item, "link") or self._attr_text(item, "link", "href")
        timestamp = self._child_text(item, "pubDate") or self._child_text(item, "updated") or self._child_text(item, "published")
        seller = self._child_text(item, "seller") or self._child_text(item, "author")
        end_time = self._child_text(item, "endTime") or self._child_text(item, "end")
        image_url = self._image_url(item)
        price, currency = self._extract_price_currency(item, title, description)
        shipping = self._extract_shipping(item, description)
        return LiveListing(
            title=title,
            price=price,
            shipping=shipping,
            currency=currency or "UNKNOWN",
            seller=seller,
            source=source,
            url=url,
            image_url=image_url,
            listing_timestamp=timestamp,
            end_timestamp=end_time,
            raw_metadata={
                "description": description,
                "source_url": source_url,
                "raw_tag": item.tag,
            },
        )

    def _extract_price_currency(self, item: ET.Element, title: str, description: str) -> Tuple[float, str]:
        for name in ("price", "currentPrice", "convertedCurrentPrice"):
            value = self._child_text(item, name)
            if value:
                amount = _text(value)
                currency = self._child_attr(item, name, "currencyId") or self._child_attr(item, name, "currency")
                parsed, parsed_currency = _parse_money(amount)
                return parsed, currency or parsed_currency
        return _parse_money(" ".join([title, description]))

    def _extract_shipping(self, item: ET.Element, description: str) -> float:
        for name in ("shipping", "shippingCost", "shippingPrice"):
            value = self._child_text(item, name)
            if value:
                parsed, _ = _parse_money(value)
                return parsed
        lowered = description.lower()
        if "free shipping" in lowered:
            return 0.0
        match = re.search(r"shipping[^0-9$]*(?:CA\$|C\$|\$)?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", description, re.IGNORECASE)
        if match:
            return round(float(match.group(1).replace(",", "")), 2)
        return 0.0

    def _iter_items(self, root: ET.Element) -> List[ET.Element]:
        items = [node for node in root.iter() if self._local_name(node.tag) in {"item", "entry"}]
        return items

    def _child_text(self, node: ET.Element, local_name: str) -> str:
        target = local_name.lower()
        for child in list(node):
            if self._local_name(child.tag).lower() == target:
                return _text(child.text)
        return ""

    def _child_attr(self, node: ET.Element, local_name: str, attr_name: str) -> str:
        target = local_name.lower()
        for child in list(node):
            if self._local_name(child.tag).lower() == target:
                return _text(child.attrib.get(attr_name))
        return ""

    def _attr_text(self, node: ET.Element, local_name: str, attr_name: str) -> str:
        target = local_name.lower()
        for child in list(node):
            if self._local_name(child.tag).lower() == target:
                return _text(child.attrib.get(attr_name))
        return ""

    def _image_url(self, node: ET.Element) -> str:
        for child in node.iter():
            name = self._local_name(child.tag).lower()
            if name in {"thumbnail", "content", "image", "galleryurl"}:
                return _text(child.attrib.get("url") or child.attrib.get("href") or child.text)
        return ""

    @staticmethod
    def _local_name(tag: str) -> str:
        return str(tag or "").split("}", 1)[-1]

    @staticmethod
    def _valid_url(url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _is_stale(timestamp: str) -> bool:
        text = _text(timestamp)
        if not text:
            return False
        for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(text, fmt)
                return (datetime.now(UTC).replace(tzinfo=None) - parsed).days > 30
            except ValueError:
                continue
        return False


@dataclass
class LiveDealHunterReport:
    source_name: str
    fetch_timestamp: str
    listing_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    validation_warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    candidate_pool: CandidatePool = field(default_factory=CandidatePool)
    ranking_report: Optional[DealHunterRankingReport] = None
    market_intelligence_reports: List[MarketIntelligenceReport] = field(default_factory=list)

    @property
    def top_opportunities(self) -> List[Any]:
        if not self.ranking_report:
            return []
        return list(self.ranking_report.ranked_deals[:5])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "fetch_timestamp": self.fetch_timestamp,
            "listing_count": self.listing_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "validation_warnings": "; ".join(self.validation_warnings),
            "errors": "; ".join(self.errors),
            "top_opportunities": [deal.to_dict() for deal in self.top_opportunities],
            "market_intelligence": [report.to_dict() for report in self.market_intelligence_reports],
        }

    def format_markdown(self) -> str:
        lines = [
            "# Live Deal Hunter Report",
            "",
            f"- Source: {self.source_name}",
            f"- Fetch timestamp: {self.fetch_timestamp}",
            f"- Listings processed: {self.listing_count}",
            f"- Accepted listings: {self.accepted_count}",
            f"- Rejected listings: {self.rejected_count}",
            "- Safety: user-triggered fetch only; no purchases, bids, background polling, or collection mutation.",
            "",
            "## Errors",
            "",
        ]
        lines.extend(f"- {error}" for error in self.errors) if self.errors else lines.append("- None.")
        lines.extend(["", "## Validation Warnings", ""])
        lines.extend(f"- {warning}" for warning in self.validation_warnings) if self.validation_warnings else lines.append("- None.")
        lines.extend(["", "## Top Opportunities", ""])
        if self.top_opportunities:
            for deal in self.top_opportunities:
                lines.append(
                    f"{deal.rank}. {deal.listing.title} - {deal.recommendation} "
                    f"(score {deal.ranking_score.score}, cost ${deal.listing.total_cost:.2f})"
                )
                lines.append(f"   - Counterargument: {deal.counterargument}")
        else:
            lines.append("- No accepted ranked opportunities.")
        lines.extend(["", "## Market Intelligence", ""])
        if self.market_intelligence_reports:
            for report in self.market_intelligence_reports:
                lines.append(
                    f"- {report.listing.title}: {report.deal_quality.quality}, "
                    f"confidence {report.confidence.score}, expected value ${report.fair_value.expected_value:.2f}"
                )
        else:
            lines.append("- No market intelligence summaries generated.")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["section", "title", "value", "detail"])
            writer.writerow(["summary", "source", self.source_name, ""])
            writer.writerow(["summary", "fetch_timestamp", self.fetch_timestamp, ""])
            writer.writerow(["summary", "listing_count", self.listing_count, ""])
            writer.writerow(["summary", "accepted_count", self.accepted_count, ""])
            writer.writerow(["summary", "rejected_count", self.rejected_count, ""])
            for warning in self.validation_warnings:
                writer.writerow(["validation_warning", warning, "", ""])
            for error in self.errors:
                writer.writerow(["error", error, "", ""])
            for deal in self.top_opportunities:
                writer.writerow([
                    "top_opportunity",
                    deal.listing.title,
                    deal.recommendation,
                    f"score={deal.ranking_score.score}; cost={deal.listing.total_cost:.2f}; url={deal.listing.listing_url}",
                ])
            for report in self.market_intelligence_reports:
                writer.writerow([
                    "market_intelligence",
                    report.listing.title,
                    report.deal_quality.quality,
                    f"confidence={report.confidence.score}; expected_value={report.fair_value.expected_value:.2f}",
                ])
        return True


class LiveDealHunter:
    """Coordinate explicitly-triggered live feed fetches through existing engines."""

    def __init__(
        self,
        collection_items: Iterable[Any],
        want_list_intents: Optional[Iterable[Any]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
        ranking_engine: Optional[DealHunterRankingEngine] = None,
        market_intelligence_engine: Optional[MarketIntelligenceEngine] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()
        self.ranking_engine = ranking_engine or DealHunterRankingEngine(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
        )
        self.market_intelligence_engine = market_intelligence_engine or MarketIntelligenceEngine(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
        )

    def run_source(self, source: LiveListingSource, limit: int = 5) -> LiveDealHunterReport:
        batch = source.fetch_listings()
        return self.analyze_batch(batch, limit=limit)

    def analyze_batch(self, batch: LiveListingBatch, limit: int = 5) -> LiveDealHunterReport:
        accepted = [listing for listing in batch.listings if not self._reject_listing(listing)]
        rejected = [listing for listing in batch.listings if self._reject_listing(listing)]
        warnings = []
        for listing in batch.listings:
            warnings.extend(f"{listing.title or 'Untitled'}: {warning}" for warning in listing.validation_warnings)
        pool = CandidatePool.from_listings(listing.to_deal_listing() for listing in accepted)
        ranking = self.ranking_engine.rank_pool(pool, limit=limit) if accepted else None
        market_reports = []
        if ranking:
            for ranked in ranking.ranked_deals[:limit]:
                market_reports.append(self.market_intelligence_engine.evaluate_listing(ranked.listing))
        return LiveDealHunterReport(
            source_name=batch.source_name,
            fetch_timestamp=batch.fetch_timestamp,
            listing_count=batch.listing_count,
            accepted_count=len(accepted),
            rejected_count=len(rejected),
            validation_warnings=_dedupe(warnings),
            errors=list(batch.errors),
            candidate_pool=pool,
            ranking_report=ranking,
            market_intelligence_reports=market_reports,
        )

    @staticmethod
    def _reject_listing(listing: LiveListing) -> bool:
        blocking = {FLAG_MISSING_TITLE, FLAG_MISSING_PRICE, FLAG_INVALID_URL, FLAG_MISSING_URL, FLAG_DUPLICATE_URL}
        return any(flag in blocking for flag in listing.validation_flags)
