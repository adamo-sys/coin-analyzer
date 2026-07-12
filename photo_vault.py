"""Structured photo metadata vault for collection and candidate images."""

import csv
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Set


PHOTO_TYPES = (
    "Collection Photo",
    "Candidate Photo",
    "Reference Photo",
    "Auction Photo",
    "Sold Photo",
)

SUPPORTED_PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff")


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


@dataclass
class PhotoVaultIssue:
    """Report-only photo metadata issue."""

    issue_type: str
    severity: str
    reference: str = ""
    photo_path: str = ""
    photo_type: str = ""
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_type": self.issue_type,
            "severity": self.severity,
            "reference": self.reference,
            "photo_path": self.photo_path,
            "photo_type": self.photo_type,
            "recommendation": self.recommendation,
        }


@dataclass
class PhotoCoverageReport:
    """Photo Vault trust and coverage report."""

    total_photo_records: int = 0
    valid_photo_references: int = 0
    missing_photo_references: int = 0
    duplicate_photo_references: int = 0
    collection_photo_coverage_percentage: float = 0.0
    certified_item_photo_coverage_percentage: float = 0.0
    candidate_photo_coverage_percentage: float = 0.0
    findings: List[PhotoVaultIssue] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_photo_records": self.total_photo_records,
            "valid_photo_references": self.valid_photo_references,
            "missing_photo_references": self.missing_photo_references,
            "duplicate_photo_references": self.duplicate_photo_references,
            "collection_photo_coverage_percentage": self.collection_photo_coverage_percentage,
            "certified_item_photo_coverage_percentage": self.certified_item_photo_coverage_percentage,
            "candidate_photo_coverage_percentage": self.candidate_photo_coverage_percentage,
            "findings": [issue.to_dict() for issue in self.findings],
            "recommended_actions": list(self.recommended_actions),
        }

    def format_markdown(self) -> str:
        lines = [
            "# Photo Vault Audit",
            "",
            "## Coverage Metrics",
            "",
            f"- Total photo records: {self.total_photo_records}",
            f"- Valid photo references: {self.valid_photo_references}",
            f"- Missing photo references: {self.missing_photo_references}",
            f"- Duplicate photo references: {self.duplicate_photo_references}",
            f"- Collection photo coverage: {self.collection_photo_coverage_percentage:.1f}%",
            f"- Certified-item photo coverage: {self.certified_item_photo_coverage_percentage:.1f}%",
            f"- Candidate photo coverage: {self.candidate_photo_coverage_percentage:.1f}%",
            "",
            "## Findings",
            "",
        ]
        if self.findings:
            for issue in self.findings:
                lines.append(
                    f"- [{issue.severity}] {issue.issue_type}: {issue.reference or issue.photo_path or 'photo metadata'}"
                )
                if issue.photo_path:
                    lines.append(f"  - Path: {issue.photo_path}")
                if issue.recommendation:
                    lines.append(f"  - Recommendation: {issue.recommendation}")
        else:
            lines.append("- No photo metadata issues found.")
        lines.extend(["", "## Recommended Actions", ""])
        lines.extend(f"- {action}" for action in self.recommended_actions) if self.recommended_actions else lines.append("- Continue regular photo metadata reviews.")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_markdown())
            return True
        except Exception as exc:
            print(f"Error exporting photo audit markdown: {exc}")
            return False

    def export_csv(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "issue_type",
                    "severity",
                    "reference",
                    "photo_path",
                    "photo_type",
                    "recommendation",
                ])
                writer.writeheader()
                for issue in self.findings:
                    writer.writerow(issue.to_dict())
            return True
        except Exception as exc:
            print(f"Error exporting photo audit CSV: {exc}")
            return False


