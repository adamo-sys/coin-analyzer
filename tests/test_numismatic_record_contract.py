"""Focused tests for the versioned authoritative numismatic record contract."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from coin_collection import (
    CollectionFormat,
    CollectionLoadState,
    CoinCollection,
    CoinItem,
    Disposition,
    IdentificationStatus,
    ItemType,
)
from collection_management.collection_mutation_repository import (
    ConditionalCollectionFieldChange,
)


T1 = "2026-08-30T12:00:00.000001Z"
T2 = "2026-08-30T12:01:00.000002Z"


def legacy_record(
    item_id: str = "coin_existing",
    *,
    country: str = "Canada",
    denomination: str = "25 cents",
    year: str = "1967",
) -> dict[str, object]:
    return {
        "id": item_id,
        "image_path": "",
        "country": country,
        "denomination": denomination,
        "year": year,
        "grade": "",
        "notes": "",
        "date_added": "2026-08-30",
    }


def new_item(
    item_id: str,
    *,
    item_type: ItemType = ItemType.COIN,
    disposition: Disposition = Disposition.UNDECIDED,
    identification_status: IdentificationStatus | None = None,
    updated_at: str = T1,
) -> CoinItem:
    return CoinItem(
        id=item_id,
        image_path="",
        country="France" if item_type is ItemType.COIN else "Germany",
        denomination="2 euro" if item_type is ItemType.COIN else "100 marks",
        year="2002" if item_type is ItemType.COIN else "Series 1920",
        grade="",
        notes="",
        date_added="2026-08-30",
        issuer="Banque de France" if item_type is ItemType.COIN else "Reichsbank",
        title="Type record",
        reference="REF-1",
        item_type=item_type,
        disposition=disposition,
        identification_status=identification_status,
        updated_at=updated_at,
    )


class VersionedNumismaticRecordContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "collection.json"

    def write(self, payload: object) -> bytes:
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        return self.path.read_bytes()

    def load(self) -> CoinCollection:
        return CoinCollection(str(self.path))

    def test_legacy_v0_defaults_identity_and_read_only_bytes(self) -> None:
        records = [
            legacy_record("coin_complete"),
            legacy_record("coin_partial", denomination="", year=""),
            legacy_record("coin_blank", country="", denomination="", year=""),
        ]
        source = self.write(records)

        collection = self.load()

        self.assertIs(collection.load_state, CollectionLoadState.VALID)
        self.assertIs(collection.collection_format, CollectionFormat.LEGACY_V0)
        self.assertEqual(source, self.path.read_bytes())
        self.assertEqual(
            ["coin_complete", "coin_partial", "coin_blank"],
            [item.id for item in collection.items],
        )
        self.assertTrue(all(item.item_type is ItemType.COIN for item in collection.items))
        self.assertTrue(
            all(item.disposition is Disposition.UNDECIDED for item in collection.items)
        )
        self.assertEqual(
            [
                IdentificationStatus.IDENTIFIED,
                IdentificationStatus.PARTIAL,
                IdentificationStatus.UNIDENTIFIED,
            ],
            [item.identification_status for item in collection.items],
        )
        self.assertTrue(all(item.updated_at is None for item in collection.items))

    def test_legacy_save_transitions_to_v1_without_changing_id_or_timestamp(self) -> None:
        self.write([legacy_record("coin_unchanged")])
        collection = self.load()

        self.assertTrue(collection.save_collection())

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(1, payload["schema_version"])
        self.assertEqual("coin_unchanged", payload["items"][0]["id"])
        self.assertEqual("COIN", payload["items"][0]["item_type"])
        self.assertEqual("UNDECIDED", payload["items"][0]["disposition"])
        self.assertEqual("IDENTIFIED", payload["items"][0]["identification_status"])
        self.assertNotIn("updated_at", payload["items"][0])
        self.assertIs(collection.collection_format, CollectionFormat.V1)

    def test_legacy_mutation_preserves_id_and_sets_updated_at(self) -> None:
        self.write([legacy_record("coin_stable")])
        collection = self.load()

        with patch("coin_collection.utc_now_rfc3339", return_value=T1):
            self.assertTrue(collection.update_item("coin_stable", {"grade": "VF"}))

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual("coin_stable", payload["items"][0]["id"])
        self.assertEqual(T1, payload["items"][0]["updated_at"])
        self.assertEqual("coin_stable", self.load().items[0].id)

    def test_missing_first_save_writes_v1(self) -> None:
        collection = self.load()

        self.assertIs(collection.load_state, CollectionLoadState.MISSING)
        self.assertTrue(collection.save_collection())

        self.assertEqual(
            {"schema_version": 1, "items": []},
            json.loads(self.path.read_text(encoding="utf-8")),
        )

    def test_valid_v1_loads_and_remains_v1_on_save(self) -> None:
        record = new_item("coin_v1").to_dict()
        self.write({"schema_version": 1, "items": [record]})

        collection = self.load()

        self.assertIs(collection.load_state, CollectionLoadState.VALID)
        self.assertIs(collection.collection_format, CollectionFormat.V1)
        self.assertTrue(collection.save_collection())
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(1, payload["schema_version"])
        self.assertEqual("coin_v1", payload["items"][0]["id"])

    def test_new_coin_and_banknote_round_trip_at_model_and_v1_levels(self) -> None:
        coin = new_item("coin_new")
        banknote = new_item("note_new", item_type=ItemType.BANKNOTE)

        model_round_trip = CoinItem.from_dict(banknote.to_dict())
        self.assertIs(model_round_trip.item_type, ItemType.BANKNOTE)
        self.assertEqual("Germany", model_round_trip.country)
        self.assertEqual("Reichsbank", model_round_trip.issuer)
        self.assertEqual("Series 1920", model_round_trip.year)

        collection = self.load()
        collection.items = [coin, banknote]
        self.assertTrue(collection.save_collection())
        reloaded = self.load()
        self.assertEqual(
            [ItemType.COIN, ItemType.BANKNOTE],
            [item.item_type for item in reloaded.items],
        )

    def test_all_dispositions_and_identification_statuses_round_trip(self) -> None:
        for disposition in Disposition:
            with self.subTest(disposition=disposition.value):
                value = new_item("item_disposition", disposition=disposition)
                self.assertIs(
                    CoinItem.from_dict(value.to_dict()).disposition, disposition
                )
        for status in IdentificationStatus:
            with self.subTest(identification_status=status.value):
                value = new_item(
                    "item_status", identification_status=status
                )
                self.assertIs(
                    CoinItem.from_dict(value.to_dict()).identification_status,
                    status,
                )

    def test_invalid_explicit_enum_values_fail_closed(self) -> None:
        for field_name in (
            "item_type",
            "disposition",
            "identification_status",
        ):
            with self.subTest(field_name=field_name):
                record = new_item("invalid_enum").to_dict()
                record[field_name] = "INVALID"
                self.write({"schema_version": 1, "items": [record]})
                collection = self.load()
                self.assertIs(
                    collection.load_state,
                    CollectionLoadState.INVALID_OR_UNSUPPORTED,
                )
                self.assertIn(field_name, collection.load_error)

    def test_unsupported_boolean_and_malformed_v1_envelopes_fail_closed(self) -> None:
        valid_record = new_item("valid").to_dict()
        cases = (
            {"schema_version": 2, "items": [valid_record]},
            {"schema_version": True, "items": [valid_record]},
            {"schema_version": 1},
            {"schema_version": 1, "items": [], "extra": True},
            {"schema_version": 1, "items": {}},
            {"schema_version": 1, "items": [{"id": "missing_contract"}]},
        )
        for payload in cases:
            with self.subTest(payload=payload):
                self.write(payload)
                self.assertIs(
                    self.load().load_state,
                    CollectionLoadState.INVALID_OR_UNSUPPORTED,
                )

    def test_duplicate_ids_and_malformed_json_remain_fail_closed(self) -> None:
        duplicate = new_item("duplicate").to_dict()
        self.write({"schema_version": 1, "items": [duplicate, duplicate]})
        self.assertIs(
            self.load().load_state,
            CollectionLoadState.INVALID_OR_UNSUPPORTED,
        )

        self.path.write_bytes(b"{not-json")
        self.assertIs(
            self.load().load_state,
            CollectionLoadState.INVALID_OR_UNSUPPORTED,
        )

    def test_normal_update_changes_updated_at_without_timing_flakiness(self) -> None:
        collection = self.load()
        with patch("coin_collection.utc_now_rfc3339", return_value=T1):
            item = CoinItem(
                id="coin_timestamp",
                image_path="",
                country="Canada",
                denomination="1 cent",
                year="1964",
                grade="",
                notes="",
                date_added="2026-08-30",
            )
            self.assertEqual(T1, item.updated_at)
            self.assertTrue(collection.add_item(item))

        with patch("coin_collection.utc_now_rfc3339", return_value=T2):
            self.assertTrue(
                collection.update_item("coin_timestamp", {"notes": "updated"})
            )

        self.assertEqual(T2, collection.items[0].updated_at)
        self.assertEqual(T2, self.load().items[0].updated_at)

    def test_enum_updates_remain_typed_and_invalid_values_do_not_write(self) -> None:
        collection = self.load()
        self.assertTrue(collection.add_item(new_item("coin_enum_update")))

        self.assertTrue(
            collection.update_item("coin_enum_update", {"disposition": "KEEP"})
        )
        self.assertIs(collection.items[0].disposition, Disposition.KEEP)
        before = self.path.read_bytes()

        self.assertFalse(
            collection.update_item(
                "coin_enum_update", {"identification_status": "INVALID"}
            )
        )
        self.assertEqual(before, self.path.read_bytes())
        self.assertIs(
            collection.items[0].identification_status,
            IdentificationStatus.IDENTIFIED,
        )

    def test_conditional_mutation_transitions_v0_to_v1_and_sets_timestamp(self) -> None:
        self.write([legacy_record("coin_conditional")])
        collection = self.load()

        with patch("coin_collection.utc_now_rfc3339", return_value=T1):
            result = collection.mutate_fields_conditionally(
                "coin_conditional",
                (
                    ConditionalCollectionFieldChange(
                        "country", "Canada", "France"
                    ),
                ),
            )

        self.assertEqual(("country",), result.applied_fields)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(1, payload["schema_version"])
        self.assertEqual("France", payload["items"][0]["country"])
        self.assertEqual(T1, payload["items"][0]["updated_at"])
        self.assertEqual("COIN", payload["items"][0]["item_type"])


if __name__ == "__main__":
    unittest.main()
