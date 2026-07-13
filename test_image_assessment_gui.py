"""GUI-facing tests for v8.8 Phase 3 Image Readiness workspace panel."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from coin_collection import CoinItem, ItemPhoto, PhotoRole
from coin_collection_gui import CoinCollectionGUI
from image_assessment import (
    DownstreamPermission,
    ImageAssessmentConfidence,
    ImageReadinessDecision,
    PhotoQualityAssessment,
    PhotoSetReadinessReport,
)
from collector_workspace import ImageAssessmentReport


class FakeText:
    def __init__(self):
        self.content = ""
        self.state = ""

    def config(self, **kwargs):
        self.state = kwargs.get("state", self.state)

    def delete(self, _start, _end):
        self.content = ""

    def insert(self, _index, content):
        self.content += content


class FakeListbox:
    def __init__(self):
        self.items = []
        self.selection = ()

    def delete(self, _start, _end):
        self.items = []
        self.selection = ()

    def insert(self, _index, content):
        self.items.append(content)

    def size(self):
        return len(self.items)

    def selection_set(self, index):
        self.selection = (index,)

    def curselection(self):
        return self.selection


class FakeVar:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeWorkspace:
    def __init__(self, report):
        self.report = report
        self.refresh_count = 0
        self.calls = []

    def refresh(self):
        self.refresh_count += 1

    def get_image_assessment(self, **kwargs):
        self.calls.append(kwargs)
        return self.report


def make_photo_assessment(path="front.jpg", role="FRONT", decision=ImageReadinessDecision.READY):
    return PhotoQualityAssessment(
        path=path,
        role=role,
        readiness_score=92,
        decision=decision,
        confidence=ImageAssessmentConfidence.HIGH,
        strengths=["Image format is supported.", "Brightness is within the usable range."],
        issues=["Minor contrast issue."],
        blocking_issues=[],
        recommended_actions=["Retake only if more detail is needed."],
        permitted_uses={
            "BROAD_IDENTIFICATION": DownstreamPermission.YES,
            "OCR": DownstreamPermission.YES,
            "VARIETY_ATTRIBUTION": DownstreamPermission.MAYBE,
            "GRADE_ESTIMATION": DownstreamPermission.YES,
            "SUBMISSION_READINESS": DownstreamPermission.MAYBE,
        },
    )


def make_report(*, degraded=False):
    assessment = make_photo_assessment()
    readiness = PhotoSetReadinessReport(
        item_id="item-1",
        overall_readiness_score=88,
        decision=ImageReadinessDecision.READY,
        confidence=ImageAssessmentConfidence.HIGH,
        photo_assessments=[assessment],
        required_roles_present={"front": True, "back": True},
        downstream_permissions={
            "BROAD_IDENTIFICATION": DownstreamPermission.YES,
            "OCR": DownstreamPermission.YES,
            "VARIETY_ATTRIBUTION": DownstreamPermission.MAYBE,
            "GRADE_ESTIMATION": DownstreamPermission.YES,
            "SUBMISSION_READINESS": DownstreamPermission.MAYBE,
        },
        evidence=["Front or obverse photo is present."],
        blocking_issues=["Image file is missing."] if degraded else [],
        recommended_actions=["Check the path or wait for cloud sync."] if degraded else ["No retake needed."],
    )
    return ImageAssessmentReport(
        selection_type="item",
        selection_id="item-1",
        item_id="item-1",
        photo_count=1,
        blocking_issue_count=1 if degraded else 0,
        warning_count=1,
        readiness_report=readiness,
        summary={
            "decision": "NOT_READY" if degraded else "READY",
            "confidence": "LOW" if degraded else "HIGH",
            "overall_readiness_score": 0 if degraded else 88,
        },
        engine_errors=["Image Assessment degraded."] if degraded else [],
    )


class ImageAssessmentGUITests(unittest.TestCase):
    def setUp(self):
        self.gui = object.__new__(CoinCollectionGUI)

    def test_empty_report_format(self):
        report = ImageAssessmentReport(
            selection_type="none",
            engine_errors=["No image assessment selection was provided."],
            summary={"decision": "NOT_READY", "confidence": "LOW", "overall_readiness_score": 0},
        )

        text = self.gui._format_image_readiness(report)

        self.assertIn("Image Readiness", text)
        self.assertIn("Selection:          none", text)
        self.assertIn("No downstream permission data available.", text)
        self.assertIn("No image assessment selection was provided.", text)

    def test_populated_report_format(self):
        text = self.gui._format_image_readiness(make_report())

        self.assertIn("Readiness Score:    88", text)
        self.assertIn("Decision:           READY", text)
        self.assertIn("Confidence:         HIGH", text)
        self.assertIn("Broad Identification: YES", text)
        self.assertIn("OCR: YES", text)
        self.assertIn("Variety Attribution: MAYBE", text)
        self.assertIn("Grade Estimation: YES", text)
        self.assertIn("Submission Readiness: MAYBE", text)
        self.assertIn("Image format is supported.", text)
        self.assertIn("Minor contrast issue.", text)
        self.assertIn("No blocking issues reported.", text)
        self.assertIn("No retake needed.", text)

    def test_degraded_report_format(self):
        text = self.gui._format_image_readiness(make_report(degraded=True))

        self.assertIn("Blocking Issues", text)
        self.assertIn("Image file is missing.", text)
        self.assertIn("Check the path or wait for cloud sync.", text)
        self.assertIn("Image Assessment degraded.", text)

    def test_per_photo_detail_format(self):
        detail = self.gui._format_image_readiness_photo_detail(make_photo_assessment())

        self.assertIn("Photo Assessment", detail)
        self.assertIn("Role:        FRONT", detail)
        self.assertIn("Readiness:   READY", detail)
        self.assertIn("Retake only if more detail is needed.", detail)

    def test_refresh_uses_workspace_api(self):
        report = make_report()
        workspace = FakeWorkspace(report)
        tab = {
            "text": FakeText(),
            "details_text": FakeText(),
            "photo_listbox": FakeListbox(),
            "item_var": FakeVar("1920 Canada Cent [item-1]"),
            "certified_var": FakeVar(False),
            "item_options": [("1920 Canada Cent [item-1]", "item-1")],
            "current_report": None,
        }

        self.gui._refresh_image_readiness_tab(tab, workspace)

        self.assertEqual(workspace.refresh_count, 1)
        self.assertEqual(workspace.calls[-1]["item_id"], "item-1")
        self.assertTrue(workspace.calls[-1]["refresh"])
        self.assertIn("Image Readiness", tab["text"].content)
        self.assertEqual(tab["photo_listbox"].size(), 1)

    def test_per_photo_selection_updates_detail(self):
        report = make_report()
        listbox = FakeListbox()
        tab = {
            "details_text": FakeText(),
            "photo_listbox": listbox,
            "current_report": report,
        }
        self.gui._populate_image_readiness_photo_list(tab, report)

        self.gui._update_image_readiness_photo_detail(tab)

        self.assertIn("Photo Assessment", tab["details_text"].content)
        self.assertIn("FRONT", tab["details_text"].content)

    def test_markdown_export_uses_current_report(self):
        tab = {"current_report": make_report()}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "image_readiness.md")
            with patch("coin_collection_gui.filedialog.asksaveasfilename", return_value=path), \
                 patch("coin_collection_gui.messagebox.showinfo") as showinfo:
                self.gui._export_image_readiness_markdown(tab)
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()

        self.assertIn("Image Assessment Readiness", content)
        showinfo.assert_called_once()

    def test_item_options_include_photos_and_legacy_image_path(self):
        modern = CoinItem(
            id="modern",
            image_path="",
            country="Canada",
            denomination="Cent",
            year="1920",
            grade="VF",
            notes="",
            date_added="2026-07-13",
            photos=[ItemPhoto("front.jpg", role=PhotoRole.FRONT)],
        )
        legacy = CoinItem(
            id="legacy",
            image_path="legacy.jpg",
            country="Canada",
            denomination="Dime",
            year="1936",
            grade="XF",
            notes="",
            date_added="2026-07-13",
        )
        no_photo = CoinItem(
            id="none",
            image_path="",
            country="Canada",
            denomination="Quarter",
            year="1967",
            grade="MS",
            notes="",
            date_added="2026-07-13",
        )
        self.gui._collection_items = lambda: [modern, legacy, no_photo]

        options = self.gui._image_readiness_item_options()

        self.assertEqual([item_id for _label, item_id in options], ["modern", "legacy"])


if __name__ == "__main__":
    unittest.main()
