from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from typing import cast
import unittest

from capture_import.archive import ValidatedArchiveIndex
from capture_import.enums import Composition, ImageRole
from capture_import.media import ValidatedMedia
from capture_import.models import PackageCoin, PackageImage, PackageManifest, PackageSession
from capture_import.package import ValidatedCapturePackage
from capture_package_reference_adapter import adapt_capture_package_reference
from multimodal_evidence_references import (
    CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
    MultimodalEvidenceKind,
    MultimodalEvidenceReference,
)
from structured_metadata_reference_adapter import (
    StructuredMetadataRecordNotFound,
    StructuredMetadataReferenceAdaptation,
    adapt_structured_metadata_reference,
)


_TIMESTAMP = "2026-09-06T00:00:00Z"
_DIGEST = "a" * 64


def _image(role: ImageRole, path: str) -> PackageImage:
    return PackageImage(
        role=role,
        path=path,
        original_name=path.rsplit("/", 1)[-1],
        mime_type="image/jpeg",
        byte_length=100,
        width=100,
        height=100,
        captured_at=_TIMESTAMP,
    )


def _coin(identifier: str = "coin-1", position: int = 0) -> PackageCoin:
    return PackageCoin(
        id=identifier,
        position=position,
        country="Canada",
        denomination="1 dollar",
        year="1967",
        mint="",
        purchase_price=Decimal("10.00"),
        purchase_currency="CAD",
        seller="Synthetic Seller",
        purchase_date="2026-09-01",
        notes="Synthetic structured metadata fixture",
        quantity=1,
        composition=Composition.NICKEL,
        is_bullion=False,
        asw_troy_ounces=None,
        photos=(
            _image(ImageRole.FRONT, f"media/{identifier}-front.jpg"),
            _image(ImageRole.REVERSE, f"media/{identifier}-reverse.jpg"),
        ),
        created_at=_TIMESTAMP,
        updated_at=_TIMESTAMP,
    )


def _package(*coins: PackageCoin) -> ValidatedCapturePackage:
    if not coins:
        coins = (_coin(),)
    manifest = PackageManifest(
        schema="coin-analyzer.capture-package",
        package_version="1.0",
        created_by="synthetic-test",
        created_with="unit-test",
        exported_at=_TIMESTAMP,
        session=PackageSession(
            id="session-1",
            name="Synthetic",
            description="",
            session_date="2026-09-06",
            created_at=_TIMESTAMP,
            updated_at=_TIMESTAMP,
        ),
        coins=coins,
    )
    manifest.validate()
    return ValidatedCapturePackage(
        package_basename="synthetic.ca-package",
        package_sha256=_DIGEST,
        package_byte_length=1234,
        archive=cast(ValidatedArchiveIndex, object()),
        manifest=manifest,
        media=cast(tuple[ValidatedMedia, ...], ()),
    )


def _package_adaptation(source: ValidatedCapturePackage | None = None):
    return adapt_capture_package_reference(
        source or _package(),
        reference_id="package-ref-1",
        source_id="capture-source-1",
    )


