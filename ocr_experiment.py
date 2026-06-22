"""Advisory OCR experiments for photo-assisted collection workflows.

OCR output is review-only. This module does not modify collection records,
create ownership entries, grade items, update recommendations, scrape data, or
perform image recognition beyond optional local text extraction.
"""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _dedupe(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        text = _clean_text(value)
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


@dataclass
class OCRConfidence:
    """Deterministic confidence label for OCR suggestions."""

    level: str
    score: int
    reason: str

    def __post_init__(self) -> None:
        self.score = max(0, min(100, int(self.score or 0)))
        level = (self.level or "").strip().title()
        if level not in {"High", "Medium", "Low"}:
            if self.score >= 75:
                level = "High"
            elif self.score >= 45:
                level = "Medium"
            else:
                level = "Low"
        self.level = level
        self.reason = _clean_text(self.reason) or "Deterministic OCR signal scoring"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "score": self.score,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "OCRConfidence":
        return cls(
            level=str(payload.get("level") or ""),
            score=int(payload.get("score") or 0),
            reason=str(payload.get("reason") or ""),
        )


@dataclass
class OCRResult:
    """Raw OCR output and source metadata."""

    image_path: str
    raw_text: str = ""
    engine: str = "pytesseract"
    created_at: str = ""
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.image_path = _clean_text(self.image_path)
        self.raw_text = str(self.raw_text or "")
        self.engine = _clean_text(self.engine) or "pytesseract"
        self.created_at = self.created_at or _now_iso()
        self.warnings = _dedupe(self.warnings)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_path": self.image_path,
            "raw_text": self.raw_text,
            "engine": self.engine,
            "created_at": self.created_at,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "OCRResult":
        return cls(
            image_path=str(payload.get("image_path") or ""),
            raw_text=str(payload.get("raw_text") or ""),
            engine=str(payload.get("engine") or "pytesseract"),
            created_at=str(payload.get("created_at") or ""),
            warnings=list(payload.get("warnings") or []),
        )


@dataclass
class OCRSuggestionReport:
    """Review-only suggestions extracted from OCR text."""

    result: OCRResult
    possible_years: List[str] = field(default_factory=list)
    possible_denominations: List[str] = field(default_factory=list)
    possible_countries: List[str] = field(default_factory=list)
    possible_note_prefixes: List[str] = field(default_factory=list)
    possible_certification_numbers: List[str] = field(default_factory=list)
    confidence: OCRConfidence = field(default_factory=lambda: OCRConfidence("Low", 0, "No OCR signals"))
    warnings: List[str] = field(default_factory=list)
    manual_review_required: bool = True
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.possible_years = _dedupe(self.possible_years)
        self.possible_denominations = _dedupe(self.possible_denominations)
        self.possible_countries = _dedupe(self.possible_countries)
        self.possible_note_prefixes = _dedupe(self.possible_note_prefixes)
        self.possible_certification_numbers = _dedupe(self.possible_certification_numbers)
        self.warnings = _dedupe([*self.result.warnings, *self.warnings, "Manual review required"])
        self.manual_review_required = True
        self.generated_at = self.generated_at or _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result": self.result.to_dict(),
            "possible_years": list(self.possible_years),
            "possible_denominations": list(self.possible_denominations),
            "possible_countries": list(self.possible_countries),
            "possible_note_prefixes": list(self.possible_note_prefixes),
            "possible_certification_numbers": list(self.possible_certification_numbers),
            "confidence": self.confidence.to_dict(),
            "warnings": list(self.warnings),
            "manual_review_required": self.manual_review_required,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "OCRSuggestionReport":
        return cls(
            result=OCRResult.from_dict(payload.get("result") or {}),
            possible_years=list(payload.get("possible_years") or []),
            possible_denominations=list(payload.get("possible_denominations") or []),
            possible_countries=list(payload.get("possible_countries") or []),
            possible_note_prefixes=list(payload.get("possible_note_prefixes") or []),
            possible_certification_numbers=list(payload.get("possible_certification_numbers") or []),
            confidence=OCRConfidence.from_dict(payload.get("confidence") or {}),
            warnings=list(payload.get("warnings") or []),
            manual_review_required=True,
            generated_at=str(payload.get("generated_at") or ""),
        )

    def format_markdown(self) -> str:
        lines = [
            "# OCR Suggestion Report",
            "",
            f"- Image path: {self.result.image_path or 'Not provided'}",
            f"- OCR engine: {self.result.engine}",
            f"- Confidence: {self.confidence.level} ({self.confidence.score}%)",
            f"- Confidence reason: {self.confidence.reason}",
            f"- Manual review required: {'YES' if self.manual_review_required else 'NO'}",
            "",
            "## Raw OCR Text",
            "",
            self.result.raw_text.strip() or "_No OCR text available._",
            "",
            "## Possible Matches",
            "",
            f"- Years: {', '.join(self.possible_years) if self.possible_years else 'None'}",
            f"- Denominations: {', '.join(self.possible_denominations) if self.possible_denominations else 'None'}",
            f"- Countries: {', '.join(self.possible_countries) if self.possible_countries else 'None'}",
            f"- Note prefixes: {', '.join(self.possible_note_prefixes) if self.possible_note_prefixes else 'None'}",
            f"- Certification numbers: {', '.join(self.possible_certification_numbers) if self.possible_certification_numbers else 'None'}",
            "",
            "## Warnings",
            "",
        ]
        lines.extend(f"- {warning}" for warning in self.warnings) if self.warnings else lines.append("- None")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_markdown())
            return True
        except Exception as exc:
            print(f"Error exporting OCR markdown: {exc}")
            return False

    def export_csv(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "image_path",
                    "confidence_level",
                    "confidence_score",
                    "possible_years",
                    "possible_denominations",
                    "possible_countries",
                    "possible_note_prefixes",
                    "possible_certification_numbers",
                    "manual_review_required",
                    "warnings",
                    "raw_text",
                ])
                writer.writeheader()
                writer.writerow({
                    "image_path": self.result.image_path,
                    "confidence_level": self.confidence.level,
                    "confidence_score": self.confidence.score,
                    "possible_years": ";".join(self.possible_years),
                    "possible_denominations": ";".join(self.possible_denominations),
                    "possible_countries": ";".join(self.possible_countries),
                    "possible_note_prefixes": ";".join(self.possible_note_prefixes),
                    "possible_certification_numbers": ";".join(self.possible_certification_numbers),
                    "manual_review_required": "YES",
                    "warnings": "; ".join(self.warnings),
                    "raw_text": self.result.raw_text,
                })
            return True
        except Exception as exc:
            print(f"Error exporting OCR CSV: {exc}")
            return False


