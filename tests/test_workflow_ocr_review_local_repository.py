"""Tests for concrete local OCR review-session persistence."""

from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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
    OCRReviewSessionRepositoryError,
    OCRReviewSessionWriteError,
)
from capture_import.workflow_ocr_review_models import (
    OCRFieldReview,
    OCRReviewDecision,
)
from capture_import.workflow_ocr_review_persistence_models import (
    CURRENT_OCR_REVIEW_SESSION_SCHEMA_VERSION,
    OCRReviewSessionEnvelope,
    OCRReviewSessionLifecycle,
    OCRReviewSessionRepository,
    OCRStoredConflictResolution,
    UnsupportedOCRReviewSessionSchemaVersion,
)
from capture_import.workflow_ocr_review_service import OCRReviewMode


_FINGERPRINT = "a" * 64
_MODULE = "capture_import.workflow_ocr_review_local_repository"


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


def _field_review(candidate: OCRFieldCandidate) -> OCRFieldReview:
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


def _envelope(
    *,
    session_id: str = "review-session-1",
    lifecycle: OCRReviewSessionLifecycle = (
        OCRReviewSessionLifecycle.IN_PROGRESS
    ),
    reviewer_id: str = "collector-1",
    with_resolution: bool = True,
) -> OCRReviewSessionEnvelope:
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
            (_field_review(front), _field_review(reverse)),
            key=lambda item: item.identity_key,
        )
    )
    resolutions = (
        (
            OCRStoredConflictResolution(
                source_coin_id="coin-1",
                field_name="year",
                decision=(
                    OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
                ),
                value="1967",
            ),
        )
        if with_resolution
        else ()
    )
    return OCRReviewSessionEnvelope(
        schema_version=CURRENT_OCR_REVIEW_SESSION_SCHEMA_VERSION,
        session_id=session_id,
        source_fingerprint=_FINGERPRINT,
        lifecycle_state=lifecycle,
        review_mode=OCRReviewMode.PARTIAL,
        reviewer_id=reviewer_id,
        source_report=OCRMetadataReport(
            provider_available=True,
            candidates=candidates,
            review_status=OCRReviewStatus.REVIEW_REQUIRED,
        ),
        field_reviews=reviews,
        conflict_resolutions=resolutions,
    )


def _target(root: Path, session_id: str) -> Path:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return root / f"{digest}.json"


def _store_raw(root: Path, session_id: str, raw: bytes) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    target = _target(root, session_id)
    target.write_bytes(raw)
    return target


def _store_payload(
    root: Path,
    session_id: str,
    payload: object,
) -> Path:
    return _store_raw(
        root,
        session_id,
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8"),
    )


class LocalRepositoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "review-sessions"
        self.repository = LocalOCRReviewSessionRepository(self.root)


class LocalOCRReviewRepositoryConstructionTests(LocalRepositoryTestCase):
    def test_explicit_root_is_required(self) -> None:
        with self.assertRaises(TypeError):
            LocalOCRReviewSessionRepository()

    def test_constructor_performs_no_writes(self) -> None:
        self.assertFalse(self.root.exists())
        self.assertEqual(self.repository.root, self.root.absolute())

    def test_blank_or_non_text_root_is_rejected(self) -> None:
        for root in ("", " ", b"bytes"):
            with self.subTest(root=root):
                with self.assertRaises((TypeError, ValueError)):
                    LocalOCRReviewSessionRepository(root)

    def test_repository_is_protocol_compatible(self) -> None:
        self.assertIsInstance(
            self.repository,
            OCRReviewSessionRepository,
        )

    def test_repository_instances_remain_independent(self) -> None:
        other_root = Path(self.temporary.name) / "other"
        other = LocalOCRReviewSessionRepository(other_root)

        self.repository.save(_envelope())

        self.assertTrue(self.repository.exists("review-session-1"))
        self.assertFalse(other.exists("review-session-1"))
        self.assertFalse(other_root.exists())


