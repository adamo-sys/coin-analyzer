"""Sprint 9 Unit 1G OCR diagnostic CLI tests."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from capture_import.workflow_ocr_cli import (
    build_parser,
    main,
    run,
)
from tests.capture_package_fixtures import package_bytes


_EXPECTED_STAGE_IDS = [
    "package-validation",
    "manifest-preparation",
    "image-normalization",
    "image-quality-scoring",
    "crop-detection",
    "ocr-metadata-extraction",
    "obverse-reverse-pairing",
    "image-duplicate-detection",
]


class OCRDiagnosticCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)

        self.root = Path(self.temporary.name)
        self.source = self.root / "fixture.ca-package"
        self.source.write_bytes(package_bytes())
        self.workspace = self.root / "diagnostic-workspace"

    def _arguments(
        self,
        *,
        raw_text: str | None = "CANADA 1967",
    ):
        values = [
            str(self.source),
            "--workspace",
            str(self.workspace),
            "--collection-id",
            "collection-1",
        ]
        if raw_text is not None:
            values.extend(["--raw-text", raw_text])
        return build_parser().parse_args(values)

    def test_parser_requires_source_and_workspace(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args([])

    def test_missing_source_returns_usage_error_without_workspace(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        missing = self.root / "missing.ca-package"

        args = build_parser().parse_args(
            [
                str(missing),
                "--workspace",
                str(self.workspace),
            ]
        )

        result = run(
            args,
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(result, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("does not exist", stderr.getvalue())
        self.assertFalse(self.workspace.exists())

    def test_deterministic_raw_text_emits_json_summary(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        result = run(
            self._arguments(),
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")

        summary = json.loads(stdout.getvalue())

        self.assertEqual(
            summary["pipeline_stage_ids"],
            _EXPECTED_STAGE_IDS,
        )
        self.assertEqual(summary["collection_id"], "collection-1")
        self.assertGreater(summary["artifact_count"], 0)
        self.assertEqual(
            summary["artifact_keys"],
            sorted(summary["artifact_keys"]),
        )

        self.assertTrue(summary["ocr"]["provider_available"])
        self.assertEqual(
            summary["ocr"]["provider_id"],
            "legacy-ocr",
        )
        self.assertEqual(
            summary["ocr"]["processed_image_count"],
            2,
        )
        self.assertTrue(summary["ocr"]["review_required"])
        self.assertEqual(len(summary["ocr"]["reports"]), 2)

    def test_raw_text_path_bypasses_optional_local_ocr_runtime(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "ocr_experiment.OCRExperiment._run_local_ocr",
            side_effect=AssertionError(
                "local OCR runtime must not be called"
            ),
        ):
            result = run(
                self._arguments(),
                stdout=stdout,
                stderr=stderr,
            )

        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")

    def test_output_is_deterministic_for_equivalent_runs(self) -> None:
        first_stdout = io.StringIO()
        second_stdout = io.StringIO()

        first_workspace = self.root / "first-workspace"
        second_workspace = self.root / "second-workspace"

        first_args = build_parser().parse_args(
            [
                str(self.source),
                "--workspace",
                str(first_workspace),
                "--raw-text",
                "CANADA 1967",
            ]
        )
        second_args = build_parser().parse_args(
            [
                str(self.source),
                "--workspace",
                str(second_workspace),
                "--raw-text",
                "CANADA 1967",
            ]
        )

        self.assertEqual(
            run(
                first_args,
                stdout=first_stdout,
                stderr=io.StringIO(),
            ),
            0,
        )
        self.assertEqual(
            run(
                second_args,
                stdout=second_stdout,
                stderr=io.StringIO(),
            ),
            0,
        )

        first = json.loads(first_stdout.getvalue())
        second = json.loads(second_stdout.getvalue())

        first.pop("workspace")
        second.pop("workspace")

        self.assertEqual(first, second)

    def test_cli_does_not_create_collection_persistence_files(self) -> None:
        stdout = io.StringIO()

        result = run(
            self._arguments(),
            stdout=stdout,
            stderr=io.StringIO(),
        )

        self.assertEqual(result, 0)

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

    def test_main_returns_success_with_explicit_arguments(self) -> None:
        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            with patch("sys.stderr", new_callable=io.StringIO) as stderr:
                result = main(
                    [
                        str(self.source),
                        "--workspace",
                        str(self.workspace),
                        "--raw-text",
                        "CANADA 1967",
                    ]
                )

        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(
            json.loads(stdout.getvalue())["ocr"]["provider_id"],
            "legacy-ocr",
        )


if __name__ == "__main__":
    unittest.main()