"""Sprint 9 Unit 1F legacy OCR runtime-factory tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from capture_import.workflow_execution import ImportWorkflow
from capture_import.workflow_models import ImportConfiguration, ImportRequest
from capture_import.workflow_ocr_runtime import build_legacy_ocr_pipeline
from capture_import.workflow_stages import build_image_processing_pipeline
from tests.capture_package_fixtures import package_bytes


_EXPECTED_DEFAULT_STAGE_IDS = (
    "package-validation",
    "manifest-preparation",
    "image-normalization",
    "image-quality-scoring",
    "crop-detection",
    "obverse-reverse-pairing",
    "image-duplicate-detection",
)

_EXPECTED_OCR_STAGE_IDS = (
    "package-validation",
    "manifest-preparation",
    "image-normalization",
    "image-quality-scoring",
    "crop-detection",
    "ocr-metadata-extraction",
    "obverse-reverse-pairing",
    "image-duplicate-detection",
)


class LegacyOCRRuntimeFactoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)

        self.root = Path(self.temporary.name)
        self.source = self.root / "fixture.ca-package"
        self.source.write_bytes(package_bytes())

        self.request = ImportRequest(
            source=self.source,
            collection_id="collection-1",
            configuration=ImportConfiguration(),
        )

    def _workspace(self, name: str) -> Path:
        workspace = self.root / name
        workspace.mkdir()
        return workspace

    def test_factory_builds_expected_opt_in_pipeline(self) -> None:
        pipeline = build_legacy_ocr_pipeline(
            raw_text_resolver=lambda *_args: "CANADA 1967"
        )

        self.assertEqual(
            pipeline.stage_ids,
            _EXPECTED_OCR_STAGE_IDS,
        )

    def test_default_pipeline_remains_unchanged(self) -> None:
        self.assertEqual(
            build_image_processing_pipeline().stage_ids,
            _EXPECTED_DEFAULT_STAGE_IDS,
        )
        self.assertNotIn(
            "ocr-metadata-extraction",
            build_image_processing_pipeline().stage_ids,
        )

    def test_deterministic_resolver_executes_real_legacy_provider(self) -> None:
        resolver_calls: list[tuple[str, str, str, bytes]] = []

        def resolver(
            source_coin_id: str,
            image_role: str,
            artifact_key: str,
            image_bytes: bytes,
        ) -> str:
            resolver_calls.append(
                (
                    source_coin_id,
                    image_role,
                    artifact_key,
                    image_bytes,
                )
            )
            return "CANADA 1967"

        outcome = ImportWorkflow(
            build_legacy_ocr_pipeline(raw_text_resolver=resolver)
        ).execute(
            self.request,
            self._workspace("resolver-workspace"),
        )

        self.assertEqual(len(resolver_calls), 2)
        self.assertEqual(
            [
                (coin_id, role, artifact_key)
                for coin_id, role, artifact_key, _image_bytes
                in resolver_calls
            ],
            [
                ("coin-1", "front", "cropped-coin-1-front"),
                ("coin-1", "reverse", "cropped-coin-1-reverse"),
            ],
        )
        self.assertTrue(
            all(image_bytes for *_, image_bytes in resolver_calls)
        )

        self.assertTrue(outcome.metadata["ocr_provider_available"])
        self.assertEqual(
            outcome.metadata["ocr_provider_id"],
            "legacy-ocr",
        )
        self.assertEqual(
            outcome.metadata["ocr_processed_image_count"],
            2,
        )
        self.assertTrue(outcome.metadata["ocr_review_required"])

    def test_resolver_path_does_not_use_local_ocr_runtime(self) -> None:
        with patch(
            "ocr_experiment.OCRExperiment._run_local_ocr",
            side_effect=AssertionError(
                "local OCR runtime must not be called"
            ),
        ):
            outcome = ImportWorkflow(
                build_legacy_ocr_pipeline(
                    raw_text_resolver=lambda *_args: "CANADA 1967"
                )
            ).execute(
                self.request,
                self._workspace("no-local-runtime-workspace"),
            )

        self.assertEqual(
            outcome.metadata["ocr_provider_id"],
            "legacy-ocr",
        )
        self.assertEqual(
            outcome.metadata["ocr_processed_image_count"],
            2,
        )

    def test_empty_resolver_output_remains_review_only(self) -> None:
        outcome = ImportWorkflow(
            build_legacy_ocr_pipeline(
                raw_text_resolver=lambda *_args: ""
            )
        ).execute(
            self.request,
            self._workspace("empty-resolver-workspace"),
        )

        self.assertTrue(outcome.metadata["ocr_provider_available"])
        self.assertEqual(
            outcome.metadata["ocr_provider_id"],
            "legacy-ocr",
        )
        self.assertEqual(
            outcome.metadata["ocr_processed_image_count"],
            2,
        )
        self.assertTrue(outcome.metadata["ocr_review_required"])

    def test_factory_does_not_create_collection_or_persistence_files(self) -> None:
        workspace = self._workspace("read-only-workspace")

        ImportWorkflow(
            build_legacy_ocr_pipeline(
                raw_text_resolver=lambda *_args: "CANADA 1967"
            )
        ).execute(
            self.request,
            workspace,
        )

        forbidden_names = {
            "collection.json",
            "app_state.json",
            "confirmed_observations.json",
        }

        self.assertFalse(
            any(
                path.name in forbidden_names
                for path in self.root.rglob("*")
                if path.is_file()
            )
        )


if __name__ == "__main__":
    unittest.main()