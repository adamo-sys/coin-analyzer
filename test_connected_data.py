import unittest
from unittest.mock import MagicMock
from enum import Enum
from datetime import datetime

from connected_data import (
    ConnectionType, MatchType, Connection, ConnectedReport,
    CrossReferenceReport, ConnectionSummary, ConnectedContext, ConnectedDataEngine
)


class TestConnectionType(unittest.TestCase):
    """Tests for ConnectionType enum."""
    
    def test_all_connection_types_exist(self):
        """All 12 connection types are present."""
        expected = {
            "PHOTO", "OCR", "GRADING", "INTELLIGENCE", "MARKET",
            "WATCHLIST", "BATCH", "SHOPPING", "WANT_LIST", "ENTRY",
            "DEAL", "ACQUISITION"
        }
        actual = {ct.name for ct in ConnectionType}
        self.assertEqual(expected, actual)
    
    def test_connection_type_values(self):
        """Each enum has correct string value."""
        self.assertEqual(ConnectionType.PHOTO.value, "photo")
        self.assertEqual(ConnectionType.GRADING.value, "grading")
        self.assertEqual(ConnectionType.WANT_LIST.value, "want_list")
    
    def test_connection_type_is_enum(self):
        """ConnectionType is an Enum."""
        self.assertTrue(issubclass(ConnectionType, Enum))
        # Verify auto() was not used (explicit string values)
        self.assertEqual(ConnectionType.PHOTO.value, "photo")


class TestMatchType(unittest.TestCase):
    """Tests for MatchType enum."""
    
    def test_all_match_types_exist(self):
        """All 4 match types are present."""
        expected = {"EXACT", "FUZZY", "DERIVED", "NONE"}
        actual = {mt.name for mt in MatchType}
        self.assertEqual(expected, actual)
    
    def test_match_type_values(self):
        """MatchType values are correct."""
        self.assertEqual(MatchType.EXACT.value, "exact")
        self.assertEqual(MatchType.FUZZY.value, "fuzzy")
        self.assertEqual(MatchType.DERIVED.value, "derived")
        self.assertEqual(MatchType.NONE.value, "none")


class TestConnection(unittest.TestCase):
    """Tests for Connection dataclass."""
    
    def test_basic_connection(self):
        """Can create a Connection with all fields."""
        conn = Connection(
            source_type="photo",
            target_type="grading",
            source_id="p1",
            target_id="g1",
            match_type=MatchType.EXACT,
            match_key="path:/photos/coin1.jpg",
            notes="Exact path match"
        )
        self.assertEqual(conn.source_type, "photo")
        self.assertEqual(conn.target_type, "grading")
        self.assertEqual(conn.match_type, MatchType.EXACT)
    
    def test_connection_defaults(self):
        """Connection defaults for optional fields."""
        conn = Connection(
            source_type="photo",
            target_type="grading",
            source_id="p1",
            target_id="g1",
            match_type=MatchType.FUZZY
        )
        self.assertIsNone(conn.match_key)
        self.assertIsNone(conn.notes)
    
    def test_connection_equality(self):
        """Connections with same fields are equal."""
        c1 = Connection("photo", "grading", "p1", "g1", MatchType.EXACT)
        c2 = Connection("photo", "grading", "p1", "g1", MatchType.EXACT)
        self.assertEqual(c1, c2)


class TestConnectedReport(unittest.TestCase):
    """Tests for ConnectedReport dataclass."""
    
    def test_empty_report(self):
        """Empty report has zero counts."""
        report = ConnectedReport(
            source_type="photo",
            target_type="grading",
            total_source=0,
            total_target=0
        )
        self.assertEqual(report.match_count, 0)
        self.assertEqual(report.match_rate, 0.0)
    
    def test_report_with_connections(self):
        """Report tracks connections and match rate."""
        conn = Connection("photo", "grading", "p1", "g1", MatchType.EXACT)
        report = ConnectedReport(
            source_type="photo",
            target_type="grading",
            total_source=5,
            total_target=3,
            connections=[conn],
            unmatched_sources=["p2", "p3", "p4", "p5"],
            unmatched_targets=["g2", "g3"]
        )
        self.assertEqual(report.match_count, 1)
        self.assertEqual(report.match_rate, 0.2)
        self.assertEqual(len(report.unmatched_sources), 4)
        self.assertEqual(len(report.unmatched_targets), 2)
    
    def test_report_match_rate_zero_sources(self):
        """Match rate is 0.0 when total_source is 0."""
        report = ConnectedReport(
            source_type="photo", target_type="grading",
            total_source=0, total_target=0
        )
        self.assertEqual(report.match_rate, 0.0)
    
    def test_report_default_lists(self):
        """Default lists are empty."""
        report = ConnectedReport(
            source_type="photo", target_type="grading",
            total_source=0, total_target=0
        )
        self.assertEqual(report.connections, [])
        self.assertEqual(report.unmatched_sources, [])
        self.assertEqual(report.unmatched_targets, [])