class PhotoVaultIntegrityAudit:
    """Report-only audit for photo metadata reliability."""

    def __init__(
        self,
        records: Optional[Iterable[PhotoRecord]] = None,
        collection_items: Optional[Iterable[Any]] = None,
        photo_candidates: Optional[Iterable[Any]] = None,
        root_path: str = "coin_photos",
    ):
        self.records = list(records or [])
        self.collection_items = list(collection_items or [])
        self.photo_candidates = list(photo_candidates or [])
        self.root_path = root_path

    def run(self) -> PhotoCoverageReport:
        vault = PhotoVault(self.records, self.collection_items, self.root_path)
        summary = vault.coverage_summary()
        audit_records = vault.collection_photo_records(include_supplemental=True)
        candidate_reference_records = [
            record for record in self.records
            if not record.linked_collection_item_id
        ]
        all_records = audit_records + candidate_reference_records
        findings: List[PhotoVaultIssue] = []
        findings.extend(self._record_issues(all_records))
        findings.extend(self._collection_coverage_issues())
        findings.extend(self._candidate_coverage_issues())
        missing = sum(1 for issue in findings if issue.issue_type == "Missing Photo Reference")
        duplicate = sum(1 for issue in findings if issue.issue_type == "Duplicate Photo Reference")
        valid = sum(1 for record in all_records if record.file_path and os.path.exists(record.file_path))
        candidate_total = len(self.photo_candidates)
        candidate_with_photo = sum(1 for candidate in self.photo_candidates if self._candidate_photo_refs(candidate))
        report = PhotoCoverageReport(
            total_photo_records=len(all_records),
            valid_photo_references=valid,
            missing_photo_references=missing,
            duplicate_photo_references=duplicate,
            collection_photo_coverage_percentage=summary.photo_coverage_percentage,
            certified_item_photo_coverage_percentage=summary.certified_photo_coverage_percentage,
            candidate_photo_coverage_percentage=PhotoVault._percentage(candidate_with_photo, candidate_total),
            findings=findings,
            recommended_actions=self._recommended_actions(findings),
        )
        return report

    def _record_issues(self, records: Optional[Iterable[PhotoRecord]] = None) -> List[PhotoVaultIssue]:
        issues: List[PhotoVaultIssue] = []
        seen_paths: Dict[str, PhotoRecord] = {}
        for record in list(records if records is not None else self.records):
            path = record.file_path
            reference = record.linked_coin_name or record.linked_candidate_id or record.linked_collection_item_id
            if not path:
                issues.append(PhotoVaultIssue(
                    "Invalid Photo Path",
                    "WARNING",
                    reference=reference,
                    photo_type=record.photo_type,
                    recommendation="Add a local photo path or remove the empty metadata record.",
                ))
                continue
            normalized_path = os.path.normcase(os.path.normpath(path))
            if normalized_path in seen_paths:
                issues.append(PhotoVaultIssue(
                    "Duplicate Photo Reference",
                    "WARNING",
                    reference=reference,
                    photo_path=path,
                    photo_type=record.photo_type,
                    recommendation="Confirm whether duplicate metadata should be merged or kept intentionally.",
                ))
            else:
                seen_paths[normalized_path] = record
            if not os.path.exists(path):
                issues.append(PhotoVaultIssue(
                    "Missing Photo Reference",
                    "WARNING",
                    reference=reference,
                    photo_path=path,
                    photo_type=record.photo_type,
                    recommendation="Move the photo back or update the saved photo path.",
                ))
            if self._invalid_extension(path):
                issues.append(PhotoVaultIssue(
                    "Invalid File Extension",
                    "WARNING",
                    reference=reference,
                    photo_path=path,
                    photo_type=record.photo_type,
                    recommendation=f"Use supported image extensions: {', '.join(SUPPORTED_PHOTO_EXTENSIONS)}.",
                ))
            if self._unsupported_path(path):
                issues.append(PhotoVaultIssue(
                    "Unsupported File Path",
                    "WARNING",
                    reference=reference,
                    photo_path=path,
                    photo_type=record.photo_type,
                    recommendation="Use a local filesystem path stored in the project photo folders when practical.",
                ))
            if not record.linked_collection_item_id and not record.linked_candidate_id and not record.linked_coin_name:
                issues.append(PhotoVaultIssue(
                    "Unlinked Photo Record",
                    "WARNING",
                    photo_path=path,
                    photo_type=record.photo_type,
                    recommendation="Link the photo to a collection item, candidate, or reference label.",
                ))
        return issues

    def _collection_coverage_issues(self) -> List[PhotoVaultIssue]:
        issues = []
        records_by_item: Set[str] = {
            str(record.linked_collection_item_id)
            for record in PhotoVault(self.records, self.collection_items, self.root_path).collection_photo_records(include_supplemental=True)
            if record.linked_collection_item_id
        }
        for item in self.collection_items:
            item_id = str(getattr(item, "id", "") or "")
            coin_name = PhotoVault._coin_name(item)
            has_photo = item_id in records_by_item
            if not has_photo:
                issue_type = "Certified Item Without Photo" if PhotoVault._item_certified(item) else "Collection Item Without Photo"
                recommendation = "Add slab/certification photos for certified items." if PhotoVault._item_certified(item) else "Add collection photos when available."
                issues.append(PhotoVaultIssue(
                    issue_type,
                    "INFO",
                    reference=coin_name or item_id,
                    recommendation=recommendation,
                ))
        return issues

    def _candidate_coverage_issues(self) -> List[PhotoVaultIssue]:
        issues = []
        candidate_ids_with_records = {
            str(record.linked_candidate_id)
            for record in self.records
            if record.linked_candidate_id
        }
        for candidate in self.photo_candidates:
            candidate_id = str(getattr(candidate, "candidate_id", "") or getattr(candidate, "id", "") or "")
            title = str(getattr(candidate, "title", "") or getattr(candidate, "item_title", "") or candidate_id)
            refs = self._candidate_photo_refs(candidate)
            if not refs and candidate_id not in candidate_ids_with_records:
                issues.append(PhotoVaultIssue(
                    "Candidate Without Photo",
                    "WARNING",
                    reference=title,
                    recommendation="Attach at least one candidate photo reference before acquisition review.",
                ))
            front = str(getattr(candidate, "front_photo", "") or "")
            reverse = str(getattr(candidate, "reverse_photo", "") or "")
            if candidate_id and not front and refs:
                issues.append(PhotoVaultIssue(
                    "Missing Front Photo",
                    "INFO",
                    reference=title,
                    recommendation="Add a front/obverse photo when available.",
                ))
            if candidate_id and not reverse and refs:
                issues.append(PhotoVaultIssue(
                    "Missing Reverse Photo",
                    "INFO",
                    reference=title,
                    recommendation="Add a reverse photo when available.",
                ))
        return issues

    @staticmethod
    def _candidate_photo_refs(candidate: Any) -> List[str]:
        if hasattr(candidate, "photo_references"):
            refs = getattr(candidate, "photo_references")
            return list(refs() if callable(refs) else refs)
        refs = []
        for attr in ["front_photo", "reverse_photo", "photo_reference_id"]:
            value = str(getattr(candidate, attr, "") or "").strip()
            if value:
                refs.append(value)
        refs.extend(str(value).strip() for value in getattr(candidate, "reference_photos", []) or [] if str(value).strip())
        refs.extend(str(value).strip() for value in getattr(candidate, "photo_reference_ids", []) or [] if str(value).strip())
        return refs

    @staticmethod
    def _invalid_extension(path: str) -> bool:
        _, ext = os.path.splitext(str(path or ""))
        return bool(path) and ext.lower() not in SUPPORTED_PHOTO_EXTENSIONS

    @staticmethod
    def _unsupported_path(path: str) -> bool:
        text = str(path or "").strip().lower()
        return text.startswith(("http://", "https://", "ftp://"))

    @staticmethod
    def _recommended_actions(findings: List[PhotoVaultIssue]) -> List[str]:
        actions = []
        for issue in findings:
            if issue.recommendation and issue.recommendation not in actions:
                actions.append(issue.recommendation)
        return actions


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
        records = self.all_indexed_records()
        needle = self._normalize(query)
        if not needle:
            return records
        return [
            record for record in records
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
        for record in self.collection_photo_records(include_supplemental=True):
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
            total_photos=len(self.all_indexed_records()),
        )

    def all_indexed_records(self) -> List[PhotoRecord]:
        return self.collection_photo_records(include_supplemental=True) + [
            record for record in self.records if not record.linked_collection_item_id
        ]

    def collection_photo_records(self, include_supplemental: bool = True) -> List[PhotoRecord]:
        records = self._item_owned_photo_records()
        if include_supplemental:
            records.extend(record for record in self.records if record.linked_collection_item_id)
        return records

    def _item_owned_photo_records(self) -> List[PhotoRecord]:
        records: List[PhotoRecord] = []
        for item in self.collection_items:
            for photo in self._item_photos(item):
                records.append(PhotoRecord(
                    file_path=photo["path"],
                    photo_type="Collection Photo",
                    linked_collection_item_id=str(getattr(item, "id", "")),
                    linked_coin_name=self._coin_name(item),
                    notes=photo.get("notes", ""),
                ))
        return records

    @staticmethod
    def _item_photos(item: Any) -> List[Dict[str, str]]:
        if hasattr(item, "normalized_photos"):
            return [
                {"path": getattr(photo, "path", ""), "notes": getattr(photo, "notes", "")}
                for photo in item.normalized_photos()
                if getattr(photo, "path", "")
            ]
        image_path = str(getattr(item, "image_path", "") or "").strip()
        return [{"path": image_path, "notes": ""}] if image_path else []

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
        display_records = self.all_indexed_records()
        if not display_records:
            lines.append("- No photo records available.")
        for record in display_records:
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
                for record in self.all_indexed_records():
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
