"""
Batch Processing Engine — v8.1 Phase 4

Thin orchestration layer that processes a folder of photos through the
existing Smart Phone Cataloguer pipeline.

Phase 1: folder scanning, photo discovery, auto-pairing, candidate creation,
         catalogue intake, summary, export
Phase 2: Integration with OCR, collection matching, and proposed entries
         via SmartPhoneCataloguer batch methods
Phase 3: Collection Intelligence and Deal Hunter batch outputs
         — gap reports, duplicate detection, upgrade candidates,
           acquisition priorities, and deal evaluation
Phase 4: Batch Review Workflow
         — review states (approve, reject, needs-review),
           per-candidate review decisions, review summaries,
           improved export with review states
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
from collection_intelligence import CollectionIntelligenceEngine, AcquisitionTarget
from deal_hunter import DealHunter, DealListing, DealHunterResult, DealHunterReport


class BatchStatus(Enum):
    """Processing status of a batch candidate."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class ReviewStatus(Enum):
    """Review status of a batch candidate."""
    UNREVIEWED = "unreviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


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
    ocr_result: Optional[OCRIdentificationReport] = None
    collection_match: Optional[CollectionMatchResult] = None
    proposed_entry: Optional[ProposedCollectionEntry] = None
    status: BatchStatus = BatchStatus.PENDING
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    review_notes: str = ""
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    catalogue_result: Optional[CatalogueResult] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "front_path": self.front_path,
            "back_path": self.back_path,
            "subject": self.subject,
            "status": self.status.value,
            "review_status": self.review_status.value,
            "review_notes": self.review_notes,
            "warnings": self.warnings,
            "errors": self.errors,
            "has_ocr_result": self.ocr_result is not None,
            "has_collection_match": self.collection_match is not None,
            "has_proposed_entry": self.proposed_entry is not None,
            "catalogue_result": self.catalogue_result.to_dict() if self.catalogue_result else None,
        }

    def is_reviewable(self) -> bool:
        """Return True if candidate can be reviewed (completed, not failed)."""
        return self.status == BatchStatus.COMPLETED

    def approve(self, notes: str = "") -> None:
        """Approve this candidate."""
        if not self.is_reviewable():
            raise ValueError(f"Cannot approve candidate with status {self.status.value}")
        self.review_status = ReviewStatus.APPROVED
        self.review_notes = notes

    def reject(self, notes: str = "") -> None:
        """Reject this candidate."""
        if not self.is_reviewable():
            raise ValueError(f"Cannot reject candidate with status {self.status.value}")
        self.review_status = ReviewStatus.REJECTED
        self.review_notes = notes

    def mark_needs_review(self, notes: str = "") -> None:
        """Mark candidate as needing manual review."""
        if not self.is_reviewable():
            raise ValueError(f"Cannot mark candidate with status {self.status.value}")
        self.review_status = ReviewStatus.NEEDS_REVIEW
        self.review_notes = notes


@dataclass
class BatchSummary:
    """Summary statistics for the batch."""
    total_photos: int = 0
    processed: int = 0
    failed: int = 0
    ocr_ready: int = 0
    review_ready: int = 0
    duplicates_detected: int = 0
    upgrade_opportunities: int = 0
    gap_opportunities: int = 0
    reviewed_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    needs_review_count: int = 0
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
            "reviewed_count": self.reviewed_count,
            "approved_count": self.approved_count,
            "rejected_count": self.rejected_count,
            "needs_review_count": self.needs_review_count,
            "warnings": self.warnings,
            "errors": self.errors,
        }


@dataclass
class BatchIntelligence:
    """Collection intelligence outputs for the batch pool."""
    gap_report: Optional[Dict[str, Any]] = None
    batch_duplicates: List[Dict[str, Any]] = field(default_factory=list)
    batch_upgrades: List[Dict[str, Any]] = field(default_factory=list)
    acquisition_priorities: List[AcquisitionTarget] = field(default_factory=list)
    deal_evaluation: Optional[DealHunterReport] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_report": self.gap_report,
            "batch_duplicates": self.batch_duplicates,
            "batch_upgrades": self.batch_upgrades,
            "acquisition_priorities": [t.to_dict() for t in self.acquisition_priorities],
            "has_deal_evaluation": self.deal_evaluation is not None,
        }