class TestCrossReferenceReport(unittest.TestCase):
    """Tests for CrossReferenceReport dataclass."""
    
    def test_empty_report(self):
        """Empty report has no sub-reports."""
        report = CrossReferenceReport()
        self.assertEqual(report.reports, [])
        self.assertIsNotNone(report.generated_at)
    
    def test_by_source_target(self):
        """Can lookup report by source/target pair."""
        r1 = ConnectedReport("photo", "grading", 5, 3)
        r2 = ConnectedReport("ocr", "grading", 2, 3)
        report = CrossReferenceReport(reports=[r1, r2])
        
        found = report.by_source_target("photo", "grading")
        self.assertIsNotNone(found)
        self.assertEqual(found.source_type, "photo")
        
        not_found = report.by_source_target("photo", "ocr")
        self.assertIsNone(not_found)
    
    def test_by_source_target_no_reports(self):
        """Lookup returns None when no reports."""
        report = CrossReferenceReport()
        self.assertIsNone(report.by_source_target("photo", "grading"))


class TestConnectionSummary(unittest.TestCase):
    """Tests for ConnectionSummary dataclass."""
    
    def test_default_summary(self):
        """Default summary has all zeros."""
        summary = ConnectionSummary()
        self.assertEqual(summary.total_photos, 0)
        self.assertEqual(summary.photos_linked, 0)
        self.assertEqual(summary.overall_link_rate, 0.0)
    
    def test_overall_link_rate(self):
        """Overall link rate is linked / total."""
        summary = ConnectionSummary(
            total_photos=10, photos_linked=5,
            total_ocr=4, ocr_linked=2,
            total_grading=6, grading_linked=3
        )
        # total = 10 + 4 + 6 = 20; linked = 5 + 2 + 3 = 10; rate = 0.5
        self.assertEqual(summary.overall_link_rate, 0.5)
    
    def test_overall_link_rate_with_zero_sources(self):
        """Grading as target only, so total doesn't include it."""
        summary = ConnectionSummary(
            total_photos=0, photos_linked=0,
        )
        self.assertEqual(summary.overall_link_rate, 0.0)
    
    def test_summary_generated_at(self):
        """Summary has generated timestamp."""
        summary = ConnectionSummary()
        self.assertIsNotNone(summary.generated_at)
        # Should be ISO format string
        self.assertIsInstance(summary.generated_at, str)


class TestConnectedContext(unittest.TestCase):
    """Tests for ConnectedContext dataclass."""
    
    def test_basic_context(self):
        """Can create context with required collection_items."""
        ctx = ConnectedContext(collection_items=[])
        self.assertEqual(ctx.collection_items, [])
        self.assertIsNone(ctx.photo_records)
    
    def test_context_with_all_fields(self):
        """Can create context with all optional fields."""
        ctx = ConnectedContext(
            collection_items=["item1"],
            photo_records=["p1"],
            ocr_reports=["o1"],
            grading_assessments=["g1"],
            market_records=["m1"],
            shopping_candidates=["s1"],
            want_list_intents=["w1"],
            watchlists=["wl1"],
            workflow_statuses=["ws1"],
            batch_candidates=["b1"]
        )
        self.assertEqual(len(ctx.collection_items), 1)
        self.assertEqual(len(ctx.photo_records), 1)
    
    def test_context_to_dict(self):
        """to_dict returns counts for all fields."""
        ctx = ConnectedContext(
            collection_items=["a", "b"],
            photo_records=["p1"],
            ocr_reports=["o1", "o2"]
        )
        d = ctx.to_dict()
        self.assertEqual(d["collection_item_count"], 2)
        self.assertEqual(d["photo_record_count"], 1)
        self.assertEqual(d["ocr_report_count"], 2)
        self.assertEqual(d["grading_assessment_count"], 0)
    
    def test_analysis_context(self):
        """analysis_context returns OCR and grading."""
        ctx = ConnectedContext(
            collection_items=[],
            ocr_reports=["o1"],
            grading_assessments=["g1"]
        )
        ac = ctx.analysis_context
        self.assertEqual(ac["ocr_reports"], ["o1"])
        self.assertEqual(ac["grading_assessments"], ["g1"])
    
    def test_shopping_context(self):
        """shopping_context returns shopping-related data."""
        ctx = ConnectedContext(
            collection_items=[],
            shopping_candidates=["s1"],
            want_list_intents=["w1"],
            watchlists=["wl1"]
        )
        sc = ctx.shopping_context
        self.assertEqual(sc["shopping_candidates"], ["s1"])
        self.assertEqual(sc["want_list_intents"], ["w1"])
        self.assertEqual(sc["watchlists"], ["wl1"])


