from __future__ import annotations

import unittest

from capture_import.evidence_fusion import (
    FusionFieldStatus,
    fuse_identity_evidence,
)


def _visual(rank=1, country="United States", denomination="Half Dollar", year="1935"):
    return {
        "rank": rank,
        "country": country,
        "denomination": denomination,
        "year": year,
        "confidence": 0.99,
        "provider_id": "visual-provider",
        "model_id": "fixed-model",
    }


def _ocr(field, value, role="reverse"):
    return {
        "field_name": field,
        "normalized_value": value,
        "provider_id": "legacy-ocr",
        "image_role": role,
        "artifact_key": f"artifact-{role}",
        "confidence_score": 0.4,
    }


class EvidenceFusionTests(unittest.TestCase):
    def test_canonical_agreement_retains_both_sources_without_confidence_math(self) -> None:
        report = fuse_identity_evidence(
            visual_candidates=[_visual()],
            ocr_candidates=[_ocr("denomination", "1/2 dollar")],
        )
        field = report.field("denomination")
        self.assertIs(field.status, FusionFieldStatus.AGREED)
        self.assertEqual(field.selected_value, "Half Dollar")
        self.assertEqual(len(field.visual_values), 1)
        self.assertEqual(len(field.ocr_values), 1)
        self.assertEqual(field.visual_values[0].confidence_score, 0.99)
        self.assertEqual(field.ocr_values[0].confidence_score, 0.4)

    def test_visual_only_is_not_treated_as_disagreement(self) -> None:
        report = fuse_identity_evidence(
            visual_candidates=[_visual()], ocr_candidates=[]
        )
        self.assertIs(report.field("year").status, FusionFieldStatus.VISUAL_ONLY)
        self.assertEqual(report.field("year").selected_value, "1935")

    def test_ocr_only_is_retained_and_requires_review(self) -> None:
        visual = _visual(year=None)
        report = fuse_identity_evidence(
            visual_candidates=[visual],
            ocr_candidates=[_ocr("year", "1935")],
        )
        self.assertIs(report.field("year").status, FusionFieldStatus.OCR_ONLY)
        self.assertEqual(report.field("year").selected_value, "1935")
        self.assertTrue(report.review_required)

    def test_conflict_retains_values_and_selects_neither(self) -> None:
        report = fuse_identity_evidence(
            visual_candidates=[_visual(year="1935")],
            ocr_candidates=[_ocr("year", "1936")],
        )
        field = report.field("year")
        self.assertIs(field.status, FusionFieldStatus.CONFLICT)
        self.assertIsNone(field.selected_value)
        self.assertEqual(
            {item.raw_value for item in (*field.visual_values, *field.ocr_values)},
            {"1935", "1936"},
        )
        self.assertTrue(report.unresolved)

    def test_no_evidence_is_unresolved(self) -> None:
        report = fuse_identity_evidence(visual_candidates=[], ocr_candidates=[])
        self.assertTrue(report.unresolved)
        self.assertTrue(
            all(field.status is FusionFieldStatus.UNRESOLVED for field in report.fields)
        )

    def test_lower_rank_agreement_is_surfaced_without_promotion(self) -> None:
        report = fuse_identity_evidence(
            visual_candidates=[
                _visual(rank=1, year="1935"),
                _visual(rank=2, year="1936"),
            ],
            ocr_candidates=[_ocr("year", "1936")],
        )
        field = report.field("year")
        self.assertIs(field.status, FusionFieldStatus.CONFLICT)
        self.assertEqual(field.lower_rank_visual_agreements, (2,))
        self.assertIsNone(field.selected_value)

    def test_explicit_or_multiple_ocr_conflict_never_auto_resolves(self) -> None:
        candidates = [_ocr("year", "1935"), _ocr("year", "1936", "obverse")]
        explicit = [{"field_name": "year", "candidate_values": ["1935", "1936"]}]
        for conflicts in ([], explicit):
            with self.subTest(conflicts=conflicts):
                report = fuse_identity_evidence(
                    visual_candidates=[_visual(year="1935")],
                    ocr_candidates=candidates,
                    ocr_conflicts=conflicts,
                )
                self.assertIs(
                    report.field("year").status, FusionFieldStatus.CONFLICT
                )
                self.assertIsNone(report.field("year").selected_value)

    def test_year_ocr_never_replaces_visual_year(self) -> None:
        report = fuse_identity_evidence(
            visual_candidates=[_visual(year="1920")],
            ocr_candidates=[_ocr("year", "1620")],
        )
        self.assertIs(report.field("year").status, FusionFieldStatus.CONFLICT)
        self.assertIsNone(report.field("year").selected_comparable_value)


if __name__ == "__main__":
    unittest.main()
