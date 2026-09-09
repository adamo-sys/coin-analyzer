from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal
from itertools import permutations
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import time
import unittest
from unittest.mock import Mock, patch

from coin_collection import (
    CaptureImportMediaProvenance,
    CoinCollection,
    CoinItem,
    CollectionLoadState,
    IdentificationStatus,
    ItemPhoto,
    ItemType,
    PhotoRole,
)
from collector_work_queue import (
    WorkQueuePriority,
    WorkQueueProjectionError,
    WorkQueueTaskType,
    derive_work_queue,
)


def make_item(item_id="item-1", **overrides):
    values = {
        "id": item_id,
        "image_path": "",
        "country": "Canada",
        "denomination": "5 cents",
        "year": "1899",
        "grade": "",
        "notes": "",
        "date_added": "2026-08-31",
        "identification_status": IdentificationStatus.IDENTIFIED,
        "item_type": ItemType.COIN,
        "photos": [ItemPhoto("front.jpg", PhotoRole.FRONT)],
    }
    values.update(overrides)
    return CoinItem(**values)


def make_collection(items=(), state=CollectionLoadState.LOADED):
    collection = object.__new__(CoinCollection)
    collection.items = list(items)
    collection.load_state = state
    collection.load_error = "private path must not escape"
    collection.save_collection = Mock(name="save_collection")
    return collection


def tasks_of_type(projection, task_type):
    return tuple(task for task in projection.tasks if task.task_type is task_type)


def safe_item_snapshot(item):
    photos = tuple(
        (
            id(photo),
            photo.path,
            photo.role,
            photo.display_order,
            photo.is_primary,
            photo.notes,
            photo.capture_import_media,
        )
        for photo in item.photos
    )
    return (
        id(item.photos),
        item.id,
        item.item_type,
        item.identification_status,
        item.title,
        item.issuer,
        item.country,
        item.denomination,
        item.year,
        item.date_added,
        item.image_path,
        item.purchase_price,
        item.shipping_cost,
        item.buyers_premium,
        item.tax,
        photos,
    )


class TestUnresolvedIdentityRule(unittest.TestCase):
    def test_duplicate_ids_refused(self):
        with self.assertRaises(WorkQueueProjectionError):
            derive_work_queue(make_collection([make_item(), make_item()]))

    def test_non_enum_status_refused(self):
        for value in (None, "PARTIAL", "UNIDENTIFIED"):
            specimen = make_item()
            specimen.identification_status = value
            with self.subTest(value=value), self.assertRaises(WorkQueueProjectionError):
                derive_work_queue(make_collection([specimen]))

    def test_identified_absent(self):
        projection = derive_work_queue(make_collection([make_item()]))
        self.assertFalse(tasks_of_type(projection, WorkQueueTaskType.UNRESOLVED_IDENTITY))

    def test_partial_has_exact_copy_priority_action_and_evidence(self):
        item = make_item(identification_status=IdentificationStatus.PARTIAL)
        task = tasks_of_type(
            derive_work_queue(make_collection([item])),
            WorkQueueTaskType.UNRESOLVED_IDENTITY,
        )[0]
        self.assertEqual(task.title, "Confirm identity")
        self.assertEqual(task.reason, "Identification is partial.")
        self.assertIs(task.priority, WorkQueuePriority.P1)
        self.assertEqual(task.action_label, "Edit identity")
        self.assertEqual(task.evidence, ("identification_status=PARTIAL",))

    def test_unidentified_has_exact_reason(self):
        item = make_item(identification_status=IdentificationStatus.UNIDENTIFIED)
        task = tasks_of_type(
            derive_work_queue(make_collection([item])),
            WorkQueueTaskType.UNRESOLVED_IDENTITY,
        )[0]
        self.assertEqual(task.reason, "Identification has not been established.")
        self.assertEqual(task.evidence, ("identification_status=UNIDENTIFIED",))

    def test_title_does_not_override_authoritative_unidentified_status(self):
        item = make_item(
            title="Apparently complete title",
            identification_status=IdentificationStatus.UNIDENTIFIED,
        )
        projection = derive_work_queue(make_collection([item]))
        self.assertEqual(
            len(tasks_of_type(projection, WorkQueueTaskType.UNRESOLVED_IDENTITY)), 1
        )

    def test_transition_to_identified_removes_only_identity_task(self):
        item = make_item(
            identification_status=IdentificationStatus.UNIDENTIFIED,
            shipping_cost=Decimal("1"),
        )
        before = derive_work_queue(make_collection([item]))
        item.identification_status = IdentificationStatus.IDENTIFIED
        after = derive_work_queue(make_collection([item]))
        self.assertEqual(len(before.tasks), 3)
        self.assertEqual(
            {task.task_type for task in after.tasks},
            {
                WorkQueueTaskType.MISSING_REVERSE_PHOTO,
                WorkQueueTaskType.MISSING_ACQUISITION_PRICE,
            },
        )

    def test_unsupported_status_fails_closed(self):
        item = make_item()
        item.identification_status = "BROKEN"
        with self.assertRaisesRegex(WorkQueueProjectionError, "unsupported identification"):
            derive_work_queue(make_collection([item]))


