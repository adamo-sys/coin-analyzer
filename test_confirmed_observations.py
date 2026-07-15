"""Tests for durable, collector-confirmed observation records."""

import ast
import json
import os
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import Mock, patch

from coin_collection_gui import CoinCollectionGUI
from confirmed_observations import (
    CONFIRMED_OBSERVATIONS_FILENAME,
    ConfirmedObservationRecord,
    ConfirmedObservationStore,
    FeedbackCategory,
    ObservationOutcome,
)


def make_record(
    observation_id="observation-1",
    outcome=ObservationOutcome.ACCEPTED,
    category=FeedbackCategory.OTHER,
    created_at="2026-07-15T12:00:00Z",
):
    return ConfirmedObservationRecord(
        observation_id=observation_id,
        created_at=created_at,
        outcome=outcome,
        category=category,
        suggested_values={"country": "Canada", "year": "1907"},
        confirmed_values={} if outcome in {ObservationOutcome.DEFERRED, ObservationOutcome.REJECTED} else {
            "country": "Canada",
            "year": "1907",
        },
        engine_name="coin_recognition",
        engine_version="unknown",
        recognition_method="coin_recognition",
        application_version="v8.8.0",
        photo_references=("front.jpg", "back.jpg"),
        evidence_snapshot={"confidence": 0.8, "reason": "Date visible"},
        source_workflow="test",
        collector_note="Confirmed by collector",
    )


class _Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _Text:
    def __init__(self, value=""):
        self.value = value

    def get(self, *_args):
        return self.value


class _App:
    def __init__(self, should_save):
        self.current_image_path = "front.jpg"
        self.last_added_item_id = "item-1"
        self.should_save = should_save
        self.calls = 0

    def add_to_collection(self, *_args, **_kwargs):
        self.calls += 1
        return self.should_save


