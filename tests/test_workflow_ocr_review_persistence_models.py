"""Tests for versioned immutable OCR review-session persistence contracts."""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError
import importlib
import inspect
import json
import unittest

from capture_import.workflow_ocr_conflict_resolution import (
    OCRConflictResolutionDecision,
)
from capture_import.workflow_ocr_models import (
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRReviewStatus,
)
from capture_import.workflow_ocr_review_controller import (
    OCRReviewSessionController,
)
from capture_import.workflow_ocr_review_models import (
    OCRFieldReview,
    OCRReportReview,
    OCRReviewDecision,
)
from capture_import.workflow_ocr_review_persistence_models import (
    CURRENT_OCR_REVIEW_SESSION_SCHEMA_VERSION,
    OCRReviewSessionEnvelope,
    OCRReviewSessionLifecycle,
    OCRReviewSessionReconstruction,
    OCRReviewSessionRepository,
    OCRStoredConflictResolution,
    UnsupportedOCRReviewSessionSchemaVersion,
)
from capture_import.workflow_ocr_review_service import OCRReviewMode
from capture_import.workflow_ocr_review_session import OCRReviewSessionService


_FINGERPRINT = "a" * 64


def _candidate(
    *,
    value: str,
    image_role: str,
    artifact_key: str,
    field_name: str = "year",
) -> OCRFieldCandidate:
    return OCRFieldCandidate(
        source_coin_id="coin-1",
        image_role=image_role,
        artifact_key=artifact_key,
        provider_id="provider-1",
        field_name=field_name,
        raw_text=value,
        normalized_value=value,
        confidence_score=90.0,
        evidence=(f"{image_role} evidence",),
    )


def _report(
    *candidates: OCRFieldCandidate,
) -> OCRMetadataReport:
    return OCRMetadataReport(
        provider_available=True,
        candidates=tuple(
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
        ),
        review_status=OCRReviewStatus.REVIEW_REQUIRED,
    )


def _field_review(
    candidate: OCRFieldCandidate,
    *,
    decision: OCRReviewDecision = OCRReviewDecision.APPROVE,
    reviewed_value: str | None = None,
) -> OCRFieldReview:
    if decision is OCRReviewDecision.APPROVE and reviewed_value is None:
        reviewed_value = candidate.normalized_value
    return OCRFieldReview(
        source_coin_id=candidate.source_coin_id,
        image_role=candidate.image_role,
        artifact_key=candidate.artifact_key,
        provider_id=candidate.provider_id,
        field_name=candidate.field_name,
        original_value=candidate.normalized_value,
        decision=decision,
        reviewed_value=reviewed_value,
        reason=f"Reviewed {candidate.artifact_key}.",
    )


def _conflict_inputs() -> tuple[
    OCRMetadataReport,
    tuple[OCRFieldReview, ...],
]:
    front = _candidate(
        value="1967",
        image_role="front",
        artifact_key="year-front",
    )
    reverse = _candidate(
        value="1968",
        image_role="reverse",
        artifact_key="year-reverse",
    )
    return (
        _report(front, reverse),
        (_field_review(front), _field_review(reverse)),
    )


def _resolution(
    *,
    decision: OCRConflictResolutionDecision = (
        OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
    ),
    value: str | None = "1967",
    field_name: str = "year",
) -> OCRStoredConflictResolution:
    return OCRStoredConflictResolution(
        source_coin_id="coin-1",
        field_name=field_name,
        decision=decision,
        value=value,
    )


def _envelope(
    *,
    lifecycle: OCRReviewSessionLifecycle = (
        OCRReviewSessionLifecycle.IN_PROGRESS
    ),
    resolutions: tuple[OCRStoredConflictResolution, ...] = (),
    field_reviews: tuple[OCRFieldReview, ...] | None = None,
    report: OCRMetadataReport | None = None,
) -> OCRReviewSessionEnvelope:
    default_report, default_reviews = _conflict_inputs()
    return OCRReviewSessionEnvelope(
        schema_version=CURRENT_OCR_REVIEW_SESSION_SCHEMA_VERSION,
        session_id="review-session-1",
        source_fingerprint=_FINGERPRINT,
        lifecycle_state=lifecycle,
        review_mode=OCRReviewMode.PARTIAL,
        reviewer_id="collector-1",
        source_report=default_report if report is None else report,
        field_reviews=(
            default_reviews if field_reviews is None else field_reviews
        ),
        conflict_resolutions=resolutions,
    )


