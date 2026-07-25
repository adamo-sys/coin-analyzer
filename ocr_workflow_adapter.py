"""Adapter from legacy advisory OCR reports to workflow OCR contracts.

This module is deliberately outside ``capture_import``. The hardened importer
contracts therefore remain independent from the older mutable OCR experiment
and validation implementations.
"""

from __future__ import annotations

from typing import Iterable

from capture_import.workflow_ocr_models import (
    OCRConflict,
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRObservation,
    OCRReviewStatus,
)
from ocr_experiment import OCRSuggestionReport
from ocr_validation import OCRValidationReport


_FIELD_SOURCES = (
    ("year", "possible_years"),
    ("denomination", "possible_denominations"),
    ("country", "possible_countries"),
    ("banknote_prefix", "possible_note_prefixes"),
    ("certification_number", "possible_certification_numbers"),
)


def _unique_sorted(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(value).strip()
                for value in values
                if str(value).strip()
            }
        )
    )


class OCRWorkflowAdapter:
    """Translate existing OCR reports into immutable workflow metadata."""

    @staticmethod
    def unavailable() -> OCRMetadataReport:
        report = OCRMetadataReport(
            provider_available=False,
            review_status=OCRReviewStatus.UNAVAILABLE,
        )
        report.validate()
        return report

    def adapt(
        self,
        *,
        source_coin_id: str,
        image_role: str,
        artifact_key: str,
        suggestion_report: OCRSuggestionReport,
        validation_report: OCRValidationReport,
    ) -> OCRMetadataReport:
        if validation_report.suggestion_report is not suggestion_report:
            if (
                validation_report.suggestion_report.to_dict()
                != suggestion_report.to_dict()
            ):
                raise ValueError(
                    "validation_report does not describe suggestion_report."
                )

        provider_id = (
            str(suggestion_report.result.engine).strip()
            or "unknown-ocr-provider"
        )
        raw_text = str(suggestion_report.result.raw_text or "")
        confidence_score = float(validation_report.validation_score.score)

        observation = OCRObservation(
            source_coin_id=source_coin_id,
            image_role=image_role,
            artifact_key=artifact_key,
            provider_id=provider_id,
            raw_text=raw_text,
            confidence_score=confidence_score,
        )
        observation.validate()

        evidence = _unique_sorted(
            (
                f"trust:{validation_report.trust_level.value}",
                f"validation-score:{validation_report.validation_score.score}",
                *validation_report.validation_score.strengths,
            )
        )

        candidates: list[OCRFieldCandidate] = []
        conflicts: list[OCRConflict] = []

        for field_name, attribute_name in _FIELD_SOURCES:
            values = _unique_sorted(
                getattr(suggestion_report, attribute_name, ())
            )

            for value in values:
                candidate = OCRFieldCandidate(
                    source_coin_id=source_coin_id,
                    image_role=image_role,
                    artifact_key=artifact_key,
                    provider_id=provider_id,
                    field_name=field_name,
                    raw_text=raw_text,
                    normalized_value=value,
                    confidence_score=confidence_score,
                    evidence=evidence,
                    review_status=(
                        OCRReviewStatus.CONFLICT
                        if len(values) > 1
                        else OCRReviewStatus.REVIEW_REQUIRED
                    ),
                )
                candidate.validate()
                candidates.append(candidate)

            if len(values) > 1:
                conflict = OCRConflict(
                    source_coin_id=source_coin_id,
                    field_name=field_name,
                    candidate_values=values,
                    reason=(
                        f"OCR produced multiple {field_name} candidates "
                        "that require manual review."
                    ),
                )
                conflict.validate()
                conflicts.append(conflict)

        ordered_candidates = tuple(
            sorted(
                candidates,
                key=lambda item: (
                    item.source_coin_id,
                    item.field_name,
                    item.image_role,
                    item.normalized_value,
                    item.provider_id,
                    item.artifact_key,
                ),
            )
        )
        ordered_conflicts = tuple(
            sorted(
                conflicts,
                key=lambda item: (
                    item.source_coin_id,
                    item.field_name,
                    item.candidate_values,
                ),
            )
        )

        report = OCRMetadataReport(
            provider_available=True,
            observations=(observation,),
            candidates=ordered_candidates,
            conflicts=ordered_conflicts,
            review_status=(
                OCRReviewStatus.CONFLICT
                if ordered_conflicts
                else OCRReviewStatus.REVIEW_REQUIRED
            ),
        )
        report.validate()
        return report