class TestConnectedDataEngineValidation(unittest.TestCase):
    """Tests for ConnectedDataEngine input validation."""
    
    def setUp(self):
        self.context = ConnectedContext(collection_items=[])
        self.engine = ConnectedDataEngine(self.context)
    
    def test_connect_with_enum_types(self):
        """connect() accepts ConnectionType enum values."""
        # Unsupported pair returns empty report, no error
        report = self.engine.connect(ConnectionType.PHOTO, ConnectionType.DEAL)
        self.assertIsInstance(report, ConnectedReport)
    
    def test_connect_rejects_string_source(self):
        """connect() raises ValueError for string source_type."""
        with self.assertRaises(ValueError) as ctx:
            self.engine.connect("photo", ConnectionType.GRADING)
        self.assertIn("source_type must be a ConnectionType", str(ctx.exception))
    
    def test_connect_rejects_string_target(self):
        """connect() raises ValueError for string target_type."""
        with self.assertRaises(ValueError) as ctx:
            self.engine.connect(ConnectionType.PHOTO, "grading")
        self.assertIn("target_type must be a ConnectionType", str(ctx.exception))
    
    def test_connect_rejects_int_source(self):
        """connect() raises ValueError for int source_type."""
        with self.assertRaises(ValueError) as ctx:
            self.engine.connect(1, ConnectionType.GRADING)
        self.assertIn("source_type must be a ConnectionType", str(ctx.exception))


class TestConnectedDataEngineExactMatch(unittest.TestCase):
    """Tests for exact matching in ConnectedDataEngine."""
    
    def test_photo_to_grading_exact_match(self):
        """Photo to grading exact match by photo path."""
        photo = MagicMock()
        photo.file_path = "/photos/coin1.jpg"
        photo.id = "p1"
        
        grading = MagicMock()
        grading.photo_references = ["/photos/coin1.jpg"]
        grading.id = "g1"
        
        context = ConnectedContext(
            collection_items=[],
            photo_records=[photo],
            grading_assessments=[grading]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.PHOTO, ConnectionType.GRADING)
        self.assertEqual(report.source_type, "photo")
        self.assertEqual(report.target_type, "grading")
        self.assertEqual(report.total_source, 1)
        self.assertEqual(report.total_target, 1)
        self.assertEqual(report.match_count, 1)
        self.assertEqual(report.connections[0].match_type, MatchType.EXACT)
        self.assertEqual(report.connections[0].match_key, "/photos/coin1.jpg")
    
    def test_photo_to_grading_no_match(self):
        """No match when photo paths differ."""
        photo = MagicMock()
        photo.file_path = "/photos/coin1.jpg"
        photo.id = "p1"
        
        grading = MagicMock()
        grading.photo_references = ["/photos/coin2.jpg"]
        grading.id = "g1"
        
        context = ConnectedContext(
            collection_items=[],
            photo_records=[photo],
            grading_assessments=[grading]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.PHOTO, ConnectionType.GRADING)
        self.assertEqual(report.match_count, 0)
        self.assertEqual(len(report.unmatched_sources), 1)
        self.assertEqual(len(report.unmatched_targets), 1)
    
    def test_photo_to_ocr_derived_match(self):
        """Photo to OCR derived match by image path."""
        photo = MagicMock()
        photo.file_path = "/photos/coin1.jpg"
        photo.id = "p1"
        
        ocr = MagicMock()
        ocr.image_path = "/photos/coin1.jpg"
        ocr.id = "o1"
        
        context = ConnectedContext(
            collection_items=[],
            photo_records=[photo],
            ocr_reports=[ocr]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.PHOTO, ConnectionType.OCR)
        self.assertEqual(report.match_count, 1)
        self.assertEqual(report.connections[0].match_type, MatchType.DERIVED)
    
    def test_photo_to_batch_multi_target_match(self):
        """Photo to batch with front/back path matching."""
        photo = MagicMock()
        photo.file_path = "/photos/coin1_front.jpg"
        photo.id = "p1"
        
        batch = MagicMock()
        batch.front_path = "/photos/coin1_front.jpg"
        batch.back_path = "/photos/coin1_back.jpg"
        batch.id = "b1"
        
        context = ConnectedContext(
            collection_items=[],
            photo_records=[photo],
            batch_candidates=[batch]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.PHOTO, ConnectionType.BATCH)
        self.assertEqual(report.match_count, 1)
        self.assertEqual(report.connections[0].match_type, MatchType.EXACT)
    
    def test_batch_to_grading_exact_by_linked_id(self):
        """Batch to grading exact match by grading_assessment_id."""
        batch = MagicMock()
        batch.id = "b1"
        batch.grading_assessment_id = "g1"
        batch.country = "USA"
        batch.denomination = "1 Dollar"
        batch.year = "1921"
        
        grading = MagicMock()
        grading.id = "g1"
        grading.country = "USA"
        grading.denomination = "1 Dollar"
        grading.year = "1921"
        
        context = ConnectedContext(
            collection_items=[],
            batch_candidates=[batch],
            grading_assessments=[grading]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.BATCH, ConnectionType.GRADING)
        self.assertEqual(report.match_count, 1)
        self.assertEqual(report.connections[0].match_type, MatchType.EXACT)
        self.assertEqual(report.connections[0].match_key, "grading_assessment_id:g1")


