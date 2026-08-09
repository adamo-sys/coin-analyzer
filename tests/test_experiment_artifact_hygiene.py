from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from capture_import.fusion_evaluation_cli import build_parser as fusion_parser
from capture_import.visual_evaluation_cli import build_parser as visual_parser


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    ROOT / "artifacts" / "benchmark-v2-terra-prospective-report.json",
    ROOT / "artifacts" / "benchmark-v2-visual-ocr-fusion-report.json",
)
SECRET_PATTERN = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{20,}|gh[opusr]_[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9._-]{12,})",
    re.IGNORECASE,
)
ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?:^[A-Za-z]:[\\/]|(?:^|[\\/])Users[\\/]|(?:^|[\\/])home[\\/]|AppData[\\/])",
    re.IGNORECASE,
)


def _walk(value, path="$" ):
    if isinstance(value, dict):
        for key, item in value.items():
            yield path, key, item
            yield from _walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")


class ExperimentArtifactHygieneTests(unittest.TestCase):
    def test_committed_reports_contain_no_operational_or_secret_material(self):
        for artifact in ARTIFACTS:
            with self.subTest(artifact=artifact.name):
                payload = json.loads(artifact.read_text(encoding="utf-8"))
                for path, key, value in _walk(payload):
                    lowered = str(key).casefold()
                    self.assertNotIn("response_id", lowered, path)
                    self.assertNotIn(lowered, {
                        "api_key", "authorization", "access_token",
                        "refresh_token", "password", "secret",
                    }, path)
                    if isinstance(value, str):
                        self.assertIsNone(SECRET_PATTERN.search(value), path)
                        self.assertIsNone(ABSOLUTE_PATH_PATTERN.search(value), path)
                        self.assertNotIn("data:image/", value.casefold(), path)
                        self.assertNotIn(";base64,", value.casefold(), path)

    def test_reports_contain_no_raw_image_payload_fields(self):
        for artifact in ARTIFACTS:
            with self.subTest(artifact=artifact.name):
                payload = json.loads(artifact.read_text(encoding="utf-8"))
                keys = {str(key).casefold() for _, key, _ in _walk(payload)}
                self.assertTrue(
                    keys.isdisjoint(
                        {"image_url", "image_data", "image_bytes", "base64_image"}
                    )
                )

    def test_rerun_cli_defaults_cannot_overwrite_historical_artifacts(self):
        visual = visual_parser().parse_args(["benchmarks/v2/manifest.json"])
        fusion = fusion_parser().parse_args(
            [
                "benchmarks/v2/manifest.json",
                "--visual-report",
                "artifacts/benchmark-v2-terra-prospective-report.json",
            ]
        )
        for output in (visual.json, visual.summary, fusion.json, fusion.summary):
            self.assertEqual(output.parts[:2], ("artifacts", "reruns"))
        self.assertNotEqual(
            visual.json.name, "benchmark-v2-terra-prospective-report.json"
        )
        self.assertNotEqual(
            fusion.json.name, "benchmark-v2-visual-ocr-fusion-report.json"
        )


if __name__ == "__main__":
    unittest.main()
