"""Focused read-only mapping and preview tests for Sprint 4."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import tempfile
import unittest

from coin_collection import PhotoRole

from capture_import.baseline import capture_collection_baseline
from capture_import.enums import DuplicateDecision, ImageRole
from capture_import.models import CollectionBaseline
from capture_import.package import CapturePackageValidator
from capture_import.preview import PackageImportPreviewBuilder
from tests.capture_package_fixtures import image_bytes, manifest_dict, package_bytes


def validate_package(payload: bytes):
    return CapturePackageValidator().validate_stream(
        BytesIO(payload),
        "show.ca-package",
        package_sha256=sha256(payload).hexdigest(),
        package_byte_length=len(payload),
    )


class PackageImportPreviewBuilderTests(unittest.TestCase):
    def test_maps_documented_fields_without_allocating_desktop_resources(self) -> None:
        manifest = manifest_dict()
        coin = manifest["coins"][0]  # type: ignore[index]
        coin["purchase_price"] = "12.5000"
        coin["quantity"] = 3
        coin["mint"] = "Royal Canadian Mint"
        payload = package_bytes(manifest=manifest)
        baseline = CollectionBaseline("a" * 64, 42)

        preview = PackageImportPreviewBuilder().build(
            validate_package(payload), baseline
        )
        proposal = preview.proposals[0]

        self.assertEqual(proposal.country, "Canada")
        self.assertEqual(proposal.denomination, "Dollar")
        self.assertEqual(proposal.year, "1967")
        self.assertEqual(proposal.notes, "Fixture")
        self.assertEqual(proposal.acquisition_date, "2026-07-18")
        self.assertEqual(proposal.purchase_price, Decimal("12.5000"))
        self.assertEqual(proposal.total_cost, Decimal("12.5000"))
        self.assertEqual(proposal.purchase_currency, "CAD")
        self.assertEqual(proposal.purchase_source, "Dealer")
        self.assertEqual(proposal.quantity, 3)
        self.assertEqual(proposal.grade, "")
        self.assertEqual(proposal.reference, "")
        self.assertEqual(proposal.numista_number, "")
        self.assertEqual(proposal.estimate_cad, 0.0)
        self.assertFalse(hasattr(proposal, "desktop_item_id"))
        self.assertEqual(preview.collection_baseline, baseline)
        self.assertEqual(len(preview.decisions), 1)
        self.assertIs(
            preview.decisions[0].decision, DuplicateDecision.IMPORT_AS_NEW
        )

    def test_maps_media_roles_and_unmapped_facts_deterministically(self) -> None:
        manifest = manifest_dict()
        coin = manifest["coins"][0]  # type: ignore[index]
        edge = image_bytes()
        coin["photos"]["edge"] = {  # type: ignore[index]
            "path": "images/edge.png",
            "original_name": "private-edge.heic",
            "mime_type": "image/png",
            "byte_length": len(edge),
            "width": 2,
            "height": 3,
            "captured_at": "2026-07-18T12:00:00Z",
        }
        coin["mint"] = "Ottawa"
        coin["is_bullion"] = True
        payload = package_bytes(
            manifest=manifest,
            extras={"images/edge.png": edge},
        )

        preview = PackageImportPreviewBuilder().build(
            validate_package(payload), CollectionBaseline("b" * 64, 10)
        )
        proposal = preview.proposals[0]

        self.assertEqual(
            tuple(photo.source_role for photo in proposal.photos),
            (ImageRole.FRONT, ImageRole.REVERSE, ImageRole.EDGE),
        )
        self.assertEqual(
            tuple(photo.desktop_role for photo in proposal.photos),
            (PhotoRole.FRONT, PhotoRole.BACK, PhotoRole.EDGE),
        )
        self.assertEqual(
            tuple(photo.is_primary for photo in proposal.photos),
            (True, False, False),
        )
        self.assertEqual(
            tuple(fact.field for fact in proposal.unmapped_facts),
            ("mint", "composition", "is_bullion", "asw_troy_ounces"),
        )
        self.assertEqual(proposal.warnings, tuple(sorted(proposal.warnings)))
        display_text = repr(preview)
        self.assertNotIn("private-source-name.heic", display_text)
        self.assertNotIn("private-edge.heic", display_text)
        self.assertNotIn("C:\\", display_text)

    def test_preview_is_immutable_and_deterministic(self) -> None:
        payload = package_bytes()
        package = validate_package(payload)
        baseline = CollectionBaseline("c" * 64, 11)
        builder = PackageImportPreviewBuilder()

        first = builder.build(package, baseline)
        second = builder.build(package, baseline)

        self.assertEqual(first, second)
        with self.assertRaises(FrozenInstanceError):
            first.session_name = "changed"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            first.proposals[0].country = "changed"  # type: ignore[misc]

    def test_preview_preserves_collection_bytes_exactly(self) -> None:
        payload = package_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            collection_path = Path(temporary) / "collection.json"
            original = b'{"items":[{"id":"existing"}]}\r\n'
            collection_path.write_bytes(original)
            baseline = capture_collection_baseline(collection_path)

            PackageImportPreviewBuilder().build(
                validate_package(payload), baseline
            )

            self.assertEqual(collection_path.read_bytes(), original)
            self.assertEqual(capture_collection_baseline(collection_path), baseline)

    def test_rejects_media_manifest_mismatch(self) -> None:
        payload = package_bytes()
        package = validate_package(payload)
        hostile_media = replace(package.media[0], archive_path="images/other.png")
        hostile = replace(package, media=(hostile_media,) + package.media[1:])

        with self.assertRaisesRegex(ValueError, "does not match manifest"):
            PackageImportPreviewBuilder().build(
                hostile, CollectionBaseline("d" * 64, 12)
            )


if __name__ == "__main__":
    unittest.main()