class LocalOCRReviewRepositoryPathSafetyTests(LocalRepositoryTestCase):
    def test_invalid_session_ids_are_rejected_without_creating_root(
        self,
    ) -> None:
        invalid = (
            "",
            " ",
            ".",
            "..",
            "../escape",
            r"..\escape",
            "/absolute",
            r"\absolute",
            "C:escape",
            r"C:\escape",
            "x" * 257,
        )
        for session_id in invalid:
            with self.subTest(session_id=session_id):
                with self.assertRaises((TypeError, ValueError)):
                    self.repository.get(session_id)
                with self.assertRaises((TypeError, ValueError)):
                    self.repository.exists(session_id)
        self.assertFalse(self.root.exists())

    def test_invalid_envelope_session_id_is_rejected_before_write(
        self,
    ) -> None:
        for session_id in ("../escape", r"..\escape", "/absolute", "C:x"):
            with self.subTest(session_id=session_id):
                with self.assertRaises(ValueError):
                    self.repository.save(
                        replace(_envelope(), session_id=session_id)
                    )
        self.assertFalse(self.root.exists())

    def test_non_string_session_id_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            self.repository.get(123)

    def test_unicode_session_id_uses_contained_digest_filename(self) -> None:
        session_id = "séance-β-一"
        envelope = _envelope(session_id=session_id)

        self.repository.save(envelope)

        files = tuple(self.root.iterdir())
        self.assertEqual(files, (_target(self.root, session_id),))
        self.assertEqual(self.repository.get(session_id), envelope)
        self.assertEqual(
            self.repository.get(session_id).session_id,
            session_id,
        )

    def test_filename_mapping_is_deterministic_and_not_raw_identity(
        self,
    ) -> None:
        envelope = _envelope()

        self.repository.save(envelope)

        expected = _target(self.root, envelope.session_id)
        self.assertTrue(expected.is_file())
        self.assertNotIn(envelope.session_id, expected.name)
        self.assertEqual(expected.parent, self.root)


