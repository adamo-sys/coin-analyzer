"""Headless tests for explicit desktop OCR review persistence."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
import importlib
import inspect
from pathlib import Path
import tempfile
import unittest

from capture_import.desktop_ocr_candidate_review import (
    OCRCandidateReviewModel,
    create_ocr_candidate_review_dialog,
)
from capture_import.desktop_ocr_conflict_review import (
    OCRConflictReviewModel,
)
from capture_import.desktop_ocr_review_persistence import (
    DesktopOCRReviewPersistenceCoordinator,
    DesktopOCRReviewResumeState,
    create_desktop_ocr_review_persistence_coordinator,
)
from capture_import.workflow_ocr_conflict_resolution import (
    OCRConflictResolutionDecision,
    OCRConflictResolutionRequest,
)
from capture_import.workflow_ocr_consolidation import (
    OCRConsolidationStatus,
)
from capture_import.workflow_ocr_models import (
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRReviewStatus,
)
from capture_import.workflow_ocr_review_controller import (
    OCRReviewSessionController,
)
from capture_import.workflow_ocr_review_local_repository import (
    LocalOCRReviewSessionRepository,
    OCRReviewSessionCorruptError,
    OCRReviewSessionWriteError,
)
from capture_import.workflow_ocr_review_models import (
    OCRFieldReview,
    OCRReportReview,
    OCRReviewDecision,
)
from capture_import.workflow_ocr_review_persistence_models import (
    OCRReviewSessionEnvelope,
    OCRReviewSessionLifecycle,
    OCRReviewSessionRepository,
    UnsupportedOCRReviewSessionSchemaVersion,
)
from capture_import.workflow_ocr_review_persistence_service import (
    OCRReviewSessionNotResumableError,
    OCRReviewSessionPersistenceService,
    OCRReviewSessionStaleSourceError,
)
from capture_import.workflow_ocr_review_service import OCRReviewMode
from capture_import.workflow_ocr_review_session import (
    OCRReviewSessionConflictResolutionRequest,
    OCRReviewSessionRequest,
    OCRReviewSessionService,
)


_FINGERPRINT = "a" * 64
_STALE_FINGERPRINT = "b" * 64
_MODULE = "capture_import.desktop_ocr_review_persistence"


def _candidate(
    *,
    field_name: str,
    value: str,
    image_role: str,
    artifact_key: str,
    provider_id: str | None = None,
) -> OCRFieldCandidate:
    return OCRFieldCandidate(
        source_coin_id="coin-1",
        image_role=image_role,
        artifact_key=artifact_key,
        provider_id=(
            f"provider-{image_role}"
            if provider_id is None
            else provider_id
        ),
        field_name=field_name,
        raw_text=f"raw {value}",
        normalized_value=value,
        confidence_score=90.0,
        evidence=(f"{artifact_key} evidence",),
    )


def _report(
    candidates: tuple[OCRFieldCandidate, ...],
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


def _report_review(
    candidates: tuple[OCRFieldCandidate, ...],
    *,
    decisions: dict[
        str,
        tuple[OCRReviewDecision, str | None],
    ] | None = None,
) -> OCRReportReview:
    selected = {} if decisions is None else decisions
    reviews = []
    for candidate in candidates:
        decision, reviewed_value = selected.get(
            candidate.artifact_key,
            (
                OCRReviewDecision.APPROVE,
                candidate.normalized_value,
            ),
        )
        reviews.append(
            OCRFieldReview(
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
        )
    return OCRReportReview(
        reviewer_id="reviewer-1",
        field_reviews=tuple(
            sorted(reviews, key=lambda item: item.identity_key)
        ),
    )


def _one_conflict() -> tuple[
    OCRMetadataReport,
    OCRReportReview,
    tuple[OCRReviewSessionConflictResolutionRequest, ...],
]:
    candidates = (
        _candidate(
            field_name="year",
            value="1967",
            image_role="front",
            artifact_key="year-front",
        ),
        _candidate(
            field_name="year",
            value="1968",
            image_role="reverse",
            artifact_key="year-reverse",
        ),
    )
    report = _report(candidates)
    review = _report_review(candidates)
    return (
        report,
        review,
        _targeted_resolutions(
            report,
            review,
            {
                (
                    "coin-1",
                    "year",
                ): (
                    OCRConflictResolutionDecision.SELECT_EXISTING_VALUE,
                    "1967",
                )
            },
        ),
    )


def _three_conflicts() -> tuple[
    OCRMetadataReport,
    OCRReportReview,
    tuple[OCRReviewSessionConflictResolutionRequest, ...],
]:
    candidates = (
        _candidate(
            field_name="year",
            value="1967",
            image_role="front",
            artifact_key="year-front",
        ),
        _candidate(
            field_name="year",
            value="1968",
            image_role="reverse",
            artifact_key="year-reverse",
        ),
        _candidate(
            field_name="country",
            value="Canada",
            image_role="front",
            artifact_key="country-front",
        ),
        _candidate(
            field_name="country",
            value="United States",
            image_role="reverse",
            artifact_key="country-reverse",
        ),
        _candidate(
            field_name="denomination",
            value="1 dollar",
            image_role="front",
            artifact_key="denomination-front",
        ),
        _candidate(
            field_name="denomination",
            value="2 dollars",
            image_role="reverse",
            artifact_key="denomination-reverse",
        ),
    )
    report = _report(candidates)
    review = _report_review(candidates)
    return (
        report,
        review,
        _targeted_resolutions(
            report,
            review,
            {
                (
                    "coin-1",
                    "year",
                ): (
                    OCRConflictResolutionDecision.SELECT_EXISTING_VALUE,
                    "1967",
                ),
                (
                    "coin-1",
                    "country",
                ): (
                    OCRConflictResolutionDecision.ENTER_CORRECTED_VALUE,
                    "Kanata",
                ),
                (
                    "coin-1",
                    "denomination",
                ): (
                    OCRConflictResolutionDecision.DEFER,
                    None,
                ),
            },
        ),
    )


def _targeted_resolutions(
    report: OCRMetadataReport,
    review: OCRReportReview,
    decisions: dict[
        tuple[str, str],
        tuple[OCRConflictResolutionDecision, str | None],
    ],
) -> tuple[OCRReviewSessionConflictResolutionRequest, ...]:
    baseline = OCRReviewSessionService().run(
        request=OCRReviewSessionRequest(
            source_report=report,
            review=review,
            mode=OCRReviewMode.PARTIAL,
        )
    )
    targets = {
        (field.source_coin_id, field.field_name): field
        for field in baseline.consolidation.fields
        if field.status is OCRConsolidationStatus.CONFLICT
    }
    return tuple(
        OCRReviewSessionConflictResolutionRequest(
            field=targets[identity],
            request=OCRConflictResolutionRequest(
                decision=decision,
                value=value,
            ),
        )
        for identity, (decision, value) in sorted(decisions.items())
    )


class RecordingRepository:
    def __init__(self) -> None:
        self.items: dict[str, OCRReviewSessionEnvelope] = {}
        self.save_calls: list[OCRReviewSessionEnvelope] = []
        self.get_calls: list[str] = []
        self.save_error: Exception | None = None
        self.get_error: Exception | None = None

    def save(self, envelope: OCRReviewSessionEnvelope) -> None:
        self.save_calls.append(envelope)
        if self.save_error is not None:
            raise self.save_error
        self.items[envelope.session_id] = envelope

    def get(
        self,
        session_id: str,
    ) -> OCRReviewSessionEnvelope | None:
        self.get_calls.append(session_id)
        if self.get_error is not None:
            raise self.get_error
        return self.items.get(session_id)

    def exists(self, session_id: str) -> bool:
        return session_id in self.items


class RecordingController(OCRReviewSessionController):
    def __init__(self) -> None:
        super().__init__()
        self.present_calls = []
        self.review_modes = []

    def present_session(self, **kwargs):
        self.present_calls.append(kwargs)
        return super().present_session(**kwargs)

    def apply_field_reviews(self, *, report, review, mode):
        self.review_modes.append(mode)
        return super().apply_field_reviews(
            report=report,
            review=review,
            mode=mode,
        )


def _coordinator(
    *,
    repository: RecordingRepository | None = None,
    controller: OCRReviewSessionController | None = None,
) -> tuple[
    DesktopOCRReviewPersistenceCoordinator,
    OCRReviewSessionPersistenceService,
    RecordingRepository,
    OCRReviewSessionController,
]:
    selected_repository = (
        RecordingRepository()
        if repository is None
        else repository
    )
    service = OCRReviewSessionPersistenceService(
        selected_repository
    )
    selected_controller = (
        RecordingController()
        if controller is None
        else controller
    )
    return (
        DesktopOCRReviewPersistenceCoordinator(
            persistence_service=service,
            review_controller=selected_controller,
        ),
        service,
        selected_repository,
        selected_controller,
    )


def _create(
    coordinator: DesktopOCRReviewPersistenceCoordinator,
    *,
    session_id: str = "review-session-1",
    with_resolution: bool = True,
) -> OCRReviewSessionEnvelope:
    report, review, resolutions = _one_conflict()
    return coordinator.create_session(
        session_id=session_id,
        source_fingerprint=_FINGERPRINT,
        report=report,
        report_review=review,
        review_mode=OCRReviewMode.PARTIAL,
        conflict_resolutions=(
            resolutions if with_resolution else ()
        ),
    )


class DesktopOCRReviewPersistenceConstructionTests(unittest.TestCase):
    def test_explicit_dependencies_are_required(self) -> None:
        with self.assertRaises(TypeError):
            DesktopOCRReviewPersistenceCoordinator()

    def test_invalid_dependencies_are_rejected(self) -> None:
        service = OCRReviewSessionPersistenceService(
            RecordingRepository()
        )
        with self.assertRaisesRegex(TypeError, "persistence_service"):
            DesktopOCRReviewPersistenceCoordinator(
                persistence_service=object(),
                review_controller=OCRReviewSessionController(),
            )
        with self.assertRaisesRegex(TypeError, "review_controller"):
            DesktopOCRReviewPersistenceCoordinator(
                persistence_service=service,
                review_controller=object(),
            )

    def test_factory_preserves_injected_dependencies(self) -> None:
        service = OCRReviewSessionPersistenceService(
            RecordingRepository()
        )
        controller = OCRReviewSessionController()

        coordinator = (
            create_desktop_ocr_review_persistence_coordinator(
                persistence_service=service,
                review_controller=controller,
            )
        )

        self.assertIs(coordinator.persistence_service, service)
        self.assertIs(coordinator.review_controller, controller)

    def test_coordinator_is_frozen_slotted_and_stateless(self) -> None:
        coordinator, _service, _repository, _controller = _coordinator()

        with self.assertRaises(FrozenInstanceError):
            coordinator.persistence_service = object()
        with self.assertRaises(AttributeError):
            coordinator.current_session = object()

    def test_construction_performs_no_repository_or_filesystem_work(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "sessions"
            repository = LocalOCRReviewSessionRepository(root)
            service = OCRReviewSessionPersistenceService(repository)

            create_desktop_ocr_review_persistence_coordinator(
                persistence_service=service,
                review_controller=OCRReviewSessionController(),
            )

            self.assertFalse(root.exists())


class DesktopOCRReviewPersistenceCreateSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        (
            self.coordinator,
            self.service,
            self.repository,
            self.controller,
        ) = _coordinator()

    def test_create_builds_in_progress_envelope_without_saving(self) -> None:
        report, review, resolutions = _one_conflict()

        envelope = self.coordinator.create_session(
            session_id="review-session-1",
            source_fingerprint=_FINGERPRINT,
            report=report,
            report_review=review,
            review_mode=OCRReviewMode.PARTIAL,
            conflict_resolutions=resolutions,
        )

        self.assertEqual(
            envelope.lifecycle_state,
            OCRReviewSessionLifecycle.IN_PROGRESS,
        )
        self.assertIs(envelope.source_report, report)
        self.assertIs(envelope.field_reviews, review.field_reviews)
        self.assertEqual(envelope.reviewer_id, review.reviewer_id)
        self.assertEqual(
            envelope.conflict_resolutions[0].decision,
            resolutions[0].request.decision,
        )
        self.assertEqual(self.repository.save_calls, [])

    def test_create_requires_first_field_review(self) -> None:
        report, _review, _resolutions = _one_conflict()

        with self.assertRaisesRegex(ValueError, "at least one"):
            self.coordinator.create_session(
                session_id="review-session-1",
                source_fingerprint=_FINGERPRINT,
                report=report,
                report_review=OCRReportReview(
                    reviewer_id="reviewer-1",
                    field_reviews=(),
                ),
                review_mode=OCRReviewMode.PARTIAL,
            )

    def test_create_does_not_mutate_inputs(self) -> None:
        report, review, resolutions = _one_conflict()
        before = (report, review, resolutions)

        self.coordinator.create_session(
            session_id="review-session-1",
            source_fingerprint=_FINGERPRINT,
            report=report,
            report_review=review,
            review_mode=OCRReviewMode.PARTIAL,
            conflict_resolutions=resolutions,
        )

        self.assertEqual((report, review, resolutions), before)

    def test_explicit_save_delegates_once_and_returns_same_envelope(
        self,
    ) -> None:
        envelope = _create(self.coordinator)

        saved = self.coordinator.save_session(envelope)

        self.assertIs(saved, envelope)
        self.assertEqual(self.repository.save_calls, [envelope])

    def test_save_error_propagates_unchanged(self) -> None:
        error = OCRReviewSessionWriteError("write failed")
        self.repository.save_error = error

        with self.assertRaises(OCRReviewSessionWriteError) as raised:
            self.coordinator.save_session(_create(self.coordinator))

        self.assertIs(raised.exception, error)


class DesktopOCRReviewPersistenceResumeTests(unittest.TestCase):
    def setUp(self) -> None:
        (
            self.coordinator,
            self.service,
            self.repository,
            self.controller,
        ) = _coordinator()

    def test_missing_session_returns_none_without_write(self) -> None:
        result = self.coordinator.load_for_resume(
            "missing",
            current_source_fingerprint=_FINGERPRINT,
        )

        self.assertIsNone(result)
        self.assertEqual(self.repository.get_calls, ["missing"])
        self.assertEqual(self.repository.save_calls, [])

    def test_valid_session_returns_bounded_immutable_resume_state(
        self,
    ) -> None:
        envelope = _create(self.coordinator)
        self.coordinator.save_session(envelope)

        resumed = self.coordinator.load_for_resume(
            envelope.session_id,
            current_source_fingerprint=_FINGERPRINT,
        )

        self.assertIsInstance(resumed, DesktopOCRReviewResumeState)
        self.assertEqual(resumed.envelope, envelope)
        self.assertEqual(resumed.report, envelope.source_report)
        self.assertEqual(
            resumed.report_review.field_reviews,
            envelope.field_reviews,
        )
        self.assertEqual(resumed.review_mode, envelope.review_mode)
        self.assertEqual(len(resumed.conflict_resolutions), 1)
        self.assertIsNotNone(resumed.controller_state.session)
        self.assertEqual(len(self.controller.present_calls), 1)
        self.assertEqual(self.repository.save_calls, [envelope])

        with self.assertRaises(FrozenInstanceError):
            resumed.report = object()

    def test_stale_source_propagates_without_write(self) -> None:
        envelope = _create(self.coordinator)
        self.coordinator.save_session(envelope)
        before = list(self.repository.save_calls)

        with self.assertRaises(OCRReviewSessionStaleSourceError):
            self.coordinator.load_for_resume(
                envelope.session_id,
                current_source_fingerprint=_STALE_FINGERPRINT,
            )

        self.assertEqual(self.repository.save_calls, before)
        self.assertEqual(self.controller.present_calls, [])

    def test_completed_and_abandoned_are_not_resumable(self) -> None:
        completed = self.coordinator.complete_session(
            _create(self.coordinator, session_id="completed")
        )
        abandoned = self.coordinator.abandon_session(
            _create(
                self.coordinator,
                session_id="abandoned",
                with_resolution=False,
            )
        )
        for envelope in (completed, abandoned):
            self.coordinator.save_session(envelope)
            with self.subTest(lifecycle=envelope.lifecycle_state):
                with self.assertRaises(
                    OCRReviewSessionNotResumableError
                ):
                    self.coordinator.load_for_resume(
                        envelope.session_id,
                        current_source_fingerprint=_FINGERPRINT,
                    )

    def test_repository_load_errors_propagate_unchanged(self) -> None:
        for error in (
            OCRReviewSessionCorruptError("corrupt"),
            UnsupportedOCRReviewSessionSchemaVersion("future"),
        ):
            with self.subTest(error=type(error).__name__):
                self.repository.get_error = error
                with self.assertRaises(type(error)) as raised:
                    self.coordinator.load_for_resume(
                        "review-session-1",
                        current_source_fingerprint=_FINGERPRINT,
                    )
                self.assertIs(raised.exception, error)


class DesktopOCRReviewPersistenceCandidateIntegrationTests(
    unittest.TestCase
):
    def test_resumed_decisions_initialize_candidate_model(self) -> None:
        candidates = (
            _candidate(
                field_name="year",
                value="1967",
                image_role="front",
                artifact_key="approve",
            ),
            _candidate(
                field_name="country",
                value="Canada",
                image_role="reverse",
                artifact_key="correct",
            ),
            _candidate(
                field_name="denomination",
                value="1 dollar",
                image_role="front",
                artifact_key="reject",
            ),
            _candidate(
                field_name="monarch",
                value="Elizabeth II",
                image_role="reverse",
                artifact_key="defer",
            ),
        )
        report = _report(candidates)
        review = _report_review(
            candidates,
            decisions={
                "approve": (
                    OCRReviewDecision.APPROVE,
                    "1967",
                ),
                "correct": (
                    OCRReviewDecision.CORRECT,
                    "Kanata",
                ),
                "reject": (
                    OCRReviewDecision.REJECT,
                    None,
                ),
                "defer": (
                    OCRReviewDecision.DEFER,
                    None,
                ),
            },
        )
        coordinator, _service, _repository, _controller = _coordinator()
        envelope = coordinator.create_session(
            session_id="candidate-decisions",
            source_fingerprint=_FINGERPRINT,
            report=report,
            report_review=review,
            review_mode=OCRReviewMode.PARTIAL,
        )
        coordinator.save_session(envelope)
        resumed = coordinator.load_for_resume(
            envelope.session_id,
            current_source_fingerprint=_FINGERPRINT,
        )

        model = OCRCandidateReviewModel(
            report=resumed.report,
            review_controller=OCRReviewSessionController(),
            reviewer_id=resumed.report_review.reviewer_id,
            reviews=resumed.report_review.field_reviews,
            mode=resumed.review_mode,
        )

        self.assertEqual(resumed.review_mode, OCRReviewMode.PARTIAL)
        observed = {}
        ordered_identities = []
        while True:
            candidate = model.current_candidate
            review_value = model.current_review
            ordered_identities.append(
                (
                    candidate.source_coin_id,
                    candidate.field_name,
                    candidate.artifact_key,
                )
            )
            observed[candidate.artifact_key] = (
                review_value.decision,
                review_value.reviewed_value,
                candidate.human_review_state,
                candidate.provider_id,
                candidate.image_role,
                candidate.evidence,
            )
            if not model.next_candidate():
                break

        self.assertEqual(
            observed["approve"][:3],
            (
                OCRReviewDecision.APPROVE,
                "1967",
                "APPROVE",
            ),
        )
        self.assertEqual(
            observed["correct"][:3],
            (
                OCRReviewDecision.CORRECT,
                "Kanata",
                "CORRECT",
            ),
        )
        self.assertEqual(
            observed["reject"][:3],
            (
                OCRReviewDecision.REJECT,
                None,
                "REJECT",
            ),
        )
        self.assertEqual(
            observed["defer"][:3],
            (
                OCRReviewDecision.DEFER,
                None,
                "DEFER",
            ),
        )
        expected_order = [
            (
                candidate.source_coin_id,
                candidate.field_name,
                candidate.artifact_key,
            )
            for candidate in resumed.controller_state.candidates
        ]
        self.assertEqual(ordered_identities, expected_order)
        self.assertEqual(
            observed["approve"][3:],
            (
                "provider-front",
                "front",
                ("approve evidence",),
            ),
        )

    def test_strict_resume_mode_initializes_candidate_model(self) -> None:
        report, review, resolutions = _one_conflict()
        coordinator, _service, _repository, _controller = _coordinator()
        envelope = coordinator.create_session(
            session_id="strict-candidates",
            source_fingerprint=_FINGERPRINT,
            report=report,
            report_review=review,
            review_mode=OCRReviewMode.STRICT_COMPLETE,
            conflict_resolutions=resolutions,
        )
        coordinator.save_session(envelope)
        resumed = coordinator.load_for_resume(
            envelope.session_id,
            current_source_fingerprint=_FINGERPRINT,
        )
        controller = RecordingController()

        OCRCandidateReviewModel(
            report=resumed.report,
            review_controller=controller,
            reviewer_id=resumed.report_review.reviewer_id,
            reviews=resumed.report_review.field_reviews,
            mode=resumed.review_mode,
        )

        self.assertEqual(
            controller.review_modes,
            [OCRReviewMode.STRICT_COMPLETE],
        )

    def test_candidate_model_rejects_unknown_persisted_review(
        self,
    ) -> None:
        report, review, _resolutions = _one_conflict()
        unknown = OCRFieldReview(
            source_coin_id="coin-invented",
            image_role="front",
            artifact_key="invented",
            provider_id="provider-front",
            field_name="year",
            original_value="1900",
            decision=OCRReviewDecision.APPROVE,
            reviewed_value="1900",
            reason="Invented.",
        )

        with self.assertRaisesRegex(ValueError, "does not target"):
            OCRCandidateReviewModel(
                report=report,
                review_controller=OCRReviewSessionController(),
                reviewer_id=review.reviewer_id,
                reviews=(unknown,),
            )

    def test_candidate_dialog_factory_exposes_initial_reviews_seam(
        self,
    ) -> None:
        self.assertIn(
            "reviews",
            inspect.signature(
                create_ocr_candidate_review_dialog
            ).parameters,
        )
        self.assertIn(
            "mode",
            inspect.signature(
                create_ocr_candidate_review_dialog
            ).parameters,
        )


class DesktopOCRReviewPersistenceConflictIntegrationTests(
    unittest.TestCase
):
    def test_resumed_resolutions_initialize_conflict_model(self) -> None:
        report, review, resolutions = _three_conflicts()
        coordinator, _service, _repository, _controller = _coordinator()
        envelope = coordinator.create_session(
            session_id="conflict-decisions",
            source_fingerprint=_FINGERPRINT,
            report=report,
            report_review=review,
            review_mode=OCRReviewMode.PARTIAL,
            conflict_resolutions=resolutions,
        )
        coordinator.save_session(envelope)
        resumed = coordinator.load_for_resume(
            envelope.session_id,
            current_source_fingerprint=_FINGERPRINT,
        )

        model = OCRConflictReviewModel(
            report=resumed.report,
            review=resumed.report_review,
            review_controller=OCRReviewSessionController(),
            resolutions=resumed.conflict_resolutions,
            mode=resumed.review_mode,
        )

        observed = {}
        while True:
            conflict = model.current_conflict
            resolution = model.current_resolution
            observed[conflict.field_name] = (
                resolution.request.decision,
                resolution.request.value,
                conflict.selected_or_corrected_value,
                conflict.is_deferred,
                conflict.is_unresolved,
            )
            if not model.next_conflict():
                break

        self.assertEqual(
            observed["year"][:3],
            (
                OCRConflictResolutionDecision.SELECT_EXISTING_VALUE,
                "1967",
                "1967",
            ),
        )
        self.assertEqual(
            observed["country"][:3],
            (
                OCRConflictResolutionDecision.ENTER_CORRECTED_VALUE,
                "Kanata",
                "Kanata",
            ),
        )
        self.assertEqual(
            observed["denomination"][0:2],
            (
                OCRConflictResolutionDecision.DEFER,
                None,
            ),
        )
        self.assertTrue(observed["denomination"][3])
        self.assertTrue(observed["denomination"][4])
        self.assertFalse(model.display.is_complete)
        self.assertEqual(model.display.unresolved_field_count, 1)
        self.assertEqual(
            {
                field.field_name
                for field in model.display.unresolved_fields
            },
            {"denomination"},
        )
        finals = {
            field.field_name: field.final_value
            for field in model.display.final_fields
        }
        self.assertEqual(finals["year"], "1967")
        self.assertEqual(finals["country"], "Kanata")


class DesktopOCRReviewPersistenceLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        (
            self.coordinator,
            self.service,
            self.repository,
            self.controller,
        ) = _coordinator()

    def test_abandon_is_immutable_and_does_not_save_or_delete(self) -> None:
        original = _create(self.coordinator, with_resolution=False)

        abandoned = self.coordinator.abandon_session(original)

        self.assertIsNot(abandoned, original)
        self.assertEqual(
            original.lifecycle_state,
            OCRReviewSessionLifecycle.IN_PROGRESS,
        )
        self.assertEqual(
            abandoned.lifecycle_state,
            OCRReviewSessionLifecycle.ABANDONED,
        )
        self.assertIs(abandoned.source_report, original.source_report)
        self.assertIs(abandoned.field_reviews, original.field_reviews)
        self.assertEqual(self.repository.save_calls, [])

    def test_complete_is_immutable_and_requires_domain_completion(
        self,
    ) -> None:
        original = _create(self.coordinator)

        completed = self.coordinator.complete_session(original)

        self.assertIsNot(completed, original)
        self.assertEqual(
            original.lifecycle_state,
            OCRReviewSessionLifecycle.IN_PROGRESS,
        )
        self.assertEqual(
            completed.lifecycle_state,
            OCRReviewSessionLifecycle.COMPLETED,
        )
        for name in (
            "schema_version",
            "session_id",
            "source_fingerprint",
            "review_mode",
            "reviewer_id",
            "source_report",
            "field_reviews",
            "conflict_resolutions",
        ):
            self.assertIs(
                getattr(completed, name),
                getattr(original, name),
            )
        self.assertEqual(self.repository.save_calls, [])

    def test_incomplete_completion_is_rejected_without_save(self) -> None:
        original = _create(self.coordinator, with_resolution=False)

        with self.assertRaisesRegex(ValueError, "complete"):
            self.coordinator.complete_session(original)

        self.assertEqual(self.repository.save_calls, [])

    def test_explicit_save_persists_transitioned_envelope(self) -> None:
        abandoned = self.coordinator.abandon_session(
            _create(self.coordinator, with_resolution=False)
        )

        self.coordinator.save_session(abandoned)

        self.assertIs(
            self.service.load(abandoned.session_id),
            abandoned,
        )

    def test_terminal_transition_rejection_propagates(self) -> None:
        completed = self.coordinator.complete_session(
            _create(self.coordinator)
        )

        with self.assertRaisesRegex(ValueError, "IN_PROGRESS"):
            self.coordinator.abandon_session(completed)


class DesktopOCRReviewPersistenceRealRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "sessions"
        self.repository = LocalOCRReviewSessionRepository(self.root)
        self.service = OCRReviewSessionPersistenceService(
            self.repository
        )
        self.coordinator = DesktopOCRReviewPersistenceCoordinator(
            persistence_service=self.service,
            review_controller=OCRReviewSessionController(),
        )

    def test_create_save_and_resume_round_trip(self) -> None:
        envelope = _create(self.coordinator)

        self.coordinator.save_session(envelope)
        resumed = self.coordinator.load_for_resume(
            envelope.session_id,
            current_source_fingerprint=_FINGERPRINT,
        )

        self.assertEqual(resumed.envelope, envelope)
        self.assertEqual(resumed.report, envelope.source_report)

    def test_abandon_and_complete_explicit_save_round_trip(self) -> None:
        abandoned = self.coordinator.abandon_session(
            _create(
                self.coordinator,
                session_id="abandoned",
                with_resolution=False,
            )
        )
        completed = self.coordinator.complete_session(
            _create(
                self.coordinator,
                session_id="completed",
            )
        )

        self.coordinator.save_session(abandoned)
        self.coordinator.save_session(completed)

        self.assertEqual(self.service.load("abandoned"), abandoned)
        self.assertEqual(self.service.load("completed"), completed)

    def test_stale_source_rejection_does_not_change_repository(self) -> None:
        envelope = _create(self.coordinator)
        self.coordinator.save_session(envelope)
        before = tuple(
            path.read_bytes()
            for path in self.root.iterdir()
        )

        with self.assertRaises(OCRReviewSessionStaleSourceError):
            self.coordinator.load_for_resume(
                envelope.session_id,
                current_source_fingerprint=_STALE_FINGERPRINT,
            )

        self.assertEqual(
            tuple(path.read_bytes() for path in self.root.iterdir()),
            before,
        )


class DesktopOCRReviewPersistenceArchitectureTests(unittest.TestCase):
    def test_import_boundary_is_headless_and_storage_agnostic(self) -> None:
        module = importlib.import_module(_MODULE)
        tree = ast.parse(inspect.getsource(module))
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
                "dataclasses",
                "workflow_ocr_models",
                "workflow_ocr_review_controller",
                "workflow_ocr_review_models",
                "workflow_ocr_review_persistence_models",
                "workflow_ocr_review_persistence_service",
                "workflow_ocr_review_service",
                "workflow_ocr_review_session",
            },
        )

    def test_no_serialization_gui_ocr_or_out_of_scope_behavior(self) -> None:
        source = inspect.getsource(importlib.import_module(_MODULE))
        for fragment in (
            "json",
            "to_dict",
            "from_dict",
            "tkinter",
            "desktop_ocr_candidate",
            "desktop_ocr_conflict",
            "collection",
            "confirmed_observation",
            "getenv",
            "environ[",
            "hashlib",
            "Path(",
            "uuid",
            "datetime",
            "timestamp",
            "threading",
            "autosave",
        ):
            self.assertNotIn(fragment, source)

    def test_default_desktop_composition_remains_unchanged(self) -> None:
        composition = importlib.import_module(
            "capture_import.desktop_ocr_review_composition"
        )
        source = inspect.getsource(composition)

        self.assertNotIn(
            "desktop_ocr_review_persistence",
            source,
        )
        self.assertNotIn(
            "persistence_service",
            inspect.signature(
                composition.create_desktop_ocr_review_composition
            ).parameters,
        )

    def test_coordinator_method_set_has_no_automatic_persistence(
        self,
    ) -> None:
        methods = {
            name
            for name, value in vars(
                DesktopOCRReviewPersistenceCoordinator
            ).items()
            if callable(value) and not name.startswith("_")
        }

        self.assertEqual(
            methods,
            {
                "create_session",
                "save_session",
                "load_for_resume",
                "abandon_session",
                "complete_session",
            },
        )
        for name in (
            "autosave",
            "save_periodically",
            "start_background",
            "delete",
            "list",
        ):
            self.assertFalse(
                hasattr(
                    DesktopOCRReviewPersistenceCoordinator,
                    name,
                )
            )


if __name__ == "__main__":
    unittest.main()
