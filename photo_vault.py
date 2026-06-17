"""Structured photo metadata vault for collection and candidate images."""

import csv
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


PHOTO_TYPES = (
    "Collection Photo",
    "Candidate Photo",
    "Reference Photo",
    "Auction Photo",
    "Sold Photo",
)


@dataclass
class PhotoRecord:
    """Metadata-only photo record; no OCR or image recognition is performed."""

    file_path: str
    photo_type: str
    linked_collection_item_id: str = ""
    linked_candidate_id: str = ""
    linked_coin_name: str = ""
    created_date: str = ""
    notes: str = ""
    iccs_number: str = ""
    pcgs_number: str = ""
    ngc_number: str = ""

    def __post_init__(self) -> None:
        self.file_path = (self.file_path or "").strip()
        self.photo_type = self._normalize_photo_type(self.photo_type)
        self.linked_collection_item_id = str(self.linked_collection_item_id or "").strip()
        self.linked_candidate_id = str(self.linked_candidate_id or "").strip()
        self.linked_coin_name = (self.linked_coin_name or "").strip()
        self.created_date = self.created_date or datetime.now().strftime("%Y-%m-%d")
        self.notes = (self.notes or "").strip()
        self.iccs_number = self._clean_cert(self.iccs_number)
        self.pcgs_number = self._clean_cert(self.pcgs_number)
        self.ngc_number = self._clean_cert(self.ngc_number)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "photo_type": self.photo_type,
            "linked_collection_item_id": self.linked_collection_item_id,
            "linked_candidate_id": self.linked_candidate_id,
            "linked_coin_name": self.linked_coin_name,
            "created_date": self.created_date,
            "notes": self.notes,
            "iccs_number": self.iccs_number,
            "pcgs_number": self.pcgs_number,
            "ngc_number": self.ngc_number,
        }

    def certification_numbers(self) -> List[str]:
        return [value for value in [self.iccs_number, self.pcgs_number, self.ngc_number] if value]

    @staticmethod
    def _normalize_photo_type(photo_type: str) -> str:
        text = (photo_type or "").strip().lower()
        for supported in PHOTO_TYPES:
            if text == supported.lower():
                return supported
        return "Reference Photo"

    @staticmethod
    def _clean_cert(value: str) -> str:
        return str(value or "").strip().upper()


@dataclass
class CollectionPhotoStatus:
    item_id: str
    coin_name: str
    has_photos: bool
    photo_count: int
    certification_numbers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "coin_name": self.coin_name,
            "has_photos": self.has_photos,
            "photo_count": self.photo_count,
            "certification_numbers": list(self.certification_numbers),
        }


@dataclass
class PhotoCoverageSummary:
    total_collection_items: int
    items_with_photos: int
    items_without_photos: int
    photo_coverage_percentage: float
    certified_items: int
    certified_items_with_photos: int
    certified_photo_coverage_percentage: float
    total_photos: int

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


