"""Tests for OCR review-session persistence application coordination."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
import importlib
import inspect
from pathlib import Path
import tempfile
import unittest

from tests.frozen_dataclass_compat import (
    assert_frozen_slotted_assignment_rejected,
)

from capture_import.workflow_ocr_conflict_resolution import (
    OCRConflictResolutionDecision,
)
from capture_import.workflow_ocr_models import (
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRReviewStatus,
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
    CURRENT_OCR_REVIEW_SESSION_SCHEMA_VERSION,
    OCRReviewSessionEnvelope,
    OCRReviewSessionLifecycle,
    OCRReviewSessionReconstruction,
    OCRReviewSessionRepository,
    OCRStoredConflictResolution,
    UnsupportedOCRReviewSessionSchemaVersion,
)
from capture_import.workflow_ocr_review_persistence_service import (
    OCRReviewSessionNotResumableError,
    OCRReviewSessionPersistenceService,
    OCRReviewSessionPersistenceServiceError,
    OCRReviewSessionStaleSourceError,
)
from capture_import.workflow_ocr_review_service import OCRReviewMode
from capture_import.workflow_ocr_review_session import (
    OCRReviewSessionRequest,
    OCRReviewSessionResult,
    OCRReviewSessionService,
)


_FINGERPRINT = "a" * 64
_OTHER_FINGERPRINT = "b" * 64
_MODULE = "capture_import.workflow_ocr_review_persistence_service"


def _candidate(
    *,
    value: str,
    image_role: str,
    artifact_key: str,
) -> OCRFieldCandidate:
    return OCRFieldCandidate(
        source_coin_id="coin-1",
        image_role=image_role,
        artifact_key=artifact_key,
        provider_id="provider-1",
        field_name="year",
        raw_text=value,
        normalized_value=value,
        confidence_score=90.0,
        evidence=(f"{image_role} evidence",),
    )


def _review(candidate: OCRFieldCandidate) -> OCRFieldReview:
    return OCRFieldReview(
        source_coin_id=candidate.source_coin_id,
        image_role=candidate.image_role,
        artifact_key=candidate.artifact_key,
        provider_id=candidate.provider_id,
        field_name=candidate.field_name,
        original_value=candidate.normalized_value,
        decision=OCRReviewDecision.APPROVE,
        reviewed_value=candidate.normalized_value,
        reason=f"Reviewed {candidate.artifact_key}.",
    )


def _domain_inputs() -> tuple[
    OCRMetadataReport,
    OCRReportReview,
    tuple[OCRStoredConflictResolution, ...],
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
    candidates = tuple(
        sorted(
            (front, reverse),
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
    reviews = tuple(
        sorted(
            (_review(front), _review(reverse)),
            key=lambda item: item.identity_key,
        )
    )
    return (
        OCRMetadataReport(
            provider_available=True,
            candidates=candidates,
            review_status=OCRReviewStatus.REVIEW_REQUIRED,
        ),
        OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=reviews,
        ),
        (
            OCRStoredConflictResolution(
                source_coin_id="coin-1",
                field_name="year",
                decision=(
                    OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
                ),
                value="1967",
            ),
        ),
    )


class RecordingRepository:
    def __init__(self) -> None:
        self.items: dict[str, OCRReviewSessionEnvelope] = {}
        self.save_calls: list[OCRReviewSessionEnvelope] = []
        self.get_calls: list[str] = []
        self.exists_calls: list[str] = []
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
        self.exists_calls.append(session_id)
        return session_id in self.items


class RecordingSessionService(OCRReviewSessionService):
    def __init__(self) -> None:
        self.requests: list[OCRReviewSessionRequest] = []

    def run(
        self,
        *,
        request: OCRReviewSessionRequest,
    ) -> OCRReviewSessionResult:
        self.requests.append(request)
        return super().run(request=request)


def _service(
    *,
    repository: RecordingRepository | None = None,
    session_service: OCRReviewSessionService | None = None,
) -> tuple[
    OCRReviewSessionPersistenceService,
    RecordingRepository,
]:
    selected = RecordingRepository() if repository is None else repository
    return (
        OCRReviewSessionPersistenceService(
            selected,
            session_service=session_service,
        ),
        selected,
    )


def _create(
    service: OCRReviewSessionPersistenceService,
    *,
    session_id: str = "review-session-1",
    source_fingerprint: str = _FINGERPRINT,
    with_resolution: bool = True,
) -> OCRReviewSessionEnvelope:
    report, review, resolutions = _domain_inputs()
    return service.create_in_progress(
        session_id=session_id,
        source_fingerprint=source_fingerprint,
        source_report=report,
        report_review=review,
        review_mode=OCRReviewMode.PARTIAL,
        conflict_resolutions=(
            resolutions if with_resolution else ()
        ),
    )


class OCRReviewSessionPersistenceConstructionTests(unittest.TestCase):
    def test_repository_is_required(self) -> None:
        with self.assertRaises(TypeError):
            OCRReviewSessionPersistenceService()

    def test_invalid_repository_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "repository"):
            OCRReviewSessionPersistenceService(object())

    def test_runtime_protocol_repository_is_accepted(self) -> None:
        repository = RecordingRepository()

        service = OCRReviewSessionPersistenceService(repository)

        self.assertIsInstance(repository, OCRReviewSessionRepository)
        self.assertIs(service._repository, repository)

    def test_default_session_service_is_constructed(self) -> None:
        service, _repository = _service()

        self.assertIsInstance(
            service._session_service,
            OCRReviewSessionService,
        )

    def test_injected_session_service_is_preserved(self) -> None:
        session_service = RecordingSessionService()

        service, _repository = _service(
            session_service=session_service
        )

        self.assertIs(service._session_service, session_service)

    def test_invalid_session_service_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "session_service"):
            OCRReviewSessionPersistenceService(
                RecordingRepository(),
                session_service=object(),
            )

    def test_service_is_frozen_slotted_and_has_no_session_state(self) -> None:
        service, _repository = _service()

        with self.assertRaises(FrozenInstanceError):
            service._repository = RecordingRepository()
        with assert_frozen_slotted_assignment_rejected(self, service):
            service.current_session = "session"

    def test_construction_performs_no_repository_operations(self) -> None:
        service, repository = _service()

        self.assertIsNotNone(service)
        self.assertEqual(repository.save_calls, [])
        self.assertEqual(repository.get_calls, [])
        self.assertEqual(repository.exists_calls, [])


class OCRReviewSessionPersistenceCreateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service, self.repository = _service()

    def test_create_builds_valid_in_progress_envelope(self) -> None:
        envelope = _create(self.service)

        envelope.validate()
        self.assertEqual(
            envelope.schema_version,
            CURRENT_OCR_REVIEW_SESSION_SCHEMA_VERSION,
        )
        self.assertEqual(
            envelope.lifecycle_state,
            OCRReviewSessionLifecycle.IN_PROGRESS,
        )
        self.assertEqual(envelope.session_id, "review-session-1")
        self.assertEqual(envelope.source_fingerprint, _FINGERPRINT)
        self.assertEqual(envelope.review_mode, OCRReviewMode.PARTIAL)

    def test_create_preserves_domain_inputs(self) -> None:
        report, review, resolutions = _domain_inputs()

        envelope = self.service.create_in_progress(
            session_id="review-session-1",
            source_fingerprint=_FINGERPRINT,
            source_report=report,
            report_review=review,
            review_mode=OCRReviewMode.PARTIAL,
            conflict_resolutions=resolutions,
        )

        self.assertIs(envelope.source_report, report)
        self.assertIs(envelope.field_reviews, review.field_reviews)
        self.assertEqual(envelope.reviewer_id, review.reviewer_id)
        self.assertIs(envelope.conflict_resolutions, resolutions)

    def test_create_does_not_save_automatically(self) -> None:
        _create(self.service)

        self.assertEqual(self.repository.save_calls, [])

    def test_explicit_identity_and_fingerprint_are_validated(self) -> None:
        for session_id, fingerprint in (
            ("", _FINGERPRINT),
            ("review-session-1", ""),
            ("review-session-1", "A" * 64),
            ("review-session-1", "a" * 63),
        ):
            with self.subTest(
                session_id=session_id,
                fingerprint=fingerprint,
            ):
                with self.assertRaises(ValueError):
                    _create(
                        self.service,
                        session_id=session_id,
                        source_fingerprint=fingerprint,
                    )
        self.assertEqual(self.repository.save_calls, [])

    def test_report_review_must_use_existing_contract(self) -> None:
        report, _review_value, resolutions = _domain_inputs()

        with self.assertRaisesRegex(TypeError, "report_review"):
            self.service.create_in_progress(
                session_id="review-session-1",
                source_fingerprint=_FINGERPRINT,
                source_report=report,
                report_review=object(),
                review_mode=OCRReviewMode.PARTIAL,
                conflict_resolutions=resolutions,
            )

    def test_pre_first_review_limitation_is_preserved(self) -> None:
        report, _review_value, _resolutions = _domain_inputs()
        empty_review = OCRReportReview(
            reviewer_id="collector-1",
            field_reviews=(),
        )

        with self.assertRaisesRegex(ValueError, "at least one"):
            self.service.create_in_progress(
                session_id="review-session-1",
                source_fingerprint=_FINGERPRINT,
                source_report=report,
                report_review=empty_review,
                review_mode=OCRReviewMode.PARTIAL,
            )


class OCRReviewSessionPersistenceSaveLoadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_service = RecordingSessionService()
        self.service, self.repository = _service(
            session_service=self.session_service
        )

    def test_save_validates_and_delegates_exactly_once(self) -> None:
        envelope = _create(self.service)

        self.service.save(envelope)

        self.assertEqual(self.repository.save_calls, [envelope])
        self.assertGreaterEqual(len(self.session_service.requests), 1)

    def test_incomplete_in_progress_envelope_is_saveable(self) -> None:
        envelope = _create(self.service, with_resolution=False)

        self.service.save(envelope)

        self.assertEqual(self.repository.save_calls, [envelope])

    def test_incomplete_completed_envelope_is_rejected_before_save(
        self,
    ) -> None:
        envelope = _create(self.service, with_resolution=False)
        invalid = OCRReviewSessionEnvelope(
            schema_version=envelope.schema_version,
            session_id=envelope.session_id,
            source_fingerprint=envelope.source_fingerprint,
            lifecycle_state=OCRReviewSessionLifecycle.COMPLETED,
            review_mode=envelope.review_mode,
            reviewer_id=envelope.reviewer_id,
            source_report=envelope.source_report,
            field_reviews=envelope.field_reviews,
            conflict_resolutions=envelope.conflict_resolutions,
        )

        with self.assertRaisesRegex(ValueError, "complete"):
            self.service.save(invalid)
        self.assertEqual(self.repository.save_calls, [])

    def test_abandoned_envelope_is_saveable_for_audit(self) -> None:
        abandoned = self.service.abandon(
            _create(self.service, with_resolution=False)
        )

        self.service.save(abandoned)

        self.assertEqual(self.repository.save_calls, [abandoned])

    def test_load_delegates_once_without_reconstruction(self) -> None:
        envelope = _create(self.service)
        self.repository.items[envelope.session_id] = envelope

        loaded = self.service.load(envelope.session_id)

        self.assertIs(loaded, envelope)
        self.assertEqual(
            self.repository.get_calls,
            [envelope.session_id],
        )
        self.assertEqual(self.session_service.requests, [])

    def test_load_missing_returns_none(self) -> None:
        self.assertIsNone(self.service.load("missing"))
        self.assertEqual(self.repository.get_calls, ["missing"])

    def test_repository_write_error_propagates_unchanged(self) -> None:
        error = OCRReviewSessionWriteError("write failed")
        self.repository.save_error = error

        with self.assertRaises(OCRReviewSessionWriteError) as raised:
            self.service.save(_create(self.service))
        self.assertIs(raised.exception, error)

    def test_repository_corruption_error_propagates_unchanged(self) -> None:
        error = OCRReviewSessionCorruptError("corrupt")
        self.repository.get_error = error

        with self.assertRaises(OCRReviewSessionCorruptError) as raised:
            self.service.load("review-session-1")
        self.assertIs(raised.exception, error)

    def test_unsupported_schema_error_propagates_unchanged(self) -> None:
        error = UnsupportedOCRReviewSessionSchemaVersion("2.0")
        self.repository.get_error = error

        with self.assertRaises(
            UnsupportedOCRReviewSessionSchemaVersion
        ) as raised:
            self.service.load("review-session-1")
        self.assertIs(raised.exception, error)


class OCRReviewSessionPersistenceResumeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_service = RecordingSessionService()
        self.service, self.repository = _service(
            session_service=self.session_service
        )

    def test_matching_in_progress_session_reconstructs_real_inputs(
        self,
    ) -> None:
        envelope = _create(self.service)
        self.repository.items[envelope.session_id] = envelope

        reconstruction = self.service.load_for_resume(
            envelope.session_id,
            current_source_fingerprint=_FINGERPRINT,
        )

        self.assertIsInstance(
            reconstruction,
            OCRReviewSessionReconstruction,
        )
        self.assertIs(
            reconstruction.source_report,
            envelope.source_report,
        )
        self.assertEqual(
            reconstruction.review.field_reviews,
            envelope.field_reviews,
        )
        self.assertEqual(len(reconstruction.conflict_resolutions), 1)

    def test_stale_source_is_rejected_without_write_or_mutation(self) -> None:
        envelope = _create(self.service)
        self.repository.items[envelope.session_id] = envelope

        with self.assertRaises(OCRReviewSessionStaleSourceError):
            self.service.load_for_resume(
                envelope.session_id,
                current_source_fingerprint=_OTHER_FINGERPRINT,
            )

        self.assertEqual(self.repository.save_calls, [])
        self.assertIs(
            self.repository.items[envelope.session_id],
            envelope,
        )

    def test_invalid_current_fingerprint_is_caller_error(self) -> None:
        for fingerprint in (None, "", "A" * 64, "a" * 63, "z" * 64):
            with self.subTest(fingerprint=fingerprint):
                with self.assertRaises(ValueError):
                    self.service.load_for_resume(
                        "review-session-1",
                        current_source_fingerprint=fingerprint,
                    )
        self.assertEqual(self.repository.get_calls, [])

    def test_abandoned_and_completed_sessions_are_not_resumable(
        self,
    ) -> None:
        original = _create(self.service)
        for envelope in (
            self.service.abandon(original),
            self.service.complete(original),
        ):
            with self.subTest(lifecycle=envelope.lifecycle_state):
                self.repository.items[envelope.session_id] = envelope
                with self.assertRaises(
                    OCRReviewSessionNotResumableError
                ):
                    self.service.load_for_resume(
                        envelope.session_id,
                        current_source_fingerprint=_FINGERPRINT,
                    )

    def test_missing_session_returns_none_without_write(self) -> None:
        result = self.service.load_for_resume(
            "missing",
            current_source_fingerprint=_FINGERPRINT,
        )

        self.assertIsNone(result)
        self.assertEqual(self.repository.save_calls, [])
        self.assertEqual(self.session_service.requests, [])


class OCRReviewSessionPersistenceTransitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_service = RecordingSessionService()
        self.service, self.repository = _service(
            session_service=self.session_service
        )

    def test_complete_returns_new_valid_envelope_and_preserves_state(
        self,
    ) -> None:
        original = _create(self.service)

        completed = self.service.complete(original)

        self.assertIsNot(completed, original)
        self.assertEqual(
            original.lifecycle_state,
            OCRReviewSessionLifecycle.IN_PROGRESS,
        )
        self.assertEqual(
            completed.lifecycle_state,
            OCRReviewSessionLifecycle.COMPLETED,
        )
        for field_name in (
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
                getattr(completed, field_name),
                getattr(original, field_name),
            )
        self.assertGreaterEqual(len(self.session_service.requests), 1)
        self.assertEqual(self.repository.save_calls, [])

    def test_complete_rejects_incomplete_projection(self) -> None:
        original = _create(self.service, with_resolution=False)

        with self.assertRaisesRegex(ValueError, "complete"):
            self.service.complete(original)

        self.assertEqual(
            original.lifecycle_state,
            OCRReviewSessionLifecycle.IN_PROGRESS,
        )
        self.assertEqual(self.repository.save_calls, [])

    def test_completed_envelope_can_be_explicitly_saved_and_loaded(
        self,
    ) -> None:
        completed = self.service.complete(_create(self.service))

        self.service.save(completed)

        self.assertIs(self.service.load(completed.session_id), completed)

    def test_abandon_returns_new_envelope_and_preserves_all_state(
        self,
    ) -> None:
        original = _create(self.service, with_resolution=False)

        abandoned = self.service.abandon(original)

        self.assertIsNot(abandoned, original)
        self.assertEqual(
            original.lifecycle_state,
            OCRReviewSessionLifecycle.IN_PROGRESS,
        )
        self.assertEqual(
            abandoned.lifecycle_state,
            OCRReviewSessionLifecycle.ABANDONED,
        )
        self.assertEqual(
            abandoned.conflict_resolutions,
            original.conflict_resolutions,
        )
        self.assertIs(abandoned.source_report, original.source_report)
        self.assertIs(abandoned.field_reviews, original.field_reviews)
        self.assertEqual(self.repository.save_calls, [])

    def test_abandoned_envelope_can_be_explicitly_saved_and_loaded(
        self,
    ) -> None:
        abandoned = self.service.abandon(
            _create(self.service, with_resolution=False)
        )

        self.service.save(abandoned)

        self.assertIs(self.service.load(abandoned.session_id), abandoned)

    def test_terminal_envelopes_cannot_transition_again(self) -> None:
        original = _create(self.service)
        completed = self.service.complete(original)
        abandoned = self.service.abandon(original)

        for envelope, operation in (
            (completed, self.service.complete),
            (completed, self.service.abandon),
            (abandoned, self.service.complete),
            (abandoned, self.service.abandon),
        ):
            with self.subTest(
                lifecycle=envelope.lifecycle_state,
                operation=operation.__name__,
            ):
                with self.assertRaisesRegex(ValueError, "IN_PROGRESS"):
                    operation(envelope)


class OCRReviewSessionPersistenceIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "sessions"
        self.repository = LocalOCRReviewSessionRepository(self.root)
        self.service = OCRReviewSessionPersistenceService(
            self.repository
        )

    def test_create_save_load_and_resume_round_trip(self) -> None:
        envelope = _create(self.service)

        self.service.save(envelope)
        loaded = self.service.load(envelope.session_id)
        resumed = self.service.load_for_resume(
            envelope.session_id,
            current_source_fingerprint=_FINGERPRINT,
        )

        self.assertEqual(loaded, envelope)
        self.assertIsInstance(resumed, OCRReviewSessionReconstruction)
        self.assertEqual(resumed.source_report, envelope.source_report)
        self.assertEqual(
            resumed.review.field_reviews,
            envelope.field_reviews,
        )

    def test_complete_and_abandon_round_trip_without_auto_resume(
        self,
    ) -> None:
        completed = self.service.complete(
            _create(self.service, session_id="completed")
        )
        abandoned = self.service.abandon(
            _create(
                self.service,
                session_id="abandoned",
                with_resolution=False,
            )
        )

        self.service.save(completed)
        self.service.save(abandoned)

        self.assertEqual(self.service.load("completed"), completed)
        self.assertEqual(self.service.load("abandoned"), abandoned)
        for session_id in ("completed", "abandoned"):
            with self.assertRaises(
                OCRReviewSessionNotResumableError
            ):
                self.service.load_for_resume(
                    session_id,
                    current_source_fingerprint=_FINGERPRINT,
                )

    def test_stale_source_after_real_load_does_not_change_storage(
        self,
    ) -> None:
        envelope = _create(self.service)
        self.service.save(envelope)
        before = tuple(
            path.read_bytes()
            for path in self.root.iterdir()
        )

        with self.assertRaises(OCRReviewSessionStaleSourceError):
            self.service.load_for_resume(
                envelope.session_id,
                current_source_fingerprint=_OTHER_FINGERPRINT,
            )

        after = tuple(
            path.read_bytes()
            for path in self.root.iterdir()
        )
        self.assertEqual(after, before)
        self.assertEqual(self.service.load(envelope.session_id), envelope)


class OCRReviewSessionPersistenceArchitectureTests(unittest.TestCase):
    def test_import_boundary_excludes_side_effect_layers(self) -> None:
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
                "workflow_ocr_review_models",
                "workflow_ocr_review_persistence_models",
                "workflow_ocr_review_service",
                "workflow_ocr_review_session",
            },
        )

    def test_no_gui_filesystem_generation_or_collection_behavior(
        self,
    ) -> None:
        source = inspect.getsource(importlib.import_module(_MODULE))
        for fragment in (
            "tkinter",
            "desktop_ocr",
            "confirmed_observation",
            "pathlib",
            "hashlib",
            "open(",
            "getenv",
            "environ[",
            "uuid",
            "datetime",
            "timestamp",
            "OCRReviewPresenter",
            "OCRReviewCandidateView",
        ):
            self.assertNotIn(fragment, source)

    def test_public_method_set_is_narrow_and_has_no_combined_writes(
        self,
    ) -> None:
        methods = {
            name
            for name, value in vars(
                OCRReviewSessionPersistenceService
            ).items()
            if callable(value) and not name.startswith("_")
        }

        self.assertEqual(
            methods,
            {
                "create_in_progress",
                "save",
                "load",
                "load_for_resume",
                "complete",
                "abandon",
            },
        )
        for name in (
            "create_and_save",
            "complete_and_save",
            "abandon_and_save",
            "delete",
            "list",
        ):
            self.assertFalse(
                hasattr(OCRReviewSessionPersistenceService, name)
            )

    def test_exception_hierarchy_is_policy_specific(self) -> None:
        self.assertTrue(
            issubclass(
                OCRReviewSessionStaleSourceError,
                OCRReviewSessionPersistenceServiceError,
            )
        )
        self.assertTrue(
            issubclass(
                OCRReviewSessionNotResumableError,
                OCRReviewSessionPersistenceServiceError,
            )
        )


if __name__ == "__main__":
    unittest.main()