class OCRReviewSessionEnvelopeConstructionTests(unittest.TestCase):
    def test_current_schema_version_is_explicit(self) -> None:
        self.assertEqual(
            CURRENT_OCR_REVIEW_SESSION_SCHEMA_VERSION,
            "1.0",
        )

    def test_valid_in_progress_session(self) -> None:
        envelope = _envelope()

        envelope.validate()

        self.assertEqual(
            envelope.lifecycle_state,
            OCRReviewSessionLifecycle.IN_PROGRESS,
        )

    def test_valid_completed_session(self) -> None:
        envelope = _envelope(
            lifecycle=OCRReviewSessionLifecycle.COMPLETED,
            resolutions=(_resolution(),),
        )

        envelope.validate()
        envelope.validate_lifecycle(
            session_service=OCRReviewSessionService()
        )

    def test_valid_abandoned_session_preserves_audit_state(self) -> None:
        envelope = _envelope(
            lifecycle=OCRReviewSessionLifecycle.ABANDONED
        )

        envelope.validate()
        envelope.validate_lifecycle(
            session_service=OCRReviewSessionService()
        )
        with self.assertRaisesRegex(ValueError, "not resumable"):
            envelope.reconstruct(
                session_service=OCRReviewSessionService()
            )

    def test_envelope_is_frozen_and_slotted(self) -> None:
        envelope = _envelope()

        with self.assertRaises(FrozenInstanceError):
            envelope.session_id = "changed"
        with self.assertRaises(AttributeError):
            envelope.extra = "value"

    def test_blank_session_id_is_rejected(self) -> None:
        envelope = _envelope()
        invalid = OCRReviewSessionEnvelope(
            schema_version=envelope.schema_version,
            session_id=" ",
            source_fingerprint=envelope.source_fingerprint,
            lifecycle_state=envelope.lifecycle_state,
            review_mode=envelope.review_mode,
            reviewer_id=envelope.reviewer_id,
            source_report=envelope.source_report,
            field_reviews=envelope.field_reviews,
        )

        with self.assertRaisesRegex(ValueError, "session_id"):
            invalid.validate()

    def test_blank_or_malformed_source_fingerprint_is_rejected(self) -> None:
        envelope = _envelope()
        for fingerprint in ("", "A" * 64, "a" * 63, "z" * 64):
            with self.subTest(fingerprint=fingerprint):
                invalid = OCRReviewSessionEnvelope(
                    schema_version=envelope.schema_version,
                    session_id=envelope.session_id,
                    source_fingerprint=fingerprint,
                    lifecycle_state=envelope.lifecycle_state,
                    review_mode=envelope.review_mode,
                    reviewer_id=envelope.reviewer_id,
                    source_report=envelope.source_report,
                    field_reviews=envelope.field_reviews,
                )
                with self.assertRaises(ValueError):
                    invalid.validate()

    def test_reviewer_identity_is_required_and_opaque(self) -> None:
        envelope = _envelope()
        opaque = OCRReviewSessionEnvelope(
            schema_version=envelope.schema_version,
            session_id=envelope.session_id,
            source_fingerprint=envelope.source_fingerprint,
            lifecycle_state=envelope.lifecycle_state,
            review_mode=envelope.review_mode,
            reviewer_id="identity-provider://actor/42",
            source_report=envelope.source_report,
            field_reviews=envelope.field_reviews,
        )
        opaque.validate()

        invalid = OCRReviewSessionEnvelope(
            schema_version=envelope.schema_version,
            session_id=envelope.session_id,
            source_fingerprint=envelope.source_fingerprint,
            lifecycle_state=envelope.lifecycle_state,
            review_mode=envelope.review_mode,
            reviewer_id=" ",
            source_report=envelope.source_report,
            field_reviews=envelope.field_reviews,
        )
        with self.assertRaisesRegex(ValueError, "reviewer_id"):
            invalid.validate()