class TestMissingReversePhotoRule(unittest.TestCase):
    def _has_task(self, item):
        projection = derive_work_queue(make_collection([item]))
        return bool(tasks_of_type(projection, WorkQueueTaskType.MISSING_REVERSE_PHOTO))

    def test_role_matrix(self):
        cases = (
            ([], True),
            ([ItemPhoto("a", PhotoRole.FRONT)], True),
            ([ItemPhoto("a", PhotoRole.OTHER)], True),
            ([ItemPhoto("a", PhotoRole.HOLDER_BACK)], True),
            ([ItemPhoto("a", PhotoRole.BACK)], False),
            ([ItemPhoto("a", PhotoRole.FRONT), ItemPhoto("b", PhotoRole.BACK)], False),
            ([ItemPhoto("a", PhotoRole.BACK), ItemPhoto("b", PhotoRole.BACK)], False),
        )
        for photos, expected in cases:
            with self.subTest(roles=[photo.role for photo in photos]):
                self.assertEqual(self._has_task(make_item(photos=photos)), expected)

    def test_banknote_without_photos_absent(self):
        self.assertFalse(self._has_task(make_item(item_type=ItemType.BANKNOTE, photos=[])))

    def test_alias_and_malformed_roles_follow_normalization(self):
        reverse = ItemPhoto("reverse.jpg", PhotoRole.OTHER)
        reverse.role = "reverse"
        malformed = ItemPhoto("unknown.jpg", PhotoRole.OTHER)
        malformed.role = "not-a-role"
        self.assertFalse(self._has_task(make_item(photos=[reverse])))
        self.assertTrue(self._has_task(make_item(photos=[malformed])))

    def test_legacy_string_and_dict_shapes_are_defensive_and_detached(self):
        item = make_item(photos=[])
        item.photos = [
            "front.jpg",
            {"file_path": "back.jpg", "photo_role": "REVERSE"},
        ]
        self.assertFalse(self._has_task(item))
        self.assertIsInstance(item.photos[0], str)
        self.assertIsInstance(item.photos[1], dict)

    def test_legacy_image_path_is_other(self):
        item = make_item(photos=[], image_path="legacy-back-filename.jpg")
        self.assertTrue(self._has_task(item))

    def test_structured_photos_take_precedence_over_legacy_image_path(self):
        item = make_item(
            photos=[ItemPhoto("front.jpg", PhotoRole.FRONT)],
            image_path="reverse.jpg",
        )
        self.assertTrue(self._has_task(item))

    def test_filename_path_primary_and_order_do_not_infer_back(self):
        photo = ItemPhoto(
            "C:/managed/reverse-back.jpg",
            PhotoRole.FRONT,
            is_primary=True,
            display_order=-999,
        )
        self.assertTrue(self._has_task(make_item(photos=[photo])))

    def test_ownership_existence_and_provenance_do_not_change_back_role(self):
        provenance = CaptureImportMediaProvenance(
            schema_version="1.0",
            import_id="12345678-1234-4234-8234-123456789abc",
            source_kind="PROCESSED_SNAPSHOT",
            package_sha256="a" * 64,
            processed_snapshot_id="abcdefab-cdef-4def-8def-abcdefabcdef",
            artifact_key="artifact",
            artifact_sha256="b" * 64,
            variant="NORMALIZED",
        )
        photo = ItemPhoto(
            "Z:/missing/external.jpg",
            PhotoRole.BACK,
            capture_import_media=provenance,
        )
        self.assertFalse(self._has_task(make_item(photos=[photo])))

    def test_blank_paths_are_ignored(self):
        item = make_item(photos=[])
        blank = ItemPhoto("placeholder", PhotoRole.BACK)
        blank.path = "   "
        item.photos = [blank]
        self.assertTrue(self._has_task(item))

    def test_evidence_counts_effective_photos_only(self):
        item = make_item(
            photos=[
                ItemPhoto("a", PhotoRole.FRONT),
                ItemPhoto("b", PhotoRole.HOLDER_BACK),
            ]
        )
        task = tasks_of_type(
            derive_work_queue(make_collection([item])),
            WorkQueueTaskType.MISSING_REVERSE_PHOTO,
        )[0]
        self.assertEqual(task.evidence, ("photo_count=2", "back_role_count=0"))


