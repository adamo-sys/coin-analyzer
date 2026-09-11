"""Actual Tk widgets with synthetic proposals; no provider or collection access."""
from dataclasses import replace
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from capture_import.desktop_visual_identity_review import (
    VisualIdentityReviewDialog, create_visual_identity_proposal,
)
from tests.test_desktop_visual_identity_review import _report


class VisualReviewPresentationTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Native Tk display unavailable: {exc}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.addCleanup(patch.stopall)
        patch("socket.socket", side_effect=AssertionError("Provider/network forbidden")).start()

    def open_dialog(self, **changes):
        report = _report()
        candidate = replace(report.candidates[0], **changes)
        self.confirmed, self.rejected, self.deferred = Mock(), Mock(), Mock()
        dialog = VisualIdentityReviewDialog(
            self.root, proposal=create_visual_identity_proposal(replace(report, candidates=(candidate,))),
            on_confirm=self.confirmed, on_reject=self.rejected, on_defer=self.deferred,
        )
        self.root.update()
        return dialog

    def partial(self):
        return self.open_dialog(country="Canada", denomination=None, year=None, type_design=None,
                                confidence=.99, observed_text=("CANADA",),
                                field_evidence=(("country", ("CANADA legend",)),),
                                evidence_observations=("A generic rim is visible",))

    def test_country_only_high_score_shows_three_unproposed_fields(self):
        dialog = self.partial()
        self.assertEqual(dialog.coverage_label.cget("text"), "Partial proposal: 1 of 4 fields proposed")
        self.assertEqual(dialog.proposed_value_labels["country"].cget("text"), "Canada")
        for field in ("denomination", "year", "type_design"):
            self.assertEqual(dialog.proposed_value_labels[field].cget("text"), "Not proposed")
            self.assertEqual(dialog.field_support_labels[field].cget("text"), "No supporting evidence supplied")
        self.assertIn("99%", dialog.score_label.cget("text"))
        self.assertIn("not a confidence score for each field", dialog.score_label.cget("text"))

    def test_support_is_field_specific_and_generic_observations_stay_separate(self):
        fields = ("country", "denomination", "year", "type_design")
        dialog = self.open_dialog(field_evidence=tuple((f, (f + " support",)) for f in fields))
        for field in fields:
            self.assertEqual(dialog.field_support_labels[field].cget("text"), field + " support")
        dialog.defer()
        partial = self.partial()
        self.assertEqual(partial.field_support_labels["country"].cget("text"), "CANADA legend")
        self.assertIn("generic rim", partial.general_evidence_label.cget("text"))
        self.assertFalse(any("generic rim" in w.cget("text") for w in partial.field_support_labels.values()))

    def test_full_coverage_ignores_low_score_and_missing_evidence_is_explicit(self):
        dialog = self.open_dialog(confidence=.01)
        self.assertEqual(dialog.coverage_label.cget("text"), "Full proposal: 4 of 4 fields proposed")
        self.assertTrue(all(w.cget("text") == "No supporting evidence supplied"
                            for w in dialog.field_support_labels.values()))
        self.assertEqual(dialog.proposed_value_labels["country"].cget("text"), "United States of America")
        self.assertEqual(dialog.country.get(), "United States")

    def test_transcription_and_collector_edits_do_not_change_original_proposal(self):
        dialog = self.partial()
        before = {f: w.cget("text") for f, w in dialog.proposed_value_labels.items()}
        support = {f: w.cget("text") for f, w in dialog.field_support_labels.items()}
        dialog.country.set("Newfoundland")
        dialog.denomination.set("5 cents")
        dialog.year.set("1940")
        dialog.type_design.set("Collector description")
        self.root.update()
        self.assertEqual(dialog.transcribed_text_label.cget("text"), "Provider-transcribed text: CANADA")
        self.assertEqual({f: w.cget("text") for f, w in dialog.proposed_value_labels.items()}, before)
        self.assertEqual({f: w.cget("text") for f, w in dialog.field_support_labels.items()}, support)
        self.assertEqual(dialog.coverage_label.cget("text"), "Partial proposal: 1 of 4 fields proposed")
        self.assertIsNone(dialog.proposal.candidate.year)

    def test_native_confirm_still_requires_country_denomination_year(self):
        dialog = self.partial()
        with patch("capture_import.desktop_visual_identity_review.messagebox.showwarning") as warning:
            dialog.confirm()
        warning.assert_called_once()
        self.confirmed.assert_not_called()
        self.assertTrue(dialog.window.winfo_exists())
        dialog.denomination.set("5 cents")
        dialog.year.set("1940")
        dialog.confirm()
        self.confirmed.assert_called_once()
        reviewed = self.confirmed.call_args.args[0]
        self.assertEqual((reviewed.country, reviewed.denomination, reviewed.year), ("Canada", "5 cents", "1940"))
        self.assertIsNone(dialog.proposal.candidate.year)
        self.rejected.assert_not_called()
        self.deferred.assert_not_called()

    def test_native_reject_defer_and_window_close_remain_single_outcome(self):
        for action in ("reject", "defer"):
            dialog = self.partial()
            self.assertTrue(dialog.window.protocol("WM_DELETE_WINDOW"))
            getattr(dialog, action)()
            dialog.defer()
            self.confirmed.assert_not_called()
            (self.rejected if action == "reject" else self.deferred).assert_called_once_with()
            (self.deferred if action == "reject" else self.rejected).assert_not_called()


if __name__ == "__main__":
    unittest.main()