@dataclass
class BatchReport:
    """Consolidated report for the entire batch."""
    source: BatchSource
    candidates: List[BatchCandidate] = field(default_factory=list)
    summary: BatchSummary = field(default_factory=BatchSummary)
    intelligence: BatchIntelligence = field(default_factory=BatchIntelligence)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "candidates": [c.to_dict() for c in self.candidates],
            "summary": self.summary.to_dict(),
            "intelligence": self.intelligence.to_dict(),
            "created_at": self.created_at,
        }

    def review_summary(self) -> Dict[str, Any]:
        """Return a summary of review states across all candidates."""
        total = len(self.candidates)
        reviewable = [c for c in self.candidates if c.is_reviewable()]
        approved = [c for c in self.candidates if c.review_status == ReviewStatus.APPROVED]
        rejected = [c for c in self.candidates if c.review_status == ReviewStatus.REJECTED]
        needs_review = [c for c in self.candidates if c.review_status == ReviewStatus.NEEDS_REVIEW]
        unreviewed = [c for c in self.candidates if c.review_status == ReviewStatus.UNREVIEWED]

        return {
            "total_candidates": total,
            "reviewable": len(reviewable),
            "approved": len(approved),
            "rejected": len(rejected),
            "needs_review": len(needs_review),
            "unreviewed": len(unreviewed),
            "review_completion_pct": (len(approved) + len(rejected)) / len(reviewable) * 100 if reviewable else 0,
        }

    def approved_candidates(self) -> List[BatchCandidate]:
        """Return all approved candidates."""
        return [c for c in self.candidates if c.review_status == ReviewStatus.APPROVED]

    def rejected_candidates(self) -> List[BatchCandidate]:
        """Return all rejected candidates."""
        return [c for c in self.candidates if c.review_status == ReviewStatus.REJECTED]

    def needs_review_candidates(self) -> List[BatchCandidate]:
        """Return all candidates marked as needs-review."""
        return [c for c in self.candidates if c.review_status == ReviewStatus.NEEDS_REVIEW]

    def export_csv(self, path: str) -> None:
        """Export batch report to CSV."""
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "candidate_id", "subject", "status", "review_status", "review_notes",
                "front_path", "back_path",
                "warnings", "errors", "has_ocr", "has_match", "has_proposed_entry",
            ])
            for c in self.candidates:
                writer.writerow([
                    c.candidate_id,
                    c.subject,
                    c.status.value,
                    c.review_status.value,
                    c.review_notes,
                    c.front_path or "",
                    c.back_path or "",
                    "; ".join(c.warnings) if c.warnings else "",
                    "; ".join(c.errors) if c.errors else "",
                    "yes" if c.ocr_result else "no",
                    "yes" if c.collection_match else "no",
                    "yes" if c.proposed_entry else "no",
                ])
            writer.writerow([])
            writer.writerow(["Summary"])
            writer.writerow(["total_photos", self.summary.total_photos])
            writer.writerow(["processed", self.summary.processed])
            writer.writerow(["failed", self.summary.failed])
            writer.writerow(["ocr_ready", self.summary.ocr_ready])
            writer.writerow(["review_ready", self.summary.review_ready])
            writer.writerow(["duplicates_detected", self.summary.duplicates_detected])
            writer.writerow(["upgrade_opportunities", self.summary.upgrade_opportunities])
            writer.writerow(["gap_opportunities", self.summary.gap_opportunities])
            writer.writerow(["reviewed_count", self.summary.reviewed_count])
            writer.writerow(["approved_count", self.summary.approved_count])
            writer.writerow(["rejected_count", self.summary.rejected_count])
            writer.writerow(["needs_review_count", self.summary.needs_review_count])

    def export_markdown(self, path: str) -> None:
        """Export batch report to Markdown."""
        review = self.review_summary()
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
            f"- Duplicates detected: {self.summary.duplicates_detected}",
            f"- Upgrade opportunities: {self.summary.upgrade_opportunities}",
            f"- Gap opportunities: {self.summary.gap_opportunities}",
            "",
            "## Review Summary",
            "",
            f"- Total candidates: {review['total_candidates']}",
            f"- Reviewable: {review['reviewable']}",
            f"- Approved: {review['approved']}",
            f"- Rejected: {review['rejected']}",
            f"- Needs review: {review['needs_review']}",
            f"- Unreviewed: {review['unreviewed']}",
            f"- Completion: {review['review_completion_pct']:.1f}%",
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

        # Phase 3: Collection Intelligence section
        if self.intelligence.batch_duplicates or self.intelligence.batch_upgrades or self.intelligence.acquisition_priorities:
            lines.extend(["## Collection Intelligence", ""])
            if self.intelligence.batch_duplicates:
                lines.extend(["### Batch Duplicates", ""])
                for dup in self.intelligence.batch_duplicates:
                    lines.append(f"- {dup.get('country', '')} {dup.get('denomination', '')} {dup.get('year', '')}: {dup.get('count', 1)} in batch")
                lines.append("")
            if self.intelligence.batch_upgrades:
                lines.extend(["### Batch Upgrade Candidates", ""])
                for upg in self.intelligence.batch_upgrades:
                    lines.append(f"- {upg.get('country', '')} {upg.get('denomination', '')} {upg.get('year', '')}: best grade {upg.get('current_best_grade', 'unknown')}")
                lines.append("")
            if self.intelligence.acquisition_priorities:
                lines.extend(["### Acquisition Priorities", ""])
                for target in self.intelligence.acquisition_priorities[:10]:
                    lines.append(f"- [{target.priority_score}] {target.coin_label} ({target.target_type}): {target.reason}")
                lines.append("")

        lines.extend(["## Candidates", ""])
        for c in self.candidates:
            lines.append(f"### {c.candidate_id}")
            lines.append(f"- **Subject:** {c.subject}")
            lines.append(f"- **Status:** {c.status.value}")
            lines.append(f"- **Review:** {c.review_status.value}")
            if c.review_notes:
                lines.append(f"- **Review Notes:** {c.review_notes}")
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
    Phase 2: Integration with OCR, collection matching, and proposed entries.
    Phase 3: Collection Intelligence and Deal Hunter batch outputs.
    Phase 4: Batch Review Workflow — per-candidate review states and summaries.
    """

    def __init__(self, cataloguer: SmartPhoneCataloguer):
        """Initialize with an existing SmartPhoneCataloguer instance."""
        self.cataloguer = cataloguer

    def _discover_photos(self, folder_path: str, file_pattern: str = "*.jpg") -> List[str]:
        """Discover photo files in a folder matching the pattern."""
        if not os.path.isdir(folder_path):
            raise ValueError(f"Folder not found: {folder_path}")
        pattern = os.path.join(folder_path, file_pattern)
        photos = sorted(glob.glob(pattern))
        if not photos and file_pattern == "*.jpg":
            for ext in ["*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]:
                alt_pattern = os.path.join(folder_path, ext)
                photos.extend(glob.glob(alt_pattern))
            photos = sorted(set(photos))
        return photos

    def _auto_pair_photos(self, photos: List[str]) -> List[Dict[str, Optional[str]]]:
        """Auto-pair front and back photos by filename."""
        if not photos:
            return []
        groups: Dict[str, Dict[str, str]] = {}
        for photo in photos:
            basename = os.path.basename(photo)
            name, _ = os.path.splitext(basename)
            lower_name = name.lower()
            if any(suffix in lower_name for suffix in ["_back", "_reverse", "_rev"]):
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
                if name not in groups:
                    groups[name] = {}
                groups[name]["front"] = photo
        paired = []
        for base, group in sorted(groups.items()):
            paired.append({"front": group.get("front"), "back": group.get("back"), "base_name": base})
        return paired

    def _create_batch_items(self, paired_photos: List[Dict[str, Optional[str]]]) -> List[Dict[str, Any]]:
        """Create batch items for SmartPhoneCataloguer from paired photos."""
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

    def _run_collection_intelligence(self, candidates: List[BatchCandidate], collection_items: Iterable) -> BatchIntelligence:
        """Run CollectionIntelligenceEngine on the batch pool and collection."""
        intelligence = BatchIntelligence()
        pool_items = list(collection_items) if collection_items else []
        for candidate in candidates:
            if candidate.proposed_entry:
                pool_items.append(candidate.proposed_entry)
        if not pool_items:
            return intelligence
        try:
            ci_engine = CollectionIntelligenceEngine(pool_items)
            intelligence.gap_report = ci_engine.generate_gap_report()
            all_duplicates = ci_engine.detect_duplicates()
            batch_candidate_ids = {c.candidate_id for c in candidates}
            intelligence.batch_duplicates = [
                dup for dup in all_duplicates
                if any(getattr(item, 'candidate_id', None) in batch_candidate_ids for item in dup.get("items", []))
            ]
            intelligence.batch_upgrades = ci_engine.detect_upgrade_candidates()
            intelligence.acquisition_priorities = ci_engine.generate_acquisition_priorities()
        except Exception as e:
            intelligence.gap_report = {"error": str(e)}
        return intelligence

    def _evaluate_deals(self, candidates: List[BatchCandidate], collection_items: Iterable) -> Optional[DealHunterReport]:
        """Evaluate batch candidates as deals using DealHunter."""
        try:
            listings = []
            for candidate in candidates:
                if candidate.catalogue_result and candidate.catalogue_result.status == "success":
                    listing = DealListing(
                        title=candidate.subject,
                        price_cad=0.0,
                        shipping_cad=0.0,
                        description=f"Batch candidate: {candidate.candidate_id}",
                    )
                    listings.append(listing)
            if not listings:
                return None
            hunter = DealHunter(collection_items)
            return hunter.generate_report(listings)
        except Exception:
            return None

    def _update_review_summary(self, report: BatchReport) -> None:
        """Update summary counts from candidate review states."""
        report.summary.reviewed_count = sum(1 for c in report.candidates if c.review_status != ReviewStatus.UNREVIEWED)
        report.summary.approved_count = sum(1 for c in report.candidates if c.review_status == ReviewStatus.APPROVED)
        report.summary.rejected_count = sum(1 for c in report.candidates if c.review_status == ReviewStatus.REJECTED)
        report.summary.needs_review_count = sum(1 for c in report.candidates if c.review_status == ReviewStatus.NEEDS_REVIEW)

    def review_candidate(self, report: BatchReport, candidate_id: str, 
                         review_status: ReviewStatus, notes: str = "") -> None:
        """Review a single candidate in a batch report.

        Args:
            report: The BatchReport containing the candidate.
            candidate_id: The candidate_id to review.
            review_status: The review decision (APPROVED, REJECTED, NEEDS_REVIEW).
            notes: Optional review notes.
        """
        candidate = next((c for c in report.candidates if c.candidate_id == candidate_id), None)
        if not candidate:
            raise ValueError(f"Candidate {candidate_id} not found in report")

        if review_status == ReviewStatus.APPROVED:
            candidate.approve(notes)
        elif review_status == ReviewStatus.REJECTED:
            candidate.reject(notes)
        elif review_status == ReviewStatus.NEEDS_REVIEW:
            candidate.mark_needs_review(notes)
        elif review_status == ReviewStatus.UNREVIEWED:
            candidate.review_status = ReviewStatus.UNREVIEWED
            candidate.review_notes = notes
        else:
            raise ValueError(f"Invalid review status: {review_status}")

        self._update_review_summary(report)

    def auto_review(self, report: BatchReport) -> None:
        """Auto-review candidates based on intelligence signals.

        Automatically approves candidates with no warnings and no duplicates.
        Marks candidates with errors or duplicates as needs-review.

        Args:
            report: The BatchReport to auto-review.
        """
        for candidate in report.candidates:
            if not candidate.is_reviewable():
                continue

            if candidate.errors:
                candidate.mark_needs_review("Auto: candidate has errors")
            elif candidate.warnings:
                candidate.mark_needs_review("Auto: candidate has warnings")
            elif candidate.collection_match and candidate.collection_match.is_duplicate:
                candidate.mark_needs_review("Auto: possible duplicate")
            else:
                candidate.approve("Auto: no issues detected")

        self._update_review_summary(report)

    def process_folder(self, folder_path: str,
                       collection_items: Iterable,
                       file_pattern: str = "*.jpg",
                       auto_pair: bool = True) -> BatchReport:
        """Process an entire folder of photos."""
        source = BatchSource(
            folder_path=folder_path,
            file_pattern=file_pattern,
            auto_pair=auto_pair,
        )
        return self.process(source, collection_items)

    def process(self, source: BatchSource,
                collection_items: Iterable) -> BatchReport:
        """Process a BatchSource through the existing pipeline.

        Phase 4: Includes review workflow initialization.
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
            paired = [{"front": p, "back": None, "base_name": os.path.splitext(os.path.basename(p))[0]} for p in photos]

        # Step 3: Create batch items
        items = self._create_batch_items(paired)

        # Step 4: Run batch catalogue through existing engine
        try:
            batch_result = self.cataloguer.batch_catalogue(items)
        except Exception as e:
            summary.errors.append(f"Batch catalogue failed: {str(e)}")
            report.summary = summary
            return report

        # Step 5: Create BatchCandidates from catalogue results
        candidates = []
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

            candidates.append(candidate)

        # Step 6: Phase 2 — Batch OCR identification
        try:
            ocr_results = self.cataloguer.batch_identify([c.catalogue_result for c in candidates if c.catalogue_result])
            for candidate, ocr_result in zip(candidates, ocr_results):
                candidate.ocr_result = ocr_result
        except Exception as e:
            summary.warnings.append(f"Batch OCR failed: {str(e)}")

        # Step 7: Phase 2 — Batch collection matching
        try:
            match_results = self.cataloguer.batch_match([c.catalogue_result for c in candidates if c.catalogue_result], collection_items)
            for candidate, match_result in zip(candidates, match_results):
                candidate.collection_match = match_result
                if match_result and match_result.is_duplicate:
                    summary.duplicates_detected += 1
                if match_result and match_result.is_upgrade:
                    summary.upgrade_opportunities += 1
                if match_result and match_result.is_gap:
                    summary.gap_opportunities += 1
        except Exception as e:
            summary.warnings.append(f"Batch matching failed: {str(e)}")

        # Step 8: Phase 2 — Batch proposed entries
        try:
            proposed = self.cataloguer.batch_create_proposed_entries([c.catalogue_result for c in candidates if c.catalogue_result])
            for candidate, proposed_entry in zip(candidates, proposed):
                candidate.proposed_entry = proposed_entry
        except Exception as e:
            summary.warnings.append(f"Batch proposed entries failed: {str(e)}")

        # Step 9: Phase 3 — Collection Intelligence
        try:
            report.intelligence = self._run_collection_intelligence(candidates, collection_items)
        except Exception as e:
            summary.warnings.append(f"Collection intelligence failed: {str(e)}")

        # Step 10: Phase 3 — Deal Hunter
        try:
            report.intelligence.deal_evaluation = self._evaluate_deals(candidates, collection_items)
        except Exception:
            pass

        # Step 11: Add batch-level errors
        for error in batch_result.errors:
            summary.errors.append(error)

        report.candidates = candidates
        report.summary = summary

        # Step 12: Phase 4 — Initialize review summary counts
        self._update_review_summary(report)

        return report
