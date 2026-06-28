"""
Batch Processing Engine — v8.1 Phase 1

Thin orchestration layer that processes a folder of photos through the
existing Smart Phone Cataloguer pipeline.

Design principles:
- Favor reuse over invention
- No new OCR, matching, or cataloguing logic
- Phase 1: folder scanning, photo discovery, auto-pairing, candidate creation,
  catalogue intake, summary, export
- Phase 2+: OCR, matching, proposed-entry processing
"""

import os
import re
import csv
import glob
from typing import List, Dict, Any, Optional, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum

from smart_phone_cataloguer import (
    SmartPhoneCataloguer,
    CatalogueResult,
    BatchCatalogueResult,
    CollectionMatchResult,
    ProposedCollectionEntry,
)
from photo_capture_workflow import PhotoCaptureWorkflow
from ocr_assisted_identification import OCRIdentificationReport


class BatchStatus(Enum):
    """Status of a batch candidate."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class BatchSource:
    """Source of photos for batch processing."""
    folder_path: str
    file_pattern: str = "*.jpg"
    auto_pair: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "folder_path": self.folder_path,
            "file_pattern": self.file_pattern,
            "auto_pair": self.auto_pair,
        }


@dataclass
class BatchCandidate:
    """A single candidate from the batch pipeline."""
    candidate_id: str
    front_path: Optional[str] = None
    back_path: Optional[str] = None
    subject: str = ""
    ocr_result: Optional[OCRIdentificationReport] = None  # Phase 2+
    collection_match: Optional[CollectionMatchResult] = None  # Phase 3+
    proposed_entry: Optional[ProposedCollectionEntry] = None  # Phase 4+
    status: BatchStatus = BatchStatus.PENDING
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    catalogue_result: Optional[CatalogueResult] = None  # Phase 1: populated

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "front_path": self.front_path,
            "back_path": self.back_path,
            "subject": self.subject,
            "status": self.status.value,
            "warnings": self.warnings,
            "errors": self.errors,
            "has_ocr_result": self.ocr_result is not None,
            "has_collection_match": self.collection_match is not None,
            "has_proposed_entry": self.proposed_entry is not None,
            "catalogue_result": self.catalogue_result.to_dict() if self.catalogue_result else None,
        }


@dataclass
class BatchSummary:
    """Summary statistics for the batch."""
    total_photos: int = 0
    processed: int = 0
    failed: int = 0
    ocr_ready: int = 0
    review_ready: int = 0
    duplicates_detected: int = 0  # Phase 3+
    upgrade_opportunities: int = 0  # Phase 3+
    gap_opportunities: int = 0  # Phase 3+
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_photos": self.total_photos,
            "processed": self.processed,
            "failed": self.failed,
            "ocr_ready": self.ocr_ready,
            "review_ready": self.review_ready,
            "duplicates_detected": self.duplicates_detected,
            "upgrade_opportunities": self.upgrade_opportunities,
            "gap_opportunities": self.gap_opportunities,
            "warnings": self.warnings,
            "errors": self.errors,
        }


@dataclass
class BatchReport:
    """Consolidated report for the entire batch."""
    source: BatchSource
    candidates: List[BatchCandidate] = field(default_factory=list)
    summary: BatchSummary = field(default_factory=BatchSummary)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "candidates": [c.to_dict() for c in self.candidates],
            "summary": self.summary.to_dict(),
            "created_at": self.created_at,
        }

    def export_csv(self, path: str) -> None:
        """Export batch report to CSV."""
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # Header
            writer.writerow([
                "candidate_id", "subject", "status", "front_path", "back_path",
                "warnings", "errors", "has_ocr", "has_match", "has_proposed_entry",
            ])
            # Rows
            for c in self.candidates:
                writer.writerow([
                    c.candidate_id,
                    c.subject,
                    c.status.value,
                    c.front_path or "",
                    c.back_path or "",
                    "; ".join(c.warnings) if c.warnings else "",
                    "; ".join(c.errors) if c.errors else "",
                    "yes" if c.ocr_result else "no",
                    "yes" if c.collection_match else "no",
                    "yes" if c.proposed_entry else "no",
                ])
            # Summary
            writer.writerow([])
            writer.writerow(["Summary"])
            writer.writerow(["total_photos", self.summary.total_photos])
            writer.writerow(["processed", self.summary.processed])
            writer.writerow(["failed", self.summary.failed])
            writer.writerow(["ocr_ready", self.summary.ocr_ready])
            writer.writerow(["review_ready", self.summary.review_ready])

    def export_markdown(self, path: str) -> None:
        """Export batch report to Markdown."""
        lines = [
            "# Batch Processing Report",
            "",
            f"**Source:** {self.source.folder_path}",
            f"**Pattern:** {self.source.file_pattern}",
            f"**Auto-pair:** {self.source.auto_pair}",
            f"**Created:** {self.created_at}",
            "",
            "## Summary",
            "",
            f"- Total photos: {self.summary.total_photos}",
            f"- Processed: {self.summary.processed}",
            f"- Failed: {self.summary.failed}",
            f"- OCR ready: {self.summary.ocr_ready}",
            f"- Review ready: {self.summary.review_ready}",
            "",
        ]

        if self.summary.warnings:
            lines.extend(["### Warnings", ""])
            for w in self.summary.warnings:
                lines.append(f"- {w}")
            lines.append("")

        if self.summary.errors:
            lines.extend(["### Errors", ""])
            for e in self.summary.errors:
                lines.append(f"- {e}")
            lines.append("")

        lines.extend(["## Candidates", ""])

        for c in self.candidates:
            lines.append(f"### {c.candidate_id}")
            lines.append(f"- **Subject:** {c.subject}")
            lines.append(f"- **Status:** {c.status.value}")
            if c.front_path:
                lines.append(f"- **Front:** {c.front_path}")
            if c.back_path:
                lines.append(f"- **Back:** {c.back_path}")
            if c.warnings:
                lines.append(f"- **Warnings:** {', '.join(c.warnings)}")
            if c.errors:
                lines.append(f"- **Errors:** {', '.join(c.errors)}")
            lines.append("")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


class BatchProcessingEngine:
    """Orchestrates batch photo processing through existing engines.

    Phase 1: Folder scanning, photo discovery, auto-pairing, candidate creation,
             catalogue intake, summary, export.
    Phase 2+: OCR, matching, proposed-entry processing.
    """

    def __init__(self, cataloguer: SmartPhoneCataloguer):
        """Initialize with an existing SmartPhoneCataloguer instance.

        Args:
            cataloguer: Configured SmartPhoneCataloguer with workflow and engines.
        """
        self.cataloguer = cataloguer

    def _discover_photos(self, folder_path: str, file_pattern: str = "*.jpg") -> List[str]:
        """Discover photo files in a folder matching the pattern.

        Args:
            folder_path: Path to folder containing photos.
            file_pattern: Glob pattern for photo files.

        Returns:
            Sorted list of photo file paths.
        """
        if not os.path.isdir(folder_path):
            raise ValueError(f"Folder not found: {folder_path}")

        pattern = os.path.join(folder_path, file_pattern)
        photos = sorted(glob.glob(pattern))

        # Also check common variations
        if not photos and file_pattern == "*.jpg":
            for ext in ["*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]:
                alt_pattern = os.path.join(folder_path, ext)
                photos.extend(glob.glob(alt_pattern))
            photos = sorted(set(photos))

        return photos

    def _auto_pair_photos(self, photos: List[str]) -> List[Dict[str, Optional[str]]]:
        """Auto-pair front and back photos by filename.

        Recognizes patterns like:
        - IMG_0001_front.jpg / IMG_0001_back.jpg
        - IMG_0001_obverse.jpg / IMG_0001_reverse.jpg
        - IMG_0001.jpg / IMG_0001_back.jpg (single front implied)

        Args:
            photos: List of photo file paths.

        Returns:
            List of dicts with 'front' and 'back' keys.
        """
        if not photos:
            return []

        # Group photos by base name (without _front/_back/_obverse/_reverse suffixes)
        groups: Dict[str, Dict[str, str]] = {}

        for photo in photos:
            basename = os.path.basename(photo)
            name, _ = os.path.splitext(basename)

            # Determine role from filename
            lower_name = name.lower()
            if any(suffix in lower_name for suffix in ["_back", "_reverse", "_rev"]):
                # Extract base name by removing suffix
                base = re.sub(r'_(back|reverse|rev)$', '', name, flags=re.IGNORECASE)
                if base not in groups:
                    groups[base] = {}
                groups[base]["back"] = photo
            elif any(suffix in lower_name for suffix in ["_front", "_obverse", "_obv"]):
                base = re.sub(r'_(front|obverse|obv)$', '', name, flags=re.IGNORECASE)
                if base not in groups:
                    groups[base] = {}
                groups[base]["front"] = photo
            else:
                # No suffix — treat as front by default
                if name not in groups:
                    groups[name] = {}
                groups[name]["front"] = photo

        # Convert groups to paired list
        paired = []
        for base, group in sorted(groups.items()):
            paired.append({
                "front": group.get("front"),
                "back": group.get("back"),
                "base_name": base,
            })

        return paired

    def _create_batch_items(self, paired_photos: List[Dict[str, Optional[str]]]) -> List[Dict[str, Any]]:
        """Create batch items for SmartPhoneCataloguer from paired photos.

        Args:
            paired_photos: List of paired photo dicts.

        Returns:
            List of item dicts for batch_catalogue().
        """
        items = []
        for pair in paired_photos:
            front = pair.get("front")
            back = pair.get("back")
            base_name = pair.get("base_name", "unknown")

            item = {
                "type": "coin",
                "subject": base_name,
                "front_path": front or "",
                "back_path": back or "",
                "location": "",
                "notes": f"Batch processing candidate: {base_name}",
            }
            items.append(item)

        return items

    def process_folder(self, folder_path: str,
                       collection_items: Iterable,
                       file_pattern: str = "*.jpg",
                       auto_pair: bool = True) -> BatchReport:
        """Process an entire folder of photos.

        Phase 1: Discovers photos, auto-pairs, creates candidates,
        delegates to SmartPhoneCataloguer for catalogue intake.

        Args:
            folder_path: Path to folder containing photos.
            collection_items: Current collection items for matching (Phase 3+).
            file_pattern: Glob pattern for photo files.
            auto_pair: Whether to auto-pair front/back photos.

        Returns:
            BatchReport with all candidates and summary.
        """
        source = BatchSource(
            folder_path=folder_path,
            file_pattern=file_pattern,
            auto_pair=auto_pair,
        )
        return self.process(source, collection_items)

    def process(self, source: BatchSource,
                collection_items: Iterable) -> BatchReport:
        """Process a BatchSource through the existing pipeline.

        Args:
            source: BatchSource with folder path and options.
            collection_items: Current collection items for matching (Phase 3+).

        Returns:
            BatchReport with all candidates and summary.
        """
        report = BatchReport(source=source)
        summary = BatchSummary()

        # Step 1: Discover photos
        try:
            photos = self._discover_photos(source.folder_path, source.file_pattern)
        except ValueError as e:
            summary.errors.append(str(e))
            report.summary = summary
            return report

        if not photos:
            summary.warnings.append(f"No photos found in {source.folder_path} matching {source.file_pattern}")
            report.summary = summary
            return report

        summary.total_photos = len(photos)

        # Step 2: Auto-pair photos
        if source.auto_pair:
            paired = self._auto_pair_photos(photos)
        else:
            # No pairing — each photo is a standalone front
            paired = [{"front": p, "back": None, "base_name": os.path.splitext(os.path.basename(p))[0]} for p in photos]

        # Step 3: Create batch items and delegate to SmartPhoneCataloguer
        items = self._create_batch_items(paired)

        # Step 4: Run batch catalogue through existing engine
        try:
            batch_result = self.cataloguer.batch_catalogue(items)
        except Exception as e:
            summary.errors.append(f"Batch catalogue failed: {str(e)}")
            report.summary = summary
            return report

        # Step 5: Create BatchCandidates from results
        for i, (item, catalogue_result) in enumerate(zip(items, batch_result.results)):
            candidate = BatchCandidate(
                candidate_id=f"batch_{i:04d}_{item['subject']}",
                front_path=item.get("front_path") or None,
                back_path=item.get("back_path") or None,
                subject=item["subject"],
                catalogue_result=catalogue_result,
                status=BatchStatus.COMPLETED if catalogue_result.status == "success" else BatchStatus.FAILED,
            )

            if catalogue_result.status != "success":
                candidate.errors.append(catalogue_result.message or "Catalogue failed")
                summary.failed += 1
            else:
                summary.processed += 1
                if catalogue_result.ocr_ready:
                    summary.ocr_ready += 1
                if catalogue_result.review_ready:
                    summary.review_ready += 1

            # Phase 2+ placeholders
            candidate.ocr_result = None
            candidate.collection_match = None
            candidate.proposed_entry = None

            report.candidates.append(candidate)

        # Step 6: Add any batch-level errors
        for error in batch_result.errors:
            summary.errors.append(error)

        report.summary = summary
        return report
