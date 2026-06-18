"""Read-only collection data integrity audit.

This module validates local collection data and related runtime records. It
does not modify collection records, workbooks, photos, market data, app state,
or backup packages.
"""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from backup_manager import BackupManager, DataSafetyValidator
from market_awareness import MarketAwarenessEngine
from persistence_manager import PersistenceManager
from photo_vault import PHOTO_TYPES, PhotoRecord
from smart_shopping_assistant import ShoppingCandidate


VALID_COUNTRY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'\-&()]*$")
VALID_YEAR_PATTERN = re.compile(r"^\d{3,4}$")
VALID_CERT_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9\- ]{2,}$")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return " ".join(_text(value).lower().replace(".", "").split())


def _coin_label(item: Any) -> str:
    parts = [
        _text(getattr(item, "country", "")),
        _text(getattr(item, "denomination", "")),
        _text(getattr(item, "year", "")),
        _text(getattr(item, "grade", "")),
    ]
    label = " ".join(part for part in parts if part)
    return label or f"item {getattr(item, 'id', '') or 'unknown'}"


def _record_key(*values: Any) -> str:
    return "|".join(_norm(value) for value in values)


@dataclass
class IntegrityFinding:
    severity: str
    category: str
    message: str
    recommendation: str = ""
    record_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "category": self.category,
            "record_id": self.record_id,
            "message": self.message,
            "recommendation": self.recommendation,
        }


@dataclass
class PhotoIntegritySummary:
    total_photos: int = 0
    missing_files: int = 0
    orphan_photo_references: int = 0
    duplicate_photo_references: int = 0
    invalid_photo_metadata: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class MarketIntegritySummary:
    total_records: int = 0
    orphan_market_records: int = 0
    invalid_references: int = 0
    duplicate_observations: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class CertificationIntegritySummary:
    duplicate_certification_ids: int = 0
    missing_certification_references: int = 0
    malformed_certification_references: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class CollectionIntegrityScore:
    score: int
    category_scores: Dict[str, int] = field(default_factory=dict)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "category_scores": dict(self.category_scores),
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "recommended_actions": list(self.recommended_actions),
        }


@dataclass
class CollectionIntegrityReport:
    integrity_score: CollectionIntegrityScore
    findings: List[IntegrityFinding] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    photo_summary: PhotoIntegritySummary = field(default_factory=PhotoIntegritySummary)
    market_summary: MarketIntegritySummary = field(default_factory=MarketIntegritySummary)
    certification_summary: CertificationIntegritySummary = field(default_factory=CertificationIntegritySummary)
    backup_status: str = "UNKNOWN"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "integrity_score": self.integrity_score.to_dict(),
            "findings": [finding.to_dict() for finding in self.findings],
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
            "photo_summary": self.photo_summary.to_dict(),
            "market_summary": self.market_summary.to_dict(),
            "certification_summary": self.certification_summary.to_dict(),
            "backup_status": self.backup_status,
        }

    def format_markdown(self) -> str:
        score = self.integrity_score
        lines = [
            "# Collection Integrity Audit",
            "",
            f"- Integrity Score: {score.score}/100",
            f"- Backup Readiness: {self.backup_status}",
            "",
            "## Category Scores",
            "",
        ]
        for category, value in score.category_scores.items():
            lines.append(f"- {category}: {value}/100")
        lines.extend(["", "## Findings", ""])
        if self.findings:
            for finding in self.findings:
                suffix = f" ({finding.record_id})" if finding.record_id else ""
                lines.append(f"- [{finding.severity}] {finding.category}{suffix}: {finding.message}")
                if finding.recommendation:
                    lines.append(f"  - Action: {finding.recommendation}")
        else:
            lines.append("- No integrity findings.")
        lines.extend(["", "## Photo Integrity", ""])
        lines.extend([
            f"- Total photos: {self.photo_summary.total_photos}",
            f"- Missing files: {self.photo_summary.missing_files}",
            f"- Orphan photo references: {self.photo_summary.orphan_photo_references}",
            f"- Duplicate photo references: {self.photo_summary.duplicate_photo_references}",
            f"- Invalid photo metadata: {self.photo_summary.invalid_photo_metadata}",
            "",
            "## Market Integrity",
            "",
            f"- Total market records: {self.market_summary.total_records}",
            f"- Orphan market records: {self.market_summary.orphan_market_records}",
            f"- Invalid references: {self.market_summary.invalid_references}",
            f"- Duplicate observations: {self.market_summary.duplicate_observations}",
            "",
            "## Certification Integrity",
            "",
            f"- Duplicate certification IDs: {self.certification_summary.duplicate_certification_ids}",
            f"- Missing certification references: {self.certification_summary.missing_certification_references}",
            f"- Malformed certification references: {self.certification_summary.malformed_certification_references}",
            "",
            "## Strengths",
            "",
        ])
        lines.extend(f"- {item}" for item in score.strengths) if score.strengths else lines.append("- None identified yet.")
        lines.extend(["", "## Weaknesses", ""])
        lines.extend(f"- {item}" for item in score.weaknesses) if score.weaknesses else lines.append("- None identified.")
        lines.extend(["", "## Recommendations", ""])
        lines.extend(f"- {item}" for item in self.recommendations) if self.recommendations else lines.append("- Continue routine integrity and backup checks.")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["section", "severity", "category", "record_id", "message", "recommendation"])
            writer.writerow(["score", "", "Overall", "", f"{self.integrity_score.score}/100", ""])
            for category, value in self.integrity_score.category_scores.items():
                writer.writerow(["score", "", category, "", f"{value}/100", ""])
            for finding in self.findings:
                writer.writerow([
                    "finding",
                    finding.severity,
                    finding.category,
                    finding.record_id,
                    finding.message,
                    finding.recommendation,
                ])
            for recommendation in self.recommendations:
                writer.writerow(["recommendation", "", "", "", recommendation, ""])
        return True