class OCRReviewSessionEnvelopeSerializationTests(unittest.TestCase):
    def test_canonical_serialized_shape(self) -> None:
        payload = _envelope(
            resolutions=(_resolution(),)
        ).to_dict()

        self.assertEqual(
            tuple(payload),
            (
                "schema_version",
                "session_id",
                "source_fingerprint",
                "lifecycle_state",
                "review_mode",
                "reviewer_id",
                "source_report",
                "field_reviews",
                "conflict_resolutions",
            ),
        )
        self.assertNotIn("metadata", payload)
        self.assertNotIn("presentation", payload)

    def test_enums_and_tuples_serialize_canonically(self) -> None:
        payload = _envelope(
            resolutions=(_resolution(),)
        ).to_dict()

        self.assertEqual(payload["lifecycle_state"], "IN_PROGRESS")
        self.assertEqual(payload["review_mode"], "PARTIAL")
        self.assertIsInstance(payload["field_reviews"], list)
        self.assertIsInstance(payload["conflict_resolutions"], list)
        self.assertEqual(
            payload["conflict_resolutions"][0]["decision"],
            "SELECT_EXISTING_VALUE",
        )

    def test_round_trip_is_exact_and_json_safe(self) -> None:
        original = _envelope(
            lifecycle=OCRReviewSessionLifecycle.COMPLETED,
            resolutions=(_resolution(),),
        )

        loaded = OCRReviewSessionEnvelope.from_dict(
            original.to_dict()
        )

        self.assertEqual(loaded, original)
        self.assertEqual(loaded.to_dict(), original.to_dict())
        json.dumps(loaded.to_dict(), sort_keys=True)

    def test_equivalent_inputs_serialize_identically(self) -> None:
        first = _envelope(resolutions=(_resolution(),))
        second = _envelope(
            resolutions=(_resolution(),),
            field_reviews=tuple(reversed(first.field_reviews)),
        )

        self.assertEqual(first.to_dict(), second.to_dict())

    def test_from_dict_does_not_mutate_input(self) -> None:
        payload = _envelope(
            resolutions=(_resolution(),)
        ).to_dict()
        before = deepcopy(payload)

        OCRReviewSessionEnvelope.from_dict(payload)

        self.assertEqual(payload, before)

    def test_missing_schema_version_is_malformed(self) -> None:
        payload = _envelope().to_dict()
        del payload["schema_version"]

        with self.assertRaisesRegex(ValueError, "missing fields"):
            OCRReviewSessionEnvelope.from_dict(payload)

    def test_unsupported_version_has_distinct_exception(self) -> None:
        payload = _envelope().to_dict()
        payload["schema_version"] = "2.0"

        with self.assertRaises(
            UnsupportedOCRReviewSessionSchemaVersion
        ):
            OCRReviewSessionEnvelope.from_dict(payload)

    def test_unknown_top_level_field_is_rejected(self) -> None:
        payload = _envelope().to_dict()
        payload["metadata"] = {"unexpected": True}

        with self.assertRaisesRegex(ValueError, "unknown fields"):
            OCRReviewSessionEnvelope.from_dict(payload)

    def test_missing_required_field_is_rejected(self) -> None:
        payload = _envelope().to_dict()
        del payload["source_fingerprint"]

        with self.assertRaisesRegex(ValueError, "source_fingerprint"):
            OCRReviewSessionEnvelope.from_dict(payload)

    def test_malformed_nested_report_is_rejected(self) -> None:
        payload = _envelope().to_dict()
        payload["source_report"]["candidates"][0][
            "confidence_score"
        ] = "high"

        with self.assertRaisesRegex(ValueError, "numeric"):
            OCRReviewSessionEnvelope.from_dict(payload)

    def test_unknown_nested_report_field_is_rejected(self) -> None:
        payload = _envelope().to_dict()
        payload["source_report"]["unexpected"] = True

        with self.assertRaisesRegex(ValueError, "unknown fields"):
            OCRReviewSessionEnvelope.from_dict(payload)

    def test_malformed_field_review_is_rejected(self) -> None:
        payload = _envelope().to_dict()
        payload["field_reviews"][0]["decision"] = "AUTOMATIC"

        with self.assertRaisesRegex(ValueError, "unsupported"):
            OCRReviewSessionEnvelope.from_dict(payload)

    def test_malformed_conflict_resolution_is_rejected(self) -> None:
        payload = _envelope(
            resolutions=(
                _resolution(
                    decision=(
                        OCRConflictResolutionDecision
                        .ENTER_CORRECTED_VALUE
                    ),
                    value="1969",
                ),
            )
        ).to_dict()
        payload["conflict_resolutions"][0]["value"] = ""

        with self.assertRaisesRegex(ValueError, "blank"):
            OCRReviewSessionEnvelope.from_dict(payload)