class PhotoVault:
    """Manage photo metadata records and deterministic lookup."""

    def __init__(
        self,
        records: Optional[Iterable[PhotoRecord]] = None,
        collection_items: Optional[Iterable[Any]] = None,
        root_path: str = "coin_photos",
    ):
        self.records = list(records or [])
        self.collection_items = list(collection_items or [])
        self.root_path = root_path

    def add_photo(self, record: PhotoRecord) -> PhotoRecord:
        self.records.append(record)
        return record

    def link_collection_photo(
        self,
        file_path: str,
        item: Any,
        notes: str = "",
        iccs_number: str = "",
        pcgs_number: str = "",
        ngc_number: str = "",
    ) -> PhotoRecord:
        return self.add_photo(PhotoRecord(
            file_path=file_path,
            photo_type="Collection Photo",
            linked_collection_item_id=str(getattr(item, "id", "")),
            linked_coin_name=self._coin_name(item),
            notes=notes,
            iccs_number=iccs_number,
            pcgs_number=pcgs_number,
            ngc_number=ngc_number,
        ))

    def link_candidate_photo(
        self,
        file_path: str,
        candidate_id: str,
        coin_name: str,
        notes: str = "",
        photo_type: str = "Candidate Photo",
    ) -> PhotoRecord:
        return self.add_photo(PhotoRecord(
            file_path=file_path,
            photo_type=photo_type,
            linked_candidate_id=candidate_id,
            linked_coin_name=coin_name,
            notes=notes,
        ))

    def link_reference_photo(self, file_path: str, coin_name: str, notes: str = "") -> PhotoRecord:
        return self.add_photo(PhotoRecord(
            file_path=file_path,
            photo_type="Reference Photo",
            linked_coin_name=coin_name,
            notes=notes,
        ))

    def search(self, query: str) -> List[PhotoRecord]:
        needle = self._normalize(query)
        if not needle:
            return list(self.records)
        return [
            record for record in self.records
            if needle in self._record_search_text(record)
        ]

    def find_by_certification_number(self, certification_number: str) -> List[PhotoRecord]:
        needle = PhotoRecord._clean_cert(certification_number)
        if not needle:
            return []
        return [
            record for record in self.records
            if needle in record.certification_numbers()
        ]

    def collection_photo_statuses(self) -> List[CollectionPhotoStatus]:
        records_by_item: Dict[str, List[PhotoRecord]] = {}
        for record in self.records:
            if record.linked_collection_item_id:
                records_by_item.setdefault(record.linked_collection_item_id, []).append(record)

        statuses = []
        for item in self.collection_items:
            item_id = str(getattr(item, "id", ""))
            linked = records_by_item.get(item_id, [])
            certs = sorted({
                cert
                for record in linked
                for cert in record.certification_numbers()
            })
            statuses.append(CollectionPhotoStatus(
                item_id=item_id,
                coin_name=self._coin_name(item),
                has_photos=bool(linked),
                photo_count=len(linked),
                certification_numbers=certs,
            ))
        return statuses

    def coverage_summary(self) -> PhotoCoverageSummary:
        statuses = self.collection_photo_statuses()
        total_items = len(statuses)
        with_photos = sum(1 for status in statuses if status.has_photos)
        certified_items = [item for item in self.collection_items if self._item_certified(item)]
        certified_ids = {str(getattr(item, "id", "")) for item in certified_items}
        certified_with_photos = sum(
            1 for status in statuses
            if status.item_id in certified_ids and status.has_photos
        )
        return PhotoCoverageSummary(
            total_collection_items=total_items,
            items_with_photos=with_photos,
            items_without_photos=max(0, total_items - with_photos),
            photo_coverage_percentage=self._percentage(with_photos, total_items),
            certified_items=len(certified_items),
            certified_items_with_photos=certified_with_photos,
            certified_photo_coverage_percentage=self._percentage(certified_with_photos, len(certified_items)),
            total_photos=len(self.records),
        )

    def format_markdown(self) -> str:
        summary = self.coverage_summary()
        lines = [
            "# Photo Vault",
            "",
            "## Coverage",
            "",
            f"- Total photos: {summary.total_photos}",
            f"- Collection photo coverage: {summary.photo_coverage_percentage:.1f}%",
            f"- Items with photos: {summary.items_with_photos}",
            f"- Items without photos: {summary.items_without_photos}",
            f"- Certified coins with photos: {summary.certified_photo_coverage_percentage:.1f}%",
            "",
            "## Photo Records",
            "",
        ]
        if not self.records:
            lines.append("- No photo records available.")
        for record in self.records:
            certs = ", ".join(record.certification_numbers()) or "none"
            lines.append(
                f"- {record.photo_type}: {record.linked_coin_name or os.path.basename(record.file_path)} "
                f"({record.file_path}); certs: {certs}; notes: {record.notes or 'none'}"
            )
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_markdown())
            return True
        except Exception as exc:
            print(f"Error exporting photo vault markdown: {exc}")
            return False

    def export_csv(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "photo_type",
                    "file_path",
                    "linked_collection_item_id",
                    "linked_candidate_id",
                    "linked_coin_name",
                    "created_date",
                    "notes",
                    "iccs_number",
                    "pcgs_number",
                    "ngc_number",
                ])
                writer.writeheader()
                for record in self.records:
                    writer.writerow(record.to_dict())
            return True
        except Exception as exc:
            print(f"Error exporting photo vault CSV: {exc}")
            return False

    def expected_folder_for_type(self, photo_type: str) -> str:
        normalized = PhotoRecord._normalize_photo_type(photo_type)
        folder = {
            "Collection Photo": "collection",
            "Candidate Photo": os.path.join("candidates", "active"),
            "Reference Photo": "references",
            "Auction Photo": "auction_wins",
            "Sold Photo": "sold",
        }[normalized]
        return os.path.join(self.root_path, folder)

    def _record_search_text(self, record: PhotoRecord) -> str:
        return self._normalize(" ".join([
            record.file_path,
            os.path.basename(record.file_path),
            record.photo_type,
            record.linked_collection_item_id,
            record.linked_candidate_id,
            record.linked_coin_name,
            record.notes,
            " ".join(record.certification_numbers()),
        ]))

    @staticmethod
    def _coin_name(item: Any) -> str:
        parts = [
            getattr(item, "country", "") or "",
            getattr(item, "year", "") or "",
            getattr(item, "denomination", "") or "",
            getattr(item, "grade", "") or "",
        ]
        return " ".join(part for part in parts if part).strip()

    @staticmethod
    def _item_certified(item: Any) -> bool:
        text = " ".join([
            str(getattr(item, "certifier", "") or ""),
            str(getattr(item, "certification_number", "") or ""),
            str(getattr(item, "notes", "") or ""),
            str(getattr(item, "comments", "") or ""),
            str(getattr(item, "title", "") or ""),
        ]).lower()
        return any(term in text for term in ["pcgs", "ngc", "iccs", "anacs", "cert", "slab"])

    @staticmethod
    def _percentage(numerator: int, denominator: int) -> float:
        return round((numerator / denominator) * 100, 1) if denominator else 0.0

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(str(value or "").lower().split())