class TestConnectedDataEngineFuzzyMatch(unittest.TestCase):
    """Tests for fuzzy matching in ConnectedDataEngine (exact year only)."""
    
    def test_ocr_to_grading_fuzzy_match(self):
        """OCR to grading fuzzy match by country/denom/year."""
        ocr = MagicMock()
        ocr.id = "o1"
        ocr.country = "USA"
        ocr.denomination = "1 Dollar"
        ocr.year = "1921"
        
        grading = MagicMock()
        grading.id = "g1"
        grading.country = "USA"
        grading.denomination = "1 Dollar"
        grading.year = "1921"
        grading.ocr_source = None
        
        # OCR reports wrap candidates
        ocr_report = MagicMock()
        ocr_report.candidates = [ocr]
        
        context = ConnectedContext(
            collection_items=[],
            ocr_reports=[ocr_report],
            grading_assessments=[grading]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.OCR, ConnectionType.GRADING)
        self.assertEqual(report.match_count, 1)
        self.assertEqual(report.connections[0].match_type, MatchType.FUZZY)
        self.assertEqual(report.connections[0].match_key, "usa:1 dollar:1921")
    
    def test_ocr_to_grading_no_match_different_year(self):
        """No fuzzy match when year differs."""
        ocr = MagicMock()
        ocr.id = "o1"
        ocr.country = "USA"
        ocr.denomination = "1 Dollar"
        ocr.year = "1921"
        
        grading = MagicMock()
        grading.id = "g1"
        grading.country = "USA"
        grading.denomination = "1 Dollar"
        grading.year = "1922"  # Different year
        grading.ocr_source = None
        
        ocr_report = MagicMock()
        ocr_report.candidates = [ocr]
        
        context = ConnectedContext(
            collection_items=[],
            ocr_reports=[ocr_report],
            grading_assessments=[grading]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.OCR, ConnectionType.GRADING)
        self.assertEqual(report.match_count, 0)
    
    def test_ocr_to_entry_fuzzy_match(self):
        """OCR to entry fuzzy match by country/denom/year."""
        ocr = MagicMock()
        ocr.id = "o1"
        ocr.country = "USA"
        ocr.denomination = "1 Dollar"
        ocr.year = "1921"
        
        entry = MagicMock()
        entry.id = "e1"
        entry.country = "USA"
        entry.denomination = "1 Dollar"
        entry.year = "1921"
        
        ocr_report = MagicMock()
        ocr_report.candidates = [ocr]
        
        workflow = MagicMock()
        workflow.entry_candidates = [entry]
        
        context = ConnectedContext(
            collection_items=[],
            ocr_reports=[ocr_report],
            workflow_statuses=[workflow]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.OCR, ConnectionType.ENTRY)
        self.assertEqual(report.match_count, 1)
        self.assertEqual(report.connections[0].match_type, MatchType.FUZZY)
    
    def test_intelligence_to_shopping_fuzzy_match(self):
        """Intelligence to shopping fuzzy match by country/denom/year."""
        intel = MagicMock()
        intel.id = "i1"
        intel.country = "USA"
        intel.denomination = "1 Dollar"
        intel.year = "1921"
        
        shopping = MagicMock()
        shopping.id = "s1"
        shopping.country = "USA"
        shopping.denomination = "1 Dollar"
        shopping.year = "1921"
        
        context = ConnectedContext(
            collection_items=[],
            want_list_intents=[intel],
            shopping_candidates=[shopping]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.INTELLIGENCE, ConnectionType.SHOPPING)
        self.assertEqual(report.match_count, 1)
        self.assertEqual(report.connections[0].match_type, MatchType.FUZZY)
    
    def test_intelligence_to_want_list_fuzzy_match(self):
        """Intelligence to want list fuzzy match."""
        intel = MagicMock()
        intel.id = "i1"
        intel.country = "USA"
        intel.denomination = "1 Dollar"
        intel.year = "1921"
        
        # Single item in want_list_intents matches itself
        context = ConnectedContext(
            collection_items=[],
            want_list_intents=[intel]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.INTELLIGENCE, ConnectionType.WANT_LIST)
        self.assertEqual(report.match_count, 1)


