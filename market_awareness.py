"""Personal market awareness records and summaries.

This module uses local records only. It does not scrape, fetch, predict, or call
market-price APIs.
"""

import csv
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _money(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    cleaned = str(value).strip().replace("$", "").replace(",", "")
    return round(float(cleaned), 2) if cleaned else 0.0


@dataclass
class ObservedPriceRecord:
    item_name: str
    country: str = ""
    denomination: str = ""
    year: str = ""
    grade: str = ""
    observed_price: float = 0.0
    shipping: float = 0.0
    source: str = ""
    date_observed: str = ""
    notes: str = ""
    linked_photo_ids: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.item_name = (self.item_name or "").strip()
        self.country = (self.country or "").strip()
        self.denomination = (self.denomination or "").strip()
        self.year = str(self.year or "").strip()
        self.grade = (self.grade or "").strip()
        self.observed_price = _money(self.observed_price)
        self.shipping = _money(self.shipping)
        self.source = (self.source or "").strip()
        self.date_observed = self.date_observed or _today()
        self.notes = (self.notes or "").strip()

    @property
    def total_observed_cost(self) -> float:
        return round(self.observed_price + self.shipping, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_name": self.item_name,
            "country": self.country,
            "denomination": self.denomination,
            "year": self.year,
            "grade": self.grade,
            "observed_price": self.observed_price,
            "shipping": self.shipping,
            "total_observed_cost": self.total_observed_cost,
            "source": self.source,
            "date_observed": self.date_observed,
            "notes": self.notes,
            "linked_photo_ids": ";".join(self.linked_photo_ids),
        }


@dataclass
class PurchaseRecord:
    item: str
    purchase_price: float = 0.0
    shipping: float = 0.0
    seller: str = ""
    source: str = ""
    purchase_date: str = ""
    notes: str = ""
    country: str = ""
    denomination: str = ""
    year: str = ""
    grade: str = ""
    linked_photo_ids: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.item = (self.item or "").strip()
        self.purchase_price = _money(self.purchase_price)
        self.shipping = _money(self.shipping)
        self.seller = (self.seller or "").strip()
        self.source = (self.source or "").strip()
        self.purchase_date = self.purchase_date or _today()
        self.notes = (self.notes or "").strip()
        self.country = (self.country or "").strip()
        self.denomination = (self.denomination or "").strip()
        self.year = str(self.year or "").strip()
        self.grade = (self.grade or "").strip()

    @property
    def total_cost(self) -> float:
        return round(self.purchase_price + self.shipping, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item": self.item,
            "purchase_price": self.purchase_price,
            "shipping": self.shipping,
            "total_cost": self.total_cost,
            "seller": self.seller,
            "source": self.source,
            "purchase_date": self.purchase_date,
            "notes": self.notes,
            "country": self.country,
            "denomination": self.denomination,
            "year": self.year,
            "grade": self.grade,
            "linked_photo_ids": ";".join(self.linked_photo_ids),
        }


@dataclass
class SaleRecord:
    item: str
    sale_price: float = 0.0
    fees: float = 0.0
    buyer_source: str = ""
    sale_date: str = ""
    notes: str = ""
    country: str = ""
    denomination: str = ""
    year: str = ""
    grade: str = ""
    linked_photo_ids: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.item = (self.item or "").strip()
        self.sale_price = _money(self.sale_price)
        self.fees = _money(self.fees)
        self.buyer_source = (self.buyer_source or "").strip()
        self.sale_date = self.sale_date or _today()
        self.notes = (self.notes or "").strip()
        self.country = (self.country or "").strip()
        self.denomination = (self.denomination or "").strip()
        self.year = str(self.year or "").strip()
        self.grade = (self.grade or "").strip()

    @property
    def net_proceeds(self) -> float:
        return round(self.sale_price - self.fees, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item": self.item,
            "sale_price": self.sale_price,
            "fees": self.fees,
            "net_proceeds": self.net_proceeds,
            "buyer_source": self.buyer_source,
            "sale_date": self.sale_date,
            "notes": self.notes,
            "country": self.country,
            "denomination": self.denomination,
            "year": self.year,
            "grade": self.grade,
            "linked_photo_ids": ";".join(self.linked_photo_ids),
        }


@dataclass
class AuctionRecord:
    item: str
    bid_amount: float = 0.0
    winning_bid: float = 0.0
    auction_result: str = "Passed"
    source: str = ""
    auction_date: str = ""
    notes: str = ""
    country: str = ""
    denomination: str = ""
    year: str = ""
    grade: str = ""
    linked_photo_ids: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.item = (self.item or "").strip()
        self.bid_amount = _money(self.bid_amount)
        self.winning_bid = _money(self.winning_bid)
        self.auction_result = self._normalize_result(self.auction_result)
        self.source = (self.source or "").strip()
        self.auction_date = self.auction_date or _today()
        self.notes = (self.notes or "").strip()
        self.country = (self.country or "").strip()
        self.denomination = (self.denomination or "").strip()
        self.year = str(self.year or "").strip()
        self.grade = (self.grade or "").strip()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item": self.item,
            "bid_amount": self.bid_amount,
            "winning_bid": self.winning_bid,
            "auction_result": self.auction_result,
            "source": self.source,
            "auction_date": self.auction_date,
            "notes": self.notes,
            "country": self.country,
            "denomination": self.denomination,
            "year": self.year,
            "grade": self.grade,
            "linked_photo_ids": ";".join(self.linked_photo_ids),
        }

    @staticmethod
    def _normalize_result(value: str) -> str:
        text = (value or "").strip().lower()
        if text == "won":
            return "Won"
        if text == "lost":
            return "Lost"
        return "Passed"


