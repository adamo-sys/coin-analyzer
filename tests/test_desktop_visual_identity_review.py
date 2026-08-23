from __future__ import annotations

import inspect
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from capture_import.desktop_visual_identity_review import (
    ConfirmedVisualIdentity,
    VisualIdentityReviewDialog,
    VisualReviewError,
    create_visual_identity_proposal,
    create_visual_request_from_capture_package,
)
from capture_import.image_store import ManagedCollectionImageStore
from capture_import.reviewed_coin_collection_entry import persist_reviewed_coin
from capture_import.reviewed_coin_collection_entry import ReviewedCoinPersistenceError
from capture_import.snapshot import CapturePackageSnapshotService
from capture_import.standalone_image_intake import create_temporary_capture_package
from capture_import.visual_identity_provider import (
    VisualIdentityCandidate,
    VisualIdentityContractError,
    VisualIdentityReport,
)
from coin_collection import CoinCollection
from coin_collection_gui import CoinCollectionGUI


def _report(*, outcome: str = "CANDIDATES") -> VisualIdentityReport:
    candidates = ()
    if outcome == "CANDIDATES":
        candidates = (
            VisualIdentityCandidate(
                rank=1,
                country="United States of America",
                denomination="Half Dollar",
                year="1964",
                type_design="Kennedy half dollar",
                confidence=0.91,
                evidence_observations=("KENNEDY portrait", "HALF DOLLAR legend"),
                supporting_image_roles=("obverse", "reverse"),
                provider_id="openai-responses-visual",
                model_id="gpt-5.6-terra",
            ),
        )
    return VisualIdentityReport(
        outcome=outcome,
        candidates=candidates,
        provider_id="openai-responses-visual",
        model_id="gpt-5.6-terra",
        response_id="response-must-not-be-persisted",
        input_tokens=500,
        output_tokens=50,
        raw_structured_result={"outcome": outcome, "candidates": []},
    )


