"""Immutable handoff from opt-in OCR workflow output to desktop review.

The OCR workflow emits JSON-safe per-image report payloads.  Desktop review
operates on one immutable ``OCRMetadataReport`` so accepted candidates from
different image roles can be consolidated together.  This module performs
only that decoding and deterministic aggregation; review, consolidation,
conflict-resolution, and projection rules remain in the existing services.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from capture_import.workflow_execution import PipelineOutcome
from capture_import.workflow_ocr_models import (
    OCRConflict,
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRObservation,
    OCRReviewStatus,
)
from capture_import.workflow_ocr_review_controller import (
    OCRReviewSessionController,
)
from capture_import.workflow_pipeline import ProcessingPipeline


@dataclass(frozen=True, slots=True)
class DesktopOCRReviewHandoff:
    """Existing review inputs recovered from one opt-in workflow outcome."""

    report: OCRMetadataReport
    review_controller: OCRReviewSessionController

    def __post_init__(self) -> None:
        if not isinstance(self.report, OCRMetadataReport):
            raise TypeError("report must be an OCRMetadataReport.")
        if not isinstance(
            self.review_controller,
            OCRReviewSessionController,
        ):
            raise TypeError(
                "review_controller must be an "
                "OCRReviewSessionController."
            )
        self.report.validate()


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object.")
    if not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} keys must be strings.")
    return value


def _list(value: object, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list.")
    return value


def _string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string.")
    return value


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean.")
    return value


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer.")
    return value


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric.")
    return float(value)


def _status(value: object, name: str) -> OCRReviewStatus:
    try:
        return OCRReviewStatus(_string(value, name))
    except ValueError as exc:
        raise ValueError(f"{name} is unsupported.") from exc


def _composition_contract(
    composition: object,
) -> tuple[ProcessingPipeline, OCRReviewSessionController]:
    try:
        pipeline = composition.pipeline
    except AttributeError as exc:
        raise TypeError(
            "composition must expose a public pipeline attribute."
        ) from exc
    if not isinstance(pipeline, ProcessingPipeline):
        raise TypeError(
            "composition.pipeline must be a ProcessingPipeline."
        )
    if "ocr-metadata-extraction" not in pipeline.stage_ids:
        raise ValueError(
            "composition.pipeline must contain the advisory OCR metadata "
            "stage."
        )

    try:
        review_controller = composition.review_controller
    except AttributeError as exc:
        raise TypeError(
            "composition must expose a public review_controller attribute."
        ) from exc
    if not isinstance(
        review_controller,
        OCRReviewSessionController,
    ):
        raise TypeError(
            "composition.review_controller must be an "
            "OCRReviewSessionController."
        )
    return pipeline, review_controller


def _observation(
    value: object,
    *,
    report_index: int,
    item_index: int,
) -> OCRObservation:
    name = f"ocr_reports[{report_index}].observations[{item_index}]"
    payload = _mapping(value, name)
    result = OCRObservation(
        source_coin_id=_string(
            payload.get("source_coin_id"),
            f"{name}.source_coin_id",
        ),
        image_role=_string(
            payload.get("image_role"),
            f"{name}.image_role",
        ),
        artifact_key=_string(
            payload.get("artifact_key"),
            f"{name}.artifact_key",
        ),
        provider_id=_string(
            payload.get("provider_id"),
            f"{name}.provider_id",
        ),
        raw_text=_string(
            payload.get("raw_text"),
            f"{name}.raw_text",
        ),
        confidence_score=_number(
            payload.get("confidence_score"),
            f"{name}.confidence_score",
        ),
    )
    result.validate()
    return result


def _candidate(
    value: object,
    *,
    report_index: int,
    item_index: int,
) -> OCRFieldCandidate:
    name = f"ocr_reports[{report_index}].candidates[{item_index}]"
    payload = _mapping(value, name)
    evidence = _list(payload.get("evidence"), f"{name}.evidence")
    result = OCRFieldCandidate(
        source_coin_id=_string(
            payload.get("source_coin_id"),
            f"{name}.source_coin_id",
        ),
        image_role=_string(
            payload.get("image_role"),
            f"{name}.image_role",
        ),
        artifact_key=_string(
            payload.get("artifact_key"),
            f"{name}.artifact_key",
        ),
        provider_id=_string(
            payload.get("provider_id"),
            f"{name}.provider_id",
        ),
        field_name=_string(
            payload.get("field_name"),
            f"{name}.field_name",
        ),
        raw_text=_string(
            payload.get("raw_text"),
            f"{name}.raw_text",
        ),
        normalized_value=_string(
            payload.get("normalized_value"),
            f"{name}.normalized_value",
        ),
        confidence_score=_number(
            payload.get("confidence_score"),
            f"{name}.confidence_score",
        ),
        evidence=tuple(
            _string(item, f"{name}.evidence[{index}]")
            for index, item in enumerate(evidence)
        ),
        review_status=_status(
            payload.get("review_status"),
            f"{name}.review_status",
        ),
    )
    result.validate()
    return result


def _conflict(
    value: object,
    *,
    report_index: int,
    item_index: int,
) -> OCRConflict:
    name = f"ocr_reports[{report_index}].conflicts[{item_index}]"
    payload = _mapping(value, name)
    candidate_values = _list(
        payload.get("candidate_values"),
        f"{name}.candidate_values",
    )
    result = OCRConflict(
        source_coin_id=_string(
            payload.get("source_coin_id"),
            f"{name}.source_coin_id",
        ),
        field_name=_string(
            payload.get("field_name"),
            f"{name}.field_name",
        ),
        candidate_values=tuple(
            _string(item, f"{name}.candidate_values[{index}]")
            for index, item in enumerate(candidate_values)
        ),
        reason=_string(payload.get("reason"), f"{name}.reason"),
        review_status=_status(
            payload.get("review_status"),
            f"{name}.review_status",
        ),
    )
    result.validate()
    return result


def _report(value: object, *, report_index: int) -> OCRMetadataReport:
    name = f"ocr_reports[{report_index}]"
    payload = _mapping(value, name)
    observations = _list(
        payload.get("observations"),
        f"{name}.observations",
    )
    candidates = _list(
        payload.get("candidates"),
        f"{name}.candidates",
    )
    conflicts = _list(payload.get("conflicts"), f"{name}.conflicts")

    expected_counts = (
        (
            "observation_count",
            _integer(
                payload.get("observation_count"),
                f"{name}.observation_count",
            ),
            len(observations),
        ),
        (
            "candidate_count",
            _integer(
                payload.get("candidate_count"),
                f"{name}.candidate_count",
            ),
            len(candidates),
        ),
        (
            "conflict_count",
            _integer(
                payload.get("conflict_count"),
                f"{name}.conflict_count",
            ),
            len(conflicts),
        ),
    )
    for count_name, expected, actual in expected_counts:
        if expected != actual:
            raise ValueError(f"{name}.{count_name} does not match payload.")

    if not _boolean(
        payload.get("manual_review_required"),
        f"{name}.manual_review_required",
    ):
        raise ValueError(f"{name} must require manual review.")
    selected_variant = _string(
        payload.get("selected_variant"),
        f"{name}.selected_variant",
    )
    if selected_variant not in {"cropped", "normalized"}:
        raise ValueError(f"{name}.selected_variant is unsupported.")

    result = OCRMetadataReport(
        provider_available=_boolean(
            payload.get("provider_available"),
            f"{name}.provider_available",
        ),
        observations=tuple(
            _observation(
                item,
                report_index=report_index,
                item_index=index,
            )
            for index, item in enumerate(observations)
        ),
        candidates=tuple(
            _candidate(
                item,
                report_index=report_index,
                item_index=index,
            )
            for index, item in enumerate(candidates)
        ),
        conflicts=tuple(
            _conflict(
                item,
                report_index=report_index,
                item_index=index,
            )
            for index, item in enumerate(conflicts)
        ),
        review_status=_status(
            payload.get("review_status"),
            f"{name}.review_status",
        ),
    )
    result.validate()
    return result


def _aggregate_reports(
    reports: tuple[OCRMetadataReport, ...],
) -> OCRMetadataReport:
    observations = tuple(
        sorted(
            (
                item
                for report in reports
                for item in report.observations
            ),
            key=lambda item: (
                item.source_coin_id,
                item.image_role,
                item.artifact_key,
                item.provider_id,
                item.raw_text,
            ),
        )
    )
    candidates = tuple(
        sorted(
            (
                item
                for report in reports
                for item in report.candidates
            ),
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
    conflicts = tuple(
        sorted(
            (
                item
                for report in reports
                for item in report.conflicts
            ),
            key=lambda item: (
                item.source_coin_id,
                item.field_name,
                item.candidate_values,
            ),
        )
    )
    result = OCRMetadataReport(
        provider_available=True,
        observations=observations,
        candidates=candidates,
        conflicts=conflicts,
        review_status=(
            OCRReviewStatus.CONFLICT
            if conflicts
            else OCRReviewStatus.REVIEW_REQUIRED
        ),
    )
    result.validate()
    return result


def create_desktop_ocr_review_handoff(
    *,
    composition: object,
    outcome: PipelineOutcome,
) -> DesktopOCRReviewHandoff:
    """Decode one successful opt-in workflow outcome for desktop review."""

    _pipeline, review_controller = _composition_contract(composition)
    if not isinstance(outcome, PipelineOutcome):
        raise TypeError("outcome must be a PipelineOutcome.")

    metadata = outcome.metadata
    provider_available = _boolean(
        metadata.get("ocr_provider_available"),
        "ocr_provider_available",
    )
    if not _boolean(
        metadata.get("ocr_review_required"),
        "ocr_review_required",
    ):
        raise ValueError("OCR workflow output must require review.")

    report_values = _list(metadata.get("ocr_reports"), "ocr_reports")
    processed_count = _integer(
        metadata.get("ocr_processed_image_count"),
        "ocr_processed_image_count",
    )
    if processed_count != len(report_values):
        raise ValueError(
            "ocr_processed_image_count does not match ocr_reports."
        )

    if not provider_available:
        if report_values:
            raise ValueError(
                "Unavailable OCR provider cannot emit reports."
            )
        report = OCRMetadataReport(
            provider_available=False,
            review_status=OCRReviewStatus.UNAVAILABLE,
        )
    else:
        provider_id = _string(
            metadata.get("ocr_provider_id"),
            "ocr_provider_id",
        )
        if not provider_id.strip():
            raise ValueError("ocr_provider_id must not be empty.")
        reports = tuple(
            _report(value, report_index=index)
            for index, value in enumerate(report_values)
        )
        if not reports:
            raise ValueError(
                "Available OCR workflow output must contain reports."
            )
        if any(not report.provider_available for report in reports):
            raise ValueError(
                "Available OCR workflow output contains an unavailable "
                "report."
            )
        report = _aggregate_reports(reports)

    return DesktopOCRReviewHandoff(
        report=report,
        review_controller=review_controller,
    )