class CollectionIntegrityAudit:
    """Generate deterministic read-only integrity reports for collection data."""

    def __init__(
        self,
        collection_items: Iterable[Any],
        photo_records: Optional[Iterable[PhotoRecord]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
        shopping_candidates: Optional[Iterable[ShoppingCandidate]] = None,
        persistence_manager: Optional[PersistenceManager] = None,
        backup_manager: Optional[BackupManager] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.photo_records = list(photo_records or [])
        self.market = market_awareness_engine or MarketAwarenessEngine()
        self.shopping_candidates = list(shopping_candidates or [])
        self.persistence_manager = persistence_manager or PersistenceManager()
        self.backup_manager = backup_manager or BackupManager(persistence_manager=self.persistence_manager)

    def run(self) -> CollectionIntegrityReport:
        findings: List[IntegrityFinding] = []
        photo_summary = self._audit_photos(findings)
        market_summary = self._audit_market(findings)
        certification_summary = self._audit_certifications(findings)
        findings.extend(self._audit_collection_items())
        findings.extend(self._audit_shopping_candidates())
        backup_status = self._audit_backup_readiness(findings)
        score = self._score(findings, photo_summary, market_summary, certification_summary, backup_status)
        recommendations = self._recommendations(findings, score)
        warnings = [finding.message for finding in findings if finding.severity in {"WARNING", "FAIL"}]
        return CollectionIntegrityReport(
            integrity_score=score,
            findings=findings,
            warnings=warnings,
            recommendations=recommendations,
            photo_summary=photo_summary,
            market_summary=market_summary,
            certification_summary=certification_summary,
            backup_status=backup_status,
        )

    def _audit_collection_items(self) -> List[IntegrityFinding]:
        findings: List[IntegrityFinding] = []
        seen: Dict[str, List[Any]] = {}
        for item in self.collection_items:
            item_id = _text(getattr(item, "id", ""))
            country = _text(getattr(item, "country", ""))
            denomination = _text(getattr(item, "denomination", ""))
            year = _text(getattr(item, "year", ""))
            grade = _text(getattr(item, "grade", ""))
            if not country or _norm(country) in {"unknown", "n/a", "none"} or not VALID_COUNTRY_PATTERN.match(country):
                findings.append(self._finding("WARNING", "Ownership Data", f"Invalid or missing country for {_coin_label(item)}.", "Review and normalize country.", item_id))
            if not denomination or _norm(denomination) in {"unknown", "n/a", "none"}:
                findings.append(self._finding("WARNING", "Ownership Data", f"Invalid or missing denomination for {_coin_label(item)}.", "Review and normalize denomination.", item_id))
            if not year:
                findings.append(self._finding("WARNING", "Ownership Data", f"Missing date/year for {_coin_label(item)}.", "Add the coin date or mark it explicitly unknown.", item_id))
            elif not self._valid_year(year):
                findings.append(self._finding("WARNING", "Ownership Data", f"Invalid year value '{year}' for {_coin_label(item)}.", "Use a numeric year when known.", item_id))
            if not grade:
                findings.append(self._finding("WARNING", "Ownership Data", f"Missing grade for {_coin_label(item)}.", "Add a raw or certified grade.", item_id))
            key = _record_key(country, denomination, year)
            if key.strip("|"):
                seen.setdefault(key, []).append(item)
        for rows in seen.values():
            if len(rows) > 1:
                labels = ", ".join(_text(getattr(row, "id", "")) or _coin_label(row) for row in rows)
                findings.append(self._finding(
                    "WARNING",
                    "Duplicate Ownership",
                    f"Probable duplicate ownership records: {labels}.",
                    "Review duplicate holdings before using dashboard and shopping recommendations.",
                    labels,
                ))
        return findings

    def _audit_photos(self, findings: List[IntegrityFinding]) -> PhotoIntegritySummary:
        item_ids = {_text(getattr(item, "id", "")) for item in self.collection_items if _text(getattr(item, "id", ""))}
        paths: Dict[str, int] = {}
        missing_files = orphan_refs = invalid_metadata = 0
        for record in self.photo_records:
            paths[_norm(record.file_path)] = paths.get(_norm(record.file_path), 0) + 1
            if not record.file_path or not os.path.exists(record.file_path):
                missing_files += 1
                findings.append(self._finding("WARNING", "Photos", f"Photo file is missing: {record.file_path or 'blank path'}.", "Move the photo back or update the Photo Vault record."))
            if record.photo_type not in PHOTO_TYPES:
                invalid_metadata += 1
                findings.append(self._finding("WARNING", "Photos", f"Invalid photo type for {record.file_path}.", "Use a supported Photo Vault photo type."))
            if record.linked_collection_item_id and record.linked_collection_item_id not in item_ids:
                orphan_refs += 1
                findings.append(self._finding("WARNING", "Photos", f"Photo references missing collection item {record.linked_collection_item_id}.", "Relink or remove the orphan photo metadata.", record.linked_collection_item_id))
        duplicate_paths = sum(1 for count in paths.values() if count > 1 and paths)
        if duplicate_paths:
            findings.append(self._finding("WARNING", "Photos", f"{duplicate_paths} duplicate photo file reference(s) found.", "Review duplicate Photo Vault entries."))
        return PhotoIntegritySummary(
            total_photos=len(self.photo_records),
            missing_files=missing_files,
            orphan_photo_references=orphan_refs,
            duplicate_photo_references=duplicate_paths,
            invalid_photo_metadata=invalid_metadata,
        )

    def _audit_market(self, findings: List[IntegrityFinding]) -> MarketIntegritySummary:
        records = self._market_records()
        collection_keys = {_record_key(getattr(item, "country", ""), getattr(item, "denomination", ""), getattr(item, "year", "")) for item in self.collection_items}
        photo_refs = self._photo_reference_ids()
        seen_observations: Dict[str, int] = {}
        orphan_records = invalid_refs = duplicate_observations = 0
        for kind, record in records:
            key = _record_key(getattr(record, "country", ""), getattr(record, "denomination", ""), getattr(record, "year", ""))
            if key.strip("|") and key not in collection_keys and kind in {"purchase", "sale"}:
                orphan_records += 1
                findings.append(self._finding("WARNING", "Market Records", f"{kind.title()} record is not linked to an owned collection item: {self._market_label(record)}.", "Review whether this market record should be linked or retained."))
            for photo_id in getattr(record, "linked_photo_ids", []) or []:
                if photo_id and photo_id not in photo_refs:
                    invalid_refs += 1
                    findings.append(self._finding("WARNING", "Market Records", f"Market record references missing photo ID/path: {photo_id}.", "Relink the market record photo reference."))
            if kind == "observation":
                obs_key = _record_key(getattr(record, "item_name", ""), getattr(record, "observed_price", ""), getattr(record, "source", ""), getattr(record, "date_observed", ""))
                seen_observations[obs_key] = seen_observations.get(obs_key, 0) + 1
        duplicate_observations = sum(1 for count in seen_observations.values() if count > 1)
        if duplicate_observations:
            findings.append(self._finding("WARNING", "Market Records", f"{duplicate_observations} duplicate market observation(s) found.", "Review duplicate local market observations."))
        return MarketIntegritySummary(
            total_records=len(records),
            orphan_market_records=orphan_records,
            invalid_references=invalid_refs,
            duplicate_observations=duplicate_observations,
        )

    def _audit_certifications(self, findings: List[IntegrityFinding]) -> CertificationIntegritySummary:
        cert_sources: Dict[str, List[str]] = {}
        missing = malformed = 0
        for item in self.collection_items:
            item_id = _text(getattr(item, "id", ""))
            certs = self._item_cert_numbers(item)
            text = " ".join(_text(getattr(item, field, "")) for field in ["notes", "comments", "title", "reference"])
            if not certs and any(word in text.lower() for word in ["pcgs", "ngc", "iccs", "anacs", "cert", "slab"]):
                missing += 1
                findings.append(self._finding("WARNING", "Certifications", f"Certified/slabbed wording found without certification ID on {_coin_label(item)}.", "Add the certification number when available.", item_id))
            for cert in certs:
                if not VALID_CERT_PATTERN.match(cert):
                    malformed += 1
                    findings.append(self._finding("WARNING", "Certifications", f"Malformed certification ID '{cert}' on {_coin_label(item)}.", "Review certification number formatting.", item_id))
                cert_sources.setdefault(cert, []).append(item_id or _coin_label(item))
        for record in self.photo_records:
            for cert in record.certification_numbers():
                if not VALID_CERT_PATTERN.match(cert):
                    malformed += 1
                    findings.append(self._finding("WARNING", "Certifications", f"Malformed photo certification ID '{cert}'.", "Review Photo Vault certification metadata."))
                cert_sources.setdefault(cert, []).append(record.file_path or "photo")
        duplicates = sum(1 for sources in cert_sources.values() if len(sources) > 1)
        for cert, sources in cert_sources.items():
            if len(sources) > 1:
                findings.append(self._finding("WARNING", "Certifications", f"Duplicate certification ID '{cert}' appears in {', '.join(sources)}.", "Confirm whether records refer to the same slab."))
        return CertificationIntegritySummary(
            duplicate_certification_ids=duplicates,
            missing_certification_references=missing,
            malformed_certification_references=malformed,
        )

    def _audit_shopping_candidates(self) -> List[IntegrityFinding]:
        findings: List[IntegrityFinding] = []
        photo_refs = self._photo_reference_ids()
        for candidate in self.shopping_candidates:
            for photo_id in getattr(candidate, "photo_reference_ids", []) or []:
                if photo_id and photo_id not in photo_refs:
                    findings.append(self._finding("WARNING", "Shopping Candidates", f"Shopping candidate '{candidate.item_name}' references missing photo ID/path: {photo_id}.", "Relink or remove the photo reference."))
            if not _text(getattr(candidate, "item_name", "")):
                findings.append(self._finding("WARNING", "Shopping Candidates", "Shopping candidate is missing item name.", "Add item name before using shopping recommendations."))
        return findings

    def _audit_backup_readiness(self, findings: List[IntegrityFinding]) -> str:
        report = DataSafetyValidator(
            self.persistence_manager,
            self.backup_manager.backup_dir,
            self.backup_manager.collection_json_path,
        ).validate()
        for issue in report.issues:
            findings.append(self._finding(issue.severity, "Backups", issue.message, issue.recommended_action))
        return report.status

    def _score(
        self,
        findings: Sequence[IntegrityFinding],
        photo_summary: PhotoIntegritySummary,
        market_summary: MarketIntegritySummary,
        certification_summary: CertificationIntegritySummary,
        backup_status: str,
    ) -> CollectionIntegrityScore:
        category_scores = {
            "ownership data": self._category_score(findings, "Ownership Data", "Duplicate Ownership"),
            "photos": max(0, 100 - (photo_summary.missing_files * 8) - (photo_summary.orphan_photo_references * 10) - (photo_summary.duplicate_photo_references * 5) - (photo_summary.invalid_photo_metadata * 8)),
            "market records": max(0, 100 - (market_summary.orphan_market_records * 10) - (market_summary.invalid_references * 8) - (market_summary.duplicate_observations * 5)),
            "certifications": max(0, 100 - (certification_summary.duplicate_certification_ids * 12) - (certification_summary.missing_certification_references * 8) - (certification_summary.malformed_certification_references * 8)),
            "persistence": self._category_score(findings, "Backups"),
            "backups": 100 if backup_status == "PASS" else 75 if backup_status == "WARNING" else 45,
        }
        overall = round(sum(category_scores.values()) / len(category_scores)) if category_scores else 100
        strengths = [f"{category.title()} looks healthy" for category, value in category_scores.items() if value >= 90]
        weaknesses = [f"{category.title()} needs attention" for category, value in category_scores.items() if value < 80]
        return CollectionIntegrityScore(
            score=max(0, min(100, overall)),
            category_scores=category_scores,
            strengths=strengths[:5],
            weaknesses=weaknesses[:5],
            recommended_actions=[],
        )

    def _category_score(self, findings: Sequence[IntegrityFinding], *categories: str) -> int:
        score = 100
        wanted = set(categories)
        for finding in findings:
            if finding.category in wanted:
                score -= 12 if finding.severity == "FAIL" else 6
        return max(0, min(100, score))

    def _recommendations(self, findings: Sequence[IntegrityFinding], score: CollectionIntegrityScore) -> List[str]:
        actions: List[str] = []
        for finding in findings:
            if finding.recommendation and finding.recommendation not in actions:
                actions.append(finding.recommendation)
        for action in score.recommended_actions:
            if action not in actions:
                actions.append(action)
        return actions[:10] or ["Continue routine integrity audits after imports, purchases, and backup changes."]

    def _market_records(self) -> List[Tuple[str, Any]]:
        rows: List[Tuple[str, Any]] = []
        rows.extend(("observation", record) for record in getattr(self.market, "observations", []))
        rows.extend(("purchase", record) for record in getattr(self.market, "purchases", []))
        rows.extend(("sale", record) for record in getattr(self.market, "sales", []))
        rows.extend(("auction", record) for record in getattr(self.market, "auctions", []))
        return rows

    def _photo_reference_ids(self) -> set:
        refs = set()
        for record in self.photo_records:
            if record.file_path:
                refs.add(record.file_path)
                refs.add(os.path.basename(record.file_path))
            refs.update(record.certification_numbers())
            if record.linked_candidate_id:
                refs.add(record.linked_candidate_id)
            if record.linked_collection_item_id:
                refs.add(record.linked_collection_item_id)
        return refs

    def _item_cert_numbers(self, item: Any) -> List[str]:
        certs = []
        for field in ["certification_number", "cert_number", "slab_number", "iccs_number", "pcgs_number", "ngc_number"]:
            value = _text(getattr(item, field, ""))
            if value:
                certs.append(value.upper())
        return certs

    def _valid_year(self, value: str) -> bool:
        text = _text(value)
        if not VALID_YEAR_PATTERN.match(text):
            return False
        year = int(text)
        return 500 <= year <= 2100

    def _market_label(self, record: Any) -> str:
        return _text(getattr(record, "item", "")) or _text(getattr(record, "item_name", "")) or "market record"

    def _finding(self, severity: str, category: str, message: str, recommendation: str = "", record_id: str = "") -> IntegrityFinding:
        return IntegrityFinding(severity=severity, category=category, message=message, recommendation=recommendation, record_id=record_id)
