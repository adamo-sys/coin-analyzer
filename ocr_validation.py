"""Validation layer for advisory OCR experiment output.

This module evaluates OCR trustworthiness only. It does not modify collection
records, update ownership, change grades, alter recommendations, or perform
image recognition.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from ocr_experiment import OCRExperiment, OCRResult, OCRSuggestionReport


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _dedupe(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        text = str(value or "").strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def _canonical_warning(value: str) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if lower == "manual review required":
        return "Manual Review Required"
    if lower == "low confidence ocr":
        return "Low Confidence OCR"
    if lower == "conflicting ocr results":
        return "Conflicting OCR Results"
    if lower == "incomplete ocr":
        return "Incomplete OCR"
    return text


class OCRTrustLevel(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class OCRValidationFinding:
    category: str
    severity: str
    message: str
    recommendation: str = "Manual review required"

    def __post_init__(self) -> None:
        self.category = str(self.category or "General").strip()
        self.severity = str(self.severity or "WARNING").strip().upper()
        self.message = str(self.message or "").strip()
        self.recommendation = str(self.recommendation or "Manual review required").strip()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "recommendation": self.recommendation,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "OCRValidationFinding":
        return cls(
            category=str(payload.get("category") or ""),
            severity=str(payload.get("severity") or ""),
            message=str(payload.get("message") or ""),
            recommendation=str(payload.get("recommendation") or "Manual review required"),
        )


@dataclass
class OCRValidationScore:
    score: int
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.score = max(0, min(100, int(self.score or 0)))
        self.strengths = _dedupe(self.strengths)
        self.weaknesses = _dedupe(self.weaknesses)
        self.recommended_actions = _dedupe(self.recommended_actions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "recommended_actions": list(self.recommended_actions),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "OCRValidationScore":
        return cls(
            score=int(payload.get("score") or 0),
            strengths=list(payload.get("strengths") or []),
            weaknesses=list(payload.get("weaknesses") or []),
            recommended_actions=list(payload.get("recommended_actions") or []),
        )


@dataclass
class OCRValidationExplanation:
    trust_level: OCRTrustLevel
    reasons: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.trust_level, OCRTrustLevel):
            self.trust_level = OCRTrustLevel(str(self.trust_level or "LOW").upper())
        self.reasons = _dedupe(self.reasons)

    def format_text(self) -> str:
        reason_text = "; ".join(self.reasons) if self.reasons else "Manual review required"
        return f"{self.trust_level.value} TRUST: {reason_text}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trust_level": self.trust_level.value,
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "OCRValidationExplanation":
        return cls(
            trust_level=OCRTrustLevel(str(payload.get("trust_level") or "LOW").upper()),
            reasons=list(payload.get("reasons") or []),
        )


@dataclass
class OCRValidationReport:
    suggestion_report: OCRSuggestionReport
    trust_level: OCRTrustLevel
    validation_score: OCRValidationScore
    explanation: OCRValidationExplanation
    findings: List[OCRValidationFinding] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    review_recommendations: List[str] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.trust_level, OCRTrustLevel):
            self.trust_level = OCRTrustLevel(str(self.trust_level or "LOW").upper())
        self.findings = [finding if isinstance(finding, OCRValidationFinding) else OCRValidationFinding.from_dict(finding) for finding in self.findings]
        self.warnings = _dedupe([_canonical_warning(warning) for warning in [*self.warnings, "Manual Review Required"]])
        self.review_recommendations = _dedupe(self.review_recommendations or ["Manually verify OCR before using it"])
        self.generated_at = self.generated_at or _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggestion_report": self.suggestion_report.to_dict(),
            "trust_level": self.trust_level.value,
            "validation_score": self.validation_score.to_dict(),
            "explanation": self.explanation.to_dict(),
            "findings": [finding.to_dict() for finding in self.findings],
            "warnings": list(self.warnings),
            "review_recommendations": list(self.review_recommendations),
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "OCRValidationReport":
        return cls(
            suggestion_report=OCRSuggestionReport.from_dict(payload.get("suggestion_report") or {}),
            trust_level=OCRTrustLevel(str(payload.get("trust_level") or "LOW").upper()),
            validation_score=OCRValidationScore.from_dict(payload.get("validation_score") or {}),
            explanation=OCRValidationExplanation.from_dict(payload.get("explanation") or {}),
            findings=[OCRValidationFinding.from_dict(row) for row in payload.get("findings", [])],
            warnings=list(payload.get("warnings") or []),
            review_recommendations=list(payload.get("review_recommendations") or []),
            generated_at=str(payload.get("generated_at") or ""),
        )

    def format_markdown(self) -> str:
        lines = [
            "# OCR Validation Report",
            "",
            f"- Trust level: {self.trust_level.value}",
            f"- Validation score: {self.validation_score.score} / 100",
            f"- Explanation: {self.explanation.format_text()}",
            f"- Manual review required: YES",
            "",
            "## OCR Suggestions",
            "",
            f"- Years: {', '.join(self.suggestion_report.possible_years) if self.suggestion_report.possible_years else 'None'}",
            f"- Denominations: {', '.join(self.suggestion_report.possible_denominations) if self.suggestion_report.possible_denominations else 'None'}",
            f"- Countries: {', '.join(self.suggestion_report.possible_countries) if self.suggestion_report.possible_countries else 'None'}",
            f"- Certification numbers: {', '.join(self.suggestion_report.possible_certification_numbers) if self.suggestion_report.possible_certification_numbers else 'None'}",
            "",
            "## Findings",
            "",
        ]
        if self.findings:
            lines.extend(f"- [{finding.severity}] {finding.category}: {finding.message} Recommendation: {finding.recommendation}" for finding in self.findings)
        else:
            lines.append("- No validation findings.")
        lines.extend(["", "## Strengths", ""])
        lines.extend(f"- {strength}" for strength in self.validation_score.strengths) if self.validation_score.strengths else lines.append("- None")
        lines.extend(["", "## Weaknesses", ""])
        lines.extend(f"- {weakness}" for weakness in self.validation_score.weaknesses) if self.validation_score.weaknesses else lines.append("- None")
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in self.warnings) if self.warnings else lines.append("- None")
        lines.extend(["", "## Review Recommendations", ""])
        lines.extend(f"- {action}" for action in self.review_recommendations)
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_markdown())
            return True
        except Exception as exc:
            print(f"Error exporting OCR validation markdown: {exc}")
            return False

    def export_csv(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "trust_level",
                    "validation_score",
                    "confidence_level",
                    "confidence_score",
                    "years",
                    "denominations",
                    "countries",
                    "certification_numbers",
                    "findings",
                    "warnings",
                    "review_recommendations",
                ])
                writer.writeheader()
                writer.writerow({
                    "trust_level": self.trust_level.value,
                    "validation_score": self.validation_score.score,
                    "confidence_level": self.suggestion_report.confidence.level,
                    "confidence_score": self.suggestion_report.confidence.score,
                    "years": ";".join(self.suggestion_report.possible_years),
                    "denominations": ";".join(self.suggestion_report.possible_denominations),
                    "countries": ";".join(self.suggestion_report.possible_countries),
                    "certification_numbers": ";".join(self.suggestion_report.possible_certification_numbers),
                    "findings": "; ".join(f"{finding.category}: {finding.message}" for finding in self.findings),
                    "warnings": "; ".join(self.warnings),
                    "review_recommendations": "; ".join(self.review_recommendations),
                })
            return True
        except Exception as exc:
            print(f"Error exporting OCR validation CSV: {exc}")
            return False


class OCRValidationEngine:
    """Evaluate whether OCR output is trustworthy enough to use after review."""

    PLAUSIBLE_YEAR_MIN = 1500
    PLAUSIBLE_YEAR_MAX = 2099

    def validate(
        self,
        ocr_result: Optional[OCRResult] = None,
        suggestion_report: Optional[OCRSuggestionReport] = None,
    ) -> OCRValidationReport:
        report = suggestion_report or self._report_from_result(ocr_result)
        findings = []
        findings.extend(self.validate_years(report))
        findings.extend(self.validate_denominations(report))
        findings.extend(self.validate_countries(report))
        findings.extend(self.validate_certifications(report))
        findings.extend(self.validate_overall(report))
        score = self.calculate_score(report, findings)
        trust_level = self.calculate_trust_level(report, findings, score)
        warnings = self._warnings_from_findings(report, findings, trust_level)
        recommendations = self._recommendations_from_findings(findings, trust_level)
        explanation = self.explain(report, findings, score, trust_level)
        return OCRValidationReport(
            suggestion_report=report,
            trust_level=trust_level,
            validation_score=score,
            explanation=explanation,
            findings=findings,
            warnings=warnings,
            review_recommendations=recommendations,
        )

    def validate_captured_photo(self, captured_photo: Any, raw_text: Optional[str] = None) -> OCRValidationReport:
        suggestion_report = OCRExperiment().from_captured_photo(captured_photo, raw_text=raw_text)
        return self.validate(suggestion_report=suggestion_report)

    def validate_years(self, report: OCRSuggestionReport) -> List[OCRValidationFinding]:
        years = report.possible_years
        findings = []
        if not years:
            findings.append(OCRValidationFinding("Year", "WARNING", "No year candidate detected", "Confirm date manually"))
            return findings
        invalid = [year for year in years if not self._is_plausible_year(year)]
        if invalid:
            findings.append(OCRValidationFinding("Year", "WARNING", f"Implausible year candidate(s): {', '.join(invalid)}", "Verify date before use"))
        if len(years) > 1:
            findings.append(OCRValidationFinding("Year", "WARNING", f"Conflicting year candidates: {', '.join(years)}", "Compare photo manually for date attribution"))
        if self._has_ambiguous_digit_context(report.result.raw_text, years):
            findings.append(OCRValidationFinding("Year", "WARNING", "Ambiguous year reading detected", "Check similar digits such as 6/8 or 3/8"))
        return findings

    def validate_denominations(self, report: OCRSuggestionReport) -> List[OCRValidationFinding]:
        denominations = report.possible_denominations
        findings = []
        if not denominations:
            findings.append(OCRValidationFinding("Denomination", "WARNING", "No denomination candidate detected", "Confirm denomination manually"))
            return findings
        normalized = {self._normalize_denomination(value) for value in denominations}
        if len(normalized) > 1:
            findings.append(OCRValidationFinding("Denomination", "WARNING", f"Conflicting denomination candidates: {', '.join(denominations)}", "Verify denomination before use"))
        if any(self._ambiguous_denomination(value) for value in denominations):
            findings.append(OCRValidationFinding("Denomination", "WARNING", "Ambiguous denomination candidate detected", "Check whether OCR confused values such as 5 and 50"))
        return findings

    def validate_countries(self, report: OCRSuggestionReport) -> List[OCRValidationFinding]:
        countries = report.possible_countries
        findings = []
        if not countries:
            findings.append(OCRValidationFinding("Country", "WARNING", "No recognized country detected", "Confirm country manually"))
        elif len(countries) > 1:
            findings.append(OCRValidationFinding("Country", "WARNING", f"Conflicting country candidates: {', '.join(countries)}", "Verify country manually"))
        raw = report.result.raw_text.upper()
        if "CANAOA" in raw or "CAN AOA" in raw:
            findings.append(OCRValidationFinding("Country", "WARNING", "Possible incomplete country reading: CANAOA", "Check whether OCR meant CANADA"))
        return findings

    def validate_certifications(self, report: OCRSuggestionReport) -> List[OCRValidationFinding]:
        certs = report.possible_certification_numbers
        findings = []
        for cert in certs:
            compact = re.sub(r"[^A-Z0-9]", "", cert.upper())
            if len(compact) < 5:
                findings.append(OCRValidationFinding("Certification", "WARNING", f"Incomplete certification candidate: {cert}", "Verify certification number manually"))
            elif not re.search(r"\d", compact):
                findings.append(OCRValidationFinding("Certification", "WARNING", f"Malformed certification candidate: {cert}", "Confirm certification number manually"))
        return findings

    def validate_overall(self, report: OCRSuggestionReport) -> List[OCRValidationFinding]:
        findings = []
        text = report.result.raw_text.strip()
        if not text or len(text) < 12:
            findings.append(OCRValidationFinding("OCR", "WARNING", "Incomplete OCR text", "Run OCR again or manually enter visible text"))
        if report.confidence.level == "Low" or report.confidence.score < 45:
            findings.append(OCRValidationFinding("OCR", "WARNING", "Low confidence OCR", "Treat suggestions as low trust"))
        if report.result.warnings:
            findings.append(OCRValidationFinding("OCR", "WARNING", "; ".join(report.result.warnings), "Resolve source OCR warning if possible"))
        return findings

    def calculate_score(self, report: OCRSuggestionReport, findings: List[OCRValidationFinding]) -> OCRValidationScore:
        score = int(report.confidence.score)
        categories_present = sum(1 for values in [
            report.possible_years,
            report.possible_denominations,
            report.possible_countries,
            report.possible_certification_numbers,
        ] if values)
        score += categories_present * 5
        for finding in findings:
            if finding.severity == "ERROR":
                score -= 25
            else:
                score -= 10
        score = max(0, min(100, score))
        strengths = []
        weaknesses = []
        if report.possible_years and len(report.possible_years) == 1:
            strengths.append("Single year candidate detected")
        if report.possible_denominations and len({self._normalize_denomination(value) for value in report.possible_denominations}) == 1:
            strengths.append("Denomination candidate is internally consistent")
        if report.possible_countries and len(report.possible_countries) == 1:
            strengths.append("Single country candidate detected")
        if report.confidence.level == "High":
            strengths.append("Underlying OCR confidence is high")
        weaknesses = [finding.message for finding in findings]
        actions = self._recommendations_from_findings(findings, self._trust_from_score(score))
        return OCRValidationScore(score, strengths, weaknesses, actions)

    def calculate_trust_level(
        self,
        report: OCRSuggestionReport,
        findings: List[OCRValidationFinding],
        score: OCRValidationScore,
    ) -> OCRTrustLevel:
        warning_count = len(findings)
        critical_missing = any(finding.category in {"Year", "Denomination", "Country"} and "No " in finding.message for finding in findings)
        conflict = any("Conflicting" in finding.message or "Ambiguous" in finding.message for finding in findings)
        if score.score >= 80 and report.confidence.level == "High" and warning_count <= 1 and not conflict:
            return OCRTrustLevel.HIGH
        if score.score >= 50 and not critical_missing:
            return OCRTrustLevel.MEDIUM
        return OCRTrustLevel.LOW

    def explain(
        self,
        report: OCRSuggestionReport,
        findings: List[OCRValidationFinding],
        score: OCRValidationScore,
        trust_level: OCRTrustLevel,
    ) -> OCRValidationExplanation:
        reasons = []
        if report.possible_years:
            reasons.append("Year candidate detected" if len(report.possible_years) == 1 else "Multiple year candidates require review")
        if report.possible_countries:
            reasons.append("Country candidate detected" if len(report.possible_countries) == 1 else "Multiple country candidates require review")
        if report.possible_denominations:
            reasons.append("Denomination candidate detected" if len(report.possible_denominations) == 1 else "Multiple denomination candidates require review")
        if findings:
            reasons.append(f"{len(findings)} validation finding(s) require manual review")
        reasons.append(f"Validation score is {score.score}/100")
        return OCRValidationExplanation(trust_level, reasons)

    def _report_from_result(self, ocr_result: Optional[OCRResult]) -> OCRSuggestionReport:
        result = ocr_result or OCRResult(image_path="", raw_text="", warnings=["No OCR result supplied"])
        experiment = OCRExperiment()
        suggestions = experiment.extract_suggestions(result.raw_text)
        confidence = experiment.calculate_confidence(result.raw_text, suggestions, result.warnings)
        return OCRSuggestionReport(result=result, confidence=confidence, warnings=["Manual review required"], **suggestions)

    def _warnings_from_findings(
        self,
        report: OCRSuggestionReport,
        findings: List[OCRValidationFinding],
        trust_level: OCRTrustLevel,
    ) -> List[str]:
        warnings = list(report.warnings)
        for finding in findings:
            if finding.category == "Year":
                warnings.append("Ambiguous Year" if "Ambiguous" in finding.message or "Conflicting" in finding.message else finding.message)
            elif finding.category == "Denomination":
                warnings.append("Ambiguous Denomination" if "Ambiguous" in finding.message or "Conflicting" in finding.message else finding.message)
            elif finding.category == "Country":
                warnings.append("Ambiguous Country" if "Ambiguous" in finding.message or "incomplete" in finding.message.lower() else finding.message)
            else:
                warnings.append(finding.message)
        if trust_level == OCRTrustLevel.LOW:
            warnings.append("Low Confidence OCR")
        if len(findings) >= 3:
            warnings.append("Conflicting OCR Results")
        warnings.append("Manual Review Required")
        return _dedupe(_canonical_warning(warning) for warning in warnings)

    def _recommendations_from_findings(
        self,
        findings: List[OCRValidationFinding],
        trust_level: OCRTrustLevel,
    ) -> List[str]:
        recommendations = [finding.recommendation for finding in findings]
        if trust_level == OCRTrustLevel.HIGH:
            recommendations.append("Verify OCR suggestions before copying them into another workflow")
        elif trust_level == OCRTrustLevel.MEDIUM:
            recommendations.append("Use OCR suggestions as a starting point only")
        else:
            recommendations.append("Do not rely on OCR suggestions without manual inspection")
        recommendations.append("Manual review required")
        return _dedupe(recommendations)

    def _trust_from_score(self, score: int) -> OCRTrustLevel:
        if score >= 80:
            return OCRTrustLevel.HIGH
        if score >= 50:
            return OCRTrustLevel.MEDIUM
        return OCRTrustLevel.LOW

    def _is_plausible_year(self, year: str) -> bool:
        try:
            value = int(year)
            return self.PLAUSIBLE_YEAR_MIN <= value <= self.PLAUSIBLE_YEAR_MAX
        except ValueError:
            return False

    @staticmethod
    def _has_ambiguous_digit_context(raw_text: str, years: List[str]) -> bool:
        text = str(raw_text or "")
        return len(years) > 1 and bool(re.search(r"\b\d{2}[2368][2368]\b", text))

    @staticmethod
    def _normalize_denomination(value: str) -> str:
        text = str(value or "").lower().replace(" ", "")
        text = text.replace("cents", "cent").replace("dollars", "dollar")
        return text

    @staticmethod
    def _ambiguous_denomination(value: str) -> bool:
        text = str(value or "").lower()
        return bool(re.search(r"\b5\s*(?:cent|cents|c)\b", text) and re.search(r"\b50\s*(?:cent|cents|c)\b", text))
