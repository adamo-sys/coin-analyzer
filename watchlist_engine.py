"""Watchlists and on-demand alerts for collector opportunity reports.

This module is intentionally report-driven. It does not poll sources, push
notifications, buy items, bid on items, or mutate collection data.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


WATCH_TYPE_SERIES = "Series Watch"
WATCH_TYPE_SPECIFIC_COIN = "Specific Coin Watch"
WATCH_TYPE_KEYWORD = "Keyword Watch"
WATCH_TYPE_CUSTOM = "Custom Watch"

ALERT_TYPE_WATCHLIST_MATCH = "Watchlist Match"
ALERT_TYPE_UPGRADE_OPPORTUNITY = "Upgrade Opportunity"
ALERT_TYPE_COLLECTION_GAP_OPPORTUNITY = "Collection Gap Opportunity"
ALERT_TYPE_HIGH_PRIORITY_OPPORTUNITY = "High Priority Opportunity"
ALERT_TYPE_RARE_TARGET_OPPORTUNITY = "Rare Target Opportunity"


class WatchPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(_safe_text(item) for item in value)
    return str(value)


def _normalize(value: Any) -> str:
    text = _safe_text(value).lower()
    text = text.replace("¢", " cents ")
    text = text.replace("cents", " cent ")
    text = text.replace("nickel", " 5 cent ")
    text = text.replace("dime", " 10 cent ")
    text = text.replace("quarter", " 25 cent ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(value: Any) -> List[str]:
    return [token for token in _normalize(value).split() if len(token) > 1]


def _dedupe(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        text = _safe_text(value).strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(value)))


def _call_to_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        try:
            data = value.to_dict()
            if isinstance(data, dict):
                return data
        except Exception:
            return {}
    return {}


def _candidate_listing(candidate: Any) -> Any:
    if hasattr(candidate, "original_listing"):
        return getattr(candidate, "original_listing")
    if hasattr(candidate, "listing"):
        return getattr(candidate, "listing")
    if hasattr(candidate, "deal_result") and hasattr(candidate.deal_result, "listing"):
        return candidate.deal_result.listing
    return candidate


def _candidate_title(candidate: Any) -> str:
    listing = _candidate_listing(candidate)
    if isinstance(listing, dict):
        return _safe_text(listing.get("title") or listing.get("item_name") or listing.get("coin"))
    return _safe_text(getattr(listing, "title", "") or getattr(candidate, "title", ""))


def _candidate_recommendation(candidate: Any) -> str:
    for attr in ("escalated_recommendation", "recommendation", "original_recommendation"):
        if hasattr(candidate, attr):
            value = _safe_text(getattr(candidate, attr)).strip()
            if value:
                return value
    if hasattr(candidate, "deal_result"):
        return _candidate_recommendation(candidate.deal_result)
    data = _call_to_dict(candidate)
    return _safe_text(data.get("escalated_recommendation") or data.get("recommendation"))


def _candidate_relevance(candidate: Any) -> int:
    if hasattr(candidate, "collection_relevance"):
        relevance = getattr(candidate, "collection_relevance")
        if hasattr(relevance, "collection_relevance_score"):
            return _as_int(relevance.collection_relevance_score)
    for attr in ("collection_fit_score", "priority_score"):
        if hasattr(candidate, attr):
            return _as_int(getattr(candidate, attr))
    if hasattr(candidate, "deal_result"):
        return max(_candidate_relevance(candidate.deal_result), _candidate_relevance(getattr(candidate, "deal_result")))
    data = _call_to_dict(candidate)
    return _as_int(data.get("collection_relevance_score") or data.get("collection_fit_score") or data.get("priority_score"))


def _candidate_opportunity_score(candidate: Any) -> int:
    if hasattr(candidate, "ranking_score") and hasattr(candidate.ranking_score, "score"):
        return _as_int(candidate.ranking_score.score)
    for attr in ("priority_score", "collection_fit_score"):
        if hasattr(candidate, attr):
            return _as_int(getattr(candidate, attr))
    if hasattr(candidate, "deal_result"):
        return max(_candidate_opportunity_score(candidate.deal_result), _candidate_relevance(candidate.deal_result))
    data = _call_to_dict(candidate)
    return _as_int(data.get("ranking_score") or data.get("priority_score") or data.get("collection_fit_score"))


def _candidate_market_confidence(candidate: Any) -> int:
    if hasattr(candidate, "opportunity_confidence"):
        return _as_int(getattr(candidate, "opportunity_confidence"))
    if hasattr(candidate, "market_report") and hasattr(candidate.market_report, "confidence"):
        return _as_int(getattr(candidate.market_report.confidence, "score", 0))
    data = _call_to_dict(candidate)
    return _as_int(data.get("opportunity_confidence") or data.get("confidence") or data.get("confidence_score"))


def _candidate_classifications(candidate: Any) -> List[str]:
    values: List[str] = []
    if hasattr(candidate, "collection_relevance"):
        relevance = getattr(candidate, "collection_relevance")
        values.extend(_safe_text(item) for item in getattr(relevance, "classifications", []) or [])
        values.append(_safe_text(getattr(relevance, "collection_goal_advanced", "")))
        values.append(_safe_text(getattr(relevance, "relevance_explanation", "")))
    for attr in ("collection_status", "collection_impact", "budget_fit"):
        if hasattr(candidate, attr):
            values.append(_safe_text(getattr(candidate, attr)))
    if hasattr(candidate, "deal_result"):
        values.extend(_candidate_classifications(candidate.deal_result))
    data = _call_to_dict(candidate)
    for key in ("classifications", "collection_status", "collection_impact", "collection_goal_advanced", "reasons"):
        values.append(_safe_text(data.get(key)))
    return _dedupe(values)


def _candidate_search_text(candidate: Any) -> str:
    parts = [_candidate_title(candidate), _candidate_recommendation(candidate)]
    listing = _candidate_listing(candidate)
    for attr in ("description", "seller", "source", "listing_url", "notes"):
        if hasattr(listing, attr):
            parts.append(_safe_text(getattr(listing, attr)))
    data = _call_to_dict(candidate)
    parts.extend(_safe_text(value) for value in data.values() if not isinstance(value, (dict, list)))
    parts.extend(_candidate_classifications(candidate))
    return _normalize(" ".join(parts))


def _candidate_summary(candidate: Any) -> Dict[str, Any]:
    listing = _candidate_listing(candidate)
    data = _call_to_dict(candidate)
    if hasattr(listing, "to_dict"):
        listing_data = listing.to_dict()
    elif isinstance(listing, dict):
        listing_data = dict(listing)
    else:
        listing_data = {}
    summary = {
        "title": _candidate_title(candidate),
        "recommendation": _candidate_recommendation(candidate),
        "collection_relevance_score": _candidate_relevance(candidate),
        "opportunity_score": _candidate_opportunity_score(candidate),
        "market_confidence": _candidate_market_confidence(candidate),
        "classifications": "; ".join(_candidate_classifications(candidate)),
    }
    for key in ("total_cost", "price_cad", "seller", "source", "listing_url"):
        if key in listing_data:
            summary[key] = listing_data[key]
        elif key in data:
            summary[key] = data[key]
    return summary


@dataclass
class WatchlistItem:
    name: str
    watch_type: str = WATCH_TYPE_KEYWORD
    query: str = ""
    priority: WatchPriority | str = WatchPriority.NORMAL
    keywords: List[str] = field(default_factory=list)
    notes: str = ""
    active: bool = True

    def __post_init__(self) -> None:
        self.name = _safe_text(self.name).strip() or _safe_text(self.query).strip() or "Untitled Watch"
        if isinstance(self.priority, WatchPriority):
            pass
        else:
            try:
                self.priority = WatchPriority[_safe_text(self.priority).upper()]
            except KeyError:
                self.priority = WatchPriority.NORMAL
        self.watch_type = _safe_text(self.watch_type).strip() or WATCH_TYPE_KEYWORD
        self.query = _safe_text(self.query).strip() or self.name
        self.keywords = _dedupe(self.keywords or _tokens(self.query))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "watch_type": self.watch_type,
            "query": self.query,
            "priority": self.priority.value,
            "keywords": "; ".join(self.keywords),
            "notes": self.notes,
            "active": self.active,
        }


@dataclass
class Watchlist:
    name: str
    items: List[WatchlistItem] = field(default_factory=list)
    notes: str = ""

    def add_item(self, item: WatchlistItem) -> None:
        self.items.append(item)

    def remove_item(self, name_or_query: str) -> bool:
        needle = _normalize(name_or_query)
        before = len(self.items)
        self.items = [
            item for item in self.items
            if _normalize(item.name) != needle and _normalize(item.query) != needle
        ]
        return len(self.items) != before

    def active_items(self) -> List[WatchlistItem]:
        return [item for item in self.items if item.active]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "notes": self.notes,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass
class WatchlistMatch:
    watchlist_name: str
    watch_item: WatchlistItem
    candidate_title: str
    confidence: int
    relevance: int
    match_reason: str
    candidate_summary: Dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "watchlist_name": self.watchlist_name,
            "watch_name": self.watch_item.name,
            "watch_type": self.watch_item.watch_type,
            "watch_priority": self.watch_item.priority.value,
            "query": self.watch_item.query,
            "candidate_title": self.candidate_title,
            "confidence": self.confidence,
            "relevance": self.relevance,
            "recommendation": self.recommendation,
            "match_reason": self.match_reason,
            **{f"candidate_{key}": value for key, value in self.candidate_summary.items()},
        }


@dataclass
class AlertScore:
    score: int
    watch_priority_points: int = 0
    collection_relevance_points: int = 0
    opportunity_points: int = 0
    market_confidence_points: int = 0
    upgrade_points: int = 0
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_score": self.score,
            "watch_priority_points": self.watch_priority_points,
            "collection_relevance_points": self.collection_relevance_points,
            "opportunity_points": self.opportunity_points,
            "market_confidence_points": self.market_confidence_points,
            "upgrade_points": self.upgrade_points,
            "score_explanation": self.explanation,
        }


@dataclass
class AlertRecord:
    alert_type: str
    candidate_title: str
    score: AlertScore
    recommendation: str
    reason: str
    matched_watch: Optional[WatchlistMatch] = None
    generated_at: str = ""
    candidate_summary: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        watch = self.matched_watch
        return {
            "alert_type": self.alert_type,
            "candidate_title": self.candidate_title,
            "recommendation": self.recommendation,
            "reason": self.reason,
            "generated_at": self.generated_at,
            "matched_watch": watch.watch_item.name if watch else "",
            "watch_priority": watch.watch_item.priority.value if watch else "",
            "watch_confidence": watch.confidence if watch else "",
            **self.score.to_dict(),
            **{f"candidate_{key}": value for key, value in self.candidate_summary.items()},
        }


@dataclass
class WatchlistReport:
    watchlist: Watchlist
    matches: List[WatchlistMatch] = field(default_factory=list)
    candidates_scanned: int = 0
    warnings: List[str] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "watchlist": self.watchlist.to_dict(),
            "generated_at": self.generated_at,
            "candidates_scanned": self.candidates_scanned,
            "match_count": len(self.matches),
            "warnings": "; ".join(self.warnings),
            "matches": [match.to_dict() for match in self.matches],
        }

    def format_markdown(self) -> str:
        lines = [
            "# Watchlist Report",
            "",
            f"- Generated: {self.generated_at}",
            f"- Watchlist: {self.watchlist.name}",
            f"- Candidates scanned: {self.candidates_scanned}",
            f"- Matches: {len(self.matches)}",
            "- Safety note: report-driven alerts only; no background polling, notifications, purchases, or collection mutation.",
            "",
        ]
        if self.warnings:
            lines.extend(["## Warnings", ""])
            lines.extend(f"- {warning}" for warning in self.warnings)
            lines.append("")
        lines.extend(["## Matches", ""])
        if not self.matches:
            lines.append("- None.")
        for index, match in enumerate(self.matches, start=1):
            lines.extend([
                f"### {index}. {match.candidate_title}",
                f"- Watch: {match.watch_item.name} ({match.watch_item.priority.value})",
                f"- Type: {match.watch_item.watch_type}",
                f"- Confidence: {match.confidence}",
                f"- Relevance: {match.relevance}",
                f"- Recommendation: {match.recommendation or 'Unknown'}",
                f"- Reason: {match.match_reason}",
                "",
            ])
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        fieldnames = [
            "watchlist_name", "watch_name", "watch_type", "watch_priority", "query",
            "candidate_title", "confidence", "relevance", "recommendation", "match_reason",
            "candidate_total_cost", "candidate_source", "candidate_seller", "candidate_listing_url",
            "candidate_classifications",
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for match in self.matches:
                writer.writerow(match.to_dict())
        return True


@dataclass
class AlertReport:
    alerts: List[AlertRecord] = field(default_factory=list)
    candidates_scanned: int = 0
    warnings: List[str] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "candidates_scanned": self.candidates_scanned,
            "alert_count": len(self.alerts),
            "warnings": "; ".join(self.warnings),
            "alerts": [alert.to_dict() for alert in self.alerts],
        }

    def format_markdown(self) -> str:
        lines = [
            "# Alert Report",
            "",
            f"- Generated: {self.generated_at}",
            f"- Candidates scanned: {self.candidates_scanned}",
            f"- Alerts: {len(self.alerts)}",
            "- Safety note: alerts are generated on demand only; no push, email, SMS, background polling, purchasing, bidding, or collection mutation.",
            "",
        ]
        if self.warnings:
            lines.extend(["## Warnings", ""])
            lines.extend(f"- {warning}" for warning in self.warnings)
            lines.append("")
        lines.extend(["## Alerts", ""])
        if not self.alerts:
            lines.append("- None.")
        for index, alert in enumerate(self.alerts, start=1):
            lines.extend([
                f"### {index}. {alert.candidate_title}",
                f"- Type: {alert.alert_type}",
                f"- Alert score: {alert.score.score}",
                f"- Recommendation: {alert.recommendation or 'Unknown'}",
                f"- Reason: {alert.reason}",
                f"- Score basis: {alert.score.explanation}",
                "",
            ])
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        fieldnames = [
            "alert_type", "candidate_title", "recommendation", "reason", "generated_at",
            "matched_watch", "watch_priority", "watch_confidence", "alert_score",
            "watch_priority_points", "collection_relevance_points", "opportunity_points",
            "market_confidence_points", "upgrade_points", "score_explanation",
            "candidate_total_cost", "candidate_source", "candidate_seller", "candidate_listing_url",
            "candidate_classifications",
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for alert in self.alerts:
                writer.writerow(alert.to_dict())
        return True


class WatchlistEngine:
    """Match collector-defined watchlists against existing candidate outputs."""

    def __init__(self, watchlists: Optional[Sequence[Watchlist]] = None) -> None:
        self.watchlists: List[Watchlist] = list(watchlists or [])

    @classmethod
    def adam_presets(cls) -> Watchlist:
        return Watchlist(
            name="Adam Collection Presets",
            notes="Editable starter watches for current collection priorities.",
            items=[
                WatchlistItem("Newfoundland Coins", WATCH_TYPE_SERIES, "Newfoundland", WatchPriority.CRITICAL),
                WatchlistItem("Newfoundland Silver", WATCH_TYPE_SERIES, "Newfoundland silver 5 10 20 50 cents", WatchPriority.CRITICAL),
                WatchlistItem("Canadian Silver", WATCH_TYPE_SERIES, "Canada silver dime quarter half dollar dollar", WatchPriority.HIGH),
                WatchlistItem("Canadian Banknotes", WATCH_TYPE_SERIES, "Canada banknote bank note chartered note", WatchPriority.HIGH),
                WatchlistItem("1859 Large Cent Varieties", WATCH_TYPE_SPECIFIC_COIN, "1859 Canada Large Cent Wide 9 Narrow 9 over 9", WatchPriority.CRITICAL),
                WatchlistItem("1926 Near 6 Nickel", WATCH_TYPE_SPECIFIC_COIN, "1926 Near 6 nickel Canada 5 cents", WatchPriority.CRITICAL),
                WatchlistItem("1973 Large Bust Quarter", WATCH_TYPE_SPECIFIC_COIN, "1973 Large Bust quarter Canada 25 cents", WatchPriority.CRITICAL),
            ],
        )

    def add_watchlist(self, watchlist: Watchlist) -> None:
        self.watchlists.append(watchlist)

    def remove_watchlist(self, name: str) -> bool:
        needle = _normalize(name)
        before = len(self.watchlists)
        self.watchlists = [watchlist for watchlist in self.watchlists if _normalize(watchlist.name) != needle]
        return len(self.watchlists) != before

    def update_watchlist(self, watchlist: Watchlist) -> None:
        self.remove_watchlist(watchlist.name)
        self.add_watchlist(watchlist)

    def scan(self, candidates: Sequence[Any], watchlists: Optional[Sequence[Watchlist]] = None) -> WatchlistReport:
        selected = list(watchlists or self.watchlists)
        merged = self._merge_watchlists(selected)
        matches: List[WatchlistMatch] = []
        for candidate in candidates:
            for item in merged.active_items():
                match = self.match_candidate(candidate, item, merged.name)
                if match:
                    matches.append(match)
        matches.sort(key=lambda match: (match.watch_item.priority.value, -match.confidence, -match.relevance, match.candidate_title))
        priority_order = {WatchPriority.CRITICAL.value: 0, WatchPriority.HIGH.value: 1, WatchPriority.NORMAL.value: 2, WatchPriority.LOW.value: 3}
        matches.sort(key=lambda match: (priority_order.get(match.watch_item.priority.value, 9), -match.confidence, -match.relevance, match.candidate_title))
        return WatchlistReport(watchlist=merged, matches=matches, candidates_scanned=len(candidates))

    def match_candidate(self, candidate: Any, watch_item: WatchlistItem, watchlist_name: str = "") -> Optional[WatchlistMatch]:
        searchable = _candidate_search_text(candidate)
        if not searchable or not watch_item.active:
            return None
        confidence, reason = self._match_score(searchable, watch_item)
        if confidence <= 0:
            return None
        relevance = _candidate_relevance(candidate)
        return WatchlistMatch(
            watchlist_name=watchlist_name or "Watchlist",
            watch_item=watch_item,
            candidate_title=_candidate_title(candidate),
            confidence=confidence,
            relevance=relevance,
            match_reason=reason,
            candidate_summary=_candidate_summary(candidate),
            recommendation=_candidate_recommendation(candidate),
        )

    def _match_score(self, searchable: str, watch_item: WatchlistItem) -> Tuple[int, str]:
        query = _normalize(watch_item.query)
        keywords = [_normalize(keyword) for keyword in watch_item.keywords if _normalize(keyword)]
        watch_type = watch_item.watch_type.lower()

        if "keyword" in watch_type:
            hits = [keyword for keyword in keywords if keyword and keyword in searchable]
            if hits:
                confidence = min(95, 45 + (len(hits) * 15))
                return confidence, f"Matched keyword(s): {', '.join(hits[:5])}"
            return 0, ""

        if "specific" in watch_type:
            terms = [term for term in _tokens(query) if len(term) > 2 or term.isdigit()]
            hits = [term for term in terms if term in searchable]
            if not terms:
                return 0, ""
            ratio = len(hits) / len(terms)
            if ratio >= 0.75:
                confidence = _clamp(55 + int(ratio * 40))
                return confidence, f"Matched specific target terms: {', '.join(hits)}"
            return 0, ""

        if "series" in watch_type:
            series_confidence = self._series_match_confidence(searchable, query, keywords)
            if series_confidence > 0:
                return series_confidence, f"Matched series watch: {watch_item.query}"
            return 0, ""

        if query and query in searchable:
            return 75, f"Matched custom watch query: {watch_item.query}"
        hits = [keyword for keyword in keywords if keyword and keyword in searchable]
        if hits:
            return min(85, 40 + len(hits) * 12), f"Matched custom keyword(s): {', '.join(hits[:5])}"
        return 0, ""

    def _series_match_confidence(self, searchable: str, query: str, keywords: List[str]) -> int:
        if query and query in searchable:
            return 85
        hits = [keyword for keyword in keywords if keyword and keyword in searchable]
        confidence = 0
        if hits:
            confidence = 45 + min(35, len(hits) * 8)
        if "newfoundland" in query and "newfoundland" in searchable:
            confidence = max(confidence, 80)
            if any(term in query for term in ("silver", "5", "10", "20", "50")) and any(term in searchable for term in ("silver", "5 cent", "10 cent", "20 cent", "50 cent")):
                confidence = max(confidence, 90)
        if "canada silver" in query or "canadian silver" in query:
            if "canada" in searchable and any(term in searchable for term in ("silver", "10 cent", "25 cent", "50 cent", "dollar")):
                confidence = max(confidence, 88)
        if "banknote" in query or "bank note" in query:
            if any(term in searchable for term in ("banknote", "bank note", "note", "chartered", "pmg")):
                confidence = max(confidence, 82)
        if "large cent" in query and ("large cent" in searchable or ("1859" in searchable and "cent" in searchable)):
            confidence = max(confidence, 86)
        return _clamp(confidence)

    def _merge_watchlists(self, watchlists: Sequence[Watchlist]) -> Watchlist:
        if len(watchlists) == 1:
            return watchlists[0]
        items: List[WatchlistItem] = []
        names: List[str] = []
        for watchlist in watchlists:
            names.append(watchlist.name)
            items.extend(watchlist.items)
        return Watchlist(name="; ".join(names) or "Watchlists", items=items)


class AlertEngine:
    """Generate on-demand alert reports from watchlists and existing candidate scoring."""

    def __init__(self, watchlist_engine: Optional[WatchlistEngine] = None) -> None:
        self.watchlist_engine = watchlist_engine or WatchlistEngine([WatchlistEngine.adam_presets()])

    def generate_alerts(self, candidates: Sequence[Any], watchlists: Optional[Sequence[Watchlist]] = None) -> AlertReport:
        watch_report = self.watchlist_engine.scan(candidates, watchlists)
        alerts: List[AlertRecord] = []
        seen = set()
        for match in watch_report.matches:
            alert = self._alert_from_match(match)
            alerts.append(alert)
            seen.add((alert.alert_type, alert.candidate_title.lower(), alert.reason.lower()))
        for candidate in candidates:
            for alert_type, reason in self._opportunity_alert_reasons(candidate):
                key = (alert_type, _candidate_title(candidate).lower(), reason.lower())
                if key in seen:
                    continue
                score = self._score_alert(candidate, None, alert_type)
                if score.score <= 0:
                    continue
                alerts.append(AlertRecord(
                    alert_type=alert_type,
                    candidate_title=_candidate_title(candidate),
                    score=score,
                    recommendation=_candidate_recommendation(candidate),
                    reason=reason,
                    candidate_summary=_candidate_summary(candidate),
                ))
                seen.add(key)
        alerts.sort(key=lambda alert: (-alert.score.score, alert.alert_type, alert.candidate_title))
        return AlertReport(alerts=alerts, candidates_scanned=len(candidates), warnings=watch_report.warnings)

    def _alert_from_match(self, match: WatchlistMatch) -> AlertRecord:
        score = self._score_alert(match.candidate_summary, match, ALERT_TYPE_WATCHLIST_MATCH)
        return AlertRecord(
            alert_type=ALERT_TYPE_WATCHLIST_MATCH,
            candidate_title=match.candidate_title,
            score=score,
            recommendation=match.recommendation,
            reason=match.match_reason,
            matched_watch=match,
            candidate_summary=match.candidate_summary,
        )

    def _opportunity_alert_reasons(self, candidate: Any) -> List[Tuple[str, str]]:
        title = _normalize(_candidate_title(candidate))
        text = _candidate_search_text(candidate)
        classes = _normalize(" ".join(_candidate_classifications(candidate)))
        reasons: List[Tuple[str, str]] = []
        if "upgrade" in classes or "upgrade" in text:
            reasons.append((ALERT_TYPE_UPGRADE_OPPORTUNITY, "Existing candidate output indicates upgrade potential."))
        if "gap" in classes or "collection gap" in text or "missing" in classes:
            reasons.append((ALERT_TYPE_COLLECTION_GAP_OPPORTUNITY, "Existing candidate output indicates a collection-gap opportunity."))
        if _candidate_opportunity_score(candidate) >= 75 or _candidate_relevance(candidate) >= 75:
            reasons.append((ALERT_TYPE_HIGH_PRIORITY_OPPORTUNITY, "Existing candidate scoring marks this as high priority."))
        rare_terms = ("near 6", "large bust", "wide 9", "narrow 9", "newfoundland", "chartered")
        if any(term in title or term in text for term in rare_terms):
            reasons.append((ALERT_TYPE_RARE_TARGET_OPPORTUNITY, "Candidate text matches a high-priority collector target."))
        return _dedupe_tuple(reasons)

    def _score_alert(self, candidate: Any, match: Optional[WatchlistMatch], alert_type: str) -> AlertScore:
        priority = match.watch_item.priority if match else WatchPriority.NORMAL
        priority_points = {
            WatchPriority.CRITICAL: 35,
            WatchPriority.HIGH: 28,
            WatchPriority.NORMAL: 18,
            WatchPriority.LOW: 8,
        }.get(priority, 18)
        relevance = match.relevance if match else _candidate_relevance(candidate)
        confidence = match.confidence if match else _candidate_market_confidence(candidate)
        opportunity = _candidate_opportunity_score(candidate)
        classifications = _normalize(" ".join(_candidate_classifications(candidate)))
        upgrade_points = 10 if "upgrade" in classifications or alert_type == ALERT_TYPE_UPGRADE_OPPORTUNITY else 0
        if alert_type == ALERT_TYPE_RARE_TARGET_OPPORTUNITY:
            upgrade_points = max(upgrade_points, 5)
        relevance_points = min(25, max(0, relevance) // 4)
        opportunity_points = min(20, max(0, opportunity) // 5)
        confidence_points = min(15, max(0, confidence) // 7)
        total = _clamp(priority_points + relevance_points + opportunity_points + confidence_points + upgrade_points)
        explanation = (
            f"priority {priority_points}, relevance {relevance_points}, opportunity {opportunity_points}, "
            f"market confidence {confidence_points}, upgrade/rare target {upgrade_points}"
        )
        return AlertScore(
            score=total,
            watch_priority_points=priority_points,
            collection_relevance_points=relevance_points,
            opportunity_points=opportunity_points,
            market_confidence_points=confidence_points,
            upgrade_points=upgrade_points,
            explanation=explanation,
        )


def _dedupe_tuple(values: Iterable[Tuple[str, str]]) -> List[Tuple[str, str]]:
    seen = set()
    result: List[Tuple[str, str]] = []
    for alert_type, reason in values:
        key = (alert_type, reason)
        if key not in seen:
            seen.add(key)
            result.append((alert_type, reason))
    return result