class StructuredMetadataReferenceAdapterTests(unittest.TestCase):
    def test_maps_validated_package_coin_to_structured_metadata(self) -> None:
        package = _package_adaptation()
        result = adapt_structured_metadata_reference(
            package,
            source_coin_id="coin-1",
            reference_id="metadata-ref-1",
        )

        self.assertIs(result.source, package.source.manifest.coins[0])
        self.assertEqual(result.reference.kind, MultimodalEvidenceKind.STRUCTURED_METADATA)
        self.assertEqual(result.reference.source_id, "capture-source-1")
        self.assertEqual(result.reference.locator, "coin-1")
        self.assertEqual(result.reference.source_fingerprint, _DIGEST)
        result.validate()

    def test_preserves_structured_source_record_verbatim(self) -> None:
        package = _package_adaptation()
        result = adapt_structured_metadata_reference(
            package,
            source_coin_id="coin-1",
            reference_id="metadata-ref-1",
        )

        self.assertEqual(result.source.country, "Canada")
        self.assertEqual(result.source.denomination, "1 dollar")
        self.assertEqual(result.source.year, "1967")
        self.assertEqual(result.source.notes, "Synthetic structured metadata fixture")

    def test_selects_exact_requested_record_from_multi_coin_manifest(self) -> None:
        package = _package_adaptation(_package(_coin("coin-1", 0), _coin("coin-2", 1)))
        result = adapt_structured_metadata_reference(
            package,
            source_coin_id="coin-2",
            reference_id="metadata-ref-2",
        )

        self.assertEqual(result.source.id, "coin-2")
        self.assertEqual(result.reference.locator, "coin-2")

    def test_missing_record_fails_closed(self) -> None:
        with self.assertRaises(StructuredMetadataRecordNotFound):
            adapt_structured_metadata_reference(
                _package_adaptation(),
                source_coin_id="missing",
                reference_id="metadata-ref-1",
            )

    def test_empty_source_coin_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            adapt_structured_metadata_reference(
                _package_adaptation(),
                source_coin_id="",
                reference_id="metadata-ref-1",
            )

    def test_non_package_adaptation_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            adapt_structured_metadata_reference(  # type: ignore[arg-type]
                object(),
                source_coin_id="coin-1",
                reference_id="metadata-ref-1",
            )

    def test_invalid_manifest_is_rejected_before_mapping(self) -> None:
        valid = _package()
        invalid_coin = replace(valid.manifest.coins[0], country="")
        invalid_manifest = replace(valid.manifest, coins=(invalid_coin,))
        invalid = replace(valid, manifest=invalid_manifest)
        package = adapt_capture_package_reference(
            invalid,
            reference_id="package-ref-1",
            source_id="capture-source-1",
        )

        with self.assertRaises(ValueError):
            adapt_structured_metadata_reference(
                package,
                source_coin_id="coin-1",
                reference_id="metadata-ref-1",
            )

    def test_reference_is_immutable(self) -> None:
        result = adapt_structured_metadata_reference(
            _package_adaptation(),
            source_coin_id="coin-1",
            reference_id="metadata-ref-1",
        )
        with self.assertRaises(FrozenInstanceError):
            result.reference.locator = "other"  # type: ignore[misc]

    def test_nonexistent_package_locator_does_not_require_filesystem_access(self) -> None:
        source = replace(_package(), package_basename="definitely-not-on-disk.ca-package")
        package = _package_adaptation(source)
        result = adapt_structured_metadata_reference(
            package,
            source_coin_id="coin-1",
            reference_id="metadata-ref-1",
        )
        self.assertEqual(result.source.id, "coin-1")

    def test_inconsistent_kind_is_rejected(self) -> None:
        package = _package_adaptation()
        source = package.source.manifest.coins[0]
        reference = MultimodalEvidenceReference(
            schema_version=CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
            reference_id="metadata-ref-1",
            kind=MultimodalEvidenceKind.OCR_TEXT,
            source_id=package.reference.source_id,
            locator=source.id,
            source_fingerprint=_DIGEST,
        )
        result = StructuredMetadataReferenceAdaptation(package, source, reference)
        with self.assertRaises(ValueError):
            result.validate()

    def test_inconsistent_locator_is_rejected(self) -> None:
        package = _package_adaptation()
        source = package.source.manifest.coins[0]
        reference = MultimodalEvidenceReference(
            schema_version=CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
            reference_id="metadata-ref-1",
            kind=MultimodalEvidenceKind.STRUCTURED_METADATA,
            source_id=package.reference.source_id,
            locator="other-coin",
            source_fingerprint=_DIGEST,
        )
        result = StructuredMetadataReferenceAdaptation(package, source, reference)
        with self.assertRaises(ValueError):
            result.validate()

    def test_inconsistent_package_lineage_is_rejected(self) -> None:
        package = _package_adaptation()
        source = package.source.manifest.coins[0]
        reference = MultimodalEvidenceReference(
            schema_version=CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
            reference_id="metadata-ref-1",
            kind=MultimodalEvidenceKind.STRUCTURED_METADATA,
            source_id="different-source",
            locator=source.id,
            source_fingerprint="b" * 64,
        )
        result = StructuredMetadataReferenceAdaptation(package, source, reference)
        with self.assertRaises(ValueError):
            result.validate()


if __name__ == "__main__":
    unittest.main()