class TestConnectedDataEngineDerivedMatch(unittest.TestCase):
    """Tests for derived matching in ConnectedDataEngine."""
    
    def test_ocr_to_grading_derived_by_ocr_source(self):
        """OCR to grading derived match when grading has ocr_source."""
        ocr = MagicMock()
        ocr.id = "o1"
        ocr.country = "USA"
        ocr.denomination = "1 Dollar"
        ocr.year = "1921"
        
        grading = MagicMock()
        grading.id = "g1"
        grading.country = "CANADA"  # Different country — no fuzzy match
        grading.denomination = "1 Dollar"
        grading.year = "1921"
        grading.ocr_source = "o1"  # But derived from this OCR
        
        ocr_report = MagicMock()
        ocr_report.candidates = [ocr]
        
        context = ConnectedContext(
            collection_items=[],
            ocr_reports=[ocr_report],
            grading_assessments=[grading]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.OCR, ConnectionType.GRADING)
        # Should have 1 derived match (not fuzzy because country differs)
        self.assertEqual(report.match_count, 1)
        self.assertEqual(report.connections[0].match_type, MatchType.DERIVED)
        self.assertEqual(report.connections[0].match_key, "ocr_source:o1")
    
    def test_batch_to_entry_derived_by_status(self):
        """Batch to entry derived match by approved status."""
        batch = MagicMock()
        batch.id = "b1"
        batch.entry_status = "approved"
        batch.entry_candidate_id = "e1"
        batch.country = "USA"
        batch.denomination = "1 Dollar"
        batch.year = "1921"
        
        entry = MagicMock()
        entry.id = "e1"
        entry.country = "USA"
        entry.denomination = "1 Dollar"
        entry.year = "1921"
        
        workflow = MagicMock()
        workflow.entry_candidates = [entry]
        
        context = ConnectedContext(
            collection_items=[],
            batch_candidates=[batch],
            workflow_statuses=[workflow]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.BATCH, ConnectionType.ENTRY)
        self.assertGreaterEqual(report.match_count, 1)
        derived = [c for c in report.connections if c.match_type == MatchType.DERIVED]
        self.assertEqual(len(derived), 1)
        self.assertEqual(derived[0].match_key, "entry_status:approved")


class TestConnectedDataEngineUnsupportedPairs(unittest.TestCase):
    """Tests for unsupported connection pairs."""
    
    def setUp(self):
        self.context = ConnectedContext(collection_items=[])
        self.engine = ConnectedDataEngine(self.context)
    
    def test_unsupported_pair_returns_empty(self):
        """Unsupported pair returns empty report with zero counts."""
        report = self.engine.connect(ConnectionType.PHOTO, ConnectionType.DEAL)
        self.assertEqual(report.total_source, 0)
        self.assertEqual(report.total_target, 0)
        self.assertEqual(report.match_count, 0)
    
    def test_all_supported_pairs_in_dispatch_table(self):
        """All 12 supported pairs are in _DISPATCH_TABLE."""
        self.assertEqual(len(ConnectedDataEngine._DISPATCH_TABLE), 12)
    
    def test_dispatch_table_keys_are_enums(self):
        """All keys in dispatch table are (ConnectionType, ConnectionType)."""
        for key in ConnectedDataEngine._DISPATCH_TABLE.keys():
            self.assertIsInstance(key[0], ConnectionType)
            self.assertIsInstance(key[1], ConnectionType)