class TestMissingAcquisitionPriceRule(unittest.TestCase):
    def _tasks(self, **overrides):
        projection = derive_work_queue(make_collection([make_item(**overrides)]))
        return tasks_of_type(projection, WorkQueueTaskType.MISSING_ACQUISITION_PRICE)

    def test_each_ancillary_field_including_zero_triggers(self):
        for field in ("shipping_cost", "buyers_premium", "tax"):
            for value in (Decimal("4.25"), Decimal("0")):
                with self.subTest(field=field, value=value):
                    self.assertEqual(len(self._tasks(**{field: value})), 1)

    def test_multiple_costs_make_exactly_one_task_with_fixed_evidence_order(self):
        task = self._tasks(
            shipping_cost=Decimal("1"),
            buyers_premium=Decimal("2"),
            tax=Decimal("3"),
        )[0]
        self.assertEqual(
            task.evidence,
            (
                "shipping_cost_present",
                "buyers_premium_present",
                "tax_present",
                "purchase_price_missing",
            ),
        )

    def test_present_purchase_price_including_zero_resolves(self):
        for value in (Decimal("10"), Decimal("0")):
            with self.subTest(value=value):
                self.assertFalse(
                    self._tasks(purchase_price=value, shipping_cost=Decimal("1"))
                )

    def test_non_authoritative_context_does_not_trigger(self):
        cases = (
            {"acquisition_date": "2025-01-01"},
            {"purchase_source": "dealer"},
            {"notes": "purchased from dealer"},
            {"notes": "gift inheritance"},
            {"purchase_currency": None},
        )
        for values in cases:
            with self.subTest(values=values):
                self.assertFalse(self._tasks(**values))

    def test_free_text_does_not_suppress_explicit_cost_evidence(self):
        self.assertEqual(
            len(self._tasks(notes="gift", shipping_cost=Decimal("0"))), 1
        )


class TestTaskIdentityAndDTOs(unittest.TestCase):
    def test_exact_identity_contains_version_type_and_full_colon_id(self):
        item = make_item("specimen:with:colons", photos=[])
        task = tasks_of_type(
            derive_work_queue(make_collection([item])),
            WorkQueueTaskType.MISSING_REVERSE_PHOTO,
        )[0]
        self.assertEqual(
            task.task_id,
            "work-queue:1:MISSING_REVERSE_PHOTO:specimen:with:colons",
        )
        self.assertEqual(task.item_id, "specimen:with:colons")
        self.assertEqual(task.rule_version, 1)

    def test_equivalent_reconstruction_and_recurrence_are_stable(self):
        first = make_item("stable", photos=[])
        first_id = tasks_of_type(
            derive_work_queue(make_collection([first])),
            WorkQueueTaskType.MISSING_REVERSE_PHOTO,
        )[0].task_id
        resolved = make_item("stable", photos=[ItemPhoto("b", PhotoRole.BACK)])
        self.assertFalse(
            tasks_of_type(
                derive_work_queue(make_collection([resolved])),
                WorkQueueTaskType.MISSING_REVERSE_PHOTO,
            )
        )
        returning = make_item("stable", photos=[])
        returned_id = tasks_of_type(
            derive_work_queue(make_collection([returning])),
            WorkQueueTaskType.MISSING_REVERSE_PHOTO,
        )[0].task_id
        self.assertEqual(first_id, returned_id)

    def test_different_items_and_task_types_do_not_collide(self):
        items = [
            make_item("a", photos=[], identification_status=IdentificationStatus.PARTIAL),
            make_item("b", photos=[], identification_status=IdentificationStatus.PARTIAL),
        ]
        tasks = derive_work_queue(make_collection(items)).tasks
        ids = [task.task_id for task in tasks]
        self.assertEqual(len(ids), len(set(ids)))

    def test_dtos_are_frozen_hashable_and_evidence_is_tuple(self):
        projection = derive_work_queue(make_collection([make_item(photos=[])]))
        task = projection.tasks[0]
        hash(task)
        hash(projection)
        self.assertIsInstance(task.evidence, tuple)
        with self.assertRaises(FrozenInstanceError):
            task.title = "changed"

    def test_counts_include_all_types_in_fixed_order_even_at_zero(self):
        projection = derive_work_queue(
            make_collection([make_item(photos=[ItemPhoto("b", PhotoRole.BACK)])])
        )
        self.assertEqual(
            projection.counts_by_type,
            tuple((task_type, 0) for task_type in WorkQueueTaskType),
        )

    def test_blank_item_id_fails_closed(self):
        item = make_item()
        item.id = " "
        with self.assertRaisesRegex(WorkQueueProjectionError, "nonblank stable"):
            derive_work_queue(make_collection([item]))


