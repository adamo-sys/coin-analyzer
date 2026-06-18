"""Point-in-time collection snapshots and historical comparison reports."""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from collection_integrity import CollectionIntegrityAudit
from collection_quality import CollectionQualityEngine
from market_awareness import MarketAwarenessEngine
from photo_vault import PhotoRecord, PhotoVault
from series_tracker import SeriesTracker
from smart_shopping_assistant import ShoppingCandidate


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _delta(current: float, previous: float) -> float:
    return round(float(current or 0) - float(previous or 0), 2)


@dataclass
class CollectionSnapshot:
    snapshot_timestamp: str
    collection_size: int = 0
    quality_score: int = 0
    integrity_score: int = 0
    photo_coverage: float = 0.0
    series_completion_metrics: Dict[str, float] = field(default_factory=dict)
    market_record_count: int = 0
    shopping_candidate_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_timestamp": self.snapshot_timestamp,
            "collection_size": self.collection_size,
            "quality_score": self.quality_score,
            "integrity_score": self.integrity_score,
            "photo_coverage": self.photo_coverage,
            "series_completion_metrics": dict(self.series_completion_metrics),
            "market_record_count": self.market_record_count,
            "shopping_candidate_count": self.shopping_candidate_count,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CollectionSnapshot":
        return cls(
            snapshot_timestamp=str(payload.get("snapshot_timestamp") or ""),
            collection_size=int(payload.get("collection_size") or 0),
            quality_score=int(payload.get("quality_score") or 0),
            integrity_score=int(payload.get("integrity_score") or 0),
            photo_coverage=float(payload.get("photo_coverage") or 0.0),
            series_completion_metrics={
                str(key): float(value or 0.0)
                for key, value in (payload.get("series_completion_metrics") or {}).items()
            },
            market_record_count=int(payload.get("market_record_count") or 0),
            shopping_candidate_count=int(payload.get("shopping_candidate_count") or 0),
        )


@dataclass
class GrowthSummary:
    current_size: int
    previous_size: int
    first_size: int
    growth_since_last_snapshot: int
    growth_since_first_snapshot: int

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class SeriesProgressDelta:
    series_name: str
    previous_completion: float
    current_completion: float
    completion_delta: float
    newly_completed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class CollectionSnapshotReport:
    current_snapshot: CollectionSnapshot
    previous_snapshot: Optional[CollectionSnapshot] = None
    first_snapshot: Optional[CollectionSnapshot] = None
    growth_summary: Optional[GrowthSummary] = None
    quality_delta: int = 0
    integrity_delta: int = 0
    photo_coverage_delta: float = 0.0
    series_progress: List[SeriesProgressDelta] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_snapshot": self.current_snapshot.to_dict(),
            "previous_snapshot": self.previous_snapshot.to_dict() if self.previous_snapshot else None,
            "first_snapshot": self.first_snapshot.to_dict() if self.first_snapshot else None,
            "growth_summary": self.growth_summary.to_dict() if self.growth_summary else None,
            "quality_delta": self.quality_delta,
            "integrity_delta": self.integrity_delta,
            "photo_coverage_delta": self.photo_coverage_delta,
            "series_progress": [row.to_dict() for row in self.series_progress],
        }

    def format_markdown(self) -> str:
        cur = self.current_snapshot
        prev = self.previous_snapshot
        lines = [
            "# Collection Snapshot Report",
            "",
            "## Current Snapshot",
            "",
            f"- Timestamp: {cur.snapshot_timestamp}",
            f"- Owned items: {cur.collection_size}",
            f"- Quality score: {cur.quality_score}",
            f"- Integrity score: {cur.integrity_score}",
            f"- Photo coverage: {cur.photo_coverage:.1f}%",
            f"- Market records: {cur.market_record_count}",
            f"- Shopping candidates: {cur.shopping_candidate_count}",
            "",
            "## Previous Snapshot",
            "",
        ]
        if prev:
            lines.extend([
                f"- Timestamp: {prev.snapshot_timestamp}",
                f"- Owned items: {prev.collection_size}",
                f"- Quality score: {prev.quality_score}",
                f"- Integrity score: {prev.integrity_score}",
                f"- Photo coverage: {prev.photo_coverage:.1f}%",
            ])
        else:
            lines.append("- No previous snapshot available.")
        lines.extend(["", "## Delta", ""])
        if self.growth_summary:
            lines.append(f"- Owned items since previous: {self.growth_summary.growth_since_last_snapshot:+d}")
            lines.append(f"- Owned items since first: {self.growth_summary.growth_since_first_snapshot:+d}")
        lines.extend([
            f"- Quality score: {self.quality_delta:+d}",
            f"- Integrity score: {self.integrity_delta:+d}",
            f"- Photo coverage: {self.photo_coverage_delta:+.1f}%",
            "",
            "## Series Progress",
            "",
        ])
        if self.series_progress:
            for row in self.series_progress:
                completed = " Newly completed." if row.newly_completed else ""
                lines.append(
                    f"- {row.series_name}: {row.previous_completion:.1f}% -> "
                    f"{row.current_completion:.1f}% ({row.completion_delta:+.1f}%).{completed}"
                )
        else:
            lines.append("- No series progress delta available.")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["section", "metric", "current", "previous", "delta"])
            current = self.current_snapshot
            previous = self.previous_snapshot or CollectionSnapshot("")
            writer.writerow(["snapshot", "owned_items", current.collection_size, previous.collection_size, self.growth_summary.growth_since_last_snapshot if self.growth_summary else 0])
            writer.writerow(["snapshot", "quality_score", current.quality_score, previous.quality_score, self.quality_delta])
            writer.writerow(["snapshot", "integrity_score", current.integrity_score, previous.integrity_score, self.integrity_delta])
            writer.writerow(["snapshot", "photo_coverage", current.photo_coverage, previous.photo_coverage, self.photo_coverage_delta])
            for row in self.series_progress:
                writer.writerow(["series", row.series_name, row.current_completion, row.previous_completion, row.completion_delta])
        return True