class LocalOCRReviewRepositoryRoundTripTests(LocalRepositoryTestCase):
    def test_save_get_and_exists_round_trip_full_envelope(self) -> None:
        envelope = _envelope()

        self.assertFalse(self.repository.exists(envelope.session_id))
        self.assertIsNone(self.repository.get(envelope.session_id))
        self.repository.save(envelope)

        self.assertTrue(self.repository.exists(envelope.session_id))
        self.assertEqual(self.repository.get(envelope.session_id), envelope)

    def test_root_is_created_lazily_on_first_save(self) -> None:
        self.assertFalse(self.root.exists())

        self.repository.save(_envelope())

        self.assertTrue(self.root.is_dir())

    def test_equivalent_envelopes_produce_identical_bytes(self) -> None:
        first_root = Path(self.temporary.name) / "first"
        second_root = Path(self.temporary.name) / "second"
        first = LocalOCRReviewSessionRepository(first_root)
        second = LocalOCRReviewSessionRepository(second_root)
        envelope = _envelope()

        first.save(envelope)
        second.save(
            replace(
                envelope,
                field_reviews=tuple(reversed(envelope.field_reviews)),
            )
        )

        self.assertEqual(
            _target(first_root, envelope.session_id).read_bytes(),
            _target(second_root, envelope.session_id).read_bytes(),
        )

    def test_serialized_bytes_are_canonical_utf8_without_bom(self) -> None:
        envelope = _envelope(reviewer_id="réviseur-一")

        self.repository.save(envelope)

        raw = _target(self.root, envelope.session_id).read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        self.assertIn("réviseur-一", raw.decode("utf-8"))
        self.assertEqual(
            raw,
            json.dumps(
                envelope.to_dict(),
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8"),
        )

    def test_all_lifecycle_states_round_trip(self) -> None:
        for lifecycle in OCRReviewSessionLifecycle:
            with self.subTest(lifecycle=lifecycle):
                session_id = f"session-{lifecycle.value}"
                envelope = _envelope(
                    session_id=session_id,
                    lifecycle=lifecycle,
                    with_resolution=(
                        lifecycle
                        is not OCRReviewSessionLifecycle.IN_PROGRESS
                    ),
                )
                self.repository.save(envelope)
                self.assertEqual(
                    self.repository.get(session_id),
                    envelope,
                )

    def test_unicode_nested_content_round_trips(self) -> None:
        envelope = _envelope(reviewer_id="collectionneur-é")
        unicode_reviews = tuple(
            replace(review, reason=f"{review.reason} Vérifié 一.")
            for review in envelope.field_reviews
        )
        envelope = replace(envelope, field_reviews=unicode_reviews)

        self.repository.save(envelope)

        self.assertEqual(self.repository.get(envelope.session_id), envelope)

    def test_second_save_atomically_replaces_first_document(self) -> None:
        first = _envelope(with_resolution=False)
        second = replace(
            _envelope(),
            lifecycle_state=OCRReviewSessionLifecycle.COMPLETED,
            reviewer_id="collector-2",
        )
        self.repository.save(first)

        self.repository.save(second)

        self.assertEqual(self.repository.get(first.session_id), second)
        self.assertEqual(
            len(tuple(self.root.glob("*.json"))),
            1,
        )
        self.assertEqual(tuple(self.root.glob("*.tmp")), ())

    def test_wrong_envelope_type_is_rejected_without_writes(self) -> None:
        with self.assertRaises(TypeError):
            self.repository.save(object())
        self.assertFalse(self.root.exists())


class LocalOCRReviewRepositoryCorruptionTests(LocalRepositoryTestCase):
    def _assert_corrupt_raw(self, raw: bytes) -> None:
        _store_raw(self.root, "review-session-1", raw)
        with self.assertRaises(OCRReviewSessionCorruptError):
            self.repository.get("review-session-1")

    def test_invalid_empty_truncated_and_non_object_json_are_corrupt(
        self,
    ) -> None:
        for raw in (b"not-json", b"", b'{"schema_version":', b"[]"):
            with self.subTest(raw=raw):
                self._assert_corrupt_raw(raw)

    def test_invalid_utf8_is_corrupt(self) -> None:
        self._assert_corrupt_raw(b"\xff\xfe")

    def test_duplicate_json_fields_are_corrupt(self) -> None:
        self._assert_corrupt_raw(
            b'{"schema_version":"1.0","schema_version":"1.0"}'
        )

    def test_missing_schema_version_is_corrupt(self) -> None:
        payload = _envelope().to_dict()
        del payload["schema_version"]
        _store_payload(self.root, "review-session-1", payload)

        with self.assertRaises(OCRReviewSessionCorruptError):
            self.repository.get("review-session-1")

    def test_unknown_top_level_field_is_corrupt(self) -> None:
        payload = _envelope().to_dict()
        payload["unexpected"] = True
        _store_payload(self.root, "review-session-1", payload)

        with self.assertRaises(OCRReviewSessionCorruptError):
            self.repository.get("review-session-1")

    def test_malformed_nested_report_is_corrupt(self) -> None:
        payload = _envelope().to_dict()
        payload["source_report"]["candidates"][0][
            "confidence_score"
        ] = "high"
        _store_payload(self.root, "review-session-1", payload)

        with self.assertRaises(OCRReviewSessionCorruptError):
            self.repository.get("review-session-1")

    def test_unsupported_schema_version_propagates_distinctly(self) -> None:
        payload = _envelope().to_dict()
        payload["schema_version"] = "2.0"
        _store_payload(self.root, "review-session-1", payload)

        with self.assertRaises(
            UnsupportedOCRReviewSessionSchemaVersion
        ):
            self.repository.get("review-session-1")

    def test_stored_session_id_must_match_requested_id(self) -> None:
        payload = _envelope(session_id="stored-id").to_dict()
        _store_payload(self.root, "requested-id", payload)

        with self.assertRaisesRegex(
            OCRReviewSessionCorruptError,
            "corrupt",
        ) as raised:
            self.repository.get("requested-id")
        self.assertIsInstance(raised.exception.__cause__, ValueError)

    def test_non_regular_target_is_not_treated_as_a_session(self) -> None:
        self.root.mkdir(parents=True)
        _target(self.root, "review-session-1").mkdir()

        with self.assertRaises(OCRReviewSessionCorruptError):
            self.repository.get("review-session-1")
        with self.assertRaises(OCRReviewSessionRepositoryError):
            self.repository.exists("review-session-1")

    def test_read_access_failure_is_not_treated_as_absence(self) -> None:
        envelope = _envelope()
        self.repository.save(envelope)

        with patch.object(
            Path,
            "open",
            side_effect=PermissionError("denied"),
        ):
            with self.assertRaises(
                OCRReviewSessionRepositoryError
            ) as raised:
                self.repository.get(envelope.session_id)
        self.assertIsInstance(raised.exception.__cause__, PermissionError)

    def test_exists_access_failure_is_not_treated_as_absence(self) -> None:
        with patch.object(
            Path,
            "lstat",
            side_effect=PermissionError("denied"),
        ):
            with self.assertRaises(
                OCRReviewSessionRepositoryError
            ) as raised:
                self.repository.exists("review-session-1")
        self.assertIsInstance(raised.exception.__cause__, PermissionError)


class LocalOCRReviewRepositoryAtomicityTests(LocalRepositoryTestCase):
    def test_success_uses_same_directory_temp_and_atomic_replace(self) -> None:
        repository_module = importlib.import_module(_MODULE)
        real_mkstemp = tempfile.mkstemp
        real_replace = os.replace
        with (
            patch.object(
                repository_module.tempfile,
                "mkstemp",
                wraps=real_mkstemp,
            ) as mkstemp,
            patch.object(
                repository_module.os,
                "replace",
                wraps=real_replace,
            ) as atomic_replace,
        ):
            self.repository.save(_envelope())

        self.assertEqual(
            Path(mkstemp.call_args.kwargs["dir"]),
            self.root,
        )
        source, destination = atomic_replace.call_args.args
        self.assertEqual(Path(source).parent, self.root)
        self.assertEqual(Path(destination).parent, self.root)
        self.assertEqual(tuple(self.root.glob("*.tmp")), ())

    def test_target_is_not_visible_before_first_replace(self) -> None:
        repository_module = importlib.import_module(_MODULE)
        envelope = _envelope()
        target = _target(self.root, envelope.session_id)
        real_replace = os.replace

        def checked_replace(source, destination):
            self.assertFalse(target.exists())
            real_replace(source, destination)

        with patch.object(
            repository_module.os,
            "replace",
            side_effect=checked_replace,
        ):
            self.repository.save(envelope)

        self.assertTrue(target.is_file())

    def test_temporary_creation_failure_leaves_no_target(self) -> None:
        repository_module = importlib.import_module(_MODULE)
        envelope = _envelope()
        with patch.object(
            repository_module.tempfile,
            "mkstemp",
            side_effect=OSError("temporary creation failed"),
        ):
            with self.assertRaises(
                OCRReviewSessionWriteError
            ) as raised:
                self.repository.save(envelope)

        self.assertIsInstance(raised.exception.__cause__, OSError)
        self.assertFalse(_target(self.root, envelope.session_id).exists())

    def test_temporary_write_failure_cleans_up_and_chains(self) -> None:
        repository_module = importlib.import_module(_MODULE)
        envelope = _envelope()
        with patch.object(
            repository_module,
            "_write_and_sync",
            side_effect=OSError("write failed"),
        ):
            with self.assertRaises(
                OCRReviewSessionWriteError
            ) as raised:
                self.repository.save(envelope)

        self.assertIsInstance(raised.exception.__cause__, OSError)
        self.assertFalse(_target(self.root, envelope.session_id).exists())
        self.assertEqual(tuple(self.root.glob("*.tmp")), ())

    def test_flush_failure_cleans_up_without_publishing(self) -> None:
        repository_module = importlib.import_module(_MODULE)
        envelope = _envelope()
        with patch.object(
            repository_module,
            "_flush_and_sync",
            side_effect=OSError("flush failed"),
        ):
            with self.assertRaises(OCRReviewSessionWriteError):
                self.repository.save(envelope)

        self.assertFalse(_target(self.root, envelope.session_id).exists())
        self.assertEqual(tuple(self.root.glob("*.tmp")), ())

    def test_fsync_failure_cleans_up_without_publishing(self) -> None:
        repository_module = importlib.import_module(_MODULE)
        envelope = _envelope()
        with patch.object(
            repository_module.os,
            "fsync",
            side_effect=OSError("fsync failed"),
        ):
            with self.assertRaises(OCRReviewSessionWriteError):
                self.repository.save(envelope)

        self.assertFalse(_target(self.root, envelope.session_id).exists())
        self.assertEqual(tuple(self.root.glob("*.tmp")), ())

    def test_replace_failure_preserves_old_target_and_cleans_temp(
        self,
    ) -> None:
        repository_module = importlib.import_module(_MODULE)
        original = _envelope(with_resolution=False)
        replacement = replace(
            _envelope(),
            reviewer_id="collector-2",
        )
        self.repository.save(original)
        target = _target(self.root, original.session_id)
        original_bytes = target.read_bytes()

        with (
            patch.object(
                repository_module.os,
                "replace",
                side_effect=OSError("replace failed"),
            ),
            patch.object(
                repository_module,
                "_remove_temporary",
                wraps=repository_module._remove_temporary,
            ) as cleanup,
        ):
            with self.assertRaises(
                OCRReviewSessionWriteError
            ) as raised:
                self.repository.save(replacement)

        self.assertIsInstance(raised.exception.__cause__, OSError)
        cleanup.assert_called_once()
        self.assertEqual(target.read_bytes(), original_bytes)
        self.assertEqual(self.repository.get(original.session_id), original)
        self.assertEqual(tuple(self.root.glob("*.tmp")), ())


class LocalOCRReviewRepositoryArchitectureTests(unittest.TestCase):
    def test_import_boundary_is_storage_only(self) -> None:
        module = importlib.import_module(_MODULE)
        tree = ast.parse(inspect.getsource(module))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module is not None
        }
        plain_imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }

        self.assertEqual(
            imports,
            {
                "__future__",
                "pathlib",
                "typing",
                "_json",
                "limits",
                "workflow_ocr_review_persistence_models",
            },
        )
        self.assertEqual(
            plain_imports,
            {"hashlib", "os", "stat", "tempfile"},
        )

    def test_no_out_of_scope_integration_or_generated_state(self) -> None:
        source = inspect.getsource(importlib.import_module(_MODULE))
        for fragment in (
            "tkinter",
            "desktop_ocr",
            "collection",
            "confirmed_observation",
            "sqlite",
            "getenv",
            "environ[",
            "uuid",
            "datetime",
            "timestamp",
        ):
            self.assertNotIn(fragment, source)

    def test_hashing_is_limited_to_filename_derivation(self) -> None:
        module = importlib.import_module(_MODULE)
        source = inspect.getsource(module)
        path_source = inspect.getsource(
            module.LocalOCRReviewSessionRepository._path
        )

        self.assertEqual(source.count("hashlib.sha256"), 1)
        self.assertIn("hashlib.sha256", path_source)
        self.assertNotIn("source_fingerprint", path_source)

    def test_constructor_has_no_default_root_or_global_instance(self) -> None:
        module = importlib.import_module(_MODULE)
        signature = inspect.signature(
            module.LocalOCRReviewSessionRepository
        )

        self.assertIs(
            signature.parameters["root"].default,
            inspect.Parameter.empty,
        )
        instances = [
            value
            for value in vars(module).values()
            if isinstance(value, LocalOCRReviewSessionRepository)
        ]
        self.assertEqual(instances, [])

    def test_repository_exposes_protocol_method_set_without_delete_or_list(
        self,
    ) -> None:
        methods = {
            name
            for name, value in vars(
                LocalOCRReviewSessionRepository
            ).items()
            if callable(value) and not name.startswith("_")
        }

        self.assertEqual(methods, {"save", "get", "exists"})
        self.assertFalse(
            hasattr(LocalOCRReviewSessionRepository, "delete")
        )
        self.assertFalse(
            hasattr(LocalOCRReviewSessionRepository, "list")
        )

    def test_exception_hierarchy_is_narrow(self) -> None:
        self.assertTrue(
            issubclass(
                OCRReviewSessionCorruptError,
                OCRReviewSessionRepositoryError,
            )
        )
        self.assertTrue(
            issubclass(
                OCRReviewSessionWriteError,
                OCRReviewSessionRepositoryError,
            )
        )


if __name__ == "__main__":
    unittest.main()