class OCRExperiment:
    """Run review-only OCR and extract deterministic text suggestions."""

    COUNTRY_TERMS = [
        "Argentina",
        "Australia",
        "Austria",
        "Belgium",
        "Brazil",
        "Canada",
        "China",
        "France",
        "Germany",
        "Great Britain",
        "India",
        "Italy",
        "Japan",
        "Mexico",
        "Netherlands",
        "Newfoundland",
        "Portugal",
        "Spain",
        "United Kingdom",
        "United States",
        "USA",
    ]
    DENOMINATION_PATTERNS = [
        r"\b\d+\s?(?:cent|cents|c|¢)\b",
        r"\b\d+\s?(?:dollar|dollars)\b",
        r"\$\s?\d+\b",
        r"\b(?:penny|nickel|dime|quarter|half dollar|dollar)\b",
        r"\b(?:five|ten|twenty|fifty|one hundred)\s?(?:cents|dollars)\b",
    ]
    YEAR_PATTERN = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")
    NOTE_PREFIX_PATTERN = re.compile(r"\b[A-Z]{1,4}\s?\d{5,9}\b")
    CERTIFIER_PATTERN = re.compile(r"\b(?:PCGS|NGC|ICCS|ANACS|CCCS)\s*[:#-]?\s*([A-Z0-9]{4,14})\b", re.IGNORECASE)

    def run(self, image_path: str = "", raw_text: Optional[str] = None, engine: str = "pytesseract") -> OCRSuggestionReport:
        warnings = []
        text = ""
        engine_name = engine or "pytesseract"
        if raw_text is not None:
            text = str(raw_text)
            engine_name = "provided text"
        else:
            image_path = _clean_text(image_path)
            if not image_path:
                warnings.append("No image path supplied")
            elif not os.path.exists(image_path):
                warnings.append(f"Image file not found: {image_path}")
            else:
                text, ocr_warnings = self._run_local_ocr(image_path)
                warnings.extend(ocr_warnings)
        result = OCRResult(
            image_path=image_path,
            raw_text=text,
            engine=engine_name,
            warnings=warnings,
        )
        suggestions = self.extract_suggestions(text)
        report_warnings = self._report_warnings(text, suggestions)
        confidence = self.calculate_confidence(text, suggestions, warnings + report_warnings)
        return OCRSuggestionReport(
            result=result,
            confidence=confidence,
            warnings=report_warnings,
            **suggestions,
        )

    def from_photo_candidate(self, photo_candidate: Any, raw_text: Optional[str] = None) -> OCRSuggestionReport:
        image_path = ""
        for attr in ["front_photo", "reverse_photo"]:
            image_path = _clean_text(getattr(photo_candidate, attr, ""))
            if image_path:
                break
        if not image_path:
            refs = list(getattr(photo_candidate, "reference_photos", []) or [])
            image_path = _clean_text(refs[0]) if refs else ""
        report = self.run(image_path=image_path, raw_text=raw_text)
        if not image_path:
            report.warnings = _dedupe([*report.warnings, "Photo candidate has no photo reference"])
        return report

    def from_photo_record(self, photo_record: Any, raw_text: Optional[str] = None) -> OCRSuggestionReport:
        return self.run(image_path=_clean_text(getattr(photo_record, "file_path", "")), raw_text=raw_text)

    def from_captured_photo(self, captured_photo: Any, raw_text: Optional[str] = None) -> OCRSuggestionReport:
        return self.run(image_path=_clean_text(getattr(captured_photo, "file_path", "")), raw_text=raw_text)

    def from_mobile_candidate(self, mobile_candidate: Any, raw_text: Optional[str] = None) -> OCRSuggestionReport:
        return self.run(image_path=_clean_text(getattr(mobile_candidate, "photo_reference_id", "")), raw_text=raw_text)

    def extract_suggestions(self, text: str) -> Dict[str, List[str]]:
        source = str(text or "")
        lower_source = source.lower()
        countries = [country for country in self.COUNTRY_TERMS if country.lower() in lower_source]
        denominations = []
        for pattern in self.DENOMINATION_PATTERNS:
            denominations.extend(re.findall(pattern, source, flags=re.IGNORECASE))
        certs = [match.upper() for match in self.CERTIFIER_PATTERN.findall(source)]
        note_prefixes = [match.replace(" ", "").upper() for match in self.NOTE_PREFIX_PATTERN.findall(source)]
        generic_certs = [
            token.upper()
            for token in re.findall(r"\b[A-Z]{2,4}\d{4,10}\b", source)
            if token.upper() not in note_prefixes
        ]
        certs.extend(generic_certs)
        return {
            "possible_years": _dedupe(self.YEAR_PATTERN.findall(source)),
            "possible_denominations": _dedupe(denominations),
            "possible_countries": _dedupe(countries),
            "possible_note_prefixes": _dedupe(note_prefixes),
            "possible_certification_numbers": _dedupe(certs),
        }

    def calculate_confidence(self, text: str, suggestions: Dict[str, List[str]], warnings: Optional[Iterable[str]] = None) -> OCRConfidence:
        source = str(text or "").strip()
        active_categories = sum(1 for values in suggestions.values() if values)
        score = min(35, len(source) // 4) + active_categories * 14
        if len(source) >= 40:
            score += 8
        if warnings:
            score -= min(20, len(list(warnings)) * 5)
        score = max(0, min(95, score))
        if score >= 75:
            level = "High"
        elif score >= 45:
            level = "Medium"
        else:
            level = "Low"
        reason = f"{active_categories} suggestion categor{'y' if active_categories == 1 else 'ies'} found from {len(source)} OCR character(s)"
        if not source:
            reason = "No OCR text available"
        return OCRConfidence(level, score, reason)

    def _run_local_ocr(self, image_path: str) -> tuple[str, List[str]]:
        try:
            from PIL import Image
            import pytesseract

            with Image.open(image_path) as image:
                return pytesseract.image_to_string(image), []
        except Exception as exc:
            return "", [f"OCR engine unavailable or failed: {exc}"]

    @staticmethod
    def _report_warnings(text: str, suggestions: Dict[str, List[str]]) -> List[str]:
        warnings = ["OCR output is advisory only"]
        if not str(text or "").strip():
            warnings.append("No OCR text available")
        if sum(1 for values in suggestions.values() if values) == 0:
            warnings.append("No structured suggestions extracted")
        if len(str(text or "").strip()) < 12:
            warnings.append("OCR text is incomplete or ambiguous")
        return warnings