class CollectionSnapshotManager:
    """Create, persist, load, and compare collection snapshots."""

    def __init__(self, snapshot_path: str = os.path.join("collection_data", "app_state", "collection_snapshots.json")):
        self.snapshot_path = snapshot_path

    def create_snapshot(
        self,
        collection_items: Iterable[Any],
        want_list_intents: Optional[Iterable[Any]] = None,
        photo_records: Optional[Iterable[PhotoRecord]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
        shopping_candidates: Optional[Iterable[ShoppingCandidate]] = None,
    ) -> CollectionSnapshot:
        items = list(collection_items or [])
        wants = list(want_list_intents or [])
        photos = list(photo_records or [])
        market = market_awareness_engine or MarketAwarenessEngine()
        shopping = list(shopping_candidates or [])
        quality = CollectionQualityEngine(items, wants).generate_report()
        integrity = CollectionIntegrityAudit(
            items,
            photo_records=photos,
            market_awareness_engine=market,
            shopping_candidates=shopping,
        ).run()
        photo_summary = PhotoVault(photos, items).coverage_summary()
        series = {
            report.series_name: report.completion_percentage
            for report in SeriesTracker(items, wants).generate_reports()
        }
        market_count = sum(len(getattr(market, attr, [])) for attr in ["observations", "purchases", "sales", "auctions"])
        return CollectionSnapshot(
            snapshot_timestamp=_now_iso(),
            collection_size=len(items),
            quality_score=quality.overall_quality_score,
            integrity_score=integrity.integrity_score.score,
            photo_coverage=photo_summary.photo_coverage_percentage,
            series_completion_metrics=series,
            market_record_count=market_count,
            shopping_candidate_count=len(shopping),
        )

    def save_snapshot(self, snapshot: CollectionSnapshot) -> bool:
        snapshots = self.load_snapshots()
        snapshots.append(snapshot)
        self.save_snapshots(snapshots)
        return True

    def save_snapshots(self, snapshots: Iterable[CollectionSnapshot]) -> bool:
        directory = os.path.dirname(self.snapshot_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        payload = {"snapshots": [snapshot.to_dict() for snapshot in snapshots]}
        with open(self.snapshot_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        return True

    def load_snapshots(self) -> List[CollectionSnapshot]:
        if not os.path.exists(self.snapshot_path):
            return []
        with open(self.snapshot_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return [CollectionSnapshot.from_dict(row) for row in payload.get("snapshots", [])]

    def latest_report(self, current_snapshot: Optional[CollectionSnapshot] = None) -> CollectionSnapshotReport:
        snapshots = self.load_snapshots()
        current = current_snapshot or (snapshots[-1] if snapshots else CollectionSnapshot(_now_iso()))
        previous = snapshots[-2] if len(snapshots) >= 2 and current is snapshots[-1] else snapshots[-1] if snapshots and current is not snapshots[-1] else None
        first = snapshots[0] if snapshots else current
        return self.compare_snapshots(current, previous, first)

    def compare_snapshots(
        self,
        current: CollectionSnapshot,
        previous: Optional[CollectionSnapshot],
        first: Optional[CollectionSnapshot] = None,
    ) -> CollectionSnapshotReport:
        first = first or previous or current
        growth = GrowthSummary(
            current_size=current.collection_size,
            previous_size=previous.collection_size if previous else 0,
            first_size=first.collection_size,
            growth_since_last_snapshot=current.collection_size - (previous.collection_size if previous else 0),
            growth_since_first_snapshot=current.collection_size - first.collection_size,
        )
        return CollectionSnapshotReport(
            current_snapshot=current,
            previous_snapshot=previous,
            first_snapshot=first,
            growth_summary=growth,
            quality_delta=int(_delta(current.quality_score, previous.quality_score if previous else 0)),
            integrity_delta=int(_delta(current.integrity_score, previous.integrity_score if previous else 0)),
            photo_coverage_delta=_delta(current.photo_coverage, previous.photo_coverage if previous else 0.0),
            series_progress=self._series_progress(current, previous),
        )

    def _series_progress(self, current: CollectionSnapshot, previous: Optional[CollectionSnapshot]) -> List[SeriesProgressDelta]:
        previous_metrics = previous.series_completion_metrics if previous else {}
        rows = []
        for name, current_value in current.series_completion_metrics.items():
            previous_value = float(previous_metrics.get(name, 0.0))
            change = _delta(current_value, previous_value)
            if change:
                rows.append(SeriesProgressDelta(
                    series_name=name,
                    previous_completion=previous_value,
                    current_completion=current_value,
                    completion_delta=change,
                    newly_completed=previous_value < 100 <= current_value,
                ))
        return sorted(rows, key=lambda row: (-row.completion_delta, row.series_name))
