"""Focused tests for exact-byte collection baselines."""

from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from capture_import.baseline import (
    capture_collection_baseline,
    collection_matches_baseline,
    require_collection_baseline,
)
from capture_import.errors import CollectionChanged
from capture_import.limits import MISSING_COLLECTION_SENTINEL


class CollectionBaselineServiceTests(unittest.TestCase):
    def test_missing_collection_uses_normative_sentinel(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline = capture_collection_baseline(Path(temporary) / "collection.json")
        self.assertEqual(baseline.sha256_or_sentinel, MISSING_COLLECTION_SENTINEL)
        self.assertEqual(baseline.byte_length, 0)

    def test_exact_bytes_are_hashed_without_parsing_or_reserialization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "collection.json"
            raw = b'{\n  "items": [1, 2]\n}\n'
            path.write_bytes(raw)
            baseline = capture_collection_baseline(path, chunk_size=3)
            self.assertEqual(baseline.sha256_or_sentinel, hashlib.sha256(raw).hexdigest())
            self.assertEqual(baseline.byte_length, len(raw))
            path.write_bytes(b'{"items":[1,2]}')
            self.assertFalse(collection_matches_baseline(path, baseline))
            with self.assertRaises(CollectionChanged):
                require_collection_baseline(path, baseline)

    def test_empty_existing_file_is_distinct_from_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "collection.json"
            path.write_bytes(b"")
            baseline = capture_collection_baseline(path)
            self.assertEqual(baseline.sha256_or_sentinel, hashlib.sha256(b"").hexdigest())
            self.assertEqual(baseline.byte_length, 0)

    def test_matching_baseline_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "collection.json"
            path.write_bytes(b"[]")
            baseline = capture_collection_baseline(path)
            self.assertTrue(collection_matches_baseline(path, baseline))
            require_collection_baseline(path, baseline)

    def test_non_regular_collection_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(CollectionChanged):
                capture_collection_baseline(temporary)

    def test_chunk_size_validation_rejects_non_positive_and_boolean(self) -> None:
        for invalid in (0, -1, True, 1.5):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    capture_collection_baseline("missing.json", chunk_size=invalid)
