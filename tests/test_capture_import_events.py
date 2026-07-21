"""Tests for the structured import event system."""

from __future__ import annotations

import json
import unittest

from capture_import.events import (
    EventSeverity,
    EventType,
    ImportEvent,
    ImportEventBus,
)


class EventTypeAndSeverityTests(unittest.TestCase):
    def test_all_event_types_are_unique(self) -> None:
        values = [e.value for e in EventType]
        self.assertEqual(len(values), len(set(values)))

    def test_all_severities_are_ordered(self) -> None:
        expected = [
            EventSeverity.DEBUG,
            EventSeverity.INFO,
            EventSeverity.WARNING,
            EventSeverity.ERROR,
            EventSeverity.CRITICAL,
        ]
        self.assertEqual(list(EventSeverity), expected)


class ImportEventTests(unittest.TestCase):
    def test_event_is_frozen(self) -> None:
        event = ImportEvent(
            event_type=EventType.IMPORT_STARTED,
            timestamp="2026-07-21T12:00:00Z",
            import_id="test-id",
            severity=EventSeverity.INFO,
        )
        with self.assertRaises(AttributeError):
            event.timestamp = "other"

    def test_to_dict_is_json_serializable(self) -> None:
        event = ImportEvent(
            event_type=EventType.IMAGES_IMPORTED,
            timestamp="2026-07-21T12:00:00Z",
            import_id="id",
            severity=EventSeverity.INFO,
            context={"image_count": 3, "paths": ("a.jpg", "b.png")},
        )
        data = event.to_dict()
        text = json.dumps(data)
        restored = json.loads(text)
        self.assertEqual(restored["event_type"], "IMAGES_IMPORTED")
        self.assertEqual(restored["context"]["image_count"], 3)


class ImportEventBusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = ImportEventBus(clock=lambda: "2026-07-21T12:00:00Z")

    def test_empty_bus_has_no_events(self) -> None:
        self.assertEqual(len(self.bus), 0)
        self.assertFalse(self.bus)
        self.assertIsNone(self.bus.latest())
        self.assertEqual(self.bus.events, ())

    def test_record_appends_and_returns_event(self) -> None:
        event = self.bus.record(
            EventType.IMPORT_STARTED,
            import_id="i1",
            severity=EventSeverity.INFO,
            proposed_count=5,
        )
        self.assertIs(event.event_type, EventType.IMPORT_STARTED)
        self.assertEqual(event.import_id, "i1")
        self.assertEqual(event.context["proposed_count"], 5)
        self.assertEqual(len(self.bus), 1)
        self.assertIs(self.bus.latest(), event)

    def test_convenience_methods_record_typed_events(self) -> None:
        self.bus.record_started(
            import_id="i1",
            package_basename="pkg.ca-package",
            proposed_count=3,
        )
        self.bus.record_validated(
            import_id="i1",
            package_sha256="abc",
            package_byte_length=1024,
        )
        self.bus.record_collection_created(
            import_id="i1",
            journal_phase="PREPARED",
        )
        self.bus.record_images_imported(
            import_id="i1",
            image_count=2,
            created_relative_paths=("a.jpg", "b.jpg"),
        )
        self.bus.record_collection_committed(
            import_id="i1",
            committed_count=2,
            desktop_item_ids=("d1", "d2"),
        )
        self.bus.record_complete(
            import_id="i1",
            status="SUCCEEDED",
            imported_count=2,
            skipped_count=1,
            image_count=2,
        )
        self.assertEqual(len(self.bus), 6)
        types = [e.event_type for e in self.bus.events]
        self.assertEqual(
            types,
            [
                EventType.IMPORT_STARTED,
                EventType.PACKAGE_VALIDATED,
                EventType.COLLECTION_CREATED,
                EventType.IMAGES_IMPORTED,
                EventType.COLLECTION_COMMITTED,
                EventType.IMPORT_COMPLETE,
            ],
        )

    def test_rollback_and_recovery_events(self) -> None:
        self.bus.record_rollback_started(import_id="i1", reason="commit failed")
        self.bus.record_rollback_complete(import_id="i1", status="ROLLED_BACK")
        self.bus.record_recovery_triggered(
            import_id="i1",
            journal_phase="FILES_READY",
            recovery_attempt_count=1,
        )
        self.bus.record_recovery_complete(import_id="i1", final_phase="ROLLED_BACK")
        severities = [e.severity for e in self.bus.events]
        self.assertEqual(severities[0], EventSeverity.WARNING)
        self.assertEqual(severities[1], EventSeverity.INFO)
        self.assertEqual(severities[2], EventSeverity.WARNING)
        self.assertEqual(severities[3], EventSeverity.INFO)

    def test_progress_events_are_debug(self) -> None:
        self.bus.record_progress(
            import_id="i1", stage="copy", current=2, total=5
        )
        event = self.bus.latest()
        self.assertIsNotNone(event)
        assert event is not None
        self.assertIs(event.severity, EventSeverity.DEBUG)
        self.assertEqual(event.context["stage"], "copy")
        self.assertEqual(event.context["current"], 2)
        self.assertEqual(event.context["total"], 5)

    def test_by_type_filter(self) -> None:
        self.bus.record_started(import_id="i1", package_basename="x", proposed_count=1)
        self.bus.record_progress(import_id="i1", stage="copy", current=1, total=2)
        self.bus.record_progress(import_id="i1", stage="copy", current=2, total=2)
        self.bus.record_complete(
            import_id="i1", status="SUCCEEDED", imported_count=1, skipped_count=0, image_count=1
        )
        progress = self.bus.by_type(EventType.PROGRESS)
        self.assertEqual(len(progress), 2)
        self.assertTrue(all(e.event_type is EventType.PROGRESS for e in progress))

    def test_by_severity_filter(self) -> None:
        self.bus.record(EventType.IMPORT_STARTED, import_id="i1", severity=EventSeverity.DEBUG)
        self.bus.record(EventType.PACKAGE_VALIDATED, import_id="i1", severity=EventSeverity.INFO)
        self.bus.record(EventType.ROLLBACK_STARTED, import_id="i1", severity=EventSeverity.WARNING)
        self.bus.record(EventType.IMPORT_COMPLETE, import_id="i1", severity=EventSeverity.ERROR)
        warnings_and_above = self.bus.by_severity(EventSeverity.WARNING)
        self.assertEqual(len(warnings_and_above), 2)
        self.assertTrue(
            all(e.severity in {EventSeverity.WARNING, EventSeverity.ERROR} for e in warnings_and_above)
        )

    def test_to_dicts_serializes_all_events(self) -> None:
        self.bus.record_started(import_id="i1", package_basename="x", proposed_count=1)
        dicts = self.bus.to_dicts()
        self.assertEqual(len(dicts), 1)
        self.assertEqual(dicts[0]["event_type"], "IMPORT_STARTED")
        self.assertEqual(dicts[0]["import_id"], "i1")

    def test_events_are_immutable_tuple(self) -> None:
        self.bus.record_started(import_id="i1", package_basename="x", proposed_count=1)
        events = self.bus.events
        with self.assertRaises(TypeError):
            events[0] = events[0]  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
