"""Tests for the v2.1 lightweight persistence layer."""

import json
import os
import tempfile
import unittest

from legacy_portfolio_importer import LegacyWantListIntent
from market_awareness import (
    AuctionRecord,
    MarketAwarenessEngine,
    ObservedPriceRecord,
    PurchaseRecord,
    SaleRecord,
)
from persistence_manager import AppState, PersistenceManager
from photo_vault import PhotoRecord
from session_context import LoadedCollectionContext, LoadedWantListContext, SessionContext
from smart_shopping_assistant import ShoppingCandidate


def make_manager(temp_dir):
    return PersistenceManager(state_dir=os.path.join(temp_dir, "collection_data", "app_state"))


def make_intent():
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id="want-1",
        target_coin="Newfoundland 50 cents 1904",
        priority="High",
        target_grade="VF-20",
        budget=150,
        why_wanted="Persistence test",
        status="Active",
        priority_score=80,
    )


class TestPersistenceManager(unittest.TestCase):
    def test_save_empty_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = make_manager(temp_dir)
            result = manager.save_state(AppState())

            self.assertTrue(result.success)
            self.assertTrue(os.path.exists(manager.state_path))

    def test_load_empty_state_when_file_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = make_manager(temp_dir).load_state()

            self.assertTrue(result.success)
            self.assertEqual(result.state.collection_workbook_path, "")
            self.assertTrue(result.warnings)

    def test_save_and_load_session_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = make_manager(temp_dir)
            workbook_path = os.path.join(temp_dir, "portfolio.xlsx")
            with open(workbook_path, "w", encoding="utf-8") as handle:
                handle.write("placeholder")
            context = SessionContext(
                loaded_collection=LoadedCollectionContext(
                    source_path=workbook_path,
                    item_count=3,
                    rows_found=4,
                    importable_count=3,
                    loaded_at="2026-06-18 12:00:00",
                ),
                loaded_want_list=LoadedWantListContext(
                    source_path=workbook_path,
                    want_list_count=1,
                    intents=[make_intent()],
                    rows_found=1,
                    loaded_at="2026-06-18 12:00:00",
                ),
                last_loaded_at="2026-06-18 12:00:00",
                load_status="Loaded",
            )

            manager.save_state(manager.create_state(session_context=context))
            loaded = manager.load_state()

            self.assertTrue(loaded.success)
            self.assertEqual(loaded.state.collection_workbook_path, workbook_path)
            self.assertEqual(loaded.state.session_context.loaded_collection.item_count, 3)
            self.assertEqual(loaded.state.session_context.loaded_want_list.want_list_count, 1)
            self.assertEqual(loaded.state.session_context.loaded_want_list.intents[0].target_coin, "Newfoundland 50 cents 1904")

    def test_save_and_load_market_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = make_manager(temp_dir)
            market = MarketAwarenessEngine(
                observations=[ObservedPriceRecord("NF 20c", "Newfoundland", "20 cents", "1900", "VF-20", 25, 3, "eBay", linked_photo_ids=["p1"])],
                purchases=[PurchaseRecord("Canada dime", 10, 2, seller="Dealer")],
                sales=[SaleRecord("World coin", 7, 1, buyer_source="Local")],
                auctions=[AuctionRecord("NF 50c", 100, 120, "Lost")],
            )

            manager.save_state(manager.create_state(market_awareness_engine=market))
            loaded = manager.load_state()

            self.assertEqual(len(loaded.state.market_awareness.observations), 1)
            self.assertEqual(loaded.state.market_awareness.observations[0].linked_photo_ids, ["p1"])
            self.assertEqual(len(loaded.state.market_awareness.purchases), 1)
            self.assertEqual(len(loaded.state.market_awareness.sales), 1)
            self.assertEqual(loaded.state.market_awareness.auctions[0].auction_result, "Lost")

    def test_save_and_load_photo_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = make_manager(temp_dir)
            photos = [
                PhotoRecord(
                    file_path="coin_photos/collection/Newfoundland/1900.jpg",
                    photo_type="Collection Photo",
                    linked_collection_item_id="1",
                    linked_coin_name="Newfoundland 20 cents 1900",
                    pcgs_number="12345",
                )
            ]

            manager.save_state(manager.create_state(photo_records=photos))
            loaded = manager.load_state()

            self.assertEqual(len(loaded.state.photo_records), 1)
            self.assertEqual(loaded.state.photo_records[0].pcgs_number, "12345")

    def test_save_and_load_shopping_candidates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = make_manager(temp_dir)
            candidates = [
                ShoppingCandidate(
                    item_name="Newfoundland 50 cents 1904",
                    asking_price=100,
                    shipping=5,
                    source="Manual",
                    photo_reference_ids=["photo-1"],
                )
            ]

            manager.save_state(manager.create_state(shopping_candidates=candidates))
            loaded = manager.load_state()

            self.assertEqual(len(loaded.state.shopping_candidates), 1)
            self.assertEqual(loaded.state.shopping_candidates[0].total_cost, 105)
            self.assertEqual(loaded.state.shopping_candidates[0].photo_reference_ids, ["photo-1"])

    def test_missing_referenced_workbook_warns_without_crashing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = make_manager(temp_dir)
            payload = AppState(collection_workbook_path=os.path.join(temp_dir, "missing.xlsx")).to_dict()

            validation = manager.validate_state(payload)

            self.assertTrue(validation.success)
            self.assertTrue(any("missing.xlsx" in warning for warning in validation.warnings))

    def test_corrupt_json_handled_gracefully(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = make_manager(temp_dir)
            os.makedirs(manager.state_dir, exist_ok=True)
            with open(manager.state_path, "w", encoding="utf-8") as handle:
                handle.write("{not valid json")

            result = manager.load_state()

            self.assertFalse(result.success)
            self.assertEqual(result.status, "State JSON is corrupt")

    def test_clear_state_removes_file_and_creates_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = make_manager(temp_dir)
            manager.save_state(AppState())

            result = manager.clear_state()

            self.assertTrue(result.success)
            self.assertFalse(os.path.exists(manager.state_path))
            self.assertTrue(os.path.exists(result.backup_path))

    def test_backup_creation_before_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = make_manager(temp_dir)
            manager.save_state(AppState(app_preferences={"theme": "light"}))

            result = manager.save_state(AppState(app_preferences={"theme": "dark"}))

            self.assertTrue(result.success)
            self.assertTrue(os.path.exists(result.backup_path))
            self.assertIn("backups", result.backup_path)

    def test_export_and_import_state_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = make_manager(temp_dir)
            export_path = os.path.join(temp_dir, "state-export.json")
            state = AppState(app_preferences={"last_tool": "Collector Home"})

            export_result = manager.export_state(export_path, state)
            import_result = manager.import_state(export_path)
            loaded = manager.load_state()

            self.assertTrue(export_result.success)
            self.assertTrue(import_result.success)
            self.assertEqual(loaded.state.app_preferences["last_tool"], "Collector Home")

    def test_invalid_schema_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = make_manager(temp_dir)
            invalid_path = os.path.join(temp_dir, "invalid.json")
            with open(invalid_path, "w", encoding="utf-8") as handle:
                json.dump(["not", "object"], handle)

            result = manager.load_state(invalid_path)

            self.assertFalse(result.success)
            self.assertIn("State root must be a JSON object", result.errors)


if __name__ == "__main__":
    unittest.main()
