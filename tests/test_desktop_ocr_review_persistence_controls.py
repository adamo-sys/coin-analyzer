"""Headless tests for explicit desktop OCR persistence controls."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
import importlib
import inspect
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from capture_import.desktop_ocr_candidate_review import (
    OCRCandidateReviewModel,
)
from capture_import.desktop_ocr_conflict_review import (
    OCRConflictReviewModel,
)
from capture_import.desktop_ocr_review_persistence import (
    DesktopOCRReviewPersistenceCoordinator,
)
from capture_import.desktop_ocr_review_persistence_controls import (
    DesktopOCRReviewPersistenceCommandResult,
    DesktopOCRReviewPersistenceControls,
    DesktopOCRReviewPersistenceControlsDisplay,
    DesktopOCRReviewPersistenceControlsModel,
    DesktopOCRReviewPersistenceErrorCategory,
    DesktopOCRReviewPersistenceOperation,
    DesktopOCRReviewPersistenceOutcome,
    DesktopOCRReviewSessionDraft,
    create_desktop_ocr_review_persistence_controls,
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
    OCRReviewSessionRepositoryError,
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
_MODULE = "capture_import.desktop_ocr_review_persistence_controls"


def _candidate(
    *,
    field_name: str,
    value: str,
    role: str,
    artifact: str,
) -> OCRFieldCandidate:
    return OCRFieldCandidate(
        source_coin_id="coin-1",
        image_role=role,
        artifact_key=artifact,
        provider_id=f"provider-{role}",
        field_name=field_name,
        raw_text=f"raw {value}",
        normalized_value=value,
        confidence_score=91.5,
        evidence=(f"{artifact} evidence",),
    )


def _report(
    candidates: tuple[OCRFieldCandidate, ...],
) -> OCRMetadataReport:
    result = OCRMetadataReport(
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
    result.validate()
    return result


def _review(
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
        decision, value = selected.get(
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
                reviewed_value=value,
                reason=f"Reviewed {candidate.artifact_key}.",
            )
        )
    result = OCRReportReview(
        reviewer_id="reviewer-1",
        field_reviews=tuple(
            sorted(reviews, key=lambda item: item.identity_key)
        ),
    )
    result.validate()
    return result


def _targeted_resolution(
    report: OCRMetadataReport,
    review: OCRReportReview,
) -> tuple[OCRReviewSessionConflictResolutionRequest, ...]:
    baseline = OCRReviewSessionService().run(
        request=OCRReviewSessionRequest(
            source_report=report,
            review=review,
            mode=OCRReviewMode.PARTIAL,
        )
    )
    target = next(
        field
        for field in baseline.consolidation.fields
        if field.status is OCRConsolidationStatus.CONFLICT
    )
    return (
        OCRReviewSessionConflictResolutionRequest(
            field=target,
            request=OCRConflictResolutionRequest(
                decision=(
                    OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
                ),
                value="1967",
            ),
        ),
    )


def _draft(
    *,
    session_id: str = "review-session-1",
    resolved: bool = True,
    fingerprint: str = _FINGERPRINT,
) -> DesktopOCRReviewSessionDraft:
    candidates = (
        _candidate(
            field_name="year",
            value="1967",
            role="front",
            artifact="year-front",
        ),
        _candidate(
            field_name="year",
            value="1968",
            role="reverse",
            artifact="year-reverse",
        ),
    )
    report = _report(candidates)
    review = _review(candidates)
    return DesktopOCRReviewSessionDraft(
        session_id=session_id,
        source_fingerprint=fingerprint,
        report=report,
        report_review=review,
        review_mode=OCRReviewMode.PARTIAL,
        conflict_resolutions=(
            _targeted_resolution(report, review) if resolved else ()
        ),
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


class RecordingCoordinator:
    """Public-contract recording wrapper around the real Unit 1D coordinator."""

    def __init__(
        self,
        delegate: DesktopOCRReviewPersistenceCoordinator,
    ) -> None:
        self.delegate = delegate
        self.create_calls = []
        self.save_calls = []
        self.resume_calls = []
        self.abandon_calls = []
        self.complete_calls = []

    def create_session(self, **kwargs):
        self.create_calls.append(kwargs)
        return self.delegate.create_session(**kwargs)

    def save_session(self, envelope):
        self.save_calls.append(envelope)
        return self.delegate.save_session(envelope)

    def load_for_resume(self, session_id, **kwargs):
        self.resume_calls.append((session_id, kwargs))
        return self.delegate.load_for_resume(session_id, **kwargs)

    def abandon_session(self, envelope):
        self.abandon_calls.append(envelope)
        return self.delegate.abandon_session(envelope)

    def complete_session(self, envelope):
        self.complete_calls.append(envelope)
        return self.delegate.complete_session(envelope)


class ErrorCoordinator:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def create_session(self, **kwargs):
        raise self.error

    def save_session(self, envelope):
        raise self.error

    def load_for_resume(self, session_id, **kwargs):
        raise self.error

    def abandon_session(self, envelope):
        raise self.error

    def complete_session(self, envelope):
        raise self.error


def _coordinator(
    repository: RecordingRepository | None = None,
) -> tuple[RecordingCoordinator, RecordingRepository]:
    selected = RecordingRepository() if repository is None else repository
    real = DesktopOCRReviewPersistenceCoordinator(
        persistence_service=OCRReviewSessionPersistenceService(selected),
        review_controller=OCRReviewSessionController(),
    )
    return RecordingCoordinator(real), selected


def _model(
    *,
    coordinator=None,
    state=None,
    applications=None,
    abandon=True,
    complete=True,
) -> DesktopOCRReviewPersistenceControlsModel:
    selected, _repository = _coordinator()
    applied = [] if applications is None else applications
    return DesktopOCRReviewPersistenceControlsModel(
        coordinator=selected if coordinator is None else coordinator,
        apply_resume=applied.append,
        confirm_abandon=lambda: abandon,
        confirm_complete=lambda: complete,
        current_state=state,
    )


def _save_draft(
    model: DesktopOCRReviewPersistenceControlsModel,
) -> OCRReviewSessionEnvelope:
    result = model.save()
    if result.envelope is None:
        raise AssertionError(result)
    return result.envelope


class PersistenceControlContractTests(unittest.TestCase):
    def test_construction_requires_explicit_dependencies(self) -> None:
        with self.assertRaises(TypeError):
            DesktopOCRReviewPersistenceControlsModel()

    def test_coordinator_public_contract_is_validated(self) -> None:
        with self.assertRaisesRegex(TypeError, "Unit 1D"):
            _model(coordinator=object())

    def test_callbacks_are_required_and_validated(self) -> None:
        coordinator, _repository = _coordinator()
        for name in (
            "apply_resume",
            "confirm_abandon",
            "confirm_complete",
        ):
            arguments = {
                "coordinator": coordinator,
                "apply_resume": lambda _state: None,
                "confirm_abandon": lambda: True,
                "confirm_complete": lambda: True,
            }
            arguments[name] = object()
            with self.subTest(name=name):
                with self.assertRaisesRegex(TypeError, name):
                    DesktopOCRReviewPersistenceControlsModel(**arguments)

    def test_construction_performs_no_repository_or_filesystem_work(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "sessions"
            coordinator = DesktopOCRReviewPersistenceCoordinator(
                persistence_service=OCRReviewSessionPersistenceService(
                    LocalOCRReviewSessionRepository(root)
                ),
                review_controller=OCRReviewSessionController(),
            )

            _model(coordinator=coordinator)

            self.assertFalse(root.exists())

    def test_draft_result_and_display_are_frozen_and_slotted(self) -> None:
        draft = _draft()
        result = DesktopOCRReviewPersistenceCommandResult(
            operation=DesktopOCRReviewPersistenceOperation.SAVE,
            outcome=DesktopOCRReviewPersistenceOutcome.FAILED,
            message="Failed.",
            error_category=(
                DesktopOCRReviewPersistenceErrorCategory.WRITE_FAILURE
            ),
        )
        display = _model(state=draft).display

        for value, name in (
            (draft, "session_id"),
            (result, "message"),
            (display, "save_available"),
        ):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, name, object())
                with self.assertRaises(AttributeError):
                    value.unexpected = object()

    def test_model_holds_only_explicit_ephemeral_state(self) -> None:
        draft = _draft()
        model = _model(state=draft)

        self.assertIs(model.current_state, draft)
        self.assertIsNone(model.current_envelope)
        self.assertIsNone(model.last_result)
        with self.assertRaises(AttributeError):
            model.autosave_queue = []

    def test_set_current_state_validates_before_replacing_state(self) -> None:
        draft = _draft()
        model = _model(state=draft)

        with self.assertRaises(TypeError):
            model.set_current_state(object())

        self.assertIs(model.current_state, draft)

    def test_control_availability_tracks_explicit_current_state(self) -> None:
        model = _model()
        self.assertEqual(
            (
                model.display.save_available,
                model.display.resume_available,
                model.display.abandon_available,
                model.display.complete_available,
            ),
            (False, True, False, False),
        )

        model.set_current_state(_draft())
        self.assertEqual(
            (
                model.display.save_available,
                model.display.resume_available,
                model.display.abandon_available,
                model.display.complete_available,
            ),
            (True, True, False, False),
        )

        _save_draft(model)
        self.assertEqual(
            (
                model.display.save_available,
                model.display.resume_available,
                model.display.abandon_available,
                model.display.complete_available,
            ),
            (True, True, True, True),
        )


class PersistenceControlSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.coordinator, self.repository = _coordinator()
        self.draft = _draft()
        self.model = _model(
            coordinator=self.coordinator,
            state=self.draft,
        )

    def test_create_and_save_delegates_exactly_once(self) -> None:
        result = self.model.save()

        self.assertEqual(
            result.outcome,
            DesktopOCRReviewPersistenceOutcome.SUCCESS,
        )
        self.assertEqual(len(self.coordinator.create_calls), 1)
        self.assertEqual(len(self.coordinator.save_calls), 1)
        self.assertIs(result.envelope, self.model.current_envelope)
        self.assertEqual(
            result.envelope.lifecycle_state,
            OCRReviewSessionLifecycle.IN_PROGRESS,
        )

    def test_save_existing_envelope_saves_that_exact_object(self) -> None:
        envelope = _save_draft(self.model)
        before_create = len(self.coordinator.create_calls)

        result = self.model.save()

        self.assertIs(result.envelope, envelope)
        self.assertEqual(len(self.coordinator.create_calls), before_create)
        self.assertIs(self.coordinator.save_calls[-1], envelope)

    def test_save_does_not_transition_lifecycle(self) -> None:
        result = self.model.save()

        self.assertEqual(
            result.envelope.lifecycle_state,
            OCRReviewSessionLifecycle.IN_PROGRESS,
        )
        self.assertEqual(self.coordinator.abandon_calls, [])
        self.assertEqual(self.coordinator.complete_calls, [])

    def test_missing_state_disables_save_and_returns_invalid_input(self) -> None:
        model = _model()

        result = model.save()

        self.assertFalse(model.display.save_available)
        self.assertEqual(
            result.error_category,
            DesktopOCRReviewPersistenceErrorCategory.INVALID_CALLER_INPUT,
        )

    def test_invalid_draft_save_preserves_prior_state(self) -> None:
        invalid = _draft(fingerprint="invalid")
        model = _model(
            coordinator=self.coordinator,
            state=invalid,
        )

        result = model.save()

        self.assertEqual(
            result.error_category,
            DesktopOCRReviewPersistenceErrorCategory.INVALID_CALLER_INPUT,
        )
        self.assertIs(model.current_state, invalid)
        self.assertEqual(self.coordinator.save_calls, [])

    def test_write_failure_preserves_draft_and_does_not_retry(self) -> None:
        self.repository.save_error = OCRReviewSessionWriteError("path detail")

        result = self.model.save()

        self.assertEqual(
            result.error_category,
            DesktopOCRReviewPersistenceErrorCategory.WRITE_FAILURE,
        )
        self.assertNotIn("path detail", result.message)
        self.assertIs(self.model.current_state, self.draft)
        self.assertEqual(len(self.repository.save_calls), 1)

    def test_repository_access_failure_is_distinct(self) -> None:
        model = _model(
            coordinator=ErrorCoordinator(
                OCRReviewSessionRepositoryError("private path")
            ),
            state=self.draft,
        )

        result = model.save()

        self.assertEqual(
            result.error_category,
            DesktopOCRReviewPersistenceErrorCategory.REPOSITORY_ACCESS,
        )
        self.assertNotIn("private path", result.message)


class PersistenceControlResumeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.coordinator, self.repository = _coordinator()
        source_model = _model(
            coordinator=self.coordinator,
            state=_draft(),
        )
        self.envelope = _save_draft(source_model)
        self.applications = []
        self.previous = _draft(session_id="current")
        self.model = _model(
            coordinator=self.coordinator,
            state=self.previous,
            applications=self.applications,
        )
        self.repository.save_calls.clear()
        self.coordinator.save_calls.clear()

    def test_valid_resume_applies_once_then_changes_current_state(self) -> None:
        result = self.model.resume(
            self.envelope.session_id,
            current_source_fingerprint=_FINGERPRINT,
        )

        self.assertEqual(
            result.outcome,
            DesktopOCRReviewPersistenceOutcome.SUCCESS,
        )
        self.assertEqual(self.applications, [result.resume_state])
        self.assertEqual(self.model.current_envelope, self.envelope)
        self.assertEqual(len(self.coordinator.resume_calls), 1)
        self.assertEqual(self.coordinator.save_calls, [])
        self.assertEqual(self.repository.save_calls, [])

    def test_missing_session_is_non_error_not_found(self) -> None:
        result = self.model.resume(
            "missing",
            current_source_fingerprint=_FINGERPRINT,
        )

        self.assertEqual(
            result.outcome,
            DesktopOCRReviewPersistenceOutcome.NOT_FOUND,
        )
        self.assertEqual(
            result.error_category,
            DesktopOCRReviewPersistenceErrorCategory.NOT_FOUND,
        )
        self.assertIs(self.model.current_state, self.previous)
        self.assertEqual(self.applications, [])

    def test_resume_error_categories_remain_distinct(self) -> None:
        cases = (
            (
                OCRReviewSessionStaleSourceError("stale"),
                DesktopOCRReviewPersistenceErrorCategory.STALE_SOURCE,
            ),
            (
                OCRReviewSessionNotResumableError(
                    "private non-resumable detail"
                ),
                DesktopOCRReviewPersistenceErrorCategory.NOT_RESUMABLE,
            ),
            (
                OCRReviewSessionCorruptError("private corrupt detail"),
                DesktopOCRReviewPersistenceErrorCategory.CORRUPT_DATA,
            ),
            (
                UnsupportedOCRReviewSessionSchemaVersion("future"),
                DesktopOCRReviewPersistenceErrorCategory.UNSUPPORTED_SCHEMA,
            ),
            (
                OCRReviewSessionRepositoryError("private repository path"),
                DesktopOCRReviewPersistenceErrorCategory.REPOSITORY_ACCESS,
            ),
        )
        for error, category in cases:
            with self.subTest(category=category):
                applications = []
                previous = _draft(session_id="previous")
                model = _model(
                    coordinator=ErrorCoordinator(error),
                    state=previous,
                    applications=applications,
                )

                result = model.resume(
                    "session",
                    current_source_fingerprint=_FINGERPRINT,
                )

                self.assertEqual(result.error_category, category)
                self.assertIs(model.current_state, previous)
                self.assertEqual(applications, [])
                self.assertNotIn(str(error), result.message)

    def test_invalid_fingerprint_does_not_apply_or_change_state(self) -> None:
        result = self.model.resume(
            self.envelope.session_id,
            current_source_fingerprint="invalid",
        )

        self.assertEqual(
            result.error_category,
            DesktopOCRReviewPersistenceErrorCategory.INVALID_CALLER_INPUT,
        )
        self.assertIs(self.model.current_state, self.previous)
        self.assertEqual(self.applications, [])

    def test_apply_resume_validation_failure_preserves_state(self) -> None:
        model = DesktopOCRReviewPersistenceControlsModel(
            coordinator=self.coordinator,
            apply_resume=lambda _state: (_ for _ in ()).throw(
                ValueError("Caller rejected resume.")
            ),
            confirm_abandon=lambda: True,
            confirm_complete=lambda: True,
            current_state=self.previous,
        )

        result = model.resume(
            self.envelope.session_id,
            current_source_fingerprint=_FINGERPRINT,
        )

        self.assertEqual(
            result.error_category,
            DesktopOCRReviewPersistenceErrorCategory.INVALID_CALLER_INPUT,
        )
        self.assertIs(model.current_state, self.previous)

    def test_unexpected_apply_resume_error_is_not_swallowed(self) -> None:
        model = DesktopOCRReviewPersistenceControlsModel(
            coordinator=self.coordinator,
            apply_resume=lambda _state: (_ for _ in ()).throw(
                RuntimeError("unexpected")
            ),
            confirm_abandon=lambda: True,
            confirm_complete=lambda: True,
            current_state=self.previous,
        )

        with self.assertRaisesRegex(RuntimeError, "unexpected"):
            model.resume(
                self.envelope.session_id,
                current_source_fingerprint=_FINGERPRINT,
            )

        self.assertIs(model.current_state, self.previous)


class PersistenceControlLifecycleTests(unittest.TestCase):
    def test_confirmation_must_return_boolean(self) -> None:
        coordinator, _repository = _coordinator()
        model = DesktopOCRReviewPersistenceControlsModel(
            coordinator=coordinator,
            apply_resume=lambda _state: None,
            confirm_abandon=lambda: "yes",
            confirm_complete=lambda: True,
            current_state=_draft(),
        )
        original = _save_draft(model)

        result = model.abandon_and_save()

        self.assertEqual(
            result.error_category,
            DesktopOCRReviewPersistenceErrorCategory.INVALID_CALLER_INPUT,
        )
        self.assertIs(model.current_envelope, original)
        self.assertEqual(coordinator.abandon_calls, [])

    def test_abandon_confirmation_declined_changes_nothing(self) -> None:
        coordinator, _repository = _coordinator()
        model = _model(
            coordinator=coordinator,
            state=_draft(),
            abandon=False,
        )
        original = _save_draft(model)

        result = model.abandon_and_save()

        self.assertEqual(
            result.outcome,
            DesktopOCRReviewPersistenceOutcome.CANCELLED,
        )
        self.assertIs(model.current_envelope, original)
        self.assertEqual(coordinator.abandon_calls, [])
        self.assertEqual(len(coordinator.save_calls), 1)

    def test_abandon_transitions_and_saves_once(self) -> None:
        coordinator, repository = _coordinator()
        model = _model(coordinator=coordinator, state=_draft())
        original = _save_draft(model)
        coordinator.save_calls.clear()
        repository.save_calls.clear()

        result = model.abandon_and_save()

        self.assertEqual(len(coordinator.abandon_calls), 1)
        self.assertEqual(len(coordinator.save_calls), 1)
        self.assertEqual(len(repository.save_calls), 1)
        self.assertIs(coordinator.abandon_calls[0], original)
        self.assertEqual(
            original.lifecycle_state,
            OCRReviewSessionLifecycle.IN_PROGRESS,
        )
        self.assertEqual(
            result.envelope.lifecycle_state,
            OCRReviewSessionLifecycle.ABANDONED,
        )
        self.assertIs(model.current_envelope, result.envelope)

    def test_abandon_save_failure_preserves_active_envelope(self) -> None:
        coordinator, repository = _coordinator()
        model = _model(coordinator=coordinator, state=_draft())
        original = _save_draft(model)
        repository.save_calls.clear()
        coordinator.save_calls.clear()
        repository.save_error = OCRReviewSessionWriteError("write")

        result = model.abandon_and_save()

        self.assertEqual(
            result.error_category,
            DesktopOCRReviewPersistenceErrorCategory.WRITE_FAILURE,
        )
        self.assertIs(model.current_envelope, original)
        self.assertEqual(len(coordinator.abandon_calls), 1)
        self.assertEqual(len(coordinator.save_calls), 1)
        self.assertEqual(len(repository.save_calls), 1)

    def test_complete_confirmation_declined_changes_nothing(self) -> None:
        coordinator, _repository = _coordinator()
        model = _model(
            coordinator=coordinator,
            state=_draft(),
            complete=False,
        )
        original = _save_draft(model)

        result = model.complete_and_save()

        self.assertEqual(
            result.outcome,
            DesktopOCRReviewPersistenceOutcome.CANCELLED,
        )
        self.assertIs(model.current_envelope, original)
        self.assertEqual(coordinator.complete_calls, [])

    def test_complete_transitions_and_saves_once(self) -> None:
        coordinator, repository = _coordinator()
        model = _model(coordinator=coordinator, state=_draft())
        original = _save_draft(model)
        coordinator.save_calls.clear()
        repository.save_calls.clear()

        result = model.complete_and_save()

        self.assertEqual(len(coordinator.complete_calls), 1)
        self.assertEqual(len(coordinator.save_calls), 1)
        self.assertEqual(len(repository.save_calls), 1)
        self.assertIs(coordinator.complete_calls[0], original)
        self.assertEqual(
            original.lifecycle_state,
            OCRReviewSessionLifecycle.IN_PROGRESS,
        )
        self.assertEqual(
            result.envelope.lifecycle_state,
            OCRReviewSessionLifecycle.COMPLETED,
        )

    def test_incomplete_projection_is_domain_validation_failure(self) -> None:
        coordinator, repository = _coordinator()
        model = _model(
            coordinator=coordinator,
            state=_draft(resolved=False),
        )
        original = _save_draft(model)
        coordinator.save_calls.clear()
        repository.save_calls.clear()

        result = model.complete_and_save()

        self.assertEqual(
            result.error_category,
            DesktopOCRReviewPersistenceErrorCategory.DOMAIN_VALIDATION,
        )
        self.assertIs(model.current_envelope, original)
        self.assertEqual(len(coordinator.complete_calls), 1)
        self.assertEqual(coordinator.save_calls, [])
        self.assertEqual(repository.save_calls, [])

    def test_complete_save_failure_preserves_active_envelope(self) -> None:
        coordinator, repository = _coordinator()
        model = _model(coordinator=coordinator, state=_draft())
        original = _save_draft(model)
        coordinator.save_calls.clear()
        repository.save_calls.clear()
        repository.save_error = OCRReviewSessionWriteError("write")

        result = model.complete_and_save()

        self.assertEqual(
            result.error_category,
            DesktopOCRReviewPersistenceErrorCategory.WRITE_FAILURE,
        )
        self.assertIs(model.current_envelope, original)
        self.assertEqual(len(coordinator.complete_calls), 1)
        self.assertEqual(len(coordinator.save_calls), 1)

    def test_terminal_control_availability_is_bounded(self) -> None:
        for operation in ("abandon", "complete"):
            with self.subTest(operation=operation):
                coordinator, _repository = _coordinator()
                model = _model(coordinator=coordinator, state=_draft())
                _save_draft(model)
                result = (
                    model.abandon_and_save()
                    if operation == "abandon"
                    else model.complete_and_save()
                )

                self.assertIsNotNone(result.envelope)
                self.assertFalse(model.display.save_available)
                self.assertTrue(model.display.resume_available)
                self.assertFalse(model.display.abandon_available)
                self.assertFalse(model.display.complete_available)


class PersistenceControlResumeHandoffTests(unittest.TestCase):
    def test_resumed_state_initializes_candidate_and_conflict_models(
        self,
    ) -> None:
        coordinator, _repository = _coordinator()
        source = _model(coordinator=coordinator, state=_draft())
        envelope = _save_draft(source)
        applied = []
        model = _model(
            coordinator=coordinator,
            applications=applied,
        )

        result = model.resume(
            envelope.session_id,
            current_source_fingerprint=_FINGERPRINT,
        )
        resumed = result.resume_state
        candidate_model = OCRCandidateReviewModel(
            report=resumed.report,
            review_controller=OCRReviewSessionController(),
            reviewer_id=resumed.report_review.reviewer_id,
            reviews=resumed.report_review.field_reviews,
            mode=resumed.review_mode,
        )
        conflict_model = OCRConflictReviewModel(
            report=resumed.report,
            review=resumed.report_review,
            review_controller=OCRReviewSessionController(),
            resolutions=resumed.conflict_resolutions,
            mode=resumed.review_mode,
        )

        self.assertEqual(applied, [resumed])
        self.assertEqual(
            candidate_model.reviews,
            resumed.report_review.field_reviews,
        )
        self.assertEqual(
            conflict_model.current_resolution.request.value,
            "1967",
        )
        self.assertTrue(conflict_model.display.is_complete)
        year = next(
            field
            for field in conflict_model.display.final_fields
            if field.field_name == "year"
        )
        self.assertEqual(year.final_value, "1967")
        self.assertTrue(year.is_resolved)

    def test_handoff_uses_only_public_model_apis(self) -> None:
        source = inspect.getsource(
            PersistenceControlResumeHandoffTests
            .test_resumed_state_initializes_candidate_and_conflict_models
        )
        self.assertNotIn("._", source)


class PersistenceControlRealRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "sessions"
        repository = LocalOCRReviewSessionRepository(self.root)
        self.coordinator = DesktopOCRReviewPersistenceCoordinator(
            persistence_service=OCRReviewSessionPersistenceService(
                repository
            ),
            review_controller=OCRReviewSessionController(),
        )

    def model(
        self,
        *,
        state=None,
        applications=None,
    ) -> DesktopOCRReviewPersistenceControlsModel:
        applied = [] if applications is None else applications
        return DesktopOCRReviewPersistenceControlsModel(
            coordinator=self.coordinator,
            apply_resume=applied.append,
            confirm_abandon=lambda: True,
            confirm_complete=lambda: True,
            current_state=state,
        )

    def test_save_resume_abandon_and_complete_round_trips(self) -> None:
        abandoned_model = self.model(
            state=_draft(session_id="abandoned")
        )
        _save_draft(abandoned_model)
        abandoned = abandoned_model.abandon_and_save().envelope

        completed_model = self.model(
            state=_draft(session_id="completed")
        )
        _save_draft(completed_model)
        completed = completed_model.complete_and_save().envelope

        active_model = self.model(state=_draft(session_id="active"))
        active = _save_draft(active_model)
        applications = []
        resumed = self.model(applications=applications).resume(
            active.session_id,
            current_source_fingerprint=_FINGERPRINT,
        )

        self.assertEqual(
            abandoned.lifecycle_state,
            OCRReviewSessionLifecycle.ABANDONED,
        )
        self.assertEqual(
            completed.lifecycle_state,
            OCRReviewSessionLifecycle.COMPLETED,
        )
        self.assertEqual(resumed.resume_state.envelope, active)
        self.assertEqual(applications, [resumed.resume_state])
        self.assertTrue(self.root.is_dir())
        self.assertEqual(len(tuple(self.root.iterdir())), 3)

    def test_terminal_sessions_are_not_resumable(self) -> None:
        for operation in ("abandon", "complete"):
            with self.subTest(operation=operation):
                model = self.model(
                    state=_draft(session_id=operation)
                )
                _save_draft(model)
                (
                    model.abandon_and_save()
                    if operation == "abandon"
                    else model.complete_and_save()
                )
                result = self.model().resume(
                    operation,
                    current_source_fingerprint=_FINGERPRINT,
                )
                self.assertEqual(
                    result.error_category,
                    DesktopOCRReviewPersistenceErrorCategory.NOT_RESUMABLE,
                )

    def test_stale_source_rejection_performs_no_write(self) -> None:
        model = self.model(state=_draft())
        envelope = _save_draft(model)
        before = tuple(
            (path.name, path.read_bytes())
            for path in self.root.iterdir()
        )

        result = self.model().resume(
            envelope.session_id,
            current_source_fingerprint=_STALE_FINGERPRINT,
        )

        self.assertEqual(
            result.error_category,
            DesktopOCRReviewPersistenceErrorCategory.STALE_SOURCE,
        )
        self.assertEqual(
            tuple(
                (path.name, path.read_bytes())
                for path in self.root.iterdir()
            ),
            before,
        )


class PersistenceControlSurfaceAndArchitectureTests(unittest.TestCase):
    def test_factory_wires_model_without_default_storage(self) -> None:
        coordinator, _repository = _coordinator()
        captured = {}
        sentinel = object()

        def construct(**kwargs):
            captured.update(kwargs)
            return sentinel

        with patch(
            f"{_MODULE}.DesktopOCRReviewPersistenceControls",
            side_effect=construct,
        ):
            result = create_desktop_ocr_review_persistence_controls(
                parent=object(),
                coordinator=coordinator,
                apply_resume=lambda _state: None,
                current_state=_draft(),
                confirm_abandon=lambda: False,
                confirm_complete=lambda: False,
            )

        self.assertIs(result, sentinel)
        self.assertIsInstance(
            captured["model"],
            DesktopOCRReviewPersistenceControlsModel,
        )
        self.assertIsNone(captured["model"].current_envelope)

    def test_thin_surface_commands_only_model_and_rerenders(self) -> None:
        calls = []

        class Model:
            def save(self):
                calls.append("save")

            def resume(self, session_id, *, current_source_fingerprint):
                calls.append(
                    ("resume", session_id, current_source_fingerprint)
                )

            def abandon_and_save(self):
                calls.append("abandon")

            def complete_and_save(self):
                calls.append("complete")

        class Variable:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        controls = DesktopOCRReviewPersistenceControls.__new__(
            DesktopOCRReviewPersistenceControls
        )
        controls._model = Model()
        controls._resume_session_id = Variable("session")
        controls._source_fingerprint = Variable(_FINGERPRINT)
        controls._render = lambda: calls.append("render")

        controls._save()
        controls._resume()
        controls._abandon()
        controls._complete()

        self.assertEqual(
            calls,
            [
                "save",
                "render",
                ("resume", "session", _FINGERPRINT),
                "render",
                "abandon",
                "render",
                "complete",
                "render",
            ],
        )

    def test_default_desktop_composition_remains_unchanged(self) -> None:
        source = inspect.getsource(
            importlib.import_module(
                "capture_import.desktop_ocr_review_composition"
            )
        )
        self.assertNotIn(
            "desktop_ocr_review_persistence_controls",
            source,
        )

    def test_import_boundary_has_no_out_of_scope_dependencies(self) -> None:
        module = importlib.import_module(_MODULE)
        tree = ast.parse(inspect.getsource(module))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        forbidden_fragments = (
            "collection",
            "confirmed_observation",
            "hashlib",
            "pathlib",
            "uuid",
            "datetime",
            "threading",
            "workflow_ocr_runtime",
            "desktop_ocr_review_composition",
        )
        self.assertFalse(
            any(
                fragment in imported
                for imported in imports
                for fragment in forbidden_fragments
            )
        )
        self.assertNotIn("os", imports)

    def test_no_serialization_autosave_listing_or_deletion(self) -> None:
        source = inspect.getsource(importlib.import_module(_MODULE))
        for fragment in (
            "json",
            "to_dict",
            "from_dict",
            "autosave",
            "save_periodically",
            "start_background",
            "list_sessions",
            "delete_session",
            "migrate",
        ):
            self.assertNotIn(fragment, source)

    def test_public_command_surface_is_bounded(self) -> None:
        public = {
            name
            for name, value in vars(
                DesktopOCRReviewPersistenceControlsModel
            ).items()
            if callable(value) and not name.startswith("_")
        }
        self.assertEqual(
            public,
            {
                "set_current_state",
                "save",
                "resume",
                "abandon_and_save",
                "complete_and_save",
            },
        )


if __name__ == "__main__":
    unittest.main()
