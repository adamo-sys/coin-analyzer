"""Strict JSON and format 1.0 manifest parser tests."""

from __future__ import annotations

import json
import unittest

from capture_import.errors import EmptyPackage, InvalidManifest, PackageTooLarge, UnsupportedVersion
from capture_import.manifest import CapturePackageManifestParser
from capture_import.validation_limits import ValidationLimits
from tests.capture_package_fixtures import manifest_dict


class CapturePackageManifestParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = CapturePackageManifestParser()

    def encode(self, value: object) -> bytes:
        return json.dumps(value, separators=(",", ":")).encode("utf-8")

    def test_parses_exact_contract_and_bounded_additive_fields(self) -> None:
        value = manifest_dict()
        value["future"] = {"bounded": "ignored"}
        result = self.parser.parse(self.encode(value))
        self.assertEqual(result.package_version, "1.0")
        self.assertEqual(result.coins[0].purchase_currency, "CAD")

    def test_rejects_encoding_bom_malformed_duplicate_and_non_object(self) -> None:
        payloads = (
            b"\xff",
            b"\xef\xbb\xbf{}",
            b"{",
            b'{"schema":"a","schema":"b"}',
            b"[]",
            b'{"number":NaN}',
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(InvalidManifest):
                    self.parser.parse(payload)

    def test_rejects_unknown_schema_version_and_empty_package(self) -> None:
        value = manifest_dict()
        value["schema"] = "other"
        with self.assertRaises(UnsupportedVersion):
            self.parser.parse(self.encode(value))
        value = manifest_dict()
        value["package_version"] = "2.0"
        with self.assertRaises(UnsupportedVersion):
            self.parser.parse(self.encode(value))
        value = manifest_dict()
        value["coins"] = []
        with self.assertRaises(EmptyPackage):
            self.parser.parse(self.encode(value))
        value = manifest_dict()
        del value["schema"]
        with self.assertRaises(InvalidManifest):
            self.parser.parse(self.encode(value))

    def test_enforces_json_and_coin_budgets(self) -> None:
        value = manifest_dict()
        value["future"] = "x" * 20
        with self.assertRaises(InvalidManifest):
            CapturePackageManifestParser(ValidationLimits(string_chars=10)).parse(
                self.encode(value)
            )
        with self.assertRaises(PackageTooLarge):
            CapturePackageManifestParser(ValidationLimits(manifest_bytes=10)).parse(
                self.encode(manifest_dict())
            )
        value = manifest_dict()
        value["coins"] = value["coins"] * 2  # type: ignore[operator]
        with self.assertRaises(PackageTooLarge):
            CapturePackageManifestParser(ValidationLimits(coins=1)).parse(
                self.encode(value)
            )

    def test_domain_validation_rejects_duplicate_ids_positions_and_bad_scalars(self) -> None:
        value = manifest_dict()
        first = value["coins"][0]  # type: ignore[index]
        value["coins"] = [first, {**first, "position": 1}]  # type: ignore[arg-type]
        with self.assertRaises(InvalidManifest):
            self.parser.parse(self.encode(value))
        for field, invalid in (("quantity", True), ("purchase_price", "1e2"), ("purchase_date", "2026-02-30")):
            with self.subTest(field=field):
                value = manifest_dict()
                value["coins"][0][field] = invalid  # type: ignore[index]
                with self.assertRaises(InvalidManifest):
                    self.parser.parse(self.encode(value))


if __name__ == "__main__":
    unittest.main()