class TestConnectedDataEngineCrossReferenceReport(unittest.TestCase):
    """Tests for generate_cross_reference_report."""
    
    def test_generates_all_pairs(self):
        """generate_cross_reference_report calls all 12 pairs."""
        context = ConnectedContext(collection_items=[])
        engine = ConnectedDataEngine(context)
        
        report = engine.generate_cross_reference_report()
        self.assertEqual(len(report.reports), 12)
        self.assertIsNotNone(report.generated_at)
    
    def test_each_report_has_correct_types(self):
        """Each sub-report has correct source/target types."""
        context = ConnectedContext(collection_items=[])
        engine = ConnectedDataEngine(context)
        
        report = engine.generate_cross_reference_report()
        for r in report.reports:
            self.assertIsInstance(r.source_type, str)
            self.assertIsInstance(r.target_type, str)
            self.assertNotEqual(r.source_type, "")
            self.assertNotEqual(r.target_type, "")
    
    def test_cross_reference_with_data(self):
        """Cross-reference report includes actual matches."""
        photo = MagicMock()
        photo.file_path = "/photos/coin1.jpg"
        photo.id = "p1"
        
        grading = MagicMock()
        grading.photo_references = ["/photos/coin1.jpg"]
        grading.id = "g1"
        
        context = ConnectedContext(
            collection_items=[],
            photo_records=[photo],
            grading_assessments=[grading]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.generate_cross_reference_report()
        photo_grading = report.by_source_target("photo", "grading")
        self.assertIsNotNone(photo_grading)
        self.assertEqual(photo_grading.match_count, 1)


class TestConnectedDataEngineSummary(unittest.TestCase):
    """Tests for generate_summary."""
    
    def test_empty_summary(self):
        """Summary with no data has all zeros."""
        context = ConnectedContext(collection_items=[])
        engine = ConnectedDataEngine(context)
        
        summary = engine.generate_summary()
        self.assertEqual(summary.total_photos, 0)
        self.assertEqual(summary.photos_linked, 0)
        self.assertEqual(summary.overall_link_rate, 0.0)
    
    def test_summary_with_matches(self):
        """Summary reflects actual matches."""
        photo = MagicMock()
        photo.file_path = "/photos/coin1.jpg"
        photo.id = "p1"
        
        grading = MagicMock()
        grading.photo_references = ["/photos/coin1.jpg"]
        grading.id = "g1"
        
        context = ConnectedContext(
            collection_items=[],
            photo_records=[photo],
            grading_assessments=[grading]
        )
        engine = ConnectedDataEngine(context)
        
        summary = engine.generate_summary()
        self.assertEqual(summary.total_photos, 1)
        self.assertEqual(summary.photos_linked, 1)  # Only photo->grading has a match
        # photos_unmatched accumulates across photo reports (0 from photo->grading, 1 from photo->ocr, 1 from photo->batch)
        self.assertEqual(summary.photos_unmatched, 2)
        # Grading is target, so it gets counted from reports
        self.assertGreaterEqual(summary.total_grading, 1)
        self.assertGreaterEqual(summary.grading_linked, 1)
    
    def test_summary_has_timestamp(self):
        """Summary includes generated timestamp."""
        context = ConnectedContext(collection_items=[])
        engine = ConnectedDataEngine(context)
        
        summary = engine.generate_summary()
        self.assertIsNotNone(summary.generated_at)


class TestConnectedDataEngineNullSafety(unittest.TestCase):
    """Tests for null/None safety."""
    
    def test_none_photo_records(self):
        """None photo_records handled gracefully."""
        context = ConnectedContext(
            collection_items=[],
            photo_records=None,
            grading_assessments=[]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.PHOTO, ConnectionType.GRADING)
        self.assertEqual(report.total_source, 0)
        self.assertEqual(report.total_target, 0)
    
    def test_none_grading_assessments(self):
        """None grading_assessments handled gracefully."""
        photo = MagicMock()
        photo.file_path = "/photos/coin1.jpg"
        photo.id = "p1"
        
        context = ConnectedContext(
            collection_items=[],
            photo_records=[photo],
            grading_assessments=None
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.PHOTO, ConnectionType.GRADING)
        self.assertEqual(report.total_source, 1)
        self.assertEqual(report.total_target, 0)
        self.assertEqual(report.match_count, 0)
    
    def test_missing_file_path_attribute(self):
        """Photo without file_path uses fallback."""
        photo = MagicMock()
        photo.file_path = None
        photo.path = "/photos/coin1.jpg"
        photo.id = "p1"
        
        grading = MagicMock()
        grading.photo_references = ["/photos/coin1.jpg"]
        grading.id = "g1"
        
        context = ConnectedContext(
            collection_items=[],
            photo_records=[photo],
            grading_assessments=[grading]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.PHOTO, ConnectionType.GRADING)
        self.assertEqual(report.match_count, 1)
    
    def test_missing_attributes_fall_back_to_id(self):
        """Missing attributes fall back to object id()."""
        bare_obj = object()
        
        context = ConnectedContext(
            collection_items=[bare_obj],
            photo_records=[bare_obj]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.PHOTO, ConnectionType.GRADING)
        # Should not crash, just produce empty report
        self.assertEqual(report.total_source, 1)


class TestConnectedDataEngineKeywordMatch(unittest.TestCase):
    """Tests for keyword matching (watchlist)."""
    
    def test_watchlist_to_deals_keyword_match(self):
        """Watchlist keyword appears in deal title."""
        watchlist = MagicMock()
        watchlist.id = "wl1"
        watchlist.keyword = " Morgan Dollar"
        watchlist.name = None
        
        deal = MagicMock()
        deal.id = "d1"
        deal.title = "1921 Morgan Dollar for sale"
        deal.description = "Nice condition"
        
        workflow = MagicMock()
        workflow.deal_candidates = [deal]
        
        context = ConnectedContext(
            collection_items=[],
            watchlists=[watchlist],
            workflow_statuses=[workflow]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.WATCHLIST, ConnectionType.DEAL)
        self.assertEqual(report.match_count, 1)
        self.assertEqual(report.connections[0].match_type, MatchType.FUZZY)
        self.assertEqual(report.connections[0].match_key, "keyword:morgan dollar")
    
    def test_watchlist_to_shopping_keyword_match(self):
        """Watchlist keyword appears in shopping candidate."""
        watchlist = MagicMock()
        watchlist.id = "wl1"
        watchlist.keyword = "Peace Dollar"
        watchlist.name = None
        
        shopping = MagicMock()
        shopping.id = "s1"
        shopping.title = "1922 Peace Dollar"
        shopping.country = "USA"
        shopping.denomination = "1 Dollar"
        
        context = ConnectedContext(
            collection_items=[],
            watchlists=[watchlist],
            shopping_candidates=[shopping]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.WATCHLIST, ConnectionType.SHOPPING)
        self.assertEqual(report.match_count, 1)
        self.assertEqual(report.connections[0].match_type, MatchType.FUZZY)


class TestConnectedDataEngineMarketMatch(unittest.TestCase):
    """Tests for market to acquisition matching."""
    
    def test_market_to_acquisition_fuzzy_match(self):
        """Market to acquisition fuzzy match by country/denomination."""
        market = MagicMock()
        market.id = "m1"
        market.country = "USA"
        market.denomination = "1 Dollar"
        market.year = "1921"
        
        acq = MagicMock()
        acq.id = "a1"
        acq.country = "USA"
        acq.denomination = "1 Dollar"
        acq.year = "1922"
        
        context = ConnectedContext(
            collection_items=[],
            market_records=[market],
            shopping_candidates=[acq]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.MARKET, ConnectionType.ACQUISITION)
        self.assertEqual(report.match_count, 1)
        self.assertEqual(report.connections[0].match_type, MatchType.FUZZY)


class TestConnectedDataEngineEdgeCases(unittest.TestCase):
    """Tests for edge cases."""
    
    def test_multiple_sources_match_one_target(self):
        """Multiple photos can match one grading (all references)."""
        photo1 = MagicMock()
        photo1.file_path = "/photos/coin1_front.jpg"
        photo1.id = "p1"
        
        photo2 = MagicMock()
        photo2.file_path = "/photos/coin1_back.jpg"
        photo2.id = "p2"
        
        grading = MagicMock()
        grading.photo_references = ["/photos/coin1_front.jpg", "/photos/coin1_back.jpg"]
        grading.id = "g1"
        
        context = ConnectedContext(
            collection_items=[],
            photo_records=[photo1, photo2],
            grading_assessments=[grading]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.PHOTO, ConnectionType.GRADING)
        self.assertEqual(report.match_count, 2)
        self.assertEqual(len(report.unmatched_sources), 0)
    
    def test_duplicate_connections_not_added(self):
        """Batch to grading doesn't duplicate exact+fuzzy connections."""
        batch = MagicMock()
        batch.id = "b1"
        batch.grading_assessment_id = "g1"
        batch.country = "USA"
        batch.denomination = "1 Dollar"
        batch.year = "1921"
        
        grading = MagicMock()
        grading.id = "g1"
        grading.country = "USA"
        grading.denomination = "1 Dollar"
        grading.year = "1921"
        
        context = ConnectedContext(
            collection_items=[],
            batch_candidates=[batch],
            grading_assessments=[grading]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.BATCH, ConnectionType.GRADING)
        # Should have exactly 1 connection (exact), not 2 (exact + fuzzy)
        self.assertEqual(report.match_count, 1)
    
    def test_empty_lists_return_zero_counts(self):
        """All empty lists produce zero counts."""
        context = ConnectedContext(
            collection_items=[],
            photo_records=[],
            grading_assessments=[],
            ocr_reports=[],
            batch_candidates=[]
        )
        engine = ConnectedDataEngine(context)
        
        report = engine.connect(ConnectionType.PHOTO, ConnectionType.GRADING)
        self.assertEqual(report.total_source, 0)
        self.assertEqual(report.total_target, 0)
        self.assertEqual(report.match_count, 0)


# ---------------------------------------------------------------------------
# Phase 4: Reporting tests
# ---------------------------------------------------------------------------

class TestConnectedDataEngineReporting(unittest.TestCase):
    """Tests for format_markdown and generate_gap_summary."""

    def test_format_markdown_empty_report(self):
        """Empty report formats gracefully."""
        engine = ConnectedDataEngine(ConnectedContext(collection_items=[]))
        cross_ref = engine.generate_cross_reference_report()
        md = engine.format_markdown(cross_ref)
        self.assertIn("# Connected Data Cross-Reference Report", md)
        self.assertIn("Generated:", md)

    def test_format_markdown_with_connections(self):
        """Markdown includes connections and gaps."""
        photo = MagicMock()
        photo.file_path = "/photos/coin1.jpg"
        photo.id = "p1"
        
        grading = MagicMock()
        grading.photo_references = ["/photos/coin1.jpg"]
        grading.id = "g1"
        
        context = ConnectedContext(
            collection_items=[],
            photo_records=[photo],
            grading_assessments=[grading]
        )
        engine = ConnectedDataEngine(context)
        cross_ref = engine.generate_cross_reference_report()
        md = engine.format_markdown(cross_ref)
        
        self.assertIn("# Connected Data Cross-Reference Report", md)
        self.assertIn("photo", md)
        self.assertIn("grading", md)
        self.assertIn("p1", md)
        self.assertIn("g1", md)

    def test_generate_gap_summary_empty(self):
        """Empty report produces empty gaps."""
        engine = ConnectedDataEngine(ConnectedContext(collection_items=[]))
        cross_ref = engine.generate_cross_reference_report()
        gaps = engine.generate_gap_summary(cross_ref)
        self.assertEqual(gaps, {})

    def test_generate_gap_summary_with_unmatched(self):
        """Gap summary extracts unmatched items."""
        photo = MagicMock()
        photo.file_path = "/photos/coin1.jpg"
        photo.id = "p1"
        
        # No matching grading
        context = ConnectedContext(
            collection_items=[],
            photo_records=[photo],
            grading_assessments=[]
        )
        engine = ConnectedDataEngine(context)
        cross_ref = engine.generate_cross_reference_report()
        gaps = engine.generate_gap_summary(cross_ref)
        
        self.assertIn("photo", gaps)
        self.assertIn("p1", gaps["photo"])

    def test_export_markdown(self):
        """export_markdown writes to file and returns True."""
        import tempfile
        import os
        
        engine = ConnectedDataEngine(ConnectedContext(collection_items=[]))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.md")
            result = engine.export_markdown(path)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(path))
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("# Connected Data Cross-Reference Report", content)

    def test_export_markdown_with_report(self):
        """export_markdown can accept an existing report."""
        import tempfile
        import os
        
        photo = MagicMock()
        photo.file_path = "/photos/coin1.jpg"
        photo.id = "p1"
        
        grading = MagicMock()
        grading.photo_references = ["/photos/coin1.jpg"]
        grading.id = "g1"
        
        context = ConnectedContext(
            collection_items=[],
            photo_records=[photo],
            grading_assessments=[grading]
        )
        engine = ConnectedDataEngine(context)
        cross_ref = engine.generate_cross_reference_report()
        
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.md")
            result = engine.export_markdown(path, cross_ref)
            self.assertTrue(result)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("p1", content)


if __name__ == "__main__":
    unittest.main()