class _Provider:
    provider_id = "openai-responses-visual"
    model_id = "gpt-5.6-terra"

    def __init__(self, report=None, error=None) -> None:
        self.report = report or _report()
        self.error = error
        self.requests = []

    def identify(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.report


class DesktopVisualIdentityReviewTests(unittest.TestCase):
    def _images(self, root: Path) -> tuple[Path, Path]:
        front = root / "front.jpg"
        reverse = root / "reverse.png"
        Image.new("RGB", (60, 40), "red").save(front, "JPEG")
        Image.new("RGB", (30, 50), "blue").save(reverse, "PNG")
        return front, reverse

    def _gui(self, collection) -> CoinCollectionGUI:
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = object()
        gui.app = SimpleNamespace(collection=collection)
        gui.capture_import_ready = True
        gui.refresh_collection_list = Mock()
        gui._visual_identity_provider = None
        return gui

    def test_proposal_preserves_raw_canonical_and_provider_evidence(self) -> None:
        proposal = create_visual_identity_proposal(_report())

        self.assertEqual(proposal.candidate.country, "United States of America")
        self.assertEqual(proposal.initial_country, "United States")
        self.assertEqual(proposal.initial_denomination, "1/2 dollar")
        self.assertEqual(proposal.provider_id, "openai-responses-visual")
        self.assertEqual(proposal.model_id, "gpt-5.6-terra")
        self.assertIn("jurisdiction.official-long-name", proposal.canonical_country.normalization_rules)

    def test_partial_proposal_keeps_unknown_fields_empty_for_operator_review(self) -> None:
        report = _report()
        candidate = report.candidates[0]
        partial = VisualIdentityReport(
            outcome="CANDIDATES",
            candidates=(
                VisualIdentityCandidate(
                    rank=candidate.rank,
                    country=None,
                    denomination="Half Dollar",
                    year=None,
                    type_design=None,
                    confidence=candidate.confidence,
                    evidence_observations=candidate.evidence_observations,
                    supporting_image_roles=candidate.supporting_image_roles,
                    provider_id=candidate.provider_id,
                    model_id=candidate.model_id,
                    observed_text=("HALF DOLLAR",),
                    field_evidence=(("denomination", ("HALF DOLLAR is visible",)),),
                ),
            ),
            provider_id=report.provider_id,
            model_id=report.model_id,
            response_id=report.response_id,
            input_tokens=report.input_tokens,
            output_tokens=report.output_tokens,
            raw_structured_result=report.raw_structured_result,
        )

        proposal = create_visual_identity_proposal(partial)

        self.assertEqual(proposal.initial_country, "")
        self.assertEqual(proposal.initial_denomination, "1/2 dollar")
        self.assertIsNone(proposal.candidate.year)

    def test_operator_correction_becomes_existing_reviewed_coin_draft(self) -> None:
        proposal = create_visual_identity_proposal(_report())
        draft = ConfirmedVisualIdentity(
            country="United States",
            denomination="50 cents",
            year="1964",
            type_design="Kennedy half dollar",
        ).to_reviewed_coin_draft(proposal)

        self.assertEqual((draft.country, draft.denomination, draft.year), ("United States", "50 cents", "1964"))
        provenance = dict(draft.unmapped_fields)
        self.assertEqual(provenance["visual_raw_country"], "United States of America")
        self.assertEqual(provenance["visual_canonical_country"], "United States")
        self.assertEqual(provenance["visual_canonical_denomination"], "1/2 dollar")
        self.assertIn("official-long-name", provenance["visual_country_rules"])
        self.assertEqual(provenance["visual_model"], "gpt-5.6-terra")
        self.assertIn("KENNEDY portrait", provenance["visual_evidence"])
        self.assertNotIn("response-must-not-be-persisted", repr(draft))

    def test_required_fields_cannot_be_confirmed_empty(self) -> None:
        with self.assertRaises(VisualReviewError):
            ConfirmedVisualIdentity("", "50 cents", "1964", "").to_reviewed_coin_draft(
                create_visual_identity_proposal(_report())
            )

    def test_abstention_is_not_converted_to_a_candidate(self) -> None:
        with self.assertRaises(VisualReviewError):
            create_visual_identity_proposal(_report(outcome="ABSTAINED"))

    def test_request_uses_exact_validated_package_images_without_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            front, reverse = self._images(root)
            expected_front = front.read_bytes()
            expected_reverse = reverse.read_bytes()
            source = create_temporary_capture_package(front_path=front, reverse_path=reverse)
            try:
                request = create_visual_request_from_capture_package(source.path)
            finally:
                source.release()

        self.assertEqual([image.role for image in request.images], ["obverse", "reverse"])
        self.assertEqual([image.media_type for image in request.images], ["image/jpeg", "image/png"])
        self.assertEqual(request.images[0].data, expected_front)
        self.assertEqual(request.images[1].data, expected_reverse)
        self.assertNotIn("front.jpg", repr(request))
        self.assertNotIn("reverse.png", repr(request))

    def test_review_screen_is_explicit_about_ai_provider_confidence_and_evidence(self) -> None:
        source = inspect.getsource(VisualIdentityReviewDialog.__init__)
        self.assertIn("AI-generated proposal", source)
        self.assertIn("Provider:", source)
        self.assertIn("Provider source score (uncalibrated):", source)
        self.assertIn("Separately transcribed visible text:", source)
        self.assertIn("Evidence:", source)
        self.assertIn("Raw provider values:", source)
        self.assertIn("Supporting image roles:", source)
        self.assertIn("Canonical presentation rules", source)
        self.assertIn("Reject", source)
        self.assertIn("Defer", source)

    def test_declining_upload_disclosure_never_creates_or_calls_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            front, reverse = self._images(root)
            gui = self._gui(CoinCollection(str(root / "collection.json")))
            factory = Mock()
            gui._visual_identity_provider_factory = factory
            with (
                patch("coin_collection_gui.filedialog.askopenfilename", side_effect=[str(front), str(reverse)]),
                patch("coin_collection_gui.messagebox.askyesno", return_value=False),
            ):
                gui.import_coin_images_with_visual_ai()

        factory.assert_not_called()
        self.assertEqual(gui.app.collection.items, [])

    def test_supplied_attached_paths_skip_picker_but_keep_upload_disclosure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            front, reverse = self._images(root)
            gui = self._gui(CoinCollection(str(root / "collection.json")))
            factory = Mock()
            gui._visual_identity_provider_factory = factory
            with (
                patch("coin_collection_gui.filedialog.askopenfilename") as picker,
                patch("coin_collection_gui.messagebox.askyesno", return_value=False) as disclosure,
            ):
                gui.import_coin_images_with_visual_ai(
                    front_path=str(front),
                    reverse_path=str(reverse),
                )

        picker.assert_not_called()
        disclosure.assert_called_once()
        factory.assert_not_called()
        self.assertEqual(gui.app.collection.items, [])

    def test_cancelled_picker_never_creates_or_calls_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            collection = CoinCollection(str(Path(temp) / "collection.json"))
            gui = self._gui(collection)
            factory = Mock()
            gui._visual_identity_provider_factory = factory
            with patch("coin_collection_gui.filedialog.askopenfilename", return_value=""):
                gui.import_coin_images_with_visual_ai()
        factory.assert_not_called()
        self.assertEqual(collection.items, [])

    def test_missing_key_is_clear_and_zero_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            front, reverse = self._images(root)
            collection = CoinCollection(str(root / "collection.json"))
            gui = self._gui(collection)
            with (
                patch.dict("coin_collection_gui.os.environ", {}, clear=True),
                patch("coin_collection_gui.filedialog.askopenfilename", side_effect=[str(front), str(reverse)]),
                patch("coin_collection_gui.messagebox.askyesno", return_value=True),
                patch("coin_collection_gui.messagebox.showerror") as error,
            ):
                gui.import_coin_images_with_visual_ai()
        self.assertEqual(collection.items, [])
        self.assertEqual(error.call_args.args[0], "AI Identity Service Not Configured")
        self.assertIn("OPENAI_API_KEY is not configured", error.call_args.args[1])

    def test_provider_failure_is_safe_and_does_not_expose_error_or_mutate(self) -> None:
        secret = "sk-secret-should-never-appear"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            front, reverse = self._images(root)
            collection = CoinCollection(str(root / "collection.json"))
            gui = self._gui(collection)
            gui._visual_identity_provider_factory = lambda: _Provider(error=RuntimeError(secret))
            with (
                patch("coin_collection_gui.filedialog.askopenfilename", side_effect=[str(front), str(reverse)]),
                patch("coin_collection_gui.messagebox.askyesno", return_value=True),
                patch("coin_collection_gui.messagebox.showerror") as error,
            ):
                gui.import_coin_images_with_visual_ai()

        self.assertEqual(collection.items, [])
        self.assertNotIn(secret, repr(error.call_args))
        self.assertIn("No collection data was changed", error.call_args.args[1])

    def test_malformed_provider_output_is_zero_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            front, reverse = self._images(root)
            collection = CoinCollection(str(root / "collection.json"))
            gui = self._gui(collection)
            gui._visual_identity_provider_factory = lambda: _Provider(
                error=VisualIdentityContractError("malformed output")
            )
            with (
                patch("coin_collection_gui.filedialog.askopenfilename", side_effect=[str(front), str(reverse)]),
                patch("coin_collection_gui.messagebox.askyesno", return_value=True),
                patch("coin_collection_gui.messagebox.showwarning") as warning,
            ):
                gui.import_coin_images_with_visual_ai()

        self.assertEqual(collection.items, [])
        self.assertIn("malformed output", warning.call_args.args[1])

    def test_reject_and_defer_are_zero_mutation(self) -> None:
        for callback_name in ("on_reject", "on_defer"):
            with self.subTest(callback=callback_name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                front, reverse = self._images(root)
                collection = CoinCollection(str(root / "collection.json"))
                gui = self._gui(collection)
                gui._visual_identity_provider_factory = lambda: _Provider()

                def dialog(**kwargs):
                    kwargs[callback_name]()
                    return object()

                with (
                    patch("coin_collection_gui.filedialog.askopenfilename", side_effect=[str(front), str(reverse)]),
                    patch("coin_collection_gui.messagebox.askyesno", return_value=True),
                    patch("capture_import.desktop_visual_identity_review.create_visual_identity_review_dialog", side_effect=dialog),
                    patch("coin_collection_gui.messagebox.showinfo"),
                ):
                    gui.import_coin_images_with_visual_ai()
                self.assertEqual(collection.items, [])

    def test_final_save_cancellation_after_proposal_is_zero_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            front, reverse = self._images(root)
            collection = CoinCollection(str(root / "collection.json"))
            gui = self._gui(collection)
            gui._visual_identity_provider_factory = lambda: _Provider()

            def dialog(**kwargs):
                kwargs["on_confirm"](
                    ConfirmedVisualIdentity("United States", "50 cents", "1964", "Kennedy")
                )
                return object()

            with (
                patch("coin_collection_gui.filedialog.askopenfilename", side_effect=[str(front), str(reverse)]),
                patch("coin_collection_gui.messagebox.askyesno", side_effect=[True, False]),
                patch("capture_import.desktop_visual_identity_review.create_visual_identity_review_dialog", side_effect=dialog),
                patch("capture_import.reviewed_coin_collection_entry.persist_reviewed_coin") as persist,
            ):
                gui.import_coin_images_with_visual_ai()
        persist.assert_not_called()
        self.assertEqual(collection.items, [])

    def test_persistence_failure_is_zero_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            front, reverse = self._images(root)
            collection = CoinCollection(str(root / "collection.json"))
            gui = self._gui(collection)
            gui._visual_identity_provider_factory = lambda: _Provider()

            def dialog(**kwargs):
                kwargs["on_confirm"](
                    ConfirmedVisualIdentity("United States", "50 cents", "1964", "Kennedy")
                )
                return object()

            with (
                patch("coin_collection_gui.filedialog.askopenfilename", side_effect=[str(front), str(reverse)]),
                patch("coin_collection_gui.messagebox.askyesno", side_effect=[True, True]),
                patch("capture_import.desktop_visual_identity_review.create_visual_identity_review_dialog", side_effect=dialog),
                patch("capture_import.reviewed_coin_collection_entry.persist_reviewed_coin", side_effect=ReviewedCoinPersistenceError("disk unavailable")),
                patch("coin_collection_gui.messagebox.showerror") as error,
            ):
                gui.import_coin_images_with_visual_ai()
        self.assertEqual(collection.items, [])
        self.assertIn("disk unavailable", error.call_args.args[1])

    def test_correct_confirm_save_and_reload_uses_real_managed_photo_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            front, reverse = self._images(root)
            storage = root / "collection.json"
            collection = CoinCollection(str(storage))
            gui = self._gui(collection)
            provider = _Provider()
            gui._visual_identity_provider_factory = lambda: provider
            real_persist = persist_reviewed_coin

            def bounded_persist(**kwargs):
                return real_persist(
                    **kwargs,
                    managed_image_store=ManagedCollectionImageStore(root / "managed"),
                    snapshot_service=CapturePackageSnapshotService(root / "snapshots"),
                    import_lock_path=root / "import.lock",
                )

            def dialog(**kwargs):
                kwargs["on_confirm"](
                    ConfirmedVisualIdentity(
                        "United States", "50 cents", "1964", "Kennedy half dollar"
                    )
                )
                return object()

            with (
                patch("coin_collection_gui.filedialog.askopenfilename", side_effect=[str(front), str(reverse)]),
                patch("coin_collection_gui.messagebox.askyesno", side_effect=[True, True]),
                patch("capture_import.desktop_visual_identity_review.create_visual_identity_review_dialog", side_effect=dialog),
                patch("capture_import.reviewed_coin_collection_entry.persist_reviewed_coin", side_effect=bounded_persist),
                patch("coin_collection_gui.messagebox.showinfo"),
            ):
                gui.import_coin_images_with_visual_ai()

            reopened = CoinCollection(str(storage))
            self.assertEqual(len(provider.requests), 1)
            self.assertEqual(len(reopened.items), 1)
            self.assertEqual(reopened.items[0].country, "United States")
            self.assertEqual(reopened.items[0].denomination, "50 cents")
            self.assertEqual(len(reopened.items[0].photos), 2)
            retained = [
                path
                for path in (root / "managed").rglob("*")
                if path.suffix.casefold() in {".jpg", ".png"}
            ]
            self.assertEqual(len(retained), 2)
            self.assertTrue(
                all("coin-analyzer-image-intake" not in photo.path for photo in reopened.items[0].photos)
            )
            gui.refresh_collection_list.assert_called_once_with()

    def test_file_menu_has_separate_visual_action_and_ocr_path_is_unchanged(self) -> None:
        source = inspect.getsource(CoinCollectionGUI.create_menu_bar)
        self.assertIn("AI-Assisted Coin Images...", source)
        self.assertIn("self.import_coin_images_with_visual_ai", source)
        ocr_source = inspect.getsource(CoinCollectionGUI.import_coin_images_with_ocr)
        self.assertNotIn("visual_identity", ocr_source)
        self.assertNotIn("evidence_fusion", inspect.getsource(CoinCollectionGUI))

    def test_application_initialization_does_not_construct_or_call_provider(self) -> None:
        source = inspect.getsource(CoinCollectionGUI.__init__)
        self.assertIn("self._visual_identity_provider = None", source)
        self.assertNotIn("OpenAITerraVisualIdentityProvider", source)
        self.assertNotIn(".identify(", source)


if __name__ == "__main__":
    unittest.main()