class ConfirmedObservationTests(unittest.TestCase):
    def make_gui(self, should_save=True, country="Canada"):
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.app = _App(should_save)
        gui.country_var = _Value(country)
        gui.denomination_var = _Value("25 cents")
        gui.year_var = _Value("1907")
        gui.grade_var = _Value("VF-20")
        gui.notes_text = _Text("notes")
        gui.current_item_photos = []
        gui.pending_inbox_manager = None
        gui.pending_inbox_photo_set_id = ""
        gui.detection_result = {
            "success": True,
            "country": "Canada",
            "denomination": "25 cents",
            "year": "1907",
            "confidence": 0.8,
            "year_confidence": 0.9,
            "method": "coin_recognition",
        }
        gui.sync_current_image_path_from_photos = Mock()
        gui.record_detection_observation_after_save = Mock()
        gui.log_correction = Mock()
        gui.clear_form = Mock()
        gui.refresh_collection_list = Mock()
        return gui

    def test_deterministic_dto_serialization_and_unicode_round_trip(self):
        record = make_record()
        first = record.to_dict()
        second = record.to_dict()

        self.assertEqual(first, second)
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ConfirmedObservationStore(os.path.join(temp_dir, CONFIRMED_OBSERVATIONS_FILENAME))
            unicode_record = ConfirmedObservationRecord(
                **{**record.__dict__, "observation_id": "unicode", "collector_note": "Piece de collection: epreuve"}
            )
            self.assertTrue(store.append(unicode_record).success)
            self.assertEqual("Piece de collection: epreuve", store.load().records[0].collector_note)

    def test_all_outcomes_validate_and_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ConfirmedObservationStore(os.path.join(temp_dir, CONFIRMED_OBSERVATIONS_FILENAME))
            outcomes = list(ObservationOutcome)
            for index, outcome in enumerate(outcomes):
                result = store.append(make_record(
                    observation_id=f"outcome-{outcome.value}",
                    outcome=outcome,
                    category=FeedbackCategory.OTHER,
                    created_at=f"2026-07-15T12:00:0{index}Z",
                ))
                self.assertTrue(result.success)
            self.assertEqual(outcomes, [record.outcome for record in store.load().records])

    def test_accepted_and_corrected_detection_save_semantics(self):
        accepted = ConfirmedObservationRecord.for_detection_save(
            {"country": "Canada", "denomination": "25 cents", "year": "1907", "method": "test"},
            {"country": "Canada", "denomination": "25 cents", "year": "1907"},
            "item-accepted",
            "v8.8.0",
            created_at="2026-07-15T12:00:00Z",
        )
        corrected = ConfirmedObservationRecord.for_detection_save(
            {"country": "Canada", "denomination": "25 cents", "year": "1908", "method": "test"},
            {"country": "Canada", "denomination": "25 cents", "year": "1907"},
            "item-corrected",
            "v8.8.0",
            created_at="2026-07-15T12:00:01Z",
        )

        self.assertEqual(ObservationOutcome.ACCEPTED, accepted.outcome)
        self.assertEqual(ObservationOutcome.CORRECTED, corrected.outcome)
        self.assertEqual(FeedbackCategory.IDENTIFICATION_MISMATCH, corrected.category)

    def test_observation_ids_are_immutable(self):
        record = make_record()
        with self.assertRaises(FrozenInstanceError):
            record.observation_id = "changed"

    def test_idempotent_duplicate_write_and_conflicting_id_rejection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ConfirmedObservationStore(os.path.join(temp_dir, CONFIRMED_OBSERVATIONS_FILENAME))
            first = make_record()
            retry = ConfirmedObservationRecord(**{**first.__dict__, "created_at": "2026-07-15T12:05:00Z"})

            self.assertTrue(store.append(first).success)
            repeated = store.append(retry)
            self.assertTrue(repeated.success)
            self.assertTrue(repeated.already_recorded)
            self.assertEqual(1, len(store.load().records))

            conflicting = ConfirmedObservationRecord(**{
                **first.__dict__,
                "confirmed_values": {"country": "Canada", "year": "1908"},
            })
            self.assertFalse(store.append(conflicting).success)
            self.assertEqual(1, len(store.load().records))

    def test_malformed_and_unsupported_store_is_tolerated_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, CONFIRMED_OBSERVATIONS_FILENAME)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"schema_version": "1", "records": [make_record().to_dict(), {"bad": "record"}]}, handle)
            store = ConfirmedObservationStore(path)

            loaded = store.load()
            self.assertTrue(loaded.success)
            self.assertEqual(1, len(loaded.records))
            self.assertTrue(loaded.warnings)
            self.assertFalse(store.append(make_record("new-id")).success)

            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"schema_version": "99", "records": []}, handle)
            unsupported = store.load()
            self.assertFalse(unsupported.success)
            self.assertIn("Unsupported observation store schema version", unsupported.errors[0])

    def test_atomic_write_and_replace_failures_leave_previous_document_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, CONFIRMED_OBSERVATIONS_FILENAME)
            store = ConfirmedObservationStore(path)
            self.assertTrue(store.append(make_record()).success)
            with open(path, "rb") as handle:
                original = handle.read()

            with patch("atomic_json.json.dump", side_effect=OSError("write failed")):
                write_failure = store.append(make_record("write-failure"))
            self.assertFalse(write_failure.success)
            with open(path, "rb") as handle:
                self.assertEqual(original, handle.read())
            self.assertEqual([], list(Path(temp_dir).glob("*.tmp")))

            with patch("atomic_json.os.replace", side_effect=OSError("replace failed")):
                replace_failure = store.append(make_record("replace-failure"))
            self.assertFalse(replace_failure.success)
            with open(path, "rb") as handle:
                self.assertEqual(original, handle.read())
            self.assertEqual([], list(Path(temp_dir).glob("*.tmp")))

    def test_injected_path_never_touches_live_collection_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "private", CONFIRMED_OBSERVATIONS_FILENAME)
            store = ConfirmedObservationStore(path)
            self.assertTrue(store.append(make_record()).success)
            self.assertTrue(os.path.exists(path))
            self.assertFalse(os.path.exists(os.path.join("data", "confirmed_observations.json")))

    def test_successful_detection_save_records_once_and_failed_or_invalid_save_records_nothing(self):
        successful = self.make_gui(should_save=True)
        with patch("coin_collection_gui.messagebox.showinfo"):
            successful.save_to_collection()
        successful.record_detection_observation_after_save.assert_called_once()

        failed = self.make_gui(should_save=False)
        with patch("coin_collection_gui.messagebox.showerror"):
            failed.save_to_collection()
        failed.record_detection_observation_after_save.assert_not_called()

        invalid = self.make_gui(should_save=True, country="")
        with patch("coin_collection_gui.messagebox.showwarning"):
            invalid.save_to_collection()
        self.assertEqual(0, invalid.app.calls)
        invalid.record_detection_observation_after_save.assert_not_called()

    def test_gui_post_save_hook_writes_confirmed_observation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
            gui.app = _App(True)
            gui.detection_result = {
                "success": True,
                "country": "Canada",
                "denomination": "25 cents",
                "year": "1907",
                "confidence": 0.8,
                "method": "coin_recognition",
            }
            gui.confirmed_observation_store = ConfirmedObservationStore(
                os.path.join(temp_dir, CONFIRMED_OBSERVATIONS_FILENAME)
            )

            result = gui.record_detection_observation_after_save("Canada", "25 cents", "1907", [])

            self.assertTrue(result.success)
            self.assertEqual(ObservationOutcome.ACCEPTED, gui.confirmed_observation_store.load().records[0].outcome)

    def test_production_engines_do_not_import_the_store(self):
        allowed_consumers = {"confirmed_observations.py", "coin_collection_gui.py", "backup_manager.py"}
        for path in Path(".").glob("*.py"):
            if path.name.startswith("test_") or path.name in allowed_consumers:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                imported = []
                if isinstance(node, ast.Import):
                    imported = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imported = [node.module or ""]
                self.assertNotIn("confirmed_observations", imported, f"Unexpected store dependency in {path}")


if __name__ == "__main__":
    unittest.main()