@dataclass
class MarketSummary:
    observation_count: int
    purchase_count: int
    sale_count: int
    auction_count: int
    average_observed_price: float
    average_purchase_price: float
    average_sale_price: float

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class MarketContext:
    observed_costs: List[float] = field(default_factory=list)
    current_listing_cost: float = 0.0
    context_summary: str = "No local observation context available."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observed_costs": list(self.observed_costs),
            "current_listing_cost": self.current_listing_cost,
            "context_summary": self.context_summary,
        }


@dataclass
class MarketAwarenessReport:
    summary: MarketSummary
    observations: List[ObservedPriceRecord] = field(default_factory=list)
    purchases: List[PurchaseRecord] = field(default_factory=list)
    sales: List[SaleRecord] = field(default_factory=list)
    auctions: List[AuctionRecord] = field(default_factory=list)
    recent_activity: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "observations": [record.to_dict() for record in self.observations],
            "purchases": [record.to_dict() for record in self.purchases],
            "sales": [record.to_dict() for record in self.sales],
            "auctions": [record.to_dict() for record in self.auctions],
            "recent_activity": list(self.recent_activity),
        }


class MarketAwarenessEngine:
    """Generate personal market summaries from locally stored records."""

    def __init__(
        self,
        observations: Optional[Iterable[ObservedPriceRecord]] = None,
        purchases: Optional[Iterable[PurchaseRecord]] = None,
        sales: Optional[Iterable[SaleRecord]] = None,
        auctions: Optional[Iterable[AuctionRecord]] = None,
    ):
        self.observations = list(observations or [])
        self.purchases = list(purchases or [])
        self.sales = list(sales or [])
        self.auctions = list(auctions or [])

    def generate_report(self) -> MarketAwarenessReport:
        return MarketAwarenessReport(
            summary=MarketSummary(
                observation_count=len(self.observations),
                purchase_count=len(self.purchases),
                sale_count=len(self.sales),
                auction_count=len(self.auctions),
                average_observed_price=self._average([record.total_observed_cost for record in self.observations]),
                average_purchase_price=self._average([record.total_cost for record in self.purchases]),
                average_sale_price=self._average([record.net_proceeds for record in self.sales]),
            ),
            observations=list(self.observations),
            purchases=list(self.purchases),
            sales=list(self.sales),
            auctions=list(self.auctions),
            recent_activity=self._recent_activity(),
        )

    def historical_context_for_candidate(self, candidate: Any, current_listing_cost: float = 0.0) -> MarketContext:
        matches = [
            record.total_observed_cost
            for record in self.observations
            if self._candidate_matches_record(candidate, record)
        ]
        matches = sorted(matches)
        if not matches:
            return MarketContext([], _money(current_listing_cost))
        current = _money(current_listing_cost)
        low = matches[0]
        high = matches[-1]
        avg = self._average(matches)
        if current <= 0:
            summary = f"Recent observed range: ${low:.2f}-${high:.2f}; average ${avg:.2f}."
        elif current < low:
            summary = "Below recent observed range"
        elif current > high:
            summary = "Above recent observed range"
        else:
            summary = "Within recent observed range"
        return MarketContext(matches, current, summary)

    def format_markdown(self) -> str:
        report = self.generate_report()
        s = report.summary
        lines = [
            "# Market Awareness Report",
            "",
            "## Summary",
            "",
            f"- Observations: {s.observation_count}",
            f"- Purchases: {s.purchase_count}",
            f"- Sales: {s.sale_count}",
            f"- Auctions: {s.auction_count}",
            f"- Average observed price: ${s.average_observed_price:.2f}",
            f"- Average purchase price: ${s.average_purchase_price:.2f}",
            f"- Average sale proceeds: ${s.average_sale_price:.2f}",
            "",
            "## Recent Activity",
            "",
        ]
        lines.extend(f"- {activity}" for activity in report.recent_activity) if report.recent_activity else lines.append("- No activity recorded.")
        lines.extend(["", "## Observations", ""])
        lines.extend(f"- {record.item_name}: ${record.total_observed_cost:.2f} from {record.source or 'unknown source'}" for record in self.observations) if self.observations else lines.append("- None")
        lines.extend(["", "## Purchases", ""])
        lines.extend(f"- {record.item}: ${record.total_cost:.2f} from {record.seller or record.source or 'unknown seller'}" for record in self.purchases) if self.purchases else lines.append("- None")
        lines.extend(["", "## Sales", ""])
        lines.extend(f"- {record.item}: net ${record.net_proceeds:.2f}" for record in self.sales) if self.sales else lines.append("- None")
        lines.extend(["", "## Auctions", ""])
        lines.extend(f"- {record.item}: {record.auction_result}; bid ${record.bid_amount:.2f}; winning ${record.winning_bid:.2f}" for record in self.auctions) if self.auctions else lines.append("- None")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_markdown())
            return True
        except Exception as exc:
            print(f"Error exporting market awareness markdown: {exc}")
            return False

    def export_csv(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Section", "Item", "Country", "Denomination", "Year", "Grade", "Amount", "Source", "Date", "Notes", "Linked Photos"])
                for record in self.observations:
                    writer.writerow(["Observation", record.item_name, record.country, record.denomination, record.year, record.grade, record.total_observed_cost, record.source, record.date_observed, record.notes, ";".join(record.linked_photo_ids)])
                for record in self.purchases:
                    writer.writerow(["Purchase", record.item, record.country, record.denomination, record.year, record.grade, record.total_cost, record.source or record.seller, record.purchase_date, record.notes, ";".join(record.linked_photo_ids)])
                for record in self.sales:
                    writer.writerow(["Sale", record.item, record.country, record.denomination, record.year, record.grade, record.net_proceeds, record.buyer_source, record.sale_date, record.notes, ";".join(record.linked_photo_ids)])
                for record in self.auctions:
                    writer.writerow(["Auction", record.item, record.country, record.denomination, record.year, record.grade, record.winning_bid, record.source, record.auction_date, f"{record.auction_result}; {record.notes}", ";".join(record.linked_photo_ids)])
            return True
        except Exception as exc:
            print(f"Error exporting market awareness CSV: {exc}")
            return False

    def _recent_activity(self) -> List[str]:
        rows = []
        for record in self.observations:
            rows.append((record.date_observed, f"Observed {record.item_name} at ${record.total_observed_cost:.2f}"))
        for record in self.purchases:
            rows.append((record.purchase_date, f"Purchased {record.item} at ${record.total_cost:.2f}"))
        for record in self.sales:
            rows.append((record.sale_date, f"Sold {record.item} for net ${record.net_proceeds:.2f}"))
        for record in self.auctions:
            rows.append((record.auction_date, f"Auction {record.auction_result}: {record.item}"))
        return [text for _, text in sorted(rows, reverse=True)[:10]]

    def _candidate_matches_record(self, candidate: Any, record: ObservedPriceRecord) -> bool:
        return (
            self._normalize(getattr(candidate, "country", "")) == self._normalize(record.country)
            and self._normalize(getattr(candidate, "denomination", "")) == self._normalize(record.denomination)
            and str(getattr(candidate, "year", "") or "").strip() == record.year
        )

    @staticmethod
    def _average(values: List[float]) -> float:
        return round(sum(values) / len(values), 2) if values else 0.0

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(str(value or "").lower().split())
