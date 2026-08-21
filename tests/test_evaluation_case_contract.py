import json
import math
from pathlib import Path
import tempfile
import unittest

from capture_import.evaluation_case_contract import (
    EvaluationCase,
    EvaluationCaseContractError,
    EvaluationInput,
    EvaluationProvenance,
    ExpectedFinding,
    canonical_manifest,
    parse_evaluation_case_manifest,
)
from capture_import.evaluation_harness import (
    BenchmarkCase,
    BenchmarkManifest,
    to_evaluation_case as ocr_evaluation_case,
)
from capture_import.visual_evaluation_harness import (
    VisualBenchmarkCase,
    VisualBenchmarkImage,
    VisualBenchmarkManifest,
    to_evaluation_case as visual_evaluation_case,
)


def _case(case_id="case-b", value=1967):
    return EvaluationCase(
        case_id=case_id,
        specimen_id="specimen-1",
        inputs=(EvaluationInput("obverse", "images/obverse.jpg"),),
        expected_findings=(ExpectedFinding("year", value),),
        allowed_abstention=True,
        provenance=(
            EvaluationProvenance(
                "obverse",
                "https://example.invalid/reference",
                "CC0-1.0",
                "Synthetic Fixture Author",
                "controlled_fixture",
            ),
        ),
        privacy_classification="synthetic",
    )


class EvaluationCaseContractTests(unittest.TestCase):
    def test_finite_numeric_findings_are_preserved(self):
        case = _case(value=2.5)

        self.assertEqual(2.5, case.expected_findings[0].value)

    def test_non_finite_numeric_findings_are_rejected(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(EvaluationCaseContractError):
                    _case(value=value)

    def test_input_reference_must_be_sanitized_and_relative(self):
        for reference in (".", "C:/private/coin.jpg", "/private/coin.jpg", "../coin.jpg", "a\\coin.jpg"):
            with self.subTest(reference=reference):
                with self.assertRaises(EvaluationCaseContractError):
                    EvaluationInput("obverse", reference)

    def test_provenance_rejects_local_filesystem_paths(self):
        for reference in ("C:/private/coin.jpg", "C:\\private\\coin.jpg", "/private/coin.jpg", "file:///private/coin.jpg"):
            with self.subTest(reference=reference):
                with self.assertRaises(EvaluationCaseContractError):
                    EvaluationProvenance(
                        "obverse",
                        reference,
                        "CC0-1.0",
                        "Synthetic Fixture Author",
                        "controlled_fixture",
                    )

    def test_manifest_serialization_and_round_trip_are_deterministic(self):
        manifest = canonical_manifest((_case("case-b"), _case("case-a")))

        first = manifest.to_json()
        second = manifest.to_json()
        parsed = parse_evaluation_case_manifest(json.loads(first))

        self.assertEqual(("case-a", "case-b"), tuple(case.case_id for case in manifest.cases))
        self.assertEqual(first, second)
        self.assertEqual(first, parsed.to_json())
        self.assertNotIn("NaN", first)

    def test_manifest_rejects_non_object_collection_entries(self):
        payload = canonical_manifest((_case(),)).to_dict()
        payload["cases"][0]["inputs"] = ["not-an-object"]

        with self.assertRaises(EvaluationCaseContractError):
            parse_evaluation_case_manifest(payload)

    def test_manifest_rejects_unknown_schema_version(self):
        payload = canonical_manifest((_case(),)).to_dict()
        payload["version"] = "999"

        with self.assertRaises(EvaluationCaseContractError):
            parse_evaluation_case_manifest(payload)

    def test_ocr_path_projects_into_common_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case = BenchmarkCase(
                case_id="ocr-case",
                obverse=root / "images" / "obverse.jpg",
                reverse=root / "images" / "reverse.jpg",
                expected={"country": "Canada", "denomination": "5 cents", "year": "1964"},
                identity_certain=True,
                difficulty=("synthetic",),
                provenance={
                    "source_url": "https://example.invalid/ocr",
                    "license": "CC0-1.0",
                    "author": "Synthetic Fixture Author",
                },
                notes="",
            )
            manifest = BenchmarkManifest(version="test", root=root, cases=(case,))

            projected = ocr_evaluation_case(
                manifest,
                case,
                allowed_abstention=True,
                privacy_classification="synthetic",
            )

        self.assertIsNone(projected.specimen_id)
        self.assertEqual(("obverse", "reverse"), tuple(item.role for item in projected.inputs))
        self.assertTrue(projected.allowed_abstention)

    def test_visual_path_projects_specimen_and_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def image(role):
                return VisualBenchmarkImage(
                    role=role,
                    path=root / "images" / f"{role}.jpg",
                    source_asset_path=root / "source" / f"{role}.jpg",
                    source_page=f"https://example.invalid/{role}",
                    source_file_url=f"https://example.invalid/{role}.jpg",
                    author="Synthetic Fixture Author",
                    license="CC0-1.0",
                    retrieved_at="2026-08-21",
                    source_sha256="0" * 64,
                    transformation="none",
                )

            case = VisualBenchmarkCase(
                case_id="visual-case",
                underlying_identity="specimen-visual",
                obverse=image("obverse"),
                reverse=image("reverse"),
                expected={"country": "Canada", "denomination": "5 cents", "year": "1964"},
                identity_certain=True,
                era="modern",
                difficulty=("synthetic",),
                previously_used=False,
                notes="",
            )
            manifest = VisualBenchmarkManifest(version="test", root=root, cases=(case,))

            projected = visual_evaluation_case(
                manifest,
                case,
                allowed_abstention=False,
                privacy_classification="synthetic",
            )

        self.assertEqual("specimen-visual", projected.specimen_id)
        self.assertEqual(("obverse", "reverse"), tuple(item.role for item in projected.provenance))
        self.assertTrue(all(item.source_sha256 == "0" * 64 for item in projected.provenance))
        self.assertFalse(projected.allowed_abstention)


if __name__ == "__main__":
    unittest.main()
