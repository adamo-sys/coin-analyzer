"""Focused tests for capture-import domain models, limits, enums, and errors."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from enum import Enum
import inspect
import unittest

import capture_import.enums as enum_module
import capture_import.errors as error_module
from capture_import.enums import (
    Composition,
    DuplicateDecision,
    ErrorCategory,
    ImageRole,
    ImportPhase,
    ImportRecordOutcome,
    ImportResult,
)
from capture_import.errors import CaptureImportError
from capture_import.limits import (
    MAX_COINS_PER_PACKAGE,
    MAX_DECIMAL_CHARS,
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_SIZE,
    MAX_PACKAGE_SIZE,
    MAX_QUANTITY,
    MAX_STRING_CHARS,
    MISSING_COLLECTION_SENTINEL,
    SUPPORTED_SCHEMA,
    SUPPORTED_SCHEMA_VERSION,
)
from capture_import.models import (
    CollectionBaseline,
    ImportDecision,
    ImportSession,
    PackageCoin,
    PackageImage,
    PackageManifest,
    PackageSession,
    PreviewCoin,
)

NOW = "2026-07-18T14:30:00.000Z"
SHA = "a" * 64


def canonical_manifest_payload() -> dict[str, object]:
    """Format-1.0 fixture derived from Mobile CAPTURE_PACKAGE_SPEC.md."""

    def photo(role: str) -> dict[str, object]:
        return {
            "path": f"images/0000-{role}.jpg",
            "original_name": f"0000-{role}.jpg",
            "mime_type": "image/jpeg",
            "byte_length": 1024,
            "width": 640,
            "height": 480,
            "captured_at": NOW,
        }

    return {
        "schema": "coin-analyzer.capture-package",
        "package_version": "1.0",
        "created_by": "Coin Analyzer Mobile Companion",
        "created_with": "0.1.0",
        "exported_at": NOW,
        "session": {
            "id": "session-1",
            "name": "Toronto Coin Show",
            "description": "July 2026",
            "session_date": "2026-07-18",
            "created_at": NOW,
            "updated_at": NOW,
        },
        "coins": [
            {
                "id": "coin-1",
                "position": 0,
                "country": "Canada",
                "denomination": "1 Dollar",
                "year": "1967",
                "mint": "Royal Canadian Mint",
                "purchase_price": "24.50",
                "purchase_currency": "CAD",
                "seller": "Toronto Coin Expo",
                "purchase_date": "2026-07-18",
                "notes": "Test fixture",
                "quantity": 1,
                "composition": "silver",
                "is_bullion": False,
                "asw_troy_ounces": "0.6",
                "photos": {"front": photo("front"), "reverse": photo("reverse")},
                "created_at": NOW,
                "updated_at": NOW,
            }
        ],
    }


def make_image(
    role: ImageRole,
    *,
    byte_length: int = 1024,
    width: int = 640,
    height: int = 480,
) -> PackageImage:
    extension = ".png" if role is ImageRole.EDGE else ".jpg"
    return PackageImage(
        role=role,
        path=f"images/0000-{role.value}{extension}",
        original_name=f"0000-{role.value}{extension}",
        mime_type="image/png" if extension == ".png" else "image/jpeg",
        byte_length=byte_length,
        width=width,
        height=height,
        captured_at=NOW,
    )


def make_coin(*, coin_id: str = "coin-1", position: int = 0) -> PackageCoin:
    return PackageCoin(
        id=coin_id,
        position=position,
        country="Canada",
        denomination="1 Dollar",
        year="1967",
        mint="Royal Canadian Mint",
        purchase_price=Decimal("24.50"),
        purchase_currency="CAD",
        seller="Toronto Coin Expo",
        purchase_date="2026-07-18",
        notes="Test fixture",
        quantity=1,
        composition=Composition.SILVER,
        is_bullion=False,
        asw_troy_ounces=Decimal("0.6"),
        photos=(make_image(ImageRole.FRONT), make_image(ImageRole.REVERSE)),
        created_at=NOW,
        updated_at=NOW,
    )


def make_manifest(*, coins: tuple[PackageCoin, ...] | None = None) -> PackageManifest:
    return PackageManifest(
        schema=SUPPORTED_SCHEMA,
        package_version=SUPPORTED_SCHEMA_VERSION,
        created_by="Coin Analyzer Mobile Companion",
        created_with="0.1.0",
        exported_at=NOW,
        session=PackageSession(
            id="session-1",
            name="Toronto Coin Show",
            description="July 2026",
            session_date="2026-07-18",
            created_at=NOW,
            updated_at=NOW,
        ),
        coins=(make_coin(),) if coins is None else coins,
    )


def make_import_session(*, byte_length: int = 2048) -> ImportSession:
    coin = make_coin()
    return ImportSession(
        package_basename="Toronto.ca-package",
        package_sha256=SHA,
        package_byte_length=byte_length,
        collection_baseline=CollectionBaseline(SHA, 512),
        preview_coins=(PreviewCoin(coin, (), ()),),
        decisions=(ImportDecision(coin.id, DuplicateDecision.IMPORT_AS_NEW),),
    )


def assert_json_primitives(test: unittest.TestCase, value: object) -> None:
    if isinstance(value, dict):
        test.assertTrue(all(isinstance(key, str) for key in value))
        for item in value.values():
            assert_json_primitives(test, item)
    elif isinstance(value, list):
        for item in value:
            assert_json_primitives(test, item)
    else:
        test.assertIsInstance(value, (str, int, float, bool, type(None)))


class CanonicalContractTests(unittest.TestCase):
    def test_canonical_format_1_manifest_round_trip(self) -> None:
        manifest = PackageManifest.from_dict(canonical_manifest_payload())

        self.assertEqual(manifest, make_manifest())
        self.assertEqual(manifest.to_dict(), canonical_manifest_payload())
        self.assertEqual(manifest.to_dict()["coins"][0]["composition"], "silver")
        self.assertIn("captured_at", manifest.to_dict()["coins"][0]["photos"]["front"])

    def test_captured_at_is_required(self) -> None:
        payload = canonical_manifest_payload()
        del payload["coins"][0]["photos"]["front"]["captured_at"]
        with self.assertRaisesRegex(ValueError, "missing fields"):
            PackageManifest.from_dict(payload)

    def test_package_additive_fields_are_ignored_but_strict_dtos_reject_them(self) -> None:
        payload = canonical_manifest_payload()
        payload["future_root"] = True
        payload["session"]["future_session"] = 1
        payload["coins"][0]["future_coin"] = "ignored"
        payload["coins"][0]["photos"]["front"]["future_photo"] = None
        self.assertEqual(PackageManifest.from_dict(payload), make_manifest())

        strict = CollectionBaseline(SHA, 1).to_dict()
        strict["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            CollectionBaseline.from_dict(strict)

    def test_serialization_is_deterministic_and_json_compatible(self) -> None:
        manifest = make_manifest()
        self.assertEqual(manifest.to_dict(), manifest.to_dict())
        assert_json_primitives(self, manifest.to_dict())


class DtoCoverageTests(unittest.TestCase):
    def test_every_dto_round_trips(self) -> None:
        image = make_image(ImageRole.FRONT)
        coin = make_coin()
        session = make_manifest().session
        manifest = make_manifest()
        baseline = CollectionBaseline(SHA, 1)
        preview = PreviewCoin(coin, ("duplicate evidence",), ("warning",))
        decision = ImportDecision("coin-1", DuplicateDecision.SKIP)
        import_session = make_import_session()

        cases = (
            (PackageImage.from_dict(ImageRole.FRONT, image.to_dict()), image),
            (PackageCoin.from_dict(coin.to_dict()), coin),
            (PackageSession.from_dict(session.to_dict()), session),
            (PackageManifest.from_dict(manifest.to_dict()), manifest),
            (CollectionBaseline.from_dict(baseline.to_dict()), baseline),
            (PreviewCoin.from_dict(preview.to_dict()), preview),
            (ImportDecision.from_dict(decision.to_dict()), decision),
            (ImportSession.from_dict(import_session.to_dict()), import_session),
        )
        for actual, expected in cases:
            with self.subTest(dto=type(expected).__name__):
                self.assertEqual(actual, expected)

    def test_every_dto_is_frozen(self) -> None:
        values = (
            make_image(ImageRole.FRONT),
            make_coin(),
            make_manifest().session,
            make_manifest(),
            CollectionBaseline(SHA, 1),
            PreviewCoin(make_coin()),
            ImportDecision("coin-1", DuplicateDecision.SKIP),
            make_import_session(),
        )
        for value in values:
            with self.subTest(dto=type(value).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, next(iter(value.__dataclass_fields__)), "changed")

    def test_missing_required_fields_fail(self) -> None:
        cases = (
            (PackageSession, make_manifest().session.to_dict(), "name"),
            (PackageCoin, make_coin().to_dict(), "country"),
            (PackageManifest, make_manifest().to_dict(), "created_by"),
            (CollectionBaseline, CollectionBaseline(SHA, 1).to_dict(), "byte_length"),
            (PreviewCoin, PreviewCoin(make_coin()).to_dict(), "warnings"),
            (ImportDecision, ImportDecision("coin-1", DuplicateDecision.SKIP).to_dict(), "decision"),
            (ImportSession, make_import_session().to_dict(), "decisions"),
        )
        for dto, payload, field in cases:
            with self.subTest(dto=dto.__name__, field=field):
                del payload[field]
                with self.assertRaisesRegex(ValueError, "missing fields"):
                    dto.from_dict(payload)


class EnumAndErrorTests(unittest.TestCase):
    def test_every_enum_member_round_trips(self) -> None:
        enum_types = (
            ImportPhase,
            DuplicateDecision,
            ImportRecordOutcome,
            ImportResult,
            ErrorCategory,
            ImageRole,
            Composition,
        )
        for enum_type in enum_types:
            for member in enum_type:
                with self.subTest(enum=enum_type.__name__, member=member.name):
                    self.assertIs(enum_type(member.value), member)

    def test_incomplete_unconditional_transition_table_is_not_public(self) -> None:
        self.assertFalse(hasattr(enum_module, "LEGAL_PHASE_TRANSITIONS"))

    def test_every_typed_exception_has_category_and_path_safe_message(self) -> None:
        expected_categories = {
            "ArchiveNameCollision": ErrorCategory.ARCHIVE_NAME_COLLISION,
            "AuditFinalizationPending": ErrorCategory.AUDIT_FINALIZATION_PENDING,
            "CollectionChanged": ErrorCategory.COLLECTION_CHANGED,
            "CollectionCommitFailed": ErrorCategory.COLLECTION_COMMIT_FAILED,
            "DuplicatePackage": ErrorCategory.DUPLICATE_PACKAGE,
            "EmptyPackage": ErrorCategory.EMPTY_PACKAGE,
            "ImageCollision": ErrorCategory.MANAGED_PATH_COLLISION,
            "ImageCopyFailed": ErrorCategory.COPYING_IMAGES_FAILED,
            "ImportLocked": ErrorCategory.IMPORT_LOCKED,
            "InvalidManifest": ErrorCategory.MANIFEST_INVALID,
            "InvalidMedia": ErrorCategory.MEDIA_INVALID,
            "JournalCorrupt": ErrorCategory.JOURNAL_CORRUPT,
            "ManifestMissing": ErrorCategory.MANIFEST_MISSING,
            "MediaMissing": ErrorCategory.MEDIA_MISSING,
            "PackageChanged": ErrorCategory.PACKAGE_CHANGED,
            "PackageNotFound": ErrorCategory.PACKAGE_NOT_FOUND,
            "PackageNotZip": ErrorCategory.PACKAGE_NOT_ZIP,
            "PackageTooLarge": ErrorCategory.PACKAGE_LIMIT_EXCEEDED,
            "PreviewStale": ErrorCategory.PREVIEW_STALE,
            "RecoveryRequired": ErrorCategory.RECOVERY_REQUIRED,
            "RollbackFailed": ErrorCategory.ROLLBACK_FAILED,
            "SnapshotFailed": ErrorCategory.SNAPSHOT_FAILED,
            "SnapshotRecoveryRequired": ErrorCategory.SNAPSHOT_RECOVERY_REQUIRED,
            "UnreferencedArchiveEntry": ErrorCategory.ARCHIVE_ENTRY_UNREFERENCED,
            "UnsafeArchiveEntry": ErrorCategory.ARCHIVE_ENTRY_UNSAFE,
            "UnsupportedVersion": ErrorCategory.UNSUPPORTED_PACKAGE_VERSION,
        }
        exception_types = {
            name: value
            for name, value in inspect.getmembers(error_module, inspect.isclass)
            if issubclass(value, CaptureImportError) and value is not CaptureImportError
        }
        self.assertEqual(set(exception_types), set(expected_categories))
        diagnostics = (
            r"C:\Users\person\private.ca-package",
            "/home/person/private.ca-package",
            "<script>hostile manifest</script>",
        )
        for name, exception_type in exception_types.items():
            self.assertIs(exception_type.category, expected_categories[name])
            for diagnostic in diagnostics:
                with self.subTest(exception=exception_type.__name__, diagnostic=diagnostic):
                    error = exception_type(diagnostic)
                    self.assertEqual(str(error), error.safe_message)
                    self.assertNotIn(diagnostic, str(error))
                    self.assertEqual(error._diagnostic_context, diagnostic)


class NumericBoundaryTests(unittest.TestCase):
    def test_quantity_boundaries_and_non_finite_decimals(self) -> None:
        for valid in (1, MAX_QUANTITY):
            replace(make_coin(), quantity=valid).validate()
        for invalid in (0, MAX_QUANTITY + 1, True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    replace(make_coin(), quantity=invalid).validate()
        for invalid in (Decimal("NaN"), Decimal("Infinity"), Decimal("-1")):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    replace(make_coin(), purchase_price=invalid).validate()

    def test_decimal_string_length_boundary(self) -> None:
        payload = make_coin().to_dict()
        payload["purchase_price"] = "9" * MAX_DECIMAL_CHARS
        PackageCoin.from_dict(payload)
        payload["purchase_price"] = "9" * (MAX_DECIMAL_CHARS + 1)
        with self.assertRaises(ValueError):
            PackageCoin.from_dict(payload)

    def test_string_length_boundary(self) -> None:
        replace(make_coin(), country="C" * MAX_STRING_CHARS).validate()
        with self.assertRaises(ValueError):
            replace(make_coin(), country="C" * (MAX_STRING_CHARS + 1)).validate()

    def test_image_byte_dimension_and_pixel_boundaries(self) -> None:
        for size in (1, MAX_IMAGE_SIZE):
            make_image(ImageRole.FRONT, byte_length=size).validate()
        for invalid in (0, MAX_IMAGE_SIZE + 1, True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    make_image(ImageRole.FRONT, byte_length=invalid).validate()
        make_image(ImageRole.FRONT, width=MAX_IMAGE_DIMENSION, height=1).validate()
        make_image(ImageRole.FRONT, width=10_000, height=8_000).validate()
        with self.assertRaises(ValueError):
            make_image(ImageRole.FRONT, width=MAX_IMAGE_DIMENSION + 1).validate()
        with self.assertRaises(ValueError):
            make_image(ImageRole.FRONT, width=10_000, height=8_001).validate()

    def test_package_byte_boundaries(self) -> None:
        for size in (1, MAX_PACKAGE_SIZE - 1, MAX_PACKAGE_SIZE):
            make_import_session(byte_length=size).validate()
        for invalid in (0, -1, MAX_PACKAGE_SIZE + 1, True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    make_import_session(byte_length=invalid).validate()

    def test_coin_and_photo_cardinality_boundaries(self) -> None:
        coins = tuple(
            make_coin(coin_id=f"coin-{index}", position=index)
            for index in range(MAX_COINS_PER_PACKAGE)
        )
        make_manifest(coins=coins).validate()
        with self.assertRaises(ValueError):
            make_manifest(
                coins=coins + (make_coin(coin_id="overflow", position=len(coins)),)
            ).validate()

        replace(
            make_coin(),
            photos=(
                make_image(ImageRole.FRONT),
                make_image(ImageRole.REVERSE),
                make_image(ImageRole.EDGE),
            ),
        ).validate()
        payload = make_coin().to_dict()
        payload["photos"]["oblique"] = payload["photos"]["front"]
        with self.assertRaisesRegex(ValueError, "unsupported photo role"):
            PackageCoin.from_dict(payload)


class DecisionAndIdentityTests(unittest.TestCase):
    def _two_coin_session(self) -> ImportSession:
        coins = (make_coin(), make_coin(coin_id="coin-2", position=1))
        return ImportSession(
            package_basename="Toronto.ca-package",
            package_sha256=SHA,
            package_byte_length=1,
            collection_baseline=CollectionBaseline(SHA, 1),
            preview_coins=tuple(PreviewCoin(coin) for coin in coins),
            decisions=tuple(
                ImportDecision(coin.id, DuplicateDecision.IMPORT_AS_NEW)
                for coin in coins
            ),
        )

    def test_decisions_require_exact_preview_order(self) -> None:
        session = self._two_coin_session()
        session.validate()
        invalid = (
            replace(session, decisions=tuple(reversed(session.decisions))),
            replace(session, decisions=session.decisions[:1]),
            replace(
                session,
                decisions=session.decisions
                + (ImportDecision("extra", DuplicateDecision.SKIP),),
            ),
            replace(session, decisions=(session.decisions[0], session.decisions[0])),
            replace(session, preview_coins=(session.preview_coins[0], session.preview_coins[0])),
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    value.validate()

    def test_hash_timestamp_enum_and_boolean_validation(self) -> None:
        with self.assertRaises(ValueError):
            replace(make_import_session(), package_sha256="A" * 64).validate()
        with self.assertRaises(ValueError):
            replace(make_manifest().session, created_at="2026-07-18 12:00:00Z").validate()
        payload = make_coin().to_dict()
        payload["composition"] = "steel"
        with self.assertRaises(ValueError):
            PackageCoin.from_dict(payload)
        payload = make_coin().to_dict()
        payload["quantity"] = True
        with self.assertRaises(ValueError):
            PackageCoin.from_dict(payload)

    def test_collection_baseline_missing_sentinel_is_exact(self) -> None:
        CollectionBaseline(MISSING_COLLECTION_SENTINEL, 0).validate()
        with self.assertRaises(ValueError):
            CollectionBaseline(MISSING_COLLECTION_SENTINEL, 1).validate()


if __name__ == "__main__":
    unittest.main()