class TestDisplayIdentity(unittest.TestCase):
    def _display(self, **overrides):
        item = make_item(photos=[], **overrides)
        return derive_work_queue(make_collection([item])).tasks[0].display_identity

    def test_trimmed_title_wins_without_appending_other_fields(self):
        self.assertEqual(self._display(title="  Stored title  "), "Stored title")

    def test_issuer_wins_country_and_separator_is_frozen(self):
        self.assertEqual(
            self._display(issuer=" Royal Mint ", country="Canada"),
            "Royal Mint · 5 cents · 1899",
        )

    def test_country_fallback_and_unicode_survive(self):
        self.assertEqual(
            self._display(issuer="", country="México", denomination="½ real", year=" año 1 "),
            "México · ½ real · año 1",
        )

    def test_partial_components_are_not_fabricated(self):
        self.assertEqual(
            self._display(country="", issuer="", denomination="Token", year=""),
            "Token",
        )

    def test_type_aware_fallbacks(self):
        blank = {"title": "", "issuer": "", "country": "", "denomination": "", "year": ""}
        self.assertEqual(self._display(**blank), "Unidentified coin")
        self.assertEqual(
            self._display(
                item_type=ItemType.BANKNOTE,
                identification_status=IdentificationStatus.UNIDENTIFIED,
                **blank,
            ),
            "Unidentified banknote",
        )


class TestOrderingAndDeterminism(unittest.TestCase):
    def test_priority_and_task_type_order(self):
        item = make_item(
            "multi",
            photos=[],
            identification_status=IdentificationStatus.PARTIAL,
            shipping_cost=Decimal("1"),
        )
        projection = derive_work_queue(make_collection([item]))
        self.assertEqual(
            [task.task_type for task in projection.tasks],
            list(WorkQueueTaskType),
        )

    def test_date_contract_and_stable_id_tie_break(self):
        dates = {
            "date": "2026-08-31",
            "space": "2026-08-31 22:15:00",
            "tee": "2026-08-31T22:15:00",
            "zone": "2026-08-31T22:15:00-04:00",
            "older": "2025-01-02 anything",
            "impossible": "2026-02-30",
            "locale": "31/08/2026",
            "short": "2026-8-1",
            "embedded": "abc2026-08-31",
            "blank": "",
        }
        items = [make_item(item_id, photos=[], date_added=value) for item_id, value in dates.items()]
        tasks = tasks_of_type(
            derive_work_queue(make_collection(items)),
            WorkQueueTaskType.MISSING_REVERSE_PHOTO,
        )
        self.assertEqual(
            [task.item_id for task in tasks],
            [
                "older",
                "date",
                "space",
                "tee",
                "zone",
                "blank",
                "embedded",
                "impossible",
                "locale",
                "short",
            ],
        )

    def test_all_input_permutations_produce_identical_order(self):
        items = [
            make_item("c", photos=[], date_added=""),
            make_item("a", photos=[], date_added="2020-01-01"),
            make_item("b", photos=[], date_added="2020-01-01T23:59"),
        ]
        orders = {
            tuple(task.task_id for task in derive_work_queue(make_collection(order)).tasks)
            for order in permutations(items)
        }
        self.assertEqual(len(orders), 1)

    def test_unrelated_field_changes_do_not_change_task_identity_or_eligibility(self):
        item = make_item("stable", photos=[])
        before = derive_work_queue(make_collection([item])).tasks
        item.grade = "MS 65"
        item.notes = "unrelated"
        after = derive_work_queue(make_collection([item])).tasks
        self.assertEqual(
            [(task.task_id, task.task_type) for task in before],
            [(task.task_id, task.task_type) for task in after],
        )