class OCRReviewSessionEnvelopeDomainTests(unittest.TestCase):
    def test_duplicate_stored_resolution_identity_is_rejected(self) -> None:
        envelope = _envelope(
            resolutions=(_resolution(), _resolution(value="1968"))
        )

        with self.assertRaisesRegex(ValueError, "Duplicate"):
            envelope.validate()

    def test_duplicate_field_review_is_rejected_by_existing_contract(
        self,
    ) -> None:
        report, reviews = _conflict_inputs()
        envelope = _envelope(
            report=report,
            field_reviews=(reviews[0], reviews[0]),
        )

        with self.assertRaisesRegex(ValueError, "Duplicate"):
            envelope.validate()

    def test_grade_in_source_report_is_rejected(self) -> None:
        grade = _candidate(
            value="MS-65",
            image_role="front",
            artifact_key="grade-front",
            field_name="grade",
        )
        report = _report(grade)
        review = _field_review(grade)
        envelope = _envelope(
            report=report,
            field_reviews=(review,),
        )

        with self.assertRaisesRegex(ValueError, "field_name"):
            envelope.validate()

    def test_grade_resolution_is_rejected(self) -> None:
        invalid = _resolution(field_name="grade")

        with self.assertRaisesRegex(ValueError, "field_name"):
            invalid.validate()

    def test_in_progress_session_may_remain_unresolved(self) -> None:
        envelope = _envelope()

        envelope.validate_lifecycle(
            session_service=OCRReviewSessionService()
        )

    def test_completed_session_requires_complete_projection(self) -> None:
        envelope = _envelope(
            lifecycle=OCRReviewSessionLifecycle.COMPLETED
        )

        with self.assertRaisesRegex(
            ValueError,
            "complete final projection",
        ):
            envelope.validate_lifecycle(
                session_service=OCRReviewSessionService()
            )

    def test_invalid_existing_resolution_is_rejected_by_sprint_10(
        self,
    ) -> None:
        envelope = _envelope(
            resolutions=(_resolution(value="1900"),)
        )

        with self.assertRaisesRegex(
            ValueError,
            "existing distinct value",
        ):
            envelope.reconstruct(
                session_service=OCRReviewSessionService()
            )

    def test_non_conflict_resolution_target_is_rejected(self) -> None:
        envelope = _envelope(
            resolutions=(
                _resolution(
                    field_name="country",
                    value="Canada",
                ),
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "does not target a current",
        ):
            envelope.reconstruct(
                session_service=OCRReviewSessionService()
            )

    def test_reconstruct_returns_exact_unit_1b_inputs(self) -> None:
        envelope = _envelope(resolutions=(_resolution(),))

        reconstructed = envelope.reconstruct(
            session_service=OCRReviewSessionService()
        )

        self.assertIsInstance(
            reconstructed,
            OCRReviewSessionReconstruction,
        )
        self.assertIs(reconstructed.source_report, envelope.source_report)
        self.assertEqual(
            reconstructed.review,
            OCRReportReview(
                reviewer_id=envelope.reviewer_id,
                field_reviews=envelope.field_reviews,
            ),
        )
        self.assertEqual(len(reconstructed.conflict_resolutions), 1)
        target = reconstructed.conflict_resolutions[0].field
        self.assertEqual(target.distinct_values, ("1967", "1968"))
        self.assertEqual(reconstructed.mode, OCRReviewMode.PARTIAL)

    def test_reconstruction_can_be_presented_by_unit_1b(self) -> None:
        envelope = _envelope(resolutions=(_resolution(),))
        reconstructed = envelope.reconstruct(
            session_service=OCRReviewSessionService()
        )

        state = OCRReviewSessionController().present_session(
            report=reconstructed.source_report,
            review=reconstructed.review,
            resolutions=reconstructed.conflict_resolutions,
            mode=reconstructed.mode,
        )

        self.assertTrue(state.session.is_complete)
        year = next(
            field
            for field in state.session.final_fields
            if field.field_name == "year"
        )
        self.assertEqual(year.final_value, "1967")


class OCRReviewSessionRepositoryContractTests(unittest.TestCase):
    def test_repository_is_runtime_checkable_protocol(self) -> None:
        class Repository:
            def save(self, envelope):
                return None

            def get(self, session_id):
                return None

            def exists(self, session_id):
                return False

        self.assertIsInstance(Repository(), OCRReviewSessionRepository)
        with self.assertRaises(TypeError):
            OCRReviewSessionRepository()

    def test_repository_has_minimal_exact_methods(self) -> None:
        methods = {
            name
            for name, value in vars(
                OCRReviewSessionRepository
            ).items()
            if callable(value) and not name.startswith("_")
        }

        self.assertEqual(methods, {"save", "get", "exists"})
        self.assertEqual(
            tuple(
                inspect.signature(
                    OCRReviewSessionRepository.save
                ).parameters
            ),
            ("self", "envelope"),
        )
        self.assertEqual(
            tuple(
                inspect.signature(
                    OCRReviewSessionRepository.get
                ).parameters
            ),
            ("self", "session_id"),
        )

    def test_no_concrete_repository_is_implemented(self) -> None:
        module = importlib.import_module(
            "capture_import.workflow_ocr_review_persistence_models"
        )
        repository_classes = [
            value
            for name, value in vars(module).items()
            if (
                inspect.isclass(value)
                and name.endswith("Repository")
            )
        ]

        self.assertEqual(
            repository_classes,
            [OCRReviewSessionRepository],
        )


class OCRReviewSessionPersistenceArchitectureTests(unittest.TestCase):
    def test_import_boundary_excludes_side_effect_layers(self) -> None:
        module = importlib.import_module(
            "capture_import.workflow_ocr_review_persistence_models"
        )
        source = inspect.getsource(module)
        tree = ast.parse(source)
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module is not None
        }
        self.assertEqual(
            imports,
            {
                "__future__",
                "collections.abc",
                "dataclasses",
                "enum",
                "typing",
                "capture_import.workflow_ocr_conflict_resolution",
                "capture_import.workflow_ocr_consolidation",
                "capture_import.workflow_ocr_models",
                "capture_import.workflow_ocr_review_models",
                "capture_import.workflow_ocr_review_service",
                "capture_import.workflow_ocr_review_session",
            },
        )

    def test_no_generation_filesystem_environment_or_gui_behavior(
        self,
    ) -> None:
        source = inspect.getsource(
            importlib.import_module(
                "capture_import.workflow_ocr_review_persistence_models"
            )
        )

        for fragment in (
            "uuid",
            "timestamp",
            "datetime",
            "getenv",
            "open(",
            "Path(",
            "Toplevel",
            "OCRReviewPresenter",
            "OCRReviewCandidateView",
        ):
            self.assertNotIn(fragment, source)

    def test_presentation_state_is_not_serialized(self) -> None:
        payload = _envelope(resolutions=(_resolution(),)).to_dict()
        serialized = json.dumps(payload, sort_keys=True)

        for field_name in (
            "field_label",
            "position_label",
            "confidence_label",
            "final_fields",
            "unresolved_fields",
            "is_complete",
        ):
            self.assertNotIn(field_name, serialized)


if __name__ == "__main__":
    unittest.main()
