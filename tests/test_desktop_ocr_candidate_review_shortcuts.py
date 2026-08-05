"""Shortcut and navigation-focused tests for the desktop OCR candidate-review dialog."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from capture_import.desktop_ocr_candidate_review import (
    OCRCandidatePreview,
    OCRCandidateReviewDialog,
    OCRCandidateReviewModel,
    _FOCUS_APPROVE,
    _FOCUS_CLOSE,
    _FOCUS_CORRECT,
    _FOCUS_CORRECTION,
    _FOCUS_DEFER,
    _FOCUS_REASON,
    _FOCUS_REJECT,
    _ImageReviewAdjustmentStore,
    _SHORTCUT_BINDINGS,
    _SHORTCUT_HELP_TEXT,
    _initial_focus_role,
)
from capture_import.workflow_ocr_models import (
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRReviewStatus,
)
from capture_import.workflow_ocr_review_controller import (
    OCRReviewSessionController,
)
from capture_import.workflow_ocr_review_models import OCRReviewDecision


class _ShortcutTestWindow:
    def __init__(self) -> None:
        self.exists = True
        self.focused_widget = object()
        self.bindings = []
        self.idle_callbacks = []
        self.destroy_count = 0

    def bind(self, sequence, callback, add=None):
        self.bindings.append((sequence, callback, add))

    def winfo_exists(self):
        return self.exists

    def focus_get(self):
        return self.focused_widget

    def after_idle(self, callback):
        self.idle_callbacks.append(callback)

    def destroy(self):
        self.exists = False
        self.destroy_count += 1


def _shortcut_event(keysym: str):
    return SimpleNamespace(keysym=keysym)


def _candidate(
    *,
    source_coin_id: str = "coin-1",
    field_name: str = "year",
    value: str = "1967",
    image_role: str = "front",
    artifact_key: str = "crop-1",
    provider_id: str = "provider-1",
    confidence_score: float = 94.5,
    evidence: tuple[str, ...] = (),
) -> OCRFieldCandidate:
    return OCRFieldCandidate(
        source_coin_id=source_coin_id,
        image_role=image_role,
        artifact_key=artifact_key,
        provider_id=provider_id,
        field_name=field_name,
        raw_text=f"raw {value}",
        normalized_value=value,
        confidence_score=confidence_score,
        evidence=evidence,
    )


def _report(*candidates: OCRFieldCandidate) -> OCRMetadataReport:
    return OCRMetadataReport(
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


class OCRCandidateReviewModelTests(unittest.TestCase):
    def model(
        self,
        *candidates: OCRFieldCandidate,
        controller: OCRReviewSessionController | None = None,
        preview_resolver=None,
    ) -> OCRCandidateReviewModel:
        return OCRCandidateReviewModel(
            report=_report(*candidates),
            review_controller=(
                OCRReviewSessionController()
                if controller is None
                else controller
            ),
            reviewer_id="reviewer-1",
            preview_resolver=preview_resolver,
        )

    def test_position_and_count_update_during_navigation(self) -> None:
        model = self.model(
            _candidate(field_name="country", value="Canada"),
            _candidate(),
        )

        self.assertEqual(model.display.position_label, "Candidate 1 of 2")
        model.next_candidate()
        self.assertEqual(model.display.position_label, "Candidate 2 of 2")

    def test_candidate_navigation_moves_selection_to_exact_reference(self) -> None:
        model = self.model(
            _candidate(
                field_name="country",
                value="Canada",
                image_role="front",
                artifact_key="front-country",
            ),
            _candidate(
                field_name="year",
                value="1967",
                image_role="front",
                artifact_key="front-year",
            ),
        )
        first = model._side_previews(model.display)[0]

        self.assertTrue(model.next_candidate())
        second = model._side_previews(model.display)[0]

        self.assertTrue(first.is_selected)
        self.assertTrue(second.is_selected)
        self.assertNotEqual(first.preview.reference, second.preview.reference)
        self.assertEqual(
            second.preview.reference,
            model.current_candidate.artifact_key,
        )

    def test_selection_is_distinct_from_human_review_decision(self) -> None:
        model = self.model(_candidate())

        before = model._side_previews(model.display)[0]
        model.approve(reason="Confirmed visually.")
        after = model._side_previews(model.display)[0]

        self.assertEqual(before.selection_label, after.selection_label)
        self.assertEqual(after.selection_label, "Selected candidate reference")
        self.assertNotIn("approve", after.selection_label.lower())
        self.assertNotIn("reject", after.selection_label.lower())
        self.assertEqual(model.current_candidate.human_review_state, "APPROVE")

    def test_selection_navigation_preserves_crop_zoom_and_contrast_state(
        self,
    ) -> None:
        def resolve(candidate):
            return OCRCandidatePreview(
                reference=candidate.artifact_key,
                image=object(),
                crop_adjusted_image_renderer=(
                    lambda _zoom, _contrast, _crop: object()
                ),
            )

        model = self.model(
            _candidate(
                field_name="country",
                value="Canada",
                artifact_key="front-country",
            ),
            _candidate(field_name="year", artifact_key="front-year"),
            preview_resolver=resolve,
        )
        store = _ImageReviewAdjustmentStore()
        original_side = model._side_previews(model.display)[0]
        store.change_zoom(original_side.identity, original_side.preview, 1)
        store.change_contrast(original_side.identity, original_side.preview, 1)
        store.change_crop(
            original_side.identity,
            original_side.preview,
            "left",
            1,
        )

        self.assertTrue(model.next_candidate())
        self.assertTrue(model.previous_candidate())
        restored_side = model._side_previews(model.display)[0]
        restored = store.adjustment(restored_side.identity)

        self.assertEqual(restored_side.identity, original_side.identity)
        self.assertEqual(restored.zoom, 1.25)
        self.assertEqual(restored.contrast, 1.1)
        self.assertEqual(restored.crop.left, 0.05)

    def test_navigation_updates_only_batch_position(self) -> None:
        model = self.model(
            _candidate(source_coin_id="coin-1", field_name="country", value="Canada"),
            _candidate(source_coin_id="coin-1"),
            _candidate(source_coin_id="coin-2"),
        )
        before = model._batch_progress()

        self.assertTrue(model.next_candidate())
        after = model._batch_progress()

        self.assertEqual(
            (
                before.total,
                before.reviewed,
                before.remaining,
                before.approved,
                before.corrected,
                before.rejected,
                before.deferred,
                before.unresolved_conflicts,
            ),
            (
                after.total,
                after.reviewed,
                after.remaining,
                after.approved,
                after.corrected,
                after.rejected,
                after.deferred,
                after.unresolved_conflicts,
            ),
        )
        self.assertEqual((before.overall_position, after.overall_position), (1, 2))
        self.assertEqual((before.coin_position, after.coin_position), (1, 2))

    def _shortcut_dialog(
        self,
        *candidates: OCRFieldCandidate,
    ) -> OCRCandidateReviewDialog:
        dialog = OCRCandidateReviewDialog.__new__(OCRCandidateReviewDialog)
        dialog._model = self.model(*candidates)
        dialog.window = _ShortcutTestWindow()  # type: ignore[assignment]
        dialog._pressed_shortcut_keys = set()
        return dialog

    def test_dialog_binds_documented_shortcuts_once_outside_render(self) -> None:
        dialog = self._shortcut_dialog(_candidate())

        dialog._bind_shortcuts()

        self.assertEqual(
            tuple(binding[0] for binding in dialog.window.bindings),
            tuple(sequence for sequence, _action in _SHORTCUT_BINDINGS)
            + ("<KeyRelease>",),
        )
        self.assertTrue(
            all(binding[2] == "+" for binding in dialog.window.bindings)
        )
        self.assertNotIn("_bind_shortcuts", inspect.getsource(dialog._render))

    def test_each_shortcut_routes_to_the_existing_dialog_command_once(
        self,
    ) -> None:
        dialog = self._shortcut_dialog(
            _candidate(field_name="country", value="Canada"),
            _candidate(),
            _candidate(field_name="denomination", value="1 cent"),
        )
        dialog._model.next_candidate()
        calls = []
        for method_name in ("_previous", "_next", "_approve", "_reject", "close"):
            setattr(
                dialog,
                method_name,
                lambda name=method_name: calls.append(name),
            )

        cases = (
            ("previous", "Left", "_previous"),
            ("next", "Right", "_next"),
            ("approve", "Return", "_approve"),
            ("reject", "BackSpace", "_reject"),
            ("close", "Escape", "close"),
        )
        for action, keysym, expected in cases:
            with self.subTest(action=action):
                result = dialog._handle_shortcut(
                    _shortcut_event(keysym),
                    action,
                )
                dialog._release_shortcut_key(_shortcut_event(keysym))
                self.assertEqual(result, "break")
                self.assertEqual(calls[-1], expected)

        self.assertEqual(len(calls), len(cases))

    def test_key_repeat_is_consumed_without_duplicate_invocation(self) -> None:
        dialog = self._shortcut_dialog(_candidate())
        calls = []
        dialog._approve = lambda: calls.append("approve")
        event = _shortcut_event("Return")

        self.assertEqual(dialog._handle_shortcut(event, "approve"), "break")
        self.assertEqual(dialog._handle_shortcut(event, "approve"), "break")
        self.assertEqual(calls, ["approve"])

        dialog._release_shortcut_key(event)
        self.assertEqual(dialog._handle_shortcut(event, "approve"), "break")
        self.assertEqual(calls, ["approve", "approve"])

    def test_unavailable_navigation_and_decisions_are_not_consumed(self) -> None:
        dialog = self._shortcut_dialog()
        calls = []
        dialog._previous = lambda: calls.append("previous")
        dialog._next = lambda: calls.append("next")
        dialog._approve = lambda: calls.append("approve")
        dialog._reject = lambda: calls.append("reject")

        for action, keysym in (
            ("previous", "Left"),
            ("next", "Right"),
            ("approve", "Return"),
            ("reject", "BackSpace"),
        ):
            with self.subTest(action=action):
                self.assertIsNone(
                    dialog._handle_shortcut(_shortcut_event(keysym), action)
                )

        self.assertEqual(calls, [])

    def test_navigation_shortcuts_respect_existing_boundaries(self) -> None:
        dialog = self._shortcut_dialog(
            _candidate(),
            _candidate(field_name="country"),
        )
        dialog._error_var = SimpleNamespace(set=lambda _value: None)
        dialog._render = lambda: None

        self.assertIsNone(
            dialog._handle_shortcut(_shortcut_event("Left"), "previous")
        )
        self.assertEqual(
            dialog._handle_shortcut(_shortcut_event("Right"), "next"),
            "break",
        )
        dialog._release_shortcut_key(_shortcut_event("Right"))
        self.assertEqual(dialog._model.candidate_index, 1)
        self.assertIsNone(
            dialog._handle_shortcut(_shortcut_event("Right"), "next")
        )

    def test_shortcuts_are_suppressed_for_editable_and_native_controls(
        self,
    ) -> None:
        dialog = self._shortcut_dialog(_candidate())
        calls = []
        dialog._approve = lambda: calls.append("approve")

        with patch(
            "capture_import.desktop_ocr_candidate_review."
            "_is_editable_or_native_key_widget",
            return_value=True,
        ):
            result = dialog._handle_shortcut(
                _shortcut_event("Return"),
                "approve",
            )

        self.assertIsNone(result)
        self.assertEqual(calls, [])

    def test_unmodified_native_keys_have_no_dialog_binding(self) -> None:
        sequences = tuple(sequence for sequence, _action in _SHORTCUT_BINDINGS)

        for unmodified in (
            "<Left>",
            "<Right>",
            "<space>",
            "<Return>",
            "<Tab>",
            "<Shift-Tab>",
        ):
            self.assertNotIn(unmodified, sequences)

    def test_shortcuts_do_not_run_after_dialog_destruction(self) -> None:
        dialog = self._shortcut_dialog(_candidate())
        calls = []
        dialog._approve = lambda: calls.append("approve")
        dialog.window.exists = False

        result = dialog._handle_shortcut(
            _shortcut_event("Return"),
            "approve",
        )

        self.assertIsNone(result)
        self.assertEqual(calls, [])

    def test_shortcut_navigation_updates_selection_without_losing_adjustments(
        self,
    ) -> None:
        def resolve(candidate):
            return OCRCandidatePreview(
                reference=candidate.artifact_key,
                image=object(),
                crop_adjusted_image_renderer=(
                    lambda _zoom, _contrast, _crop: object()
                ),
            )

        dialog = self._shortcut_dialog(
            _candidate(
                field_name="country",
                value="Canada",
                artifact_key="country",
            ),
            _candidate(artifact_key="year"),
        )
        dialog._model = self.model(
            _candidate(
                field_name="country",
                value="Canada",
                artifact_key="country",
            ),
            _candidate(artifact_key="year"),
            preview_resolver=resolve,
        )
        dialog._adjustments = _ImageReviewAdjustmentStore()
        first = dialog._model._side_previews(dialog._model.display)[0]
        dialog._adjustments.change_zoom(first.identity, first.preview, 1)
        dialog._adjustments.change_contrast(first.identity, first.preview, 1)
        dialog._error_var = SimpleNamespace(set=lambda _value: None)
        dialog._render = lambda: None

        result = dialog._handle_shortcut(_shortcut_event("Right"), "next")
        second = dialog._model._side_previews(dialog._model.display)[0]

        self.assertEqual(result, "break")
        self.assertTrue(second.is_selected)
        self.assertNotEqual(first.identity, second.identity)
        retained = dialog._adjustments.adjustment(first.identity)
        self.assertEqual((retained.zoom, retained.contrast), (1.25, 1.1))

    def test_decision_shortcuts_use_existing_review_semantics(self) -> None:
        dialog = self._shortcut_dialog(_candidate())
        dialog._reason_var = SimpleNamespace(get=lambda: "Keyboard review.")
        dialog._error_var = SimpleNamespace(set=lambda _value: None)
        dialog._render = lambda: None

        self.assertEqual(
            dialog._handle_shortcut(_shortcut_event("Return"), "approve"),
            "break",
        )
        self.assertEqual(
            dialog._model.current_review.decision,
            OCRReviewDecision.APPROVE,
        )
        dialog._release_shortcut_key(_shortcut_event("Return"))
        self.assertEqual(
            dialog._handle_shortcut(_shortcut_event("BackSpace"), "reject"),
            "break",
        )
        self.assertEqual(
            dialog._model.current_review.decision,
            OCRReviewDecision.REJECT,
        )

    def test_escape_uses_existing_close_callback_and_destroy_path(self) -> None:
        dialog = self._shortcut_dialog(_candidate())
        closed_reviews = []
        dialog._on_close = lambda reviews: closed_reviews.append(reviews)

        result = dialog._handle_shortcut(_shortcut_event("Escape"), "close")

        self.assertEqual(result, "break")
        self.assertEqual(closed_reviews, [dialog._model.reviews])
        self.assertEqual(dialog.window.destroy_count, 1)
        self.assertFalse(dialog.window.exists)

    def test_shortcut_help_is_readable_and_matches_bindings(self) -> None:
        self.assertEqual(
            _SHORTCUT_HELP_TEXT,
            "Keyboard shortcuts: Alt+Left Previous | Alt+Right Next | "
            "Ctrl+Enter Approve | Ctrl+Backspace Reject | Esc Close",
        )
        self.assertEqual(
            _SHORTCUT_BINDINGS,
            (
                ("<Alt-Left>", "previous"),
                ("<Alt-Right>", "next"),
                ("<Control-Return>", "approve"),
                ("<Control-BackSpace>", "reject"),
                ("<Escape>", "close"),
            ),
        )

    def test_initial_focus_role_is_reason_or_close(self) -> None:
        self.assertEqual(_initial_focus_role(True), _FOCUS_REASON)
        self.assertEqual(_initial_focus_role(False), _FOCUS_CLOSE)

    def test_focus_scheduling_runs_after_idle_and_skips_disabled_widgets(
        self,
    ) -> None:
        callbacks = []

        class FocusWidget:
            def __init__(self, state="normal"):
                self.state = state
                self.focus_count = 0

            def cget(self, name):
                self.assert_name = name
                return self.state

            def focus_set(self):
                self.focus_count += 1

        enabled = FocusWidget()
        disabled = FocusWidget("disabled")
        dialog = OCRCandidateReviewDialog.__new__(OCRCandidateReviewDialog)
        dialog.window = SimpleNamespace(after_idle=callbacks.append)
        dialog._focus_widgets = {
            _FOCUS_REASON: enabled,
            _FOCUS_CORRECTION: disabled,
        }

        dialog._schedule_focus(_FOCUS_REASON)
        self.assertEqual(enabled.focus_count, 0)
        callbacks.pop()()
        self.assertEqual(enabled.focus_count, 1)

        dialog._schedule_focus(_FOCUS_CORRECTION)
        callbacks.pop()()
        self.assertEqual(disabled.focus_count, 0)

    def test_navigation_rerender_restores_reason_focus(self) -> None:
        dialog = self._shortcut_dialog(
            _candidate(field_name="country", value="Canada"),
            _candidate(),
        )
        dialog._error_var = SimpleNamespace(set=lambda _value: None)
        renders = []
        focus_roles = []
        dialog._render = lambda: renders.append(True)
        dialog._schedule_focus = focus_roles.append

        dialog._next()
        dialog._previous()

        self.assertEqual(renders, [True, True])
        self.assertEqual(focus_roles, [_FOCUS_REASON, _FOCUS_REASON])
        self.assertEqual(dialog._model.candidate_index, 0)
        self.assertEqual(dialog._model.reviews, ())

    def test_successful_decisions_focus_corresponding_visible_button(self) -> None:
        cases = (
            ("_approve", OCRReviewDecision.APPROVE, _FOCUS_APPROVE),
            ("_correct", OCRReviewDecision.CORRECT, _FOCUS_CORRECT),
            ("_reject", OCRReviewDecision.REJECT, _FOCUS_REJECT),
            ("_defer", OCRReviewDecision.DEFER, _FOCUS_DEFER),
        )
        for method_name, decision, focus_role in cases:
            with self.subTest(method_name=method_name):
                dialog = OCRCandidateReviewDialog.__new__(
                    OCRCandidateReviewDialog
                )
                dialog._model = self.model(_candidate())
                dialog._reason_var = SimpleNamespace(
                    get=lambda: "Reviewed accessibly."
                )
                dialog._correction_var = SimpleNamespace(
                    get=lambda: "1968"
                )
                dialog._error_var = SimpleNamespace(set=lambda _value: None)
                dialog._render = lambda: None
                focus_roles = []
                dialog._schedule_focus = focus_roles.append

                getattr(dialog, method_name)()

                self.assertEqual(dialog._model.candidate_index, 0)
                self.assertEqual(
                    dialog._model.current_review.decision,
                    decision,
                )
                self.assertEqual(focus_roles, [focus_role])

    def test_validation_failure_focuses_correction_or_reason(self) -> None:
        dialog = OCRCandidateReviewDialog.__new__(OCRCandidateReviewDialog)
        dialog._model = self.model(_candidate())
        dialog._error_var = SimpleNamespace(set=lambda _value: None)
        dialog._render = lambda: self.fail("failed action must not rerender")
        focus_roles = []
        dialog._schedule_focus = focus_roles.append
        dialog._reason_var = SimpleNamespace(get=lambda: "Valid reason.")
        dialog._correction_var = SimpleNamespace(get=lambda: "")

        dialog._correct()
        self.assertEqual(focus_roles, [_FOCUS_CORRECTION])
        self.assertIsNone(dialog._model.current_review)

        focus_roles.clear()
        dialog._reason_var = SimpleNamespace(get=lambda: "")
        dialog._approve()
        self.assertEqual(focus_roles, [_FOCUS_REASON])
        self.assertIsNone(dialog._model.current_review)

    def test_escape_from_entry_uses_close_path_exactly_once(self) -> None:
        dialog = self._shortcut_dialog(_candidate())
        calls = []
        dialog.close = lambda: calls.append("close")
        event = _shortcut_event("Escape")

        with (
            patch(
                "capture_import.desktop_ocr_candidate_review."
                "_is_editable_or_native_key_widget",
                return_value=True,
            ),
            patch(
                "capture_import.desktop_ocr_candidate_review."
                "_escape_closes_from_widget",
                return_value=True,
            ),
        ):
            self.assertEqual(
                dialog._handle_shortcut(event, "close"),
                "break",
            )
            self.assertEqual(
                dialog._handle_shortcut(event, "close"),
                "break",
            )

        self.assertEqual(calls, ["close"])