class TestProjectionStateAndSafety(unittest.TestCase):
    def test_missing_returns_empty_missing_projection(self):
        collection = make_collection([], CollectionLoadState.MISSING)
        projection = derive_work_queue(collection)
        self.assertIs(projection.collection_state, CollectionLoadState.MISSING)
        self.assertEqual(projection.tasks, ())
        self.assertEqual([count for _, count in projection.counts_by_type], [0, 0, 0])

    def test_invalid_fails_closed_without_leaking_load_error(self):
        collection = make_collection([], CollectionLoadState.FAILED)
        with self.assertRaises(WorkQueueProjectionError) as raised:
            derive_work_queue(collection)
        self.assertNotIn(collection.load_error, str(raised.exception))
        self.assertIn("FAILED", str(raised.exception))

    def test_unknown_state_fails_closed(self):
        collection = make_collection([])
        collection.load_state = "VALID"
        with self.assertRaises(WorkQueueProjectionError):
            derive_work_queue(collection)

    def test_projection_does_not_call_save_or_filesystem_writes(self):
        collection = make_collection([make_item(photos=[])])
        with patch("builtins.open") as open_mock, patch("os.makedirs") as mkdir_mock:
            derive_work_queue(collection)
        collection.save_collection.assert_not_called()
        open_mock.assert_not_called()
        mkdir_mock.assert_not_called()

    def test_authoritative_item_and_photo_metadata_are_unchanged(self):
        photos = [
            ItemPhoto("later.jpg", PhotoRole.FRONT, False, "later", 99),
            ItemPhoto("earlier.jpg", PhotoRole.OTHER, True, "earlier", -7),
        ]
        item = make_item(
            photos=photos,
            image_path="legacy.jpg",
            identification_status=IdentificationStatus.PARTIAL,
            shipping_cost=Decimal("0"),
        )
        collection = make_collection([item])
        before = safe_item_snapshot(item)
        first = derive_work_queue(collection)
        middle = safe_item_snapshot(item)
        second = derive_work_queue(collection)
        after = safe_item_snapshot(item)
        self.assertEqual(before, middle)
        self.assertEqual(before, after)
        self.assertEqual(first, second)
        collection.save_collection.assert_not_called()

    def test_derivation_creates_no_files_or_directories(self):
        collection = make_collection([make_item(photos=[])])
        with TemporaryDirectory() as directory:
            before = set(Path(directory).iterdir())
            previous = os.getcwd()
            try:
                os.chdir(directory)
                derive_work_queue(collection)
            finally:
                os.chdir(previous)
            self.assertEqual(set(Path(directory).iterdir()), before)


class TestPerformanceDiagnostics(unittest.TestCase):
    def test_five_thousand_item_projection_has_linear_bounded_work(self):
        items = []
        for index in range(5000):
            items.append(
                make_item(
                    f"synthetic-{index:05d}",
                    photos=[] if index % 2 else [ItemPhoto("back", PhotoRole.BACK)],
                    identification_status=(
                        IdentificationStatus.PARTIAL
                        if index % 3 == 0
                        else IdentificationStatus.IDENTIFIED
                    ),
                    shipping_cost=Decimal("0") if index % 5 == 0 else None,
                )
            )
        started = time.perf_counter()
        projection = derive_work_queue(make_collection(items))
        elapsed = time.perf_counter() - started
        self.assertGreater(len(projection.tasks), 0)
        self.assertLess(elapsed, 10.0, "diagnostic guard against accidental superlinear work")


if __name__ == "__main__":
    unittest.main()
